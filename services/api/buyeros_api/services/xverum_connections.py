"""Project authority and local revocation; OAuth remains separately provisioned.

External refresh/activation IO must run outside a customer DB transaction.
The provider stages the successor generation; a short DB CAS publishes it.
No local asyncio lock is claimed as multi-process coordination.
"""
from typing import Protocol
from sqlalchemy import delete, select, text, update
from ..api.deps import permission_for_roles
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency
from ..db.icp import Project
from ..db.models import Membership
from ..db.xverum import XverumConnection as Connection, XverumProjectAssignment as Assignment
from ..sales.contracts import ConnectionBinding, ConnectionAssignment, Scope, SecretHandle
from ..providers.xverum_mcp import XverumTransport
from .audit_service import append_audit


def unavailable():
    return ApiError(503, 'XVERUM_CONFIGURATION_REQUIRED', 'Xverum requires administrator configuration')


def not_found():
    return ApiError(404, 'NOT_FOUND', 'connection not available')


def stale():
    return ApiError(409, 'STALE_REVISION', 'connection changed; reload before trying again')


class CredentialProvider(Protocol):
    """Server-only secret service contract, never an HTTP/client/model input.

    Activation requires verified OAuth client registration, refresh, SaaS
    account/workspace delegation, and *durable cross-process* single-flight
    keyed by (connection id, generation). Every resolve rechecks durable
    revocation. refresh stages exactly generation+1, all concurrent callers
    get the same successor, and cannot revive a locally revoked generation.
    revoke_local is idempotent, durable and monotonic through the supplied
    generation (including any successor staged from an older generation).
    Explicit administrator reactivation stages a strictly newer generation.
    It performs no upstream IO.
    A stale successor must never be published or resolved after revocation.

    The adapter owns opaque secret_ref -> credential/account mapping; it must
    verify that binding.id/account_ref match this mapping, not borrow another
    provider's credentials. Application DB holds no token/refresh material.
    An outage in this local secret service cannot prevent DB disconnection.
    Independent processes, cancellation/crash recovery and tombstones must be
    proven by that adapter before live activation. This Protocol is not proof.
    """
    enabled: bool
    durable_generation_singleflight: bool
    async def resolve(self, binding: ConnectionBinding) -> SecretHandle: ...
    async def refresh(self, binding: ConnectionBinding) -> SecretHandle: ...
    async def revoke_local(self, binding: ConnectionBinding) -> None: ...


class DisabledCredentialProvider:
    enabled = False
    durable_generation_singleflight = False

    async def resolve(self, binding):raise unavailable()
    async def refresh(self, binding):raise unavailable()
    async def revoke_local(self, binding):return None


CREDENTIAL_PROVIDER: CredentialProvider = DisabledCredentialProvider()


def provider():
    if not CREDENTIAL_PROVIDER.enabled or not CREDENTIAL_PROVIDER.durable_generation_singleflight:
        raise unavailable()
    return CREDENTIAL_PROVIDER


async def require_schema(session):
    # Catalog guard before querying tenant data.0062 owns the bounded boolean
    # gate and independently checked runtime grants/FORCE-RLS contract.
    ready = (await session.execute(text("""
        SELECT to_regclass('public.xverum_connections') IS NOT NULL
           AND to_regclass('public.xverum_project_assignments') IS NOT NULL
           AND to_regprocedure('public.buyeros_xverum_connections_ready()') IS NOT NULL
    """))).scalar_one()
    if ready is not True:
        raise ApiError(503, 'XVERUM_SCHEMA_NOT_READY', 'Xverum connection schema is not installed')
    # Native SECURITY DEFINER fence pattern: runtime roles never receive direct
    # alembic_version privileges. Task8 installs this exact bounded boolean gate.
    if (await session.execute(text('SELECT public.buyeros_xverum_connections_ready()'))).scalar_one() is not True:
        raise ApiError(503, 'XVERUM_SCHEMA_NOT_READY', 'Xverum connection schema is not ready')


async def authority(session, scope: Scope, operation='listXverumConnections'):
    member = (await session.execute(select(Membership).where(Membership.workspace_id == scope.workspace_id,
        Membership.user_id == scope.actor_id, Membership.active.is_(True)).execution_options(populate_existing=True))).scalar_one_or_none()
    if member is None or not permission_for_roles(member.roles, operation):raise not_found()
    project = (await session.execute(select(Project.id).where(Project.workspace_id == scope.workspace_id,
        Project.id == scope.project_id, Project.status == 'active'))).scalar_one_or_none()
    if project is None:raise not_found()
    await require_schema(session)


async def binding(session, scope, row):
    projects = (await session.execute(select(Assignment.project_id).where(Assignment.workspace_id == scope.workspace_id,
        Assignment.connection_id == row.id).order_by(Assignment.project_id))).scalars().all()
    return ConnectionBinding(id=row.id,generation=row.generation,version=row.version,account_ref=row.account_ref,
        tariff_version=row.tariff_version,project_ids=tuple(projects),status=row.status)


