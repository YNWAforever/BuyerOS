"""Privileged exact principal binding; no email matching, membership grants or cache."""
import uuid
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,StrictInt,StrictStr,TypeAdapter
from sqlalchemy import select,text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from ..api.auth import Principal
from ..api.errors import ApiError
from ..db.models import User,UserIdentity

class IdentityRow(BaseModel):
    model_config=ConfigDict(extra='forbid')
    canonical_user_id:uuid.UUID
    workspace_id:uuid.UUID
    issuer:StrictStr=Field(min_length=1,max_length=255)
    subject:StrictStr=Field(min_length=1,max_length=255)
    proof_kind:Literal['administrator_verified']
    proof_ref:StrictStr=Field(min_length=1,max_length=200)
    reason:StrictStr=Field(min_length=3,max_length=2000)
    expected_version:StrictInt=Field(ge=0,le=2147483646)

def _exact(value,limit):
    if not isinstance(value,str) or not value or len(value)>limit or value!=value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ApiError(422,'INVALID_IDENTITY','invalid identity manifest')
    return value

def parse_identity_manifest(manifest)->list[IdentityRow]:
    if not isinstance(manifest,list) or not 1<=len(manifest)<=100:raise ValueError('manifest requires 1..100 rows')
    rows=TypeAdapter(list[IdentityRow]).validate_python(manifest)
    if len({(row.issuer,row.subject) for row in rows})!=len(rows):raise ValueError('duplicate principals')
    for row in rows:_exact(row.issuer,255);_exact(row.subject,255);_exact(row.proof_ref,200)
    return rows

async def require_identity_writer(session):
    allowed=(await session.execute(text("SELECT has_table_privilege(current_user,'public.user_identities','INSERT') AND has_table_privilege(current_user,'public.user_identities','UPDATE')"))).scalar_one()
    if not allowed:raise ApiError(403,'PERMISSION_DENIED','privileged identity writer required')

async def link_identity(session:AsyncSession,*,user_id:uuid.UUID,issuer:str,subject:str,proof_ref:str,expected_version:int|None=None)->uuid.UUID:
    issuer=_exact(issuer,255);subject=_exact(subject,255);proof_ref=_exact(proof_ref,200)
    if not isinstance(user_id,uuid.UUID) or expected_version is not None and (type(expected_version) is not int or expected_version<0):
        raise ApiError(422,'INVALID_IDENTITY','invalid identity manifest')
    await require_identity_writer(session)
    target=(await session.execute(select(User.id).where(User.id==user_id).with_for_update())).scalar_one_or_none()
    if target is None:raise ApiError(404,'NOT_FOUND','canonical user not found')
    def conflict():raise ApiError(409,'IDENTITY_CONFLICT','identity binding conflict')
    current=(await session.execute(select(UserIdentity).where(UserIdentity.issuer==issuer,UserIdentity.subject==subject).with_for_update())).scalar_one_or_none()
    if current is None:
        if expected_version not in (None,0):conflict()
        created=(await session.execute(insert(UserIdentity).values(issuer=issuer,subject=subject,user_id=user_id,proof_ref=proof_ref).on_conflict_do_nothing(index_elements=['issuer','subject']).returning(UserIdentity.user_id))).scalar_one_or_none()
        if created is not None:return created
        current=(await session.execute(select(UserIdentity).where(UserIdentity.issuer==issuer,UserIdentity.subject==subject).with_for_update())).scalar_one()
    if current.user_id!=user_id or current.status!='active':conflict()
    if expected_version is not None and current.version!=expected_version:
        # Only replay the exact initial receipt, never revive a later/revoked state.
        if not(expected_version==0 and current.version==1 and current.proof_ref==proof_ref):conflict()
    return current.user_id


