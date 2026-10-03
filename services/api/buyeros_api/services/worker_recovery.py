"""Bounded database-only recovery. Never submit, settle or release an operation."""
import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic

from sqlalchemy import String, cast, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from buyeros_api.db.contact import ProviderOperation
from buyeros_api.db.outbox import OutboxEvent, TERMINAL_STATES
from buyeros_api.db.worker_execution import WorkerRuntimeControl, WorkerRuntimeProbe, WorkerStep
from buyeros_api.settings import get_settings

UNCERTAIN = {'submitting', 'unknown', 'accepted', 'pending'}


@dataclass(frozen=True)
class RecoveryReport:
    recovered: int
    oldest_work_at: datetime | None


async def read_execution_health(session, *, now: datetime) -> dict:
    # Ordinary API role receives only these selector columns, no activation or
    # global execution-slot privileges. Staff membership is checked by the route.
    control = (await session.execute(select(WorkerRuntimeControl.backend,
        WorkerRuntimeControl.enabled, WorkerRuntimeControl.epoch))).one()
    probe = (await session.execute(select(WorkerRuntimeProbe))).scalar_one()
    worker, queue = 'unavailable', 'unavailable'
    selected = control.enabled and control.backend == 'cloudflare' and get_settings().cloudflare_execution_enabled
    if selected and probe.runtime_epoch == control.epoch and probe.last_probe_at is not None:
        age = (now - probe.last_probe_at).total_seconds()
        if 0 <= age <= 180:
            worker = queue = 'ready'
        else:
            worker = 'stale'
    alerts = [] if worker == 'ready' else ['PROBE_STALE']
    if (probe.metrics_epoch == control.epoch and probe.oldest_work_at is not None
            and (now - probe.oldest_work_at).total_seconds() > 300):
        alerts.append('WORK_BACKLOG')
    return {'worker': worker, 'queue': queue, 'alerts': alerts}


async def _schedule_uncertain(session, row):
    """Reuse permanent provider keys and the existing status-only intent shape."""
    payload = row.payload or {}
    query = select(ProviderOperation).where(ProviderOperation.status.in_(UNCERTAIN))
    try:
        if row.event_type in {'contact.lookup', 'contact.reconcile'}:
            query = query.where(ProviderOperation.job_id == uuid.UUID(payload['job_id']))
            prefix, event_type = 'contact.reconcile:', 'contact.reconcile'
        elif row.event_type in {'run.discover', 'research.reconcile', 'run.fit'}:
            query = query.where(ProviderOperation.intent_key.like(f"research:{uuid.UUID(payload['run_id'])}:%"))
            prefix, event_type = 'research:reconcile:', 'research.reconcile'
        elif row.event_type in {'provider.external', 'provider.reconcile'}:
            query = query.where(ProviderOperation.id == uuid.UUID(payload['operation_id']))
            prefix, event_type = 'provider.reconcile:', 'provider.reconcile'
        else:
            return False, False, False
    except (KeyError, ValueError, TypeError, AttributeError):
        return False, False, True  # retain opaque intent, no guessed provider identity
    uncertain = (await session.execute(query.limit(1))).first() is not None
    missing = ~exists(select(OutboxEvent.id).where(
        OutboxEvent.workspace_id == row.workspace_id, OutboxEvent.event_type == event_type,
        OutboxEvent.intent_key == prefix + cast(ProviderOperation.id, String)))
    # At most one new child per recovered parent; inspect the second ID only to
    # keep the parent fenced for the next sweep. Never truncate accepted truth.
    operations = (await session.execute(query.where(missing).order_by(ProviderOperation.id).limit(2))).scalars().all()
    for operation in operations[:1]:
        if row.event_type.startswith('contact.'):
            key, event_type = f'contact.reconcile:{operation.id}', 'contact.reconcile'
            body = {'workspace_id': str(row.workspace_id), 'job_id': str(operation.job_id), 'operation_id': str(operation.id)}
        elif row.event_type in {'run.discover', 'research.reconcile', 'run.fit'}:
            prefix, run_id, query_id = operation.intent_key.split(':', 2)
            if prefix != 'research' or run_id != str(uuid.UUID(payload['run_id'])):
                return True, False, True
            key, event_type = f'research:reconcile:{operation.id}', 'research.reconcile'
            body = {'run_id': run_id, 'operation_id': str(operation.id), 'query_id': query_id}
        else:
            from buyeros_api.execution.provider_dispatch import _provider_command
            command = _provider_command(row.intent_key, row.event_type, payload)
            if command is None:
                return True, False, True
            from buyeros_api.execution.external_runner import _queue_reconciliation
            await _queue_reconciliation(session, row, operation.id, command[1])
            continue
        existing = (await session.execute(select(OutboxEvent.id).where(
            OutboxEvent.intent_key == key, OutboxEvent.event_type == event_type))).first()
        if existing is None:
            session.add(OutboxEvent(workspace_id=row.workspace_id, intent_key=key, event_type=event_type, payload=body))
    return uncertain, len(operations) > 1, False


