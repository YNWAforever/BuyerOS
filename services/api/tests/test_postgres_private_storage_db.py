"""Real private document bytes, API transactions, worker parsing, and tenant RLS."""
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from tests.test_offer_document_routes_db import api, doc_api
from tests.test_buyer_review_db import OPERATOR, VIEWER, WORKSPACE_A, WORKSPACE_B, PROJECT_A, _h
from tests.conftest import runtime_role_dsn

BODY = b"Product: Fictional sensor\nValue proposition: Measures temperature\n"


@pytest.fixture
def private_postgres(monkeypatch, seeded):
    from buyeros_api.settings import get_settings
    monkeypatch.setenv("BUYEROS_PRIVATE_OBJECT_BACKEND", "postgres")
    monkeypatch.setenv("BUYEROS_R2_ENABLED", "false")
    monkeypatch.setenv("BUYEROS_CLOUDFLARE_EXECUTION_ENABLED", "false")
    get_settings.cache_clear()
    yield
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("DELETE FROM private_document_objects WHERE workspace_id IN (%s,%s)", (WORKSPACE_A, WORKSPACE_B))
    get_settings.cache_clear()


@pytest.fixture
def worker_receipt_cleanup(doc_api, seeded):
    yield
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("DELETE FROM worker_steps WHERE workspace_id=%s", (WORKSPACE_A,))


def upload(client, *, key="private-pg-upload-001", subject=OPERATOR, body=BODY, digest=None):
    return client.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/offer-documents",
        headers=_h(subject=subject, key=key),
        files={"file": ("offer.md", body, "text/markdown")},
        data={"declared_sha256": digest or hashlib.sha256(body).hexdigest()},
    )


def test_explicit_postgres_upload_is_atomic_private_and_replayable(doc_api, seeded, private_postgres):
    result = upload(doc_api)
    assert result.status_code == 202, result.text
    data = result.json()["data"]
    assert data["status"] == "ready"
    assert [(item["field"], item["value"], item["approved"]) for item in data["fact_candidates"]] == [
        ("product", "Fictional sensor", False), ("value_proposition", "Measures temperature", False),
    ]
    assert "object_key" not in data and "body" not in data
    replay = upload(doc_api)
    assert replay.status_code == 202 and replay.json()["data"]["id"] == data["id"]
    assert upload(doc_api, body=b"Product: Other\n").status_code == 409
    assert upload(doc_api, key="private-pg-viewer", subject=VIEWER).status_code == 403
    assert upload(doc_api, key="private-pg-digest", digest="0" * 64).status_code == 400
    with psycopg.connect(seeded) as db:
        row = db.execute(
            "SELECT d.object_key,o.body,o.source_sha256,o.retention_until-o.created_at "
            "FROM offer_documents d JOIN private_document_objects o "
            "ON o.workspace_id=d.workspace_id AND o.id=split_part(d.object_key,'/',4)::uuid "
            "WHERE d.id=%s", (data["id"],),
        ).fetchone()
        assert row[0].startswith(f"postgres/tenants/{WORKSPACE_A}/")
        assert bytes(row[1]) == BODY and row[2] == hashlib.sha256(BODY).hexdigest()
        assert row[3] == timedelta(days=30)
        assert db.execute("SELECT count(*) FROM private_document_objects WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM outbox_events WHERE intent_key=%s", (f"offer.parse:{data['id']}",)).fetchone()[0] == 1
        assert db.execute("SELECT state,payload->>'processing_mode' FROM outbox_events WHERE intent_key=%s", (f"offer.parse:{data['id']}",)).fetchone() == ("done", "inline_deterministic")
        assert db.execute("SELECT count(*) FROM worker_steps WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone() == (0,)


def test_postgres_upload_rolls_back_bytes_with_document_receipt_and_outbox(doc_api, seeded, private_postgres, monkeypatch):
    from buyeros_api.api.routes import documents
    from buyeros_api.api.errors import ApiError

    def fail_receipt(*args, **kwargs):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "injected transaction failure")

    monkeypatch.setattr(documents, "complete_idempotency", fail_receipt)
    result = upload(doc_api, key="private-pg-rollback")
    assert result.status_code == 503
    with psycopg.connect(seeded) as db:
        for table in ("private_document_objects", "offer_documents"):
            assert db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='offer.parse'", (WORKSPACE_A,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM idempotency_records WHERE workspace_id=%s AND key='private-pg-rollback'", (WORKSPACE_A,)).fetchone()[0] == 0


