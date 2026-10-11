"""Opt-in disposable T29 buyer read benchmark; invoke through scripts/benchmark-buyeros.py."""

import asyncio
import contextvars
import json
import os
import platform
import statistics
import subprocess
import threading
import time
import uuid
from pathlib import Path

import httpx
import psycopg
from sqlalchemy import event, text, __version__ as sqlalchemy_version
from sqlalchemy.engine import Engine

from buyeros_api.api import deps
from tools.quality_metrics import install_queue_wait_probe, summarize_requests, write_new_report
from tools.owned_request_capture import capture_http_request
from tests import auth_fixtures as fx

CURRENT = contextvars.ContextVar("buyer_read_observation", default=None)
from tests.test_buyer_review_db import WORKSPACE_A, PROJECT_A, OPERATOR, api


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)


def test_representative_buyer_read_baseline(api, seeded):
    fixture_size = int(os.environ["BUYEROS_BENCH_FIXTURE_SIZE"])
    workspace_count = int(os.environ["BUYEROS_BENCH_WORKSPACES"])
    assert fixture_size in {1000, 10000}
    assert workspace_count in {1, 10, 100}
    capacity_actors = int(os.environ.get("BUYEROS_BENCH_CAPACITY_ACTORS", "0"))
    samples = int(os.environ.get("BUYEROS_BENCH_SAMPLES", "30"))
    assert capacity_actors in (0,1,10,25) and 30 <= samples <= 100
    extra = []
    snapshot_id = None
    query_count = 0
    lock = threading.Lock()

    def count_query(*_args):
        nonlocal query_count
        with lock:
            query_count += 1

    try:
        with psycopg.connect(seeded, autocommit=True) as conn:
            # Real migrated tables and FKs; synthetic names and no external identities.
            for number in range(1, workspace_count):
                workspace_id, project_id, icp_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
                extra.append((workspace_id, project_id))
                conn.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,%s,'live')",
                             (workspace_id, f"Benchmark workspace {number}"))
                conn.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) "
                             "VALUES (%s,%s,%s,'Fixture Ltd','Fixture offer','{US}','{en}',1)",
                             (project_id, workspace_id, f"Benchmark project {number}"))
                conn.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,basis_offer_revision) "
                             "VALUES (%s,%s,%s,1,'{}'::jsonb,%s,1)",
                             (icp_id, workspace_id, project_id, "sha256:" + "0" * 64))
            conn.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,basis_offer_revision) "
                         "VALUES (%s,%s,%s,1,'{}'::jsonb,%s,1)",
                         (uuid.uuid4(), WORKSPACE_A, PROJECT_A, "sha256:" + "0" * 64))
            conn.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) "
                         "SELECT gen_random_uuid(),%s,'Fixture buyer ' || g,'Fixture buyer ' || g "
                         "FROM generate_series(1,%s) AS g", (WORKSPACE_A, fixture_size))
            conn.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) "
                         "SELECT gen_random_uuid(),workspace_id,%s,id FROM companies WHERE workspace_id=%s",
                         (PROJECT_A, WORKSPACE_A))
            for table in ("companies", "project_buyers"):
                conn.execute(f"ANALYZE {table}")
        headers = {"Authorization": f"Bearer {fx.make_token(sub=OPERATOR)}", "Idempotency-Key": "t29-benchmark-snapshot"}
        target = f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT_A}"
        started = time.perf_counter()
        created = api.post(target + "/buyer-snapshots",
                           json={"filters": {}, "sort": "name_asc", "requested_limit": 1000}, headers=headers)
        snapshot_ms = (time.perf_counter() - started) * 1000
        assert created.status_code == 201, created.text
        snapshot_id = created.json()["data"]["id"]
        assert created.json()["data"]["total"] == 1000
        params = {"snapshot_id": snapshot_id, "offset": 900, "limit": 100}
        # Each staff actor owns a separate snapshot. A shared actor would miss
        # the membership and actor-bound snapshot cost of real concurrent reads.
        staff_reads = [(headers, params)]
        staff_headers_to_snapshot = []
        with psycopg.connect(seeded, autocommit=True) as conn:
            for number in range(1, max(10,capacity_actors)):
                subject = f"auth0|t29-staff-{number}"
                user_id = uuid.uuid5(uuid.NAMESPACE_URL, subject)
                conn.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)",
                             (user_id, fx.ISSUER, subject))
                conn.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) "
                             "VALUES (%s,%s,%s,%s,true)",
                             (uuid.uuid4(), WORKSPACE_A, user_id, ["operator"]))
                staff_headers_to_snapshot.append({
                    "Authorization": f"Bearer {fx.make_token(sub=subject)}",
                    "Idempotency-Key": f"t29-staff-snapshot-{number}"})
        async def measure():
            # One persistent event loop and its existing runtime pool; no tuning.
            transport = httpx.ASGITransport(app=api.app,raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport,base_url="http://testserver") as client:
                engine=deps.get_engine()
                queue_restore=install_queue_wait_probe(engine.pool._pool,CURRENT.get)
                def before(conn,cursor,statement,parameters,context,many):
                    row=CURRENT.get()
                    if row is not None:
                        row["queries"]+=1;context._buyer_read_started=time.perf_counter()
                def finish(context):
                    row=CURRENT.get();started=getattr(context,"_buyer_read_started",None)
                    if row is not None and started is not None:
                        row["sql_ms"]+=(time.perf_counter()-started)*1000
                        context._buyer_read_started=None
                def after(conn,cursor,statement,parameters,context,many):finish(context)
                def failed(context):finish(context.execution_context)
                event.listen(Engine,"before_cursor_execute",before)
                event.listen(Engine,"after_cursor_execute",after)
                event.listen(Engine,"handle_error",failed)
                try:
                    async with engine.connect() as connection:
                        role=(await connection.execute(text("SELECT current_user,r.rolsuper,r.rolbypassrls,pg_get_userbyid(c.relowner),c.relrowsecurity FROM pg_roles r CROSS JOIN pg_class c WHERE r.rolname=current_user AND c.oid='project_buyers'::regclass"))).one()
                        postgres_version=(await connection.execute(text("SHOW server_version"))).scalar_one()
                    assert role[0]=="buyeros_api" and role[1] is role[2] is False and role[3]!=role[0] and role[4] is True
                    for staff_headers in staff_headers_to_snapshot:
                        own=await client.post(target+"/buyer-snapshots",json={"filters":{},"sort":"name_asc","requested_limit":1000},headers=staff_headers)
                        assert own.status_code==201,own.text
                        assert own.json()["data"]["total"]==1000
                        staff_reads.append((staff_headers,{"snapshot_id":own.json()["data"]["id"],"offset":900,"limit":100}))
                    assert len(staff_reads)==max(10,capacity_actors)
                    expected=[]
                    with psycopg.connect(seeded) as owner:
                        schema_head=owner.execute("SELECT version_num FROM alembic_version").fetchone()[0]
                        for _,read_params in staff_reads:
                            rows=owner.execute("SELECT buyer_id FROM buyer_snapshot_items WHERE workspace_id=%s AND project_id=%s AND snapshot_id=%s ORDER BY ordinal OFFSET 900 LIMIT 100",(WORKSPACE_A,PROJECT_A,read_params["snapshot_id"])).fetchall()
                            assert len(rows)==100
                            expected.append([str(row[0]) for row in rows])
                    async def read_page(actor=0,repetition=None):
                        read_headers,read_params=staff_reads[actor]
                        def valid(response):
                            data=response.json().get("data",{})
                            return data.get("total")==1000 and [item.get("id") for item in data.get("items",[])]==expected[actor] and data.get("offset")==900 and data.get("limit")==100
                        return await capture_http_request(CURRENT,lambda:client.get(target+"/buyers",params=read_params,headers=read_headers),valid,actor_index=actor,repetition=repetition,pool_measured=True)
                    primers=[await read_page() for _ in range(3)]
                    event.listen(Engine,"before_cursor_execute",count_query)
                    try:
                        sequential=[await read_page(repetition=i) for i in range(30)]
                        concurrent=await asyncio.gather(*(read_page(repetition=i) for i in range(10)))
                        same_actor_query_count=query_count
                        distinct=await asyncio.gather(*(read_page(i,repetition=0) for i in range(10)))
                        distinct_query_count=query_count-same_actor_query_count
                    finally:
                        event.remove(Engine,"before_cursor_execute",count_query)
                    capacity=[]
                    for repetition in range(samples if capacity_actors else 0):
                        capacity.extend(await asyncio.gather(*(read_page(i,repetition=repetition) for i in range(capacity_actors))))
                    stages={name:{"observations":rows,"summary":summarize_requests(rows)} for name,rows in [("primers",primers),("legacy_sequential",sequential),("legacy_same_actor",concurrent),("legacy_distinct_staff",distinct)]}
                    if capacity_actors:stages["capacity"]={"observations":capacity,"summary":summarize_requests(capacity),"actors":capacity_actors,"samples_per_actor":samples}
                    raw=dict(schema="buyeros.buyer-read-raw.v1",dataset_buyers=fixture_size,snapshot_items=1000,page_offset=900,page_size=100,
                        environment=dict(os=platform.platform(),python=platform.python_version(),sqlalchemy=sqlalchemy_version,region="local loopback;notHK",device="local Windows;notbrowser",network="ASGI in-process/PGloopback",cold_warm="warm after3primers;notprocesscold",duration_model="fixed batches;not10minute sustained",pool_wait="actual queue.get incl failed waits;excludes new connection/reconnect"),
                        role=dict(name=role[0],superuser=role[1],bypass_rls=role[2],buyer_owner=role[3],buyer_rls=role[4],schema_head=schema_head,schema_read_by="owned migration owner",postgres_version=postgres_version),
                        stages=stages,provider_calls=0,live_verified=False,release_accepted=False,
                        valid=all(stage["summary"]["errors"]["failed_requests"]==0 for stage in stages.values()))
                    return sequential,concurrent,distinct,same_actor_query_count,distinct_query_count,raw
                finally:
                    queue_restore()
                    event.remove(Engine,"before_cursor_execute",before)
                    event.remove(Engine,"after_cursor_execute",after)
                    event.remove(Engine,"handle_error",failed)
        sequential,concurrent,distinct,same_actor_query_count,distinct_query_count,raw=asyncio.run(measure())
        with psycopg.connect(seeded, autocommit=True) as conn:
            plan = conn.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
                "SELECT pb.id,c.display_name FROM buyer_snapshot_items si "
                "JOIN project_buyers pb ON pb.workspace_id=si.workspace_id AND pb.id=si.buyer_id "
                "JOIN companies c ON c.workspace_id=pb.workspace_id AND c.id=pb.company_id "
                "WHERE si.workspace_id=%s AND si.project_id=%s AND si.snapshot_id=%s "
                "ORDER BY si.ordinal OFFSET 900 LIMIT 100",
                (WORKSPACE_A, PROJECT_A, snapshot_id)).fetchone()[0][0]
            connections = conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()").fetchone()[0]
        source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        result = {
            "source_sha": source_sha, "machine": platform.platform(), "python": platform.python_version(),
            "fixture": {"buyers": fixture_size, "workspaces": workspace_count, "projects": workspace_count,
                        "icp_revisions": workspace_count, "snapshot_items": 1000},
            "conditions": {"database": "disposable PostgreSQL 16 Docker", "identity": "fixture OIDC",
                           "client": "in-process FastAPI ASGITransport, persistent event loop", "network": "none", "warmups": 3,
                           "sequential_samples": 30, "concurrent_requests_one_staff_actor": 10,
                           "concurrent_requests_distinct_staff": 10},
            "snapshot_create_ms": round(snapshot_ms, 3),
            "sequential_ms": {"p50": round(statistics.median(x["latency_ms"] for x in sequential), 3),
                              "p95": round(_percentile([x["latency_ms"] for x in sequential], .95), 3)},
            "concurrent_ms": {"p50": round(statistics.median(x["latency_ms"] for x in concurrent), 3),
                              "p95": round(_percentile([x["latency_ms"] for x in concurrent], .95), 3)},
            "query_count_total_40_requests": same_actor_query_count,
            "query_count_per_request_mean": round(same_actor_query_count / 40, 3),
            "distinct_staff_concurrent_ms": {
                "p50": round(statistics.median(x["latency_ms"] for x in distinct), 3),
                "p95": round(_percentile([x["latency_ms"] for x in distinct], .95), 3)},
            "distinct_staff_query_count_total_10_requests": distinct_query_count,
            "distinct_staff_query_count_per_request_mean": round(distinct_query_count / 10, 3),
            "response_bytes": {"min": min(x["bytes"] for x in sequential + concurrent),
                               "max": max(x["bytes"] for x in sequential + concurrent)},
            "db_connections_after": connections,
            "page_explain": plan,
            "queue_age_and_dispatch_fairness": "not measured by this API read benchmark",
        }
        artifact = Path(os.environ["BUYEROS_BENCH_OUTPUT"])
        artifact.parent.mkdir(parents=True, exist_ok=True)
        result["raw_capture"] = raw
        write_new_report(artifact,result)
        assert raw["valid"], "captured failed/scope-invalid request retained in raw denominator"
        assert same_actor_query_count / 40 <= 20, "buyer page read has an unbounded query count"
        assert distinct_query_count / 10 <= 20, "distinct staff page read has an unbounded query count"
    finally:
        if extra:
            with psycopg.connect(seeded, autocommit=True) as conn:
                workspace_ids = [row[0] for row in extra]
                conn.execute("DELETE FROM icp_versions WHERE workspace_id = ANY(%s)", (workspace_ids,))
                conn.execute("DELETE FROM projects WHERE workspace_id = ANY(%s)", (workspace_ids,))
                conn.execute("DELETE FROM workspaces WHERE id = ANY(%s)", (workspace_ids,))