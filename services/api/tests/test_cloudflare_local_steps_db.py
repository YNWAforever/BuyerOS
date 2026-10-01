"""Bounded native units against owned PostgreSQL; R2 substitutions are fixtures."""
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO

import psycopg
import pytest
from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.test_cloudflare_runtime_control_db import worker_runtime, seed_envelope


def local_module():
    from buyeros_api.execution import step_runner
    return step_runner


def seed_project(dsn, workspace):
    project, actor, member = (uuid.uuid4() for _ in range(3))
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
                   "VALUES(%s,%s,'Fictional CF03','Fixture','Sensor','{HK}','{en}',1)", (project, workspace))
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'https://fixture.invalid/',%s)", (actor, f"cf03|{actor}"))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES(%s,%s,%s,'{workspace_admin}',true)",
                   (member, workspace, actor))
    return project, actor, member


def run_local(envelope, key='start'):
    module = local_module()
    from buyeros_api.services.worker_execution import create_execution_engine
    async def run():
        engine = create_execution_engine()
        try:
            return await module.execute_local_step(engine, envelope, key,
                deadline=datetime.now(timezone.utc) + timedelta(seconds=60))
        finally:
            await engine.dispose()
    return asyncio.run(run())


@pytest.mark.parametrize('count', [101, 1000])
def test_bulk_restart_resumes_next_chunk_without_repeat(migrated, worker_runtime, count):
    local_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    project, actor, member = seed_project(migrated, envelope.workspace_id)
    job = uuid.uuid4()
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) "
                   "VALUES(%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,'queued',%s)",
                   (job, envelope.workspace_id, project, actor, json.dumps({'owner_membership_id': str(member), 'reason': 'Fictional bounded batch'}), count))
        for index in range(count):
            company, buyer = uuid.uuid4(), uuid.uuid4()
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fixture','Fixture')", (company, envelope.workspace_id))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)", (buyer, envelope.workspace_id, project, company))
            db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) VALUES(%s,%s,%s,%s,%s,%s,'pending')",
                       (uuid.uuid4(), envelope.workspace_id, job, buyer, index, 99 if index == 1 else 1))
        db.execute("UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s", (json.dumps({'job_id': str(job)}), envelope.outbox_id))
    assert run_local(envelope).state == 'done'
    assert run_local(envelope).state == 'done', 'process restart must read the committed receipt'
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT processed,updated,conflicts FROM async_jobs WHERE id=%s", (job,)).fetchone() == (50, 49, 1)
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone()[0] == 1
    while True:
        with psycopg.connect(migrated, autocommit=True) as db:
            successor = db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND state='ready' ORDER BY created_at LIMIT 1", (envelope.workspace_id,)).fetchone()
            if successor is None:
                break
            db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend='cloudflare',runtime_epoch=%s WHERE id=%s", (envelope.runtime_epoch, successor[0]))
        next_envelope = envelope.model_copy(update={'outbox_id': successor[0]})
        assert run_local(next_envelope).state == 'done'
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT status,processed,updated,conflicts FROM async_jobs WHERE id=%s", (job,)).fetchone() == ('completed', count, count-1, 1)
        assert db.execute("SELECT count(*) FROM project_buyers WHERE workspace_id=%s AND version=2", (envelope.workspace_id,)).fetchone()[0] == count-1
        assert db.execute("SELECT count(*) FROM audit_events WHERE workspace_id=%s AND action='buyer.owner_assigned'", (envelope.workspace_id,)).fetchone()[0] == count-1


