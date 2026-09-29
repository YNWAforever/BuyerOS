"""T23: fixture-only contact dispatch uses the job hold and never blind-resubmits."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest

from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import FixtureProviderAdapter, Money, ProviderCapability
from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
from buyeros_api.services.quote_service import quote_hash
from buyeros_worker.engine import create_engine
from buyeros_worker.tasks import execute_intent_sync
from tests.conftest import PROJECT_A, WS_A, reset_tenant, seed_outbox


@pytest.fixture
def worker_database_url(migrated, monkeypatch):
    """Run this contact suite as the real worker role, on disposable Postgres."""
    from buyeros_api.settings import get_settings

    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only-worker'")
    worker_dsn = migrated.replace("buyeros:buyeros@", "buyeros_worker:test-only-worker@", 1)
    monkeypatch.setenv("BUYEROS_DATABASE_URL", worker_dsn)
    get_settings.cache_clear()
    yield worker_dsn
    get_settings.cache_clear()


def _capability():
    return ProviderCapability(
        provider="fixture", adapter_version="contact-fixture-v1", service="contact",
        markets=frozenset({"US"}), languages=frozenset({"en"}),
        roles=frozenset({"Procurement manager"}), auth_model="fixture",
        pricing_version="fixture-price-v1", max_liability=Money(Decimal("0.300000")),
        idempotency="verified", status="verified", callback="unsupported",
        cancel="unsupported", retention="fixture-only",
        verified_at=datetime.now(timezone.utc),
        source_urls=("https://fixture.invalid/capability",),
    )


def _setup(pg_dsn, count=1):
    job_id, quote_id = uuid.uuid4(), uuid.uuid4()
    buyers = [(uuid.uuid4(), uuid.uuid4(), uuid.uuid4()) for _ in range(count)]
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        reset_tenant(db)
        for table in ("provider_callback_routes", "provider_events", "async_jobs", "provider_operations", "enrichment_jobs",
                      "budget_reservation_allocations", "cost_events", "budget_reservations",
                      "budget_accounts", "enrichment_quotes", "policy_decisions", "project_buyers", "companies"):
            db.execute(f"DELETE FROM {table} WHERE workspace_id=%s", (WS_A,))
        for ordinal, (buyer_id, company_id, _) in enumerate(buyers):
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) "
                       "VALUES (%s,%s,%s,%s,%s)",
                       (company_id, WS_A, f"Fixture {ordinal}", f"Fixture {ordinal}", f"fixture{ordinal}.example"))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
                       (buyer_id, WS_A, PROJECT_A, company_id))
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,"
                   "policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) "
                   "VALUES (%s,%s,'project',%s,%s,'contact_research','permitted','fixture-v1','fixture','fixture',"
                   "'{US}',now()+interval '1 day',1,%s)",
                   (uuid.uuid4(), WS_A, PROJECT_A, WS_A, uuid.uuid4()))
    maximum = Decimal("0.300000") * count
    async def reserve():
        engine = create_engine()
        try:
            async with tenant_session(engine, uuid.UUID(WS_A)) as session:
                await ensure_period_accounts(session, uuid.UUID(WS_A), uuid.UUID(PROJECT_A),
                                             None, "contact_lookup")
            with psycopg.connect(pg_dsn, autocommit=True) as db:
                db.execute("UPDATE budget_accounts SET approved_limit=1 WHERE workspace_id=%s", (WS_A,))
            async with tenant_session(engine, uuid.UUID(WS_A)) as session:
                return await reserve_operation(session, job_id,
                    {"workspace_id": uuid.UUID(WS_A), "project_id": uuid.UUID(PROJECT_A),
                     "category": "contact_lookup"}, maximum, "USD", "fixture-price-v1")
        finally:
            await engine.dispose()
    reservation_id = asyncio.run(reserve())
    resolved = [{"buyer_id": str(buyer_id), "buyer_version": 1,
                 "company_id": str(company_id), "eligible": True}
                for buyer_id, company_id, _ in buyers]
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        db.execute("INSERT INTO enrichment_quotes(id,workspace_id,project_id,purpose,selection,request_hash,"
                   "quote_hash,price_version,max_cost,status,adapter_version,roles,eligibility,contact_type) "
                   "VALUES (%s,%s,%s,'contact_research',%s::jsonb,%s,%s,'fixture-price-v1',%s,"
                   "'consumed','contact-fixture-v1',%s::jsonb,%s::jsonb,'business_email')",
                   (quote_id, WS_A, PROJECT_A, json.dumps({"resolved": resolved}),
                    "a" * 64, "b" * 64, maximum, json.dumps(["Procurement manager"]),
                    json.dumps([{"buyer_id": row["buyer_id"], "eligible": True} for row in resolved])))
        db.execute("INSERT INTO enrichment_jobs(id,workspace_id,quote_id,reservation_id,state) "
                   "VALUES (%s,%s,%s,%s,'reserved')", (job_id, WS_A, quote_id, reservation_id))
        for buyer_id, _, operation_id in buyers:
            intent_key = f"contact:{job_id}:{buyer_id}"
            db.execute("INSERT INTO provider_operations(id,workspace_id,job_id,buyer_id,intent_key,capability,input_hash,status) "
                       "VALUES (%s,%s,%s,%s,%s,'contact',%s,'intent')",
                       (operation_id, WS_A, job_id, buyer_id, intent_key, quote_hash({
                           "quote_hash": "b" * 64, "buyer_id": str(buyer_id),
                           "roles": ["Procurement manager"], "contact_type": "business_email"})))
        seed_outbox(db, intent_key=f"contact.lookup:{job_id}", event_type="contact.lookup",
                    payload={"workspace_id": WS_A, "job_id": str(job_id)},
                    workspace_id=WS_A, state="dispatched", generation=1)
    return job_id, buyers[0][2]


def test_timeout_after_acceptance_retains_shared_hold_and_never_resubmits(worker_database_url, pg_dsn):
    job_id, operation_id = _setup(pg_dsn)
    adapter = FixtureProviderAdapter(_capability(), environment="test", outcome="timeout_after_acceptance")
    key = f"contact.lookup:{job_id}"
    assert execute_intent_sync(key, WS_A, 1, adapter=adapter, environment="test") == "unknown"
    assert execute_intent_sync(key, WS_A, 1, adapter=adapter, environment="test") in {"duplicate", "unknown"}
    assert adapter.submit_count == 1
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT status FROM provider_operations WHERE id=%s", (operation_id,)).fetchone()[0] == "unknown"
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s",
                          (job_id,)).fetchone() == ("active", Decimal("0.300000"))


def test_worker_crash_after_provider_acceptance_recovers_as_unknown_without_resubmit(worker_database_url, pg_dsn):
    job_id, operation_id = _setup(pg_dsn)

    class CrashAfterAcceptance(FixtureProviderAdapter):
        async def submit(self, intent):
            await super().submit(intent)
            raise SystemExit("fixture worker crash after provider acceptance")

    adapter = CrashAfterAcceptance(_capability(), environment="test")
    with pytest.raises(SystemExit, match="fixture worker crash"):
        execute_intent_sync(f"contact.lookup:{job_id}", WS_A, 1,
                            adapter=adapter, environment="test")
    assert adapter.submit_count == 1
    assert execute_intent_sync(f"contact.lookup:{job_id}", WS_A, 1,
                               adapter=adapter, environment="test") == "unknown"
    assert adapter.submit_count == 1
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT status,provider_ref FROM provider_operations WHERE id=%s",
                          (operation_id,)).fetchone() == ("unknown", None)
        assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s",
                          (job_id,)).fetchone()[0] == Decimal("0.300000")


def test_late_suppression_prevents_dispatch_and_releases_unsubmitted_hold(worker_database_url, pg_dsn):
    job_id, operation_id = _setup(pg_dsn)
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        company_id = db.execute("SELECT company_id FROM project_buyers WHERE id=(SELECT buyer_id "
                                "FROM provider_operations WHERE id=%s)", (operation_id,)).fetchone()[0]
        db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,"
                   "controller_scope_id,purpose,purposes,reason,active,actor_id) "
                   "VALUES (%s,%s,%s,'company',%s,%s,'contact_research',ARRAY['contact_research'],"
                   "'Fixture late suppression',true,%s)",
                   (uuid.uuid4(), WS_A, "f" * 64, company_id, WS_A, uuid.uuid4()))
    adapter = FixtureProviderAdapter(_capability(), environment="test")
    assert execute_intent_sync(f"contact.lookup:{job_id}", WS_A, 1,
                               adapter=adapter, environment="test") == "policy_blocked"
    assert adapter.submit_count == 0
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT status FROM provider_operations WHERE id=%s",
                          (operation_id,)).fetchone()[0] == "cancelled"
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s",
                          (job_id,)).fetchone() == ("released", Decimal("0.000000"))


def test_verified_status_settles_once_and_releases_unused_shared_bound(worker_database_url, pg_dsn):
    job_id, operation_id = _setup(pg_dsn)
    adapter = FixtureProviderAdapter(_capability(), environment="test")
    assert execute_intent_sync(f"contact.lookup:{job_id}", WS_A, 1,
                               adapter=adapter, environment="test") == "accepted"
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        ref = db.execute("SELECT provider_ref FROM provider_operations WHERE id=%s",
                         (operation_id,)).fetchone()[0]
        assert ref
        key = f"contact.reconcile:{operation_id}"
        assert db.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                          (key,)).fetchone()[0] == "ready"
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 "
                   "WHERE intent_key=%s", (key,))
    adapter.resolve(ref, "not_found", observed_usage=Decimal("0.100000"))
    assert execute_intent_sync(key, WS_A, 1, adapter=adapter, environment="test") == "reconciled"
    assert adapter.submit_count == 1
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s",
                          (job_id,)).fetchone() == ("settled", Decimal("0.000000"))
        assert db.execute("SELECT amount FROM cost_events WHERE operation_id=%s",
                          (job_id,)).fetchall() == [(Decimal("0.100000"),)]
        assert db.execute("SELECT state FROM enrichment_jobs WHERE id=%s",
                          (job_id,)).fetchone()[0] == "reconciled"


def test_suppression_after_submit_quarantines_late_result_but_settles_proven_charge(worker_database_url, pg_dsn):
    job_id, operation_id = _setup(pg_dsn)
    adapter = FixtureProviderAdapter(_capability(), environment="test")
    assert execute_intent_sync(f"contact.lookup:{job_id}", WS_A, 1,
                               adapter=adapter, environment="test") == "accepted"
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        ref, company_id = db.execute(
            "SELECT p.provider_ref,b.company_id FROM provider_operations p "
            "JOIN project_buyers b ON b.id=p.buyer_id WHERE p.id=%s",
            (operation_id,)).fetchone()
        db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,"
                   "controller_scope_id,purpose,purposes,reason,active,actor_id) "
                   "VALUES (%s,%s,%s,'company',%s,%s,'contact_research',ARRAY['contact_research'],"
                   "'Fixture late suppression',true,%s)",
                   (uuid.uuid4(), WS_A, "e" * 64, company_id, WS_A, uuid.uuid4()))
        key = f"contact.reconcile:{operation_id}"
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 "
                   "WHERE intent_key=%s", (key,))
    adapter.resolve(ref, "succeeded", observed_usage=Decimal("0.300000"))
    assert execute_intent_sync(key, WS_A, 1, adapter=adapter, environment="test") == "reconciled"
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT processing_state FROM provider_events WHERE operation_id=%s",
                          (operation_id,)).fetchone()[0] == "quarantined"
        assert db.execute("SELECT amount FROM cost_events WHERE operation_id=%s",
                          (job_id,)).fetchone()[0] == Decimal("0.300000")
        assert db.execute("SELECT count(*) FROM contact_points WHERE workspace_id=%s",
                          (WS_A,)).fetchone()[0] == 0


def test_manual_reconcile_status_event_completes_tracking_job_without_submit(worker_database_url, pg_dsn):
    job_id, operation_id = _setup(pg_dsn)
    adapter = FixtureProviderAdapter(_capability(), environment="test")
    assert execute_intent_sync(f"contact.lookup:{job_id}", WS_A, 1,
                               adapter=adapter, environment="test") == "accepted"
    tracking_id, actor_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        ref = db.execute("SELECT provider_ref FROM provider_operations WHERE id=%s",
                         (operation_id,)).fetchone()[0]
        db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,'fixture-worker',%s)",
                   (actor_id, f"actor-{actor_id}"))
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,"
                   "command,status,requested,processed,updated,unchanged,blocked,conflicts) "
                   "VALUES (%s,%s,%s,%s,'reconciliation','reconcileEnrichmentJob',%s::jsonb,"
                   "'queued',1,0,0,0,0,0)",
                   (tracking_id, WS_A, PROJECT_A, actor_id,
                    json.dumps({"enrichment_job_id": str(job_id)})))
        key = f"contact.reconcile:{operation_id}:manual:{tracking_id}"
        seed_outbox(db, intent_key=key, event_type="contact.reconcile",
                    payload={"workspace_id": WS_A, "job_id": str(job_id),
                             "operation_id": str(operation_id), "async_job_id": str(tracking_id)},
                    workspace_id=WS_A, state="dispatched", generation=1)
    adapter.resolve(ref, "not_found", observed_usage=Decimal("0.200000"))
    assert execute_intent_sync(key, WS_A, 1, adapter=adapter, environment="test") == "reconciled"
    assert adapter.submit_count == 1
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT status,processed,updated FROM async_jobs WHERE id=%s",
                          (tracking_id,)).fetchone() == ("completed", 1, 1)


def test_two_intents_share_one_hold_until_both_costs_are_authoritative(worker_database_url, pg_dsn):
    job_id, _ = _setup(pg_dsn, count=2)

    class MixedAdapter(FixtureProviderAdapter):
        async def submit(self, intent):
            self.outcome = "accepted" if self.submit_count == 0 else "timeout_after_acceptance"
            return await super().submit(intent)

    adapter = MixedAdapter(_capability(), environment="test")
    assert execute_intent_sync(f"contact.lookup:{job_id}", WS_A, 1,
                               adapter=adapter, environment="test") == "unknown"
    assert adapter.submit_count == 2
    with psycopg.connect(pg_dsn, autocommit=True) as db:
        operations = db.execute("SELECT id,provider_ref,status FROM provider_operations "
                                "WHERE job_id=%s ORDER BY id", (job_id,)).fetchall()
        assert {row[2] for row in operations} == {"accepted", "unknown"}
        assert db.execute("SELECT count(*),max(remaining_hold) FROM budget_reservations "
                          "WHERE operation_id=%s", (job_id,)).fetchone() == (1, Decimal("0.600000"))
        for operation_id, _, _ in operations:
            db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 "
                       "WHERE intent_key=%s", (f"contact.reconcile:{operation_id}",))
    first, second = operations
    adapter.resolve(first[1], "not_found", observed_usage=Decimal("0.100000"))
    adapter.resolve(second[1], "not_found", observed_usage=Decimal("0.200000"))
    assert execute_intent_sync(f"contact.reconcile:{first[0]}", WS_A, 1,
                               adapter=adapter, environment="test") == "reconciled"
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s",
                          (job_id,)).fetchone() == ("active", Decimal("0.600000"))
        assert db.execute("SELECT count(*) FROM cost_events WHERE operation_id=%s",
                          (job_id,)).fetchone()[0] == 0
    assert execute_intent_sync(f"contact.reconcile:{second[0]}", WS_A, 1,
                               adapter=adapter, environment="test") == "reconciled"
    with psycopg.connect(pg_dsn) as db:
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s",
                          (job_id,)).fetchone() == ("settled", Decimal("0.000000"))
        assert db.execute("SELECT amount FROM cost_events WHERE operation_id=%s",
                          (job_id,)).fetchall() == [(Decimal("0.300000"),)]
