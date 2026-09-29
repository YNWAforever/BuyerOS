"""T18 fixture discovery uses durable intent, reservation and evidence handoff."""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.db.icp import canonical_hash
from buyeros_api.services.budget_service import _period
from buyeros_worker.discovery_runner import DiscoveryBatch, execute_discovery, execute_discovery_reconcile

WS_A = "18181818-1818-4818-8818-181818181818"
PROJECT_A = "a1800000-0000-4800-8800-000000000018"
ICP_A = "b1800000-0000-4800-8800-000000000018"
QUERY_ID = "a" * 24
RUN_ID = "d0000000-0000-4000-8000-000000000018"
ACTOR_ID = "e0000000-0000-4000-8000-000000000018"
INTENT = "job:discover-t18-fixture"
LIMITS = {"query_rounds": 3, "max_queries_per_run": 12, "max_results": 300,
          "max_pages": 200, "max_page_bytes": 2097152,
          "max_duration_seconds": 1800, "max_model_tokens": 100000,
          "provider_concurrency": 4}


class SearchFixture:
    test_only = True
    provider = "fixture"
    price_version = "fixture-price-v1"
    quoted_upper_bound = Decimal("0.100000")
    retention_seconds = 86400

    def __init__(self, dsn, *, timeout=False):
        self.dsn = dsn
        self.timeout = timeout
        self.calls = 0
        self.status_calls = 0
        self._accepted = {}

    async def search(self, query, *, market, language, limit, intent_key):
        self.calls += 1
        assert market == "US" and language == "en" and limit <= 300
        assert intent_key == f"research:{RUN_ID}:{QUERY_ID}"
        # The provider await must not retain the run row's DB lock.
        with psycopg.connect(self.dsn, autocommit=True) as db:
            with db.transaction():
                db.execute("SELECT id FROM search_runs WHERE id=%s FOR UPDATE NOWAIT", (RUN_ID,))
                usage, first = db.execute(
                    "SELECT usage_counters,first_dispatch_at FROM search_runs WHERE id=%s", (RUN_ID,)
                ).fetchone()
                assert usage["in_flight"] == 1 and first is not None
        batch = DiscoveryBatch(
            hits=[{"url": "https://example.org/acme", "legal_name": "Acme GmbH",
                   "registry_id": "DE-HRB-123", "excerpt": "Acme GmbH distributes industrial sensors.",
                   "language": "en", "external_ref": "fixture-acme"}],
            charge=Decimal("0.050000"), billing_event_id=f"fixture-bill:{intent_key}",
        )
        self._accepted[intent_key] = batch
        if self.timeout:
            raise TimeoutError("synthetic timeout after possible acceptance")
        return batch

    async def status(self, intent_key):
        self.status_calls += 1
        return self._accepted.get(intent_key)


