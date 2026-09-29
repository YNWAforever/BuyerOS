"""Opt-in T29 persisted-write/admission benchmark on disposable PostgreSQL only."""

import asyncio
import json
import os
import platform
import statistics
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import psycopg
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests import auth_fixtures as fx
from tests.test_api_projects_db import OPERATOR, WORKSPACE_A, api as project_api
from tests.test_run_admission_integration_db import PROJECT_A, _request, admission_case

SAMPLES = 20
WARMUPS = 3


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def test_persisted_mutation_and_job_admission_latency(admission_case):
    api, dsn = admission_case
    buyer_ids = []
    company_ids = []
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("UPDATE budget_accounts SET approved_limit=100 WHERE workspace_id=%s", (WORKSPACE_A,))
        for number in range(SAMPLES + WARMUPS):
            company_id, buyer_id = uuid.uuid4(), uuid.uuid4()
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
                       "VALUES (%s,%s,%s,%s)",
                       (company_id, WORKSPACE_A, f"T29 fictional buyer {number}", f"T29 fictional buyer {number}"))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) "
                       "VALUES (%s,%s,%s,%s)", (buyer_id, WORKSPACE_A, PROJECT_A, company_id))
            buyer_ids.append(str(buyer_id))
            company_ids.append(company_id)
    bearer = f"Bearer {fx.make_token(sub=OPERATOR)}"
    query_count = 0
    def count_query(*_args):
        nonlocal query_count
        query_count += 1
    target = f"/v1/workspaces/{WORKSPACE_A}"
    async def measure():
        transport = httpx.ASGITransport(app=api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async def mutate(number: int):
                headers = {"Authorization": bearer, "Idempotency-Key": f"t29-mutate-{number}",
                           "If-Match": '"1"'}
                started = time.perf_counter()
                response = await client.patch(target + f"/buyers/{buyer_ids[number]}",
                                              json={"note": f"T29 fixture note {number}"}, headers=headers)
                elapsed = (time.perf_counter() - started) * 1000
                assert response.status_code == 200, response.text
                assert response.json()["data"]["version"] == 2
                return elapsed, len(response.content)
            async def admit(number: int):
                headers = {"Authorization": bearer, "Idempotency-Key": f"t29-admit-{number}"}
                started = time.perf_counter()
                response = await client.post(target + f"/projects/{PROJECT_A}/runs",
                                             json=_request(), headers=headers)
                elapsed = (time.perf_counter() - started) * 1000
                assert response.status_code == 202, response.text
                assert response.json()["data"]["status"] == "queued"
                return elapsed, len(response.content)
            for number in range(WARMUPS):
                await mutate(number)
                await admit(number)
            event.listen(Engine, "before_cursor_execute", count_query)
            try:
                mutations = [await mutate(number) for number in range(WARMUPS, SAMPLES + WARMUPS)]
                mutation_query_count = query_count
                admissions = [await admit(number) for number in range(WARMUPS, SAMPLES + WARMUPS)]
                admission_query_count = query_count - mutation_query_count
            finally:
                event.remove(Engine, "before_cursor_execute", count_query)
            return mutations, admissions, mutation_query_count, admission_query_count
    mutations, admissions, mutation_query_count, admission_query_count = asyncio.run(measure())
    with psycopg.connect(dsn) as db:
        run_count, pending_dispatch = db.execute(
            "SELECT count(*),count(*) FILTER (WHERE first_dispatch_at IS NULL) "
            "FROM search_runs WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()
        buyer_count = db.execute(
            "SELECT count(*) FROM project_buyers WHERE workspace_id=%s AND version=2",
            (WORKSPACE_A,)).fetchone()[0]
        outbox_count = db.execute(
            "SELECT count(*) FROM outbox_events WHERE workspace_id=%s", (WORKSPACE_A,)).fetchone()[0]
    assert buyer_count == run_count == pending_dispatch == outbox_count == SAMPLES + WARMUPS
    def metrics(rows):
        values = [row[0] for row in rows]
        return {"p50": round(statistics.median(values), 3),
                "p95": round(percentile(values, .95), 3),
                "response_bytes_min": min(row[1] for row in rows),
                "response_bytes_max": max(row[1] for row in rows)}
    result = {
        "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "machine": platform.platform(), "python": platform.python_version(),
        "conditions": {"database": "disposable PostgreSQL 16 Docker", "identity": "fixture OIDC",
                       "client": "in-process FastAPI ASGITransport, persistent event loop",
                       "network": "none", "provider": "fixture capability; no provider call",
                       "warmups_each": WARMUPS, "sequential_samples_each": SAMPLES},
        "buyer_note_patch_ms": metrics(mutations),
        "buyer_note_patch_sql_per_request": round(mutation_query_count / SAMPLES, 3),
        "run_admission_ms": metrics(admissions),
        "run_admission_sql_per_request": round(admission_query_count / SAMPLES, 3),
        "persisted_buyer_edits": buyer_count, "persisted_queued_runs": run_count,
        "persisted_outbox_intents": outbox_count,
    }
    output = Path(os.environ["BUYEROS_MUTATION_BENCH_OUTPUT"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    # The imported project fixture deletes its project at teardown. Remove
    # only rows seeded by this opt-in case first, preserving FK integrity.
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("DELETE FROM project_buyers WHERE workspace_id=%s AND id = ANY(%s)",
                   (WORKSPACE_A, [uuid.UUID(value) for value in buyer_ids]))
        db.execute("DELETE FROM companies WHERE workspace_id=%s AND id = ANY(%s)",
                   (WORKSPACE_A, company_ids))
