"""Disposable-PostgreSQL fixtures for worker integration tests.

The worker/store code runs against the least-privilege ``buyeros_api`` runtime
role so row-level security is actually exercised, not bypassed. This mirrors
``services/api/tests/conftest.py``; migrations remain owned by ``buyeros_api``
and are applied from ``services/api/alembic``.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import pytest

# psycopg's async driver cannot run on Windows' default ProactorEventLoop; the
# worker uses asyncio.run directly, so tests pin the selector loop here.
if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

WORKER_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = WORKER_ROOT.parent / "api"
ALEMBIC_INI = API_ROOT / "alembic.ini"

POSTGRES_IMAGE = "postgres:16"
DB_USER = "buyeros"
DB_PASSWORD = "buyeros"
DB_NAME = "buyeros"
API_ROLE = "buyeros_api"
API_ROLE_PASSWORD = "test-only"

WS_A = "11111111-1111-4111-8111-111111111111"
WS_B = "22222222-2222-4222-8222-222222222222"
PROJECT_A = "a0000000-0000-4000-8000-000000000001"
ICP_A = "b0000000-0000-4000-8000-0000000000a1"
RUN_A = "d0000000-0000-4000-8000-0000000000a1"


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def _start_container() -> tuple[str, str]:
    name = f"buyeros-worker-test-{uuid.uuid4().hex[:8]}"
    created = _docker(
        "run", "-d", "--name", name,
        "-e", f"POSTGRES_PASSWORD={DB_PASSWORD}",
        "-e", f"POSTGRES_USER={DB_USER}",
        "-e", f"POSTGRES_DB={DB_NAME}",
        "-p", "127.0.0.1::5432",
        POSTGRES_IMAGE,
    )
    if created.returncode != 0:
        pytest.skip(f"could not start postgres container: {created.stderr.strip()}")

    deadline = time.time() + 60
    while time.time() < deadline:
        if "accepting connections" in _docker("exec", name, "pg_isready", "-U", DB_USER).stdout:
            break
        time.sleep(1)
    else:
        _docker("rm", "-f", name)
        pytest.skip("postgres container did not become ready")

    mapping = _docker("port", name, "5432").stdout.strip().splitlines()[0]
    port = mapping.rsplit(":", 1)[1]
    return name, f"postgresql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:{port}/{DB_NAME}"


def runtime_role_dsn(dsn: str) -> str:
    return dsn.replace(f"{DB_USER}:{DB_PASSWORD}", f"{API_ROLE}:{API_ROLE_PASSWORD}", 1)


@pytest.fixture(scope="session")
def pg_dsn():
    env_dsn = os.environ.get("BUYEROS_TEST_DATABASE_URL")
    if env_dsn:
        yield env_dsn
        return
    if shutil.which("docker") is None:
        pytest.skip("set BUYEROS_TEST_DATABASE_URL or install docker for DB tests")
    name, dsn = _start_container()
    try:
        yield dsn
    finally:
        _docker("rm", "-f", name)


@pytest.fixture(scope="session")
def migrated(pg_dsn):
    from alembic import command
    from alembic.config import Config

    from buyeros_api.settings import get_settings

    os.environ["BUYEROS_DATABASE_URL"] = pg_dsn
    get_settings.cache_clear()

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(config, "head")

    import psycopg

    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute("DELETE FROM workspaces WHERE id IN (%s, %s)", (WS_A, WS_B))
        conn.execute(
            "INSERT INTO workspaces(id, name, data_mode) VALUES (%s, 'A', 'live'), (%s, 'B', 'live')",
            (WS_A, WS_B),
        )
        conn.execute(
            "INSERT INTO projects(id, workspace_id, name) VALUES (%s, %s, 'ProjectA')",
            (PROJECT_A, WS_A),
        )
        conn.execute(
            "INSERT INTO icp_versions(id, workspace_id, project_id, number, content, content_hash)"
            " VALUES (%s, %s, %s, 1, '{}'::jsonb, 'hash')",
            (ICP_A, WS_A, PROJECT_A),
        )
        conn.execute(f"ALTER ROLE {API_ROLE} LOGIN PASSWORD '{API_ROLE_PASSWORD}'")
        conn.execute(f"GRANT USAGE ON SCHEMA public TO {API_ROLE}")
    return pg_dsn


@pytest.fixture(scope="session")
def runtime_dsn(migrated):
    return runtime_role_dsn(migrated)


@pytest.fixture
def worker_database_url(migrated, runtime_dsn, monkeypatch):
    """Point the worker engine at the RLS-enforcing runtime role for one test."""
    from buyeros_api.settings import get_settings

    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_dsn)
    get_settings.cache_clear()
    yield runtime_dsn
    get_settings.cache_clear()


def reset_tenant(conn, workspace_id: str = WS_A) -> None:
    conn.execute("DELETE FROM run_events WHERE workspace_id = %s", (workspace_id,))
    conn.execute("DELETE FROM search_runs WHERE workspace_id = %s", (workspace_id,))
    conn.execute("DELETE FROM outbox_events WHERE workspace_id = %s", (workspace_id,))


def seed_run(conn, run_id: str = RUN_A, workspace_id: str = WS_A, status: str = "running") -> None:
    conn.execute(
        "INSERT INTO search_runs(id, workspace_id, project_id, icp_version_id, status)"
        " VALUES (%s, %s, %s, %s, %s)",
        (run_id, workspace_id, PROJECT_A, ICP_A, status),
    )


def seed_outbox(
    conn,
    *,
    intent_key: str,
    event_type: str = "fetch.evidence",
    payload: dict | None = None,
    workspace_id: str = WS_A,
    state: str = "ready",
    generation: int = 0,
    lease_expires_at: datetime | None = None,
    outbox_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO outbox_events"
        " (id, workspace_id, intent_key, event_type, payload, state, fencing_generation, lease_expires_at)"
        " VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)",
        (
            outbox_id or str(uuid.uuid4()),
            workspace_id,
            intent_key,
            event_type,
            json.dumps(payload or {}),
            state,
            generation,
            lease_expires_at,
        ),
    )
