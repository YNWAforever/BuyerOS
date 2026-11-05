"""Task identity, intake, recovery and reviewed execution entry points."""
import uuid
import json
from datetime import datetime, timezone
from sqlalchemy import func, select
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency, request_fingerprint
from ..db.sales_tasks import SalesTask, SalesTaskEvent, SalesTaskDependency
from ..db.conversation_threads import ConversationThread
from ..sales.contracts import (Scope, TaskInput, TaskRecord, TaskEvent, TaskDetail,
    TaskFollowup, IntakeEntry, TaskCollectionPage, SourceRef)
from ..sales.registry import load_skill, validate_intake
from ..sales.planning import missing_inputs, plan_task
from ..sales.context import empty_context, resolve_context, durable_refs
from .conversation_access import load, not_found

DELETABLE = frozenset({'needs_input', 'ready_for_review', 'completed', 'failed', 'cancelled'})


def cancellation_state(state):
    if state in {'completed','failed','cancelled','outcome_unknown','cancel_requested'}:
        return state
    return 'cancelled' if state in {'needs_input','ready_for_review'} else 'cancel_requested'


def require_deletable(states):
    if any(state not in DELETABLE for state in states):
        raise ApiError(409, 'TASK_ACTIVE', 'cancel active tasks and reconcile uncertain work before deleting this discussion')


def validated_event(task_id, sequence, kind, payload):
    return TaskEvent(task_id=task_id, sequence=sequence, kind=kind, payload=payload)


def record(row):
    return TaskRecord(id=row.id, state=row.state, revision=row.revision,
        context_digest=row.context_digest, output_ids=row.output_ids, pending_review=row.pending_review)


def check_revision(actual, expected):
    if type(expected) is not int or expected < 1:
        raise ApiError(400, 'INVALID_REQUEST', 'a positive native revision is required')
    if actual != expected:
        raise ApiError(409, 'STALE_REVISION', 'discussion or task changed; reload before retrying')


def jsonb_storage_size(value):
    """Conservative UTF-8 size of PostgreSQL jsonb::text, including numeric expansion."""
    if isinstance(value, dict):
        return 2 + sum(jsonb_storage_size(key) + 2 + jsonb_storage_size(item) for key,item in value.items()) + max(0,len(value)-1)*2
    if isinstance(value, (list,tuple)):
        return 2 + sum(jsonb_storage_size(item) for item in value) + max(0,len(value)-1)*2
    if isinstance(value, float):
        from decimal import Decimal
        number = Decimal(str(value))
        if not number.is_finite():
            raise ApiError(422,'INVALID_REQUEST','finite input numbers are required')
        return len(format(number,'f').encode('utf-8'))
    return len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf-8'))


def validate_persisted_input(data):
    from ..sales.model import _nested_refs
    if any(ref.kind == 'drive' or ref.retention_class != 'durable' for ref in _nested_refs(data.arguments)):
        raise ApiError(422, 'SOURCE_UNAVAILABLE', 'restricted source cannot enter durable intake')
    serialized = json.dumps(data.arguments, ensure_ascii=False)
    if '\x00' in data.user_message or '\\u0000' in serialized:
        raise ApiError(422, 'INVALID_REQUEST', 'remove NUL characters from the task request')
    if jsonb_storage_size(data.arguments) > 131072:
        raise ApiError(422, 'INPUT_LIMIT', 'task arguments exceed 128 KiB; reduce the selected input')


def creation_identity(scope, data, key, expected_thread_version):
    native = request_fingerprint('createSalesTask',
        {'project_id':str(scope.project_id), 'thread_id':str(data.thread_id)},
        f'"{expected_thread_version}"', data.model_dump(mode='json'))
    # Native idempotency retains its algorithm prefix; the sales column stores hex.
    algorithm, separator, value = native.partition(':')
    if algorithm != 'sha256' or separator != ':' or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('unsupported native task fingerprint representation')
    return uuid.uuid5(scope.actor_id, key), value


