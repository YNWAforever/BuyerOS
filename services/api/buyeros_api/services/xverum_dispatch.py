"""Native staged dispatch. No customer transaction spans credentials or MCP IO.

Lock order: runtime/outbox, policy, USD workspace gate, thread/task/model parent,
USD reservation/accounts, credit account/limits, connection, stage/tool receipts.
Recovery records financial truth independently of permission to retain content.
"""
import asyncio
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.session import tenant_session
from ..db.outbox import OutboxEvent
from ..db.xverum import (XverumStage as Stage, XverumToolReceipt as Tool,
    XverumReceiptRow as Receipt, XverumCreditReservation as Reservation,
    XverumQuoteRow as Quote, XverumReconciliation as Reconciliation,
    XverumCreditSettlement as Settlement)
from ..sales.contracts import Scope, XverumQuote, XverumResult, XverumReceipt, ConnectionBinding, ReconciliationEvidence
from ..sales.context import digest, resolve_context
from ..providers.xverum_mcp import XverumTransportError
from . import xverum_connections as connections, xverum_quotes as quotes
from .xverum_credits import settle_credits
from .budget_service import lock_budget_workspace
from .policy_service import policy_workspace_lock, evaluate_current_policy

# Versioned code-owned projection/protocol binding, never a caller's assertion.
CONTRACT_HASH = digest({'protocol':'2025-06-18','projection':'professional-only.v1',
    'tools':['search_company_xverum','search_people_xverum','enrich_company_xverum',
             'enrich_person_xverum','get_email_xverum']})




_EVIDENCE_STACK=ContextVar('xverum_evidence_stack',default=())


async def gates(session, workspace_id):
    await policy_workspace_lock(session, workspace_id)
    await lock_budget_workspace(session, workspace_id)


async def stage_rows(session, receipt_id):
    row = await session.get(Receipt, receipt_id, populate_existing=True)
    if row is None:
        raise ApiError(404,'NOT_FOUND','receipt unavailable')
    reservation = await session.get(Reservation,row.reservation_id)
    quote = await session.get(Quote,reservation.quote_id)
    stage = await session.get(Stage,row.id,populate_existing=True)
    tools = list((await session.scalars(select(Tool).where(Tool.stage_id==row.id)
        .order_by(Tool.ordinal).execution_options(populate_existing=True))).all())
    return row,reservation,quote,stage,tools


def scope_for(row):
    return Scope(workspace_id=row.workspace_id,project_id=row.project_id,actor_id=row.actor_id)


async def financial_receipt(session,row,reservation):
    used = await session.scalar(select(Settlement.credits_used).where(Settlement.receipt_id==row.id))
    return XverumReceipt(id=row.id,version=row.version,dispatch_state=row.dispatch_state,
        request_id=row.request_id,credits_used=used,held_credits=reservation.held_credits,
        projection_digest=row.projection_digest)


async def invocation_counts(session,task_id):
    from ..db.sales_execution import SalesExecution, SalesStep
    models = list((await session.scalars(select(SalesStep).join(SalesExecution,
        SalesExecution.id==SalesStep.execution_id).where(SalesExecution.task_id==task_id))).all())
    providers = list((await session.scalars(select(Tool).join(Stage,Stage.id==Tool.stage_id)
        .where(Stage.task_id==task_id))).all())
    active = sum(x.state in {'submitting','unknown'} for x in models+providers)
    return len(models)+len(providers),len(models),active


async def require_bounds(session,task_id,*,additional=0,model_additional=0):
    total,models,active=await invocation_counts(session,task_id)
    if total+additional+model_additional>16 or models+model_additional>8:
        raise ApiError(409,'EXECUTION_LIMIT','separately reviewed follow-on task required')
    return active


