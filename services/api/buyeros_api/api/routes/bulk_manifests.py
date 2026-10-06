"""Actor-bound preview/read/execute; canonical domain API only."""
import uuid
from fastapi import APIRouter,Depends,Header,Request,Response
from ..auth import Principal,get_principal
from ..deps import load_membership,tenant_scoped
from ..errors import ApiError,envelope
from ..schemas import BulkManifestCreate,BulkManifestExecute
from ..idempotency import begin_idempotency,complete_idempotency,if_match_version
from ...services import bulk_manifest as service
router=APIRouter(prefix="/v1/workspaces/{workspace_id}/projects/{project_id}/bulk-manifests",tags=["bulk-manifests"])


def key(value):
    if not value:raise ApiError(400,"INVALID_REQUEST","Idempotency-Key header is required")
    return value


@router.post("")
async def preview_bulk_manifest(workspace_id:uuid.UUID,project_id:uuid.UUID,payload:BulkManifestCreate,request:Request,response:Response,principal:Principal=Depends(get_principal),idempotency_key:str|None=Header(default=None,alias="Idempotency-Key")):
    async with tenant_scoped(workspace_id) as session:
        member=await load_membership(session,principal=principal,workspace_id=workspace_id)
        await service.authorize(session,workspace_id=workspace_id,project_id=project_id,actor_id=member["user_id"],operation=payload.operation,command=payload.target.model_dump(mode="json"))
        outcome=await begin_idempotency(session,workspace_id=workspace_id,actor_id=member["user_id"],operation_id="previewBulkManifest",key=key(idempotency_key),body=payload.model_dump(mode="json"),target={"project_id":str(project_id)})
        if outcome.replay:
            row=await service.get(session,workspace_id=workspace_id,project_id=project_id,actor_id=member["user_id"],manifest_id=uuid.UUID(outcome.record.resource_id))
        else:
            row=await service.preview(session,workspace_id=workspace_id,project_id=project_id,actor_id=member["user_id"],payload=payload)
            complete_idempotency(outcome,str(row.id),response={"data":service.data(row)})
        response.status_code=201;response.headers["ETag"]=f'"{row.version}"';return envelope(service.data(row),request.state.request_id)


@router.get("/{manifest_id}")
async def get_bulk_manifest(workspace_id:uuid.UUID,project_id:uuid.UUID,manifest_id:uuid.UUID,request:Request,response:Response,principal:Principal=Depends(get_principal)):
    async with tenant_scoped(workspace_id) as session:
        member=await load_membership(session,principal=principal,workspace_id=workspace_id)
        row=await service.get(session,workspace_id=workspace_id,project_id=project_id,actor_id=member["user_id"],manifest_id=manifest_id)
        response.headers["ETag"]=f'"{row.version}"';return envelope(service.data(row),request.state.request_id)


@router.post("/{manifest_id}/execute")
async def execute_bulk_manifest(workspace_id:uuid.UUID,project_id:uuid.UUID,manifest_id:uuid.UUID,payload:BulkManifestExecute,request:Request,response:Response,principal:Principal=Depends(get_principal),idempotency_key:str|None=Header(default=None,alias="Idempotency-Key"),if_match:str|None=Header(default=None,alias="If-Match")):
    version=if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        member=await load_membership(session,principal=principal,workspace_id=workspace_id)
        row=await service.get(session,workspace_id=workspace_id,project_id=project_id,actor_id=member["user_id"],manifest_id=manifest_id,lock=True)
        await service.authorize(session,workspace_id=workspace_id,project_id=project_id,actor_id=member["user_id"],operation=row.operation,command=row.command)
        outcome=await begin_idempotency(session,workspace_id=workspace_id,actor_id=member["user_id"],operation_id="executeBulkManifest",key=key(idempotency_key),body=payload.model_dump(mode="json"),target={"project_id":str(project_id),"manifest_id":str(manifest_id)},precondition=if_match)
        if outcome.replay:
            if outcome.response is None:raise ApiError(409,"IDEMPOTENCY_CONFLICT","legacy execution cannot be replayed")
            status,result=outcome.response["http_status"],outcome.response["data"]
        else:
            status,result=await service.execute(session,row=row,actor_id=member["user_id"],version=version,payload=payload)
            complete_idempotency(outcome,str(row.id),response={"http_status":status,"data":result})
        response.status_code=status;response.headers["ETag"]=f'"{row.version}"';return envelope(result,request.state.request_id)
