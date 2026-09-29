"""T20 cancellation races around the unlocked external search await."""

import uuid
from decimal import Decimal

import psycopg
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.db.session import tenant_session
from buyeros_api.db.runs import SearchRun
from buyeros_api.services.run_control import cancel_run
from tests.test_discovery_runner_db import (
    SearchFixture, WS_A, RUN_ID, _execute, discovery_case,
)


class CancellingSearch(SearchFixture):
    def __init__(self, owner_dsn, runtime_dsn, *, timeout=False):
        super().__init__(owner_dsn, timeout=timeout)
        self.runtime_dsn = runtime_dsn

    async def search(self, query, *, market, language, limit, intent_key):
        engine = create_async_engine(self.runtime_dsn.replace(
            "postgresql://", "postgresql+psycopg://", 1))
        try:
            async with tenant_session(engine, uuid.UUID(WS_A)) as session:
                run = await session.get(SearchRun, uuid.UUID(RUN_ID))
                await cancel_run(session, uuid.UUID(WS_A), uuid.UUID(RUN_ID),
                                 "stop after dispatch", expected_version=run.version)
        finally:
            await engine.dispose()
        return await super().search(query, market=market, language=language,
                                    limit=limit, intent_key=intent_key)


def test_cancel_during_known_result_keeps_evidence_cost_and_stops_next_intent(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    adapter = CancellingSearch(owner_dsn, runtime_dsn)
    assert _execute(runtime_dsn, adapter) == "cancelled"
    assert adapter.calls == 1
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT status FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0] == "cancelled"
        assert db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='run.fit'",
                          (WS_A,)).fetchone()[0] == 0
        assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s",
                          (WS_A,)).fetchone()[0] == Decimal("0.000000")
        assert db.execute("SELECT event_type FROM run_events WHERE run_id=%s ORDER BY sequence DESC LIMIT 1",
                          (RUN_ID,)).fetchone()[0] == "run.cancelled"


def test_cancel_during_ambiguous_result_keeps_hold_for_reconciliation(discovery_case):
    owner_dsn, runtime_dsn = discovery_case
    adapter = CancellingSearch(owner_dsn, runtime_dsn, timeout=True)
    assert _execute(runtime_dsn, adapter) == "unknown"
    assert adapter.calls == 1
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT status FROM search_runs WHERE id=%s", (RUN_ID,)).fetchone()[0] == "cancel_requested"
        assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s",
                          (WS_A,)).fetchone()[0] == Decimal("0.100000")
        assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='run.fit'",
                          (WS_A,)).fetchone()[0] == 0
