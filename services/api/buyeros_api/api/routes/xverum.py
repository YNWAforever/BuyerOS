"""Authenticated project-assigned Xverum control plane. No browser credentials."""
import uuid
from fastapi import APIRouter, Depends, Request, Response
from ..auth import Principal, get_principal
from ..errors import envelope
from ..idempotency import if_match_version
from .sales_tasks import key
from ...sales.contracts import Scope, ConnectionAssignment, ConnectionRotation
from ...services.conversation_access import access
from ...services import xverum_connections as service

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}/xverum',tags=['xverum'])


from ...sales.contracts import EnrichmentCreate, EnrichmentApply
from ...services import xverum_enrichment as enrichment
from ...sales.actions import CONTACT_ENRICHMENT_OWNER


@router.post('/enrichment-proposals',operation_id='createEnrichmentProposal')
async def create_enrichment(workspace_id:uuid.UUID,project_id:uuid.UUID,payload:EnrichmentCreate,
    request:Request,principal:Principal=Depends(get_principal)):
    mutation_key=key(request)
    async with access(workspace_id,project_id,principal,sales=True) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        await enrichment.permission(session,scope)
        operation=await begin_idempotency(session,workspace_id=workspace_id,actor_id=actor,
            operation_id='createEnrichmentProposal',key=mutation_key,body=payload.model_dump(mode='json'),
            target={'project_id':str(project_id)})
        if operation.replay: value=await enrichment.read_proposal(session,scope,uuid.UUID(operation.record.resource_id))
        else:
            value=await CONTACT_ENRICHMENT_OWNER.propose(session,scope,payload.buyer_id,list(payload.receipt_ids),task_id=payload.task_id,selected_id=payload.selected_id,previous_proposal_id=payload.previous_proposal_id)
            complete_idempotency(operation,str(value.id))
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.get('/enrichment-proposals/{proposal_id}',operation_id='getEnrichmentProposal')
async def get_enrichment(workspace_id:uuid.UUID,project_id:uuid.UUID,proposal_id:uuid.UUID,
    request:Request,principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        value=await enrichment.read_proposal(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),proposal_id)
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.post('/enrichment-proposals/{proposal_id}/apply',operation_id='applyEnrichmentProposal')
async def apply_enrichment_route(workspace_id:uuid.UUID,project_id:uuid.UUID,proposal_id:uuid.UUID,
    payload:EnrichmentApply,request:Request,response:Response,principal:Principal=Depends(get_principal)):
    expected=if_match_version(request.headers.get('If-Match'));mutation_key=key(request)
    if payload.proposal_id!=proposal_id or payload.buyer_version!=expected:
        raise ApiError(422,'INVALID_REQUEST','exact proposal and buyer precondition required')
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        value=await CONTACT_ENRICHMENT_OWNER.apply(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            proposal_id,list(payload.selected_fields),expected,mutation_key)
    response.headers['ETag']=f'"{value.revision}"'
    return envelope(value.model_dump(mode='json'),request.state.request_id)


def result(value,request,response):
    response.headers['ETag'] = f'"{value.version}"'
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.get('/connections',operation_id='listXverumConnections')
async def listing(workspace_id:uuid.UUID,project_id:uuid.UUID,request:Request,principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        values = await service.list_connections(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor))
    return envelope({'connections':[v.model_dump(mode='json') for v in values]},request.state.request_id)


@router.put('/connections/{connection_id}/assignment',operation_id='assignXverumConnection')
async def assign(workspace_id:uuid.UUID,project_id:uuid.UUID,connection_id:uuid.UUID,payload:ConnectionAssignment,
    request:Request,response:Response,principal:Principal=Depends(get_principal)):
    expected,mutation_key = if_match_version(request.headers.get('If-Match')),key(request)
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        value = await service.assign_xverum(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            connection_id,payload,expected,mutation_key)
    if value.status == 'configuration_required':await service.revoke_local(value)
    return result(value,request,response)


@router.post('/connections/{connection_id}/disconnect',operation_id='disconnectXverumConnection')
async def disconnect(workspace_id:uuid.UUID,project_id:uuid.UUID,connection_id:uuid.UUID,
    request:Request,response:Response,principal:Principal=Depends(get_principal)):
    expected,mutation_key = if_match_version(request.headers.get('If-Match')),key(request)
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        value = await service.disconnect_xverum(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            expected,mutation_key,connection_id=connection_id)
    if value.status == 'disconnected':await service.revoke_local(value)
    return result(value,request,response)


@router.post('/connections/{connection_id}/rotate',operation_id='rotateXverumConnection')
async def rotate(workspace_id:uuid.UUID,project_id:uuid.UUID,connection_id:uuid.UUID,payload:ConnectionRotation,
    request:Request,response:Response,principal:Principal=Depends(get_principal)):
    expected,mutation_key = if_match_version(request.headers.get('If-Match')),key(request)
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        scope = Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        value,replay = await service.prepare_rotation(session,scope,connection_id,expected,mutation_key,payload.expected_generation)
    if not replay:
        # Customer transaction is closed before contacting the secret service/MCP.
        handle = await service.refresh_credential(value)
        async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
            scope = Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
            value = await service.publish_rotation(session,scope,value,handle,expected,mutation_key)
    return result(value,request,response)


