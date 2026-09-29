"""T15 dispatcher fairness and bounded cycle regressions."""
import asyncio
from datetime import datetime, timezone

import pytest

import buyeros_worker.dispatcher as dispatcher
from buyeros_worker.cli import build_parser

NOW = datetime(2026, 9, 27, tzinfo=timezone.utc)


def test_dispatch_cli_exposes_supervised_loop_without_changing_one_shot():
    args = build_parser().parse_args(["dispatch", "--loop", "--max-total", "7"])
    assert args.loop is True and args.max_total == 7
    assert build_parser().parse_args(["dispatch"]).loop is False


def test_cycle_has_global_cap_and_rotates_across_100_workspaces(monkeypatch):
    workspaces = [f"ws-{n:03d}" for n in range(100)]
    visits = []

    async def ids(engine):
        return workspaces

    async def one(engine, workspace_id, publish, owner, now, limit, lease_seconds, *, expired_only):
        visits.append(workspace_id)
        return [f"{workspace_id}:intent"] if limit else []

    monkeypatch.setattr(dispatcher, "_workspace_ids", ids)
    monkeypatch.setattr(dispatcher, "_dispatch_workspace", one)
    first = asyncio.run(dispatcher.dispatch_cycle(
        object(), lambda message: None, "owner", NOW, max_total=10,
        time_budget_seconds=5.0, cursor=0))
    second = asyncio.run(dispatcher.dispatch_cycle(
        object(), lambda message: None, "owner", NOW, max_total=10,
        time_budget_seconds=5.0, cursor=first["next_cursor"]))
    assert len(first["published"]) == len(second["published"]) == 10
    assert visits[:10] == workspaces[:10]
    assert visits[10:20] == workspaces[10:20]
    assert second["next_cursor"] == 20


def test_cycle_rejects_unbounded_limits():
    with pytest.raises(ValueError):
        asyncio.run(dispatcher.dispatch_cycle(
            object(), lambda message: None, "owner", NOW, max_total=0,
            time_budget_seconds=5.0))
    with pytest.raises(ValueError):
        asyncio.run(dispatcher.dispatch_cycle(
            object(), lambda message: None, "owner", NOW, max_total=10,
            time_budget_seconds=0))


def test_ready_intent_needs_dispatcher_claim_before_worker_can_execute(worker_database_url, pg_dsn):
    import psycopg
    from buyeros_worker.engine import create_engine
    from buyeros_worker.tasks import execute_intent_sync
    from tests.conftest import RUN_A, WS_A, reset_tenant, seed_outbox, seed_run

    intent = "job:dispatcher-required"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_run(conn)
        seed_outbox(
            conn, intent_key=intent, event_type="fetch.evidence",
            payload={"url": "https://example.com/x", "content_type": "text/html",
                     "size": 10, "run_id": RUN_A},
            state="ready", generation=0,
        )
    assert execute_intent_sync(intent, WS_A, 0) == "not_dispatched"
    with psycopg.connect(pg_dsn) as conn:
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (intent,)).fetchone()[0] == "ready"
        assert conn.execute("SELECT count(*) FROM run_events WHERE run_id=%s",
                            (RUN_A,)).fetchone()[0] == 0

    messages = []
    async def cycle():
        engine = create_engine()
        try:
            return await dispatcher.dispatch_cycle(
                engine, messages.append, "test-loop", datetime.now(timezone.utc),
                max_total=10, time_budget_seconds=5.0,
            )
        finally:
            await engine.dispose()
    result = asyncio.run(cycle())
    assert result["published"] == [intent]
    assert messages[0]["generation"] == 1
    assert execute_intent_sync(intent, WS_A, 1) == "blocked"
    with psycopg.connect(pg_dsn) as conn:
        assert conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                            (intent,)).fetchone()[0] == "failed"


def test_loop_marks_broker_outage_then_recovers_and_disposes(monkeypatch):
    import buyeros_worker.cli as cli

    class Engine:
        disposed = False
        async def dispose(self):
            self.disposed = True
    engine = Engine()
    states = []
    probes = iter([RuntimeError("broker down"), None])
    monkeypatch.setattr(cli, "create_engine", lambda: engine)
    def probe():
        failure = next(probes)
        if failure:
            raise failure
    monkeypatch.setattr(cli, "_broker_ready", probe)
    async def cycle(*args, **kwargs):
        return {"published": ["job:1"], "next_cursor": 1, "visited": 1}
    monkeypatch.setattr(cli, "dispatch_cycle", cycle)
    async def heartbeat(engine, owner, state):
        states.append(state)
    monkeypatch.setattr(cli, "_heartbeat", heartbeat)
    async def stop_after_recovery(delay):
        if len(states) == 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(cli.asyncio, "sleep", stop_after_recovery)
    monkeypatch.setattr(cli.random, "uniform", lambda a, b: 0)
    with pytest.raises(asyncio.CancelledError):
        cli._run_loop("fixture", 1, 5.0, 0.1)
    assert states == ["unavailable", "ready"]
    assert engine.disposed


def test_worker_engine_pool_is_bounded_per_event_loop(monkeypatch):
    import buyeros_worker.engine as engine_module
    import buyeros_api.settings as api_settings

    seen = {}
    def create(url, **options):
        seen.update(options)
        return object()
    monkeypatch.setattr(engine_module, "create_async_engine", create)
    monkeypatch.setattr(api_settings, "get_settings",
                        lambda: type("Settings", (), {"database_url": "postgresql://localhost/test"})())
    engine_module.create_engine()
    assert seen["pool_size"] == 2
    assert seen["max_overflow"] == 0
    assert seen["pool_pre_ping"] is True


def test_dispatcher_heartbeat_uses_least_privilege_worker_role(worker_database_url, pg_dsn, monkeypatch):
    import psycopg
    import buyeros_worker.cli as cli
    from buyeros_api.settings import get_settings
    from buyeros_worker.engine import create_engine

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        conn.execute("GRANT USAGE ON SCHEMA public TO buyeros_worker")
    worker_dsn = pg_dsn.replace("buyeros:buyeros", "buyeros_worker:test-only", 1)
    monkeypatch.setenv("BUYEROS_DATABASE_URL", worker_dsn)
    get_settings.cache_clear()
    async def beat():
        engine = create_engine()
        try:
            await cli._heartbeat(engine, "fixture", "ready")
        finally:
            await engine.dispose()
    try:
        asyncio.run(beat())
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute(
                "SELECT broker_state FROM worker_heartbeats WHERE worker_id='dispatcher:fixture'"
            ).fetchone() == ("ready",)
    finally:
        get_settings.cache_clear()
