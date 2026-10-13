"""Authenticated preview, exact confirmation and read-only import reconciliation."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
from starlette.concurrency import run_in_threadpool

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency
from ...services.buyer_import import buyer_import_source, confirm_import, get_import, import_data, require_project, stage_import
from ...services.buyer_import_parser import MAX_FILE_BYTES, parse_buyer_file

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["buyer-imports"])


class BuyerImportConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview_digest: StrictStr = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    confirmation: Literal[True]

    @field_validator("confirmation", mode="before")
    @classmethod
    def _literal_confirmation(cls, value):
        if value is not True:
            raise ValueError("confirmation must be the boolean true")
        return value


async def _member(session, principal, workspace_id, operation):
    member = await load_membership(session, principal=principal, workspace_id=workspace_id)
    if not permission_for_roles(member["roles"], operation):
        raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    return member


def _key(value):
    if not value:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    return value


@router.post("/projects/{project_id}/buyer-imports/preview", status_code=201)
async def preview_buyer_import(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    file: UploadFile = File(...), principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "previewBuyerImport")
        await require_project(session, workspace_id, project_id)
    try:
        content = await file.read(MAX_FILE_BYTES + 1)
        parsed = await run_in_threadpool(parse_buyer_file, content, file.filename or "")
    except ValueError as exc:
        raise ApiError(422, "INVALID_REQUEST", str(exc)) from exc
    finally:
        await file.close()
    async with tenant_scoped(workspace_id) as session:
        # Recheck authority after parsing; the first transaction holds no file-processing locks.
        member = await _member(session, principal, workspace_id, "previewBuyerImport")
        await require_project(session, workspace_id, project_id)
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="previewBuyerImport", key=_key(idempotency_key),
            body={"file_sha256": parsed["file_sha256"], "file_name": parsed["file_name"]},
            target={"project_id": str(project_id)})
        if outcome.replay:
            return envelope(outcome.response, request.state.request_id)
        item = await stage_import(session, workspace_id=workspace_id, project_id=project_id, actor_user_id=member["user_id"], parsed=parsed)
        data = import_data(item)
        complete_idempotency(outcome, str(item.id), response=data)
    return envelope(data, request.state.request_id)


@router.get("/projects/{project_id}/buyer-imports/{import_id}")
async def read_buyer_import(workspace_id: uuid.UUID, project_id: uuid.UUID, import_id: uuid.UUID,
    request: Request, principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "getBuyerImport")
        item = await get_import(session, workspace_id=workspace_id, project_id=project_id,
                                actor_user_id=member["user_id"], import_id=import_id)
        data = import_data(item)
    return envelope(data, request.state.request_id)


@router.post("/projects/{project_id}/buyer-imports/{import_id}/confirm")
async def confirm_buyer_import(workspace_id: uuid.UUID, project_id: uuid.UUID, import_id: uuid.UUID,
    payload: BuyerImportConfirm, request: Request, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    async with tenant_scoped(workspace_id) as session:
        member = await _member(session, principal, workspace_id, "confirmBuyerImport")
        item = await get_import(session, workspace_id=workspace_id, project_id=project_id,
                                actor_user_id=member["user_id"], import_id=import_id, lock=True)
        outcome = await begin_idempotency(session, workspace_id=workspace_id, actor_id=member["user_id"],
            operation_id="confirmBuyerImport", key=_key(idempotency_key), body=payload.model_dump(mode="json"),
            target={"project_id": str(project_id), "import_id": str(import_id)})
        if outcome.replay:
            return envelope(outcome.response, request.state.request_id)
        if item.status != "completed":
            await require_project(session, workspace_id, project_id, lock=True)
        data = await confirm_import(session, item=item, preview_digest=payload.preview_digest, actor_user_id=member["user_id"])
        complete_idempotency(outcome, str(item.id), response=data)
    return envelope(data, request.state.request_id)


@router.get("/buyers/{buyer_id}/import-source")
async def get_buyer_import_source(workspace_id: uuid.UUID, buyer_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        await _member(session, principal, workspace_id, "getBuyerImportSource")
        data = await buyer_import_source(session, workspace_id=workspace_id, buyer_id=buyer_id)
    return envelope(data, request.state.request_id)
