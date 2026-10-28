"""Flag-gated conversation boundary; never persists threads or starts research."""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, Header
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ...services.conversation_reply import resolve_sources, reply_from_grounding
from ...services.conversation_admission import prepare_conversation, complete_conversation
from ..deps import get_engine
from ...settings import get_settings

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}", tags=["conversation"])


class ConversationReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: StrictStr = Field(min_length=1, max_length=4000, pattern=r"\S")
    source_ids: list[Annotated[StrictStr, Field(min_length=1, max_length=200)]] = Field(min_length=1, max_length=20)
    language: Literal["en", "zh-HK"]


@router.post("/conversation-reply")
async def conversation_reply(workspace_id: uuid.UUID, project_id: uuid.UUID,
                             payload: ConversationReplyRequest, request: Request, response: Response,
                             principal: Principal = Depends(get_principal),
                             idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    response.headers["Cache-Control"] = "no-store"
    if not get_settings().live_read_enabled:
        raise ApiError(503, "READ_DISABLED", "live reads are temporarily disabled")
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        # Same Offer permission as Stage 1's canEdit project-context gate.
        if not permission_for_roles(member["roles"], "saveICPVersion"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        grounding = await resolve_sources(session, workspace_id=workspace_id,
            project_id=project_id, source_ids=payload.source_ids, readonly=True)
        prepared = await prepare_conversation(session, workspace_id=workspace_id, project_id=project_id,
            actor_id=member['user_id'], question=payload.question, language=payload.language,
            key=idempotency_key, grounding=grounding)
        if prepared is None:
            data = reply_from_grounding(grounding)
    if prepared is not None:
        data = await complete_conversation(get_engine(), workspace_id, prepared)
    return envelope(data, request.state.request_id)