from ...sales.contracts import QuoteRequest, QuoteApproval
from ...services import xverum_quotes as quotes
from ..idempotency import begin_idempotency, complete_idempotency
from ..errors import ApiError


@router.post('/quotes',operation_id='createXverumQuote')
async def create_quote(workspace_id:uuid.UUID,project_id:uuid.UUID,payload:QuoteRequest,
    request:Request,principal:Principal=Depends(get_principal)):
    mutation_key=key(request)
    async with access(workspace_id,project_id,principal,sales=True) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        await service.authority(session,scope,'useXverumConnection')
        outcome=await begin_idempotency(session,workspace_id=workspace_id,actor_id=actor,
            operation_id='createXverumQuote',key=mutation_key,body=payload.model_dump(mode='json'),
            target={'project_id':str(project_id)})
        if outcome.replay:value=await quotes.read_quote(session,scope,uuid.UUID(outcome.record.resource_id))
        else:
            if payload.stage=='search':
                value=await quotes.quote_search(session,scope,payload.connection_id,payload.query,payload.target,payload.buyer_id)
            else:value=await quotes.quote_details(session,scope,payload.search_receipt_id,list(payload.selected_ids),payload.include_email)
            complete_idempotency(outcome,str(value.id))
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.get('/quotes/{quote_id}',operation_id='getXverumQuote')
async def get_quote(workspace_id:uuid.UUID,project_id:uuid.UUID,quote_id:uuid.UUID,
    request:Request,principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        value=await quotes.read_quote(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),quote_id)
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.get('/receipts/{receipt_id}/candidates',operation_id='getXverumCandidates')
async def candidates(workspace_id:uuid.UUID,project_id:uuid.UUID,receipt_id:uuid.UUID,
    request:Request,principal:Principal=Depends(get_principal)):
    from ...services.xverum_dispatch import source_search_evidence
    from ...sales.contracts import XverumCompanySearch, XverumPeopleSearch
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        evidence=await source_search_evidence(session,Scope(workspace_id=workspace_id,
            project_id=project_id,actor_id=actor),receipt_id)
        schema=XverumCompanySearch if evidence['tool']=='search_company_xverum' else XverumPeopleSearch
        value=schema.model_validate(evidence['projection'])
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.get('/tasks/{task_id}/stages',operation_id='listXverumTaskStages')
async def task_stages(workspace_id:uuid.UUID,project_id:uuid.UUID,task_id:uuid.UUID,
    request:Request,principal:Principal=Depends(get_principal)):
    from sqlalchemy import select
    from ...db.xverum import XverumStage, XverumReceiptRow, XverumCreditReservation, XverumQuoteRow
    from ...services.sales_tasks import task_row
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        await task_row(session,scope,task_id)
        rows=(await session.execute(select(XverumReceiptRow,XverumQuoteRow)
            .join(XverumStage,XverumStage.id==XverumReceiptRow.id)
            .join(XverumCreditReservation,XverumCreditReservation.id==XverumReceiptRow.reservation_id)
            .join(XverumQuoteRow,XverumQuoteRow.id==XverumCreditReservation.quote_id)
            .where(XverumStage.task_id==task_id,XverumStage.workspace_id==workspace_id,
                XverumStage.project_id==project_id,XverumReceiptRow.actor_id==actor)
            .order_by(XverumReceiptRow.created_at,XverumReceiptRow.id).limit(16))).all()
        items=[]
        for receipt,quote in rows:
            selected_ids=[];reviewed_ids=[];previous=None
            if quote.payload.get('stage')=='detail' and receipt.dispatch_state=='settled':
                from ...db.xverum_enrichment import XverumEnrichment
                producers=list((await session.scalars(select(XverumEnrichment).where(
                    XverumEnrichment.workspace_id==workspace_id,XverumEnrichment.project_id==project_id,
                    XverumEnrichment.actor_id==actor,XverumEnrichment.task_id==task_id,
                    XverumEnrichment.applied.is_not(None),
                    XverumEnrichment.proof['receipt_ids'].contains([str(receipt.id)])))).all())
                latest=max(producers,key=lambda p:p.applied['native']['revision']) if producers else None
                try:
                    if latest: await enrichment.validate_record(session,scope,latest)
                    evidence=await dispatch.read_evidence(session,scope,receipt.id,_enrichment_id=latest.id if latest else None)
                    selected_ids=list(dict.fromkeys(v['provider_ids'][0] for v in evidence if v['tool'] in {'enrich_person_xverum','enrich_company_xverum'}))
                    reviewed_ids=[p.proof['provider_identity'] for p in producers]
                    previous=str(latest.id) if latest else None
                except (ApiError,ValueError): pass  # Content-free liability recovery remains available.
            current=await quotes.read_receipt(session,scope,receipt.id,_enrichment_id=uuid.UUID(previous) if previous else None)
            items.append({'receipt':current.model_dump(mode='json'),'stage':quote.payload['stage'],
                'search_receipt_id':str(quote.source_receipt_id) if quote.source_receipt_id else None,
                'selected_ids':selected_ids,'reviewed_ids':reviewed_ids,'previous_proposal_id':previous})
    return envelope({'items':items},request.state.request_id)