async def _expire_retention(session, *, now, limit):
    """Configured policy only; bounded tenant tombstones, no object-store I/O."""
    from buyeros_api.execution.config import get_settings as execution_settings
    from buyeros_api.db.buyers import SourceDocument
    from buyeros_api.db.runs import ContactPoint
    from buyeros_api.services.retention import expire_subject_data
    policy = execution_settings().retention_policy_version
    if not policy or not 1 <= len(policy) <= 64 or limit <= 0:
        return 0
    sources = (await session.execute(select(SourceDocument.id).where(
        SourceDocument.retention_until <= now,
        or_(SourceDocument.excerpt.is_not(None), ~SourceDocument.canonical_url.like('https://redacted.invalid/%')))
        .order_by(SourceDocument.retention_until, SourceDocument.id).limit(limit).with_for_update(skip_locked=True))).scalars().all()
    for source in sources:
        await expire_subject_data(session, source, policy, now, subject_type='source_document')
    contacts = (await session.execute(select(ContactPoint.id).where(ContactPoint.retention_expires_at <= now,
        ~ContactPoint.normalized_value.like('expired+%@redacted.invalid'))
        .order_by(ContactPoint.retention_expires_at, ContactPoint.id).limit(limit - len(sources))
        .with_for_update(skip_locked=True))).scalars().all()
    for contact in contacts:
        await expire_subject_data(session, contact, policy, now, subject_type='contact_point')
    return len(sources) + len(contacts)


async def recover_execution(engine, *, now: datetime, limit: int = 10, runtime_epoch: int | None = None) -> RecoveryReport:
    from .worker_execution import control_row, outcome
    if type(limit) is not int or not 1 <= limit <= 10 or now.utcoffset() is None:
        raise ValueError('recovery requires bounded count and aware time')
    async def recover():
        async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
            control = await control_row(session, lock=True)
            probe = (await session.execute(select(WorkerRuntimeProbe).with_for_update())).scalar_one()
            if (not control.enabled or control.backend != 'cloudflare' or not get_settings().cloudflare_execution_enabled
                    or (runtime_epoch is not None and runtime_epoch != control.epoch)):
                return RecoveryReport(0, probe.oldest_work_at)
            await session.execute(text("SELECT set_config('statement_timeout','10000',true)"))
            if probe.metrics_epoch != control.epoch:
                probe.metrics_epoch, probe.scan_oldest_at, probe.oldest_work_at = control.epoch, None, None
                control.recovery_cursor = None
            workspace_query = text('SELECT id FROM workspaces WHERE (CAST(:cursor AS uuid) IS NULL OR id>CAST(:cursor AS uuid)) ORDER BY id LIMIT 1000')
            workspaces = (await session.execute(workspace_query, {'cursor': control.recovery_cursor})).scalars().all()
            if not workspaces:
                control.recovery_cursor = None
                workspaces = (await session.execute(workspace_query, {'cursor': None})).scalars().all()
            recovered, started, finished_scan = 0, monotonic(), True
            for workspace in workspaces:
                if recovered >= limit or monotonic() - started >= 9:
                    finished_scan = False
                    break
                await session.execute(text("SELECT set_config('app.workspace_id',:ws,true)"), {'ws': str(workspace)})
                oldest = (await session.execute(select(func.min(OutboxEvent.created_at)).where(OutboxEvent.state.in_({'ready', 'dispatched'})))).scalar_one()
                if oldest is not None and (probe.scan_oldest_at is None or oldest < probe.scan_oldest_at):
                    probe.scan_oldest_at = oldest
                rows = (await session.execute(select(OutboxEvent).where(OutboxEvent.state == 'dispatched',
                    or_(OutboxEvent.lease_expires_at <= now, OutboxEvent.lease_expires_at.is_(None)))
                    .order_by(OutboxEvent.created_at).limit(limit - recovered).with_for_update(skip_locked=True))).scalars().all()
                for row in rows:
                    receipts = (await session.execute(select(WorkerStep).where(WorkerStep.outbox_id == row.id,
                        WorkerStep.state.in_({'running', 'reconcile'})).order_by(WorkerStep.created_at).limit(512))).scalars().all()
                    if any(receipt.state == 'running' and receipt.expires_at > now for receipt in receipts):
                        continue
                    uncertain, more, invalid = await _schedule_uncertain(session, row)
                    for receipt in receipts:
                        result = outcome('reconcile', 'PROVIDER_UNKNOWN') if uncertain else outcome('blocked', 'STEP_FAILED')
                        # Parent submit remains permanently non-claimable. A status-only
                        # child may poll again in a newer generation, with the same hold.
                        receipt.state = ('reconcile' if uncertain and not row.event_type.endswith('.reconcile') else 'blocked')
                        receipt.outcome = result.model_dump(mode='json')
                        if control.active_owner == receipt.owner:
                            control.active_owner = control.active_until = None
                    if row.state not in TERMINAL_STATES:
                        row.state = ('failed' if invalid else 'dispatched' if more else
                                     'done' if uncertain and not row.event_type.endswith('.reconcile') else 'ready')
                    row.lease_owner = row.lease_expires_at = None
                    if more:
                        row.lease_expires_at = now + timedelta(seconds=60)
                    row.runtime_backend, row.runtime_epoch = control.backend, control.epoch
                    recovered += 1
                recovered += await _expire_retention(session, now=now, limit=limit - recovered)
                control.recovery_cursor = workspace
                # Flush tenant writes BEFORE changing SET LOCAL. Otherwise ORM
                # autoflush under the next tenant is rejected by forced RLS.
                await session.flush()
            if finished_scan:
                later = (await session.execute(text('SELECT 1 FROM workspaces WHERE id>CAST(:cursor AS uuid) LIMIT 1'),
                    {'cursor': control.recovery_cursor})).first() if control.recovery_cursor is not None else None
                if later is None:
                    probe.oldest_work_at, probe.scan_oldest_at = probe.scan_oldest_at, None
                    control.recovery_cursor = None
            if control.active_until is not None and control.active_until <= now:
                control.active_owner = control.active_until = None
            return RecoveryReport(recovered, probe.oldest_work_at)
    try:
        return await asyncio.wait_for(recover(), timeout=10)
    except TimeoutError:
        return RecoveryReport(0, None)  # transaction rolls back; no partial claim


