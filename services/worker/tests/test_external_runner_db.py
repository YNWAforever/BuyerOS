"""T15: provider transport starts only after a committed bounded intent."""
import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg

from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import Money, ProviderCapability, ProviderIntent, FixtureProviderAdapter
from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
from buyeros_worker.engine import create_engine
from buyeros_worker.external_runner import execute_external, input_digest, reconcile_intent_key
from buyeros_worker.tasks import execute_intent_sync
from tests.conftest import PROJECT_A, WS_A, reset_tenant, seed_outbox


def _capability():
    return ProviderCapability(
        provider="fixture", adapter_version="fixture-v1", service="contact",
        markets=frozenset({"HK"}), languages=frozenset({"en"}),
        roles=frozenset({"company"}), auth_model="test-only",
        pricing_version="fixture-price-v1", max_liability=Money(Decimal("1.000000")),
        idempotency="verified", status="verified", callback="unsupported",
        cancel="unsupported", retention="test-only",
        verified_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        source_urls=("https://example.test/fixture",),
    )


def _setup(pg_dsn, intent, operation_id):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        conn.execute("DELETE FROM provider_callback_routes WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM provider_operations WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM budget_reservation_allocations WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM cost_events WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM budget_reservations WHERE workspace_id=%s", (WS_A,))
        conn.execute("DELETE FROM budget_accounts WHERE workspace_id=%s", (WS_A,))
    async def reserve():
        engine = create_engine()
        try:
            async with tenant_session(engine, uuid.UUID(WS_A)) as session:
                await ensure_period_accounts(session, uuid.UUID(WS_A), uuid.UUID(PROJECT_A),
                                             None, "contact_lookup")
            with psycopg.connect(pg_dsn, autocommit=True) as conn:
                conn.execute("UPDATE budget_accounts SET approved_limit=2 WHERE workspace_id=%s", (WS_A,))
            async with tenant_session(engine, uuid.UUID(WS_A)) as session:
                await reserve_operation(session, operation_id,
                                        {"workspace_id": uuid.UUID(WS_A),
                                         "project_id": uuid.UUID(PROJECT_A), "category": "contact_lookup"},
                                        Decimal("1.000000"), "USD", "fixture-price-v1")
        finally:
            await engine.dispose()
    asyncio.run(reserve())
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status)"
            " VALUES (%s,%s,%s,'contact',%s,'reserved')",
            (operation_id, WS_A, intent.key, input_digest(intent)),
        )
        seed_outbox(conn, intent_key=intent.key, event_type="provider.external",
                    payload={"operation_id": str(operation_id), "service": intent.service,
                             "market": intent.market, "language": intent.language, "role": intent.role},
                    workspace_id=WS_A, state="dispatched", generation=1)


def test_external_network_has_no_open_db_lock_and_timeout_retains_hold(worker_database_url, pg_dsn):
    intent = ProviderIntent("contact:fixture-1", "contact", "HK", "en", "company")
    operation_id = uuid.uuid4()
    _setup(pg_dsn, intent, operation_id)

    class CheckingAdapter(FixtureProviderAdapter):
        async def submit(self, request):
            with psycopg.connect(pg_dsn, autocommit=True) as conn:
                assert conn.execute("SELECT status FROM provider_operations WHERE id=%s",
                                    (operation_id,)).fetchone()[0] == "submitting"
                conn.execute("SELECT id FROM provider_operations WHERE id=%s FOR UPDATE NOWAIT",
                             (operation_id,))
            return await super().submit(request)

    adapter = CheckingAdapter(_capability(), environment="test",
                              outcome="timeout_after_acceptance")
    async def run():
        engine = create_engine()
        try:
            return await execute_external(engine, uuid.UUID(WS_A), operation_id, 1,
                                          adapter, intent, environment="test")
        finally:
            await engine.dispose()
    assert asyncio.run(run()) == "unknown"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (intent.key,)).fetchone()[0] == "done"
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (reconcile_intent_key(operation_id),)).fetchone()[0] == "ready"
        conn.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1"
                     " WHERE intent_key=%s", (reconcile_intent_key(operation_id),))
        conn.execute("UPDATE provider_operations SET cancel_requested=true WHERE id=%s",
                     (operation_id,))
    from dataclasses import replace
    adapter.capability = replace(adapter.capability, pricing_version="fixture-price-v2")
    async def reconcile():
        engine = create_engine()
        try:
            return await execute_external(engine, uuid.UUID(WS_A), operation_id, 1,
                                          adapter, intent, environment="test",
                                          outbox_intent_key=reconcile_intent_key(operation_id))
        finally:
            await engine.dispose()
    assert asyncio.run(reconcile()) == "unknown"
    assert adapter.submit_count == 1
    with psycopg.connect(pg_dsn) as conn:
        assert conn.execute("SELECT status FROM provider_operations WHERE id=%s",
                            (operation_id,)).fetchone()[0] == "unknown"
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (reconcile_intent_key(operation_id),)).fetchone()[0] == "dispatched"
        assert conn.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s",
                            (operation_id,)).fetchone() == ("active", Decimal("1.000000"))


