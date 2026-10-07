"""T28 retention must hide source content before asynchronous object cleanup."""
import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.services.retention import expire_subject_data
from tests.conftest import runtime_role_dsn
from tests.test_run_admission_integration_db import admission_case
from tests.test_api_projects_db import api as project_api

WS_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
WS_B = uuid.UUID("22222222-2222-4222-8222-222222222222")
PROJECT_A = uuid.UUID("a0000000-0000-4000-8000-000000000001")


def test_source_expiry_hides_content_and_queues_one_tenant_object_deletion(seeded):
    source_a, source_b = uuid.uuid4(), uuid.uuid4()
    company_id, evidence_id, export_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    with psycopg.connect(seeded, autocommit=True) as conn:
        for source_id, workspace, marker in (
            (source_a, WS_A, "SECRET_SOURCE_A"), (source_b, WS_B, "SECRET_SOURCE_B"),
        ):
            conn.execute(
                """INSERT INTO source_documents
                   (id,workspace_id,project_id,canonical_url,digest,storage_mode,
                    object_key,excerpt,retention_until,permission_purpose)
                   VALUES (%s,%s,%s,%s,%s,'private_object',%s,%s,%s,'account_research')""",
                (source_id, workspace, PROJECT_A if workspace == WS_A else None,
                 f"https://example.invalid/{source_id}", "a" * 64,
                 f"tenants/{workspace}/{source_id}", marker, now - timedelta(seconds=1)),
            )
        conn.execute(
            "INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,'Fictional Co','Fictional Co')",
            (company_id, WS_A),
        )
        conn.execute(
            """INSERT INTO evidence(id,workspace_id,project_id,company_id,source_document_id,
                    stance,excerpt,translation,is_inference)
               VALUES (%s,%s,%s,%s,%s,'supports','SECRET_SOURCE_A','SECRET_TRANSLATION',false)""",
            (evidence_id, WS_A, PROJECT_A, company_id, source_a),
        )
        conn.execute(
            """INSERT INTO export_jobs(id,workspace_id,project_id,kind,scope_hash,state)
               VALUES (%s,%s,%s,'buyers',%s,'ready')""",
            (export_id, WS_A, PROJECT_A, "a" * 64),
        )
    async def expire():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                result = await expire_subject_data(
                    session, source_a, "fixture-policy-v1", now, subject_type="source_document"
                )
            async with tenant_session(engine, WS_A) as session:
                replay = await expire_subject_data(
                    session, source_a, "fixture-policy-v1", now, subject_type="source_document"
                )
            return result, replay
        finally:
            await engine.dispose()
    try:
        result, replay = asyncio.run(expire())
        assert result["expired"] is True
        assert replay["expired"] is False
        with psycopg.connect(seeded) as conn:
            rows = conn.execute(
                "SELECT id,excerpt,object_key,retention_until FROM source_documents "
                "WHERE id IN (%s,%s)", (source_a, source_b),
            ).fetchall()
            by_id = {row[0]: row for row in rows}
            assert by_id[source_a][1] is None
            assert by_id[source_b][1] == "SECRET_SOURCE_B"
            events = conn.execute(
                "SELECT event_type,payload FROM outbox_events "
                "WHERE workspace_id=%s AND intent_key=%s",
                (WS_A, f"source.delete:{source_a}"),
            ).fetchall()
            assert len(events) == 1
            assert events[0][0] == "source.delete"
            assert "SECRET_SOURCE_A" not in str(events[0][1])
            assert conn.execute(
                "SELECT excerpt,translation FROM evidence WHERE id=%s", (evidence_id,)
            ).fetchone() == ("Source expired", None)
            assert conn.execute(
                "SELECT state FROM export_jobs WHERE id=%s", (export_id,)
            ).fetchone()[0] == "revoked"
        # An isolated restore can replay the tombstone after losing a queued
        # object-delete intent; it must restore the intent, never the content.
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (f"source.delete:{source_a}",))
        async def replay_after_restore():
            engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
            try:
                async with tenant_session(engine, WS_A) as session:
                    return await expire_subject_data(
                        session, source_a, "fixture-policy-v1", now,
                        subject_type="source_document",
                    )
            finally:
                await engine.dispose()
        assert asyncio.run(replay_after_restore())["expired"] is False
        with psycopg.connect(seeded) as conn:
            assert conn.execute(
                "SELECT count(*) FROM outbox_events WHERE intent_key=%s",
                (f"source.delete:{source_a}",),
            ).fetchone()[0] == 1
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (f"source.delete:{source_a}",))
            conn.execute("DELETE FROM evidence WHERE id=%s", (evidence_id,))
            conn.execute("DELETE FROM export_jobs WHERE id=%s", (export_id,))
            conn.execute("DELETE FROM source_documents WHERE id IN (%s,%s)", (source_a, source_b))
            conn.execute("DELETE FROM companies WHERE id=%s", (company_id,))

