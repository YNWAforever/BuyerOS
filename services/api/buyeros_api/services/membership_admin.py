"""Shared current authority, lock and last-admin guard for API and staff tool."""
from hashlib import sha256
from sqlalchemy import func, select
from ..api.deps import load_membership, read_current_membership
from ..api.errors import ApiError
from ..db.models import Membership
from .audit_service import append_audit


async def require_workspace_admin(session, principal, workspace_id, *, rate_admission=True):
    loader = load_membership if rate_admission else read_current_membership
    member = await loader(session, principal=principal, workspace_id=workspace_id)
    if 'workspace_admin' not in member['roles']:
        raise ApiError(403, 'PERMISSION_DENIED', 'workspace admin required')
    return member


async def lock_membership_admin(session, workspace_id):
    lock_id = int.from_bytes(sha256(f'membership-admin:{workspace_id}'.encode()).digest()[:8], 'big', signed=True)
    await session.execute(select(func.pg_advisory_xact_lock(lock_id)))


async def apply_membership_update(session, row, *, workspace_id, actor_id, roles, active,
                                  reason, request_id, detail_digest=None):
    if row.active and 'workspace_admin' in row.roles and (not active or 'workspace_admin' not in roles):
        count = (await session.execute(select(func.count()).select_from(Membership).where(
            Membership.workspace_id == workspace_id, Membership.active.is_(True),
            Membership.roles.any('workspace_admin')))).scalar_one()
        if count <= 1:
            raise ApiError(409, 'LAST_ADMIN', 'cannot remove the last active workspace admin')
    if row.roles == roles and row.active == active:
        return None
    row.roles = list(roles)
    row.active = active
    row.version += 1
    return append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                        action='membership.updated', entity_type='membership', entity_id=row.id,
                        request_id=request_id, reason=reason, detail_digest=detail_digest)