def test_stale_generation_cannot_finalize_after_provider_acceptance(worker_database_url, pg_dsn):
    intent = ProviderIntent("contact:fixture-stale", "contact", "HK", "en", "company")
    operation_id = uuid.uuid4()
    _setup(pg_dsn, intent, operation_id)

    class RacingAdapter(FixtureProviderAdapter):
        async def submit(self, request):
            result = await super().submit(request)
            with psycopg.connect(pg_dsn, autocommit=True) as conn:
                conn.execute("UPDATE outbox_events SET fencing_generation=2 WHERE intent_key=%s",
                             (intent.key,))
            return result

    adapter = RacingAdapter(_capability(), environment="test")
    async def run(generation):
        engine = create_engine()
        try:
            return await execute_external(engine, uuid.UUID(WS_A), operation_id,
                                          generation, adapter, intent, environment="test")
        finally:
            await engine.dispose()
    assert asyncio.run(run(1)) == "stale"
    assert asyncio.run(run(2)) == "unknown"
    assert adapter.submit_count == 1
    with psycopg.connect(pg_dsn) as conn:
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (intent.key,)).fetchone()[0] == "done"
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (reconcile_intent_key(operation_id),)).fetchone()[0] == "ready"
        assert conn.execute("SELECT state FROM budget_reservations WHERE operation_id=%s",
                            (operation_id,)).fetchone()[0] == "active"


def test_changed_price_or_cancel_flag_blocks_call_and_keeps_hold(worker_database_url, pg_dsn):
    from dataclasses import replace

    intent = ProviderIntent("contact:fixture-blocked", "contact", "HK", "en", "company")
    operation_id = uuid.uuid4()
    _setup(pg_dsn, intent, operation_id)

    async def run(adapter):
        engine = create_engine()
        try:
            return await execute_external(engine, uuid.UUID(WS_A), operation_id, 1,
                                          adapter, intent, environment="test")
        finally:
            await engine.dispose()

    changed_price = FixtureProviderAdapter(
        replace(_capability(), pricing_version="fixture-price-v2"), environment="test")
    assert asyncio.run(run(changed_price)) == "blocked"
    assert changed_price.submit_count == 0
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("UPDATE provider_operations SET cancel_requested=true WHERE id=%s",
                     (operation_id,))
    adapter = FixtureProviderAdapter(_capability(), environment="test")
    assert asyncio.run(run(adapter)) == "blocked"
    assert adapter.submit_count == 0
    with psycopg.connect(pg_dsn) as conn:
        assert conn.execute("SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s",
                            (operation_id,)).fetchone()[0] == Decimal("1.000000")


def test_foreign_workspace_message_cannot_submit(worker_database_url, pg_dsn):
    from tests.conftest import WS_B

    intent = ProviderIntent("contact:fixture-foreign", "contact", "HK", "en", "company")
    operation_id = uuid.uuid4()
    _setup(pg_dsn, intent, operation_id)
    adapter = FixtureProviderAdapter(_capability(), environment="test")
    async def run():
        engine = create_engine()
        try:
            return await execute_external(engine, uuid.UUID(WS_B), operation_id, 1,
                                          adapter, intent, environment="test")
        finally:
            await engine.dispose()
    assert asyncio.run(run()) == "stale"
    assert adapter.submit_count == 0


def test_celery_entry_routes_provider_and_reconciliation_without_resubmit(worker_database_url, pg_dsn):
    intent = ProviderIntent("contact:fixture-route", "contact", "HK", "en", "company")
    operation_id = uuid.uuid4()
    _setup(pg_dsn, intent, operation_id)
    adapter = FixtureProviderAdapter(_capability(), environment="test",
                                     outcome="timeout_after_acceptance")

    assert execute_intent_sync(intent.key, WS_A, 1, adapter=adapter,
                               environment="test") == "unknown"
    assert adapter.submit_count == 1
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (intent.key,)).fetchone()[0] == "done"
        key = reconcile_intent_key(operation_id)
        conn.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1"
                     " WHERE intent_key=%s", (key,))
    assert execute_intent_sync(key, WS_A, 1, adapter=adapter,
                               environment="test") == "unknown"
    assert adapter.submit_count == 1
    adapter.resolve(f"fixture:{__import__('hashlib').sha256(intent.key.encode()).hexdigest()[:24]}",
                    "succeeded")
    assert execute_intent_sync(key, WS_A, 1, adapter=adapter,
                               environment="test") == "succeeded"
    with psycopg.connect(pg_dsn) as conn:
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (key,)).fetchone()[0] == "done"
        assert conn.execute("SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s",
                            (operation_id,)).fetchone()[0] == Decimal("1.000000")