def test_paid_admission_kill_rejects_before_run_or_outbox(admission_case, monkeypatch):
    from buyeros_api.api.routes.runs import selected_run_capability
    from buyeros_api.settings import get_settings
    from tests.test_run_admission_integration_db import CAPABILITY, _count, _post

    api, dsn = admission_case
    api.app.dependency_overrides[selected_run_capability] = lambda: (
        {**CAPABILITY, "provider": "named-but-not-activated"}, "production"
    )
    monkeypatch.setenv("BUYEROS_PAID_ADMISSION_ENABLED", "false")
    get_settings.cache_clear()
    try:
        response = _post(api, key="run-admission-kill-0001")
        assert response.status_code == 503
        assert response.json()["code"] == "CAPABILITY_DISABLED"
        assert _count(dsn, "search_runs") == 0
        assert _count(dsn, "outbox_events") == 0
    finally:
        get_settings.cache_clear()

def test_server_settings_repr_does_not_disclose_database_or_object_secrets():
    from buyeros_api.settings import Settings

    settings = Settings(
        database_url="postgresql://fixture:CANARY_DSN_PASSWORD@localhost:5432/buyeros_test_api",
        database_migration_url="postgresql://fixture:CANARY_MIGRATION_PASSWORD@localhost:5432/buyeros_test_api",
        r2_secret_access_key="CANARY_R2_SECRET",
    )
    rendered = repr(settings)
    for canary in ("CANARY_DSN_PASSWORD", "CANARY_MIGRATION_PASSWORD", "CANARY_R2_SECRET"):
        assert canary not in rendered


