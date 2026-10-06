"""Bounded administrative reconciliation; no identity creation or email matching."""
import hashlib
import json
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, TypeAdapter, field_validator
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from ..api.auth import get_principal
from ..api.deps import get_engine
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency
from ..api.schemas import MembershipUpdate
from ..db.contact import IdempotencyRecord
from ..db.models import Membership, User
from ..db.session import tenant_session
from .audit_service import append_audit
from .membership_admin import require_workspace_admin, lock_membership_admin, apply_membership_update


class StaffRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    canonical_user_id: uuid.UUID
    workspace_id: uuid.UUID
    roles: list[Literal['viewer', 'operator', 'reviewer', 'workspace_admin']] = Field(min_length=1, max_length=4)
    reason: StrictStr = Field(min_length=3, max_length=2000)
    proof_ref: StrictStr = Field(min_length=1, max_length=200)
    expected_version: StrictInt = Field(ge=0, le=2147483646)

    @field_validator('roles')
    @classmethod
    def unique_roles(cls, roles):
        MembershipUpdate(roles=roles, active=True, reason='Staff reconciliation')
        return sorted(roles)


def parse_staff_manifest(manifest) -> list[StaffRow]:
    if not isinstance(manifest, list) or not 1 <= len(manifest) <= 100:
        raise ValueError('manifest requires 1..100 rows')
    rows = TypeAdapter(list[StaffRow]).validate_python(manifest)
    targets = {(r.workspace_id, r.canonical_user_id) for r in rows}
    if len(targets) != len(rows):
        raise ValueError('duplicate membership targets')
    return rows


async def _runtime_role(session):
    role = (await session.execute(text("SELECT session_user,current_user,rolsuper,rolbypassrls "
        "FROM pg_catalog.pg_roles WHERE rolname=current_user"))).one()
    if tuple(role) != ('buyeros_api', 'buyeros_api', False, False):
        raise ApiError(403, 'PERMISSION_DENIED', 'nonprivileged API login required')


def _current(row):
    return {'membership_id': str(row.id), 'version': row.version, 'roles': sorted(row.roles), 'active': row.active}


async def _row(session, item, principal, *, apply):
    await _runtime_role(session)
    actor = await require_workspace_admin(session, principal, item.workspace_id, rate_admission=False)
    if apply:
        await lock_membership_admin(session, item.workspace_id)
        actor = await require_workspace_admin(session, principal, item.workspace_id, rate_admission=False)
    target = (await session.execute(select(User).where(User.id == item.canonical_user_id))).scalar_one_or_none()
    base = {'workspace_id': str(item.workspace_id), 'canonical_user_id': str(item.canonical_user_id), 'audit_ref': None}
    if target is None or not target.issuer or not target.subject:
        return {**base, 'status': 'pending-identity'}
    query = select(Membership).where(Membership.workspace_id == item.workspace_id, Membership.user_id == item.canonical_user_id)
    if apply:
        query = query.with_for_update()
    current = (await session.execute(query)).scalar_one_or_none()
    body = item.model_dump(mode='json')
    serialized = json.dumps(body, sort_keys=True, separators=(',', ':')).encode()
    key = 'c61-staff-' + hashlib.sha256(serialized).hexdigest()
    target_binding = {'canonical_user_id': str(item.canonical_user_id)}
    # Read the exact existing receipt before any insertion/version decision. An
    # altered/revoked membership never replays a stale successful grant.
    existing = (await session.execute(select(IdempotencyRecord).where(
        IdempotencyRecord.workspace_id == item.workspace_id, IdempotencyRecord.actor_id == actor['user_id'],
        IdempotencyRecord.operation_id == 'reconcileStaffMembership', IdempotencyRecord.key == key))).scalar_one_or_none()
    if existing is not None:
        outcome = await begin_idempotency(session, workspace_id=item.workspace_id, actor_id=actor['user_id'],
            operation_id='reconcileStaffMembership', key=key, body=body, target=target_binding,
            precondition=str(item.expected_version))
        receipt = outcome.response or {}
        if current is None or any(receipt.get(k) != v for k, v in _current(current).items()):
            return {**base, 'status': 'conflict'}
        return {**receipt, 'status': 'replayed'}
    if current is None:
        if item.expected_version != 0:
            return {**base, 'status': 'conflict'}
        action = 'create'
    else:
        if current.version != item.expected_version or set(current.roles) != set(item.roles):
            return {**base, 'status': 'conflict'}
        if current.active:
            return {**base, **_current(current), 'status': 'unchanged'}
        action = 'restore'
    if not apply:
        return {**base, 'status': 'would-' + action}
    outcome = await begin_idempotency(session, workspace_id=item.workspace_id, actor_id=actor['user_id'],
        operation_id='reconcileStaffMembership', key=key, body=body, target=target_binding,
        precondition=str(item.expected_version))
    correlation = str(uuid.uuid4())
    digest = 'sha256:' + hashlib.sha256(serialized).hexdigest()
    if action == 'create':
        current = Membership(id=uuid.uuid4(), workspace_id=item.workspace_id,
                             user_id=item.canonical_user_id, roles=item.roles, active=True, version=1)
        session.add(current)
        audit = append_audit(session, workspace_id=item.workspace_id, actor_id=actor['user_id'],
            action='membership.created', entity_type='membership', entity_id=current.id,
            request_id=correlation, reason=item.reason, detail_digest=digest)
    else:
        audit = await apply_membership_update(session, current, workspace_id=item.workspace_id,
            actor_id=actor['user_id'], roles=item.roles, active=True, reason=item.reason,
            request_id=correlation, detail_digest=digest)
    await session.flush()
    result = {**base, **_current(current), 'audit_ref': str(audit.id),
              'status': 'created' if action == 'create' else 'restored'}
    complete_idempotency(outcome, str(current.id), response=result)
    return result


async def reconcile_staff_manifest(manifest, *, token: str, apply: bool = False) -> list[dict]:
    rows = parse_staff_manifest(manifest)
    request = Request({'type': 'http', 'method': 'POST', 'path': '/internal/staff-reconciliation',
                       'headers': [(b'authorization', ('Bearer ' + token).encode())]})
    principal = await get_principal(request)
    results = []
    for item in rows:
        try:
            async with tenant_session(get_engine(), item.workspace_id, read_only=not apply) as session:
                result = await _row(session, item, principal, apply=apply)
            results.append(result)
        except ApiError as exc:
            results.append({'workspace_id': str(item.workspace_id), 'canonical_user_id': str(item.canonical_user_id),
                            'status': 'denied', 'code': exc.code, 'audit_ref': None})
        except SQLAlchemyError:
            # A lost commit response has unknown status: retain the exact manifest
            # and inspect its receipt/current membership before any fresh action.
            results.append({'workspace_id': str(item.workspace_id), 'canonical_user_id': str(item.canonical_user_id),
                            'status': 'unknown-commit' if apply else 'database-unavailable', 'audit_ref': None})
    return results