async def load(session, scope, connection_id=None, *, lock=False, admin=False):
    query = select(Connection).where(Connection.workspace_id == scope.workspace_id)
    if connection_id is not None:query = query.where(Connection.id == connection_id)
    if not admin:
        query = query.join(Assignment, (Assignment.workspace_id == Connection.workspace_id) &
            (Assignment.connection_id == Connection.id)).where(Assignment.project_id == scope.project_id)
    if lock:query = query.with_for_update(of=Connection)
    row = (await session.execute(query.execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None:raise not_found()
    return row


async def list_connections(session, scope):
    await authority(session, scope)
    member = (await session.execute(select(Membership).where(Membership.workspace_id == scope.workspace_id,
        Membership.user_id == scope.actor_id, Membership.active.is_(True)))).scalar_one()
    query = select(Connection).where(Connection.workspace_id == scope.workspace_id).order_by(Connection.id).limit(100)
    if 'workspace_admin' not in member.roles:
        query = query.join(Assignment, (Assignment.workspace_id == Connection.workspace_id) &
            (Assignment.connection_id == Connection.id)).where(Assignment.project_id == scope.project_id)
    rows = (await session.execute(query.execution_options(populate_existing=True))).scalars().all()
    return [await binding(session,scope,row) for row in rows]


async def require_xverum_connection(session, scope: Scope) -> ConnectionBinding:
    await authority(session, scope, 'useXverumConnection')
    row = await load(session,scope)
    if row.status != 'connected':raise unavailable()
    return await binding(session,scope,row)


async def require_generation(session, scope, expected):
    current = await require_xverum_connection(session,scope)
    if (current.id, current.generation) != (expected.id, expected.generation):raise stale()
    return current


async def _mutation(session,scope,row,operation,expected_version,key,body):
    outcome = await begin_idempotency(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        operation_id=operation,key=key,body=body,target={'project_id':str(scope.project_id),'connection_id':str(row.id)},
        precondition=f'"{expected_version}"')
    if not outcome.replay and row.version != expected_version:raise stale()
    return outcome


def audit(session,scope,row,operation,outcome):
    append_audit(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        action='xverum.'+operation,entity_type='xverum_connection',entity_id=row.id)
    complete_idempotency(outcome,str(row.id))


async def assign_xverum(session,scope,connection_id,payload:ConnectionAssignment,expected_version,key):
    await authority(session,scope,'assignXverumConnection')
    # Stable ordered project locks serialize competing account assignments.
    ids = sorted(set(payload.project_ids) | {scope.project_id},key=str)
    projects = (await session.execute(select(Project.id).where(Project.workspace_id == scope.workspace_id,
        Project.id.in_(ids),Project.status == 'active').order_by(Project.id).with_for_update())).scalars().all()
    if set(projects) != set(ids):raise not_found()
    row = await load(session,scope,connection_id,lock=True,admin=True)
    outcome = await _mutation(session,scope,row,'assignXverumConnection',expected_version,key,payload.model_dump(mode='json'))
    if not outcome.replay:
        if row.generation != payload.expected_generation:raise stale()
        occupied = (await session.execute(select(Assignment.id).where(Assignment.workspace_id == scope.workspace_id,
            Assignment.project_id.in_(payload.project_ids),Assignment.connection_id != row.id))).first()
        if occupied:raise ApiError(409,'CONNECTION_ASSIGNED','project already has an assigned connection')
        await session.execute(delete(Assignment).where(Assignment.workspace_id == scope.workspace_id,Assignment.connection_id == row.id))
        for project_id in payload.project_ids:
            session.add(Assignment(workspace_id=scope.workspace_id,connection_id=row.id,project_id=project_id))
        row.generation += 1;row.version += 1;row.configured_by = scope.actor_id
        # Assignment invalidates activation. Explicit rotate revalidates schemas.
        row.status = 'configuration_required'
        await session.flush()
        audit(session,scope,row,'assigned',outcome)
    return await binding(session,scope,row)


async def disconnect_xverum(session,scope,expected_version:int,key:str,*,connection_id=None) -> ConnectionBinding:
    from ..execution.sales_tasks import lock_authority
    await lock_authority(session,scope.workspace_id)
    await authority(session,scope,'disconnectXverumConnection')
    row = await load(session,scope,connection_id,lock=True,admin=connection_id is not None)
    outcome = await _mutation(session,scope,row,'disconnectXverumConnection',expected_version,key,{})
    if not outcome.replay:
        row.status = 'disconnected';row.generation += 1;row.version += 1;row.configured_by = scope.actor_id
        await session.flush()
        audit(session,scope,row,'disconnected',outcome)
        from .sales_retention import drain_pending
        # Invalidate admitted generations, not the reusable connection identity.
        await session.execute(text('''INSERT INTO sales_content_tombstones(id,workspace_id,project_id,target_id,kind)
          SELECT gen_random_uuid(),q.workspace_id,q.project_id,r.id,'source' FROM xverum_quotes q
          JOIN xverum_credit_reservations z ON z.workspace_id=q.workspace_id AND z.quote_id=q.id
          JOIN xverum_receipts r ON r.workspace_id=z.workspace_id AND r.reservation_id=z.id
          WHERE q.workspace_id=:ws AND q.connection_id=:connection
          ON CONFLICT(workspace_id,target_id,kind) DO NOTHING'''),
          dict(ws=scope.workspace_id,connection=row.id))
        await drain_pending(session,scope.workspace_id)
    # Local DB tombstone is authoritative. Route calls revoke_local only AFTER
    # this transaction commits; no external/provider await under this row lock.
    return await binding(session,scope,row)


async def revoke_local(binding):
    try:await CREDENTIAL_PROVIDER.revoke_local(binding)
    except Exception:
        # Never undo committed disconnect, expose provider errors or call OAuth.
        # Every subsequent dispatch still reads the DB tombstone.
        return False
    return True


async def prepare_rotation(session,scope,connection_id,expected_version,key,expected_generation):
    await authority(session,scope,'rotateXverumConnection')
    row = await load(session,scope,connection_id,admin=True)
    # Read replay without inserting a record or holding locks across refresh IO.
    from ..db.contact import IdempotencyRecord
    from ..api.idempotency import request_fingerprint
    record = (await session.execute(select(IdempotencyRecord).where(IdempotencyRecord.workspace_id == scope.workspace_id,
        IdempotencyRecord.actor_id == scope.actor_id,IdempotencyRecord.operation_id == 'rotateXverumConnection',
        IdempotencyRecord.key == key))).scalar_one_or_none()
    if not 8 <= len(key) <= 200:raise ApiError(400,'INVALID_REQUEST','invalid Idempotency-Key')
    if record is not None:
        expected = request_fingerprint('rotateXverumConnection',{'project_id':str(scope.project_id),'connection_id':str(row.id)},
            f'"{expected_version}"',{'expected_generation':expected_generation})
        if record.request_hash != expected or record.status != 'completed':
            raise ApiError(409,'IDEMPOTENCY_CONFLICT','mutation key already used')
        return await binding(session,scope,row), True
    if row.version != expected_version or row.generation != expected_generation:raise stale()
    value = await binding(session,scope,row)
    if not value.project_ids:raise unavailable()
    return value, False


async def refresh_credential(expected):
    """NO DB session argument: external IO cannot hold customer row locks here."""
    try:
        handle = await provider().refresh(expected)
        if not isinstance(handle,SecretHandle) or (handle.connection_id,handle.generation) != (expected.id,expected.generation+1):
            raise unavailable()
        await XverumTransport().activate(handle)
        return handle
    except ApiError:raise
    except Exception:raise unavailable() from None


async def publish_rotation(session,scope,expected,handle,expected_version,key):
    await authority(session,scope,'rotateXverumConnection')
    row = await load(session,scope,expected.id,lock=True,admin=True)
    outcome = await _mutation(session,scope,row,'rotateXverumConnection',expected_version,key,{'expected_generation':expected.generation})
    if not outcome.replay:
        if ((row.generation,row.status) != (expected.generation,expected.status)
            or not isinstance(handle,SecretHandle) or (handle.connection_id,handle.generation) != (row.id,row.generation+1)):
            raise stale()
        # WHERE generation/status/version remains explicit for Task8 CAS auditing.
        result = await session.execute(update(Connection).where(Connection.workspace_id == scope.workspace_id,
            Connection.id == expected.id,Connection.generation == expected.generation,
            Connection.version == expected_version,Connection.status == expected.status).values(
                generation=handle.generation,version=expected_version+1,status='connected',configured_by=scope.actor_id))
        if result.rowcount != 1:raise stale()
        await session.refresh(row)
        audit(session,scope,row,'rotated',outcome)
    return await binding(session,scope,row)


async def call_xverum(session_factory,scope,expected,tool,arguments,*,authorize=None):
    """Task9's invocation boundary (after its quote/credit admission).

    session_factory returns a fresh tenant transaction, never a cached snapshot.
    Credential resolve and network IO happen outside customer transactions.
    No auto retry/refresh after tools/call; unknown billing remains Task9's hold.
    """
    async with session_factory() as session:
        current = await require_generation(session,scope,expected)
    try:handle = await provider().resolve(current)
    except ApiError:raise
    except Exception:raise unavailable() from None
    if not isinstance(handle,SecretHandle) or (handle.connection_id,handle.generation) != (current.id,current.generation):raise stale()
    async with session_factory() as session:
        await require_generation(session,scope,current)
    async def before_dispatch():
        async with session_factory() as session:
            await require_generation(session,scope,current)
            if authorize is not None:await authorize(session)
    result = await XverumTransport(before_dispatch=before_dispatch).call(tool,arguments,handle)
    try:
        async with session_factory() as session:
            await require_generation(session,scope,current)
    except Exception:
        from ..providers.xverum_mcp import XverumTransportError
        raise XverumTransportError('tools/call',code='XVERUM_AUTHORITY_CHANGED') from None
    return result
