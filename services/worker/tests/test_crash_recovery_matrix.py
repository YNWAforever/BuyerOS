"""T28 crash windows for durable private-object deletion."""
import uuid
from datetime import datetime, timezone

import psycopg

from buyeros_worker.tasks import execute_intent_sync
from tests.conftest import PROJECT_A, WS_A, reset_tenant, seed_outbox


def test_source_delete_retries_after_object_delete_before_database_finalize(
    worker_database_url, pg_dsn,
):
    source_id = str(uuid.uuid4())
    intent = f"source.delete:{source_id}"
    object_key = f"tenants/{WS_A}/{source_id}"
    objects = {object_key: b"fictional source"}
    attempts = []

    class Store:
        async def delete_private(self, key):
            attempts.append(key)
            objects.pop(key, None)
            if len(attempts) == 1:
                raise RuntimeError("simulated crash after object deletion")

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute(
            """INSERT INTO source_documents
               (id,workspace_id,project_id,canonical_url,digest,storage_mode,
                object_key,excerpt,retention_until,permission_purpose)
               VALUES (%s,%s,%s,%s,%s,'private_object',%s,NULL,now()-interval '1 second',
                       'account_research')""",
            (source_id, WS_A, PROJECT_A, f"https://redacted.invalid/{source_id}",
             "a" * 64, object_key),
        )
        seed_outbox(conn, intent_key=intent, event_type="source.delete",
                    payload={"source_document_id": source_id},
                    state="dispatched", generation=1)
    try:
        first = execute_intent_sync(intent, WS_A, 1, private_store=Store())
        assert first == "storage_unavailable"
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (intent,)).fetchone()[0] == "dispatched"
            assert conn.execute("SELECT object_key FROM source_documents WHERE id=%s", (source_id,)).fetchone()[0] == object_key
        assert execute_intent_sync(intent, WS_A, 1, private_store=Store()) == "done"
        assert execute_intent_sync(intent, WS_A, 1, private_store=Store()) == "duplicate"
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute("SELECT object_key FROM source_documents WHERE id=%s", (source_id,)).fetchone()[0] is None
            assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (intent,)).fetchone()[0] == "done"
        assert objects == {} and attempts == [object_key, object_key]
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (intent,))
            conn.execute("DELETE FROM source_documents WHERE id=%s", (source_id,))

def test_paid_dispatch_kill_keeps_reconciliation_claimable(
    worker_database_url, pg_dsn, monkeypatch,
):
    from buyeros_worker.config import get_settings
    from buyeros_worker.dispatcher import dispatch_once
    from buyeros_worker.engine import create_engine, run_async

    new_key, reconcile_key = f"provider.external:{uuid.uuid4()}", f"provider.reconcile:{uuid.uuid4()}"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_outbox(conn, intent_key=new_key, event_type="provider.external", state="ready")
        seed_outbox(conn, intent_key=reconcile_key, event_type="provider.reconcile", state="ready")
    monkeypatch.setenv("BUYEROS_PAID_DISPATCH_ENABLED", "false")
    get_settings.cache_clear()
    published = []

    async def cycle():
        engine = create_engine()
        try:
            return await dispatch_once(
                engine, published.append, "retention-test",
                datetime.now(timezone.utc), 10, 120,
            )
        finally:
            await engine.dispose()

    try:
        claimed = run_async(cycle())
        assert claimed == [reconcile_key]
        assert [item["intent_key"] for item in published] == [reconcile_key]
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (new_key,)).fetchone()[0] == "ready"
    finally:
        get_settings.cache_clear()
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key IN (%s,%s)", (new_key, reconcile_key))

def test_reconciliation_switch_can_pause_without_releasing_unknown_intent(
    worker_database_url, pg_dsn, monkeypatch,
):
    from buyeros_worker.config import get_settings
    from buyeros_worker.dispatcher import dispatch_once
    from buyeros_worker.engine import create_engine, run_async

    intent = f"provider.reconcile:{uuid.uuid4()}"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_outbox(conn, intent_key=intent, event_type="provider.reconcile", state="ready")
    monkeypatch.setenv("BUYEROS_RECONCILIATION_ENABLED", "false")
    get_settings.cache_clear()
    published = []

    async def cycle():
        engine = create_engine()
        try:
            return await dispatch_once(
                engine, published.append, "retention-test",
                datetime.now(timezone.utc), 10, 120,
            )
        finally:
            await engine.dispose()

    try:
        assert run_async(cycle()) == []
        assert published == []
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (intent,)).fetchone()[0] == "ready"
    finally:
        get_settings.cache_clear()
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (intent,))

