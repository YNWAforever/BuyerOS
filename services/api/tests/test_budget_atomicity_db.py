"""T13: admission and settlement use real PostgreSQL locks and ledger rows."""

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from tests.conftest import runtime_role_dsn
from buyeros_api.api.deps import async_database_url
from tests.test_buyer_review_db import ADMIN, OPERATOR, PROJECT_A, VIEWER, WORKSPACE_A, _h, api

OCTOBER = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _set_limits(dsn, amount: str, at=OCTOBER):
    from buyeros_api.services.budget_service import ensure_period_accounts

    async def create():
        engine = create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                await ensure_period_accounts(session, uuid.UUID(WORKSPACE_A), uuid.UUID(PROJECT_A),
                                             None, "discovery", at=at)
        finally:
            await engine.dispose()

    asyncio.run(create())
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("UPDATE budget_accounts SET approved_limit=%s WHERE workspace_id=%s AND period_start=%s",
                     (amount, WORKSPACE_A, datetime(2026, 10, 1, tzinfo=timezone.utc)))


def test_twenty_parallel_confirmations_cannot_overspend_and_projection_is_one_event(seeded):
    from buyeros_api.api.errors import ApiError
    from buyeros_api.services.budget_service import reserve_operation
    from buyeros_api.services.settlement import settle_operation

    _set_limits(seeded, "10.000000")

    async def race():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)), pool_size=20, max_overflow=2)
        async def one(i):
            operation = uuid.uuid4()
            try:
                async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                    await reserve_operation(session, operation,
                        {"workspace_id": uuid.UUID(WORKSPACE_A), "project_id": uuid.UUID(PROJECT_A),
                         "category": "discovery"}, Decimal("1.000000"), "USD", "verified-price-v1", at=OCTOBER)
                return operation
            except ApiError as exc:
                assert exc.code == "BUDGET_LIMIT"
                return None
        try:
            return await asyncio.gather(*(one(i) for i in range(20)))
        finally:
            await engine.dispose()

    results = asyncio.run(race())
    accepted = [r for r in results if r]
    assert len(accepted) == 10
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM budget_reservations WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 10
        assert conn.execute("SELECT count(*) FROM budget_reservation_allocations WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 30

    async def settle():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await settle_operation(session, accepted[0], Decimal("0.400000"), "vendor-event-001")
        finally:
            await engine.dispose()
    assert asyncio.run(settle())["settled"] == "0.400000"
    assert asyncio.run(settle())["settled"] == "0.400000"
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM cost_events WHERE operation_id=%s AND kind='commit'", (accepted[0],)).fetchone()[0] == 1
        assert conn.execute("SELECT sum(settled_spend) FROM budget_accounts WHERE workspace_id=%s AND period_start=%s",
                            (WORKSPACE_A, datetime(2026, 10, 1, tzinfo=timezone.utc))).fetchone()[0] == Decimal("1.200000")


def test_budget_api_requires_admin_reason_version_and_has_real_money_strings(api, seeded):
    from tests.contract_validation import assert_contract_response
    path = f"/v1/workspaces/{WORKSPACE_A}/budgets"
    listed = api.get(path, headers=_h(subject=OPERATOR))
    assert listed.status_code == 200, listed.text
    assert_contract_response("BudgetAccountPageResponse", listed.json())
    first_page = api.get(path + "?offset=0&limit=2", headers=_h(subject=OPERATOR)).json()["data"]
    second_page = api.get(path + "?offset=2&limit=2", headers=_h(subject=OPERATOR)).json()["data"]
    assert first_page["total"] == second_page["total"] >= 7
    assert len(first_page["items"]) == len(second_page["items"]) == 2
    assert {item["id"] for item in first_page["items"]}.isdisjoint(
        {item["id"] for item in second_page["items"]})
    project = next(item for item in listed.json()["data"]["items"] if item["scope"] == "project")
    assert project["approved_limit"] == {"amount": "0.000000", "currency": "USD"}
    assert api.get(path, headers=_h(subject=VIEWER)).status_code == 403
    url = f"{path}/{project['id']}"
    body = {"approved_limit": {"amount": "2.000000", "currency": "USD"}, "reason": "Pilot test limit"}
    assert api.patch(url, json=body, headers=_h(subject=OPERATOR, key="t13-operator-budget", **{"If-Match": '"1"'})).status_code == 403
    changed = api.patch(url, json=body, headers=_h(subject=ADMIN, key="t13-admin-budget", **{"If-Match": '"1"'}))
    assert changed.status_code == 200, changed.text
    assert_contract_response("BudgetAccountResponse", changed.json())
    assert changed.json()["data"]["version"] == 2
    with psycopg.connect(seeded) as conn:
        audit = conn.execute("SELECT action,subject_type,subject_id FROM audit_events "
                             "WHERE workspace_id=%s AND action='budget.limit_updated' AND subject_id=%s",
                             (WORKSPACE_A, project["id"])).fetchall()
        assert audit == [("budget.limit_updated", "budget_account", project["id"])]
    assert api.patch(url, json=body, headers=_h(subject=ADMIN, key="t13-stale-budget", **{"If-Match": '"1"'})).status_code == 412
    assert api.patch(url, json={**body, "reason": "no"}, headers=_h(subject=ADMIN, key="t13-bad-reason", **{"If-Match": '"2"'})).status_code == 422


def test_replay_scope_cost_evidence_and_limit_reduction(api, seeded):
    from buyeros_api.services.budget_service import reserve_operation
    from buyeros_api.services.settlement import settle_operation
    path = f"/v1/workspaces/{WORKSPACE_A}/budgets"
    listed = api.get(path, headers=_h(subject=ADMIN)).json()["data"]["items"]
    current = datetime.now(timezone.utc).strftime("%Y-%m")
    accounts = [row for row in listed if row["period_start"].startswith(current) and
                (row["scope"] in ("workspace", "project") or row["scope"] == "category" and row["category"] == "discovery")]
    assert len(accounts) == 3
    for row in accounts:
        body = {"approved_limit": {"amount": "2.000000", "currency": "USD"}, "reason": "Verified test ceiling"}
        changed = api.patch(f"{path}/{row['id']}", json=body,
            headers=_h(subject=ADMIN, key=f"t13-cap-{row['id']}", **{"If-Match": f'"{row["version"]}"'}))
        assert changed.status_code == 200, changed.text
    scope = {"workspace_id": uuid.UUID(WORKSPACE_A), "project_id": uuid.UUID(PROJECT_A), "category": "discovery"}
    operation = uuid.uuid4()
    async def reserve():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await reserve_operation(session, operation, scope, Decimal("1.000000"), "USD", "price-v1")
        finally:
            await engine.dispose()
    first = asyncio.run(reserve())
    assert asyncio.run(reserve()) == first
    async def wrong_scope():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await reserve_operation(session, operation, {**scope, "category": "assessment"},
                                               Decimal("1.000000"), "USD", "price-v1")
        finally:
            await engine.dispose()
    with pytest.raises(ApiError) as mismatch:
        asyncio.run(wrong_scope())
    assert mismatch.value.code == "IDEMPOTENCY_CONFLICT"
    project = next(row for row in accounts if row["scope"] == "project")
    reduced = api.patch(f"{path}/{project['id']}",
        json={"approved_limit": {"amount": "0.000000", "currency": "USD"}, "reason": "Try reducing below hold"},
        headers=_h(subject=ADMIN, key="t13-reduction-under-hold", **{"If-Match": f'"{project["version"]+1}"'}))
    assert reduced.status_code == 409 and reduced.json()["code"] == "BUDGET_LIMIT"
    async def no_evidence():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await settle_operation(session, operation, Decimal("0.000000"), "")
        finally:
            await engine.dispose()
    with pytest.raises(ApiError) as missing:
        asyncio.run(no_evidence())
    assert missing.value.code == "INVALID_REQUEST"
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s", (operation,)).fetchone()[0] == Decimal("1.000000")
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE budget_accounts SET frozen=true WHERE id=%s", (project["id"],))
    async def blocked_new_and_reconcile_old():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                with pytest.raises(ApiError) as blocked:
                    await reserve_operation(session, uuid.uuid4(), scope, Decimal("0.500000"), "USD", "price-v1")
                assert blocked.value.code == "BUDGET_LIMIT"
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await settle_operation(session, operation, Decimal("0.600000"), "vendor-frozen-settle")
        finally:
            await engine.dispose()
    assert asyncio.run(blocked_new_and_reconcile_old())["settled"] == "0.600000"
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s", (operation,)).fetchone()[0] == Decimal("0.000000")


def test_0018_empty_downgrade_upgrade_and_force_rls(migrated):
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
    with psycopg.connect(migrated, autocommit=True) as conn:
        for table in ("budget_reservation_allocations", "cost_events", "budget_reservations", "budget_accounts"):
            conn.execute(f"DELETE FROM {table}")
    config = Config(str(ALEMBIC_INI)); config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    command.downgrade(config, "0017_settings_audit")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT to_regclass('budget_reservation_allocations')").fetchone()[0] is None
    legacy_workspace = uuid.uuid4()
    legacy_account = uuid.uuid4()
    with psycopg.connect(migrated, autocommit=True) as conn:
        conn.execute("INSERT INTO workspaces(id,name) VALUES (%s,'Legacy budget preflight')", (legacy_workspace,))
        conn.execute("INSERT INTO budget_accounts(id,workspace_id,scope,period,approved_limit) "
                     "VALUES (%s,%s,'workspace','2026-09',1)", (legacy_account,legacy_workspace))
    with pytest.raises(RuntimeError, match="legacy financial rows"):
        command.upgrade(config, "head")
    with psycopg.connect(migrated, autocommit=True) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0017_settings_audit"
        assert conn.execute("SELECT approved_limit FROM budget_accounts WHERE id=%s", (legacy_account,)).fetchone()[0] == Decimal("1.000000")
        conn.execute("DELETE FROM budget_accounts WHERE id=%s", (legacy_account,))
        conn.execute("DELETE FROM workspaces WHERE id=%s", (legacy_workspace,))
    command.upgrade(config, "head")
    with psycopg.connect(migrated) as conn:
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0038_c61_workspace_directory"
        assert conn.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname='budget_reservation_allocations'").fetchone() == (True, True)


def test_run_scope_is_a_fourth_constraint_not_a_second_economic_charge(seeded):
    from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
    icp_id, run_id, operation = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash) "
                     "VALUES (%s,%s,%s,1,'{}',%s)", (icp_id, WORKSPACE_A, PROJECT_A, "a"*64))
        conn.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,target_companies,raw_result_count) "
                     "VALUES (%s,%s,%s,%s,'queued','{}',1,0)", (run_id, WORKSPACE_A, PROJECT_A, icp_id))
    async def allocate():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await ensure_period_accounts(session, uuid.UUID(WORKSPACE_A), uuid.UUID(PROJECT_A),
                                                    run_id, "discovery")
        finally:
            await engine.dispose()
    try:
        asyncio.run(allocate())
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("UPDATE budget_accounts SET approved_limit=1 WHERE workspace_id=%s AND period_start=%s",
                         (WORKSPACE_A, datetime.now(timezone.utc).replace(day=1,hour=0,minute=0,second=0,microsecond=0)))
        async def reserve():
            engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)))
            try:
                async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                    return await reserve_operation(session, operation,
                        {"workspace_id":uuid.UUID(WORKSPACE_A), "project_id":uuid.UUID(PROJECT_A),
                         "run_id":run_id, "category":"discovery"},
                        Decimal("1.000000"), "USD", "price-v1")
            finally:
                await engine.dispose()
        asyncio.run(reserve())
        with psycopg.connect(seeded) as conn:
            kinds = conn.execute(
                "SELECT a.scope FROM budget_reservation_allocations ba "
                "JOIN budget_reservations r ON r.id=ba.reservation_id "
                "JOIN budget_accounts a ON a.id=ba.account_id WHERE r.operation_id=%s",
                (operation,)).fetchall()
            assert {item[0] for item in kinds} == {"workspace","project","run","category"}
            assert conn.execute("SELECT count(*) FROM budget_reservations WHERE operation_id=%s", (operation,)).fetchone()[0] == 1
            assert conn.execute("SELECT count(*) FROM cost_events WHERE operation_id=%s", (operation,)).fetchone()[0] == 0
    finally:
        with psycopg.connect(seeded, autocommit=True) as conn:
            conn.execute("DELETE FROM search_runs WHERE id=%s", (run_id,))
            conn.execute("DELETE FROM icp_versions WHERE id=%s", (icp_id,))
