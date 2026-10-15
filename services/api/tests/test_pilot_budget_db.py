import asyncio
import copy
import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import runtime_role_dsn
from tests.lead_fixtures import ACTORS, WORKSPACE, PROJECT, headers, prepare, apply, lead_api, lead_case


@pytest.mark.parametrize("configured", [False, True], ids=["legacy-without-policy", "disabled-pilot"])
def test_worker_admission_preserves_legacy_projects_without_private_lead_access(lead_api, lead_case, configured):
    """Worker budget admission must never require private lead evidence privileges."""
    from sqlalchemy import text
    from buyeros_api.db.session import tenant_session
    from buyeros_api.api.errors import ApiError
    from buyeros_api.services.pilot_budget_service import assert_pilot_admission

    if configured:
        configure(lead_api, lead_case)

    async def run():
        engine = create_async_engine(lead_case["dsn"].replace("postgresql://", "postgresql+psycopg://"))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE)) as session:
                await session.execute(text("SET LOCAL ROLE buyeros_worker"))
                assert not await session.scalar(text(
                    "SELECT has_table_privilege(current_user,'lead_private_payloads','SELECT')"))
                if configured:
                    with pytest.raises(ApiError) as error:
                        await assert_pilot_admission(session, workspace_id=uuid.UUID(WORKSPACE),
                            project_id=uuid.UUID(PROJECT), operation_id=uuid.uuid4(),
                            upper_bound=Decimal("0.4"), now=datetime.now(timezone.utc))
                    assert error.value.code == "POLICY_BLOCKED"
                else:
                    await assert_pilot_admission(session, workspace_id=uuid.UUID(WORKSPACE),
                        project_id=uuid.UUID(PROJECT), operation_id=uuid.uuid4(),
                        upper_bound=Decimal("0.4"), now=datetime.now(timezone.utc))
        finally:
            await engine.dispose()
    asyncio.run(run())


def budget(api, case, role="workspace_admin"):
    response = api.get(f"{case['base']}/pilot-budget", headers=headers(role))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def write(api, case, action, payload, *, role="workspace_admin"):
    view = budget(api, case)
    staged = prepare(api, case, action, payload, role=role, buyer=False, version=view["version"])
    assert staged.status_code == 201, staged.text
    result = apply(api, case, staged.json()["data"], role=role)
    assert result.status_code == 200, result.text
    return result.json()["data"]


def configure(api, case):
    return write(api, case, "pilot.policy", {"monthly_limit": "10.000000", "reason": "Approved shared pilot cap"})


def source():
    return [{"title": "Offline fixture statement", "url": "https://billing.example.test/monthly"}]


def cost(api, case, amount="6.000000", **changes):
    payload = {
        "economic_charge_key": "fixture-invoice-1", "period_start": budget(api, case)["period_start"],
        "state": "committed", "usd_amount": amount, "usd_upper_bound": amount,
        "original_amount": amount, "original_currency": "USD",
        "fees_included": True, "minimum_purchase_included": True,
        "source_refs": source(), "reason": "Complete invoice including all fees",
    }
    payload.update(changes)
    return write(api, case, "cost.record", payload)


def reconcile(api, case):
    view = budget(api, case)
    return write(api, case, "budget.reconcile", {
        "period_start": view["period_start"], "ledger_version": view["ledger_version"],
        "ledger_hash": view["ledger_hash"], "coverage_start": view["period_start"],
        "coverage_end": view["as_of"], "shared_usage_known": True,
        "source_refs": source(), "reason": "All native and external account usage has been checked.",
    })


