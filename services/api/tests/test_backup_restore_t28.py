"""T28 disposable two-container older-backup restore rehearsal.

The fixture journal lives outside both disposable databases. Durability and
authenticity of a real external journal remain an activation gate.
"""
import asyncio
import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.api.app import create_app
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.services.retention import expire_subject_data
from buyeros_api.settings import get_settings
from tests.conftest import (ALEMBIC_INI, DB_NAME, DB_USER, SERVICE_ROOT,
                            _start_container, runtime_role_dsn)

WS_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
WS_B = uuid.UUID("22222222-2222-4222-8222-222222222222")
PROJECT_A = uuid.UUID("a0000000-0000-4000-8000-000000000001")


def _docker_binary(args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(["docker", *args], input=input_bytes, capture_output=True)
    if result.returncode:
        raise AssertionError(f"disposable Docker command failed: {args[:2]}: "
                             + result.stderr.decode("utf-8", errors="replace")[-1000:])
    return result.stdout


def test_disposable_restore_replays_older_backup_deletion_journal(monkeypatch, tmp_path):
    source_name = target_name = None
    prior = os.environ.get("BUYEROS_DATABASE_URL")
    prior_read = os.environ.get("BUYEROS_LIVE_READ_ENABLED")
    try:
        source_name, source_dsn = _start_container()
        target_name, target_dsn = _start_container()
        monkeypatch.setenv("BUYEROS_DATABASE_URL", source_dsn)
        get_settings.cache_clear()
        config = Config(str(ALEMBIC_INI))
        config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
        command.upgrade(config, "head")
        source_id, account_id, cost_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        period_start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        period_end = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with psycopg.connect(source_dsn, autocommit=True) as db:
            db.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
            db.execute("GRANT USAGE ON SCHEMA public TO buyeros_api")
            db.execute("INSERT INTO workspaces(id,name,data_mode) "
                       "VALUES (%s,'A','live'),(%s,'B','live')", (WS_A, WS_B))
            db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,"
                       "language_preferences,version) VALUES "
                       "(%s,%s,'A','Fictional','Fixture offer',ARRAY['US'],ARRAY['en'],1)",
                       (PROJECT_A, WS_A))
            db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,"
                       "digest,storage_mode,object_key,excerpt,retention_until) VALUES "
                       "(%s,%s,%s,%s,%s,'private_object',%s,%s,now()-interval '1 day')",
                       (source_id, WS_A, PROJECT_A, f"https://fixture.invalid/{source_id}",
                        "a" * 64, f"tenants/{WS_A}/{source_id}", "fixture source text"))
            db.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,"
                       "currency,period,period_start,period_end,version,frozen,approved_limit,"
                       "settled_spend) VALUES (%s,%s,'workspace',%s,'all','USD','monthly',"
                       "%s,%s,1,false,10.000000,1.250000)",
                       (account_id, WS_A, WS_A, period_start, period_end))
            db.execute("INSERT INTO cost_events(id,workspace_id,kind,amount,pricing_version) "
                       "VALUES (%s,%s,'commit',1.250000,'fixture-v1')", (cost_id, WS_A))

        dump = _docker_binary(["exec", source_name, "pg_dump", "-U", DB_USER,
                               "-d", DB_NAME, "--format=custom", "--no-owner"])
        # This dump predates the deletion. A separately held journal must drive
        # replay before the restored database can serve live reads.
        journal_path = tmp_path / "deletion-journal.json"
        async def expire_original():
            engine = create_async_engine(async_database_url(runtime_role_dsn(source_dsn)))
            try:
                async with tenant_session(engine, WS_A) as session:
                    return await expire_subject_data(session, source_id, "fixture-policy-v1",
                                                     datetime.now(timezone.utc),
                                                     subject_type="source_document")
            finally:
                await engine.dispose()
        assert asyncio.run(expire_original())["expired"] is True
        with psycopg.connect(source_dsn) as db:
            audit = db.execute(
                "SELECT detail_digest FROM audit_events WHERE workspace_id=%s "
                "AND subject_id=%s AND subject_type='source_document' "
                "AND action='source.expired'", (WS_A, str(source_id)),
            ).fetchone()
            assert audit is not None
            expected_digest = "sha256:" + hashlib.sha256(b"fixture-policy-v1").hexdigest()
            assert audit[0] == expected_digest
        journal_path.write_text(json.dumps({
            "workspace_id": str(WS_A), "subject_id": str(source_id),
            "subject_type": "source_document", "policy_version": "fixture-policy-v1",
            "policy_digest": expected_digest,
        }), encoding="utf-8")

        with psycopg.connect(target_dsn, autocommit=True) as db:
            db.execute("CREATE ROLE buyeros_api NOBYPASSRLS LOGIN PASSWORD 'test-only'")
            db.execute("CREATE ROLE buyeros_worker NOBYPASSRLS")
        _docker_binary(["exec", "-i", target_name, "pg_restore", "-U", DB_USER,
                        "-d", DB_NAME, "--no-owner"], input_bytes=dump)
        with psycopg.connect(target_dsn, autocommit=True) as db:
            db.execute("GRANT USAGE ON SCHEMA public TO buyeros_api")
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0038_c61_workspace_directory"
            assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                              "WHERE relname='source_documents'").fetchone() == (True, True)
            account_spend = db.execute("SELECT settled_spend FROM budget_accounts WHERE id=%s",
                                       (account_id,)).fetchone()[0]
            event_spend = db.execute("SELECT sum(amount) FROM cost_events WHERE workspace_id=%s "
                                     "AND kind='commit'", (WS_A,)).fetchone()[0]
            assert account_spend == event_spend == Decimal("1.250000")
        with psycopg.connect(target_dsn) as db:
            assert db.execute("SELECT canonical_url,excerpt FROM source_documents WHERE id=%s",
                              (source_id,)).fetchone() == (
                                  f"https://fixture.invalid/{source_id}", "fixture source text")
            assert db.execute("SELECT count(*) FROM audit_events WHERE action='source.expired' "
                              "AND subject_id=%s", (str(source_id),)).fetchone()[0] == 0
        monkeypatch.setenv("BUYEROS_LIVE_READ_ENABLED", "false")
        get_settings.cache_clear()
        with TestClient(create_app()) as api:
            blocked = api.get(f"/v1/workspaces/{WS_A}/projects")
            assert blocked.status_code == 503
            assert blocked.json()["code"] == "READ_DISABLED"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        assert journal["workspace_id"] == str(WS_A)
        assert journal["subject_type"] == "source_document"
        assert journal["policy_digest"] == "sha256:" + hashlib.sha256(
            journal["policy_version"].encode("utf-8")
        ).hexdigest()
        runtime_dsn = runtime_role_dsn(target_dsn)
        with psycopg.connect(runtime_dsn) as db:
            db.execute("SELECT set_config('app.workspace_id', %s, true)", (str(WS_B),))
            assert db.execute("SELECT count(*) FROM source_documents").fetchone()[0] == 0
            assert db.execute("SELECT count(*) FROM budget_accounts").fetchone()[0] == 0
        with psycopg.connect(runtime_dsn) as db:
            db.execute("SELECT set_config('app.workspace_id', %s, true)", (str(WS_A),))
            assert db.execute("SELECT count(*) FROM source_documents").fetchone()[0] == 1

        async def replay():
            engine = create_async_engine(async_database_url(runtime_dsn))
            try:
                async with tenant_session(engine, uuid.UUID(journal["workspace_id"])) as session:
                    first = await expire_subject_data(
                        session, uuid.UUID(journal["subject_id"]),
                        journal["policy_version"], datetime.now(timezone.utc),
                        subject_type=journal["subject_type"],
                    )
                async with tenant_session(engine, uuid.UUID(journal["workspace_id"])) as session:
                    second = await expire_subject_data(
                        session, uuid.UUID(journal["subject_id"]),
                        journal["policy_version"], datetime.now(timezone.utc),
                        subject_type=journal["subject_type"],
                    )
                return first, second
            finally:
                await engine.dispose()
        first, second = asyncio.run(replay())
        assert first["expired"] is True
        assert second["expired"] is False
        with psycopg.connect(target_dsn) as db:
            assert db.execute("SELECT canonical_url,excerpt,object_key FROM source_documents "
                              "WHERE id=%s", (source_id,)).fetchone() == (
                                  f"https://redacted.invalid/{source_id}", None,
                                  f"tenants/{WS_A}/{source_id}")
            assert db.execute("SELECT count(*) FROM audit_events WHERE action='source.expired' "
                              "AND subject_id=%s", (str(source_id),)).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM outbox_events WHERE intent_key=%s",
                              (f"source.delete:{source_id}",)).fetchone()[0] == 1
        with psycopg.connect(runtime_dsn) as db:
            db.execute("SELECT set_config('app.workspace_id', %s, true)", (str(WS_B),))
            assert db.execute("SELECT count(*) FROM source_documents").fetchone()[0] == 0
        with TestClient(create_app()) as api:
            blocked = api.get(f"/v1/workspaces/{WS_A}/projects")
            assert blocked.status_code == 503
            assert blocked.json()["code"] == "READ_DISABLED"
    finally:
        if prior is None:
            os.environ.pop("BUYEROS_DATABASE_URL", None)
        else:
            os.environ["BUYEROS_DATABASE_URL"] = prior
        if prior_read is None:
            os.environ.pop("BUYEROS_LIVE_READ_ENABLED", None)
        else:
            os.environ["BUYEROS_LIVE_READ_ENABLED"] = prior_read
        get_settings.cache_clear()
        for name in (target_name, source_name):
            if name:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True)
