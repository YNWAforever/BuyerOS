"""Opt-in T29 dispatcher fairness benchmark with disposable PostgreSQL and Valkey."""

import asyncio
import json
import os
import platform
import statistics
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from buyeros_worker.app import celery_app
from buyeros_worker.dispatcher import dispatch_cycle
from buyeros_worker.engine import create_engine
from buyeros_worker.tasks import publish_message
from tests.conftest import WS_A, WS_B, seed_outbox
from tests.test_valkey_integration import _valkey_container


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)


def test_ready_to_real_broker_across_100_workspaces(worker_database_url, pg_dsn):
    prefix = f"t29fair:{uuid.uuid4().hex}:"
    extra = [str(uuid.uuid4()) for _ in range(98)]
    workspaces = [WS_A, WS_B, *extra]
    expected = {f"{prefix}{index}" for index in range(100)}
    name = None
    original_broker = celery_app.conf.broker_url
    published_at: dict[str, datetime] = {}
    try:
        name = _valkey_container()
        port_result = subprocess.run(["docker", "port", name, "6379"],
                                     capture_output=True, text=True, check=True, timeout=15)
        port = port_result.stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        celery_app.conf.broker_url = f"redis://127.0.0.1:{port}/0"
        for _ in range(15):
            try:
                with celery_app.connection() as broker:
                    broker.ensure_connection(max_retries=1)
            except Exception:
                time.sleep(1)
            else:
                break
        else:
            raise AssertionError("disposable Valkey did not become ready")
        with psycopg.connect(pg_dsn, autocommit=True) as db:
            for index, workspace_id in enumerate(extra, start=2):
                db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,%s,'live')",
                           (workspace_id, f"Fairness fixture {index}"))
            for index, workspace_id in enumerate(workspaces):
                seed_outbox(db, workspace_id=workspace_id, intent_key=f"{prefix}{index}",
                            event_type="source.delete", payload={"source_document_id": str(uuid.uuid4())})
            ready_at = datetime.now(timezone.utc)
            db.execute("UPDATE outbox_events SET created_at=%s WHERE intent_key LIKE %s",
                       (ready_at, prefix + "%"))
        def publish(message):
            publish_message(message)
            published_at[message["intent_key"]] = datetime.now(timezone.utc)
        async def cycle_until_all():
            engine = create_engine()
            try:
                cursor = 0
                cycles = 0
                visited = 0
                deadline = time.monotonic() + 30
                while len(published_at) < 100 and time.monotonic() < deadline:
                    result = await dispatch_cycle(
                        engine, publish, "t29-benchmark", datetime.now(timezone.utc),
                        max_total=100, time_budget_seconds=5, cursor=cursor,
                    )
                    cursor = result["next_cursor"]
                    visited += result["visited"]
                    cycles += 1
                    if not result["published"]:
                        break
                return cycles, visited
            finally:
                await engine.dispose()
        cycles, visited = asyncio.run(cycle_until_all())
        assert set(published_at) == expected, f"published {len(published_at)}/100 unique workspace intents"
        ages = [(published_at[f"{prefix}{i}"] - ready_at).total_seconds() for i in range(100)]
        assert all(age >= 0 for age in ages)
        result = {
            "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "machine": platform.platform(),
            "conditions": {"database": "disposable PostgreSQL 16 Docker", "broker": "disposable Valkey 8 Docker",
                           "worker_process": "not started; publish_message enqueues to real broker",
                           "event_type": "source.delete non-paid fixture", "workspaces": 100,
                           "ready_intents": 100, "dispatcher_time_budget_seconds_per_cycle": 5},
            "published_unique": len(published_at), "cycles": cycles, "visited": visited,
            "ready_to_publish_seconds": {"p50": round(statistics.median(ages), 3),
                                         "p95": round(_percentile(ages, .95), 3),
                                         "max": round(max(ages), 3)},
            "every_workspace_progressed": True,
        }
        artifact = Path(os.environ["BUYEROS_DISPATCH_BENCH_OUTPUT"])
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        celery_app.conf.broker_url = original_broker
        with psycopg.connect(pg_dsn, autocommit=True) as db:
            db.execute("DELETE FROM outbox_events WHERE intent_key LIKE %s", (prefix + "%",))
            db.execute("DELETE FROM workspaces WHERE id = ANY(%s)", (extra,))
        if name is not None:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True, timeout=20)