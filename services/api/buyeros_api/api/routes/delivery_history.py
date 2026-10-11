"""Scoped persisted delivery history; no provider selection or resubmission."""
import uuid
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from ...db.delivery import DeliveryMessage
from ...db.drafts import OutreachDraft
from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope

router=APIRouter(prefix='/v1/workspaces/{workspace_id}',tags=['delivery'])

@router.get('/projects/{project_id}/drafts/{draft_id}/delivery-messages',
            operation_id='listDraftDeliveryMessages')
async def list_draft_delivery_messages(workspace_id:uuid.UUID, project_id:uuid.UUID,
        draft_id:uuid.UUID, request:Request, response:Response,
        principal:Principal=Depends(get_principal),
        offset:int=Query(default=0,ge=0), limit:int=Query(default=20,ge=1,le=100)) -> dict:
    async with tenant_scoped(workspace_id) as session:
        member=await load_membership(session,principal=principal,workspace_id=workspace_id)
        if not permission_for_roles(member['roles'],'listDraftDeliveryMessages'):
            raise ApiError(403,'PERMISSION_DENIED','insufficient role')
        draft=(await session.execute(select(OutreachDraft.id).where(
            OutreachDraft.workspace_id==workspace_id, OutreachDraft.project_id==project_id,
            OutreachDraft.id==draft_id))).scalar_one_or_none()
        if draft is None:
            raise ApiError(404,'NOT_FOUND','draft not found')
        predicates=(DeliveryMessage.workspace_id==workspace_id,
                    DeliveryMessage.project_id==project_id,DeliveryMessage.draft_id==draft_id)
        total=(await session.execute(select(func.count()).select_from(DeliveryMessage)
              .where(*predicates))).scalar_one()
        # Read only public metadata columns; account/ref/key/content stay private.
        columns=(DeliveryMessage.id,DeliveryMessage.workspace_id,DeliveryMessage.project_id,
                 DeliveryMessage.draft_id,DeliveryMessage.draft_revision_id,
                 DeliveryMessage.revision_number,DeliveryMessage.approval_id,
                 DeliveryMessage.state,DeliveryMessage.created_at,DeliveryMessage.updated_at)
        rows=(await session.execute(select(*columns).where(*predicates)
              .order_by(DeliveryMessage.created_at.desc(),DeliveryMessage.id.desc())
              .offset(offset).limit(limit))).mappings().all()
        items=[{key:(value.isoformat() if key in {'created_at','updated_at'} else
                    str(value) if isinstance(value,uuid.UUID) else value)
                for key,value in row.items()} for row in rows]
    response.headers['Cache-Control']='private, no-store'
    return envelope({'items':items,'offset':offset,'limit':limit,'total':total},request.state.request_id)
