"""Request-local runtime fencing around native provider transactions.

Legacy adapters share the same implementations. An execution context is never
stored in a message and never replaces PostgreSQL authority.
"""
import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

from sqlalchemy import func, select
from buyeros_api.db.contact import ProviderOperation, EnrichmentJob
from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.db.runs import SearchRun
from buyeros_api.db.session import tenant_session
from buyeros_api.db.worker_execution import WorkerStep
from .domain_executor import StaleFenced

active_execution = ContextVar('buyeros_native_execution', default=None)


@contextmanager
def execution_scope(execution):
    token = active_execution.set(execution)
    try:
        yield
    finally:
        active_execution.reset(token)


@asynccontextmanager
async def execution_session(engine, workspace_id):
    execution = active_execution.get()
    async with tenant_session(engine, workspace_id) as session:
        if execution is not None:
            # Contact cancellation locks policy/job before the outbox. Take the
            # same order here before the common control/outbox fence.
            metadata = (await session.execute(select(OutboxEvent.event_type, OutboxEvent.payload).where(
                OutboxEvent.id == execution.envelope.outbox_id))).first()
            if metadata is not None and metadata[0] in {'contact.lookup', 'contact.reconcile'}:
                from buyeros_api.services.policy_service import policy_workspace_lock
                await policy_workspace_lock(session, workspace_id)
                await session.execute(select(EnrichmentJob.id).where(
                    EnrichmentJob.id == uuid.UUID(metadata[1]['job_id'])).with_for_update())
            if uuid.UUID(str(workspace_id)) != execution.envelope.workspace_id or not await execution.guard(session):
                raise StaleFenced('native execution lost runtime fence')
        yield session
        if execution is not None and hasattr(execution, 'finish') and not execution.finished:
            result = await terminal_business_outcome(session, execution.row)
            if result is not None:
                execution.finish(result)


async def terminal_business_outcome(session, row, *, include_running=False):
    from buyeros_api.services.worker_execution import outcome
    terminal = row.state in {'done', 'failed', 'ready'}
    if not terminal and not include_running:
        return None
    payload = row.payload or {}
    unknown = None
    if row.event_type in {'run.discover', 'research.reconcile', 'run.fit'}:
        run_id = uuid.UUID(payload['run_id'])
        run = (await session.execute(select(SearchRun).where(SearchRun.id == run_id))).scalar_one_or_none()
        unknown = (await session.execute(select(ProviderOperation.id).where(
            ProviderOperation.intent_key.like(f'research:{run_id}:%'),
            ProviderOperation.status.in_({'submitting', 'unknown', 'accepted', 'pending'})).limit(1))).first()
        if unknown is None and run is not None and run.terminal_reason:
            reason = run.terminal_reason
            if reason in {'run_limit_reached', 'provider_result_exceeded_limits', 'decoded_page_bytes_exceeded_limit'}:
                return outcome('blocked', 'LIMIT_EXCEEDED')
            if reason in {'actor_revoked', 'invalid_actor', 'fit actor is absent', 'fit actor was revoked'}:
                return outcome('blocked', 'ACTOR_CHANGED')
            if (reason in {'stale_profile', 'policy_blocked', 'policy_or_context_changed_during_search'}
                    or reason.startswith(('fit profile ', 'fit policy ', 'fit basis '))):
                return outcome('blocked', 'POLICY_CHANGED')
            if run.status in {'partial', 'failed'}:
                return outcome('blocked', 'STEP_FAILED')
    elif row.event_type in {'provider.external', 'provider.reconcile', 'contact.lookup', 'contact.reconcile'}:
        query = select(ProviderOperation.id).where(ProviderOperation.status.in_({'submitting', 'unknown', 'accepted', 'pending'}))
        query = (query.where(ProviderOperation.job_id == uuid.UUID(payload['job_id']))
                 if row.event_type.startswith('contact.') else query.where(ProviderOperation.id == uuid.UUID(payload['operation_id'])))
        unknown = (await session.execute(query.limit(1))).first()
    if unknown is not None:
        return outcome('reconcile', 'PROVIDER_UNKNOWN')
    if not terminal:
        return None
    return outcome('done', 'OK') if row.state == 'done' else outcome('blocked', 'STEP_FAILED')


async def finish_continuation(session):
    execution = active_execution.get()
    if execution is None or not hasattr(execution, 'finish'):
        return
    from buyeros_api.services.worker_execution import outcome
    number = (await session.execute(select(func.count()).select_from(WorkerStep).where(
        WorkerStep.outbox_id == execution.envelope.outbox_id))).scalar_one()
    result = (outcome('blocked', 'LIMIT_EXCEEDED') if number >= 512 else
              outcome('continue', 'OK', step_key=f'step:{number}'))
    execution.finish(result)


async def finish_contact_unit(session, job_id, state):
    execution = active_execution.get()
    if execution is None or not hasattr(execution, 'finish'):
        return
    from buyeros_api.services.worker_execution import outcome
    pending = (await session.execute(select(ProviderOperation.id).where(
        ProviderOperation.job_id == job_id, ProviderOperation.status.in_({'intent', 'reserved'})).limit(1))).first()
    if pending is not None and state == 'accepted':
        await finish_continuation(session)
    else:
        if pending is None:
            execution.row.state = 'done'
            execution.row.lease_owner = execution.row.lease_expires_at = None
        execution.finish(outcome('reconcile', 'PROVIDER_UNKNOWN'))


class LegacyExecution:
    """Legacy transport fence rechecked in every prepare/finalize transaction."""
    def __init__(self, envelope):
        self.envelope = envelope

    async def guard(self, session):
        from buyeros_api.services.worker_execution import legacy_runtime_control
        control = await legacy_runtime_control(session)
        if control is None or control.epoch != self.envelope.runtime_epoch:
            return False
        row = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.id == self.envelope.outbox_id).with_for_update())).scalar_one_or_none()
        return (row is not None and row.runtime_backend == 'celery'
                and row.runtime_epoch == control.epoch and row.fencing_generation == self.envelope.generation)
