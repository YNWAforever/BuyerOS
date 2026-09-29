"""One broker-delivered, cited fixture research result across a real worker process."""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from celery import Celery

from buyeros_worker.config import get_settings
from buyeros_worker.dispatcher import dispatch_cycle
from buyeros_worker.engine import create_engine
from tests.test_discovery_runner_db import INTENT, PROJECT_A, RUN_ID, WS_A, discovery_case
from tests.test_valkey_integration import _valkey_container


def test_t30_disposable_broker_worker_persists_cited_research(discovery_case, tmp_path, monkeypatch):
    owner_dsn, runtime_dsn = discovery_case
    with psycopg.connect(owner_dsn, autocommit=True) as db:
        db.execute("UPDATE outbox_events SET state='ready' WHERE intent_key=%s", (INTENT,))
    broker_name = _valkey_container()
    worker = None
    publisher_app = None
    log_path = Path(tmp_path) / "t30-fixture-worker.log"
    try:
        port_result = subprocess.run(["docker", "port", broker_name, "6379"],
                                     capture_output=True, text=True, timeout=15, check=True)
        port = port_result.stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        broker_url = f"redis://127.0.0.1:{port}/0"
        publisher_app = Celery("t30_fixture_publisher", broker=broker_url)
        monkeypatch.setenv("BUYEROS_BROKER_URL", broker_url)
        monkeypatch.setenv("BUYEROS_PAID_DISPATCH_ENABLED", "true")
        get_settings.cache_clear()
        env = os.environ.copy()
        env.update({"BUYEROS_DATABASE_URL": runtime_dsn,
                    "BUYEROS_TEST_OWNER_DSN": owner_dsn,
                    "BUYEROS_BROKER_URL": broker_url,
                    "BUYEROS_EAGER": "false"})
        with log_path.open("wb") as log:
            worker = subprocess.Popen(
                [sys.executable, "-m", "celery", "-A", "tests.fixtures.t30_celery:celery_app",
                 "worker", "--pool=solo", "--concurrency=1", "--loglevel=INFO",
                 "--without-gossip", "--without-mingle", "--without-heartbeat"],
                cwd=str(Path(__file__).resolve().parents[1]), env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
        def publish_message(message):
            publisher_app.send_task("buyeros.execute_intent",
                                    args=[message["intent_key"], message["workspace_id"], message["generation"]])

        async def publish():
            engine = create_engine()
            try:
                return await dispatch_cycle(engine, publish_message, "t30-research-fixture",
                                            datetime.now(timezone.utc), max_total=1,
                                            time_budget_seconds=10.0)
            finally:
                await engine.dispose()
        result = asyncio.run(publish())
        assert result["published"] == [INTENT]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            with psycopg.connect(owner_dsn) as db:
                evidence = db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (RUN_ID,)).fetchone()[0]
                state = db.execute("SELECT state FROM outbox_events WHERE intent_key=%s", (INTENT,)).fetchone()[0]
            if evidence == 1 and state == "done":
                break
            if worker.poll() is not None:
                pytest.fail("Fixture Celery exited: " + log_path.read_text(errors="replace")[-3000:])
            time.sleep(0.5)
        else:
            pytest.fail(f"Broker research timed out: state={state}, evidence={evidence}, "
                        f"worker_alive={worker.poll() is None}; log=" +
                        log_path.read_text(errors="replace")[-5000:])
        with psycopg.connect(owner_dsn) as db:
            assert db.execute("SELECT count(*) FROM project_buyers WHERE project_id=%s", (PROJECT_A,)).fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM raw_candidates WHERE run_id=%s", (RUN_ID,)).fetchone()[0] == 1
            assert db.execute("SELECT amount FROM cost_events WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.050000")
            assert db.execute("SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s", (WS_A,)).fetchone()[0] == Decimal("0.000000")
    finally:
        get_settings.cache_clear()
        if publisher_app is not None:
            publisher_app.close()
        if worker is not None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=10)
        subprocess.run(["docker", "rm", "-f", broker_name],
                       capture_output=True, text=True, timeout=30)