def test_pdf_child_keeps_sanitized_env_and_eight_second_timeout(monkeypatch, tmp_path):
    from importlib.metadata import distribution
    import os
    from pathlib import Path
    import sys
    from buyeros_api.execution import pdf_parser
    from buyeros_api.services.ingestion_service import validate_upload
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    output = BytesIO()
    writer.write(output)
    body = output.getvalue()
    upload = validate_upload('fixture.pdf', 'application/pdf', body, hashlib.sha256(body).hexdigest())
    # Independently enumerate only our code and installed package metadata.
    # A hosted parent has vendor packages absent from a fresh interpreter.
    expected_roots = [Path(pdf_parser.__file__).resolve().parents[2]]
    for package in ('psycopg', 'sqlalchemy', 'pypdf', 'langgraph', 'langgraph-checkpoint-postgres'):
        root = Path(distribution(package).locate_file('')).resolve()
        if root not in expected_roots:
            expected_roots.append(root)
    expected_env = {'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1',
                    'PYTHONPATH': os.pathsep.join(str(root) for root in expected_roots)}
    if sys.platform == 'win32':
        expected_env['SystemRoot'] = os.environ.get('SystemRoot', r'C:\Windows')
    malicious = tmp_path / 'untrusted-pythonpath'
    malicious.mkdir()
    (malicious / 'pypdf.py').write_text("raise RuntimeError('untrusted inherited package')\n")
    original = pdf_parser.subprocess.run
    def observe(command, **kwargs):
        assert command[-1] == 'buyeros_api.execution.pdf_parser_child'
        assert kwargs['timeout'] == 8
        assert 'BUYEROS_WORKER_CURRENT_SECRET' not in kwargs['env']
        assert kwargs['env'] == expected_env
        assert str(malicious) not in kwargs['env']['PYTHONPATH']
        assert 'fixture-secret-must-not-be-inherited' not in kwargs['env'].values()
        assert 'buyeros-pdf-' in kwargs['cwd']
        return original(command, **kwargs)
    monkeypatch.setenv('BUYEROS_WORKER_CURRENT_SECRET', 'fixture-secret-must-not-be-inherited')
    monkeypatch.setenv('PYTHONPATH', str(malicious))
    monkeypatch.setattr(pdf_parser.subprocess, 'run', observe)
    assert pdf_parser.parse_pdf_candidates(upload) == []
    def timeout(*args, **kwargs):
        raise pdf_parser.subprocess.TimeoutExpired('fixture-parser', 8)
    monkeypatch.setattr(pdf_parser.subprocess, 'run', timeout)
    with pytest.raises(pdf_parser.PdfParserTimeout):
        pdf_parser.parse_pdf_candidates(upload)


def document_case(dsn, epoch):
    envelope = seed_envelope(dsn, epoch, event_type='offer.parse')
    project, actor, member = seed_project(dsn, envelope.workspace_id)
    document = uuid.uuid4()
    body = b'Product: Fictional sensor\n'
    key = f'tenants/{envelope.workspace_id}/{uuid.uuid4()}'
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO offer_documents(id,workspace_id,project_id,kind,filename,media_type,sha256,status,version,object_key) "
                   "VALUES(%s,%s,%s,'upload','fixture.txt','text/plain',%s,'quarantined',1,%s)",
                   (document, envelope.workspace_id, project, hashlib.sha256(body).hexdigest(), key))
        db.execute("UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s", (json.dumps({'document_id': str(document), 'actor_user_id': str(actor)}), envelope.outbox_id))
    return envelope, document, actor, key, body


