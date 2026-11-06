"""Durable sales admission and claim/await/receipt, with no automatic retries.

Lock order: native runtime/outbox, policy workspace, budget workspace, thread, task,
parent, children, reservation. Read-only recovery omits policy and budget locks.
No transaction crosses external IO. Unknown children keep their debit and hold.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.sales_execution import SalesReview, SalesExecution, SalesStep
from ..db.sales_tasks import SalesTask
from ..db.outbox import OutboxEvent
from ..db.session import tenant_session
from ..sales import actions
from ..sales.contracts import (Scope, ActionProposal, SalesModelRequest, SalesModelResult,
    SalesSectionCandidate, ModelUsage, StepReceipt, ExecutionReview)
from ..sales.context import digest, durable_refs, resolve_context
from ..sales.model import make_basis, validate_basis, wire_basis, validate_proposal
from ..sales.planning import plan_task
from ..sales.registry import load_skill, validate_action
from ..services import sales_tasks as tasks


def aggregate_state(states, *, cancelled):
    states = set(states)
    if 'unknown' in states: return 'outcome_unknown'
    if 'submitting' in states: return 'cancel_requested' if cancelled else 'running'
    if cancelled: return 'cancelled'
    if 'queued' in states: return 'running'
    if states == {'received'}: return 'ready_for_review'
    if 'received' in states: return 'partially_completed'
    return 'failed'


def recovery_state(state):
    return 'unknown' if state in {'submitting','unknown'} else state


def debit(parent, *, active, liability):
    if (not isinstance(liability,Decimal) or not liability.is_finite() or liability <= 0
        or parent.calls_started >= parent.max_calls or active >= parent.max_concurrency
        or parent.consumed_usd + liability > parent.upper_bound):
        raise ValueError('admitted parent call/concurrency/liability bound exhausted')
    parent.calls_started += 1
    parent.consumed_usd += liability


def validate_review(review, scope, task, fingerprint, now):
    if (review is None or review.revoked or review.expires_at <= now
        or (review.workspace_id,review.project_id,review.actor_id,review.task_id,review.task_revision,review.fingerprint)
        != (scope.workspace_id,scope.project_id,scope.actor_id,task.id,task.revision,fingerprint)):
        raise ValueError('current actor/scope/revision-bound approval required')


def validate_receipt_basis(basis):
    parsed = validate_basis(basis)
    # Revalidation is deliberately inside the durable receipt owner as well as the model.
    durable_refs(parsed.request.context.refs)
    return parsed


def intake_hash(row):
    return digest({'skill_id':row.skill_id,'skill_version':row.skill_version,'arguments':row.arguments,
        'source_refs':row.source_refs,'context_digest':row.context_digest,'intake_history':row.intake_history})


async def configuration(session, scope, row):
    from ..db.icp import Project
    from ..db.worker_execution import WorkerRuntimeControl
    from ..settings import get_settings
    from ..services.conversation_access import sales_enabled
    from ..services.policy_service import evaluate_current_policy
    from ..services.research_policy_context import research_use
    from ..services.conversation_reply import resolve_sources
    if not sales_enabled(scope.workspace_id):
        raise ApiError(503,'SALES_MODEL_UNAVAILABLE','sales execution is disabled')
    control=(await session.execute(select(WorkerRuntimeControl.backend,WorkerRuntimeControl.enabled))).one()
    if control.backend!='cloudflare' or not control.enabled or not get_settings().cloudflare_execution_enabled:
        raise ApiError(503,'SALES_MODEL_UNAVAILABLE','reviewed native execution runtime is required')
    project = (await session.execute(select(Project).where(Project.workspace_id==scope.workspace_id,
        Project.id==scope.project_id,Project.status=='active'))).scalar_one()
    market = sorted(project.markets)[0] if project.markets else ''
    language = row.arguments.get('language','en')
    if language not in project.language_preferences:
        raise ValueError('project language unavailable')
    item = actions.selected(market,language)
    # Selected approved sources retain the native paid_eligible policy boundary.
    refs = durable_refs(row.source_refs)
    if any(ref.kind=='output' for ref in refs):
        from ..services.sales_outputs import policy_source_refs
        refs=await policy_source_refs(session,scope,refs)
    provider_refs=[ref for ref in refs if ref.kind=='provider_evidence']
    if provider_refs:
        from ..services.xverum_dispatch import resolve_evidence
        for ref in provider_refs: await resolve_evidence(session,scope,ref)
    native_refs=[ref for ref in refs if ref.kind in {'buyer','profile','run'}]
    native_urls=[];profile_documents=set()
    if native_refs:
        native_context=await resolve_context(session,scope,native_refs)
        from ..sales.native_sources import policy_documents
        from ..services.research_policy_context import evidence_urls
        document_ids=policy_documents(native_context)
        if document_ids:
            native_urls=await evidence_urls(session,project_id=scope.project_id,source_ids=document_ids)
        for ref in native_refs:
            if ref.kind=='profile':
                from ..db.icp import IcpVersion
                from ..services.icp_service import effective_offer_facts
                profile=await session.get(IcpVersion,ref.id)
                selected_facts=[f'fact:profile:{ref.id}:{f["id"]}' for f in effective_offer_facts(profile) if f['approved']]
                if selected_facts:
                    basis=await resolve_sources(session,workspace_id=scope.workspace_id,project_id=scope.project_id,
                        source_ids=selected_facts,readonly=True)
                    if not basis.paid_eligible: raise ValueError('selected profile evidence is not paid eligible')
                    profile_documents.update(uuid.UUID(value) for value in basis.document_ids)
    refs=[ref for ref in refs if ref.kind not in {'provider_evidence','buyer','profile','run'}]
    if refs:
        grounding = await resolve_sources(session,workspace_id=scope.workspace_id,project_id=scope.project_id,
            source_ids=[ref.locator for ref in refs],readonly=True)
        if not grounding.paid_eligible:
            raise ValueError('selected evidence is not paid eligible')
        source_ids = tuple(uuid.UUID(value) for value in grounding.document_ids)
    else:
        source_ids = ()
    source_ids=tuple(sorted(set(source_ids)|profile_documents,key=str))
    policy = await evaluate_current_policy(session,{'workspace_id':scope.workspace_id,'project_id':scope.project_id},
        'account_research',datetime.now(timezone.utc),use_context=research_use(scope.project_id,'research.model',
            binding=item.policy_binding,urls=native_urls).model_copy(update={'source_ids':source_ids}))
    if not policy['allowed']:
        raise ValueError('current sales model policy required')
    return item,market,language


async def prepare(session, scope, row, proposal):
    proposal = ActionProposal.model_validate(proposal.model_dump(mode='json'))
    if any(value for name,value in row.arguments.items()
           if name in {'buyer_id','buyer_ids','profile_id','run_id','list_id','recipient_id','attendee_ids','output_id','document_ids'}):
        from ..sales.research import CORE_SKILLS,validate_intake_authority
        if row.skill_id not in CORE_SKILLS:
            raise ValueError('native source/adapter owner is not registered')
        current=await resolve_context(session,scope,list(durable_refs(row.source_refs)))
        await validate_intake_authority(session,scope,row,current)
    actions.action(proposal.capability)
    skill = load_skill(row.skill_id,row.skill_version)
    validate_action(skill,proposal.capability,proposal.arguments)
    if proposal.arguments.get('refs') or proposal.arguments.get('mutation') or proposal.arguments.get('output'):
        raise ValueError('native adapter/source owner is not registered')
    refs = durable_refs(proposal.source_versions)
    if [ref.model_dump(mode='json') for ref in refs] != row.source_refs:
        raise ValueError('proposal must bind exact selected sources')
    context = await resolve_context(session,scope,list(refs))
    if context.digest != row.context_digest:
        raise ValueError('selected sources changed')
    plan = plan_task(skill,row.arguments,context)
    if plan.missing_inputs or not plan.steps:
        raise ValueError('complete intake required')
    from ..sales.sections import require_supported_identity_kind
    require_supported_identity_kind(skill.output_kind)
    item,market,language = await configuration(session,scope,row)
    fingerprint = digest({'task_id':str(row.id),'intake_hash':intake_hash(row),
        'proposal':proposal.model_dump(mode='json'),'plan':plan.model_dump(mode='json'),
        'registration':item.contract_hash,'market':market,'language':language})
    return context,plan,item,market,language,fingerprint


async def approve_step(session, scope, task_id, proposal, expected_version, key, *, expected_fingerprint=None):
    await lock_authority(session,scope.workspace_id)
    row = await tasks.task_row(session,scope,task_id,edit=True)
    tasks.check_revision(row.revision,expected_version)
    if row.state != 'ready_for_review': raise ValueError('task is not ready for review')
    context,plan,item,market,language,fingerprint = await prepare(session,scope,row,proposal)
    if expected_fingerprint is not None and expected_fingerprint != fingerprint:
        raise ValueError('displayed execution quote changed')
    review_id = uuid.uuid5(scope.actor_id,'sales-review:'+str(task_id)+':'+key)
    existing = (await session.execute(select(SalesReview).where(SalesReview.id==review_id))).scalar_one_or_none()
    if existing is not None:
        validate_review(existing,scope,row,fingerprint,datetime.now(timezone.utc))
        review = existing
    else:
        review = SalesReview(id=review_id,workspace_id=scope.workspace_id,project_id=scope.project_id,
            thread_id=row.thread_id,task_id=row.id,actor_id=scope.actor_id,task_revision=row.revision,
            fingerprint=fingerprint,expires_at=datetime.now(timezone.utc)+timedelta(minutes=15),revoked=False)
        session.add(review)
        await session.flush()
    return ExecutionReview(id=review.id,task_id=row.id,revision=row.revision,fingerprint=fingerprint,
        expires_at=review.expires_at,max_calls=len(plan.steps),max_concurrency=plan.bounds.max_concurrent_steps,
        max_liability_usd=item.capability.max_liability.amount*len(plan.steps))


def receipt(parent, step):
    return StepReceipt(id=step.id,task_id=parent.task_id,dispatch_state=step.state,
        native_operation_id=step.native_operation_id,reservation_ids=(parent.reservation_id,))


def request_for(row, context, item, step_id, section):
    return SalesModelRequest(task_id=row.id,step_id=step_id,skill_id=row.skill_id,skill_version=row.skill_version,
        context=context,model_id=item.model_id,route=item.model_route.route_id,arguments=row.arguments,section=section)


async def admit_step(session, scope, task_id, proposal, review_id, *, expected_version=None):
    from ..services.budget_service import reserve_operation
    await lock_authority(session,scope.workspace_id,budget=True)
    row = await tasks.task_row(session,scope,task_id,edit=True)
    context,plan,item,market,language,fingerprint = await prepare(session,scope,row,proposal)
    parent = (await session.execute(select(SalesExecution).where(SalesExecution.task_id==task_id,
        SalesExecution.workspace_id==scope.workspace_id).with_for_update())).scalar_one_or_none()
    if parent is not None:
        if parent.fingerprint != fingerprint or parent.actor_id != scope.actor_id or parent.review_id != review_id:
            raise ValueError('admitted execution differs; create a separately reviewed follow-on task')
        if expected_version is not None: tasks.check_revision(parent.task_revision,expected_version)
        steps = await children(session,parent)
        return receipt(parent,steps[0])
    if expected_version is not None: tasks.check_revision(row.revision,expected_version)
    if row.state != 'ready_for_review': raise ValueError('task is not ready for execution')
    review = (await session.execute(select(SalesReview).where(SalesReview.id==review_id).with_for_update())).scalar_one_or_none()
    validate_review(review,scope,row,fingerprint,datetime.now(timezone.utc))
    from ..services.xverum_dispatch import require_bounds
    await require_bounds(session,task_id,model_additional=len(plan.steps))
    parent_id = uuid.uuid5(task_id,'sales-execution')
    upper_bound = item.capability.max_liability.amount * len(plan.steps)
    reservation_id = await reserve_operation(session,parent_id,{'workspace_id':scope.workspace_id,
        'project_id':scope.project_id,'category':'assessment'},upper_bound,'USD',item.capability.pricing_version)
    parent = SalesExecution(id=parent_id,workspace_id=scope.workspace_id,project_id=scope.project_id,
        thread_id=row.thread_id,task_id=row.id,actor_id=scope.actor_id,review_id=review.id,
        task_revision=row.revision,intake_revision=row.intake_history[-1]['revision'],
        fingerprint=fingerprint,intake_hash=intake_hash(row),registration_hash=item.contract_hash,
        reservation_id=reservation_id,proposal=proposal.model_dump(mode='json'),plan=plan.model_dump(mode='json'),market=market,language=language,
        max_calls=len(plan.steps),max_concurrency=plan.bounds.max_concurrent_steps,calls_started=0,
        upper_bound=upper_bound,consumed_usd=Decimal(0),cancelled=False,unused_released=False,
        provider_account_hash=digest(item.policy_account_reference))
    session.add(parent)
    await session.flush()
    steps=[]
    for planned in plan.steps:
        step_id = uuid.uuid5(parent.id,planned.section)
        basis = make_basis(request_for(row,context,item,step_id,planned.section),scope,context)
        validate_receipt_basis(basis)
        from ..providers.opencode_model import model_payload
        from ..providers.live_model import canonical_json
        if len(canonical_json(model_payload(basis,item.model_route,item.model_id))) > 6000:
            raise ValueError('child exceeds admitted wire input bound')
        event_id=uuid.uuid5(step_id,'outbox')
        session.add(OutboxEvent(id=event_id,workspace_id=scope.workspace_id,intent_key='sales:'+str(step_id),
            event_type='sales.step',payload={'step_id':str(step_id)},state='ready'))
        await session.flush()
        step=SalesStep(id=step_id,workspace_id=scope.workspace_id,execution_id=parent.id,outbox_id=event_id,
            section=planned.section,state='queued',basis_hash=basis['basis_hash'],projection_hash=digest(wire_basis(basis)),
            liability=item.capability.max_liability.amount)
        session.add(step)
        steps.append(step)
    await set_state(session,row,'queued')
    await session.flush()
    return receipt(parent,steps[0])


async def children(session,parent):
    return (await session.execute(select(SalesStep).where(SalesStep.workspace_id==parent.workspace_id,
        SalesStep.execution_id==parent.id).order_by(SalesStep.section).with_for_update()
        .execution_options(populate_existing=True))).scalars().all()


async def set_state(session,row,state):
    if row.state == 'completed': return  # Task6 canonical completion is terminal.
    state=await provider_task_state(session,row.id,state)
    if row.state != state:
        row.state=state
        row.revision+=1
        await session.flush()
        await tasks.append_event(session,row.id,'state',{'state':state,'revision':row.revision})


async def locked(session,step_id):
    step=(await session.execute(select(SalesStep).where(SalesStep.id==step_id))).scalar_one()
    parent=(await session.execute(select(SalesExecution).where(SalesExecution.id==step.execution_id))).scalar_one()
    # Trusted recovery/finalization may record liability after revocation; never dispatch on this alone.
    from ..db.conversation_threads import ConversationThread
    await session.execute(select(ConversationThread.id).where(ConversationThread.id==parent.thread_id).with_for_update())
    row=(await session.execute(select(SalesTask).where(SalesTask.id==parent.task_id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one()
    parent=(await session.execute(select(SalesExecution).where(SalesExecution.id==parent.id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one()
    steps=await children(session,parent)
    return row,parent,next(child for child in steps if child.id==step_id),steps


async def claim(session,step_id,*,workspace_id):
    await lock_authority(session,workspace_id,budget=True)
    row,parent,step,steps=await locked(session,step_id)
    if step.state!='queued': return receipt(parent,step),None
    if parent.cancelled:
        step.state='cancelled'
        await release_unused_parent(session,parent,steps)
        await set_state(session,row,aggregate_state([s.state for s in steps],cancelled=True))
        return receipt(parent,step),None
    scope=Scope(workspace_id=parent.workspace_id,project_id=parent.project_id,actor_id=parent.actor_id)
    try:
        await tasks.task_row(session,scope,row.id,edit=True)
        if intake_hash(row)!=parent.intake_hash or row.intake_history[-1]['revision']!=parent.intake_revision:
            raise ValueError('admitted intake changed')
        context,plan,item,market,language,fingerprint=await prepare(session,scope,row,ActionProposal.model_validate(parent.proposal))
        review=(await session.execute(select(SalesReview).where(SalesReview.id==parent.review_id))).scalar_one_or_none()
        validate_review(review,scope,SimpleNamespace(id=row.id,revision=parent.task_revision),fingerprint,datetime.now(timezone.utc))
        if plan.model_dump(mode='json')!=parent.plan:
            raise ValueError('admitted section plan changed')
        await require_parent_hold(session,parent,item.capability.pricing_version)
        if (item.contract_hash,market,language,fingerprint)!=(parent.registration_hash,parent.market,parent.language,parent.fingerprint):
            raise ValueError('reviewed registration changed')
        basis=make_basis(request_for(row,context,item,step.id,step.section),scope,context)
        validate_receipt_basis(basis)
        if basis['basis_hash']!=step.basis_hash or digest(wire_basis(basis))!=step.projection_hash:
            raise ValueError('child basis/projection changed')
    except (ValueError,ApiError) as exc:
        step.state='failed'
        if isinstance(exc,ApiError) and exc.code=='SALES_MODEL_UNAVAILABLE':
            for sibling in steps:
                if sibling.state=='queued': sibling.state='failed'
            await tasks.append_event(session,row.id,'error',{'code':'configuration_required','retryable':False})
        await release_unused_parent(session,parent,steps)
        await set_state(session,row,aggregate_state([s.state for s in steps],cancelled=False))
        return receipt(parent,step),None
    active=sum(s.state in {'submitting','unknown'} for s in steps)
    active+=await provider_active(session,row.id)
    if active>=parent.max_concurrency: return receipt(parent,step),None
    debit(parent,active=active,liability=step.liability)
    step.state='submitting'
    step.claim_id=uuid.uuid4()
    step.claimed_at=datetime.now(timezone.utc)
    await set_state(session,row,'running')
    await session.flush()
    return receipt(parent,step),(basis,item,step.claim_id)


async def persist_result(session,step_id,claim_id,basis,result):
    parsed=validate_receipt_basis(basis)
    await lock_authority(session,parsed.scope.workspace_id)
    row,parent,step,steps=await locked(session,step_id)
    if step.claim_id!=claim_id or step.state not in {'submitting','unknown'}:
        return receipt(parent,step)
    parsed=validate_receipt_basis(basis)
    if (parsed.request.task_id!=parent.task_id or parsed.request.step_id!=step.id
        or parsed.request.section!=step.section or parsed.basis_hash!=step.basis_hash
        or digest(wire_basis(basis))!=step.projection_hash):
        raise ValueError('foreign child receipt')
    if result is None:
        step.state='unknown'
    else:
        candidate=SalesSectionCandidate.model_validate(validate_proposal(result['proposal'],basis))
        model_result=SalesModelResult(candidate=candidate,usage=ModelUsage(**{key:result['usage'][key]
            for key in ('input_tokens','output_tokens')},cost=None),provider_ref=result['provider_ref'],
            model_id=result['model_id'],prompt_version=result['prompt_version'])
        if model_result.usage.input_tokens>6000 or model_result.usage.output_tokens>1000:
            raise ValueError('child usage exceeds admitted limits')
        from ..providers.model_receipts import sales_usage_receipt
        step.usage=sales_usage_receipt(model_result,parsed.request)
        step.result_digest=digest(candidate.model_dump(mode='json'))
        step.state='received'
        if actions.SECTION_OWNER is not None and not parent.cancelled:
            # Post-call revocation still permits content-free financial evidence,
            # but never a new retained source body or section output.
            scope=Scope(workspace_id=parent.workspace_id,project_id=parent.project_id,actor_id=parent.actor_id)
            try:
                await tasks.task_row(session,scope,row.id,edit=True)
                current=await resolve_context(session,scope,list(parsed.request.context.refs))
                if current.digest!=parsed.request.context.digest or intake_hash(row)!=parent.intake_hash:
                    raise ValueError('section authority changed')
            except (ValueError,ApiError):
                pass
            else:
                await actions.SECTION_OWNER.save_section(session,scope,parent,step,basis,candidate)
        # Task6 owns assembly/full validation and canonical readback, never this receipt.
    await set_state(session,row,aggregate_state([s.state for s in steps],cancelled=parent.cancelled))
    await session.flush()
    return receipt(parent,step)


async def execute_step(engine,step_id,*,workspace_id,execution=None):
    """The native selector supplies its fenced execution; direct caller cannot dispatch."""
    if execution is None:
        raise ValueError('native runtime claim required')
    async with tenant_session(engine,workspace_id) as session:
        if not await execution.guard(session): raise ValueError('stale native runtime claim')
        await lock_authority(session,workspace_id,budget=True)
        _,_,child,_=await locked(session,step_id)
        if (execution.envelope.workspace_id!=workspace_id or execution.row.id!=child.outbox_id
            or execution.row.event_type!='sales.step' or execution.row.payload!={'step_id':str(step_id)}):
            raise ValueError('native outbox does not own the selected child')
        result,prepared=await claim(session,step_id,workspace_id=workspace_id)
    if prepared is None: return result
    basis,item,claim_id=prepared
    try:
        async with asyncio.timeout(item.model_route.deadline_seconds):
            response=await actions.complete(basis,item)
        async with tenant_session(engine,workspace_id) as session:
            if isinstance(response,actions.DefinitelyUnsubmitted):
                return await persist_unsubmitted(session,step_id,claim_id,workspace_id=workspace_id)
            return await persist_result(session,step_id,claim_id,basis,response)
    except (Exception,asyncio.CancelledError):
        # Includes crash-equivalent invalid/lost response. No response text is retained.
        async with tenant_session(engine,workspace_id) as session:
            result=await persist_result(session,step_id,claim_id,basis,None)
        return result


async def cancel_task(session,scope,task_id,expected_version):
    await lock_authority(session,scope.workspace_id,budget=True)
    row=await tasks.task_row(session,scope,task_id,edit=True)
    tasks.check_revision(row.revision,expected_version)
    if row.state=='completed': return tasks.record(row)
    parent=(await session.execute(select(SalesExecution).where(SalesExecution.task_id==task_id).with_for_update())).scalar_one_or_none()
    if parent is None:
        await set_state(session,row,tasks.cancellation_state(row.state))
    else:
        parent.cancelled=True
        steps=await children(session,parent)
        for step in steps:
            if step.state=='queued': step.state='cancelled'
        await set_state(session,row,aggregate_state([s.state for s in steps],cancelled=True))
        await release_unused_parent(session,parent,steps)
    await cancel_provider_stages(session,scope,row.id)
    return tasks.record(row)


async def recover_outbox(session,outbox):
    step_id=uuid.UUID(outbox.payload['step_id'])
    row,parent,step,steps=await locked(session,step_id)
    step.state=recovery_state(step.state)
    await set_state(session,row,aggregate_state([s.state for s in steps],cancelled=parent.cancelled))
    # Queued is safe to wake; received/unknown/failed/cancelled must never resubmit.
    return step.state!='queued',False,False


async def execute_claimed(engine,execution):
    from ..services.worker_execution import outcome
    async with tenant_session(engine,execution.envelope.workspace_id) as session:
        if not await execution.guard(session): return outcome('stale','STALE_FENCE')
        step_id=uuid.UUID(execution.row.payload['step_id'])
    result=await execute_step(engine,step_id,workspace_id=execution.envelope.workspace_id,execution=execution)
    async with tenant_session(engine,execution.envelope.workspace_id) as session:
        if not await execution.guard(session): return outcome('stale','STALE_FENCE')
        state=('done' if result.dispatch_state in {'received','cancelled'} else
            'reconcile' if result.dispatch_state in {'unknown','submitting'} else
            'waiting' if result.dispatch_state=='queued' else 'blocked')
        # Requeue only unclaimed children; unknown children never return their debit.
        final=outcome('retry_later' if state=='waiting' else state,
            'PROVIDER_UNKNOWN' if state=='reconcile' else 'IN_PROGRESS' if state=='waiting' else 'OK' if state=='done' else 'STEP_FAILED',
            retry_at=datetime.now(timezone.utc)+timedelta(seconds=30) if state=='waiting' else None)
        execution.row.state=('ready' if state=='waiting' else 'failed' if state=='blocked' else 'done')
        execution.row.lease_owner=execution.row.lease_expires_at=None
        execution.finish(final)
        return final


async def list_steps(session,scope,task_id):
    await tasks.task_row(session,scope,task_id)
    parent=(await session.execute(select(SalesExecution).where(SalesExecution.task_id==task_id,
        SalesExecution.workspace_id==scope.workspace_id))).scalar_one_or_none()
    if parent is None: return []
    return [receipt(parent,step) for step in await children(session,parent)]


async def preview_step(session,scope,task_id,proposal):
    from ..sales.contracts import ExecutionPreview
    await lock_authority(session,scope.workspace_id)
    row=await tasks.task_row(session,scope,task_id,edit=True)
    if row.state!='ready_for_review': raise ValueError('task is not ready for review')
    _,plan,item,_,_,fingerprint=await prepare(session,scope,row,proposal)
    return ExecutionPreview(model_id=item.model_id,route=item.model_route.route_id,task_id=row.id,revision=row.revision,fingerprint=fingerprint,
        max_calls=len(plan.steps),max_concurrency=plan.bounds.max_concurrent_steps,
        max_liability_usd=item.capability.max_liability.amount*len(plan.steps))


async def reconcile_step(engine,step_id,*,workspace_id):
    """Trusted recovery interface: read durable truth before any owner status IO.

    No retry/repair/submit interface exists. Unregistered status owners leave unknown.
    """
    async with tenant_session(engine,workspace_id) as session:
        row,parent,step,_=await locked(session,step_id)
        if step.state not in {'unknown','submitting'} or actions.RECONCILER is None:
            return receipt(parent,step)
        claim_id=step.claim_id
        scope=Scope(workspace_id=parent.workspace_id,project_id=parent.project_id,actor_id=parent.actor_id)
        await tasks.task_row(session,scope,row.id,edit=True)
        context=await resolve_context(session,scope,row.source_refs)
        if intake_hash(row)!=parent.intake_hash:
            raise ValueError('reconciliation intake changed')
        # Exact frozen basis is required; the owner cannot fabricate missing content.
        request={'step_id':step.id,'claim_id':claim_id,'native_operation_id':step.native_operation_id,
            'basis_hash':step.basis_hash,'projection_hash':step.projection_hash}
    recovered=await actions.RECONCILER.readback(request)
    if recovered is None:
        async with tenant_session(engine,workspace_id) as session:
            _,parent,step,_=await locked(session,step_id)
            return receipt(parent,step)
    basis,result=recovered
    async with tenant_session(engine,workspace_id) as session:
        return await persist_result(session,step_id,claim_id,basis,result)


def validate_parent_hold(parent,hold,price_version):
    if (getattr(parent,'unused_released',False) or hold is None or hold.state!='active' or (hold.id,hold.workspace_id,hold.operation_id,hold.upper_bound,hold.currency,hold.price_version)
        != (parent.reservation_id,parent.workspace_id,parent.id,parent.upper_bound,'USD',price_version)
        or hold.remaining_hold != parent.upper_bound-getattr(parent,'accounted_bound',Decimal(0))):
        raise ValueError('admitted parent unresolved liability is no longer held')


async def require_parent_hold(session,parent,price_version):
    from ..db.budget import BudgetReservation
    hold=(await session.execute(select(BudgetReservation).where(BudgetReservation.id==parent.reservation_id,
        BudgetReservation.workspace_id==parent.workspace_id).with_for_update(read=True))).scalar_one_or_none()
    validate_parent_hold(parent,hold,price_version)


async def lock_authority(session,workspace_id,*,budget=False):
    from ..services.policy_service import policy_workspace_lock
    await policy_workspace_lock(session,workspace_id)
    from ..services.budget_service import lock_budget_workspace
    await lock_budget_workspace(session,workspace_id)


async def parent_reservation(session,parent):
    from ..db.budget import BudgetReservation
    return (await session.execute(select(BudgetReservation).where(
        BudgetReservation.id==parent.reservation_id,
        BudgetReservation.workspace_id==parent.workspace_id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one()


async def release_unused_parent(session,parent,steps):
    """Caller holds policy/budget then canonical parent/child locks. No partial release."""
    expected={p['section'] for p in parent.plan['steps']}
    if (len(steps)!=parent.max_calls or len(expected)!=len(steps)
        or {s.section for s in steps}!=expected or parent.calls_started!=0 or parent.consumed_usd!=0
        or any(s.state not in {'failed','cancelled'} or
               (s.claim_id is not None and not s.definitely_unsubmitted) or
               s.usage is not None or s.result_digest is not None or s.native_operation_id is not None for s in steps)):
        return False
    hold=await parent_reservation(session,parent)
    if (hold.id,hold.workspace_id,hold.operation_id,hold.upper_bound,hold.currency)!=(
        parent.reservation_id,parent.workspace_id,parent.id,parent.upper_bound,'USD'):
        raise ValueError('unused reservation binding differs')
    if parent.unused_released:
        if hold.state!='released' or hold.remaining_hold!=0: raise ValueError('unused release inconsistent')
        return True
    if hold.state!='active' or hold.remaining_hold!=parent.upper_bound:
        raise ValueError('unused reservation no longer fully held')
    from ..services.settlement import release_unsubmitted_operation
    await release_unsubmitted_operation(session,parent.id)
    parent.unused_released=True
    await session.flush()
    return True


async def persist_unsubmitted(session,step_id,claim_id,*,workspace_id):
    """Only the typed pre-HTTP local failure can supply this durable no-submit proof."""
    await lock_authority(session,workspace_id,budget=True)
    row,parent,step,steps=await locked(session,step_id)
    if step.claim_id!=claim_id or step.state not in {'submitting','unknown'}:
        return receipt(parent,step)
    if step.usage is not None or step.result_digest is not None or step.native_operation_id is not None:
        raise ValueError('no-submit proof conflicts with receipt')
    step.definitely_unsubmitted=True
    step.state='failed'
    parent.calls_started-=1
    parent.consumed_usd-=step.liability
    for sibling in steps:
        if sibling.state=='queued': sibling.state='failed'
    await tasks.append_event(session,row.id,'error',{'code':'configuration_required','retryable':False})
    await release_unused_parent(session,parent,steps)
    await set_state(session,row,aggregate_state([s.state for s in steps],cancelled=parent.cancelled))
    await session.flush()
    return receipt(parent,step)


async def provider_active(session,task_id):
    from ..db.xverum import XverumToolReceipt, XverumStage
    from sqlalchemy import func
    return await session.scalar(select(func.count()).select_from(XverumToolReceipt)
        .join(XverumStage,XverumStage.id==XverumToolReceipt.stage_id)
        .where(XverumStage.task_id==task_id,XverumToolReceipt.state.in_(['submitting','unknown'])))


async def provider_task_state(session,task_id,state):
    from ..services.xverum_dispatch import combined_task_state
    return await combined_task_state(session,task_id,state)


async def cancel_provider_stages(session,scope,task_id):
    from ..services.xverum_dispatch import stage_rows, release_known_unsubmitted, finalize_stage
    from ..db.xverum import XverumStage
    stages=(await session.scalars(select(XverumStage).where(XverumStage.task_id==task_id))).all()
    for stage in stages:
        stage.cancelled=True
        row,reservation,_,_,tools=await stage_rows(session,stage.id)
        if row.dispatch_state in {'settled','cancelled'}:continue
        if not await release_known_unsubmitted(session,row,reservation,tools):
            for tool in tools:
                if tool.state=='queued':tool.state='cancelled'
            await finalize_stage(session,row,reservation,tools)
