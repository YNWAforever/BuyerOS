"""Cached API pools replace dead idle connections without replaying transactions."""

import asyncio
import uuid

import httpx
import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from buyeros_api.api import deps
from buyeros_api.db.session import tenant_session
from buyeros_api.settings import get_settings
from tests.conftest import API_ROLE, _require_disposable_test_dsn, runtime_role_dsn
from tests.test_api_projects_db import ADMIN, WORKSPACE_A, _h, api as project_api


PROJECT_A = "a0000000-0000-4000-8000-000000000001"


def _terminate_owned_backend(dsn, backend_pid, *, expected_state):
    _require_disposable_test_dsn(dsn)
    with psycopg.connect(dsn, autocommit=True) as owner:
        owned = owner.execute(
            "SELECT usename, state FROM pg_stat_activity "
            "WHERE pid = %s AND datname = current_database() "
            "AND backend_type = 'client backend' AND pid <> pg_backend_pid()",
            (backend_pid,),
        ).fetchone()
        assert owned == (API_ROLE, expected_state)
        assert owner.execute(
            "SELECT pg_terminate_backend(pid, 5000) FROM pg_stat_activity "
            "WHERE pid = %s AND datname = current_database() AND usename = %s",
            (backend_pid, API_ROLE),
        ).fetchone() == (True,)


async def _idle_backend(engine):
    async with engine.connect() as connection:
        pid, actor, workspace = (await connection.execute(text(
            "SELECT pg_backend_pid(), current_setting('app.user_id', true), "
            "current_setting('app.workspace_id', true)"
        ))).one()
        assert actor in (None, "") and workspace in (None, "")
        return pid


@pytest.mark.parametrize("factory_name", ["get_engine", "get_rate_engine"])
def test_settings_read_recovers_dead_pooled_backend(project_api, seeded, factory_name):
    async def exercise():
        app = project_api.app
        factory = getattr(deps, factory_name)
        path = f"/v1/workspaces/{WORKSPACE_A}/preferences"
        async with app.router.lifespan_context(app), httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://checkout.fixture.invalid",
        ) as client:
            before = await client.get(path, headers=_h(ADMIN))
            assert before.status_code == 200, before.text
            engine = factory()
            backend_pid = await _idle_backend(engine)
            assert await _idle_backend(engine) == backend_pid, "must reuse a pooled backend"
            _terminate_owned_backend(seeded, backend_pid, expected_state="idle")

            recovered = await client.get(path, headers=_h(ADMIN))
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()["data"] == {
                "locale": "en", "default_markets": [], "version": 1,
            }
            assert recovered.headers["etag"] == '"1"'
            assert factory() is engine, "recovery must retain the cached engine"
            assert await _idle_backend(engine) != backend_pid

    asyncio.run(exercise())


@pytest.mark.parametrize("factory_name", ["get_engine", "get_rate_engine"])
def test_checked_out_transaction_disconnect_is_not_replayed(seeded, monkeypatch, factory_name):
    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_role_dsn(seeded))
    get_settings.cache_clear()

    async def exercise():
        factory = getattr(deps, factory_name)
        engine = factory()
        entered = 0
        try:
            with pytest.raises(OperationalError):
                async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                    entered += 1
                    assert (await session.execute(text(
                        "UPDATE projects SET name = 'uncommitted checkout test' "
                        "WHERE id = :project RETURNING id"
                    ), {"project": PROJECT_A})).scalar_one() == uuid.UUID(PROJECT_A)
                    backend_pid = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
                    _terminate_owned_backend(
                        seeded, backend_pid, expected_state="idle in transaction",
                    )
                    await session.execute(text("SELECT 1"))

            assert entered == 1
            with psycopg.connect(seeded) as owner:
                assert owner.execute(
                    "SELECT name, version FROM projects WHERE id = %s", (PROJECT_A,),
                ).fetchone() == ("ProjectA", 1)
            assert factory() is engine
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                assert (await session.execute(text(
                    "SELECT name FROM projects WHERE id = :project"
                ), {"project": PROJECT_A})).scalar_one() == "ProjectA"
        finally:
            await deps.dispose_engines()

    try:
        asyncio.run(exercise())
    finally:
        get_settings.cache_clear()