def native_rows(case, *, amount="2.000000", hold="0.000000", state="settled"):
    account, reservation, operation = (uuid.uuid4() for _ in range(3))
    with psycopg.connect(case["dsn"], autocommit=True) as db:
        db.execute(
            "INSERT INTO budget_accounts"
            "(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,"
            "version,frozen,approved_limit,settled_spend)"
            "VALUES (%s,%s,'project',%s,'all','USD',to_char(now(),'YYYY-MM'),date_trunc('month',now()),"
            "date_trunc('month',now())+interval '1 month',1,false,100,%s)",
            (account, WORKSPACE, PROJECT, amount if state == "settled" else "0"),
        )
        db.execute(
            "INSERT INTO budget_reservations"
            "(id,workspace_id,account_id,operation_id,intent_key,price_version,currency,origin_period_start,"
            "upper_bound,remaining_hold,state) VALUES (%s,%s,%s,%s,%s,'fixture-reviewed','USD',"
            "date_trunc('month',now()),%s,%s,%s)",
            (reservation, WORKSPACE, account, operation, str(operation), amount, hold, state),
        )
        db.execute("INSERT INTO budget_reservation_allocations(id,workspace_id,reservation_id,account_id)"
                   "VALUES (%s,%s,%s,%s)", (uuid.uuid4(), WORKSPACE, reservation, account))
        if state == "settled":
            db.execute("INSERT INTO cost_events(id,workspace_id,operation_id,external_event_id,kind,amount,"
                       "pricing_version,occurred_at,recorded_at)"
                       "VALUES (%s,%s,%s,%s,'commit',%s,'fixture-reviewed',date_trunc('month',now()),now())",
                       (uuid.uuid4(), WORKSPACE, operation, f"fixture-receipt-{operation}", amount))
    return account, reservation, operation


def test_unknown_history_is_not_zero_and_does_not_grant_budget(lead_api, lead_case):
    view = budget(lead_api, lead_case)
    assert view["limit"] == "10.000000" and view["remaining"] is None
    assert view["settled_total"] is None
    assert view["activation"] == "disabled"
    assert view["reconciliation_status"] == "unknown"
    configure(lead_api, lead_case)
    with psycopg.connect(lead_case["dsn"]) as db:
        for table in ("budget_accounts", "budget_reservations", "provider_operations", "outbox_events"):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
    assert budget(lead_api, lead_case)["remaining"] is None
    assert lead_api.get(f"{lead_case['base']}/pilot-budget", headers=headers("viewer")).status_code == 403


def test_cost_identity_prepaid_fees_and_carried_hold(lead_api, lead_case):
    configure(lead_api, lead_case)
    committed = cost(lead_api, lead_case)
    reconcile(lead_api, lead_case)
    assert budget(lead_api, lead_case)["remaining"] == "4.000000"
    settled = cost(lead_api, lead_case, state="settled", previous_event_id=committed["resource_id"])
    reconcile(lead_api, lead_case)
    view = budget(lead_api, lead_case)
    assert view["settled_total"] == "6.000000" and view["external_unsettled"] == "0.000000"
    write(lead_api, lead_case, "credits.record", {
        "provider": "fixture-prepaid", "unit": "prepaid_credits", "period_start": view["period_start"],
        "period_end": view["period_end"], "used": "100.000000", "remaining": "0.000000",
        "as_of": view["as_of"], "source_refs": source(),
    })
    reconcile(lead_api, lead_case)
    assert budget(lead_api, lead_case)["remaining"] == "4.000000"
    cost(lead_api, lead_case, amount="5.500000", state="corrected", previous_event_id=settled["resource_id"])
    reconcile(lead_api, lead_case)
    assert budget(lead_api, lead_case)["remaining"] == "4.500000"
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM pilot_cost_events").fetchone() == (3,)
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone() == (0,)


def test_native_cost_reference_binds_budget_operation_not_provider_request(lead_case):
    _, _, operation = native_rows(lead_case)
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        payload, event = uuid.uuid4(), uuid.uuid4()
        db.execute("INSERT INTO lead_private_payloads(id,workspace_id,project_id,contents,content_hash,retention_expires_at)"
                   "VALUES (%s,%s,%s,'{}','sha256:fixture',now()+interval '30 days')", (payload, WORKSPACE, PROJECT))
        db.execute(
            "INSERT INTO pilot_cost_events"
            "(id,workspace_id,project_id,economic_key_hash,sequence,native_operation_id,period_start,state,"
            "effective_state,usd_amount,usd_upper_bound,payload_id,recorded_by_user_id)"
            "VALUES (%s,%s,%s,'sha256:invoice',1,%s,date_trunc('month',now()),'settled','settled',2,2,%s,%s)",
            (event, WORKSPACE, PROJECT, operation, payload, ACTORS["workspace_admin"]),
        )
        assert db.execute("SELECT native_operation_id FROM pilot_cost_events WHERE id=%s", (event,)).fetchone() == (operation,)


