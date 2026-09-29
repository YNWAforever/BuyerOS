"""T27 usage and manual outcome regressions on disposable PostgreSQL."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
from buyeros_api.services.settlement import settle_operation, refund_operation
from tests.conftest import runtime_role_dsn
from tests.contract_validation import assert_contract_response

import psycopg
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import OPERATOR, REVIEWER, WORKSPACE_A, PROJECT, _h, quote_case


def _period(month_offset=0):
    today = datetime.now(timezone.utc)
    first = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = first.year * 12 + first.month - 1 + month_offset
    start = first.replace(year=months // 12, month=months % 12 + 1)
    next_month = months + 1
    end = first.replace(year=next_month // 12, month=next_month % 12 + 1)
    return {"from": start.isoformat(), "to": end.isoformat()}


def test_usage_empty_denominators_are_null_and_viewer_can_read(quote_case):
    api, _dsn, _buyers = quote_case
    response = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/usage",
                       params=_period(-1), headers=_h(REVIEWER))
    assert response.status_code == 200, response.text
    assert_contract_response("UsageResponse", response.json())
    data = response.json()["data"]
    assert data["accepted_company_count"] == 0
    assert data["eligible_contactable_company_count"] == 0
    assert data["cost_per_accepted_company"] is None
    assert data["cost_per_contactable_accepted_company"] is None
    assert data["total_settled"] == {"amount": "0.000000", "currency": "USD"}


def test_manual_outcome_is_append_only_and_viewer_cannot_write(quote_case):
    api, dsn, buyers = quote_case
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/outcomes"
    body = {"buyer_id": buyers[0][0], "stage": "meeting", "source": "manual",
            "occurred_at": "2026-09-20T11:15:00Z", "notes": "Operator logged a meeting manually"}
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE memberships SET roles=ARRAY['viewer']::varchar[],version=version+1 "
                   "WHERE workspace_id=%s AND user_id=%s",
                   (WORKSPACE_A, uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
    denied = api.post(path, json=body, headers=_h(REVIEWER, key="t27-viewer-outcome"))
    assert denied.status_code == 403, denied.text
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE memberships SET roles=ARRAY['reviewer']::varchar[],version=version+1 "
                   "WHERE workspace_id=%s AND user_id=%s",
                   (WORKSPACE_A, uuid.uuid5(uuid.NAMESPACE_URL, REVIEWER)))
    created = api.post(path, json=body, headers=_h(OPERATOR, key="t27-manual-outcome"))
    assert created.status_code == 201, created.text
    first = created.json()["data"]
    assert first["source"] == "manual" and first["stage"] == "meeting"
    assert first["actor_id"] and first["recorded_at"] != first["occurred_at"]
    assert first["project_id"] == PROJECT
    replay = api.post(path, json=body, headers=_h(OPERATOR, key="t27-manual-outcome"))
    assert replay.status_code == 201 and replay.json()["data"]["id"] == first["id"]
    corrected = api.post(f"/v1/workspaces/{WORKSPACE_A}/outcomes/{first['id']}/corrections",
        json={"stage": "opportunity", "occurred_at": "2026-09-21T12:00:00Z",
              "notes": "Corrected after manual review", "reason": "Initial stage was incomplete"},
        headers=_h(REVIEWER, key="t27-correct-outcome", **{"If-Match": '"1"'}))
    assert corrected.status_code == 201, corrected.text
    second = corrected.json()["data"]
    assert second["id"] != first["id"] and second["supersedes_id"] == first["id"]
    assert second["correction_reason"] == "Initial stage was incomplete"
    listed = api.get(path, params={"offset": 0, "limit": 10}, headers=_h(REVIEWER))
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["total"] == 2
    assert {row["id"] for row in listed.json()["data"]["items"]} == {first["id"], second["id"]}


def test_usage_real_ledger_holds_refunds_and_distinct_policy_contactability(quote_case):
    api, dsn, buyers = quote_case
    now = datetime.now(timezone.utc)
    company_a, company_b = buyers[0][1], buyers[1][1]
    run_ids = [uuid.uuid4() for _ in range(3)]
    with psycopg.connect(dsn, autocommit=True) as db:
        for run_id, status in zip(run_ids, ("partial", "cancelled", "failed")):
            db.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status) "
                       "VALUES (%s,%s,%s,%s,%s)", (run_id, WORKSPACE_A, PROJECT,
                       "d0000000-0000-4000-8000-000000000021", status))
        for index, company in enumerate((company_a, company_a, company_a, company_b)):
            db.execute("INSERT INTO contact_points(id,workspace_id,company_id,type,normalized_value,validity,checked_at,quarantined) "
                       "VALUES (%s,%s,%s,'business_email',%s,'provider_marked_valid',%s,false)",
                       (uuid.uuid4(), WORKSPACE_A, company, f"metric{index}@fixture.example", now-timedelta(minutes=1)))

    async def setup_accounts():
        engine = create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                for run_id in run_ids:
                    await ensure_period_accounts(session, uuid.UUID(WORKSPACE_A), uuid.UUID(PROJECT),
                                                 run_id, "discovery", at=now)
        finally:
            await engine.dispose()
    asyncio.run(setup_accounts())
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET approved_limit=10 WHERE workspace_id=%s AND period_start=%s",
                   (WORKSPACE_A, datetime.fromisoformat(_period()["from"])))

    async def populate_ledger():
        engine = create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            operations = [uuid.uuid4() for _ in range(3)]
            for operation, amount, run_id in zip(operations, ("2.000000", "0.500000", "1.000000"), run_ids):
                async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                    await reserve_operation(session, operation, {"workspace_id": uuid.UUID(WORKSPACE_A),
                        "project_id": uuid.UUID(PROJECT), "run_id": run_id, "category": "discovery"},
                        Decimal(amount), "USD", "fixture-v1", at=now)
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await settle_operation(session, operations[0], Decimal("1.200000"), "metric-partial-1", at=now)
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await refund_operation(session, operations[0], Decimal("0.200000"), "metric-refund-1", at=now)
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await settle_operation(session, operations[2], Decimal("0.400000"), "metric-failed-1", at=now)
        finally:
            await engine.dispose()
    asyncio.run(populate_ledger())
    response = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/usage",
                       params=_period(), headers=_h(REVIEWER))
    assert response.status_code == 200, response.text
    assert_contract_response("UsageResponse", response.json())
    data = response.json()["data"]
    assert data["accepted_company_count"] == 2
    assert data["eligible_contactable_company_count"] == 1
    assert data["total_settled"] == {"amount": "1.400000", "currency": "USD"}
    assert data["total_reserved"] == {"amount": "0.500000", "currency": "USD"}
    assert data["cost_per_accepted_company"] == {"amount": "0.700000", "currency": "USD"}
    assert data["cost_per_contactable_accepted_company"] == {"amount": "1.400000", "currency": "USD"}
    category = next(row for row in data["categories"] if row["category"] == "discovery")
    assert category["settled"] == data["total_settled"] and category["reserved"] == data["total_reserved"]


def test_outcome_pagination_correction_guards_and_contract(quote_case):
    api, dsn, buyers = quote_case
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/outcomes"
    body = {"buyer_id": buyers[0][0], "stage": "reply", "source": "manual",
            "occurred_at": "2026-09-20T11:15:00Z", "notes": "Entered from the manual tracker"}
    created = api.post(path, json=body, headers=_h(OPERATOR, key="t27-guard-create"))
    assert created.status_code == 201, created.text
    assert_contract_response("OutcomeEventResponse", created.json())
    first = created.json()["data"]
    correction_path = f"/v1/workspaces/{WORKSPACE_A}/outcomes/{first['id']}/corrections"
    correction = {"stage": "meeting", "occurred_at": body["occurred_at"],
                  "reason": "Verified stage after review", "notes": "Corrected manually"}
    assert api.post(correction_path, json=correction, headers=_h(REVIEWER,
        key="t27-missing-version")).status_code == 400
    assert api.post(correction_path, json=correction, headers=_h(REVIEWER,
        key="t27-stale-version", **{"If-Match": '"2"'})).status_code == 412
    corrected = api.post(correction_path, json=correction, headers=_h(REVIEWER,
        key="t27-valid-correction", **{"If-Match": '"1"'}))
    assert corrected.status_code == 201, corrected.text
    assert_contract_response("OutcomeEventResponse", corrected.json())
    assert api.post(correction_path, json=correction, headers=_h(REVIEWER,
        key="t27-fork-attempt", **{"If-Match": '"1"'})).status_code == 409
    p0 = api.get(path, params={"offset": 0, "limit": 1}, headers=_h(REVIEWER))
    p1 = api.get(path, params={"offset": 1, "limit": 1}, headers=_h(REVIEWER))
    assert_contract_response("OutcomeEventPageResponse", p0.json())
    assert_contract_response("OutcomeEventPageResponse", p1.json())
    assert p0.json()["data"]["total"] == p1.json()["data"]["total"] == 2
    assert p0.json()["data"]["items"][0]["id"] != p1.json()["data"]["items"][0]["id"]
    with psycopg.connect(dsn) as db:
        rows = db.execute("SELECT id,stage,actor_user_id FROM outcome_events WHERE workspace_id=%s ORDER BY created_at,id",
                          (WORKSPACE_A,)).fetchall()
        assert len(rows) == 2
        assert {row[1] for row in rows} == {"reply", "meeting"}
        assert rows[0][2] != rows[1][2]
    assert api.post(path, json={**body, "buyer_id": str(uuid.uuid4())},
                    headers=_h(OPERATOR, key="t27-foreign-buyer")).status_code == 404
    assert api.get(path, params={"offset": 0, "limit": 0}, headers=_h(REVIEWER)).status_code == 422


def test_usage_refund_is_signed_in_recorded_period_not_origin_period(quote_case):
    api, dsn, _buyers = quote_case
    prior = datetime.fromisoformat(_period(-1)["from"]) + timedelta(days=5)
    now = datetime.now(timezone.utc)
    operation = uuid.uuid4()
    async def setup_prior():
        engine = create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await ensure_period_accounts(session, uuid.UUID(WORKSPACE_A), uuid.UUID(PROJECT),
                                             None, "discovery", at=prior)
        finally:
            await engine.dispose()
    asyncio.run(setup_prior())
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET approved_limit=10 WHERE workspace_id=%s AND period_start=%s",
                   (WORKSPACE_A, datetime.fromisoformat(_period(-1)["from"])))
    async def charge_then_refund():
        engine = create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await reserve_operation(session, operation, {"workspace_id": uuid.UUID(WORKSPACE_A),
                    "project_id": uuid.UUID(PROJECT), "category": "discovery"},
                    Decimal("1.000000"), "USD", "fixture-v1", at=prior)
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await settle_operation(session, operation, Decimal("1.000000"), "t27-prior-charge", at=prior)
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await refund_operation(session, operation, Decimal("0.500000"), "t27-current-refund", at=now)
        finally:
            await engine.dispose()
    asyncio.run(charge_then_refund())
    current = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/usage",
                      params=_period(), headers=_h(REVIEWER))
    assert current.status_code == 200, current.text
    assert current.json()["data"]["total_settled"]["amount"] == "-0.500000"
    assert current.json()["data"]["cost_per_accepted_company"]["amount"] == "-0.250000"
    previous = api.get(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/usage",
                       params=_period(-1), headers=_h(REVIEWER))
    assert previous.status_code == 200, previous.text
    assert previous.json()["data"]["total_settled"]["amount"] == "1.000000"


def test_work_queue_snapshot_filters_are_server_owned(quote_case):
    api, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE project_buyers SET owner_user_id=%s WHERE id=%s",
                   (uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR), buyers[0][0]))
        company, buyer = uuid.uuid4(), uuid.uuid4()
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) "
                   "VALUES (%s,%s,'Unassessed Fixture','Unassessed Fixture','unassessed.example')",
                   (company, WORKSPACE_A))
        db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",
                   (buyer, WORKSPACE_A, PROJECT, company))
    path = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/buyer-snapshots"
    def count(filters, key):
        response = api.post(path, json={"filters": filters, "sort": "name_asc", "requested_limit": 1000},
                            headers=_h(REVIEWER, key=key))
        assert response.status_code == 201, response.text
        return response.json()["data"]["total"]
    assert count({"owner_unassigned": True}, "t27-queue-unassigned") == 2
    assert count({"unknown_fit": True}, "t27-queue-unknown") == 1
    assert count({"review": ["awaiting_review"]}, "t27-queue-review") == 1