async def create_canonical_user(session: AsyncSession, *, principal: Principal, proof_ref: str) -> uuid.UUID:
    """Create after external verification, through a privileged writer only.

    This function neither verifies a token nor creates tenant membership. Its
    caller must supply the verified principal. Exact existing bindings win,
    including concurrent first use; revoked identities cannot be recreated.
    """
    issuer = _exact(principal.issuer, 255)
    subject = _exact(principal.subject, 255)
    proof_ref = _exact(proof_ref, 200)
    await require_identity_writer(session)
    query = select(UserIdentity).where(UserIdentity.issuer == issuer, UserIdentity.subject == subject)

    def canonical(identity):
        if identity.status != 'active':
            raise ApiError(409, 'IDENTITY_CONFLICT', 'identity binding conflict')
        return identity.user_id

    current = (await session.execute(query)).scalar_one_or_none()
    if current is not None:
        return canonical(current)
    # Transaction-local proof is metadata, never authority. Runtime roles have
    # no INSERT privilege on users or identities; the trigger preserves the UUID.
    previous = (await session.execute(text("SELECT current_setting('app.identity_proof_ref',true)"))).scalar_one()
    await session.execute(text("SELECT set_config('app.identity_proof_ref',:proof,true)"), {'proof': proof_ref})
    try:
        try:
            async with session.begin_nested():
                user_id = uuid.uuid4()
                await session.execute(insert(User).values(id=user_id, issuer=issuer, subject=subject))
                return user_id
        except IntegrityError as error:
            if getattr(error.orig, 'sqlstate', None) != '23505':
                raise
            # The savepoint removes the losing canonical row. Read the committed
            # winner; never create a second User or reactivate a revoked binding.
            current = (await session.execute(query)).scalar_one_or_none()
            if current is None:
                raise ApiError(409, 'IDENTITY_CONFLICT', 'identity binding conflict') from error
            return canonical(current)
    finally:
        await session.execute(text("SELECT set_config('app.identity_proof_ref',:proof,true)"), {'proof': previous or ''})


