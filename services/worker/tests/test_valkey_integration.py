import asyncio
import os
import shutil
import sys
import subprocess
import time
import uuid
from datetime import datetime, timezone

import pytest

from buyeros_worker.app import celery_app
from buyeros_worker.dispatcher import select_ready


def _integration_unavailable(message):
    if os.environ.get("BUYEROS_STRICT_INTEGRATION") == "1":
        pytest.fail("Disposable Valkey required: " + message)
    pytest.skip(message)


def _valkey_container():
    if shutil.which("docker") is None:
        _integration_unavailable("docker unavailable")
    name = f"buyeros-valkey-{uuid.uuid4().hex[:8]}"
    run = subprocess.run(
        ["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::6379", "valkey/valkey:8"],
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        _integration_unavailable(f"could not start valkey: {run.stderr.strip()}")
    return name


def test_broker_is_reachable_and_dispatcher_selection_is_pure():
    original = celery_app.conf.broker_url
    name = None
    try:
        name = _valkey_container()
        port_output = subprocess.run(["docker", "port", name, "6379"], capture_output=True, text=True).stdout.strip()
        if not port_output:
            _integration_unavailable(f"could not resolve valkey port for {name}")
        port = port_output.splitlines()[0].rsplit(":", 1)[1]
        celery_app.conf.broker_url = f"redis://127.0.0.1:{port}/0"
        for _ in range(15):
            try:
                with celery_app.connection() as conn:
                    conn.ensure_connection(max_retries=1)
            except Exception:
                time.sleep(1)
            else:
                break
        else:
            _integration_unavailable("valkey broker did not become ready")
        assert celery_app.conf.broker_url.endswith("/0")
        selected = select_ready(
            [{"id": 1, "state": "ready", "lease_expires_at": None}],
            datetime.now(timezone.utc),
        )
        assert selected[0]["id"] == 1
    finally:
        celery_app.conf.broker_url = original
        if name is not None:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)


def test_real_broker_delivers_dispatched_intent_to_celery_worker(worker_database_url, pg_dsn, tmp_path, monkeypatch):
    """The outbox publisher and a separate solo worker share one Valkey queue."""
    import psycopg

    from buyeros_worker.dispatcher import dispatch_cycle
    from buyeros_worker.engine import create_engine
    from buyeros_worker.tasks import publish_message
    from buyeros_worker.config import get_settings
    from tests.conftest import RUN_A, WS_A, reset_tenant, seed_outbox, seed_run

    # This fixture proves broker delivery to the deliberately blocked handler;
    # allow dispatch in the isolated test process, never select a paid adapter.
    monkeypatch.setenv("BUYEROS_PAID_DISPATCH_ENABLED", "true")
    get_settings.cache_clear()

    name = _valkey_container()
    original = celery_app.conf.broker_url
    worker = None
    log_path = tmp_path / "celery-worker.log"
    try:
        port_output = subprocess.run(["docker", "port", name, "6379"],
                                     capture_output=True, text=True, check=True).stdout.strip()
        port = port_output.splitlines()[0].rsplit(":", 1)[1]
        broker_url = f"redis://127.0.0.1:{port}/0"
        celery_app.conf.broker_url = broker_url
        intent = f"job:real-broker:{uuid.uuid4()}"
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            reset_tenant(conn)
            seed_run(conn)
            seed_outbox(
                conn, intent_key=intent, event_type="run.discover",
                payload={"run_id": RUN_A},
                state="ready",
            )
        env = os.environ.copy()
        env["BUYEROS_BROKER_URL"] = broker_url
        env["BUYEROS_EAGER"] = "false"
        env["BUYEROS_PAID_DISPATCH_ENABLED"] = "true"
        with log_path.open("wb") as log:
            worker = subprocess.Popen(
                [sys.executable, "-m", "celery", "-A", "buyeros_worker.tasks",
                 "worker", "--pool=solo", "--concurrency=1", "--loglevel=WARNING",
                 "--without-gossip", "--without-mingle", "--without-heartbeat"],
                env=env, cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]), stdout=log, stderr=subprocess.STDOUT,
            )
        async def send():
            engine = create_engine()
            try:
                return await dispatch_cycle(
                    engine, publish_message, "real-broker-test", datetime.now(timezone.utc),
                    max_total=1, time_budget_seconds=10.0,
                )
            finally:
                await engine.dispose()
        result = asyncio.run(send())
        assert result["published"] == [intent]
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            with psycopg.connect(pg_dsn) as conn:
                state = conn.execute("SELECT state FROM outbox_events WHERE intent_key=%s",
                                     (intent,)).fetchone()[0]
            if state == "failed":
                break
            if worker.poll() is not None:
                pytest.fail("Celery worker exited: " + log_path.read_text(errors="replace")[-3000:])
            time.sleep(0.5)
        else:
            pytest.fail("broker delivery timed out; worker log: "
                        + log_path.read_text(errors="replace")[-3000:])
        with psycopg.connect(pg_dsn) as conn:
            assert conn.execute("SELECT count(*) FROM run_events WHERE run_id=%s",
                                (RUN_A,)).fetchone()[0] == 1
    finally:
        get_settings.cache_clear()
        celery_app.conf.broker_url = original
        if worker is not None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=10)
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)