def test_external_copy_of_native_settlement_is_not_double_counted(lead_api, lead_case):
    configure(lead_api, lead_case)
    _, _, operation = native_rows(lead_case, amount="6.000000")
    cost(lead_api, lead_case, state="settled", native_operation_id=str(operation))
    reconcile(lead_api, lead_case)
    view = budget(lead_api, lead_case)
    assert view["settled_total"] == "6.000000"
    assert view["remaining"] == "4.000000"


def test_atomic_pilot_cap_allows_only_one_of_two_040_requests(lead_api, lead_case):
    assert importlib.util.find_spec("buyeros_api.services.pilot_budget_service") is not None, "pilot budget feature is missing"
    configure(lead_api, lead_case)
    cost(lead_api, lead_case, amount="9.500000", state="settled")
    reconcile(lead_api, lead_case)
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
    from buyeros_api.api.errors import ApiError

    async def setup():
        engine = create_async_engine(runtime_role_dsn(lead_case["dsn"]).replace("postgresql://", "postgresql+psycopg://"))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE)) as session:
                await ensure_period_accounts(session, uuid.UUID(WORKSPACE), uuid.UUID(PROJECT), None, "discovery")
        finally:
            await engine.dispose()
    asyncio.run(setup())
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET approved_limit=100")

    def reserve():
        async def run():
            engine = create_async_engine(runtime_role_dsn(lead_case["dsn"]).replace("postgresql://", "postgresql+psycopg://"))
            try:
                async with tenant_session(engine, uuid.UUID(WORKSPACE)) as session:
                    await reserve_operation(session, uuid.uuid4(), {
                        "workspace_id": uuid.UUID(WORKSPACE), "project_id": uuid.UUID(PROJECT), "category": "discovery",
                    }, Decimal("0.400000"), "USD", "fixture-reviewed")
                return "reserved"
            except ApiError as error:
                assert error.code == "BUDGET_LIMIT"
                return "blocked"
            finally:
                await engine.dispose()
        return asyncio.run(run())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: reserve(), range(2)))
    assert sorted(results) == ["blocked", "reserved"]
    assert budget(lead_api, lead_case)["remaining"] == "0.100000"
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM budget_reservations").fetchone() == (1,)
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone() == (0,)


def test_utc_rollover_carries_unknown_hold(lead_case):
    assert importlib.util.find_spec("buyeros_api.services.pilot_budget_service") is not None, "pilot budget feature is missing"
    from buyeros_api.api.lead_schemas import LeadScope
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.pilot_budget_service import project_pilot_budget
    _, reservation, operation = native_rows(lead_case, amount="2", hold="2", state="active")
    # Move the fixture origin to October, then read a November UTC snapshot.
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET period_start='2026-10-01T00:00:00Z',period_end='2026-11-01T00:00:00Z',period='2026-10'")
        db.execute("UPDATE budget_reservations SET origin_period_start='2026-10-01T00:00:00Z'")
    async def read():
        engine = create_async_engine(runtime_role_dsn(lead_case["dsn"]).replace("postgresql://", "postgresql+psycopg://"))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE)) as session:
                scope = LeadScope(uuid.UUID(WORKSPACE), uuid.UUID(PROJECT), None, None,
                                  ACTORS["workspace_admin"], 1, frozenset({"workspace_admin"}))
                return await project_pilot_budget(session, scope=scope, now=datetime(2026, 11, 1, tzinfo=timezone.utc))
        finally:
            await engine.dispose()
    view = asyncio.run(read())
    assert view["carried_reserved"] == view["reserved_total"] == "2.000000"
    assert view["remaining"] is None and view["activation"] == "disabled"
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT remaining_hold,intent_key FROM budget_reservations WHERE id=%s", (reservation,)).fetchone() == (Decimal("2"), str(operation))
        assert db.execute("SELECT count(*) FROM budget_accounts").fetchone() == (1,)


