"""Native sales-task transport; all authority is server derived."""
import uuid
from fastapi import APIRouter, Depends, Query, Request
from ..auth import Principal, get_principal
from ..errors import ApiError, envelope
from ..idempotency import if_match_version
from ...sales.contracts import Scope, TaskInput, TaskFollowup, ActionProposal, StepAdmission, StepReviewInput
from ..idempotency import begin_idempotency, complete_idempotency
from ...services.conversation_access import access
from ...services import sales_tasks as service

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}/sales-tasks', tags=['sales-tasks'])


@router.get('/capability', operation_id='getSalesCapability')
async def capability(workspace_id:uuid.UUID, project_id:uuid.UUID, request:Request,
    principal:Principal=Depends(get_principal)):
    from ...services.conversation_access import sales_enabled
    async with access(workspace_id, project_id, principal, sales=True, admission=False,locks=False):
        enabled = sales_enabled(workspace_id)
    from ...sales.contracts import SalesCapability
    return envelope(SalesCapability(admission_enabled=enabled).model_dump(mode='json'), request.state.request_id)


@router.get('/native-sources', operation_id='listSalesNativeSources')
async def native_sources(workspace_id:uuid.UUID, project_id:uuid.UUID, request:Request,
    principal:Principal=Depends(get_principal)):
    from sqlalchemy import select
    from ...db.buyers import ProjectBuyer
    from ...db.icp import IcpVersion
    from ...db.runs import SearchRun
    from ...sales.contracts import SourceRef
    from ...sales.native_sources import resolve_native_source
    items=[]
    async with access(workspace_id, project_id, principal, sales=True, admission=False,locks=False) as (session, actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        for kind,model,column in [('buyer',ProjectBuyer,'version'),('profile',IcpVersion,'number'),('run',SearchRun,'version')]:
            rows=(await session.scalars(select(model).where(model.workspace_id==workspace_id,
                model.project_id==project_id).order_by(model.id).limit(50))).all()
            for row in rows:
                ref=SourceRef(id=row.id,kind=kind,version=getattr(row,column),locator=f'{kind}:{row.id}',retention_class='durable')
                try:
                    # The same current policy/revision/native authority as task intake.
                    await resolve_native_source(session,scope,ref)
                except (ValueError,ApiError):
                    continue
                items.append({'label':f'{kind} {str(row.id)[:8]}', 'ref':ref.model_dump(mode='json')})
    from ...sales.contracts import SalesNativeSources
    return envelope(SalesNativeSources(items=items).model_dump(mode='json'),request.state.request_id)


@router.get('/{task_id}/core-guidance',operation_id='getSalesCoreGuidance')
async def core_guidance(workspace_id:uuid.UUID,project_id:uuid.UUID,task_id:uuid.UUID,request:Request,
    principal:Principal=Depends(get_principal)):
    from ...sales.actions import CORE_SKILL_OWNER
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        row=await service.task_row(session,scope,task_id,edit=True)
        result=await CORE_SKILL_OWNER.guidance(session,scope,row)
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.post('/{task_id}/core-preparation',operation_id='prepareSalesCoreOutput')
async def core_preparation(workspace_id:uuid.UUID,project_id:uuid.UUID,task_id:uuid.UUID,request:Request,
    principal:Principal=Depends(get_principal)):
    from ...services.sales_outputs import assemble_or_core,save_output
    failure=None
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        if await request.body(): raise ApiError(400,'INVALID_REQUEST','preparation takes no candidate body')
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        row=await service.task_row(session,scope,task_id,edit=True)
        if row.state not in {'needs_input','ready_for_review','completed'} and not (
            row.skill_id=='sales-prospect' and row.state=='partially_completed'):
            raise ApiError(409,'TASK_ACTIVE','this task cannot prepare output')
        try:
            candidate=await assemble_or_core(session,scope,row)
        except ValueError as exc:
            if not str(exc).startswith('Needs input:'): raise ApiError(409,'NEEDS_INPUT',str(exc)) from exc
            service.check_revision(row.revision,if_match_version(request.headers.get('If-Match')))
            key(request)
            if row.state=='ready_for_review':
                row.state='needs_input';row.revision+=1
                await service.append_event(session,row.id,'state',{'state':row.state,'revision':row.revision})
                await session.flush()
            failure=ApiError(409,'NEEDS_INPUT',str(exc))
        else:
            try:
                result=await save_output(session,scope,task_id,candidate,key(request),
                    expected_revision=if_match_version(request.headers.get('If-Match')))
            except ValueError as exc: raise ApiError(409,'NEEDS_INPUT',str(exc)) from exc
    if failure: raise failure
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.get('/{task_id}/output-review',operation_id='reviewSalesOutput')
async def output_review(workspace_id:uuid.UUID,project_id:uuid.UUID,task_id:uuid.UUID,request:Request,
    principal:Principal=Depends(get_principal)):
    from ...services.sales_outputs import review_task_candidate
    from ...sales.contracts import OutputReview, SourceRef
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        row=await service.task_row(session,scope,task_id,edit=True)
        try:
            candidate=await review_task_candidate(session,scope,row)
        except ValueError as exc: raise ApiError(409,'STALE_REVISION','complete current sections required') from exc
        result=OutputReview(task_id=task_id,task_revision=row.revision,project_id=project_id,thread_id=row.thread_id,candidate=candidate)
    return envelope(result.model_dump(mode='json'),request.state.request_id)


def key(request):
    value = request.headers.get('Idempotency-Key', '')
    if not 8 <= len(value) <= 200:
        raise ApiError(400, 'INVALID_REQUEST', 'Idempotency-Key must be 8..200 characters')
    return value


@router.post('', status_code=201, operation_id='createSalesTask')
async def create(workspace_id: uuid.UUID, project_id: uuid.UUID, payload: TaskInput, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal, sales=True) as (session, actor):
        result = await service.create_task(session, Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            payload, key(request), if_match_version(request.headers.get('If-Match')))
    return envelope(result.model_dump(mode='json'), request.state.request_id)


@router.get('/{task_id}', operation_id='getSalesTask')
async def get(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal, sales=True, admission=False,locks=False) as (session, actor):
        result = await service.get_task(session, Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor), task_id)
    return envelope(result.model_dump(mode='json'), request.state.request_id)