async def _reconcile_identity_row(session, row, principal, *, apply):
    import hashlib
    import json
    from ..db.models import Membership
    from ..db.outcomes import AuditEvent
    from .audit_service import append_audit
    from .membership_admin import require_workspace_admin, lock_membership_admin

    await require_identity_writer(session)
    if apply:
        await lock_membership_admin(session, row.workspace_id)
    actor = await require_workspace_admin(session, principal, row.workspace_id, rate_admission=False)
    target_query = select(Membership).where(Membership.workspace_id == row.workspace_id,
        Membership.user_id == row.canonical_user_id, Membership.active.is_(True))
    if apply:
        target_query = target_query.with_for_update()
    if (await session.execute(target_query)).scalar_one_or_none() is None:
        raise ApiError(404, 'NOT_FOUND', 'identity target unavailable')
    identity_query = select(UserIdentity).where(UserIdentity.issuer == row.issuer, UserIdentity.subject == row.subject)
    if apply:
        identity_query = identity_query.with_for_update()
    current = (await session.execute(identity_query)).scalar_one_or_none()
    digest = 'sha256:' + hashlib.sha256(json.dumps(row.model_dump(mode='json'), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    base = {'workspace_id': str(row.workspace_id), 'canonical_user_id': str(row.canonical_user_id), 'audit_ref': None}
    if current is not None:
        exact_version = current.version == row.expected_version or row.expected_version == 0 and current.version == 1
        if (current.user_id != row.canonical_user_id or current.status != 'active'
                or current.proof_ref != row.proof_ref or not exact_version):
            return {**base, 'status': 'conflict'}
        audit = (await session.execute(select(AuditEvent.id).where(AuditEvent.workspace_id == row.workspace_id,
            AuditEvent.actor_id == actor['user_id'], AuditEvent.action == 'identity.linked',
            AuditEvent.subject_id == str(row.canonical_user_id), AuditEvent.detail_digest == digest))).scalar_one_or_none()
        return {**base, 'status': 'replayed', 'audit_ref': str(audit) if audit else None}
    if row.expected_version != 0:
        return {**base, 'status': 'conflict'}
    if not apply:
        return {**base, 'status': 'would-link'}
    await link_identity(session, user_id=row.canonical_user_id, issuer=row.issuer, subject=row.subject,
                        proof_ref=row.proof_ref, expected_version=row.expected_version)
    audit = append_audit(session, workspace_id=row.workspace_id, actor_id=actor['user_id'],
        action='identity.linked', entity_type='user_identity', entity_id=row.canonical_user_id,
        request_id=str(uuid.uuid4()), reason=row.reason, detail_digest=digest)
    await session.flush()
    return {**base, 'status': 'linked', 'audit_ref': str(audit.id)}


async def reconcile_identity_manifest(manifest, *, token: str, writer_engine, apply: bool = False) -> list[dict]:
    """Explicit administrator verification; no owner DSN fallback or email linking."""
    from sqlalchemy.exc import SQLAlchemyError
    from starlette.requests import Request
    from ..api.auth import get_principal
    from ..db.session import tenant_session

    rows = parse_identity_manifest(manifest)
    if writer_engine is None:
        raise ApiError(503, 'IDENTITY_WRITER_UNAVAILABLE', 'explicit identity writer required')
    request = Request({'type': 'http', 'method': 'POST', 'path': '/internal/identity-reconciliation',
                       'headers': [(b'authorization', ('Bearer ' + token).encode())]})
    principal = await get_principal(request)

    def base(row):
        return {'workspace_id': str(row.workspace_id), 'canonical_user_id': str(row.canonical_user_id), 'audit_ref': None}

    if apply:
        from .membership_admin import lock_membership_admin

        class BatchAbort(Exception):
            def __init__(self, index, result):
                self.index, self.result = index, result

        index = 0
        try:
            # One commit for the whole bounded manifest. Acquire tenant admin
            # locks in the same order even when input row order differs.
            async with tenant_session(writer_engine, rows[0].workspace_id) as session:
                for workspace in sorted({row.workspace_id for row in rows}, key=str):
                    await lock_membership_admin(session, workspace)
                results = []
                for index, row in enumerate(rows):
                    await session.execute(text("SELECT set_config('app.workspace_id', :ws, true)"), {'ws': str(row.workspace_id)})
                    result = await _reconcile_identity_row(session, row, principal, apply=True)
                    if result['status'] not in {'linked', 'replayed'}:
                        raise BatchAbort(index, result)
                    results.append(result)
            return results
        except BatchAbort as error:
            rejected = [{**base(row), 'status': 'not-applied', 'code': 'IDENTITY_BATCH_ABORTED'} for row in rows]
            rejected[error.index] = error.result
            return rejected
        except ApiError as error:
            rejected = [{**base(row), 'status': 'not-applied', 'code': 'IDENTITY_BATCH_ABORTED'} for row in rows]
            rejected[index] = {**base(rows[index]), 'status': 'conflict' if error.status_code == 409 else 'denied', 'code': error.code}
            return rejected
        except SQLAlchemyError:
            # A lost acknowledgement applies to the single batch commit.
            # Report every row unknown and require read-only reconciliation;
            # never continue with a second transaction or automatic write.
            return [{**base(row), 'status': 'unknown-commit'} for row in rows]

    results = []
    for row in rows:
        base = {'workspace_id': str(row.workspace_id), 'canonical_user_id': str(row.canonical_user_id), 'audit_ref': None}
        try:
            async with tenant_session(writer_engine, row.workspace_id, read_only=not apply) as session:
                result = await _reconcile_identity_row(session, row, principal, apply=apply)
            results.append(result)
        except ApiError as error:
            results.append({**base, 'status': 'conflict' if error.status_code == 409 else 'denied', 'code': error.code})
        except SQLAlchemyError:
            # Preserve the exact manifest for a read-only reconciliation. A lost
            # commit acknowledgement never triggers an automatic second write.
            results.append({**base, 'status': 'unknown-commit' if apply else 'database-unavailable'})
    return results
