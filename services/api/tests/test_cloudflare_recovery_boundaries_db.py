"""Actual owned process/restore/rollback boundaries; no live provider resources."""
import asyncio
import json
import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.test_cloudflare_runtime_control_db import worker_runtime, seed_envelope
from tests.test_cloudflare_local_steps_db import seed_project
from tests.test_cloudflare_recovery_db import call_worker, uncertain_contact
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _start_container, _docker


def config():
    result = Config(str(ALEMBIC_INI))
    result.set_main_option('script_location', str(SERVICE_ROOT / 'alembic'))
    return result


def test_0035_empty_round_trip_default_off_and_limited_api_privileges(monkeypatch):
    from buyeros_api.settings import get_settings
    name, dsn = _start_container()
    try:
        monkeypatch.setenv('BUYEROS_DATABASE_URL', dsn)
        get_settings.cache_clear()
        command.upgrade(config(), 'head')
        with psycopg.connect(dsn) as db:
            assert db.execute('SELECT backend,enabled,epoch FROM worker_runtime_control').fetchone() == ('celery', False, 1)
            assert db.execute("SELECT has_column_privilege('buyeros_api','worker_runtime_control','backend','SELECT'),has_column_privilege('buyeros_api','worker_runtime_control','active_owner','SELECT'),has_column_privilege('buyeros_api','worker_runtime_control','enabled','UPDATE')").fetchone() == (True, False, False)
        command.downgrade(config(), '0034_worker_execution')
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT to_regclass('worker_runtime_probe')").fetchone()[0] is None
        command.upgrade(config(), 'head')
        with psycopg.connect(dsn) as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0037_bulk_manifests'
    finally:
        get_settings.cache_clear()
        _docker('rm', '-f', name)


def test_populated_rollback_preserves_unknown_holds(migrated, worker_runtime):
    from buyeros_api.services.worker_execution import maintenance
    case = uncertain_contact(migrated, worker_runtime[1])
    call_worker(lambda engine: maintenance(engine, worker_runtime[1], probe_id=uuid.uuid4()))
    with psycopg.connect(migrated) as db:
        before = db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s', (case['job'],)).fetchone()
    with pytest.raises(RuntimeError, match='retained operational recovery/probe evidence'):
        command.downgrade(config(), '0034_worker_execution')
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0037_bulk_manifests'
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s', (case['job'],)).fetchone() == before
        assert db.execute("SELECT status FROM provider_operations WHERE job_id=%s", (case['job'],)).fetchone()[0] == 'submitting'
        assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s', (case['envelope'].workspace_id,)).fetchone()[0] == 0


def test_killed_native_process_resumes_new_generation_once(migrated, worker_runtime):
    from buyeros_api.services.worker_execution import create_execution_engine, execute_step
    from buyeros_api.services.worker_recovery import recover_execution
    from buyeros_api.execution.dispatcher import claim_cycle
    envelope = seed_envelope(migrated, worker_runtime[1])
    project, actor, member = seed_project(migrated, envelope.workspace_id)
    job, company, buyer = [uuid.uuid4() for _ in range(3)]
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) VALUES(%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,'queued',1)",
                   (job, envelope.workspace_id, project, actor, json.dumps({'owner_membership_id': str(member), 'reason': 'Fictional restart proof'})))
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fixture','Fixture')", (company, envelope.workspace_id))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)', (buyer, envelope.workspace_id, project, company))
        db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) VALUES(%s,%s,%s,%s,0,1,'pending')", (uuid.uuid4(), envelope.workspace_id, job, buyer))
        db.execute('UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s', (json.dumps({'job_id': str(job)}), envelope.outbox_id))
    child_source = '''import asyncio,json,os,sys
if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from datetime import datetime,timezone
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.services.worker_execution import create_execution_engine,claim_execution_step
from buyeros_api.db.session import tenant_session
async def run():
 e=create_execution_engine(); job=JobEnvelope.model_validate_json(os.environ['CF_JOB'])
 async with tenant_session(e,job.workspace_id) as s:
  claim=await claim_execution_step(s,job,'start',datetime.now(timezone.utc))
 assert claim.state=='claimed'
 print('COMMITTED_CLAIM',flush=True)
 await asyncio.Event().wait()
asyncio.run(run())'''
    env = {k: v for k, v in os.environ.items() if not k.startswith(('BUYEROS_', 'AUTH0_', 'R2_', 'VERCEL_', 'CLOUDFLARE_'))}
    env.update({'BUYEROS_EXECUTION_DATABASE_URL': worker_runtime[0], 'BUYEROS_CLOUDFLARE_EXECUTION_ENABLED': 'true'})
    env['CF_JOB'] = envelope.model_dump_json()
    child = subprocess.Popen([sys.executable, '-c', child_source], cwd=SERVICE_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf8')
    try:
        with ThreadPoolExecutor(max_workers=1) as reader:
            future = reader.submit(child.stdout.readline)
            try:
                assert future.result(timeout=20).strip() == 'COMMITTED_CLAIM'
            finally:
                child.kill()
                child.wait(timeout=10)
        assert child.returncode != 0
    finally:
        if child.poll() is None:
            child.kill(); child.wait(timeout=10)
        child.stdout.close(); child.stderr.close()
    # Advance lease clocks in the owned fixture instead of waiting 120 seconds.
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE worker_steps SET expires_at=now()-interval '1 second' WHERE outbox_id=%s", (envelope.outbox_id,))
        db.execute("UPDATE outbox_events SET lease_expires_at=now()-interval '1 second' WHERE id=%s", (envelope.outbox_id,))
        db.execute("UPDATE worker_runtime_control SET active_until=now()-interval '1 second'")
    async def resume(engine):
        await recover_execution(engine, now=datetime.now(timezone.utc))
        batch = await claim_cycle(engine, backend='cloudflare', epoch=worker_runtime[1])
        job = next(item for item in batch.items if item.outbox_id == envelope.outbox_id)
        assert job.generation == 2
        assert (await execute_step(engine, envelope, 'start')).state == 'stale'
        assert (await execute_step(engine, job, 'start')).state == 'done'
        assert (await execute_step(engine, job, 'start')).state == 'done'
    call_worker(resume)
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT version,owner_user_id FROM project_buyers WHERE id=%s', (buyer,)).fetchone() == (2, actor)
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='buyer.owner_assigned'", (envelope.workspace_id,)).fetchone()[0] == 1
        assert db.execute('SELECT state FROM outbox_events WHERE id=%s', (envelope.outbox_id,)).fetchone()[0] == 'done'


def test_restore_then_deletion_replay_keeps_reads_closed(monkeypatch, tmp_path):
    # The existing inspected T28 rehearsal owns two isolated Docker clusters,
    # dumps an older backup, replays an external fixture tombstone, checks RLS,
    # spend conservation, and READ_DISABLED before/after replay.
    from tests.test_backup_restore_t28 import test_disposable_restore_replays_older_backup_deletion_journal
    test_disposable_restore_replays_older_backup_deletion_journal(monkeypatch, tmp_path)
