"""Saved-output recovery is independent of model/provider admission switches."""
import uuid
from fastapi import APIRouter, Depends, Query, Request, Response
from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..idempotency import if_match_version
from .sales_tasks import key
from ...sales.contracts import Scope, OutputSave, OutputListQuery, ActionProposal
from ...services.conversation_access import access
from ...services import sales_outputs as service

router=APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}/sales-outputs',tags=['sales-outputs'])


@router.get('/{output_id}/permissions',operation_id='getSalesOutputPermissions')
async def permissions(workspace_id:uuid.UUID,project_id:uuid.UUID,output_id:uuid.UUID,
    request:Request,principal:Principal=Depends(get_principal)):
    from ...db.sales_outputs import SalesOutput
    from ...services.conversation_access import load
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        output=await service.get_output(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),output_id)
        row=await session.get(SalesOutput,output_id)
        editable=False
        if output.availability=='available':
            try:
                _,role=await load(session,workspace_id,project_id,row.thread_id,actor)
                editable=role in {'owner','editor'}
            except ApiError as exc:
                if exc.status_code not in {403,404}: raise
    return envelope({'can_edit':editable},request.state.request_id)


from ...sales.contracts import OutputExportInput


@router.post('/{output_id}/exports',operation_id='exportSalesOutput')
async def export_saved(workspace_id:uuid.UUID,project_id:uuid.UUID,output_id:uuid.UUID,
    payload:OutputExportInput,request:Request,principal:Principal=Depends(get_principal)):
    from ..idempotency import begin_idempotency,complete_idempotency
    from ...services.export_service import export_output,authorize_export_content
    from ...sales.contracts import NativeRef
    from ...services.xverum_dispatch import gates
    expected=if_match_version(request.headers.get('If-Match'))
    if expected!=payload.revision: raise ApiError(400,'INVALID_REQUEST','matching exact output revision required')
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        await gates(session,workspace_id)
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        operation=await begin_idempotency(session,workspace_id=workspace_id,actor_id=actor,operation_id='exportSalesOutput',
            key=key(request),body=payload.model_dump(mode='json'),target={'project_id':str(project_id),'output_id':str(output_id)},precondition=str(expected))
        if operation.replay:
            result=NativeRef.model_validate(operation.response)
            await authorize_export_content(session,workspace_id=workspace_id,actor_id=actor,export_id=result.id)
        else:
            try: result=await export_output(session,scope,output_id,payload.revision,payload.format)
            except ValueError as exc: raise ApiError(409,'NEEDS_INPUT',str(exc)) from exc
            complete_idempotency(operation,str(result.id),response=result.model_dump(mode='json'))
    return envelope(result.model_dump(mode='json'),request.state.request_id)


from ...sales.contracts import FormalDraftInput


@router.post('/{output_id}/formal-draft',operation_id='createSalesFormalDraft')
async def formal_draft(workspace_id:uuid.UUID,project_id:uuid.UUID,output_id:uuid.UUID,
    payload:FormalDraftInput,request:Request,principal:Principal=Depends(get_principal)):
    from ...sales.drafting import save_formal_draft
    expected=if_match_version(request.headers.get('If-Match'))
    if expected!=payload.expected_revision: raise ApiError(400,'INVALID_REQUEST','matching output revision required')
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        try:
            result=await save_formal_draft(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
                output_id,payload.recipient_id,expected,key(request))
        except ValueError as exc: raise ApiError(409,'STALE_REVISION',str(exc)) from exc
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.post('/native-actions',operation_id='applySalesNativeAction')
async def apply(workspace_id:uuid.UUID,project_id:uuid.UUID,payload:ActionProposal,request:Request,response:Response,
    principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        try:
            result=await service.apply_native_action(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
                payload,if_match_version(request.headers.get('If-Match')),key(request))
        except ValueError as exc: raise ApiError(409,'STALE_REVISION','current saved output and native authority required') from exc
    response.headers['ETag']=f'"{result.revision}"'
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.post('',operation_id='saveSalesOutput')
async def save(workspace_id:uuid.UUID,project_id:uuid.UUID,payload:OutputSave,request:Request,response:Response,principal:Principal=Depends(get_principal)):
    expected=if_match_version(request.headers.get('If-Match'))
    if expected!=payload.expected_task_revision: raise ApiError(400,'INVALID_REQUEST','task revision must match If-Match')
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        try:
            result=await service.save_output(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
                payload.task_id,payload.candidate,key(request),payload.visibility,expected_revision=expected)
        except ValueError as exc: raise ApiError(409,'STALE_REVISION','complete current authorized sections are required') from exc
    response.headers['ETag']=f'"{result.revision}"'
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.get('',operation_id='listSalesOutputs')
async def listing(workspace_id:uuid.UUID,project_id:uuid.UUID,request:Request,
    native_surface:str|None=None,native_id:uuid.UUID|None=None,offset:int=Query(0,ge=0,le=10000),
    limit:int=Query(50,ge=1,le=100),principal:Principal=Depends(get_principal)):
    try: query=OutputListQuery(native_surface=native_surface,native_id=native_id,offset=offset,limit=limit)
    except ValueError as exc: raise ApiError(422,'INVALID_REQUEST','paired valid native filters required') from exc
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        result=await service.list_outputs(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),query)
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.get('/{output_id}',operation_id='getSalesOutput')
async def get(workspace_id:uuid.UUID,project_id:uuid.UUID,output_id:uuid.UUID,request:Request,response:Response,
    revision:int|None=Query(None,ge=1),principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        result=await service.get_output(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),output_id,revision)
    response.headers['ETag']=f'"{result.revision}"'
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.get('/{output_id}/versions',operation_id='listSalesOutputVersions')
async def history(workspace_id:uuid.UUID,project_id:uuid.UUID,output_id:uuid.UUID,request:Request,
    before_revision:int|None=Query(None,ge=1),limit:int=Query(100,ge=1,le=100),principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        result=await service.versions(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),output_id,before_revision,limit)
    result['outputs']=[r.model_dump(mode='json') for r in result['outputs']]
    return envelope(result,request.state.request_id)


@router.get('/{output_id}/versions/{revision}',operation_id='getSalesOutputVersion')
async def exact(workspace_id:uuid.UUID,project_id:uuid.UUID,output_id:uuid.UUID,revision:int,request:Request,response:Response,
    principal:Principal=Depends(get_principal)):
    if revision<1: raise ApiError(422,'INVALID_REQUEST','positive revision required')
    return await get(workspace_id,project_id,output_id,request,response,revision,principal)


@router.get('/{output_id}/preview',operation_id='previewSalesOutput')
async def preview(workspace_id:uuid.UUID,project_id:uuid.UUID,output_id:uuid.UUID,
    revision:int|None=Query(None,ge=1),principal:Principal=Depends(get_principal)):
    from fastapi.responses import HTMLResponse
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        output=await service.get_output(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),output_id,revision)
    return HTMLResponse(service.render_output(output),headers={'Content-Security-Policy':"default-src 'none'; sandbox",
        'Referrer-Policy':'no-referrer','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