def test_document_delete_during_parse_blocks_exposure(migrated, worker_runtime, monkeypatch):
    local_module()
    from buyeros_api.execution import document_runner
    envelope, document, actor, key, body = document_case(migrated, worker_runtime[1])
    class Store:
        calls = 0
        async def get_private(self, object_key):
            self.calls += 1
            assert object_key == key
            with psycopg.connect(migrated, autocommit=True) as db:
                db.execute("SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT", (envelope.outbox_id,))
                db.execute("UPDATE offer_documents SET status='deleted',fact_candidates='[]'::jsonb,version=version+1 WHERE id=%s", (document,))
            return body
    store = Store()
    monkeypatch.setattr(document_runner, 'get_private_store', lambda ws: store)
    assert run_local(envelope).state == 'done'
    assert run_local(envelope).state == 'done'
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT status,fact_candidates FROM offer_documents WHERE id=%s", (document,)).fetchone() == ('deleted', [])
        assert db.execute("SELECT state,outcome->>'state' FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone() == ('done', 'done')
    assert store.calls == 1


def test_member_removal_blocks_draft_after_enqueue(migrated, worker_runtime):
    local_module()
    envelope = seed_envelope(migrated, worker_runtime[1], event_type='draft.generate')
    project, actor, member = seed_project(migrated, envelope.workspace_id)
    job, buyer, company = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fixture','Fixture')", (company, envelope.workspace_id))
        db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)", (buyer, envelope.workspace_id, project, company))
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) "
                   "VALUES(%s,%s,%s,%s,'draft_generation','generateDraft',%s::jsonb,'queued',1)",
                   (job, envelope.workspace_id, project, actor, json.dumps({'route': 'grounded-template.v1', 'max_cost': '0.000000'})))
        db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) VALUES(%s,%s,%s,%s,0,1,'pending')", (uuid.uuid4(), envelope.workspace_id, job, buyer))
        db.execute("UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s", (json.dumps({'job_id': str(job)}), envelope.outbox_id))
        db.execute("UPDATE memberships SET active=false WHERE id=%s", (member,))
    assert run_local(envelope).state == 'done'
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT status,blocked FROM async_jobs WHERE id=%s", (job,)).fetchone() == ('failed', 1)
        assert db.execute("SELECT reason_code FROM async_job_items WHERE job_id=%s", (job,)).fetchone()[0] == 'membership_changed'
        assert db.execute("SELECT count(*) FROM outreach_drafts WHERE workspace_id=%s", (envelope.workspace_id,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s", (envelope.workspace_id,)).fetchone()[0] == 0


def test_retention_runtime_role_membership_is_verified(migrated, worker_runtime):
    from buyeros_api.execution.handlers.retention import _delete_run_checkpoints
    workspace = uuid.uuid4()
    asyncio.run(_delete_run_checkpoints(worker_runtime[0], workspace, uuid.uuid4()))
    with pytest.raises(ValueError, match='dedicated worker role'):
        asyncio.run(_delete_run_checkpoints(migrated, workspace, uuid.uuid4()))


def test_arbitrary_local_step_key_cannot_skip_or_repeat_work(migrated, worker_runtime):
    envelope = seed_envelope(migrated, worker_runtime[1])
    assert run_local(envelope, 'bulk:99').code == 'INVALID_INTENT'
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone()[0] == 0


@pytest.mark.parametrize('change', ['membership', 'epoch'])
def test_parse_finalize_rechecks_actor_and_runtime_after_egress(migrated, worker_runtime, monkeypatch, change):
    from buyeros_api.execution import document_runner
    envelope, document, actor, key, body = document_case(migrated, worker_runtime[1])
    class Store:
        async def get_private(self, object_key):
            with psycopg.connect(migrated, autocommit=True) as db:
                if change == 'membership':
                    db.execute("UPDATE memberships SET active=false WHERE user_id=%s", (actor,))
                else:
                    db.execute("UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1")
            return body
    monkeypatch.setattr(document_runner, 'get_private_store', lambda ws: Store())
    result = run_local(envelope)
    assert (result.state, result.code) == (('blocked', 'ACTOR_CHANGED') if change == 'membership' else ('stale', 'STALE_FENCE'))
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT status,fact_candidates FROM offer_documents WHERE id=%s", (document,)).fetchone() == ('quarantined', [])


def test_disabled_r2_preserves_no_synthetic_document_facts(migrated, worker_runtime):
    from buyeros_api.settings import get_settings
    assert not get_settings().r2_enabled
    envelope, document, actor, key, body = document_case(migrated, worker_runtime[1])
    result = run_local(envelope)
    assert (result.state, result.code) == ('blocked', 'CAPABILITY_UNAVAILABLE')
    assert run_local(envelope) == result
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT status,fact_candidates FROM offer_documents WHERE id=%s", (document,)).fetchone() == ('quarantined', [])
        assert db.execute("SELECT state FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone()[0] == 'blocked'


def test_expired_local_deadline_cannot_start_work(migrated, worker_runtime):
    from buyeros_api.services.worker_execution import create_execution_engine
    envelope = seed_envelope(migrated, worker_runtime[1])
    async def run():
        engine = create_execution_engine()
        try:
            result = await local_module().execute_local_step(engine, envelope, 'start', deadline=datetime.now(timezone.utc)-timedelta(seconds=1))
            assert result.code == 'LIMIT_EXCEEDED'
        finally:
            await engine.dispose()
    asyncio.run(run())
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone()[0] == 0


def test_retention_page_redacts_only_fifty_sources_and_persists_successors(migrated, worker_runtime):
    from buyeros_api.execution.handlers.retention import expire_due_sources
    from buyeros_api.services.worker_execution import create_execution_engine
    envelope = seed_envelope(migrated, worker_runtime[1], event_type='source.delete')
    project, actor, member = seed_project(migrated, envelope.workspace_id)
    with psycopg.connect(migrated, autocommit=True) as db:
        for _ in range(60):
            source = uuid.uuid4()
            db.execute("INSERT INTO source_documents(id,workspace_id,project_id,permission_purpose,canonical_url,digest,retrieved_at,language,excerpt,retention_until,storage_mode,object_key) "
                       "VALUES(%s,%s,%s,'account_research',%s,%s,now(),'en','Fictional excerpt',now()-interval '1 minute','private_object',%s)",
                       (source, envelope.workspace_id, project, f'https://fixture.invalid/{source}', 'a'*64, f'tenants/{envelope.workspace_id}/{source}'))
    async def run():
        engine = create_execution_engine()
        try:
            assert len(await expire_due_sources(engine, datetime.now(timezone.utc), policy_version='fictional-test-only', limit=50)) == 50
        finally:
            await engine.dispose()
    asyncio.run(run())
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM source_documents WHERE workspace_id=%s AND excerpt IS NULL", (envelope.workspace_id,)).fetchone()[0] == 50
        assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND state='ready' AND event_type='source.delete'", (envelope.workspace_id,)).fetchone()[0] == 50
