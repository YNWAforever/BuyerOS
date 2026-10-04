"""Opt-in actual runtime-role directory capture; invoke the owned wrapper only."""
import asyncio
import contextvars
import json
import os
import platform
import time
import uuid
from pathlib import Path

import httpx
import psycopg
import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

from buyeros_api.api import auth, deps
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from buyeros_api.settings import get_settings
from tests import auth_fixtures as fx
from tests.conftest import _docker, _require_disposable_test_dsn, _start_container, runtime_role_dsn
from tools.quality_metrics import DATABASE_VARIABLES, provenance, summarize_requests, write_new_report

ROOT = Path(__file__).resolve().parents[3]
CURRENT = contextvars.ContextVar("directory_observation", default=None)


@pytest.fixture(scope="session")
def pg_dsn():
    # Override only in this opt-in module. Keep the shared destructive guard intact.
    for variable in DATABASE_VARIABLES:
        assert not os.environ.get(variable), f"inherited {variable} refused"
    nonce, marker = os.environ["BUYEROS_DIRECTORY_NONCE"], Path(os.environ["BUYEROS_DIRECTORY_OWNER"])
    assert nonce and not marker.exists()
    name, dsn = _start_container()
    try:
        _require_disposable_test_dsn(dsn)
        identity = json.loads(_docker("inspect", name).stdout)[0]
        write_new_report(marker, {"nonce": nonce, "name": name, "container_id": identity["Id"], "image": identity["Config"]["Image"]})
        yield dsn
    finally:
        removed = _docker("rm", "-f", name)
        assert removed.returncode == 0, "owned database cleanup failed"