def test_paid_switch_blocks_already_published_message_without_settling(
    worker_database_url, pg_dsn, monkeypatch,
):
    from buyeros_worker.config import get_settings

    intent = f"provider.external:{uuid.uuid4()}"
    operation_id = str(uuid.uuid4())
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_outbox(
            conn, intent_key=intent, event_type="provider.external",
            payload={"operation_id": operation_id, "service": "search", "market": "US",
                     "language": "en", "role": "distributor"},
            state="dispatched", generation=1,
        )
    monkeypatch.setenv("BUYEROS_PAID_DISPATCH_ENABLED", "false")
    get_settings.cache_clear()
    try:
        assert execute_intent_sync(
            intent, WS_A, 1, adapter=object(), environment="production",
        ) == "dispatch_disabled"
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (intent,)).fetchone()[0] == "dispatched"
    finally:
        get_settings.cache_clear()
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (intent,))

def test_worker_settings_repr_does_not_disclose_broker_password():
    from buyeros_worker.config import WorkerSettings

    rendered = repr(WorkerSettings(broker_url="redis://:CANARY_BROKER_PASSWORD@localhost:6379/0"))
    assert "CANARY_BROKER_PASSWORD" not in rendered

def test_configured_retention_sweep_tombstones_expired_source_without_object_io(
    worker_database_url, pg_dsn,
):
    from buyeros_worker.engine import create_engine, run_async
    from buyeros_worker.handlers.retention import expire_due_sources

    source_id = str(uuid.uuid4())
    key = f"tenants/{WS_A}/{source_id}"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute(
            """INSERT INTO source_documents
               (id,workspace_id,project_id,canonical_url,digest,storage_mode,
                object_key,excerpt,retention_until,permission_purpose)
               VALUES (%s,%s,%s,%s,%s,'private_object',%s,%s,now()-interval '1 second',
                       'account_research')""",
            (source_id, WS_A, PROJECT_A, f"https://example.invalid/{source_id}",
             "a" * 64, key, "FICTIONAL_PRIVATE_SOURCE"),
        )

    async def sweep():
        engine = create_engine()
        try:
            return await expire_due_sources(
                engine, datetime.now(timezone.utc),
                policy_version="fixture-policy-v1", limit=10,
            )
        finally:
            await engine.dispose()

    try:
        assert run_async(sweep()) == [source_id]
        with psycopg.connect(pg_dsn) as conn:
            source = conn.execute(
                "SELECT excerpt,object_key FROM source_documents WHERE id=%s", (source_id,)
            ).fetchone()
            assert source == (None, key)
            assert conn.execute(
                "SELECT count(*) FROM outbox_events WHERE intent_key=%s",
                (f"source.delete:{source_id}",),
            ).fetchone()[0] == 1
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (f"source.delete:{source_id}",))
            conn.execute("DELETE FROM source_documents WHERE id=%s", (source_id,))


def test_configured_retention_sweep_expires_due_contact(worker_database_url, pg_dsn):
    from buyeros_worker.engine import create_engine, run_async
    from buyeros_worker.handlers.retention import expire_due_contacts

    company_id, contact_id = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
                     "VALUES (%s,%s,'Fictional','Fictional')", (company_id, WS_A))
        conn.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,"
                     "normalized_value,validity,retention_expires_at) VALUES "
                     "(%s,%s,%s,'business_email','CANARY_CONTACT_SWEEP',"
                     "'provider_marked_valid',now()-interval '1 second')",
                     (contact_id, WS_A, company_id))

    async def sweep():
        engine = create_engine()
        try:
            return await expire_due_contacts(
                engine, datetime.now(timezone.utc),
                policy_version="fixture-policy-v1", limit=10,
            )
        finally:
            await engine.dispose()
    try:
        assert run_async(sweep()) == [contact_id]
        with psycopg.connect(pg_dsn) as conn:
            value, validity, quarantined = conn.execute(
                "SELECT normalized_value,validity,quarantined FROM contact_points WHERE id=%s",
                (contact_id,),
            ).fetchone()
            assert "CANARY_CONTACT_SWEEP" not in value
            assert validity == "unavailable" and quarantined is True
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM contact_points WHERE id=%s", (contact_id,))
            conn.execute("DELETE FROM companies WHERE id=%s", (company_id,))