def test_postgres_inline_delete_erases_bytes_without_scheduler(doc_api, seeded, private_postgres):
    response = upload(doc_api, key="private-inline-delete-upload")
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    url = f"/v1/workspaces/{WORKSPACE_A}/offer-documents/{data['id']}"
    deleted = doc_api.request("DELETE", url, headers=_h(key="private-inline-delete", **{"If-Match": f'"{data["version"]}"'}), json={"reason": "fixture withdrawn"})
    assert deleted.status_code == 202, deleted.text
    assert doc_api.get(url, headers=_h()).status_code == 404
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT count(*) FROM private_document_objects WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone() == (0,)
        assert db.execute("SELECT object_key,fact_candidates FROM offer_documents WHERE id=%s", (data["id"],)).fetchone() == (None, [])
        assert db.execute("SELECT state,payload->>'processing_mode' FROM outbox_events WHERE intent_key=%s", (f"offer.delete:{data['id']}",)).fetchone() == ("done", "inline_deterministic")


def test_postgres_delete_failure_restores_bytes_and_document(doc_api, seeded, private_postgres, monkeypatch):
    from buyeros_api.api.routes import documents
    from buyeros_api.api.errors import ApiError
    response = upload(doc_api, key="private-delete-rollback-upload")
    assert response.status_code == 202, response.text
    original = response.json()["data"]

    def fail_receipt(*args, **kwargs):
        raise ApiError(503, "PROVIDER_UNAVAILABLE", "injected deletion transaction failure")

    monkeypatch.setattr(documents, "complete_idempotency", fail_receipt)
    url = f"/v1/workspaces/{WORKSPACE_A}/offer-documents/{original['id']}"
    failed = doc_api.request("DELETE", url, headers=_h(key="private-delete-rollback", **{"If-Match": f'"{original["version"]}"'}), json={"reason": "fixture withdrawn"})
    assert failed.status_code == 503
    assert doc_api.get(url, headers=_h()).json()["data"] == original
    with psycopg.connect(seeded) as db:
        assert bytes(db.execute("SELECT body FROM private_document_objects WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0]) == BODY
        assert db.execute("SELECT count(*) FROM outbox_events WHERE intent_key=%s", (f"offer.delete:{original['id']}",)).fetchone() == (0,)


def test_postgres_inline_pdf_uses_real_isolated_parser_without_scheduler(doc_api, private_postgres):
    from io import BytesIO
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    output = BytesIO()
    writer.write(output)
    body = output.getvalue()
    response = doc_api.post(
        f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/offer-documents",
        headers=_h(key="private-inline-real-pdf"),
        files={"file": ("offer.pdf", body, "application/pdf")},
        data={"declared_sha256": hashlib.sha256(body).hexdigest()},
    )
    assert response.status_code == 202, response.text
    assert response.json()["data"]["status"] == "ready"
    assert response.json()["data"]["fact_candidates"] == []


@pytest.mark.parametrize("reason", ["PARSER_TIMEOUT", "INVALID_DOCUMENT"])
def test_postgres_inline_parse_failure_is_visible_without_approved_facts(doc_api, seeded, private_postgres, monkeypatch, reason):
    from buyeros_api.api.routes import documents
    from buyeros_api.execution.pdf_parser import PdfParserTimeout

    async def parser_failure(upload):
        raise PdfParserTimeout("bounded parser fixture") if reason == "PARSER_TIMEOUT" else ValueError("invalid parser fixture")

    monkeypatch.setattr(documents, "parse_upload_candidates", parser_failure)
    response = upload(doc_api, key=f"private-inline-{reason.lower()}")
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["status"] == "failed" and data["failure_code"] == reason
    assert data["fact_candidates"] == []


def test_postgres_inline_parse_reauthorizes_before_persisting(doc_api, seeded, private_postgres, monkeypatch):
    from buyeros_api.api.routes import documents
    original = documents.parse_upload_candidates

    async def lose_permission(upload):
        facts = await original(upload)
        with psycopg.connect(seeded, autocommit=True) as db:
            db.execute("UPDATE memberships SET roles='{viewer}' WHERE workspace_id=%s AND user_id=%s", (WORKSPACE_A, uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)))
        return facts

    monkeypatch.setattr(documents, "parse_upload_candidates", lose_permission)
    assert upload(doc_api, key="private-inline-revoked").status_code == 403
    with psycopg.connect(seeded) as db:
        for table in ("private_document_objects", "offer_documents"):
            assert db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone() == (0,)


def test_postgres_upload_final_transaction_serializes_concurrent_project_archive(doc_api, seeded, private_postgres, monkeypatch):
    from buyeros_api.services.object_store import PostgresPrivateStore
    original = PostgresPrivateStore.put_private
    archive_results = []

    async def archive_during_final_transaction(store, *args, **kwargs):
        try:
            with psycopg.connect(seeded, options="-c lock_timeout=200") as db:
                db.execute("UPDATE projects SET status='archived' WHERE id=%s", (PROJECT_A,))
            archive_results.append("committed")
        except psycopg.errors.LockNotAvailable:
            archive_results.append("blocked")
        return await original(store, *args, **kwargs)

    monkeypatch.setattr(PostgresPrivateStore, "put_private", archive_during_final_transaction)
    response = upload(doc_api, key="private-project-lock")
    assert response.status_code == 202, response.text
    assert archive_results == ["blocked"]


def test_postgres_upload_rejects_project_archived_during_inline_parse(doc_api, seeded, private_postgres, monkeypatch):
    from buyeros_api.api.routes import documents
    original = documents.parse_upload_candidates

    async def archive_during_parse(upload):
        facts = await original(upload)
        with psycopg.connect(seeded, options="-c lock_timeout=200") as db:
            db.execute("UPDATE projects SET status='archived' WHERE id=%s", (PROJECT_A,))
        return facts

    monkeypatch.setattr(documents, "parse_upload_candidates", archive_during_parse)
    assert upload(doc_api, key="private-project-archived").status_code == 404
    with psycopg.connect(seeded) as db:
        for table in ("private_document_objects", "offer_documents"):
            assert db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone() == (0,)


def test_authorized_document_list_purges_only_due_private_tenant_bytes(doc_api, seeded, private_postgres):
    with psycopg.connect(seeded) as db:
        for index in range(102):
            db.execute("INSERT INTO private_document_objects(id,workspace_id,body,source_sha256,created_at,retention_until) VALUES(%s,%s,%s,%s,now()-interval '2 hours',now()-interval '1 hour')", (uuid.uuid4(), WORKSPACE_A if index < 101 else WORKSPACE_B, BODY, hashlib.sha256(BODY).hexdigest()))
    url = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/offer-documents"
    assert doc_api.get(url, headers=_h(subject=VIEWER)).status_code == 200
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT workspace_id,count(*) FROM private_document_objects GROUP BY workspace_id ORDER BY workspace_id").fetchall() == [(uuid.UUID(WORKSPACE_A), 1), (uuid.UUID(WORKSPACE_B), 1)]
    assert doc_api.get(url, headers=_h(subject=VIEWER)).status_code == 200
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT workspace_id,count(*) FROM private_document_objects GROUP BY workspace_id").fetchall() == [(uuid.UUID(WORKSPACE_B), 1)]


def test_postgres_worker_uses_its_engine_and_existing_parse_delete_workflow(doc_api, seeded, private_postgres, monkeypatch, worker_receipt_cleanup):
    from buyeros_api.settings import get_settings
    from buyeros_api.services import worker_execution
    from buyeros_api.api.worker_schemas import JobEnvelope

    result = upload(doc_api, key="private-pg-worker")
    assert result.status_code == 202, result.text
    document = result.json()["data"]["id"]
    parts = urlsplit(seeded)
    worker_dsn = urlunsplit(parts._replace(netloc=f"buyeros_worker:test-only@{parts.hostname}:{parts.port}"))
    with psycopg.connect(seeded, autocommit=True) as db:
        # Recreate a quarantined row from an older upload to exercise the native
        # worker path independently of the new inline ingestion path.
        db.execute("UPDATE offer_documents SET status='quarantined',fact_candidates='[]'::jsonb WHERE id=%s", (document,))
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL WHERE singleton=1")
        epoch = db.execute("SELECT epoch FROM worker_runtime_control").fetchone()[0]
    monkeypatch.setenv("BUYEROS_EXECUTION_DATABASE_URL", worker_dsn)
    monkeypatch.setenv("BUYEROS_CLOUDFLARE_EXECUTION_ENABLED", "true")
    get_settings.cache_clear()

    def run_intent(kind):
        with psycopg.connect(seeded, autocommit=True) as db:
            outbox = db.execute(
                "UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend='cloudflare',runtime_epoch=%s "
                "WHERE intent_key=%s RETURNING id", (epoch, f"{kind}:{document}"),
            ).fetchone()[0]
        envelope = JobEnvelope(v=1, workspace_id=WORKSPACE_A, outbox_id=outbox, generation=1, runtime_epoch=epoch)

        async def execute():
            engine = worker_execution.create_execution_engine()
            try:
                return await worker_execution.execute_step(engine, envelope, "start")
            finally:
                await engine.dispose()
        return asyncio.run(execute())

    # An ordinary API engine must never be borrowed inside worker storage I/O.
    from buyeros_api.api import deps
    original_engine = deps.get_engine
    monkeypatch.setattr(deps, "get_engine", lambda: (_ for _ in ()).throw(AssertionError("worker borrowed API engine")))
    assert run_intent("offer.parse").state == "done"
    monkeypatch.setattr(deps, "get_engine", original_engine)
    url = f"/v1/workspaces/{WORKSPACE_A}/offer-documents/{document}"
    read = doc_api.get(url, headers=_h()).json()["data"]
    assert read["status"] == "ready"
    assert [(item["field"], item["value"], item["approved"]) for item in read["fact_candidates"]] == [
        ("product", "Fictional sensor", False), ("value_proposition", "Measures temperature", False),
    ]
    deleted = doc_api.request("DELETE", url, headers=_h(key="private-pg-delete", **{"If-Match": f'"{read["version"]}"'}), json={"reason": "fixture withdrawn"})
    assert deleted.status_code == 202, deleted.text
    assert run_intent("offer.delete").state == "done"
    with psycopg.connect(seeded) as db:
        assert db.execute("SELECT count(*) FROM private_document_objects WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
        assert db.execute("SELECT status,object_key,fact_candidates FROM offer_documents WHERE id=%s", (document,)).fetchone() == ("deleted", None, [])


def test_private_postgres_enforces_database_bounds_and_tenant_isolation(seeded, private_postgres):
    from buyeros_api.api.deps import async_database_url
    from buyeros_api.services.object_store import get_private_store
    from sqlalchemy.ext.asyncio import create_async_engine

    async def exercise():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        store = get_private_store(uuid.UUID(WORKSPACE_A), engine=engine)
        try:
            key = await store.put_private(BODY, digest=hashlib.sha256(BODY).hexdigest(), retention_seconds=60)
            assert await store.get_private(key) == BODY
            foreign = get_private_store(uuid.UUID(WORKSPACE_B), engine=engine)
            for operation in (foreign.get_private, foreign.delete_private):
                with pytest.raises(ValueError, match="foreign"):
                    await operation(key)
            for body, digest, seconds in [(b"", hashlib.sha256(b"").hexdigest(), 60),
                                           (b"x" * (5 * 1024 * 1024 + 1), "a" * 64, 60),
                                           (BODY, "a" * 64, 60),
                                           (BODY, hashlib.sha256(BODY).hexdigest(), 0),
                                           (BODY, hashlib.sha256(BODY).hexdigest(), 30 * 86400 + 1)]:
                with pytest.raises(ValueError):
                    await store.put_private(body, digest=digest, retention_seconds=seconds)
            with psycopg.connect(runtime_role_dsn(seeded)) as db:
                assert db.execute("SELECT count(*) FROM private_document_objects").fetchone() == (0,)
                db.execute("SELECT set_config('app.workspace_id', %s, true)", (WORKSPACE_B,))
                assert db.execute("SELECT count(*) FROM private_document_objects").fetchone() == (0,)
                assert db.execute("DELETE FROM private_document_objects WHERE id=%s RETURNING id", (key.rsplit("/", 1)[1],)).fetchall() == []
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute("INSERT INTO private_document_objects(id,workspace_id,body,source_sha256,retention_until) VALUES(%s,%s,%s,%s,now()+interval '1 minute')", (uuid.uuid4(), WORKSPACE_A, BODY, hashlib.sha256(BODY).hexdigest()))
                db.rollback()
            for body, digest, seconds in [(b"", hashlib.sha256(b"").hexdigest(), 60),
                                           (BODY, "a" * 64, 60),
                                           (BODY, hashlib.sha256(BODY).hexdigest(), 30 * 86400 + 1)]:
                with psycopg.connect(runtime_role_dsn(seeded)) as db:
                    db.execute("SELECT set_config('app.workspace_id', %s, true)", (WORKSPACE_A,))
                    with pytest.raises(psycopg.errors.CheckViolation):
                        db.execute("INSERT INTO private_document_objects(id,workspace_id,body,source_sha256,retention_until) VALUES(%s,%s,%s,%s,now()+%s*interval '1 second')", (uuid.uuid4(), WORKSPACE_A, body, digest, seconds))
            with psycopg.connect(seeded, autocommit=True) as db:
                db.execute("UPDATE private_document_objects SET created_at=now()-interval '2 minutes',retention_until=now()-interval '1 minute' WHERE id=%s", (key.rsplit("/", 1)[1],))
            with pytest.raises(ValueError, match="expired"):
                await store.get_private(key)
            await store.delete_private(key)
            await store.delete_private(key)
        finally:
            await engine.dispose()
    asyncio.run(exercise())


def test_private_storage_keys_preserve_backend_across_default_change(seeded, private_postgres, monkeypatch):
    from buyeros_api.api.deps import async_database_url
    from buyeros_api.services.object_store import get_private_store, StoreUnavailable
    from buyeros_api.settings import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine

    async def exercise():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        workspace = uuid.UUID(WORKSPACE_A)
        store = get_private_store(workspace, engine=engine)
        body = b"x" * (5 * 1024 * 1024)
        try:
            key = await store.put_private(body, digest=hashlib.sha256(body).hexdigest(), retention_seconds=60)
            monkeypatch.setenv("BUYEROS_PRIVATE_OBJECT_BACKEND", "r2")
            get_settings.cache_clear()
            selected = get_private_store(workspace, engine=engine, object_key=key)
            assert await selected.get_private(key) == body
            with pytest.raises(StoreUnavailable, match="disabled"):
                get_private_store(workspace, engine=engine)
            for prefix in ("tenants", "r2/tenants"):
                with pytest.raises(StoreUnavailable, match="disabled"):
                    get_private_store(workspace, engine=engine, object_key=f"{prefix}/{workspace}/{uuid.uuid4()}")
            await selected.delete_private(key)
        finally:
            await engine.dispose()
            get_settings.cache_clear()
    asyncio.run(exercise())


def test_native_maintenance_erases_expired_private_bytes_with_epoch_guard(seeded, private_postgres, monkeypatch):
    from buyeros_api.settings import get_settings
    from buyeros_api.services import worker_execution
    parts = urlsplit(seeded)
    worker_dsn = urlunsplit(parts._replace(netloc=f"buyeros_worker:test-only@{parts.hostname}:{parts.port}"))
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL WHERE singleton=1")
        epoch = db.execute("SELECT epoch FROM worker_runtime_control").fetchone()[0]
        for index in range(102):
            workspace = WORKSPACE_A if index % 2 else WORKSPACE_B
            db.execute("INSERT INTO private_document_objects(id,workspace_id,body,source_sha256,created_at,retention_until) VALUES(%s,%s,%s,%s,now()-interval '2 hours',now()+%s*interval '1 hour')", (uuid.uuid4(), workspace, BODY, hashlib.sha256(BODY).hexdigest(), 1 if index == 101 else -1))
    monkeypatch.setenv("BUYEROS_EXECUTION_DATABASE_URL", worker_dsn)
    monkeypatch.setenv("BUYEROS_CLOUDFLARE_EXECUTION_ENABLED", "true")
    get_settings.cache_clear()

    def count():
        with psycopg.connect(seeded) as db:
            return db.execute("SELECT count(*) FROM private_document_objects").fetchone()[0]

    async def exercise():
        engine = worker_execution.create_execution_engine()
        try:
            assert not (await worker_execution.maintenance(engine, epoch - 1)).enabled
            assert count() == 102
            assert (await worker_execution.maintenance(engine, epoch)).enabled
            assert count() == 2, "one native maintenance tick must erase at most 100 expired objects"
            assert (await worker_execution.maintenance(engine, epoch)).enabled
            assert count() == 1, "unexpired private bytes must remain"
        finally:
            await engine.dispose()
    asyncio.run(exercise())