@pytest.fixture
def discovery_case(migrated, worker_database_url, request):
    """Own one T18/T19 fixture namespace and clean it even on setup failure."""
    def cleanup():
        with psycopg.connect(migrated, autocommit=True) as db:
            for table in ("evidence", "human_reviews", "fit_assessments", "company_aliases",
                          "raw_candidates", "project_buyers", "companies", "source_documents",
                          "cost_events", "budget_reservation_allocations", "budget_reservations",
                          "budget_accounts", "provider_operations", "run_events", "outbox_events",
                          "search_runs", "policy_decisions"):
                db.execute(f"DELETE FROM {table} WHERE workspace_id=%s", (WS_A,))
            db.execute("UPDATE projects SET active_icp_version_id=NULL WHERE id=%s", (PROJECT_A,))
            db.execute("DELETE FROM icp_versions WHERE workspace_id=%s", (WS_A,))
            db.execute("DELETE FROM projects WHERE workspace_id=%s", (WS_A,))
            db.execute("DELETE FROM memberships WHERE user_id=%s", (ACTOR_ID,))
            db.execute("DELETE FROM users WHERE id=%s", (ACTOR_ID,))
            db.execute("DELETE FROM workspaces WHERE id=%s", (WS_A,))
    request.addfinalizer(cleanup)

    content = {"markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"],
               "requirements": [{"id": "f0000000-0000-4000-8000-000000000018",
                                 "category": "must", "hard_exclusion": False,
                                 "text": "industrial sensors"}]}
    plan = {"schema": "query-plan.v1", "queries": [{"id": QUERY_ID,
            "query": '"industrial sensors" distributor', "market": "US", "language": "en",
            "role": "distributor", "requirement_id": content["requirements"][0]["id"],
            "round": 1, "filters": {"market": "US", "language": "en"}}],
            "rationale_summary": "fixture"}
    snapshot = {"icp_content_hash": canonical_hash(content), "icp_number": 1,
                "offer_revision": 1, "actor_id": ACTOR_ID,
                "capability": {"provider": "fixture", "price_version": "fixture-price-v1",
                               "verified_filters": ["market", "language"],
                               "markets": ["US"], "languages": ["en"]},
                "query_plan": plan}
    start, end, period = _period(None)
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'T18 discovery fixture','live')", (WS_A,))
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,"
                   "language_preferences,version,offer_revision) VALUES "
                   "(%s,%s,'T18 project','T18 company','industrial sensors','{US}','{en}',1,1)",
                   (PROJECT_A, WS_A))
        db.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,'https://fixture.test/','worker-actor')", (ACTOR_ID,))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) "
                   "VALUES (%s,%s,%s,'{operator}',true)", (uuid.uuid4(), WS_A, ACTOR_ID))
        db.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,"
                   "basis_offer_revision,approved_at,approved_by) "
                   "VALUES (%s,%s,%s,1,%s::jsonb,%s,1,now(),%s)",
                   (ICP_A, WS_A, PROJECT_A, json.dumps(content), canonical_hash(content), ACTOR_ID))
        db.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (ICP_A, PROJECT_A))
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
                   "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) "
                   "VALUES (%s,%s,'project',%s,%s,'account_research','permitted','fixture-v1','fixture','fixture',"
                   "'{US}',now()+interval '1 day',1,%s)",
                   (uuid.uuid4(), WS_A, PROJECT_A, WS_A, ACTOR_ID))
        db.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,"
                   "target_companies,max_cost,execution_snapshot,usage_counters) "
                   "VALUES (%s,%s,%s,%s,'queued',%s::jsonb,24,2,%s::jsonb,'{}'::jsonb)",
                   (RUN_ID, WS_A, PROJECT_A, ICP_A, json.dumps(LIMITS), json.dumps(snapshot)))
        db.execute("INSERT INTO run_events(id,workspace_id,run_id,sequence,event_type,payload) "
                   "VALUES (%s,%s,%s,1,'run.queued','{}'::jsonb)", (uuid.uuid4(), WS_A, RUN_ID))
        for scope, scope_id, category in (("workspace", WS_A, "all"),
                                           ("project", PROJECT_A, "all"),
                                           ("run", RUN_ID, "all"),
                                           ("category", PROJECT_A, "discovery")):
            db.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,"
                       "period,period_start,period_end,approved_limit,settled_spend) "
                       "VALUES (%s,%s,%s,%s,%s,'USD',%s,%s,%s,2,0)",
                       (uuid.uuid4(), WS_A, scope, scope_id, category, period, start, end))
        db.execute("INSERT INTO outbox_events(id,workspace_id,intent_key,event_type,payload,state,fencing_generation) "
                   "VALUES (%s,%s,%s,'run.discover',%s::jsonb,'dispatched',1)",
                   (uuid.uuid4(), WS_A, INTENT, json.dumps({"run_id": RUN_ID})))
    return migrated, worker_database_url


def _execute(dsn, adapter, intent=INTENT):
    async def run():
        engine = create_async_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            return await execute_discovery(engine, uuid.UUID(WS_A), intent, 1,
                                           adapter=adapter, environment="test")
        finally:
            await engine.dispose()
    return asyncio.run(run())