def test_source_expiry_redacts_derived_fit_and_draft_payloads(seeded):
    source_id, company_id, buyer_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    evidence_id, icp_id, fit_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    run_id, checkpoint_id = uuid.uuid4(), uuid.uuid4()
    draft_id, revision_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    content = {
        "subject": "SECRET_DERIVED_SUBJECT", "body": "SECRET_DERIVED_BODY",
        "claims": [{"text": "SECRET_DERIVED_CLAIM"}],
        "evidence_refs": [{"id": str(evidence_id), "version": 1}],
        "objective": "SECRET_DERIVED_OBJECTIVE", "language": "en", "kind": "initial",
        "icp_version_id": str(icp_id), "evidence_set_hash": "a" * 64,
        "value_proposition_fact_ids": [], "policy_decision_ids": [],
        "context_hash": "b" * 64,
    }
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO companies(id,workspace_id,legal_name,display_name) "
            "VALUES (%s,%s,'Fictional','Fictional')", (company_id, WS_A),
        )
        conn.execute(
            "INSERT INTO project_buyers(id,workspace_id,project_id,company_id) "
            "VALUES (%s,%s,%s,%s)", (buyer_id, WS_A, PROJECT_A, company_id),
        )
        conn.execute(
            "INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash) "
            "VALUES (%s,%s,%s,1,'{}'::jsonb,%s)",
            (icp_id, WS_A, PROJECT_A, "sha256:" + "a" * 64),
        )
        conn.execute(
            "INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,"
            "target_companies,raw_result_count) "
            "VALUES (%s,%s,%s,%s,'completed','{}'::jsonb,1,1)",
            (run_id, WS_A, PROJECT_A, icp_id),
        )
        conn.execute(
            "INSERT INTO source_documents(id,workspace_id,project_id,run_id,canonical_url,digest,"
            "storage_mode,excerpt,retention_until) VALUES (%s,%s,%s,%s,%s,%s,'excerpt_only',%s,%s)",
            (source_id, WS_A, PROJECT_A, run_id, "https://example.invalid/source", "a" * 64,
             "SECRET_SOURCE", now - timedelta(seconds=1)),
        )
        thread_id = f"{WS_A}:{run_id}:fit-v1:1:{buyer_id}"
        conn.execute(
            "INSERT INTO buyeros_graph.checkpoints(thread_id,checkpoint_ns,checkpoint_id,checkpoint,metadata) "
            "VALUES (%s,'',%s,%s::jsonb,'{}'::jsonb)",
            (thread_id, str(checkpoint_id), json.dumps({"text": "SECRET_CHECKPOINT"})),
        )
        conn.execute(
            "INSERT INTO buyeros_graph.checkpoint_blobs(thread_id,checkpoint_ns,channel,version,type,blob) "
            "VALUES (%s,'','source','v1','bytes',%s)",
            (thread_id, b"SECRET_CHECKPOINT_BLOB"),
        )
        conn.execute(
            "INSERT INTO buyeros_graph.checkpoint_writes(thread_id,checkpoint_ns,checkpoint_id,"
            "task_id,idx,channel,type,blob,task_path) "
            "VALUES (%s,'',%s,%s,0,'source','bytes',%s,'')",
            (thread_id, str(checkpoint_id), str(uuid.uuid4()), b"SECRET_CHECKPOINT_WRITE"),
        )
        conn.execute(
            "INSERT INTO evidence(id,workspace_id,project_id,company_id,source_document_id,"
            "stance,excerpt,is_inference) VALUES (%s,%s,%s,%s,%s,'supports','SECRET_SOURCE',false)",
            (evidence_id, WS_A, PROJECT_A, company_id, source_id),
        )
        conn.execute(
            "INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,"
            "icp_version_id,evidence_set_hash,verdict,rationale,evidence_ids,assessment_details) "
            "VALUES (%s,%s,%s,%s,%s,%s,'match','SECRET_DERIVED_RATIONALE',%s::jsonb,%s::jsonb)",
            (fit_id, WS_A, PROJECT_A, buyer_id, icp_id, "a" * 64,
             json.dumps([str(evidence_id)]), json.dumps({"source": "SECRET_DERIVED_DETAILS"})),
        )
        conn.execute(
            "INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
            "VALUES (%s,%s,%s,%s,1,'approved')", (draft_id, WS_A, PROJECT_A, buyer_id),
        )
        conn.execute(
            "INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,"
            "content,content_hash,evidence_ids,offer_fact_ids) "
            "VALUES (%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,'[]'::jsonb)",
            (revision_id, WS_A, draft_id, json.dumps(content), "c" * 64,
             json.dumps([str(evidence_id)])),
        )

    async def expire():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                return await expire_subject_data(
                    session, source_id, "fixture-policy-v1", now,
                    subject_type="source_document",
                )
        finally:
            await engine.dispose()
    try:
        assert asyncio.run(expire())["expired"] is True
        with psycopg.connect(seeded) as conn:
            fit = conn.execute(
                "SELECT verdict,rationale,assessment_details FROM fit_assessments WHERE id=%s",
                (fit_id,),
            ).fetchone()
            assert fit == ("needs_review", "Source expired", {})
            draft = conn.execute(
                "SELECT content FROM draft_revisions WHERE id=%s", (revision_id,)
            ).fetchone()[0]
            assert "SECRET_DERIVED" not in json.dumps(draft)
            assert draft["subject"] == "Source expired"
            assert draft["body"] == "Source expired"
            assert conn.execute(
                "SELECT state FROM outreach_drafts WHERE id=%s", (draft_id,)
            ).fetchone()[0] == "stale"
            assert conn.execute(
                "SELECT event_type FROM outbox_events WHERE intent_key=%s",
                (f"source.delete:{source_id}",),
            ).fetchone()[0] == "source.delete"
            # The checkpoint-owning worker deletes these after this transaction commits.
            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                assert conn.execute(
                    f"SELECT count(*) FROM buyeros_graph.{table} WHERE thread_id LIKE %s",
                    (f"{WS_A}:{run_id}:%",),
                ).fetchone()[0] == 1
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (f"source.delete:{source_id}",))
            conn.execute("DELETE FROM draft_revisions WHERE id=%s", (revision_id,))
            conn.execute("DELETE FROM outreach_drafts WHERE id=%s", (draft_id,))
            conn.execute("DELETE FROM fit_assessments WHERE id=%s", (fit_id,))
            conn.execute("DELETE FROM evidence WHERE id=%s", (evidence_id,))
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                conn.execute(f"DELETE FROM buyeros_graph.{table} WHERE thread_id LIKE %s",
                             (f"{WS_A}:{run_id}:%",))
            conn.execute("DELETE FROM source_documents WHERE id=%s", (source_id,))
            conn.execute("DELETE FROM search_runs WHERE id=%s", (run_id,))
            conn.execute("DELETE FROM icp_versions WHERE id=%s", (icp_id,))
            conn.execute("DELETE FROM project_buyers WHERE id=%s", (buyer_id,))
            conn.execute("DELETE FROM companies WHERE id=%s", (company_id,))