async def record_probe(engine, *, runtime_epoch: int, probe_id: uuid.UUID, now: datetime) -> bool:
    from .worker_execution import control_row
    async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
        control = await control_row(session, lock=True)
        if not control.enabled or control.backend != 'cloudflare' or control.epoch != runtime_epoch or not get_settings().cloudflare_execution_enabled:
            return False
        probe = (await session.execute(select(WorkerRuntimeProbe).with_for_update())).scalar_one()
        if probe.last_probe_id != probe_id or probe.runtime_epoch != runtime_epoch:
            probe.runtime_epoch, probe.last_probe_id, probe.last_probe_at = runtime_epoch, probe_id, now
        return True


def set_execution_runtime(dsn: str, *, expected_epoch: int, backend: str, enabled: bool,
                          reason: str, apply: bool = False) -> dict:
    """Operator-only compare-and-swap. Dry run by default; no cloud activation."""
    import psycopg
    if (type(expected_epoch) is not int or not 1 <= expected_epoch < 9007199254740991
            or backend not in {'celery', 'cloudflare'} or type(enabled) is not bool
            or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 200):
        raise ValueError('invalid runtime change')
    with psycopg.connect(dsn) as db:
        if db.execute('SELECT version_num FROM alembic_version').fetchone()[0] not in {
                '0035_worker_recovery_probe', '0036_checkpoint_schema_grants', '0037_bulk_manifests'}:
            raise ValueError('compatible 0035/0036/0037 build and migration required')
        current = db.execute('SELECT backend,enabled,epoch,active_until FROM worker_runtime_control WHERE singleton=1 FOR UPDATE').fetchone()
        if current[2] != expected_epoch:
            raise ValueError('runtime epoch changed; inspect current state')
        if enabled:
            running = db.execute("SELECT EXISTS(SELECT 1 FROM outbox_events WHERE state='dispatched' AND lease_expires_at>now())").fetchone()[0]
            active = db.execute('SELECT active_until>now() FROM worker_runtime_control').fetchone()[0]
            if running or active:
                raise ValueError('pause and drain active leases before enabling either runtime')
        result = {'backend': backend, 'enabled': enabled, 'epoch': expected_epoch + 1 if apply else expected_epoch,
                  'applied': apply, 'reason': reason.strip()}
        if apply:
            db.execute('UPDATE worker_runtime_control SET backend=%s,enabled=%s,epoch=epoch+1,cursor=NULL,recovery_cursor=NULL WHERE singleton=1', (backend, enabled))
        return result
