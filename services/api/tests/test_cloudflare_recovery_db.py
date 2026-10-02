"""Recovery conservation and honest operational readiness on owned PostgreSQL."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.test_cloudflare_runtime_control_db import worker_runtime, seed_envelope


def recovery_module():
    source = Path(__file__).resolve().parents[1] / 'buyeros_api/services/worker_recovery.py'
    assert source.is_file(), 'CF06 durable recovery and probe receipt missing'
    from buyeros_api.services import worker_recovery
    return worker_recovery


def call_worker(action):
    from buyeros_api.services.worker_execution import create_execution_engine
    async def call():
        engine = create_execution_engine()
        try:
            return await action(engine)
        finally:
            await engine.dispose()
    return asyncio.run(call())


def health(now):
    module = recovery_module()
    async def read(engine):
        async with async_sessionmaker(engine)() as session:
            return await module.read_execution_health(session, now=now)
    return call_worker(read)


def test_environment_flag_cannot_make_readiness_ready(migrated, worker_runtime):
    now = datetime.now(timezone.utc)
    assert health(now)['queue'] == health(now)['worker'] == 'unavailable'
    assert health(now)['alerts'] == ['PROBE_STALE']


def test_probe_epoch_freshness_duplicate_and_pause_fail_closed(migrated, worker_runtime):
    module = recovery_module()
    from buyeros_api.services.worker_execution import maintenance
    now, probe = datetime.now(timezone.utc), uuid.uuid4()
    epoch = worker_runtime[1]
    call_worker(lambda engine: maintenance(engine, epoch, probe_id=probe, now=now))
    assert health(now)['queue'] == health(now)['worker'] == 'ready'
    call_worker(lambda engine: maintenance(engine, epoch, probe_id=probe, now=now + timedelta(seconds=179)))
    assert health(now + timedelta(seconds=181))['worker'] == 'stale', 'duplicate receipt must not refresh freshness'
    call_worker(lambda engine: maintenance(engine, epoch - 1, probe_id=uuid.uuid4(), now=now + timedelta(seconds=181)))
    assert health(now + timedelta(seconds=181))['worker'] == 'stale'
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute('UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1 WHERE singleton=1')
    assert health(now)['worker'] == 'unavailable'
    assert module is not None


def test_queue_or_workflow_retention_does_not_reexecute_terminal_step(migrated, worker_runtime):
    module = recovery_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    now = datetime.now(timezone.utc)
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE outbox_events SET state='done',lease_expires_at=%s WHERE id=%s", (now - timedelta(days=15), envelope.outbox_id))
    report = call_worker(lambda engine: module.recover_execution(engine, now=now, limit=10))
    assert report.recovered == 0
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT state,fencing_generation FROM outbox_events WHERE id=%s', (envelope.outbox_id,)).fetchone() == ('done', 1)


def test_expired_local_step_can_resume_only_after_atomic_receipt_fence(migrated, worker_runtime):
    module = recovery_module()
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.worker_execution import claim_execution_step
    envelope = seed_envelope(migrated, worker_runtime[1], event_type='document.parse', payload={})
    now = datetime.now(timezone.utc)
    async def claim(engine):
        async with tenant_session(engine, envelope.workspace_id) as session:
            return await claim_execution_step(session, envelope, 'start', now - timedelta(seconds=121))
    assert call_worker(claim).state == 'claimed'
    report = call_worker(lambda engine: module.recover_execution(engine, now=now, limit=10))
    assert report.recovered == 1
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT state FROM worker_steps WHERE outbox_id=%s', (envelope.outbox_id,)).fetchone()[0] == 'blocked'
        assert db.execute('SELECT state FROM outbox_events WHERE id=%s', (envelope.outbox_id,)).fetchone()[0] == 'ready'
        assert db.execute('SELECT active_owner FROM worker_runtime_control').fetchone()[0] is None


def test_oldest_work_alert_is_durable_and_cross_tenant_reads_remain_closed(migrated, worker_runtime):
    module = recovery_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    now = datetime.now(timezone.utc)
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE outbox_events SET state='ready',created_at=%s WHERE id=%s", (now - timedelta(seconds=301), envelope.outbox_id))
    call_worker(lambda engine: module.recover_execution(engine, now=now, limit=10))
    assert 'WORK_BACKLOG' in health(now)['alerts']
    with psycopg.connect(worker_runtime[0]) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)", (str(uuid.uuid4()),))
        assert db.execute('SELECT count(*) FROM outbox_events').fetchone()[0] == 0


def uncertain_contact(dsn, epoch, *, historical_count=1):
    from tests.test_cloudflare_provider_steps_db import seed_contact
    case = seed_contact(dsn, epoch, count=1)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE provider_operations SET status='submitting' WHERE job_id=%s", (case['job'],))
        # Historical accepted inventory, not fabricated live provider results.
        for _ in range(historical_count - 1):
            operation = uuid.uuid4()
            db.execute("INSERT INTO provider_operations(id,workspace_id,job_id,intent_key,capability,input_hash,status) "
                       "VALUES(%s,%s,%s,%s,'contact',%s,'unknown')",
                       (operation, case['envelope'].workspace_id, case['job'], f'contact:restore:{operation}', 'a' * 64))
    return case


def test_uncertain_inventory_is_bounded_and_all_status_intents_survive(migrated, worker_runtime):
    module = recovery_module()
    case = uncertain_contact(migrated, worker_runtime[1], historical_count=101)
    now = datetime.now(timezone.utc)
    sweep = 0
    for tick in range(101):
        for _ in range(20):
            call_worker(lambda engine: module.recover_execution(engine, now=now + timedelta(seconds=61 * sweep), limit=1))
            sweep += 1
            with psycopg.connect(migrated) as db:
                count = db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='contact.reconcile'",
                                   (case['envelope'].workspace_id,)).fetchone()[0]
            assert count <= tick + 1, 'one bounded child per parent per tick'
            if count == tick + 1:
                break
        with psycopg.connect(migrated) as db:
            count = db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='contact.reconcile'",
                               (case['envelope'].workspace_id,)).fetchone()[0]
            assert count == tick + 1, 'one bounded child per parent; never truncate accepted inventory'
            if tick < 100:
                assert db.execute('SELECT state FROM outbox_events WHERE id=%s', (case['envelope'].outbox_id,)).fetchone()[0] == 'dispatched'
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT state FROM outbox_events WHERE id=%s', (case['envelope'].outbox_id,)).fetchone()[0] == 'done'
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s', (case['job'],)).fetchone() == ('active', Decimal('0.300000'))
        assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s', (case['envelope'].workspace_id,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM provider_operations WHERE job_id=%s AND status IN ('submitting','unknown')", (case['job'],)).fetchone()[0] == 101


def test_malformed_provider_intent_does_not_abort_independent_recovery(migrated, worker_runtime):
    module = recovery_module()
    bad = seed_envelope(migrated, worker_runtime[1], event_type='contact.lookup', payload={'job_id': 'invalid'})
    good = seed_envelope(migrated, worker_runtime[1], event_type='document.parse')
    call_worker(lambda engine: module.recover_execution(engine, now=datetime.now(timezone.utc)))
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT state FROM outbox_events WHERE id=%s', (bad.outbox_id,)).fetchone()[0] == 'failed'
        assert db.execute('SELECT state FROM outbox_events WHERE id=%s', (good.outbox_id,)).fetchone()[0] == 'ready'


def test_configured_periodic_retention_is_bounded_and_idempotent(migrated, worker_runtime, monkeypatch):
    from tests.test_cloudflare_local_steps_db import seed_project
    from buyeros_api.execution.config import get_settings as execution_settings
    module = recovery_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    project, _, _ = seed_project(migrated, envelope.workspace_id)
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE outbox_events SET state='done' WHERE id=%s", (envelope.outbox_id,))
        for _ in range(11):
            source = uuid.uuid4()
            db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,object_key,excerpt,retention_until) "
                       "VALUES(%s,%s,%s,%s,%s,'private_object',%s,'Fictional retained source',now()-interval '1 minute')",
                       (source, envelope.workspace_id, project, f'https://fixture.invalid/{source}', 'a'*64, f'tenants/{envelope.workspace_id}/{source}'))
    monkeypatch.delenv('BUYEROS_RETENTION_POLICY_VERSION', raising=False)
    execution_settings.cache_clear()
    call_worker(lambda engine: module.recover_execution(engine, now=datetime.now(timezone.utc)))
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT count(*) FROM source_documents WHERE workspace_id=%s AND excerpt IS NULL', (envelope.workspace_id,)).fetchone()[0] == 0
    monkeypatch.setenv('BUYEROS_RETENTION_POLICY_VERSION', 'fictional-retention-policy-v1')
    execution_settings.cache_clear()
    call_worker(lambda engine: module.recover_execution(engine, now=datetime.now(timezone.utc)))
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT count(*) FROM source_documents WHERE workspace_id=%s AND excerpt IS NULL', (envelope.workspace_id,)).fetchone()[0] == 10
    for _ in range(2):
        call_worker(lambda engine: module.recover_execution(engine, now=datetime.now(timezone.utc)))
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT count(*) FROM source_documents WHERE workspace_id=%s AND excerpt IS NULL', (envelope.workspace_id,)).fetchone()[0] == 11
        assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='source.delete'", (envelope.workspace_id,)).fetchone()[0] == 11
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='source.expired'", (envelope.workspace_id,)).fetchone()[0] == 11
    execution_settings.cache_clear()


def test_celery_cloudflare_overlap_has_one_owner(migrated, worker_runtime):
    module = recovery_module()
    assert hasattr(module, 'set_execution_runtime'), 'guarded operator runtime change missing'
    epoch = worker_runtime[1]
    before = module.set_execution_runtime(migrated, expected_epoch=epoch, backend='cloudflare', enabled=True, reason='Fictional dry run')
    assert before['epoch'] == epoch and before['applied'] is False
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute('UPDATE worker_runtime_control SET active_owner=%s,active_until=now()+interval \'1 minute\'', (uuid.uuid4(),))
    paused = module.set_execution_runtime(migrated, expected_epoch=epoch, backend='cloudflare', enabled=False, reason='Fictional pause', apply=True)
    assert paused['epoch'] == epoch + 1 and paused['enabled'] is False
    with pytest.raises(ValueError, match='drain'):
        module.set_execution_runtime(migrated, expected_epoch=epoch + 1, backend='celery', enabled=True, reason='Fictional compatibility check', apply=True)
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE worker_runtime_control SET active_until=now()-interval '1 second'")
    switched = module.set_execution_runtime(migrated, expected_epoch=epoch + 1, backend='celery', enabled=True, reason='Fictional compatibility check', apply=True)
    assert switched['epoch'] == epoch + 2 and switched['backend'] == 'celery'
    with pytest.raises(ValueError, match='epoch'):
        module.set_execution_runtime(migrated, expected_epoch=epoch, backend='cloudflare', enabled=True, reason='Fictional stale action', apply=True)
    with psycopg.connect(worker_runtime[0]) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE worker_runtime_control SET enabled=true")