async def task_row(session, scope, task_id, *, edit=False):
    from .xverum_dispatch import gates
    await gates(session,scope.workspace_id)
    row = (await session.execute(select(SalesTask).where(SalesTask.id == task_id,
        SalesTask.workspace_id == scope.workspace_id, SalesTask.project_id == scope.project_id))).scalar_one_or_none()
    if row is None:
        raise not_found()
    # Lock the thread before task, exactly as create/delete/share mutation do.
    await load(session, scope.workspace_id, scope.project_id, row.thread_id, scope.actor_id, edit=edit, lock=True)
    row = (await session.execute(select(SalesTask).where(SalesTask.id == task_id,
        SalesTask.workspace_id == scope.workspace_id, SalesTask.project_id == scope.project_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None:
        raise not_found()
    from .sales_retention import require_current
    await require_current(session,scope.workspace_id,[row.id])
    return row


async def create_task(session, scope: Scope, data: TaskInput, key: str, expected_thread_version: int) -> TaskRecord:
    from .xverum_dispatch import gates
    await gates(session,scope.workspace_id)
    validate_persisted_input(data)
    thread, _ = await load(session, scope.workspace_id, scope.project_id, data.thread_id, scope.actor_id, edit=True, lock=True)
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
        operation_id='createSalesTask', key=key, body=data.model_dump(mode='json'),
        target={'project_id':str(scope.project_id), 'thread_id':str(data.thread_id)}, precondition=f'"{expected_thread_version}"')
    if outcome.replay:
        return await get_task(session, scope, uuid.UUID(outcome.record.resource_id))
    client_id, fingerprint = creation_identity(scope, data, key, expected_thread_version)
    existing = (await session.execute(select(SalesTask).where(SalesTask.workspace_id == scope.workspace_id,
        SalesTask.actor_id == scope.actor_id, SalesTask.client_message_id == client_id))).scalar_one_or_none()
    if existing is not None:
        if existing.intent_fingerprint != fingerprint:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT', 'this message key belongs to a different task request')
        result = await get_task(session, scope, existing.id)
        complete_idempotency(outcome, str(existing.id))
        await session.flush()
        return result
    check_revision(thread.version, expected_thread_version)
    plan, context = await intake_plan(session, scope, data.skill_id, data.skill_version, data.arguments, data.source_refs)
    sequence = (await session.execute(select(func.coalesce(func.max(SalesTask.message_sequence), 0)).where(
        SalesTask.workspace_id == scope.workspace_id, SalesTask.thread_id == thread.id))).scalar_one() + 1
    row = SalesTask(workspace_id=scope.workspace_id, project_id=scope.project_id, thread_id=thread.id,
        owner_user_id=thread.owner_user_id, actor_id=scope.actor_id,
        client_message_id=client_id, intent_fingerprint=fingerprint, message_sequence=sequence,
        skill_id=data.skill_id, skill_version=data.skill_version, user_message=data.user_message,
        arguments=data.arguments, source_refs=[ref.model_dump(mode='json') for ref in context.refs],
        intake_history=[{'id':str(client_id),'revision':1,'user_message':data.user_message,
            'arguments':data.arguments,'source_refs':[ref.model_dump(mode='json') for ref in context.refs]}],
        state='needs_input' if plan.missing_inputs else 'ready_for_review',
        context_digest=context.digest, revision=1, event_sequence=0, output_ids=[])
    session.add(row)
    await session.flush()
    # Source identity only. Never copy locator strings or materialised source bodies.
    refs = {(ref.id, ref.kind, ref.version): ref for ref in data.source_refs}
    for ref in refs.values():
        session.add(SalesTaskDependency(workspace_id=scope.workspace_id, project_id=scope.project_id,
            thread_id=thread.id, task_id=row.id, source_id=ref.id, source_version=ref.version,
            kind=ref.kind, retention_class=ref.retention_class))
    thread.version += 1
    thread.updated_at = datetime.now(timezone.utc)
    await append_event(session, row.id, 'state', {'state':row.state, 'revision':row.revision})
    complete_idempotency(outcome, str(row.id))
    await session.flush()
    return detail(row)


async def get_task(session, scope: Scope, task_id: uuid.UUID) -> TaskRecord:
    row=await task_row(session, scope, task_id)
    if row.skill_id=='sales-contacts' and row.output_ids:
        from .sales_outputs import get_output
        saved=await get_output(session,scope,uuid.UUID(row.output_ids[0]))
        if saved.availability!='available': raise ApiError(409,'STALE_REVISION','contacts output authority changed')
    elif row.source_refs:
        await resolve_context(session,scope,row.source_refs)
    return detail(row)


async def append_event(session, task_id: uuid.UUID, kind: str, payload: dict) -> TaskEvent:
    """Trusted transaction helper, not an HTTP write or authorization bypass.

    Callers must hold current thread authority; workers have no table grants.
    Task row locking serializes allocation; rollback consumes no sequence.
    """
    identity = (await session.execute(select(SalesTask.workspace_id, SalesTask.thread_id).where(SalesTask.id == task_id))).one_or_none()
    if identity is None:
        raise not_found()
    # Match thread -> task ordering even for a trusted internal append.
    await session.execute(select(ConversationThread.id).where(ConversationThread.workspace_id == identity.workspace_id,
        ConversationThread.id == identity.thread_id).with_for_update())
    row = (await session.execute(select(SalesTask).where(SalesTask.id == task_id).with_for_update()
        .execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None:
        raise not_found()
    event = validated_event(task_id, row.event_sequence + 1, kind, payload)
    row.event_sequence = event.sequence
    session.add(SalesTaskEvent(workspace_id=row.workspace_id, project_id=row.project_id,
        thread_id=row.thread_id, task_id=row.id, sequence=event.sequence, kind=kind,
        payload=event.payload.model_dump(mode='json')))
    await session.flush()
    return event


async def read_events(session, scope: Scope, task_id: uuid.UUID, after: int) -> list[TaskEvent]:
    await task_row(session, scope, task_id)
    if type(after) is not int or after < 0:
        raise ApiError(400, 'INVALID_REQUEST', 'after must be a non-negative sequence')
    rows = (await session.execute(select(SalesTaskEvent).where(SalesTaskEvent.workspace_id == scope.workspace_id,
        SalesTaskEvent.project_id == scope.project_id, SalesTaskEvent.task_id == task_id,
        SalesTaskEvent.sequence > after).order_by(SalesTaskEvent.sequence).limit(100))).scalars().all()
    return [validated_event(row.task_id, row.sequence, row.kind, row.payload) for row in rows]


async def cancel_task(session, scope, task_id, key, expected_revision):
    from ..execution.sales_tasks import lock_authority
    await lock_authority(session,scope.workspace_id,budget=True)
    row = await task_row(session, scope, task_id, edit=True)
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
        operation_id='cancelSalesTask', key=key, body={}, target={'project_id':str(scope.project_id),'task_id':str(task_id)},
        precondition=f'"{expected_revision}"')
    if not outcome.replay:
        from ..execution.sales_tasks import cancel_task as cancel_execution
        await cancel_execution(session, scope, task_id, expected_revision)
        complete_idempotency(outcome, str(row.id))
        await session.flush()
    return record(row)


async def ensure_thread_deletable(session, workspace_id, thread_id):
    from ..db.sales_execution import SalesExecution
    admitted=(await session.execute(select(SalesExecution.id).where(SalesExecution.workspace_id==workspace_id,
        SalesExecution.thread_id==thread_id,SalesExecution.unused_released.is_(False)).limit(1))).first()
    if admitted:
        raise ApiError(409,'TASK_ACTIVE','retain admitted execution and liability evidence until reconciliation')
    states = (await session.execute(select(SalesTask.state).where(SalesTask.workspace_id == workspace_id,
        SalesTask.thread_id == thread_id).with_for_update())).scalars().all()
    require_deletable(states)


async def intake_plan(session, scope, skill_id, skill_version, arguments, refs):
    try:
        skill = load_skill(skill_id, skill_version)
        validate_intake(skill, arguments)
        refs = durable_refs(refs)
        context = await resolve_context(session, scope, list(refs)) if refs else empty_context()
        return plan_task(skill, arguments, context), context
    except ValueError as error:
        raise ApiError(422, 'INVALID_REQUEST', 'review supplied inputs and selected sources') from error


def detail(row):
    # Only authored intake and canonical metadata. No materialized evidence/history from other threads.
    history = row.intake_history or [{'id':str(row.client_message_id),'revision':1,
        'user_message':row.user_message,'arguments':row.arguments,'source_refs':row.source_refs}]
    entries = tuple(IntakeEntry.model_validate({key:item[key] for key in IntakeEntry.model_fields if key in item})
        for item in history)
    skill = load_skill(row.skill_id, row.skill_version)
    missing = list(missing_inputs(skill, row.arguments))
    if skill.id in {'sales-outreach','sales-followup','sales-proposal','sales-objections','sales-competitors'} and not row.source_refs:
        missing.append('selected_offer_facts')
    return TaskDetail(**record(row).model_dump(),thread_id=row.thread_id,skill_id=row.skill_id,
        skill_version=row.skill_version,message_sequence=row.message_sequence,intake=entries,
        arguments=row.arguments,source_refs=row.source_refs,missing_inputs=tuple(missing))


async def list_tasks(session, scope, thread_id, offset=0, limit=50):
    # Authorization precedes even counts, with a stable thread lock across the read.
    await load(session, scope.workspace_id, scope.project_id, thread_id, scope.actor_id, lock=True)
    if type(offset) is not int or not 0 <= offset <= 10000 or type(limit) is not int or not 1 <= limit <= 50:
        raise ApiError(400, 'INVALID_REQUEST', 'bounded task page required')
    filters = (SalesTask.workspace_id == scope.workspace_id, SalesTask.project_id == scope.project_id,
               SalesTask.thread_id == thread_id)
    total = (await session.execute(select(func.count()).select_from(SalesTask).where(*filters))).scalar_one()
    rows = (await session.execute(select(SalesTask).where(*filters).order_by(SalesTask.message_sequence,SalesTask.id)
        .offset(offset).limit(limit))).scalars().all()
    items=[]
    from .sales_retention import require_current
    for row in rows:
        try:
            await require_current(session,scope.workspace_id,[row.id])
            if row.source_refs:
                await resolve_context(session,scope,row.source_refs)
        except (ValueError,ApiError):
            continue
        items.append(detail(row))
    return TaskCollectionPage(items=items,total=total,offset=offset,limit=limit)


async def followup_task(session, scope, task_id, data: TaskFollowup, key, expected_revision):
    row = await task_row(session, scope, task_id, edit=True)
    validate_persisted_input(data)
    identity = uuid.uuid5(scope.actor_id, f"followupSalesTask:{task_id}:{key}")
    arguments = {**row.arguments, **data.arguments}
    # A durable replay is readback, not a new merged mutation. New intents must
    # pass storage validation even before begin_idempotency can flush its receipt.
    if not any(entry['id'] == str(identity) for entry in row.intake_history):
        validate_persisted_input(data.model_copy(update={'arguments':arguments}))
    outcome = await begin_idempotency(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        operation_id='followupSalesTask',key=key,body=data.model_dump(mode='json'),
        target={'project_id':str(scope.project_id),'task_id':str(task_id)},precondition=f'"{expected_revision}"')
    if outcome.replay:
        return detail(row)
    fingerprint = request_fingerprint('followupSalesTask',{'project_id':str(scope.project_id),'task_id':str(task_id)},
        f'"{expected_revision}"',data.model_dump(mode='json'))
    for entry in row.intake_history:
        if entry['id'] == str(identity):
            if entry.get('fingerprint') != fingerprint:
                raise ApiError(409,'IDEMPOTENCY_CONFLICT','follow-up key belongs to a different request')
            complete_idempotency(outcome,str(row.id))
            await session.flush()
            return detail(row)
    check_revision(row.revision,expected_revision)
    partial_core=False
    if row.skill_id=='sales-prospect' and row.state=='partially_completed':
        from ..db.sales_execution import SalesExecution
        from ..db.xverum import XverumStage
        parent=await session.scalar(select(SalesExecution.id).where(SalesExecution.task_id==row.id))
        provider=await session.scalar(select(XverumStage.id).where(XverumStage.task_id==row.id).limit(1))
        partial_core=parent is None and provider is None
    if row.state not in {'needs_input','ready_for_review'} and not partial_core:
        raise ApiError(409,'TASK_ACTIVE','this task cannot accept intake changes')
    if len(row.intake_history) >= 33:
        raise ApiError(422,'INPUT_LIMIT','follow-up history is full; start a separate task')
    refs = data.source_refs if data.source_refs is not None else [SourceRef.model_validate(ref) for ref in row.source_refs]
    plan, context = await intake_plan(session,scope,row.skill_id,row.skill_version,arguments,refs)
    entry = {'id':str(identity),'fingerprint':fingerprint,'revision':row.revision+1,
        'user_message':data.user_message,'arguments':data.arguments,
        'source_refs':[ref.model_dump(mode='json') for ref in context.refs]}
    history = [*row.intake_history,entry]
    if jsonb_storage_size(history) > 250000:
        raise ApiError(422,'INPUT_LIMIT','intake history exceeds its bound; start a separate task')
    # Dependencies retain every selected version for lifecycle invalidation; no locators/bodies.
    existing = {(ref['id'],ref['kind'],ref['version']) for item in row.intake_history for ref in item.get('source_refs',[])}
    for ref in context.refs:
        if (str(ref.id),ref.kind,ref.version) not in existing:
            session.add(SalesTaskDependency(workspace_id=scope.workspace_id,project_id=scope.project_id,
                thread_id=row.thread_id,task_id=row.id,source_id=ref.id,source_version=ref.version,
                kind=ref.kind,retention_class=ref.retention_class))
    row.arguments, row.source_refs, row.intake_history = arguments, entry['source_refs'], history
    row.context_digest = context.digest
    row.revision += 1
    row.state = 'needs_input' if plan.missing_inputs else 'ready_for_review'
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await append_event(session,row.id,'state',{'state':row.state,'revision':row.revision})
    complete_idempotency(outcome,str(row.id))
    await session.flush()
    return detail(row)


async def approve_step(session, scope, task_id, proposal, expected_version, key, *, expected_fingerprint):
    from ..execution.sales_tasks import approve_step as approve
    return await approve(session,scope,task_id,proposal,expected_version,key,expected_fingerprint=expected_fingerprint)


async def admit_step(session, scope, task_id, proposal, review_id, *, expected_version=None):
    from ..execution.sales_tasks import admit_step as admit
    return await admit(session,scope,task_id,proposal,review_id,expected_version=expected_version)
