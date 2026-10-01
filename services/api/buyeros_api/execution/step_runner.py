"""One bounded native unit. All instructions and authority come from PostgreSQL."""
from dataclasses import dataclass
from datetime import datetime, timezone

from buyeros_api.api.worker_schemas import JobEnvelope, StepOutcome
from buyeros_api.db.session import tenant_session

LOCAL_EVENTS = frozenset({'bulk.mutate', 'draft.generate', 'fetch.evidence',
                         'offer.parse', 'offer.delete', 'offer.fetch', 'source.delete'})


@dataclass
class LocalExecution:
    envelope: JobEnvelope
    step_key: str
    owner: object
    finished: bool = False

    async def guard(self, session):
        from buyeros_api.services.worker_execution import _owned_step
        from buyeros_api.settings import get_settings
        control, row, receipt, valid = await _owned_step(session, self.envelope, self.step_key, self.owner)
        self.control, self.row, self.receipt = control, row, receipt
        return (valid and control.enabled and get_settings().cloudflare_execution_enabled
                and receipt.expires_at > datetime.now(timezone.utc))

    def finish(self, result: StepOutcome):
        from buyeros_api.services.worker_execution import finish_receipt
        finish_receipt(self.control, self.receipt, result)
        self.finished = True

    def finish_done(self):
        from buyeros_api.services.worker_execution import outcome
        self.finish(outcome('done', 'OK'))


async def execute_local_step(engine, envelope: JobEnvelope, step_key: str,
                             *, deadline: datetime) -> StepOutcome:
    from buyeros_api.services.worker_execution import execute_step, outcome
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        return outcome('blocked', 'LIMIT_EXCEEDED')
    return await execute_step(engine, envelope, step_key, timeout_seconds=min(60, remaining))


async def execute_claimed(engine, envelope, step_key, owner):
    from buyeros_api.services.worker_execution import outcome
    from .domain_executor import run_intent
    execution = LocalExecution(envelope, step_key, owner)
    async with tenant_session(engine, envelope.workspace_id) as session:
        if not await execution.guard(session):
            return outcome('stale', 'STALE_FENCE')
        row = execution.row
        event_type, intent_key = row.event_type, row.intent_key
        if event_type not in LOCAL_EVENTS:
            # CF04 supplies bounded provider execution. Unsupported capabilities
            # must not manufacture rows or mark an external operation successful.
            result = outcome('blocked', 'CAPABILITY_UNAVAILABLE')
            execution.finish(result)
            return result
        if event_type in {'bulk.mutate', 'draft.generate', 'fetch.evidence'}:
            state = await run_intent(session, {'workspace_id': str(envelope.workspace_id)},
                                     intent_key, envelope.generation)
            result = outcome('done', 'OK') if state in {'done', 'duplicate'} else outcome('blocked', 'INVALID_INTENT')
            execution.finish(result)
            return result

    # Each native runner checks the same owner/epoch before prepare/finalize.
    # No transaction, permit row lock or customer lock spans object/network IO.
    if event_type in {'offer.parse', 'offer.delete'}:
        from .document_runner import execute_document
        state = await execute_document(engine, envelope.workspace_id, intent_key,
                                       envelope.generation, execution=execution)
    elif event_type == 'offer.fetch':
        from .fetch_runner import execute_offer_fetch
        state = await execute_offer_fetch(engine, envelope.workspace_id, intent_key,
                                          envelope.generation, execution=execution)
    else:
        from .handlers.retention import execute_source_delete
        state = await execute_source_delete(engine, envelope.workspace_id, intent_key,
                                            envelope.generation, execution=execution)
    if execution.finished:
        return outcome('done', 'OK')
    async with tenant_session(engine, envelope.workspace_id) as session:
        if not await execution.guard(session):
            return outcome('stale', 'STALE_FENCE')
        code = ('ACTOR_CHANGED' if state == 'actor_changed' else
                'POLICY_CHANGED' if state in {'policy_blocked', 'stale'} else
                'CAPABILITY_UNAVAILABLE' if state.endswith('_unavailable') else 'INVALID_INTENT')
        result = outcome('blocked', code)
        execution.finish(result)
        return result