def test_source_delete_uses_checkpoint_worker_role_and_retries_idempotently(
    worker_database_url, pg_dsn, monkeypatch,
):
    from buyeros_worker.config import get_settings
    from tests.conftest import ICP_A

    run_id, source_id, checkpoint_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    thread = f"{WS_A}:{run_id}:fit-v1:1"
    intent = f"source.delete:{source_id}"
    worker_dsn = worker_database_url.replace("buyeros_api:test-only", "buyeros_worker:test-only", 1)
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        conn.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,"
                     "limits,target_companies,raw_result_count) "
                     "VALUES (%s,%s,%s,%s,'completed','{}'::jsonb,1,1)",
                     (run_id, WS_A, PROJECT_A, ICP_A))
        conn.execute("INSERT INTO source_documents(id,workspace_id,project_id,run_id,canonical_url,"
                     "digest,storage_mode,excerpt,retention_until) "
                     "VALUES (%s,%s,%s,%s,%s,%s,'excerpt_only',NULL,now()-interval '1 second')",
                     (source_id, WS_A, PROJECT_A, run_id,
                      f"https://redacted.invalid/{source_id}", "a" * 64))
        seed_outbox(conn, intent_key=intent, event_type="source.delete",
                    payload={"source_document_id": source_id}, state="dispatched", generation=1)
        conn.execute("INSERT INTO buyeros_graph.checkpoints(thread_id,checkpoint_ns,checkpoint_id,"
                     "checkpoint,metadata) VALUES (%s,'',%s,%s::jsonb,'{}'::jsonb)",
                     (thread, checkpoint_id, '{"canary":"SECRET_CHECKPOINT"}'))
        conn.execute("INSERT INTO buyeros_graph.checkpoint_blobs(thread_id,checkpoint_ns,channel,"
                     "version,type,blob) VALUES (%s,'','source','v1','bytes',%s)",
                     (thread, b"SECRET_CHECKPOINT_BLOB"))
        conn.execute("INSERT INTO buyeros_graph.checkpoint_writes(thread_id,checkpoint_ns,"
                     "checkpoint_id,task_id,idx,channel,type,blob,task_path) "
                     "VALUES (%s,'',%s,%s,0,'source','bytes',%s,'')",
                     (thread, checkpoint_id, str(uuid.uuid4()), b"SECRET_CHECKPOINT_WRITE"))
        assert conn.execute("SELECT has_schema_privilege('buyeros_api',"
                            "'buyeros_graph','USAGE')").fetchone()[0] is False
    monkeypatch.delenv("BUYEROS_CHECKPOINT_DATABASE_URL", raising=False)
    get_settings.cache_clear()
    try:
        assert execute_intent_sync(intent, WS_A, 1) == "checkpoint_unavailable"
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                                (intent,)).fetchone()[0] == "dispatched"
            assert conn.execute("SELECT count(*) FROM buyeros_graph.checkpoints WHERE thread_id=%s",
                                (thread,)).fetchone()[0] == 1
        monkeypatch.setenv("BUYEROS_CHECKPOINT_DATABASE_URL", worker_dsn)
        get_settings.cache_clear()
        assert execute_intent_sync(intent, WS_A, 1) == "done"
        assert execute_intent_sync(intent, WS_A, 1) == "duplicate"
        with psycopg.connect(pg_dsn) as conn:
            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                assert conn.execute(
                    f"SELECT count(*) FROM buyeros_graph.{table} WHERE thread_id=%s", (thread,)
                ).fetchone()[0] == 0
            assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                                (intent,)).fetchone()[0] == "done"
    finally:
        get_settings.cache_clear()
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                conn.execute(f"DELETE FROM buyeros_graph.{table} WHERE thread_id=%s", (thread,))
            conn.execute("DELETE FROM outbox_events WHERE intent_key=%s", (intent,))
            conn.execute("DELETE FROM source_documents WHERE id=%s", (source_id,))
            conn.execute("DELETE FROM search_runs WHERE id=%s", (run_id,))
            conn.execute("ALTER ROLE buyeros_worker NOLOGIN")


