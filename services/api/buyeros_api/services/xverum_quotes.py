"""Actor-bound five-minute staged quotes; confirmation admits but never dispatches."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.buyers import ProjectBuyer
from ..db.xverum import (XverumQuoteRow as Quote, XverumCreditAccount as Account,
    XverumTariff as Tariff, XverumCreditReservation as Reservation, XverumReceiptRow as Receipt,
    XverumCreditSettlement as Settlement)
from ..sales.contracts import XverumQuote, XverumReceipt, StepReceipt, SearchArguments
from ..sales.context import digest
from . import xverum_connections as connections
from .budget_service import reserve_operation, lock_budget_workspace
from .xverum_credits import capacity


def invalid():return ApiError(409,'XVERUM_QUOTE_INVALID','quote changed or is no longer available')


async def buyer(session,scope,buyer_id):
    row=(await session.execute(select(ProjectBuyer).where(ProjectBuyer.workspace_id==scope.workspace_id,
        ProjectBuyer.project_id==scope.project_id,ProjectBuyer.id==buyer_id)
        .execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None:raise ApiError(404,'NOT_FOUND','buyer not available')
    return row


async def configuration(session,scope,connection_id):
    from .conversation_access import sales_enabled
    if not sales_enabled(scope.workspace_id):raise ApiError(503,'XVERUM_CONFIGURATION_REQUIRED','sales admission is disabled')
    binding=await connections.require_xverum_connection(session,scope)
    if binding.id!=connection_id:raise invalid()
    account=(await session.execute(select(Account).where(Account.workspace_id==scope.workspace_id,
        Account.account_ref==binding.account_ref))).scalar_one_or_none()
    tariff=None if account is None else (await session.execute(select(Tariff).where(
        Tariff.workspace_id==scope.workspace_id,Tariff.account_id==account.id,Tariff.version==binding.tariff_version))).scalar_one_or_none()
    if tariff is None:raise ApiError(503,'XVERUM_TARIFF_REQUIRED','administrator USD tariff required')
    return binding,account,tariff


def quote_fingerprint(payload,scope,buyer_version,account_id,rate,source_digest=None):
    return digest({'quote':{k:v for k,v in payload.items() if k!='fingerprint'},
        'workspace_id':str(scope.workspace_id),'project_id':str(scope.project_id),
        'buyer_version':buyer_version,'account_id':str(account_id),'usd_per_credit':str(rate),'source_digest':source_digest})


async def create(session,scope,connection_id,buyer_id,stage,query,ids,tools,credits,source=None):
    binding,account,tariff=await configuration(session,scope,connection_id)
    native=await buyer(session,scope,buyer_id)
    value=XverumQuote(id=uuid.uuid4(),stage=stage,actor_id=scope.actor_id,
        connection_generation=binding.generation,query=query,provider_ids=ids,tool_plan=tools,
        max_credits=credits,tariff_version=tariff.version,expires_at=datetime.now(timezone.utc)+timedelta(minutes=5),
        fingerprint='0'*64,buyer_id=buyer_id,connection_id=connection_id)
    payload=value.model_dump(mode='json')
    source_digest=None if source is None else evidence_digest(source)
    payload['fingerprint']=quote_fingerprint(payload,scope,native.version,account.id,tariff.usd_per_credit,source_digest)
    session.add(Quote(id=value.id,workspace_id=scope.workspace_id,project_id=scope.project_id,
        actor_id=scope.actor_id,buyer_id=buyer_id,buyer_version=native.version,connection_id=connection_id,
        connection_generation=binding.generation,account_id=account.id,tariff_version=tariff.version,
        expires_at=value.expires_at,fingerprint=payload['fingerprint'],payload=payload,
        source_receipt_id=None if source is None else source.id,source_digest=source_digest))
    await session.flush()
    return XverumQuote.model_validate(payload)


async def quote_search(session,scope,connection_id:uuid.UUID,query:str,
                       target:Literal['company','people'],buyer_id:uuid.UUID) -> XverumQuote:
    if target not in ('company','people'):raise ApiError(422,'INVALID_REQUEST','unsupported search target')
    args=SearchArguments(query=query,page=1,page_size=5)
    return await create(session,scope,connection_id,buyer_id,'search',args.query,[],
        [{'tool':f'search_{target}_xverum','arguments':args.model_dump()}],5)


async def owned_receipt(session,scope,receipt_id,*,_enrichment_id=None):
    from .xverum_dispatch import gates
    await gates(session,scope.workspace_id)
    await connections.authority(session,scope,'useXverumConnection')
    row=(await session.execute(select(Receipt).where(Receipt.id==receipt_id,Receipt.workspace_id==scope.workspace_id,
        Receipt.project_id==scope.project_id,Receipt.actor_id==scope.actor_id))).scalar_one_or_none()
    if row is None:raise ApiError(404,'NOT_FOUND','receipt not available')
    from ..db.xverum import XverumStage
    from .xverum_dispatch import linked_authority
    stage=await session.get(XverumStage,row.id)
    if stage is not None:await linked_authority(session,scope,stage,edit=False,_enrichment_id=_enrichment_id)
    reservation=(await session.execute(select(Reservation).where(Reservation.id==row.reservation_id))).scalar_one()
    return row,reservation


async def quote_details(session,scope,search_receipt_id:uuid.UUID,selected_ids:list[str],include_email:bool) -> XverumQuote:
    from .xverum_dispatch import source_search_evidence
    await source_search_evidence(session,scope,search_receipt_id)
    row,reservation=await owned_receipt(session,scope,search_receipt_id)
    source=(await session.execute(select(Quote).where(Quote.id==reservation.quote_id))).scalar_one()
    original=XverumQuote.model_validate(source.payload)
    binding,_,_=await configuration(session,scope,source.connection_id)
    if row.dispatch_state!='settled' or not row.projection_digest or original.stage!='search' or binding.generation!=original.connection_generation:
        raise invalid()
    people=original.tool_plan[0].tool=='search_people_xverum'
    if (type(include_email) is not bool or not selected_ids or len(selected_ids)>(3 if people else 1)
        or len(set(selected_ids))!=len(selected_ids) or any(not isinstance(i,str) or not i.isascii() or not i.isdecimal() or i not in row.returned_ids for i in selected_ids)
        or (include_email and not people)):
        raise ApiError(422,'INVALID_REQUEST','select only bounded returned identities')
    tools=[]
    for identity in selected_ids:
        tools.append({'tool':'enrich_person_xverum' if people else 'enrich_company_xverum',
            'arguments':{'id' if people else 'company_id':identity}})
        if include_email:tools.append({'tool':'get_email_xverum','arguments':{'id':identity}})
    return await create(session,scope,source.connection_id,source.buyer_id,'detail',None,selected_ids,tools,
        len(selected_ids)*(6 if include_email else 4),row)


def evidence_digest(row):
    return digest({'id':str(row.id),'reservation_id':str(row.reservation_id),
        'returned_ids':row.returned_ids,'projection_digest':row.projection_digest,'state':row.dispatch_state})


def step(row,reservation):
    return StepReceipt(id=row.id,task_id=None,native_operation_id=reservation.operation_id,
        dispatch_state={'reserved':'queued','dispatched':'submitting','settled':'received',
            'outcome_unknown':'unknown','cancelled':'cancelled'}[row.dispatch_state],
        reservation_ids=(reservation.usd_reservation_id,))


async def confirm_quote(session,scope,quote_id:uuid.UUID,fingerprint:str,key:str,*,task_id=None,expected_task_version=None) -> StepReceipt:
    if not key or len(key)>200:raise ApiError(422,'INVALID_REQUEST','operation key required')
    from .policy_service import policy_workspace_lock
    await policy_workspace_lock(session,scope.workspace_id)
    await lock_budget_workspace(session,scope.workspace_id)
    task=None
    if task_id is not None:
        from .sales_tasks import task_row,check_revision
        task=await task_row(session,scope,task_id,edit=True)
    row=(await session.execute(select(Quote).where(Quote.id==quote_id,Quote.workspace_id==scope.workspace_id,
        Quote.project_id==scope.project_id,Quote.actor_id==scope.actor_id))).scalar_one_or_none()
    if row is None:raise ApiError(404,'NOT_FOUND','quote not available')
    binding,account,tariff=await configuration(session,scope,row.connection_id)
    native=await buyer(session,scope,row.buyer_id)
    try:value=XverumQuote.model_validate(row.payload)
    except ValueError:raise invalid() from None
    if row.source_receipt_id is not None:
        from .xverum_dispatch import source_search_evidence
        await source_search_evidence(session,scope,row.source_receipt_id,expected_digest=row.source_digest)
    if (quote_fingerprint(row.payload,scope,native.version,account.id,tariff.usd_per_credit,row.source_digest)!=fingerprint
        or row.fingerprint!=fingerprint or value.fingerprint!=fingerprint
        or value.connection_generation!=binding.generation or row.connection_generation!=binding.generation
        or row.buyer_version!=native.version or row.account_id!=account.id
        or row.expires_at!=value.expires_at
        or not (binding.tariff_version==tariff.version==row.tariff_version==value.tariff_version)
        or value.id!=row.id or value.buyer_id!=row.buyer_id or value.connection_id!=row.connection_id):raise invalid()
    existing=(await session.execute(select(Receipt).where(Receipt.workspace_id==scope.workspace_id,
        Receipt.actor_id==scope.actor_id,Receipt.operation_key==key))).scalar_one_or_none()
    reserved=(await session.execute(select(Reservation).where(Reservation.workspace_id==scope.workspace_id,
        Reservation.quote_id==quote_id))).scalar_one_or_none()
    if existing:
        if reserved is None or existing.reservation_id!=reserved.id:raise ApiError(409,'IDEMPOTENCY_CONFLICT','operation key differs')
        from ..db.xverum import XverumStage
        stage=await session.get(XverumStage,existing.id)
        if stage is None or stage.task_id!=task_id:raise invalid()
        if task is not None:
            check_revision(stage.task_revision,expected_task_version)
            from .xverum_dispatch import linked_authority
            await linked_authority(session,scope,stage,edit=False)
        result=step(existing,reserved)
        return result.model_copy(update={'task_id':task_id})
    if reserved is not None or min(row.expires_at,value.expires_at)<=datetime.now(timezone.utc):raise invalid()
    if task is not None:
        check_revision(task.revision,expected_task_version)
        if task.state not in {'ready_for_review','queued','running','partially_completed'}:
            raise ApiError(409,'INVALID_STATE','task is not ready for a provider stage')
    async with session.begin_nested():
        operation=uuid.uuid4()
        usd=await reserve_operation(session,operation,{'workspace_id':scope.workspace_id,'project_id':scope.project_id,
            'category':'contact_lookup'},tariff.usd_per_credit*value.max_credits,'USD',tariff.version)
        await capacity(session,scope.workspace_id,scope.project_id,account.id,value.max_credits)
        current=await connections.load(session,scope,row.connection_id,lock=True)
        if (current.generation!=binding.generation or current.status!='connected'
            or current.tariff_version!=value.tariff_version):raise invalid()
        reservation=Reservation(id=uuid.uuid4(),workspace_id=scope.workspace_id,project_id=scope.project_id,
            account_id=account.id,quote_id=quote_id,operation_id=operation,max_credits=value.max_credits,
            held_credits=value.max_credits,usd_reservation_id=usd)
        session.add(reservation);await session.flush()
        receipt=Receipt(id=uuid.uuid4(),workspace_id=scope.workspace_id,project_id=scope.project_id,
            actor_id=scope.actor_id,reservation_id=reservation.id,operation_key=key,dispatch_state='reserved',returned_ids=[])
        session.add(receipt);await session.flush()
        from .xverum_dispatch import enqueue
        await enqueue(session,scope,receipt,reservation,row,binding,task=task)
    return step(receipt,reservation).model_copy(update={'task_id':task_id})


async def read_receipt(session,scope,receipt_id,*,_enrichment_id=None):
    row,reservation=await owned_receipt(session,scope,receipt_id,_enrichment_id=_enrichment_id)
    used=(await session.execute(select(Settlement.credits_used).where(Settlement.receipt_id==row.id))).scalar_one_or_none()
    return XverumReceipt(id=row.id,version=row.version,dispatch_state=row.dispatch_state,request_id=row.request_id,
        credits_used=used,held_credits=reservation.held_credits,projection_digest=row.projection_digest)


async def read_quote(session,scope,quote_id):
    await connections.authority(session,scope,'useXverumConnection')
    row=(await session.execute(select(Quote).where(Quote.id==quote_id,Quote.workspace_id==scope.workspace_id,
        Quote.project_id==scope.project_id,Quote.actor_id==scope.actor_id))).scalar_one_or_none()
    if row is None:raise ApiError(404,'NOT_FOUND','quote not available')
    from .sales_retention import require_current
    await require_current(session,scope.workspace_id,[row.id,row.buyer_id])
    if 'tool_plan' not in row.payload:
        raise ApiError(404,'SOURCE_UNAVAILABLE','quote content was purged')
    current=await connections.require_xverum_connection(session,scope)
    if current.id!=row.connection_id or current.generation!=row.connection_generation:
        raise ApiError(409,'STALE_REVISION','quote connection generation changed')
    if row.source_receipt_id is not None:
        from .xverum_dispatch import source_search_evidence
        await source_search_evidence(session,scope,row.source_receipt_id,expected_digest=row.source_digest)
    await buyer(session,scope,row.buyer_id)
    return XverumQuote.model_validate(row.payload)
