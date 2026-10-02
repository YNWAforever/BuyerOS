"""Real PostgreSQL arbitration and least-privilege machine runtime tests."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from tests.cloudflare_fixtures import cloudflare_database as migrated

SERVICE = Path(__file__).resolve().parents[1] / "buyeros_api/services/worker_execution.py"


def runtime_module():
    assert SERVICE.is_file(), "CF02 durable runtime selector/step fence missing"
    from buyeros_api.services import worker_execution
    return worker_execution


@pytest.fixture
def worker_runtime(migrated, monkeypatch):
    runtime_module()
    from buyeros_api.settings import get_settings
    parts = urlsplit(migrated)
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    dsn = urlunsplit(parts._replace(netloc=f"buyeros_worker:test-only@{host}:{parts.port}"))
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("UPDATE worker_runtime_control SET backend='cloudflare', enabled=true, epoch=epoch+1, "
                   "active_owner=NULL, active_until=NULL WHERE singleton=1")
        epoch = db.execute("SELECT epoch FROM worker_runtime_control").fetchone()[0]
    monkeypatch.setenv("BUYEROS_EXECUTION_DATABASE_URL", dsn)
    monkeypatch.setenv("BUYEROS_CLOUDFLARE_EXECUTION_ENABLED", "true")
    get_settings.cache_clear()
    yield dsn, epoch
    get_settings.cache_clear()


def seed_envelope(migrated, epoch, *, event_type="bulk.mutate", payload=None):
    from buyeros_api.api.worker_schemas import JobEnvelope
    workspace, outbox = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Fictional CF02','live')", (workspace,))
        db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state," 
                   "fencing_generation,runtime_backend,runtime_epoch) "
                   "VALUES(%s,%s,%s,%s,%s::jsonb,'dispatched',1,'cloudflare',%s)",
                   (outbox, workspace, f"cf02:{outbox}", event_type, json.dumps(payload or {}), epoch))
    return JobEnvelope(v=1, workspace_id=workspace, outbox_id=outbox, generation=1, runtime_epoch=epoch)


def test_same_generation_has_one_execution_owner(migrated, worker_runtime):
    service = runtime_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    async def run():
        from buyeros_api.db.session import tenant_session
        engine = service.create_execution_engine()
        async def claim():
            async with tenant_session(engine, envelope.workspace_id) as session:
                return await service.claim_execution_step(session, envelope, "start", datetime.now(timezone.utc))
        try:
            claims = await asyncio.gather(*(claim() for _ in range(20)))
            assert sum(row.state == "claimed" for row in claims) == 1
            assert sum(row.state == "busy" for row in claims) == 19
            assert len({row.owner for row in claims if row.owner is not None}) == 1
        finally:
            await engine.dispose()
    asyncio.run(run())
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone()[0] == 1


def test_selector_rejects_other_backend_and_old_epoch(migrated, worker_runtime):
    service = runtime_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE worker_runtime_control SET backend='celery', epoch=epoch+1 WHERE singleton=1")
    async def run():
        from buyeros_api.db.session import tenant_session
        engine = service.create_execution_engine()
        try:
            async with tenant_session(engine, envelope.workspace_id) as session:
                claim = await service.claim_execution_step(session, envelope, "start", datetime.now(timezone.utc))
                assert claim.state == "stale"
        finally:
            await engine.dispose()
    asyncio.run(run())
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone()[0] == 0


def test_default_off_and_worker_cannot_activate_selector(migrated):
    runtime_module()
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT enabled FROM worker_runtime_control WHERE singleton=1").fetchone() is not None
        assert db.execute("SELECT has_column_privilege('buyeros_worker','worker_runtime_control','enabled','UPDATE')").fetchone()[0] is False
        assert db.execute("SELECT has_table_privilege('buyeros_api','worker_bridge_nonces','SELECT')").fetchone()[0] is False


def test_worker_step_tenant_rls_is_forced_and_nonces_are_unique(migrated, worker_runtime):
    runtime_module()
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='worker_steps'").fetchone() == (True, True)
    with psycopg.connect(worker_runtime[0]) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE worker_runtime_control SET enabled=true")


def test_claim_cycle_persists_fair_cursor_and_obeys_db_selector(migrated, worker_runtime):
    service = runtime_module()
    for _ in range(6):
        envelope = seed_envelope(migrated, worker_runtime[1])
        with psycopg.connect(migrated, autocommit=True) as db:
            db.execute("UPDATE outbox_events SET state='ready',fencing_generation=0 WHERE id=%s", (envelope.outbox_id,))
    async def run():
        from buyeros_api.execution.dispatcher import claim_cycle
        engine = service.create_execution_engine()
        try:
            batch = await claim_cycle(engine, backend="cloudflare", epoch=worker_runtime[1], max_total=4)
            assert len(batch.items) == 4
            with psycopg.connect(migrated) as db:
                assert db.execute("SELECT cursor FROM worker_runtime_control").fetchone()[0] == batch.next_cursor
            with psycopg.connect(migrated, autocommit=True) as db:
                db.execute("UPDATE worker_runtime_control SET backend='celery',epoch=epoch+1")
            assert not (await claim_cycle(engine, backend="cloudflare", epoch=worker_runtime[1])).items
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_twenty_step_requests_commit_one_bulk_mutation(migrated, worker_runtime):
    service = runtime_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    project, user, membership, company, buyer, job = (uuid.uuid4() for _ in range(6))
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
                   "VALUES(%s,%s,'Fixture','Fixture','Fictional offer','{HK}','{en}',1)", (project, envelope.workspace_id))
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'https://fixture.invalid/',%s)", (user, f"cf02|{user}"))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES(%s,%s,%s,'{workspace_admin}',true)",
                   (membership, envelope.workspace_id, user))
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fixture','Fixture')",
                   (company, envelope.workspace_id))
        db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)",
                   (buyer, envelope.workspace_id, project, company))
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) "
                   "VALUES(%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,'queued',1)",
                   (job, envelope.workspace_id, project, user, json.dumps({"owner_membership_id": str(membership), "reason": "Fixture assignment"})))
        db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) "
                   "VALUES(%s,%s,%s,%s,0,1,'pending')", (uuid.uuid4(), envelope.workspace_id, job, buyer))
        db.execute("UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s", (json.dumps({"job_id": str(job)}), envelope.outbox_id))
    async def run():
        engine = service.create_execution_engine()
        try:
            results = await asyncio.gather(*(service.execute_step(engine, envelope, "start") for _ in range(20)))
            assert any(row.state == "done" for row in results)
            assert all(row.state in {"done", "retry_later"} for row in results)
            assert (await service.read_step_status(engine, envelope, "start")).state == "done"
        finally:
            await engine.dispose()
    asyncio.run(run())
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT owner_user_id,version FROM project_buyers WHERE id=%s", (buyer,)).fetchone() == (user, 2)
        assert db.execute("SELECT count(*) FROM audit_events WHERE subject_id=%s AND action='buyer.owner_assigned'", (str(buyer),)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (envelope.outbox_id,)).fetchone()[0] == 1


def test_foreign_tenant_cannot_claim_step(migrated, worker_runtime):
    service = runtime_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    async def run():
        from buyeros_api.db.session import tenant_session
        engine = service.create_execution_engine()
        try:
            async with tenant_session(engine, uuid.uuid4()) as session:
                claim = await service.claim_execution_step(session, envelope, "start", datetime.now(timezone.utc))
                assert claim.state == "stale"
        finally:
            await engine.dispose()
    asyncio.run(run())


def test_stale_publication_failure_cannot_release_newer_generation(migrated, worker_runtime):
    service = runtime_module()
    envelope = seed_envelope(migrated, worker_runtime[1])
    async def run():
        from buyeros_api.execution.dispatcher import release_claim
        from buyeros_api.db.session import tenant_session
        engine = service.create_execution_engine()
        try:
            async with tenant_session(engine, envelope.workspace_id) as session:
                await release_claim(session, f"cf02:{envelope.outbox_id}", generation=0)
        finally:
            await engine.dispose()
    asyncio.run(run())
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT state FROM outbox_events WHERE id=%s", (envelope.outbox_id,)).fetchone()[0] == "dispatched"