@router.post('/quotes/{quote_id}/approve',operation_id='approveXverumQuote')
async def approve_quote(workspace_id:uuid.UUID,project_id:uuid.UUID,quote_id:uuid.UUID,payload:QuoteApproval,
    request:Request,principal:Principal=Depends(get_principal)):
    mutation_key=key(request)
    if payload.quote_id!=quote_id:raise ApiError(422,'INVALID_REQUEST','quote identity mismatch')
    async with access(workspace_id,project_id,principal,sales=True) as (session,actor):
        value=await quotes.confirm_quote(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            quote_id,payload.fingerprint,mutation_key)
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.get('/receipts/{receipt_id}',operation_id='getXverumReceipt')
async def get_receipt(workspace_id:uuid.UUID,project_id:uuid.UUID,receipt_id:uuid.UUID,
    request:Request,response:Response,principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        value=await quotes.read_receipt(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),receipt_id)
    return result(value,request,response)


from ...services import xverum_dispatch as dispatch


@router.get('/receipts/{receipt_id}/liability',operation_id='getXverumLiability')
async def liability(workspace_id:uuid.UUID,project_id:uuid.UUID,receipt_id:uuid.UUID,
    request:Request,response:Response,principal:Principal=Depends(get_principal)):
    async with access(workspace_id,project_id,principal,sales=True,admission=False,locks=False) as (session,actor):
        value=await dispatch.read_liability(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),receipt_id)
    response.headers['ETag']=f'"{value.receipt.version}"'
    return envelope(value.model_dump(mode='json'),request.state.request_id)


@router.post('/receipts/{receipt_id}/reconcile',operation_id='reconcileXverumReceipt')
async def reconcile(workspace_id:uuid.UUID,project_id:uuid.UUID,receipt_id:uuid.UUID,
    payload:dispatch.ReconciliationEvidence,request:Request,response:Response,principal:Principal=Depends(get_principal)):
    mutation_key=key(request)
    expected=if_match_version(request.headers.get('If-Match'))
    if expected!=payload.expected_version:raise ApiError(422,'INVALID_REQUEST','revision differs')
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        await service.authority(session,scope,'reconcileXverumReceipt')
        replay=await begin_idempotency(session,workspace_id=workspace_id,actor_id=actor,
            operation_id='reconcileXverumReceipt',key=mutation_key,body=payload.model_dump(mode='json'),
            target={'receipt_id':str(receipt_id)},precondition=f'"{expected}"')
        # Durable evidence replay rechecks current operator authority, independently of key expiry.
        value=await dispatch.reconcile_xverum(session,scope,receipt_id,payload)
        if not replay.replay:complete_idempotency(replay,str(value.id))
    return result(value,request,response)


@router.post('/receipts/{receipt_id}/cancel',operation_id='cancelXverumReceipt')
async def cancel(workspace_id:uuid.UUID,project_id:uuid.UUID,receipt_id:uuid.UUID,
    request:Request,response:Response,principal:Principal=Depends(get_principal)):
    expected=if_match_version(request.headers.get('If-Match'))
    mutation_key=key(request)
    async with access(workspace_id,project_id,principal,sales=True,admission=False) as (session,actor):
        scope=Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor)
        # Ownership may lock a linked thread/task, including on idempotent replay.
        await dispatch.gates(session,workspace_id)
        await quotes.owned_receipt(session,scope,receipt_id)
        replay=await begin_idempotency(session,workspace_id=workspace_id,actor_id=actor,
            operation_id='cancelXverumReceipt',key=mutation_key,body={},
            target={'receipt_id':str(receipt_id)},precondition=f'"{expected}"')
        if replay.replay:value=await quotes.read_receipt(session,scope,receipt_id)
        else:
            value=await dispatch.cancel_receipt(session,scope,receipt_id,expected)
            complete_idempotency(replay,str(value.id))
    return result(value,request,response)


@router.post('/tasks/{task_id}/quotes/{quote_id}/approve',operation_id='approveLinkedXverumQuote')
async def approve_linked(workspace_id:uuid.UUID,project_id:uuid.UUID,task_id:uuid.UUID,quote_id:uuid.UUID,
    payload:QuoteApproval,request:Request,principal:Principal=Depends(get_principal)):
    expected=if_match_version(request.headers.get('If-Match'))
    mutation_key=key(request)
    if payload.quote_id!=quote_id:raise ApiError(422,'INVALID_REQUEST','quote differs')
    async with access(workspace_id,project_id,principal,sales=True) as (session,actor):
        value=await quotes.confirm_quote(session,Scope(workspace_id=workspace_id,project_id=project_id,actor_id=actor),
            quote_id,payload.fingerprint,mutation_key,task_id=task_id,expected_task_version=expected)
    return envelope(value.model_dump(mode='json'),request.state.request_id)