def test_contact_expiry_removes_address_person_and_addressed_draft(seeded):
    company_id, person_id, contact_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    buyer_id, draft_id, revision_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    approval_id, export_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(timezone.utc)
    content = {
        "subject": "Hello CANARY_CONTACT_PERSON",
        "body": "Write to CANARY_CONTACT_EMAIL",
        "claims": [], "evidence_refs": [], "kind": "initial", "language": "en",
        "icp_version_id": str(uuid.uuid4()), "evidence_set_hash": "a" * 64,
        "value_proposition_fact_ids": [], "policy_decision_ids": [],
        "context_hash": "b" * 64, "recipient_contact_id": str(contact_id),
    }
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
                     "VALUES (%s,%s,'Fictional','Fictional')", (company_id, WS_A))
        conn.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) "
                     "VALUES (%s,%s,%s,%s)", (buyer_id, WS_A, PROJECT_A, company_id))
        conn.execute("INSERT INTO people(id,workspace_id,company_id,full_name,role,retention_expires_at) "
                     "VALUES (%s,%s,%s,'CANARY_CONTACT_PERSON','buyer',%s)",
                     (person_id, WS_A, company_id, now - timedelta(seconds=1)))
        conn.execute("INSERT INTO contact_points(id,workspace_id,company_id,person_id,type,"
                     "normalized_value,validity,retention_expires_at) "
                     "VALUES (%s,%s,%s,%s,'business_email','CANARY_CONTACT_EMAIL',"
                     "'provider_marked_valid',%s)",
                     (contact_id, WS_A, company_id, person_id, now - timedelta(seconds=1)))
        conn.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
                     "VALUES (%s,%s,%s,%s,1,'draft')", (draft_id, WS_A, PROJECT_A, buyer_id))
        conn.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,"
                     "content,content_hash,evidence_ids,offer_fact_ids) "
                     "VALUES (%s,%s,%s,1,%s::jsonb,%s,'[]'::jsonb,'[]'::jsonb)",
                     (revision_id, WS_A, draft_id, json.dumps(content), "c" * 64))
        conn.execute(
            "INSERT INTO approvals(id,workspace_id,draft_id,revision_number,content_hash,"
            "context_fingerprint,approver_id,draft_revision_id,recipient_contact_id,"
            "context_snapshot,approved_at) VALUES (%s,%s,%s,1,%s,%s,%s,%s,%s,%s::jsonb,now())",
            (approval_id, WS_A, draft_id, "c" * 64, "sha256:" + "a" * 64,
             uuid.uuid4(), revision_id, contact_id,
             json.dumps({"recipient": "CANARY_CONTACT_EMAIL"})),
        )
        conn.execute(
            "INSERT INTO export_jobs(id,workspace_id,project_id,kind,scope_hash,state,"
            "include_contact_data) VALUES (%s,%s,%s,'buyers',%s,'ready',true)",
            (export_id, WS_A, PROJECT_A, "a" * 64),
        )

    async def expire():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, WS_A) as session:
                return await expire_subject_data(
                    session, contact_id, "fixture-policy-v1", now,
                    subject_type="contact_point",
                )
        finally:
            await engine.dispose()
    try:
        assert asyncio.run(expire())["expired"] is True
        with psycopg.connect(seeded) as conn:
            value, validity, quarantined = conn.execute(
                "SELECT normalized_value,validity,quarantined FROM contact_points WHERE id=%s",
                (contact_id,),
            ).fetchone()
            assert "CANARY_CONTACT_EMAIL" not in value
            assert validity == "unavailable" and quarantined is True
            assert conn.execute("SELECT full_name,role FROM people WHERE id=%s", (person_id,)).fetchone() == (None, None)
            body = conn.execute("SELECT content FROM draft_revisions WHERE id=%s", (revision_id,)).fetchone()[0]
            assert "CANARY_CONTACT" not in json.dumps(body)
            assert conn.execute("SELECT state FROM outreach_drafts WHERE id=%s", (draft_id,)).fetchone()[0] == "stale"
            assert conn.execute(
                "SELECT invalidated_reason,context_snapshot FROM approvals WHERE id=%s", (approval_id,)
            ).fetchone() == ("CONTACT_EXPIRED", None)
            assert conn.execute(
                "SELECT state FROM export_jobs WHERE id=%s", (export_id,)
            ).fetchone()[0] == "revoked"
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM approvals WHERE id=%s", (approval_id,))
            conn.execute("DELETE FROM export_jobs WHERE id=%s", (export_id,))
            conn.execute("DELETE FROM draft_revisions WHERE id=%s", (revision_id,))
            conn.execute("DELETE FROM outreach_drafts WHERE id=%s", (draft_id,))
            conn.execute("DELETE FROM contact_points WHERE id=%s", (contact_id,))
            conn.execute("DELETE FROM people WHERE id=%s", (person_id,))
            conn.execute("DELETE FROM project_buyers WHERE id=%s", (buyer_id,))
            conn.execute("DELETE FROM companies WHERE id=%s", (company_id,))


