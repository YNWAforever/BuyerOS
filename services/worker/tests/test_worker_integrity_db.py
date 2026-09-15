"""DB-backed integrity tests for the worker/dispatcher (RLS runtime role).

Each test runs the real worker code against the disposable PostgreSQL from
``tests/conftest.py`` as the least-privilege ``buyeros_api`` role.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

from buyeros_worker.dispatcher import dispatch_once, sweep_once
from buyeros_worker.engine import create_engine
from buyeros_worker.tasks import execute_intent_sync
from tests.conftest import RUN_A, WS_A, WS_B, reset_tenant, seed_outbox, seed_run

NOW = datetime.now(timezone.utc)


def _scalar(conn, sql, *params):
    return conn.execute(sql, params).fetchone()[0]


async def _dispatch(publish, now, *, limit=10, lease_seconds=60):
    engine = create_engine()
    try:
        return await dispatch_once(engine, publish, "test-dispatcher", now, limit, lease_seconds)
    finally:
        await engine.dispose()


async def _sweep(publish, now, *, limit=10, lease_seconds=60):
    engine = create_engine()
    try:
        return await sweep_once(engine, publish, "test-sweeper", now, limit, lease_seconds)
    finally:
        await engine.dispose()


def test_fencing_rejects_a_stale_generation_with_no_writes(worker_database_url, pg_dsn):
    intent = "job:fence"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_run(conn)
        seed_outbox(
            conn,
            intent_key=intent,
            payload={"url": "https://example.com/x", "content_type": "text/html", "size": 10, "run_id": RUN_A},
            state="dispatched",
            generation=1,
            lease_expires_at=NOW + timedelta(hours=1),
        )

    assert execute_intent_sync(intent, WS_A, 0) == "stale"

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert _scalar(conn, "SELECT count(*) FROM run_events WHERE run_id = %s", RUN_A) == 0
        assert conn.execute(
            "SELECT state, fencing_generation FROM outbox_events WHERE intent_key = %s", (intent,)
        ).fetchone() == ("dispatched", 1)

    # The generation the worker presents is what decides; the matching one works.
    assert execute_intent_sync(intent, WS_A, 1) == "done"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "done"


def test_duplicate_delivery_of_a_terminal_intent_is_a_noop(worker_database_url, pg_dsn):
    intent = "job:duplicate"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_run(conn)
        seed_outbox(
            conn,
            intent_key=intent,
            event_type="run.discover",
            payload={"run_id": RUN_A},
            state="dispatched",
            generation=1,
            lease_expires_at=NOW + timedelta(hours=1),
        )

    assert execute_intent_sync(intent, WS_A, 1) == "blocked"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "failed"
        assert _scalar(conn, "SELECT count(*) FROM run_events WHERE run_id = %s", RUN_A) == 1

    assert execute_intent_sync(intent, WS_A, 1) == "duplicate"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert _scalar(conn, "SELECT count(*) FROM run_events WHERE run_id = %s", RUN_A) == 1
        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "failed"


def test_expired_in_progress_intent_is_reclaimed_and_reenqueued(worker_database_url, pg_dsn):
    intent = "job:sweep"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_outbox(
            conn,
            intent_key=intent,
            payload={"url": "https://example.com/x", "content_type": "text/html", "size": 1},
            state="ready",
        )

    published = []
    base = datetime.now(timezone.utc)

    assert asyncio.run(_dispatch(published.append, base)) == [intent]
    # A fresh lease is not re-dispatched.
    assert asyncio.run(_dispatch(published.append, base + timedelta(seconds=5))) == []
    # The publish was "lost" (process died between commit and enqueue). After the
    # lease expires the sweeper re-enqueues it exactly once for the cycle.
    assert asyncio.run(_sweep(published.append, base + timedelta(seconds=61))) == [intent]
    assert asyncio.run(_sweep(published.append, base + timedelta(seconds=62))) == []

    assert [message["intent_key"] for message in published] == [intent, intent]
    assert [message["generation"] for message in published] == [1, 2]
    assert set(published[0]) == {"intent_key", "workspace_id", "generation"}


def test_dispatcher_claims_each_workspace_under_its_own_tenant_context(worker_database_url, pg_dsn):
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn, WS_A)
        reset_tenant(conn, WS_B)
        seed_outbox(conn, intent_key="job:a", payload={"url": "https://a.example"}, workspace_id=WS_A)
        seed_outbox(conn, intent_key="job:b", payload={"url": "https://b.example"}, workspace_id=WS_B)

    published = []
    asyncio.run(_dispatch(published.append, datetime.now(timezone.utc)))

    by_intent = {message["intent_key"]: message["workspace_id"] for message in published}
    assert by_intent == {"job:a": WS_A, "job:b": WS_B}


def test_blocked_handler_emits_exactly_one_event_and_makes_no_external_call(worker_database_url, pg_dsn):
    import buyeros_worker.handlers.capability_blocked as capability_blocked

    intent = "job:blocked"
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        reset_tenant(conn)
        seed_run(conn, status="running")
        seed_outbox(
            conn,
            intent_key=intent,
            event_type="run.discover",
            payload={"run_id": RUN_A, "target_companies": 5},
            state="dispatched",
            generation=1,
            lease_expires_at=NOW + timedelta(hours=1),
        )

    assert execute_intent_sync(intent, WS_A, 1) == "blocked"

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "failed"
        assert _scalar(conn, "SELECT status FROM search_runs WHERE id = %s", RUN_A) == "blocked"
        events = conn.execute(
            "SELECT event_type, sequence, payload FROM run_events WHERE run_id = %s ORDER BY sequence", (RUN_A,)
        ).fetchall()

    assert len(events) == 1
    assert events[0][0] == "capability_blocked"
    assert events[0][1] == 1
    assert events[0][2]["event_type"] == "run.discover"

    # No provider client is imported anywhere in the fail-closed handler.
    source = Path(capability_blocked.__file__).read_text(encoding="utf-8")
    for forbidden in ("http", "urllib", "requests", "socket", "httpx", "aiohttp"):
        assert forbidden not in source, forbidden