@pytest.mark.parametrize("change", [{"monthly_limit": "10.000001"}, {"monthly_limit": "-1"}, {"monthly_limit": 10.0}])
def test_pilot_policy_rejects_unapproved_limit_and_float(lead_api, lead_case, change):
    view = budget(lead_api, lead_case)
    response = prepare(lead_api, lead_case, "pilot.policy", {**change, "reason": "Invalid limit"},
                       role="workspace_admin", buyer=False, version=view["version"])
    assert response.status_code == 422


def test_unknown_amount_and_incomplete_fees_cannot_be_reconciled_as_zero(lead_api, lead_case):
    configure(lead_api, lead_case)
    cost(lead_api, lead_case, state="unknown", usd_amount=None, usd_upper_bound=None,
         original_amount=None, fees_included=False)
    reconcile(lead_api, lead_case)
    view = budget(lead_api, lead_case)
    assert view["remaining"] is None and view["settled_total"] is None
    assert "unknown_cost_upper_bound" in view["blockers"]


def test_actual_overspend_is_recorded_without_clipping_or_granting_capacity(lead_api, lead_case):
    configure(lead_api, lead_case)
    cost(lead_api, lead_case, amount="12.000000", state="settled")
    reconcile(lead_api, lead_case)
    view = budget(lead_api, lead_case)
    assert view["recorded_settled"] == view["settled_total"] == "12.000000"
    assert view["remaining"] == "0.000000"
    assert view["budget_state"] == "over_limit"


def test_duplicate_invoice_needs_exact_original_chain_and_stale_reconciliation_is_rejected(lead_api, lead_case):
    configure(lead_api, lead_case)
    old = budget(lead_api, lead_case)
    cost(lead_api, lead_case)
    duplicate = prepare(lead_api, lead_case, "cost.record", {
        "economic_charge_key": "fixture-invoice-1", "period_start": old["period_start"], "state": "settled",
        "usd_amount": "6", "usd_upper_bound": "6", "fees_included": True, "minimum_purchase_included": True,
        "source_refs": source(), "reason": "Duplicate invoice without original event",
    }, role="workspace_admin", buyer=False, version=budget(lead_api, lead_case)["version"])
    assert duplicate.status_code == 201, duplicate.text
    assert apply(lead_api, lead_case, duplicate.json()["data"], role="workspace_admin").status_code == 409
    stale = prepare(lead_api, lead_case, "budget.reconcile", {
        "period_start": old["period_start"], "ledger_version": old["ledger_version"], "ledger_hash": old["ledger_hash"],
        "coverage_start": old["period_start"], "coverage_end": old["as_of"], "shared_usage_known": True,
        "source_refs": source(), "reason": "Outdated ledger cannot be accepted",
    }, role="workspace_admin", buyer=False, version=budget(lead_api, lead_case)["version"])
    assert stale.status_code == 201
    assert apply(lead_api, lead_case, stale.json()["data"], role="workspace_admin").status_code == 412
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM pilot_cost_events").fetchone() == (1,)


def test_budget_recording_and_policy_never_require_or_enable_contact_enrichment(lead_api, lead_case):
    with psycopg.connect(lead_case["dsn"], autocommit=True) as db:
        db.execute("DELETE FROM policy_decisions WHERE purpose='contact_research'")
    configure(lead_api, lead_case)
    cost(lead_api, lead_case, amount="1.000000", state="settled")
    reconcile(lead_api, lead_case)
    assert budget(lead_api, lead_case)["remaining"] == "9.000000"
    assert budget(lead_api, lead_case)["activation"] == "disabled"
    with psycopg.connect(lead_case["dsn"]) as db:
        assert db.execute("SELECT count(*) FROM provider_operations").fetchone() == (0,)
