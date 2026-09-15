"""Shared test fixtures.

``pg_dsn`` yields a PostgreSQL DSN. It uses ``BUYEROS_TEST_DATABASE_URL`` when
set; otherwise it starts a disposable ``postgres:16`` container and removes it
again. Tests that need a database skip cleanly when neither is available.
"""

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = SERVICE_ROOT / "alembic.ini"

POSTGRES_IMAGE = "postgres:16"
DB_USER = "buyeros"
DB_PASSWORD = "buyeros"
DB_NAME = "buyeros"
API_ROLE = "buyeros_api"
API_ROLE_PASSWORD = "test-only"


def _docker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def _start_container() -> tuple[str, str]:
    name = f"buyeros-test-{uuid.uuid4().hex[:8]}"
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

    mapping = _docker("port", name, "5432").stdout.strip().splitlines()[0]  # 127.0.0.1:NNNNN
    port = mapping.rsplit(":", 1)[1]
    return name, f"postgresql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:{port}/{DB_NAME}"


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
    """Apply all migrations once against the test database."""
    from alembic import command
    from alembic.config import Config

    from buyeros_api.settings import get_settings

    os.environ["BUYEROS_DATABASE_URL"] = pg_dsn
    get_settings.cache_clear()

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    command.upgrade(config, "head")
    return pg_dsn


@pytest.fixture
def seeded(migrated):
    """Insert two workspaces/projects and grant the runtime role login."""
    import psycopg

    with psycopg.connect(migrated, autocommit=True) as conn:
        conn.execute("DELETE FROM projects WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("DELETE FROM workspaces WHERE id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute(
            "INSERT INTO workspaces(id, name, data_mode) VALUES (%s, 'A', 'live'), (%s, 'B', 'live')",
            ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"),
        )
        conn.execute(
            "INSERT INTO projects(id, workspace_id, name) VALUES "
            "('a0000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', 'ProjectA'),"
            "('b0000000-0000-4000-8000-000000000002', '22222222-2222-4222-8222-222222222222', 'ProjectB')"
        )
        conn.execute(f"ALTER ROLE {API_ROLE} LOGIN PASSWORD '{API_ROLE_PASSWORD}'")
        conn.execute(f"GRANT USAGE ON SCHEMA public TO {API_ROLE}")
    return migrated


def runtime_role_dsn(dsn: str) -> str:
    """DSN for the non-owner, NOBYPASSRLS runtime role."""
    return dsn.replace(f"{DB_USER}:{DB_PASSWORD}", f"{API_ROLE}:{API_ROLE_PASSWORD}", 1)
