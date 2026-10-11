"""Opt-in owned PG16 workloads; ordinary API discovery excludes this file."""
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.bulk_capacity_driver import reader, sample_api_resources
from tests.conftest import runtime_role_dsn
from tests.test_bulk_manifest_db import (
    api, buyer_api, _seed_many, _preview, _execute, _admin_membership, _h, WORKSPACE_A,
)

RESTART = """import asyncio,json,os,sys,uuid
if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from buyeros_api.api.deps import tenant_scoped,dispose_engines
from buyeros_api.services.bulk_service import apply_bulk_chunk
print(json.dumps({'ready_pid':os.getpid()}),flush=True)
assert sys.stdin.readline().strip()=='go'
async def resume():
 try:
  async with tenant_scoped(uuid.UUID(sys.argv[2])) as session:
   result=await apply_bulk_chunk(session,uuid.UUID(sys.argv[1]))
  print(json.dumps({'pid':os.getpid(),'processed':result['processed']}),flush=True)
 finally:await dispose_engines()
asyncio.run(resume())
"""


@pytest.mark.parametrize("count", [50, 500, 10000])
def test_owned_bulk_resources(api, seeded, count):
    output = os.environ.get("BUYEROS_BULK_CAPACITY_OUTPUT")
    assert output, "invoke the owned benchmark runner with a new output directory"
    path = Path(output) / f"capture-{count}.json"
    assert not path.exists(), "must retain previous evidence"
    _seed_many(seeded, count)
    owner = _admin_membership(seeded)
    runtime = runtime_role_dsn(seeded)
    with psycopg.connect(runtime) as db:
        role = db.execute("SELECT current_user,rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
    assert role == ("buyeros_api", False, False)
    report = dict(count=count, api_pid=os.getpid(), runtime_role=list(role), completed=False,
                  restart_pid=None, restart_owner_pid=None, memory_samples=[], queue_snapshots=[],
                  queue_mode="async_job_created_age" if count > 100 else "sync_no_queue",
                  requests=[], chunks=[], fixture_only=True, live_verified=False,
                  release_accepted=False, budget_adopted=False,
                  limitations=["single owned workload per dataset; no percentile or adopted budget",
                    "RSS samples after seeding; sampled maxima are not true peak/PSS/cgroup memory",
                    "API is in-process TestClient; RSS includes pytest/fixtures and prior datasets",
                    "async job created age is not broker dequeue latency; sync50 has no queue",
                    "restart after committed chunk and before-commit rollback; not broker inflight kill",
                    "SQL counts cover in-process SQLAlchemy only; child and observation SQL excluded",
                    "sampling overhead included; no remote provider/HK/sustained/field acceptance"])
    started = time.perf_counter()
    sql = 0
    def count_sql(*_):
        nonlocal sql
        sql += 1
    def sample():
        sample_api_resources(report["memory_samples"], time.perf_counter() - started)
    def request(kind, fn):
        at, before = time.perf_counter(), sql
        response = fn()
        report["requests"].append(dict(kind=kind, status=response.status_code, bytes=len(response.content),
                                       sql=sql-before, elapsed_ms=(time.perf_counter()-at)*1000))
        sample()
        return response
    def queue(job):
        with psycopg.connect(runtime) as db:
            db.execute("SELECT set_config('app.workspace_id',%s,true)", (WORKSPACE_A,))
            status, processed, age = db.execute(
                "SELECT status,processed,EXTRACT(EPOCH FROM clock_timestamp()-created_at) "
                "FROM async_jobs WHERE id=%s", (job,)).fetchone()
            pending = db.execute("SELECT count(*) FROM async_job_items WHERE job_id=%s AND status='pending'", (job,)).fetchone()[0]
        report["queue_snapshots"].append(dict(at_seconds=time.perf_counter()-started,
            status=status, processed=processed, pending=pending, job_created_age_seconds=float(age)))
    event.listen(Engine, "before_cursor_execute", count_sql)
    try:
        sample()
        manifest = _preview(api, owner)
        assert manifest["count"] == count
        sample()
        conflicts = 50 if count > 100 else 0
        if conflicts:
            with psycopg.connect(seeded) as db:
                stale = db.execute("SELECT buyer_id FROM bulk_manifest_items WHERE manifest_id=%s ORDER BY ordinal LIMIT 50", (manifest["id"],)).fetchall()
                db.cursor().executemany("UPDATE project_buyers SET version=version+1 WHERE id=%s", stale)
        key = str(uuid.uuid4())
        response = request("execute", lambda: _execute(api, manifest, key))
        assert response.status_code == (200 if count == 50 else 202), response.text
        replay = request("same-intent-replay", lambda: _execute(api, manifest, key))
        assert replay.status_code == response.status_code and replay.json()["data"] == response.json()["data"]
        if count == 50:
            result = response.json()["data"]
            assert (result["requested"], result["updated"], result["conflicts"]) == (50, 50, 0)
            assert len(result["results"]) == len({r["id"] for r in result["results"]}) == 50
        else:
            from buyeros_api.api.deps import tenant_scoped
            from buyeros_api.services.bulk_service import apply_bulk_chunk
            job = uuid.UUID(response.json()["data"]["id"])
            queue(job)
            async def chunk(rollback=False):
                at, before = time.perf_counter(), sql
                try:
                    async with tenant_scoped(uuid.UUID(WORKSPACE_A)) as session:
                        result = await apply_bulk_chunk(session, job)
                        assert result["processed"] <= 50
                        if rollback:
                            raise RuntimeError("owned before commit")
                except RuntimeError as cause:
                    assert str(cause) == "owned before commit"
                report["chunks"].append(dict(processed=result["processed"], rollback_injected=rollback,
                    elapsed_ms=(time.perf_counter()-at)*1000, sql=sql-before))
                sample()
                queue(job)
            async def drive():
                await chunk()
                await chunk(True)
                with psycopg.connect(seeded) as db:
                    assert db.execute("SELECT processed FROM async_jobs WHERE id=%s", (job,)).fetchone()[0] == 50
                    assert db.execute("SELECT count(*) FROM project_buyers WHERE owner_user_id IS NOT NULL AND workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 0
                child = subprocess.Popen([sys.executable, "-c", RESTART, str(job), WORKSPACE_A],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    ready = json.loads(child.stdout.readline())
                    report["restart_pid"] = ready["ready_pid"]
                    report["restart_owner_pid"] = child.pid
                    assert ready["ready_pid"] != os.getpid()
                    reader.sample_worker_resources([child], time.perf_counter()-started, report["memory_samples"])
                    child.stdin.write("go\n")
                    child.stdin.flush()
                    child.stdin.close()
                    child.stdin = None
                    deadline = time.monotonic() + 30
                    while child.poll() is None:
                        if time.monotonic() >= deadline:
                            raise subprocess.TimeoutExpired(child.args, 30)
                        try:
                            reader.sample_worker_resources([child], time.perf_counter()-started, report["memory_samples"])
                        except OSError:
                            if child.poll() is None:
                                raise
                        try:
                            child.wait(timeout=.1)
                        except subprocess.TimeoutExpired:
                            pass
                    stdout, stderr = child.communicate(timeout=5)
                    assert child.returncode == 0, stderr
                    receipt = json.loads(stdout)
                    assert receipt["pid"] == ready["ready_pid"] and receipt["processed"] == 50
                finally:
                    if child.poll() is None:
                        child.terminate()
                        child.communicate(timeout=10)
                sample()
                queue(job)
                for _ in range(count // 50 - 2):
                    await chunk()
                await chunk()  # Completed replay must apply no further changes.
                assert report["chunks"][-1]["processed"] == 0
            asyncio.run(drive())
            with psycopg.connect(seeded) as db:
                assert db.execute("SELECT requested,processed,updated,conflicts,status FROM async_jobs WHERE id=%s", (job,)).fetchone() == (count, count, count-50, 50, "completed")
                assert db.execute("SELECT count(*),count(DISTINCT buyer_id) FROM async_job_items WHERE job_id=%s", (job,)).fetchone() == (count, count)
            ids = []
            for offset in range(0, count, 100):
                page = request("result-page", lambda: api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}?offset={offset}&limit=100", headers=_h()))
                assert page.status_code == 200, page.text
                data = page.json()["data"]["result_page"]
                assert data["total"] == count and len(data["items"]) == 100
                ids.extend(r["id"] for r in data["items"])
            assert len(ids) == len(set(ids)) == count
            denial = request("blind-retry-denied", lambda: api.post(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}/retry-failed", json={}, headers=_h(key=str(uuid.uuid4()))))
            assert denial.status_code == 409 and denial.json()["code"] == "MANIFEST_REVIEW_REQUIRED"
            reviewed = _preview(api, owner, filters={}, source_job_id=str(job))
            assert reviewed["count"] == 50 and reviewed["digest"] != manifest["digest"]
            retry = request("reviewed-child", lambda: _execute(api, reviewed))
            assert retry.status_code == 200 and retry.json()["data"]["updated"] == 50, retry.text
            with psycopg.connect(seeded) as db:
                assert db.execute("SELECT count(*) FROM project_buyers WHERE version=2 AND workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == count-50
                assert db.execute("SELECT count(*) FROM project_buyers WHERE version=3 AND workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == 50
        with psycopg.connect(seeded) as db:
            assert db.execute("SELECT count(*) FROM audit_events WHERE action='buyer.owner_assigned' AND workspace_id=%s", (WORKSPACE_A,)).fetchone()[0] == count
        sample()
        report.update(completed=True, updated=count-conflicts, conflicts=conflicts,
                      distinct_results=count, reviewed_child_updated=conflicts)
    finally:
        event.remove(Engine, "before_cursor_execute", count_sql)
        report["duration_seconds"] = time.perf_counter()-started
        with path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
