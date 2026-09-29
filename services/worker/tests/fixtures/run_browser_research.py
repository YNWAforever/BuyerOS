"""Run one UI-created research intent through disposable Valkey and a test-only Celery worker."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

import psycopg
from celery import Celery

ROOT = Path(__file__).resolve().parents[4]
WORKSPACE = uuid.UUID("e0000000-0000-4000-8000-000000000001")


def docker(*args: str, timeout: int = 30) -> str:
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"disposable Docker command failed: {args[0]} {result.stderr[-300:]}")
    return result.stdout.strip()


def owner_dsn() -> str:
    marker = ROOT / "test-results" / "e2e-db-container.txt"
    name = marker.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"buyeros-test-[0-9a-f]{8}", name):
        raise RuntimeError("refusing unrecognized disposable database name")
    info = json.loads(docker("inspect", name))[0]
    if (info["Name"] != "/" + name or info["Config"]["Image"] != "postgres:16"
            or "POSTGRES_DB=buyeros_test_api" not in info["Config"]["Env"]
            or any(mount["Type"] != "volume" for mount in info["Mounts"])):
        raise RuntimeError("refusing non-fixture database container")
    mapping = docker("port", name, "5432").splitlines()[0]
    host, port = mapping.rsplit(":", 1)
    if host != "127.0.0.1" or not port.isdecimal():
        raise RuntimeError("refusing non-loopback database port")
    return f"postgresql://buyeros:buyeros@127.0.0.1:{port}/buyeros_test_api"


def main() -> None:
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: run_browser_research.py RUN_ID PROJECT_ID [DRAFT_JOB_ID]")
    run_id, project_id = (uuid.UUID(value) for value in sys.argv[1:3])
    draft_job_id = uuid.UUID(sys.argv[3]) if len(sys.argv) == 4 else None
    dsn = owner_dsn()
    runtime_dsn = dsn.replace("buyeros:buyeros", "buyeros_api:test-only", 1)
    with psycopg.connect(dsn) as db:
        row = db.execute("SELECT project_id FROM search_runs WHERE id=%s AND workspace_id=%s",
                         (run_id, WORKSPACE)).fetchone()
        if row is None or row[0] != project_id:
            raise RuntimeError("UI run is absent or belongs to another fixture project")
    if draft_job_id is not None:
        with psycopg.connect(dsn) as db:
            job = db.execute("SELECT project_id,operation FROM async_jobs WHERE id=%s AND workspace_id=%s",
                             (draft_job_id, WORKSPACE)).fetchone()
            if job is None or job != (project_id, "generateDraft"):
                raise RuntimeError("UI draft job is absent or belongs to another fixture project")
    broker_name = f"buyeros-t30-valkey-{uuid.uuid4().hex[:8]}"
    broker_created = False
    worker = None
    publisher = None
    log_path = ROOT / "test-results" / ("t30-browser-draft-worker.log" if draft_job_id else "t30-browser-worker.log")
    try:
        docker("run", "-d", "--name", broker_name, "-p", "127.0.0.1::6379", "valkey/valkey:8", timeout=60)
        broker_created = True
        mapping = docker("port", broker_name, "6379").splitlines()[0]
        host, port = mapping.rsplit(":", 1)
        if host != "127.0.0.1" or not port.isdecimal():
            raise RuntimeError("refusing non-loopback Valkey port")
        broker_url = f"redis://127.0.0.1:{port}/0"
        env = os.environ.copy()
        env.update({"BUYEROS_DATABASE_URL": runtime_dsn,
                    "BUYEROS_TEST_OWNER_DSN": dsn,
                    "BUYEROS_BROKER_URL": broker_url,
                    "BUYEROS_PAID_DISPATCH_ENABLED": "true",
                    "BUYEROS_T30_GENERIC_SEARCH": "1",
                    "BUYEROS_EAGER": "false"})
        os.environ.update({key: env[key] for key in ("BUYEROS_DATABASE_URL", "BUYEROS_BROKER_URL", "BUYEROS_PAID_DISPATCH_ENABLED")})
        from buyeros_worker.config import get_settings
        from buyeros_worker.dispatcher import dispatch_cycle
        from buyeros_worker.engine import create_engine
        get_settings.cache_clear()
        publisher = Celery("t30_browser_publisher", broker=broker_url)
        def publish(message):
            publisher.send_task("buyeros.execute_intent",
                                args=[message["intent_key"], message["workspace_id"], message["generation"]])
        with log_path.open("wb") as log:
            worker = subprocess.Popen(
                [sys.executable, "-m", "celery", "-A", "tests.fixtures.t30_celery:celery_app",
                 "worker", "--pool=solo", "--concurrency=1", "--loglevel=INFO",
                 "--without-gossip", "--without-mingle", "--without-heartbeat"],
                cwd=str(ROOT / "services" / "worker"), env=env,
                stdout=log, stderr=subprocess.STDOUT,
            )
        async def cycle():
            engine = create_engine()
            try:
                return await dispatch_cycle(engine, publish, "t30-browser-fixture",
                                            datetime.now(timezone.utc), max_total=5,
                                            time_budget_seconds=5.0)
            finally:
                await engine.dispose()
        deadline = time.monotonic() + 120
        published = []
        while time.monotonic() < deadline:
            result = (asyncio.run(cycle(), loop_factory=asyncio.SelectorEventLoop)
                      if sys.platform == "win32" else asyncio.run(cycle()))
            published.extend(result["published"])
            with psycopg.connect(dsn) as db:
                if draft_job_id is not None:
                    job = db.execute("SELECT status,command FROM async_jobs WHERE id=%s", (draft_job_id,)).fetchone()
                    if job is None:
                        raise RuntimeError("fixture draft job disappeared")
                    status = job[0]
                    draft_id = job[1].get("result_draft_id")
                    content = (db.execute("SELECT r.content FROM draft_revisions r JOIN outreach_drafts d "
                                          "ON d.workspace_id=r.workspace_id AND d.id=r.draft_id "
                                          "WHERE d.id=%s AND d.project_id=%s AND r.revision_number=1",
                                          (uuid.UUID(draft_id), project_id)).fetchone()
                               if draft_id else None)
                else:
                    evidence = db.execute("SELECT count(*) FROM evidence WHERE run_id=%s", (run_id,)).fetchone()[0]
                    buyers = db.execute("SELECT count(*) FROM project_buyers WHERE project_id=%s", (project_id,)).fetchone()[0]
                    status = db.execute("SELECT status FROM search_runs WHERE id=%s", (run_id,)).fetchone()[0]
                    fit_verdicts = [row[0] for row in db.execute("SELECT verdict FROM fit_assessments WHERE run_id=%s", (run_id,)).fetchall()]
            if draft_job_id is not None:
                if status == "failed":
                    with psycopg.connect(dsn) as db:
                        reason = db.execute("SELECT reason_code FROM async_job_items WHERE job_id=%s", (draft_job_id,)).fetchone()
                    raise RuntimeError(f"fixture draft failed: reason={reason}")
                if status == "completed" and content is not None:
                    print(json.dumps({"job_id": str(draft_job_id), "status": status,
                                      "draft_id": draft_id,
                                      "grounding_status": content[0].get("grounding_status"),
                                      "published": published}))
                    return
            else:
                if status in {"partial", "failed", "blocked", "cancelled", "paused_budget"}:
                    with psycopg.connect(dsn) as db:
                        latest = db.execute("SELECT event_type,payload FROM run_events WHERE run_id=%s ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
                    raise RuntimeError(f"fixture research halted: status={status}, event={latest}")
                if evidence >= 1 and buyers >= 1 and status == "completed":
                    print(json.dumps({"run_id": str(run_id), "status": status,
                                      "evidence": evidence, "buyers": buyers, "fit_verdicts": fit_verdicts,
                                      "published": published}))
                    return
            if worker.poll() is not None:
                raise RuntimeError("fixture worker exited: " + log_path.read_text(errors="replace")[-2500:])
            time.sleep(0.7)
        if draft_job_id is not None:
            raise RuntimeError(f"fixture draft timed out: status={status}, published={published}; worker=" +
                               log_path.read_text(errors="replace")[-2500:])
        raise RuntimeError(f"fixture research timed out: status={status}, evidence={evidence}, "
                           f"buyers={buyers}, published={published}; worker=" +
                           log_path.read_text(errors="replace")[-2500:])
    finally:
        if publisher is not None:
            publisher.close()
        if worker is not None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=10)
        if broker_created:
            docker("rm", "-f", broker_name, timeout=30)


if __name__ == "__main__":
    main()