def test_contact_retention_migration_rolls_back_and_forward_on_empty_disposable_db(migrated):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    try:
        command.downgrade(config, "0031_retention_redaction")
        with psycopg.connect(migrated) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0031_retention_redaction"
            assert conn.execute("SELECT count(*) FROM information_schema.columns "
                                "WHERE table_name='contact_points' AND column_name='retention_expires_at'").fetchone()[0] == 0
    finally:
        command.upgrade(config, "head")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0038_c61_workspace_directory"
        assert conn.execute("SELECT count(*) FROM information_schema.columns "
                            "WHERE table_name='contact_points' AND column_name='retention_expires_at'").fetchone()[0] == 1


def test_expensive_read_and_write_rate_limits_are_actor_scoped_and_durable(project_api, seeded, monkeypatch):
    from buyeros_api.settings import get_settings
    from tests.test_api_projects_db import _h, OPERATOR, REVIEWER

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            # Keep all requests in one minute even on a loaded Docker host.
            return datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)

    monkeypatch.setattr("buyeros_api.services.api_rate_limit.datetime", FixedDatetime)
    monkeypatch.setenv("BUYEROS_EXPENSIVE_READ_PER_MINUTE", "2")
    monkeypatch.setenv("BUYEROS_EXPENSIVE_WRITE_PER_MINUTE", "1")
    get_settings.cache_clear()
    reads = [project_api.get(f"/v1/workspaces/{WS_A}/projects", headers=_h(OPERATOR))
             for _ in range(3)]
    assert [response.status_code for response in reads] == [200, 200, 429]
    assert reads[-1].json()["code"] == "RATE_LIMITED"
    assert reads[-1].headers["Retry-After"] == "60"
    assert project_api.get(f"/v1/workspaces/{WS_A}/projects", headers=_h(REVIEWER)).status_code == 200

    from tests.test_api_projects_db import CREATE
    first = project_api.post(f"/v1/workspaces/{WS_A}/projects", json=CREATE,
                             headers=_h(OPERATOR, key="retention-rate-write-1"))
    assert first.status_code == 201, first.text
    second = project_api.post(f"/v1/workspaces/{WS_A}/projects", json=CREATE,
                              headers=_h(OPERATOR, key="retention-rate-write-2"))
    assert second.status_code == 429
    with psycopg.connect(seeded) as conn:
        rows = conn.execute("SELECT bucket,hits FROM api_rate_windows WHERE workspace_id=%s "
                            "AND actor_id=%s ORDER BY bucket",
                            (WS_A, uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR))).fetchall()
    assert rows == [("expensive_read", 2), ("expensive_write", 1)]
    with psycopg.connect(runtime_role_dsn(seeded)) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, true)", (str(WS_B),))
        assert conn.execute("SELECT count(*) FROM api_rate_windows").fetchone()[0] == 0
    get_settings.cache_clear()


def test_rate_window_migration_empty_rollback_and_rls(migrated):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    with psycopg.connect(migrated, autocommit=True) as conn:
        conn.execute("DELETE FROM api_rate_windows")
        assert conn.execute("SELECT count(*) FROM api_rate_windows").fetchone()[0] == 0
    try:
        command.downgrade(config, "0032_contact_retention")
        with psycopg.connect(migrated) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0032_contact_retention"
            assert conn.execute("SELECT to_regclass('public.api_rate_windows')").fetchone()[0] is None
    finally:
        command.upgrade(config, "head")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0038_c61_workspace_directory"
        assert conn.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                            "WHERE relname='api_rate_windows'").fetchone() == (True, True)
        assert conn.execute("SELECT has_table_privilege('buyeros_api','api_rate_windows','DELETE')").fetchone()[0] is False


def test_rate_window_migration_refuses_populated_rollback(migrated):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    workspace_id, actor_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(migrated, autocommit=True) as conn:
        conn.execute("INSERT INTO api_rate_windows(workspace_id,actor_id,bucket,window_start,hits) "
                     "VALUES (%s,%s,'expensive_read',date_trunc('minute',now()),1)",
                     (workspace_id, actor_id))
    try:
        with pytest.raises(RuntimeError, match="retained API rate windows"):
            command.downgrade(config, "0032_contact_retention")
        with psycopg.connect(migrated) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0038_c61_workspace_directory"
    finally:
        with psycopg.connect(migrated, autocommit=True) as conn:
            conn.execute("DELETE FROM api_rate_windows WHERE workspace_id=%s AND actor_id=%s",
                         (workspace_id, actor_id))
