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


def prepare_browser_runtime(dsn: str) -> str:
    """Explicit fixture operator setup after the caller proves container ownership."""
    from tests.conftest import _require_disposable_test_dsn
    from buyeros_api.services.worker_recovery import set_execution_runtime
    from buyeros_api.services.worker_execution import WORKER_ROLE_CATALOG_SQL
    from urllib.parse import urlsplit, urlunsplit
    _require_disposable_test_dsn(dsn)
    with psycopg.connect(dsn, autocommit=True) as owner:
        backend, enabled, epoch = owner.execute('SELECT backend,enabled,epoch FROM worker_runtime_control').fetchone()
        if backend != 'celery':
            raise ValueError('legacy fixture must not change another selected backend')
        owner.execute("""DO $$ BEGIN
          IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='buyeros_browser_worker_fixture') THEN
            CREATE ROLE buyeros_browser_worker_fixture NOBYPASSRLS IN ROLE buyeros_worker;
          END IF;
        END $$""")
        owner.execute("ALTER ROLE buyeros_browser_worker_fixture LOGIN PASSWORD 'test-only'")
    parts = urlsplit(dsn)
    runtime = urlunsplit(parts._replace(netloc=f'buyeros_browser_worker_fixture:test-only@127.0.0.1:{parts.port}'))
    with psycopg.connect(runtime) as db:
        if db.execute(WORKER_ROLE_CATALOG_SQL).fetchone() != (True,):
            raise ValueError('fixture worker catalog proof failed')
    if not enabled:
        set_execution_runtime(dsn, expected_epoch=epoch, backend='celery', enabled=True,
                              reason='Explicit owned compatibility browser fixture', apply=True)
    return runtime


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: c61_joined_unknown_research.py RUN_ID PROJECT_ID unknown|accepted")
    run_id, project_id = (uuid.UUID(value) for value in sys.argv[1:3])
    phase=sys.argv[3];assert phase in {'unknown','accepted'}
    draft_job_id=None
    directory=ROOT/'test-results/c61-joined-search'/str(run_id);directory.mkdir(parents=True,exist_ok=True)
    journal=directory/'accepted.json'
    assert (not journal.exists()) if phase=='unknown' else journal.exists()
    dsn = owner_dsn()
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
    runtime_dsn = prepare_browser_runtime(dsn)
    broker_name = f"buyeros-t30-valkey-{uuid.uuid4().hex[:8]}"
    broker_created = False
    worker = None
    publisher = None
    log_path=directory/(phase+'-celery.log')
    assert not log_path.exists()
    try:
        docker("run", "-d", "--pull", "never", "--label", "buyeros.c61.fixture=joined-unknown:"+str(run_id), "--name", broker_name, "-p", "127.0.0.1::6379", "valkey/valkey:8", timeout=60)
        broker_created = True
        mapping = docker("port", broker_name, "6379").splitlines()[0]
        host, port = mapping.rsplit(":", 1)
        if host != "127.0.0.1" or not port.isdecimal():
            raise RuntimeError("refusing non-loopback Valkey port")
        broker_url = f"redis://127.0.0.1:{port}/0"
        env = os.environ.copy()
        env.update(BUYEROS_T30_ACCEPTED_UNKNOWN_RUN_ID=str(run_id),BUYEROS_T30_ACCEPTED_UNKNOWN_PROJECT_ID=str(project_id),BUYEROS_T30_ACCEPTED_UNKNOWN_PHASE=phase,BUYEROS_T30_ACCEPTED_UNKNOWN_JOURNAL=str(journal))
        env.update({"BUYEROS_DATABASE_URL": runtime_dsn,
                    "BUYEROS_TEST_OWNER_DSN": dsn,
                    "BUYEROS_BROKER_URL": broker_url,
                    "BUYEROS_PAID_DISPATCH_ENABLED": "true",
                    "BUYEROS_CELERY_EXECUTION_ENABLED": "true",
                    "BUYEROS_CHECKPOINT_DATABASE_URL": runtime_dsn,
                    "BUYEROS_T30_GENERIC_SEARCH": "1",
                    "BUYEROS_EAGER": "false"})
        os.environ.update({key: env[key] for key in ("BUYEROS_DATABASE_URL", "BUYEROS_BROKER_URL", "BUYEROS_PAID_DISPATCH_ENABLED", "BUYEROS_CELERY_EXECUTION_ENABLED")})
        from buyeros_worker.config import get_settings
        from buyeros_worker.dispatcher import dispatch_cycle
        from buyeros_worker.engine import create_engine
        get_settings.cache_clear()
        publisher = Celery("t30_browser_publisher", broker=broker_url)
        def publish(message):
            publisher.send_task("buyeros.execute_intent",
                                args=[message["intent_key"], message["workspace_id"], message["generation"]])
        worker_executable=sys.executable
        if sys.platform=='win32':
            worker_executable=sys._base_executable;env['__PYVENV_LAUNCHER__']=sys.executable
        with log_path.open("xb") as log:
            worker = subprocess.Popen(
                [worker_executable, "-m", "celery", "-A", "tests.fixtures.c61_joined_unknown_celery:celery_app",
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
        published=[];initial_dispatch=False
        while time.monotonic() < deadline:
            if phase=='unknown':
                with psycopg.connect(dsn) as db:
                    state=db.execute('SELECT status FROM search_runs WHERE id=%s AND workspace_id=%s AND project_id=%s',(run_id,WORKSPACE,project_id)).fetchone()[0]
                    rows=db.execute("SELECT o.id,o.intent_key,o.status,r.id,r.upper_bound,r.remaining_hold,r.state FROM provider_operations o JOIN budget_reservations r ON r.operation_id=o.id AND r.workspace_id=o.workspace_id WHERE o.workspace_id=%s AND o.intent_key LIKE %s",(WORKSPACE,'research:'+str(run_id)+':%')).fetchall()
                if state in {'awaiting_reconciliation','partial'} and rows:
                    assert journal.exists() and len(rows)==1 and rows[0][2] in {'unknown','unknown_acceptance'} and rows[0][4]==rows[0][5]>0 and rows[0][6]=='active'
                    assert not journal.with_name('status.json').exists()
                    assert worker.pid==json.loads(journal.read_bytes())['native_submit_worker_pid']
                    print(json.dumps(dict(fixture_only=True,run_id=str(run_id),project_id=str(project_id),status=state,original_unknown=[str(v) for v in rows[0]],original_hold_preserved=True,submit_count=1,status_count=0,published=published,native_submit_worker_pid=json.loads(journal.read_bytes())['native_submit_worker_pid'])))
                    return
            result=({'published':[]} if phase=='unknown' and initial_dispatch else (asyncio.run(cycle(),loop_factory=asyncio.SelectorEventLoop) if sys.platform=='win32' else asyncio.run(cycle())))
            initial_dispatch=True
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
                pending_original_unknown=False
                if phase in {'unknown','accepted'} and status=='partial' and journal.exists():
                    provider=json.loads(journal.read_bytes())
                    with psycopg.connect(dsn) as db:
                        binding=db.execute("SELECT o.status,r.upper_bound,r.remaining_hold,r.state FROM provider_operations o JOIN budget_reservations r ON r.operation_id=o.id AND r.workspace_id=o.workspace_id WHERE o.workspace_id=%s AND o.intent_key=%s",(WORKSPACE,provider['intent_key'])).fetchall()
                        latest=db.execute("SELECT event_type,payload FROM run_events WHERE run_id=%s ORDER BY sequence DESC LIMIT 1",(run_id,)).fetchone()
                    # The worker can commit unknown between the top/bottom reads.
                    # Wait only for this exact original full-hold partial; next
                    # loop observes it or its status reconciliation. Other halts fail.
                    pending_original_unknown=(len(binding)==1 and binding[0][0]=='unknown' and binding[0][1]==binding[0][2]>0 and binding[0][3]=='active' and latest[0]=='run.partial' and latest[1].get('stage')=='reconciliation_required' and latest[1].get('reason')=='provider_acceptance_unknown')
                if status in {"partial", "failed", "blocked", "cancelled", "paused_budget"} and not pending_original_unknown:
                    with psycopg.connect(dsn) as db:
                        latest = db.execute("SELECT event_type,payload FROM run_events WHERE run_id=%s ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
                    raise RuntimeError(f"fixture research halted: status={status}, event={latest}")
                if evidence >= 1 and buyers >= 1 and status == "completed":
                    provider=json.loads(journal.read_bytes());observation=json.loads(journal.with_name('status.json').read_bytes());assert provider['native_submit_worker_pid']!=observation['native_status_worker_pid'] and worker.pid==observation['native_status_worker_pid']
                    with psycopg.connect(dsn) as db:
                        bindings=db.execute("SELECT o.id,o.intent_key,o.status,r.id,r.upper_bound,r.remaining_hold,r.state FROM provider_operations o JOIN budget_reservations r ON r.operation_id=o.id AND r.workspace_id=o.workspace_id WHERE o.workspace_id=%s AND o.intent_key=%s",(WORKSPACE,provider['intent_key'])).fetchall()
                        cost=db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s AND operation_id=%s',(WORKSPACE,bindings[0][0])).fetchone()[0]
                    assert len(bindings)==1 and bindings[0][2]=='settled' and bindings[0][5]==0 and cost==1
                    print(json.dumps(dict(fixture_only=True,run_id=str(run_id),project_id=str(project_id),status=status,evidence=evidence,buyers=buyers,fit_verdicts=fit_verdicts,published=published,original_resolved=[str(v) for v in bindings[0]],submit_count=1,status_count=1,native_submit_worker_pid=provider['native_submit_worker_pid'],native_status_worker_pid=observation['native_status_worker_pid'],billing_events=cost,blind_resubmits=0,real_provider=False)))
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