@router.get('/{task_id}/events', operation_id='listSalesTaskEvents')
async def events(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID, request: Request, after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal, sales=True, admission=False,locks=False) as (session, actor):
        result = await service.read_events(session, Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor), task_id, after)
        result = result[:limit]
    return envelope({'events':[item.model_dump(mode='json') for item in result], 'next_sequence':result[-1].sequence if result else None}, request.state.request_id)


@router.post('/{task_id}/cancel', operation_id='cancelSalesTask')
async def cancel(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id, project_id, principal, sales=True, admission=False) as (session, actor):
        if await request.body():
            raise ApiError(400, 'INVALID_REQUEST', 'cancel takes no request body')
        result = await service.cancel_task(session, Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            task_id, key(request), if_match_version(request.headers.get('If-Match')))
    return envelope(result.model_dump(mode='json'), request.state.request_id)


@router.get('', operation_id='listSalesTasks')
async def listing(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    thread_id: uuid.UUID = Query(...), offset: int = Query(0, ge=0, le=10000),
    limit: int = Query(50, ge=1, le=50), principal: Principal = Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        result = await service.list_tasks(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),thread_id,offset,limit)
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.post('/{task_id}/followups', operation_id='followupSalesTask')
async def followup(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID,
    payload: TaskFollowup, request: Request, principal: Principal = Depends(get_principal)):
    # Editing saved intake is recovery, not new admission/dispatch.
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        result = await service.followup_task(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            task_id,payload,key(request),if_match_version(request.headers.get('If-Match')))
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.post('/{task_id}/reviews', operation_id='approveSalesStep')
async def approve(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID,
    payload: StepReviewInput, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True) as (session,actor):
        try:
            result=await service.approve_step(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
                task_id,payload.proposal,if_match_version(request.headers.get('If-Match')),key(request),expected_fingerprint=payload.fingerprint)
        except ValueError as exc:
            raise ApiError(409,'STALE_REVISION','review the current task, sources and configuration') from exc
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.post('/{task_id}/steps', operation_id='admitSalesStep')
async def admit(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID,
    payload: StepAdmission, request: Request, principal: Principal = Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        expected=if_match_version(request.headers.get('If-Match'))
        from ...execution.sales_tasks import lock_authority
        await lock_authority(session,workspace_id,budget=True)
        row=await service.task_row(session,scope,task_id,edit=True)
        operation=await begin_idempotency(session,workspace_id=workspace_id,actor_id=actor,
            operation_id='admitSalesStep',key=key(request),body=payload.model_dump(mode='json'),
            target={'project_id':str(project_id),'task_id':str(task_id)},precondition=f'"{expected}"')
        # Current task ACL always precedes replay; the admission owner rechecks sources/config too.
        try:
            result=await service.admit_step(session,scope,task_id,payload.proposal,payload.review_id,expected_version=expected)
        except ValueError as exc:
            raise ApiError(409,'STALE_REVISION','current reviewed execution is required') from exc
        complete_idempotency(operation,str(result.id))
    return envelope(result.model_dump(mode='json'),request.state.request_id)


@router.get('/{task_id}/steps', operation_id='listSalesSteps')
async def steps(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID,
    request: Request, principal: Principal = Depends(get_principal)):
    from ...execution.sales_tasks import list_steps
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        result=await list_steps(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),task_id)
    return envelope({'items':[item.model_dump(mode='json') for item in result]},request.state.request_id)


@router.post('/{task_id}/execution-preview', operation_id='previewSalesExecution')
async def preview(workspace_id: uuid.UUID, project_id: uuid.UUID, task_id: uuid.UUID,
    payload: ActionProposal, request: Request, principal: Principal = Depends(get_principal)):
    from ...execution.sales_tasks import preview_step
    async with access(workspace_id,project_id,principal,sales=True) as (session,actor):
        try:
            result=await preview_step(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),task_id,payload)
        except ValueError as exc:
            raise ApiError(409,'STALE_REVISION','review current task sources and configuration') from exc
    return envelope(result.model_dump(mode='json'),request.state.request_id)


catalogue_router=APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}/sales',tags=['sales-tasks'])

@catalogue_router.get('/skills',operation_id='listSalesSkills')
async def skills(workspace_id:uuid.UUID,project_id:uuid.UUID,request:Request,principal:Principal=Depends(get_principal)):
    from ...sales.registry import catalogue
    from ...sales.contracts import SkillPage
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False):
        value=SkillPage(skills=catalogue())
    return envelope(value.model_dump(mode='json'),request.state.request_id)
