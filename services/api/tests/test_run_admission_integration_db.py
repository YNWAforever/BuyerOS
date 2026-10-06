"""T18 atomic admission and rejection against a disposable PostgreSQL database."""

import json
import uuid

import psycopg
import pytest

from buyeros_api.api.routes.runs import selected_run_capability
from buyeros_api.db.icp import canonical_hash
from tests.test_api_projects_db import api as project_api, WORKSPACE_A, OPERATOR, REVIEWER, _h
from tests.test_run_admission_db import LIMITS

PROJECT_A = "a0000000-0000-4000-8000-000000000001"
ICP_ID = "d0000000-0000-4000-8000-000000000018"
CAPABILITY = {
    "service": "search", "provider": "fixture", "verified": True,
    "price_version": "fixture-price-v1", "verified_filters": ["market", "language"],
    "markets": ["US"], "languages": ["en"], "roles": ["distributor"],
    "market_languages": {"US": ["en"]},
}


@pytest.fixture
def admission_case(project_api, seeded):
    content = {
        "markets": ["US"], "languages": ["en"], "buyer_types": ["distributor"],
        "requirements": [{"id": str(uuid.uuid4()), "category": "must", "text": "industrial sensors"}],
    }
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute(
            "INSERT INTO icp_versions(id, workspace_id, project_id, number, basis_offer_revision, "
            "content, content_hash, approved_at, approved_by) "
            "VALUES (%s,%s,%s,1,1,%s::jsonb,%s,now(),%s)",
            (ICP_ID, WORKSPACE_A, PROJECT_A, json.dumps(content), canonical_hash(content),
             str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER))),
        )
        db.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (ICP_ID, PROJECT_A))
        db.execute(
            "INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,"
            "purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) "
            "VALUES (%s,%s,'project',%s,%s,'account_research','permitted','test-v1','fixture','fixture',"
            "'{US}',now()+interval '1 day',1,%s)",
            (str(uuid.uuid4()), WORKSPACE_A, PROJECT_A, WORKSPACE_A,
             str(uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER))),
        )
    budgets = project_api.get(f"/v1/workspaces/{WORKSPACE_A}/budgets", headers=_h(key="run-budget-view"))
    assert budgets.status_code == 200, budgets.text
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET approved_limit=5 WHERE workspace_id=%s", (WORKSPACE_A,))
    project_api.app.dependency_overrides[selected_run_capability] = lambda: (CAPABILITY, "test")
    try:
        yield project_api, seeded
    finally:
        project_api.app.dependency_overrides.pop(selected_run_capability, None)
        with psycopg.connect(seeded, autocommit=True) as db:
            for table in ("outbox_events", "run_events", "search_runs"):
                db.execute(f"DELETE FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,))
            db.execute("DELETE FROM policy_decisions WHERE workspace_id=%s AND subject_id=%s",
                       (WORKSPACE_A, PROJECT_A))
            db.execute("DELETE FROM budget_accounts WHERE workspace_id=%s", (WORKSPACE_A,))


def _request():
    return {
        "icp_version_id": ICP_ID, "target_companies": 24,
        "max_cost": {"amount": "2.000000", "currency": "USD"},
        "limits": LIMITS,
    }


def _post(api, *, key="run-admit-0001", subject=OPERATOR, body=None):
    return api.post(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}/runs",
                    json=body or _request(), headers=_h(subject=subject, key=key))


