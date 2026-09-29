"""Actor/workspace preferences, independent of provider configuration."""
import uuid

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import select

from ..auth import Principal, get_principal
from ..deps import load_membership, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import PreferencesUpdate
from ...db.models import Membership, WorkspacePreference
from ...services.audit_service import append_audit

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/preferences", tags=["preferences"])


def _data(row: WorkspacePreference | None) -> dict:
    return {"locale": row.locale if row else "en",
            "default_markets": list(row.default_markets) if row else [],
            "version": row.version if row else 1}


@router.get("")
async def get_preferences(workspace_id: uuid.UUID, request: Request, response: Response,
                          principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        row = (await session.execute(select(WorkspacePreference).where(
            WorkspacePreference.workspace_id == workspace_id,
            WorkspacePreference.user_id == member["user_id"]))).scalar_one_or_none()
        data = _data(row)
    response.headers["ETag"] = f'"{data["version"]}"'
    return envelope(data, request.state.request_id)


@router.patch("")
async def update_preferences(workspace_id: uuid.UUID, payload: PreferencesUpdate,
                             request: Request, response: Response,
                             principal: Principal = Depends(get_principal),
                             if_match: str | None = Header(None, alias="If-Match"),
                             idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    expected = if_match_version(if_match)
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    body = payload.model_dump(mode="json", exclude_unset=True)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        await session.execute(select(Membership.id).where(
            Membership.workspace_id == workspace_id, Membership.user_id == member["user_id"]).with_for_update())
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="updatePreferences", key=idempotency_key, body=body,
            target={"workspace_id": str(workspace_id)}, precondition=if_match)
        if outcome.replay and outcome.response is not None:
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response, request.state.request_id)
        row = (await session.execute(select(WorkspacePreference).where(
            WorkspacePreference.workspace_id == workspace_id,
            WorkspacePreference.user_id == member["user_id"]).with_for_update())).scalar_one_or_none()
        if (row.version if row else 1) != expected:
            raise ApiError(412, "STALE_REVISION", "preferences version changed")
        if row is None:
            row = WorkspacePreference(workspace_id=workspace_id, user_id=member["user_id"],
                                      locale="en", default_markets=[], version=1)
            session.add(row)
        changed = any(getattr(row, field) != value for field, value in body.items())
        if changed:
            for field, value in body.items():
                setattr(row, field, value)
            row.version += 1
            append_audit(session, workspace_id=workspace_id, actor_id=member["user_id"],
                         action="preferences.updated", entity_type="user", entity_id=member["user_id"],
                         request_id=request.state.request_id)
        data = _data(row)
        complete_idempotency(outcome, str(member["user_id"]), response=data)
        response.headers["ETag"] = f'"{row.version}"'
    return envelope(data, request.state.request_id)