def test_workspace_directory_current_baseline(migrated, monkeypatch):
    samples, actors = int(os.environ["BUYEROS_DIRECTORY_SAMPLES"]), int(os.environ["BUYEROS_DIRECTORY_ACTORS"])
    assert 30 <= samples <= 100 and actors in (1, 10, 25)
    output = Path(os.environ["BUYEROS_DIRECTORY_OUTPUT"])
    subjects = [f"directory-fixture-{uuid.uuid4().hex}" for _ in range(actors+1)]
    users = [uuid.uuid4() for _ in subjects]
    workspace_ids = [uuid.uuid4() for _ in range(1000)]
    membership_ids = [uuid.uuid4() for _ in range(actors)]
    with psycopg.connect(migrated, autocommit=True) as owner:
        assert owner.execute("SELECT count(*) FROM workspaces").fetchone()[0] == 0, "fixture must be freshly owned/empty"
        owner.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
        owner.execute("GRANT USAGE ON SCHEMA public TO buyeros_api")
        for user, subject in zip(users, subjects):
            owner.execute("INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)", (user, fx.ISSUER, subject))
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(migrated))
    monkeypatch.setenv("BUYEROS_AUTH0_ISSUER", fx.ISSUER)
    monkeypatch.setenv("BUYEROS_AUTH0_AUDIENCE", fx.AUDIENCE)
    get_settings.cache_clear()
    cache = JwksKeyCache(lambda: asyncio.sleep(0, result=fx.jwks_document()), cache_seconds=3600)
    monkeypatch.setattr(auth, "_verifier_from_settings", lambda: TokenVerifier(cache, issuer=fx.ISSUER, audience=fx.AUDIENCE))
    headers = [{"Authorization": f"Bearer {fx.make_token(sub=subject)}"} for subject in subjects]

    def before(conn, cursor, statement, params, context, many):
        observation = CURRENT.get()
        if observation is not None:
            observation["queries"] += 1
            context._directory_started = time.perf_counter()

    def after(conn, cursor, statement, params, context, many):
        observation = CURRENT.get()
        if observation is not None:
            observation["sql_ms"] += (time.perf_counter()-context._directory_started)*1000

    event.listen(Engine, "before_cursor_execute", before)
    event.listen(Engine, "after_cursor_execute", after)
    matrix = []
    try:
        async def capture():
            app = create_app()
            async with app.router.lifespan_context(app), httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://fixture.test") as client:
                engine = deps.get_engine()
                async with engine.connect() as conn:
                    role = (await conn.execute(text("SELECT current_user, r.rolsuper, r.rolbypassrls, pg_get_userbyid(c.relowner), c.relrowsecurity FROM pg_roles r CROSS JOIN pg_class c WHERE r.rolname=current_user AND c.oid='memberships'::regclass"))).one()
                assert role[0] == "buyeros_api" and role[1] is role[2] is False and role[3] != role[0] and role[4] is True
                report_role = dict(name=role[0], superuser=role[1], bypass_rls=role[2], membership_owner=role[3], membership_rls=role[4])

                async def request(actor=0, visible=True):
                    observation = dict(latency_ms=0.0, status=None, bytes=0, queries=0, sql_ms=0.0, invalid_context=False)
                    token = CURRENT.set(observation)
                    started = time.perf_counter()
                    try:
                        response = await client.get("/v1/workspaces?offset=0&limit=20", headers=headers[actor])
                        observation.update(status=response.status_code, bytes=len(response.content))
                        data = response.json().get("data", {})
                        expected = [{"id":str(workspace_ids[0]), "name":"Directory fixture 0", "membership_id":str(membership_ids[actor]), "roles":["viewer"], "data_mode":"live"}] if visible else []
                        observation["invalid_context"] = data != {"items":expected, "offset":0, "limit":20, "total":int(visible)}
                    except (httpx.HTTPError, ValueError) as exc:
                        observation["transport_error"] = type(exc).__name__
                    finally:
                        observation["latency_ms"] = (time.perf_counter()-started)*1000
                        CURRENT.reset(token)
                    return observation

                previous = 0
                for count in (1, 10, 100, 1000):
                    with psycopg.connect(migrated, autocommit=True) as owner:
                        for number in range(previous, count):
                            owner.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,%s,'live')", (workspace_ids[number], f"Directory fixture {number}"))
                        if previous == 0:
                            for user, membership in zip(users[:-1], membership_ids):
                                owner.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{viewer}',true)", (membership, workspace_ids[0], user))
                        owner.execute("ANALYZE workspaces"); owner.execute("ANALYZE memberships")
                    first = await request()
                    warmups = [await request() for _ in range(3)]
                    observed = []
                    for _ in range(samples):
                        observed.extend(await asyncio.gather(*(request(i) for i in range(actors))))
                    summary = summarize_requests(observed)
                    with psycopg.connect(runtime_role_dsn(migrated)) as runtime:
                        candidate_plan = runtime.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id,name FROM workspaces ORDER BY id").fetchone()[0]
                        runtime.execute("SELECT set_config('app.workspace_id',%s,true)", (str(workspace_ids[0]),))
                        membership_plan = runtime.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id,roles FROM memberships WHERE workspace_id=%s AND user_id=%s AND active IS TRUE", (workspace_ids[0], users[0])).fetchone()[0]
                    stage = dict(total_workspaces=count, unrelated_workspaces=count-1, visible_memberships_per_actor=1, actors=actors, first_after_seed=first, warmups=warmups, warm=summary, observations=observed, explain_runtime_role=dict(candidate_query=candidate_plan, membership_query=membership_plan))
                    matrix.append(stage)
                    print(f"W={count}: warm requests={summary['requests']} SQL/request={summary['queries']['max']} p95={summary['latency_ms']['p95']}ms failed={summary['errors']['failed_requests']}", flush=True)
                    previous = count

                # Reuse the same real pool between a member, nonmember and revoked actor.
                pids, settings, probes = [], [], []
                for actor, visible in [(0,True),(actors,False),(0,True)]:
                    probes.append(await request(actor,visible))
                    async with engine.connect() as conn:
                        pid, setting = (await conn.execute(text("SELECT pg_backend_pid(), current_setting('app.workspace_id',true)"))).one()
                        pids.append(pid); settings.append(setting)
                with psycopg.connect(migrated,autocommit=True) as owner:
                    owner.execute("UPDATE memberships SET active=false WHERE id=%s",(membership_ids[0],))
                probes.append(await request(0,False))
                with psycopg.connect(migrated,autocommit=True) as owner:
                    owner.execute("UPDATE memberships SET active=true WHERE id=%s",(membership_ids[0],))
                probes.append(await request(0,True))
                assert len(set(pids)) == 1 and all(s in (None,"") for s in settings)
                assert summarize_requests(probes)["errors"]["failed_requests"] == 0
                return report_role, dict(backend_pids=pids, workspace_setting_after_return=settings, same_connection_reused=True, revocation_seen=True, probes=probes)

        role, pool = asyncio.run(capture())
        query_maxima = [r["warm"]["queries"]["max"] for r in matrix]
        valid = all(summarize_requests([r["first_after_seed"], *r["warmups"], *r["observations"]])["errors"]["failed_requests"] == 0 for r in matrix)
        gate = dict(max_sql_per_request=6, independent_of_unrelated_workspaces=len(set(query_maxima)) == 1, within_budget=max(query_maxima)<=6, passed=valid and max(query_maxima)<=6 and len(set(query_maxima))==1)
        report = dict(schema="buyeros.workspace-directory-benchmark.v1", run_id=os.environ["BUYEROS_DIRECTORY_NONCE"], evidence_mode="owned_disposable_fixture", live_verified=False,
                      environment=dict(os=platform.platform(), python=platform.python_version(), database="owned Docker PostgreSQL16", region="local loopback; no geographic network measurement", transport="in-process HTTPX ASGI + real loopback PostgreSQL", cold_warm="first-after-seed is not process-cold; warm after3primers", concurrency=actors, warm_samples_per_actor=samples, duration_model="fixed request batches; not 10-minute stairs"),
                      dataset="fictional users/workspaces only; fixed one visible membership", role=role, pool_reuse=pool, matrix=matrix, directory_gate=gate,
                      cost=dict(provider_calls=0, paid_resources_created=False, local_infrastructure_usd=None), release_accepted=False)
        report.update(provenance(ROOT,[Path(__file__).resolve(), ROOT/'scripts/benchmark-workspace-directory.py', ROOT/'services/api/tools/quality_metrics.py', ROOT/'services/api/buyeros_api/api/routes/workspaces.py', ROOT/'services/api/buyeros_api/api/deps.py']))
        write_new_report(output, report)
        assert valid, "captured response/scope failure; report retained"
    finally:
        event.remove(Engine,"before_cursor_execute",before)
        event.remove(Engine,"after_cursor_execute",after)
        get_settings.cache_clear()