def _count(dsn, table):
    with psycopg.connect(dsn) as db:
        return db.execute(f"SELECT count(*) FROM {table} WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0]


def test_start_run_is_atomic_and_replays_one_outbox_intent(admission_case):
    api, dsn = admission_case
    first = _post(api)
    assert first.status_code == 202, first.text
    data = first.json()["data"]
    assert data["status"] == "queued" and data["max_cost"]["amount"] == "2.000000"
    assert data["last_event_sequence"] == 1
    replay = _post(api)
    assert replay.status_code == 202 and replay.json()["data"]["id"] == data["id"]
    assert _count(dsn, "search_runs") == _count(dsn, "outbox_events") == _count(dsn, "run_events") == 1
    with psycopg.connect(dsn) as db:
        row = db.execute("SELECT execution_snapshot, usage_counters, first_dispatch_at FROM search_runs WHERE id=%s",
                         (data["id"],)).fetchone()
        assert row[0]["icp_content_hash"].startswith("sha256:")
        assert row[0]["capability"]["price_version"] == "fixture-price-v1"
        assert row[1]["queries"] == 0 and row[2] is None
    conflict = _post(api, body={**_request(), "target_companies": 25})
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


def test_rejected_run_does_not_queue_or_dispatch(admission_case):
    api, dsn = admission_case
    assert _post(api, key="run-role-0001", subject=REVIEWER).status_code == 403
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE icp_versions SET approved_at=NULL WHERE id=%s", (ICP_ID,))
    stale = _post(api, key="run-unapproved-0001")
    assert stale.status_code == 412, stale.text
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE icp_versions SET approved_at=now() WHERE id=%s", (ICP_ID,))
        db.execute("UPDATE projects SET offer_revision=2 WHERE id=%s", (PROJECT_A,))
    assert _post(api, key="run-stale-0001").status_code == 412
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE projects SET offer_revision=1,status='archived' WHERE id=%s", (PROJECT_A,))
    assert _post(api, key="run-archive-0001").status_code == 409
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE projects SET status='active' WHERE id=%s", (PROJECT_A,))
        db.execute("UPDATE budget_accounts SET approved_limit=0 WHERE workspace_id=%s", (WORKSPACE_A,))
    zero = _post(api, key="run-zero-budget-0001")
    assert zero.status_code == 409 and zero.json()["code"] == "BUDGET_LIMIT"
    api.app.dependency_overrides.pop(selected_run_capability)
    assert _post(api, key="run-no-provider-0001").status_code == 503
    assert _count(dsn, "search_runs") == _count(dsn, "outbox_events") == 0


def test_persisted_usage_survives_worker_restart(admission_case):
    import asyncio
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.db.runs import SearchRun
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.run_usage import UsageExceeded, advance_usage
    from tests.conftest import runtime_role_dsn

    api, dsn = admission_case
    result = _post(api, key="run-restart-0001")
    assert result.status_code == 202, result.text
    run_id = uuid.UUID(result.json()["data"]["id"])
    async_dsn = runtime_role_dsn(dsn).replace("postgresql://", "postgresql+psycopg://", 1)

    async def claim(amount, at):
        engine = create_async_engine(async_dsn)
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                run = (await session.execute(select(SearchRun).where(SearchRun.id == run_id)
                    .with_for_update())).scalar_one()
                advance_usage(run, {"queries": amount}, at=at, external=True)
        finally:
            await engine.dispose()

    start = datetime(2026, 9, 28, tzinfo=timezone.utc)
    asyncio.run(claim(12, start))
    with pytest.raises(UsageExceeded):
        asyncio.run(claim(1, start))
    with psycopg.connect(dsn) as db:
        counters, first = db.execute("SELECT usage_counters, first_dispatch_at FROM search_runs WHERE id=%s",
                                     (str(run_id),)).fetchone()
        assert counters["queries"] == 12 and first == start


def test_lost_admission_response_replays_one_bounded_economic_intent(admission_case):
    api, dsn = admission_case
    lost = _post(api, key="audit-lost-202")
    assert lost.status_code == 202
    first_id = lost.json()["data"]["id"]
    replay = _post(api, key="audit-lost-202")
    assert replay.status_code == 202 and replay.json()["data"]["id"] == first_id
    assert _count(dsn,"search_runs") == _count(dsn,"outbox_events") == 1
    with psycopg.connect(dsn) as db:
        ceiling = db.execute("SELECT count(*),min(approved_limit) FROM budget_accounts WHERE workspace_id=%s AND scope='run' AND scope_id=%s",(WORKSPACE_A,first_id)).fetchone()
        assert ceiling[0] == 1 and str(ceiling[1]) == '2.000000'
        # Admission records a ceiling, not a submitted provider operation or hold.
        assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0] == 0
        assert db.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0] == 0