def test_operational_metrics_are_tenant_scoped_aggregate_only(worker_database_url, pg_dsn):
    from buyeros_worker.engine import create_engine, run_async
    from buyeros_worker.metrics import collect_operational_metrics

    ready, expired, failed = (f"metric:{uuid.uuid4()}" for _ in range(3))
    account_id, operation_id, reservation_id = (str(uuid.uuid4()) for _ in range(3))
    # Other worker suites retain the current monthly account in this shared
    # disposable DB. This aggregate test owns a separate synthetic period.
    metric_period_start = datetime(2030, 1, 1, tzinfo=timezone.utc)
    metric_period_end = datetime(2030, 2, 1, tzinfo=timezone.utc)
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_outbox(conn, intent_key=ready, event_type="source.delete", state="ready",
                    payload={"canary": "PRIVATE_METRIC_PAYLOAD"})
        seed_outbox(conn, intent_key=expired, event_type="provider.reconcile",
                    state="dispatched", generation=1,
                    lease_expires_at=datetime.now(timezone.utc))
        seed_outbox(conn, intent_key=failed, event_type="source.delete", state="failed")
        conn.execute("UPDATE outbox_events SET created_at=now()-interval '5 minutes' "
                     "WHERE intent_key=%s", (ready,))
        conn.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,"
                     "currency,period,period_start,period_end,version,frozen,approved_limit,"
                     "settled_spend) VALUES (%s,%s,'workspace',%s,'all','USD','monthly',"
                     "%s,%s,1,false,1.000000,0.000000)",
                     (account_id, WS_A, WS_A, metric_period_start, metric_period_end))
        conn.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,"
                     "input_hash,status,provider_ref) VALUES "
                     "(%s,%s,%s,'account_search','fixture-hash','unknown','PRIVATE_PROVIDER_REF')",
                     (operation_id, WS_A, f"metric:unknown:{operation_id}"))
        conn.execute("INSERT INTO budget_reservations(id,workspace_id,account_id,operation_id,"
                     "intent_key,price_version,currency,origin_period_start,upper_bound,"
                     "remaining_hold,state) VALUES (%s,%s,%s,%s,%s,'fixture-price-v1','USD',"
                     "%s,0.250000,0.250000,'active')",
                     (reservation_id, WS_A, account_id, operation_id,
                      f"metric:unknown:{operation_id}", metric_period_start))

    async def read(workspace):
        engine = create_engine()
        try:
            return await collect_operational_metrics(engine, uuid.UUID(workspace),
                                                     datetime.now(timezone.utc))
        finally:
            await engine.dispose()
    try:
        own = run_async(read(WS_A))
        other = run_async(read("22222222-2222-4222-8222-222222222222"))
        assert own["ready_intents"] == 1
        assert own["expired_leases"] == 1
        assert own["failed_intents"] == 1
        assert own["oldest_ready_seconds"] >= 299
        assert own["unknown_hold_count"] == 1
        assert own["unknown_hold_usd"] == "0.250000"
        assert other["ready_intents"] == 0
        assert other["unknown_hold_count"] == 0
        assert "PRIVATE_METRIC_PAYLOAD" not in str(own)
        assert "PRIVATE_PROVIDER_REF" not in str(own)
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("DELETE FROM budget_reservations WHERE id=%s", (reservation_id,))
            conn.execute("DELETE FROM provider_operations WHERE id=%s", (operation_id,))
            conn.execute("DELETE FROM budget_accounts WHERE id=%s", (account_id,))
            conn.execute("DELETE FROM outbox_events WHERE intent_key IN (%s,%s,%s)",
                         (ready, expired, failed))