async def combined_task_state(session,task_id,fallback):
    from ..db.sales_execution import SalesExecution,SalesStep
    from ..execution.sales_tasks import aggregate_state
    provider_states=list((await session.scalars(select(Tool.state).join(Stage,Stage.id==Tool.stage_id)
        .where(Stage.task_id==task_id))).all())
    if not provider_states:return fallback
    model_states=list((await session.scalars(select(SalesStep.state).join(SalesExecution,
        SalesExecution.id==SalesStep.execution_id).where(SalesExecution.task_id==task_id))).all())
    states=model_states+[{'nonaccepted':'failed'}.get(s,s) for s in provider_states]
    if set(states)=={'queued'}:return 'queued'
    return aggregate_state(states,cancelled=fallback in {'cancelled','cancel_requested'} or set(states)=={'cancelled'})


async def sync_task(session,receipt_id):
    stage=await session.get(Stage,receipt_id)
    if stage is None or stage.task_id is None:return
    from ..db.sales_tasks import SalesTask
    from ..db.conversation_threads import ConversationThread
    from ..execution.sales_tasks import set_state
    # Trusted content-free status recovery is allowed after actor revocation.
    await session.execute(select(ConversationThread.id).where(ConversationThread.id==stage.thread_id).with_for_update())
    row=await session.scalar(select(SalesTask).where(SalesTask.id==stage.task_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is not None:
        await set_state(session,row,await combined_task_state(session,row.id,row.state))


async def linked_authority(session,scope,stage,*,edit=True,_enrichment_id=None):
    if stage.task_id is None:
        return None
    from .sales_tasks import task_row
    from ..execution.sales_tasks import intake_hash
    task=await task_row(session,scope,stage.task_id,edit=edit)
    context=await resolve_context(session,scope,task.source_refs,_enrichment_id=_enrichment_id)
    if (task.thread_id!=stage.thread_id or context.digest!=stage.context_digest
            or intake_hash(task)!=stage.intake_hash):
        raise ApiError(409,'STALE_REVISION','linked task context changed')
    if edit and task.state in {'cancelled','cancel_requested','completed','failed'}:
        raise ApiError(409,'INVALID_STATE','linked task is not dispatchable')
    return task


async def enqueue(session,scope,row,reservation,quote,binding,*,task=None):
    """Called inside Task8 admission savepoint; standalone cannot be relinked later."""
    from ..execution.sales_tasks import intake_hash
    from ..sales.registry import load_skill
    value=XverumQuote.model_validate(quote.payload)
    context=None
    if task is not None:
        skill=load_skill(task.skill_id,task.skill_version)
        if any(t.tool not in skill.allowed_actions for t in value.tool_plan):
            raise ApiError(422,'INVALID_REQUEST','tool is outside linked skill')
        if task.arguments.get('buyer_id')!=str(quote.buyer_id):
            raise ApiError(409,'STALE_REVISION','linked buyer differs')
        context=await resolve_context(session,scope,task.source_refs)
        await require_bounds(session,task.id,additional=len(value.tool_plan))
    event_id=uuid.uuid5(row.id,'xverum-outbox')
    session.add(OutboxEvent(id=event_id,workspace_id=scope.workspace_id,
        intent_key='xverum:'+str(row.id),event_type='xverum.step',payload={'step_id':str(row.id)},state='ready'))
    await session.flush()
    row.outbox_id=event_id
    session.add(Stage(id=row.id,workspace_id=scope.workspace_id,project_id=scope.project_id,
        task_id=task.id if task else None,thread_id=task.thread_id if task else None,
        task_revision=task.revision if task else None,
        context_digest=context.digest if context else None,intake_hash=intake_hash(task) if task else None,
        binding=binding.model_dump(mode='json'),cancelled=False))
    await session.flush()
    for i,tool in enumerate(value.tool_plan):
        session.add(Tool(id=uuid.uuid5(row.id,str(i)),workspace_id=scope.workspace_id,stage_id=row.id,
            ordinal=i,tool=tool.tool,arguments=tool.arguments.model_dump(mode='json'),state='queued',attempts=0))
    await session.flush()
    await sync_task(session,row.id)


async def policy(session,scope,quote,binding):
    from .provider_policy_context import company_context
    native=await quotes.buyer(session,scope,quote.buyer_id)
    # Stage evidence review shares enrichment purpose; canonical contact-point reads are separate.
    use=await company_context(session,project_id=scope.project_id,company_id=native.company_id,
        action='contact.enrich',provider_name='xverum',
        account_reference=binding.account_ref,contract_sha256=CONTRACT_HASH)
    result=await evaluate_current_policy(session,{'workspace_id':scope.workspace_id,
        'project_id':scope.project_id,'company_id':native.company_id},'contact_research',
        datetime.now(timezone.utc),use_context=use)
    if not result['allowed']:
        raise ApiError(403,'POLICY_BLOCKED','current provider purpose and suppression gate denied')


async def current_authority(session,row,reservation,quote,stage,*,dispatch=True):
    scope=scope_for(row)
    await connections.authority(session,scope,'useXverumConnection')
    await linked_authority(session,scope,stage,edit=dispatch)
    # Immutable quote dependency carries source privacy even into standalone stages.
    # This also runs for post-response retention (dispatch=False).
    if quote.source_receipt_id is not None:
        await source_search_evidence(session,scope,quote.source_receipt_id,expected_digest=quote.source_digest)
    binding=ConnectionBinding.model_validate(stage.binding)
    current=await connections.require_generation(session,scope,binding)
    if current!=binding:raise quotes.invalid()
    if dispatch:
        from ..settings import get_settings
        from ..execution.config import get_settings as worker_settings
        from ..db.worker_execution import WorkerRuntimeControl
        from ..db.budget import BudgetReservation
        from .conversation_access import sales_enabled
        control=(await session.execute(select(WorkerRuntimeControl.backend,WorkerRuntimeControl.enabled))).one()
        if (not sales_enabled(scope.workspace_id) or not get_settings().paid_admission_enabled
            or not worker_settings().paid_dispatch_enabled or not get_settings().cloudflare_execution_enabled
            or control.backend!='cloudflare' or not control.enabled or stage.cancelled):
            raise ApiError(409,'EXECUTION_DISABLED','provider dispatch disabled')
        connections.provider()  # readiness declaration only; never credential IO in this transaction
        current=await connections.require_xverum_connection(session,scope)
        if current!=binding or quote.expires_at<=datetime.now(timezone.utc):
            raise quotes.invalid()
        native=await quotes.buyer(session,scope,quote.buyer_id)
        if native.version!=quote.buyer_version:
            raise quotes.invalid()
        _,account,tariff=await quotes.configuration(session,scope,quote.connection_id)
        value=XverumQuote.model_validate(quote.payload)
        if (account.id!=quote.account_id or tariff.version!=quote.tariff_version
            or value.connection_generation!=binding.generation or value.connection_id!=binding.id
            or value.actor_id!=row.actor_id or value.buyer_id!=quote.buyer_id
            or value.expires_at!=quote.expires_at or value.fingerprint!=quote.fingerprint
            or quotes.quote_fingerprint(quote.payload,scope,native.version,account.id,
                tariff.usd_per_credit,quote.source_digest)!=quote.fingerprint):
            raise quotes.invalid()
        hold=await session.get(BudgetReservation,reservation.usd_reservation_id)
        if (hold is None or hold.state!='active' or hold.operation_id!=reservation.operation_id
            or hold.currency!='USD' or hold.price_version!=quote.tariff_version
            or hold.remaining_hold!=hold.upper_bound or hold.upper_bound!=tariff.usd_per_credit*value.max_credits
            or reservation.max_credits!=value.max_credits or reservation.held_credits!=reservation.max_credits):
            raise ApiError(409,'BUDGET_LIMIT','admitted holds unavailable')
    await policy(session,scope,quote,binding)
    return binding


async def release_known_unsubmitted(session,row,reservation,tools):
    if any(t.state not in {'queued','nonaccepted','cancelled'} for t in tools):
        return False
    from .settlement import release_unsubmitted_operation
    if row.dispatch_state!='cancelled':
        await release_unsubmitted_operation(session,reservation.operation_id)
        reservation.held_credits=0
        row.dispatch_state='cancelled';row.version+=1
    for tool in tools:
        if tool.state in {'queued','nonaccepted'}:tool.state='cancelled'
    await session.flush()
    await sync_task(session,row.id)
    return True


async def claim(session,receipt_id,execution):
    if not await execution.guard(session):
        raise ApiError(409,'STALE_FENCE','native execution fence changed')
    await gates(session,execution.envelope.workspace_id)
    row,reservation,quote,stage,tools=await stage_rows(session,receipt_id)
    if (stage is None or row.outbox_id!=execution.row.id or execution.row.event_type!='xverum.step'
        or execution.row.payload!={'step_id':str(row.id)} or row.workspace_id!=execution.envelope.workspace_id):
        raise ApiError(409,'INVALID_INTENT','native receipt binding differs')
    if row.dispatch_state in {'settled','cancelled','outcome_unknown'}:
        return None
    # A committed claim is never queued again, even if the process died before HTTP.
    if any(t.state in {'submitting','unknown'} for t in tools):
        await mark_unknown(session,row,tools)
        return None
    try:
        binding=await current_authority(session,row,reservation,quote,stage)
    except (ApiError,ValueError):
        stage.cancelled=True
        if not await release_known_unsubmitted(session,row,reservation,tools):
            for t in tools:
                if t.state=='queued':t.state='cancelled'
            await finalize_stage(session,row,reservation,tools)
        return None
    if stage.task_id and await require_bounds(session,stage.task_id)>=2:
        return None
    tool=next((t for t in tools if t.state=='queued'),None)
    if tool is None:
        await finalize_stage(session,row,reservation,tools)
        return None
    tool.claim_id=uuid.uuid4();tool.attempts+=1;tool.state='submitting'
    row.claim_id=tool.claim_id;row.claimed_at=datetime.now(timezone.utc)
    row.dispatch_state='dispatched';row.version+=1
    await session.flush()
    await sync_task(session,row.id)
    return scope_for(row),binding,tool.id,tool.claim_id,tool.tool,tool.arguments


async def mark_unknown(session,row,tools):
    for tool in tools:
        if tool.state=='submitting':tool.state='unknown'
    if row.dispatch_state not in {'settled','cancelled','outcome_unknown'}:
        row.dispatch_state='outcome_unknown';row.version+=1
    await session.flush()
    await sync_task(session,row.id)


async def finalize_stage(session,row,reservation,tools):
    if row.dispatch_state in {'settled','cancelled'}:return
    if any(t.state in {'submitting','unknown'} for t in tools):
        await mark_unknown(session,row,tools)
    elif all(t.state in {'received','nonaccepted','cancelled'} for t in tools):
        if all(t.state!='received' for t in tools):
            await release_known_unsubmitted(session,row,reservation,tools)
        else:
            usage=sum(t.credits_used for t in tools if t.state=='received')
            row.dispatch_state='dispatched'
            await settle_credits(session,row.id,usage)
            retained=[t for t in tools if t.projection is not None]
            if len(retained)==sum(t.state=='received' for t in tools):
                row.projection_digest=digest([t.projection_digest for t in retained])
            await session.flush()
    await sync_task(session,row.id)


async def persist_result(session,receipt_id,tool_id,claim_id,result):
    initial=await session.get(Receipt,receipt_id)
    await gates(session,initial.workspace_id)
    row,reservation,quote,stage,tools=await stage_rows(session,receipt_id)
    tool=next(t for t in tools if t.id==tool_id)
    if tool.claim_id!=claim_id:
        raise ApiError(409,'STALE_REVISION','tool claim differs')
    result=XverumResult.model_validate(result.model_dump(mode='json'))
    if result.tool!=tool.tool:
        raise ValueError('tool result differs')
    ceiling=5 if tool.tool.startswith('search_') else 2 if tool.tool=='get_email_xverum' else 4
    if result.credits_used>ceiling:
        await mark_unknown(session,row,tools)
        return
    if tool.state=='received':
        if (tool.request_id,tool.credits_used)!=(result.request_id,result.credits_used):
            raise ApiError(409,'IDEMPOTENCY_CONFLICT','provider evidence differs')
        return
    if row.dispatch_state in {'settled','cancelled'}:return
    if tool.state not in {'submitting','unknown'}:raise ValueError('tool was not claimed')
    # Financial observations survive revocation, projected content does not.
    retain=False
    try:
        await current_authority(session,row,reservation,quote,stage,dispatch=False)
        retain=not stage.cancelled
    except (ApiError,ValueError):pass
    tool.request_id=result.request_id;tool.credits_used=result.credits_used;tool.state='received'
    row.request_id=result.request_id if len(tools)==1 else None
    if retain:
        projection=result.projection.model_dump(mode='json')
        tool.projection=projection;tool.projection_digest=digest(projection)
        # Short-lived review evidence. Current policy is rechecked on every read.
        tool.expires_at=datetime.now(timezone.utc)+timedelta(hours=24)
        if tool.tool.startswith('search_'):
            ids=[x['id'] for x in projection['results']]
            if len(ids)!=len(set(ids)) or any(not i.isascii() or not i.isdecimal() for i in ids):
                raise ValueError('invalid returned identities')
            row.returned_ids=ids
    row.version+=1
    await finalize_stage(session,row,reservation,tools)
    await session.flush()


async def dispatch_xverum(engine,step_id:uuid.UUID,*,execution=None)->XverumReceipt:
    if execution is None:raise ValueError('native runtime claim required')
    workspace_id=execution.envelope.workspace_id
    for _ in range(12):  # <=6 approved tools, <=2 proven-nonaccepted attempts each
        async with tenant_session(engine,workspace_id) as session:
            prepared=await claim(session,step_id,execution)
        if prepared is None:break
        scope,binding,tool_id,claim_id,tool,arguments=prepared
        async def before_dispatch(session):
            if not await execution.guard(session):raise ValueError('stale native fence')
            await gates(session,workspace_id)
            row,reservation,quote,stage,tools=await stage_rows(session,step_id)
            current=next(t for t in tools if t.id==tool_id)
            if current.claim_id!=claim_id or current.state!='submitting':raise ValueError('stale tool claim')
            await current_authority(session,row,reservation,quote,stage)
        try:
            result=await connections.call_xverum(lambda:tenant_session(engine,workspace_id),
                scope,binding,tool,arguments,authorize=before_dispatch)
            async with tenant_session(engine,workspace_id) as session:
                await persist_result(session,step_id,tool_id,claim_id,result)
        except (Exception,asyncio.CancelledError) as exc:
            retry=False
            async with tenant_session(engine,workspace_id) as session:
                await gates(session,workspace_id)
                row,reservation,quote,stage,tools=await stage_rows(session,step_id)
                current=next(t for t in tools if t.id==tool_id)
                if current.claim_id==claim_id and current.state in {'submitting','unknown'}:
                    if isinstance(exc,XverumTransportError) and exc.definitely_nonaccepted:
                        current.state='nonaccepted'
                        retry=(current.attempts<2 and not stage.cancelled and
                            quote.expires_at>datetime.now(timezone.utc)+timedelta(seconds=1))
                        if retry:current.state='queued'
                        else:
                            for t in tools:
                                if t.state=='queued':t.state='cancelled'
                            await finalize_stage(session,row,reservation,tools)
                    else:await mark_unknown(session,row,tools)
            if retry:
                await asyncio.sleep(.1)
                continue
            break
    async with tenant_session(engine,workspace_id) as session:
        row,reservation,_,_,_=await stage_rows(session,step_id)
        return await financial_receipt(session,row,reservation)


async def execute_claimed(engine,execution):
    from .worker_execution import outcome
    step_id=uuid.UUID(execution.row.payload['step_id'])
    value=await dispatch_xverum(engine,step_id,execution=execution)
    async with tenant_session(engine,execution.envelope.workspace_id) as session:
        if not await execution.guard(session):return outcome('stale','STALE_FENCE')
        state='done' if value.dispatch_state in {'settled','cancelled'} else 'reconcile' if value.dispatch_state=='outcome_unknown' else 'retry_later'
        final=outcome(state,'PROVIDER_UNKNOWN' if state=='reconcile' else 'IN_PROGRESS' if state=='retry_later' else 'OK',
            retry_at=datetime.now(timezone.utc)+timedelta(seconds=30) if state=='retry_later' else None)
        execution.row.state='ready' if state=='retry_later' else 'done'
        execution.row.lease_owner=execution.row.lease_expires_at=None
        execution.finish(final)
        return final


async def recover_outbox(session,outbox):
    await gates(session,outbox.workspace_id)
    row,reservation,quote,stage,tools=await stage_rows(session,uuid.UUID(outbox.payload['step_id']))
    if row.outbox_id!=outbox.id:raise ValueError('foreign recovery outbox')
    if any(t.state in {'submitting','unknown'} for t in tools):await mark_unknown(session,row,tools)
    return row.dispatch_state in {'settled','cancelled','outcome_unknown'},False,False


async def cancel_receipt(session,scope,receipt_id,expected_version):
    await gates(session,scope.workspace_id)
    row,reservation=await quotes.owned_receipt(session,scope,receipt_id)
    row,reservation,quote,stage,tools=await stage_rows(session,receipt_id)
    await linked_authority(session,scope,stage,edit=False)
    if row.version!=expected_version:raise ApiError(409,'STALE_REVISION','receipt revision changed')
    if not stage.cancelled:
        stage.cancelled=True
        row.version+=1
    if not await release_known_unsubmitted(session,row,reservation,tools):
        for t in tools:
            if t.state=='queued':t.state='cancelled'
        await finalize_stage(session,row,reservation,tools)
    return await financial_receipt(session,row,reservation)


async def reconcile_xverum(session,scope,receipt_id:uuid.UUID,evidence:ReconciliationEvidence)->XverumReceipt:
    evidence=ReconciliationEvidence.model_validate(evidence)
    await gates(session,scope.workspace_id)
    # Same current operational role as native enrichment reconciliation; no transcript access.
    await connections.authority(session,scope,'reconcileXverumReceipt')
    row,reservation,quote,stage,tools=await stage_rows(session,receipt_id)
    if row.workspace_id!=scope.workspace_id or row.project_id!=scope.project_id:
        raise ApiError(404,'NOT_FOUND','receipt unavailable')
    fingerprint=digest({'receipt_id':str(receipt_id),'account_id':str(quote.account_id),
        'connection_id':str(quote.connection_id),'generation':quote.connection_generation,
        'evidence':evidence.model_dump(mode='json')})
    existing=await session.scalar(select(Reconciliation).where(Reconciliation.receipt_id==receipt_id,
        Reconciliation.evidence_ref==evidence.evidence_ref))
    if existing:
        if existing.fingerprint!=fingerprint:raise ApiError(409,'IDEMPOTENCY_CONFLICT','repair evidence differs')
        return await financial_receipt(session,row,reservation)
    if row.version!=evidence.expected_version:raise ApiError(409,'STALE_REVISION','receipt revision changed')
    if row.dispatch_state not in {'dispatched','outcome_unknown'}:
        raise ApiError(409,'INVALID_STATE','receipt is not awaiting reconciliation')
    selected=next((t for t in tools if t.id==evidence.tool_receipt_id),None) if evidence.tool_receipt_id else tools[0] if len(tools)==1 else None
    if evidence.resolution!='unknown' and selected is None:
        raise ApiError(422,'INVALID_REQUEST','exact tool receipt identity required')
    if evidence.resolution=='usage':
        ceiling=5 if selected.tool.startswith('search_') else 2 if selected.tool=='get_email_xverum' else 4
        if (not evidence.provider_request_id or evidence.authoritative_usage is None
            or evidence.authoritative_usage>ceiling or selected.state not in {'submitting','unknown','received'}
            or (selected.request_id and selected.request_id!=evidence.provider_request_id)):
            raise ApiError(422,'INVALID_REQUEST','exact authoritative tool usage required')
        if selected.credits_used is not None and selected.credits_used!=evidence.authoritative_usage:
            raise ApiError(409,'IDEMPOTENCY_CONFLICT','tool usage differs')
        selected.request_id=evidence.provider_request_id
        selected.credits_used=evidence.authoritative_usage
        selected.state='received'
        row.request_id=evidence.provider_request_id if len(tools)==1 else None
    elif evidence.resolution=='non_dispatch':
        if evidence.authoritative_usage not in (None,0) or selected.request_id or selected.state=='received':
            raise ApiError(409,'IDEMPOTENCY_CONFLICT','non-dispatch conflicts with retained evidence')
        selected.state='nonaccepted'
    else:
        await mark_unknown(session,row,tools)
    if not stage.cancelled:
        stage.cancelled=True  # repair never opens a new dispatch/retry path
        row.version+=1
    if evidence.resolution!='unknown':
        for tool in tools:
            if tool.state=='queued':tool.state='cancelled'
        row.version+=1
        await finalize_stage(session,row,reservation,tools)
    session.add(Reconciliation(id=uuid.uuid4(),workspace_id=scope.workspace_id,receipt_id=row.id,
        actor_id=scope.actor_id,evidence_ref=evidence.evidence_ref,fingerprint=fingerprint,
        expected_version=evidence.expected_version,resolution=evidence.resolution))
    await session.flush()
    return await financial_receipt(session,row,reservation)


async def source_search_evidence(session,scope,receipt_id,*,expected_digest=None,_enrichment_id=None):
    """Exactly one terminal search dependency; never traverse a detail chain.

    The immutable quote's source receipt/digest retains the original stage's
    linked authority/context. Do not copy its projection into downstream scope.
    All entry points take workspace gates before acquiring either thread lock.
    """
    await gates(session,scope.workspace_id)
    await quotes.owned_receipt(session,scope,receipt_id,_enrichment_id=_enrichment_id)
    row,reservation,quote,stage,tools=await stage_rows(session,receipt_id)
    from .sales_retention import require_current
    await require_current(session,scope.workspace_id,[receipt_id])
    value=XverumQuote.model_validate(quote.payload)
    if (stage is None or quote.source_receipt_id is not None or value.stage!='search'
        or len(tools)!=1 or not tools[0].tool.startswith('search_')
        or not row.projection_digest or (expected_digest is not None and quotes.evidence_digest(row)!=expected_digest)):
        raise quotes.invalid()
    # read_evidence cannot recurse here: a search with any parent was rejected.
    evidence=await read_evidence(session,scope,receipt_id,_enrichment_id=_enrichment_id)
    if (len(evidence)!=1 or tools[0].state!='received'
        or digest(evidence[0]['projection'])!=tools[0].projection_digest
        or digest([tools[0].projection_digest])!=row.projection_digest
        or [card['id'] for card in evidence[0]['projection']['results']]!=list(row.returned_ids)):
        raise quotes.invalid()
    return evidence[0]


async def read_evidence(session,scope,receipt_id,*,_enrichment_id=None):
    await gates(session,scope.workspace_id)
    await quotes.owned_receipt(session,scope,receipt_id,_enrichment_id=_enrichment_id)
    row,reservation,quote,stage,tools=await stage_rows(session,receipt_id)
    from .sales_retention import require_current
    await require_current(session,scope.workspace_id,[receipt_id,quote.connection_id,quote.buyer_id,*[t.id for t in tools]])
    native=await quotes.buyer(session,scope,quote.buyer_id)
    transition_digests=None
    if native.version!=quote.buyer_version:
        if _enrichment_id is None:
            raise ApiError(409,'STALE_REVISION','provider evidence buyer revision changed')
        from .xverum_enrichment import _transition_source_digests
        transition_digests=await _transition_source_digests(session,scope,_enrichment_id,receipt_id,quote)
    source=None
    if quote.source_receipt_id is not None:
        source=await source_search_evidence(session,scope,quote.source_receipt_id,
            expected_digest=quote.source_digest,_enrichment_id=_enrichment_id)
    await linked_authority(session,scope,stage,edit=False,_enrichment_id=_enrichment_id)
    await connections.require_generation(session,scope,ConnectionBinding.model_validate(stage.binding))
    await policy(session,scope,quote,ConnectionBinding.model_validate(stage.binding))
    if row.dispatch_state!='settled':raise ApiError(409,'INVALID_STATE','provider evidence is unresolved')
    now=datetime.now(timezone.utc)
    # Retained projections cannot become a second copy of a native quarantined
    # subject. This also covers person-detail sources without an email body.
    from ..db.runs import ContactPoint,Person
    from sqlalchemy import or_
    for tool in tools:
        identity=tool.arguments.get('id')
        pid=uuid.uuid5(native.company_id,str(quote.connection_id)+':'+identity) if identity else None
        emails=[x['email'].lower() for x in (tool.projection or {}).get('emails',[])]
        matches=list((await session.scalars(select(ContactPoint).where(ContactPoint.company_id==native.company_id,
            or_(ContactPoint.person_id==pid if pid else False,ContactPoint.normalized_value.in_(emails))))).all())
        if any(c.quarantined or c.validity=='unavailable' or not c.retention_expires_at or c.retention_expires_at<=now for c in matches):
            raise ApiError(403,'POLICY_BLOCKED','native subject unavailable')
        person=await session.get(Person,pid) if pid else None
        if person and (not person.retention_expires_at or person.retention_expires_at<=now):
            raise ApiError(403,'POLICY_BLOCKED','native subject unavailable')
    evidence=[{'id':str(t.id),'version':1,'receipt_id':str(row.id),'tool':t.tool,
        'buyer_id':str(quote.buyer_id),'buyer_version':quote.buyer_version,
        'connection_id':str(quote.connection_id),'connection_generation':quote.connection_generation,
        'provider_ids':list(row.returned_ids) if t.tool.startswith('search_') else
            [t.arguments.get('id') or t.arguments.get('company_id')],
        'request_id':t.request_id,'projection_digest':t.projection_digest,'projection':t.projection,
        'retrieved_at':(t.expires_at-timedelta(hours=24)).isoformat(),
        'expires_at':min(t.expires_at,datetime.fromisoformat(source['expires_at']) if source else t.expires_at).isoformat()} for t in tools
        if t.projection is not None and t.expires_at and t.expires_at>now]
    if transition_digests is not None and {value['id']:digest(value) for value in evidence}!=transition_digests:
        raise ApiError(409,'STALE_REVISION','reviewed producer source changed')
    return evidence


async def resolve_evidence(session,scope,ref,*,_enrichment_id=None):
    """Task10 source authority: exact immutable per-tool identity, never a model ID."""
    if ref.version!=1 or ref.locator!='provider_evidence:'+str(ref.id):
        raise ValueError('invalid provider evidence reference')
    tool=await session.get(Tool,ref.id)
    if tool is None:raise ValueError('provider evidence unavailable')
    if _enrichment_id is not None:
        from .xverum_enrichment import load_record
        producer=await load_record(session,scope,_enrichment_id)
        # Other task-selected sources receive ordinary authority, never borrow
        # the producer's transition or its internal parent-search exception.
        if ref.model_dump(mode='json') not in producer.proposal['source_refs']:
            _enrichment_id=None
    stack=_EVIDENCE_STACK.get()
    if ref.id in stack or len(stack)>=32: raise ValueError('cyclic provider context dependency')
    token=_EVIDENCE_STACK.set(stack+(ref.id,))
    try: rows=await read_evidence(session,scope,tool.stage_id,_enrichment_id=_enrichment_id)
    finally: _EVIDENCE_STACK.reset(token)
    value=next((r for r in rows if r['id']==str(ref.id)),None)
    if value is None:raise ValueError('provider evidence expired or unavailable')
    return value


async def read_liability(session,scope,receipt_id):
    from ..sales.contracts import XverumLiability,XverumToolLiability
    await gates(session,scope.workspace_id)
    await connections.authority(session,scope,'reconcileXverumReceipt')
    row,reservation,quote,stage,tools=await stage_rows(session,receipt_id)
    if row.project_id!=scope.project_id or row.workspace_id!=scope.workspace_id:
        raise ApiError(404,'NOT_FOUND','receipt unavailable')
    return XverumLiability(receipt=await financial_receipt(session,row,reservation),
        connection_id=quote.connection_id,connection_generation=quote.connection_generation,
        account_ref=stage.binding['account_ref'],tools=[XverumToolLiability(id=t.id,ordinal=t.ordinal,
            tool=t.tool,state=t.state,request_id=t.request_id,credits_used=t.credits_used) for t in tools])