def _reconcile(dsn, adapter, intent):
    async def run():
        engine = create_async_engine(dsn.replace("postgresql://", "postgresql+psycopg://", 1))
        try:
            return await execute_discovery_reconcile(engine, uuid.UUID(WS_A), intent, 1,
                                                     adapter=adapter, environment="test")
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_fixture_search_persists_cited_buyer_and_settles_bounded_cost(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    adapter = SearchFixture(owner_dsn)
    assert _execute(runtime_dsn, adapter) == "done"
    assert adapter.calls == 1
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT count(*) FROM raw_candidates WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM project_buyers WHERE project_id=%s", (PROJECT_A,)).fetchone()[0] == 1
        state, counters, first = db.execute(
            "SELECT status,usage_counters,first_dispatch_at FROM search_runs WHERE id=%s", (RUN_ID,)
        ).fetchone()
        assert state == "running" and counters["queries"] == 1
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='run.fit' "
                          "AND state='ready' AND workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert counters["raw_results"] == 1 and counters["in_flight"] == 0 and first is not None
        assert db.execute("SELECT amount FROM cost_events WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.050000")
        assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.000000")


def test_timeout_retains_hold_and_never_blindly_resubmits(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    adapter = SearchFixture(owner_dsn, timeout=True)
    assert _execute(runtime_dsn, adapter) == "unknown"
    assert adapter.calls == 1
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.100000")
        assert db.execute("SELECT usage_counters FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0]["pages"] == 1
        assert db.execute("SELECT count(*) FROM raw_candidates WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 0
    assert _execute(runtime_dsn, adapter) in {"duplicate", "unknown", "stale"}
    assert adapter.calls == 1
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        reconcile = db.execute("SELECT intent_key FROM outbox_events WHERE workspace_id=%s "
                               "AND event_type='research.reconcile' AND state='ready'", (WS_A,)).fetchone()
        assert reconcile is not None
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 "
                   "WHERE workspace_id=%s AND intent_key=%s", (WS_A, reconcile[0]))
    from buyeros_worker.tasks import execute_intent_sync
    assert execute_intent_sync(reconcile[0], WS_A, 1, search_adapter=adapter, environment="test") == "done"
    assert adapter.calls == 1 and adapter.status_calls == 1
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.000000")
        assert db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 1
        state, counters = db.execute("SELECT status,usage_counters FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()
        assert state == "running" and counters["in_flight"] == 0
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='run.fit' "
                          "AND state='ready' AND workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s "
                          "AND status='settled'", (WS_A,)).fetchone()[0] == 1


def test_worker_entrypoint_uses_fixture_runner_only_with_explicit_test_adapter(discovery_case):
    from buyeros_worker.tasks import execute_intent_sync

    owner_dsn, _ = discovery_case
    adapter = SearchFixture(owner_dsn)
    assert execute_intent_sync(INTENT, WS_A, 1, search_adapter=adapter, environment="test") == "done"
    assert adapter.calls == 1
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 1


def test_zero_budget_pauses_before_adapter_call(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET approved_limit=0 WHERE workspace_id=%s", (WS_A,))
    adapter = SearchFixture(owner_dsn)
    assert _execute(runtime_dsn, adapter) == "paused_budget"
    assert adapter.calls == 0
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT status FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0] == "paused_budget"
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 0


def test_policy_revoke_during_search_keeps_cost_but_blocks_evidence(discovery_case):
    owner_dsn, runtime_dsn = discovery_case

    class RevokingFixture(SearchFixture):
        async def search(self, *args, **kwargs):
            batch = await super().search(*args, **kwargs)
            with psycopg.connect(self.dsn, autocommit=True) as db:
                db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s "
                           "AND subject_id=%s AND purpose='account_research'", (WS_A, PROJECT_A))
            return batch

    adapter = RevokingFixture(owner_dsn)
    assert _execute(runtime_dsn, adapter) == "partial"
    assert adapter.calls == 1
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 0
        assert db.execute("SELECT amount FROM cost_events WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.050000")
        assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.000000")


def test_second_query_after_restart_does_not_recount_the_same_company(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        snapshot = db.execute("SELECT execution_snapshot FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0]
        second = dict(snapshot["query_plan"]["queries"][0])
        second["id"] = "b" * 24
        second["round"] = 2
        snapshot["query_plan"]["queries"].append(second)
        db.execute("UPDATE search_runs SET execution_snapshot=%s::jsonb WHERE id=%s",
                   (json.dumps(snapshot), RUN_ID))

    class TwoQueryFixture(SearchFixture):
        async def search(self, query, *, market, language, limit, intent_key):
            self.calls += 1
            assert intent_key in {f"research:{RUN_ID}:{QUERY_ID}", f"research:{RUN_ID}:{'b'*24}"}
            suffix = "one" if self.calls == 1 else "two"
            return DiscoveryBatch(
                hits=[{"url": f"https://example.org/{suffix}", "legal_name": "Acme GmbH",
                       "registry_id": "DE-HRB-123",
                       "excerpt": "Acme GmbH distributes industrial sensors.", "language": "en"}],
                charge=Decimal("0.050000"), billing_event_id=f"fixture-bill:{intent_key}",
            )

    adapter = TwoQueryFixture(owner_dsn)
    assert _execute(runtime_dsn, adapter) == "done"
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        pending = db.execute("SELECT intent_key FROM outbox_events WHERE workspace_id=%s "
                             "AND event_type='run.discover' AND state='ready'", (WS_A,)).fetchone()
        assert pending is not None
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 "
                   "WHERE workspace_id=%s AND intent_key=%s", (WS_A, pending[0]))
    assert _execute(runtime_dsn, adapter, pending[0]) == "done"
    assert adapter.calls == 2
    with psycopg.connect(owner_dsn) as db:
        status, usage = db.execute("SELECT status,usage_counters FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()
        assert status == "running" and usage["queries"] == 2
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='run.fit' "
                          "AND state='ready' AND workspace_id=%s", (WS_A,)).fetchone()[0] == 1
        assert usage["rounds"] == 2 and usage["pages"] == 2
        assert usage["companies"] == 1
        assert db.execute("SELECT count(*) FROM project_buyers WHERE project_id=%s", (PROJECT_A,)).fetchone()[0] == 1


def test_oversized_page_settles_known_cost_without_persisting_result(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        limits = dict(LIMITS)
        limits["max_page_bytes"] = 1024
        db.execute("UPDATE search_runs SET limits=%s::jsonb WHERE id=%s",
                   (json.dumps(limits), RUN_ID))

    class OversizedFixture(SearchFixture):
        async def search(self, query, *, market, language, limit, intent_key):
            self.calls += 1
            return DiscoveryBatch(
                hits=[{"url": "https://example.org/large", "legal_name": "Acme GmbH",
                       "excerpt": "x" * 1025, "language": "en"}],
                charge=Decimal("0.050000"), billing_event_id=f"fixture-bill:{intent_key}",
            )

    adapter = OversizedFixture(owner_dsn)
    assert _execute(runtime_dsn, adapter) == "partial"
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 0
        assert db.execute("SELECT amount FROM cost_events WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.050000")
        assert db.execute("SELECT usage_counters FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0]["pages"] == 1


def test_archived_project_blocks_the_queued_worker_without_provider_call(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        db.execute("UPDATE projects SET status='archived' WHERE id=%s", (PROJECT_A,))
    try:
        adapter = SearchFixture(owner_dsn)
        assert _execute(runtime_dsn, adapter) == "failed"
        assert adapter.calls == 0
        with psycopg.connect(owner_dsn) as db:
            assert db.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (INTENT,)).fetchone()[0] == "done"
            assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == 0
    finally:
        with psycopg.connect(owner_dsn, autocommit=True) as db:
            db.execute("UPDATE projects SET status='active' WHERE id=%s", (PROJECT_A,))
