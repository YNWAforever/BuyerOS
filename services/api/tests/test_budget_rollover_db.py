"""T13: carried unknown liability survives UTC boundaries and late reversals."""

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
from tests.test_buyer_review_db import PROJECT_A, WORKSPACE_A

SEPTEMBER = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)
OCTOBER = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
NOVEMBER = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)


def _run(dsn, action):
    async def run():
        engine = create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await action(session)
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_zero_period_and_carried_unknown_hold_block_new_admission_until_approved(seeded):
    from buyeros_api.services.budget_service import account_snapshot, ensure_period_accounts, reserve_operation
    scope = {"workspace_id": uuid.UUID(WORKSPACE_A), "project_id": uuid.UUID(PROJECT_A), "category": "discovery"}
    _run(seeded, lambda session: ensure_period_accounts(session, scope["workspace_id"], scope["project_id"], None, "discovery", at=SEPTEMBER))
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE budget_accounts SET approved_limit=5 WHERE workspace_id=%s AND period_start=%s",
                     (WORKSPACE_A, datetime(2026, 9, 1, tzinfo=timezone.utc)))
    operation = uuid.uuid4()
    _run(seeded, lambda session: reserve_operation(session, operation, scope, Decimal("2.000000"), "USD", "price-v1", at=SEPTEMBER))
    october = _run(seeded, lambda session: account_snapshot(session, scope["workspace_id"], scope["project_id"], None, "discovery", at=OCTOBER))
    assert all(row["approved_limit"]["amount"] == "0.000000" for row in october)
    assert all(row["carried_reserved"]["amount"] == "2.000000" for row in october)
    assert all(row["effective_state"] == "frozen_pending_budget" for row in october)
    with pytest.raises(ApiError) as blocked:
        _run(seeded, lambda session: reserve_operation(session, uuid.uuid4(), scope, Decimal("1.000000"), "USD", "price-v1", at=OCTOBER))
    assert blocked.value.code == "BUDGET_LIMIT"
    november = _run(seeded, lambda session: account_snapshot(session, scope["workspace_id"], scope["project_id"], None, "discovery", at=NOVEMBER))
    assert all(row["carried_reserved"]["amount"] == "2.000000" for row in november)
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE budget_accounts SET approved_limit=3 WHERE workspace_id=%s AND period_start=%s",
                     (WORKSPACE_A, NOVEMBER))
    _run(seeded, lambda session: reserve_operation(session, uuid.uuid4(), scope, Decimal("1.000000"), "USD", "price-v1", at=NOVEMBER))


def test_late_settlement_and_refund_keep_origin_period_and_idempotent_events(seeded):
    from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
    from buyeros_api.services.settlement import refund_operation, settle_operation
    scope = {"workspace_id": uuid.UUID(WORKSPACE_A), "project_id": uuid.UUID(PROJECT_A), "category": "discovery"}
    _run(seeded, lambda session: ensure_period_accounts(session, scope["workspace_id"], scope["project_id"], None, "discovery", at=SEPTEMBER))
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE budget_accounts SET approved_limit=5 WHERE workspace_id=%s AND period_start=%s",
                     (WORKSPACE_A, datetime(2026, 9, 1, tzinfo=timezone.utc)))
    operation = uuid.uuid4()
    _run(seeded, lambda session: reserve_operation(session, operation, scope, Decimal("2.000000"), "USD", "price-v1", at=SEPTEMBER))
    _run(seeded, lambda session: settle_operation(session, operation, Decimal("1.500000"), "vendor-charge-1", at=NOVEMBER))
    _run(seeded, lambda session: refund_operation(session, operation, Decimal("0.500000"), "vendor-refund-1", at=NOVEMBER))
    _run(seeded, lambda session: refund_operation(session, operation, Decimal("0.500000"), "vendor-refund-1", at=NOVEMBER))
    with psycopg.connect(seeded) as conn:
        events = conn.execute("SELECT kind,amount,occurred_at,recorded_at FROM cost_events WHERE operation_id=%s ORDER BY created_at,id", (operation,)).fetchall()
        assert [(row[0], row[1]) for row in events] == [("commit", Decimal("1.500000")), ("reversal", Decimal("-0.500000"))]
        assert all(row[2].month == 9 and row[3].month >= 9 for row in events)
        assert conn.execute("SELECT DISTINCT settled_spend FROM budget_accounts WHERE workspace_id=%s AND period_start=%s",
                            (WORKSPACE_A, datetime(2026, 9, 1, tzinfo=timezone.utc))).fetchall() == [(Decimal("1.000000"),)]


def test_two_confirmations_racing_at_utc_rollover_count_carry_once(seeded):
    from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
    scope = {"workspace_id": uuid.UUID(WORKSPACE_A), "project_id": uuid.UUID(PROJECT_A), "category": "discovery"}
    _run(seeded, lambda session: ensure_period_accounts(session, scope["workspace_id"], scope["project_id"], None, "discovery", at=SEPTEMBER))
    _run(seeded, lambda session: ensure_period_accounts(session, scope["workspace_id"], scope["project_id"], None, "discovery", at=OCTOBER))
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE budget_accounts SET approved_limit=1 WHERE workspace_id=%s AND period_start=%s",
                     (WORKSPACE_A, datetime(2026, 9, 1, tzinfo=timezone.utc)))
        conn.execute("UPDATE budget_accounts SET approved_limit=2 WHERE workspace_id=%s AND period_start=%s",
                     (WORKSPACE_A, OCTOBER))
    async def race():
        engine = create_async_engine(async_database_url(runtime_role_dsn(seeded)), pool_size=2)
        async def one(at):
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                return await reserve_operation(session, uuid.uuid4(), scope, Decimal("1.000000"), "USD", "price-v1", at=at)
        try:
            return await asyncio.gather(one(SEPTEMBER), one(OCTOBER))
        finally:
            await engine.dispose()
    assert len(set(asyncio.run(race()))) == 2
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM budget_reservations WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 2
