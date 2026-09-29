"""Shared test fixtures.

``pg_dsn`` yields a PostgreSQL DSN. It uses ``BUYEROS_TEST_DATABASE_URL`` when
set; otherwise it starts a disposable ``postgres:16`` container and removes it
again. Tests that need a database skip cleanly when neither is available.
"""

import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest

# psycopg's async driver cannot run on Windows' default ProactorEventLoop; the
# async SQLAlchemy engine used by the route tests needs the selector loop pinned.
if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

SERVICE_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = SERVICE_ROOT / "alembic.ini"

POSTGRES_IMAGE = "postgres:16"
DB_USER = "buyeros"
DB_PASSWORD = "buyeros"
DB_NAME = "buyeros_test_api"
API_ROLE = "buyeros_api"
API_ROLE_PASSWORD = "test-only"
_MIGRATED_DSN: str | None = None


def _require_disposable_test_dsn(dsn: str) -> None:
    parsed = urlsplit(dsn)
    database = parsed.path.lstrip("/")
    if (
        parsed.scheme not in {"postgresql", "postgres"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or not database.startswith("buyeros_test_")
        or parsed.query
        or parsed.fragment
    ):
        raise pytest.UsageError(
            "destructive fixtures require a disposable loopback buyeros_test_* database"
        )


def _unavailable(message: str) -> None:
    if os.environ.get("BUYEROS_STRICT_INTEGRATION") == "1":
        pytest.fail("Docker/disposable integration database required: " + message)
    pytest.skip(message)


def _docker(*args: str) -> subprocess.CompletedProcess:
    command = ["docker", *args]
    timeout = 30 if args and args[0] == "run" else 10
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 124, stdout="", stderr="docker command timed out")


def _start_container() -> tuple[str, str]:
    import psycopg

    last_error = "disposable postgres did not start"
    for attempt in range(2):
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
            last_error = f"could not start postgres container: {created.stderr.strip()}"
            _docker("rm", "-f", name)
            time.sleep(2 * (attempt + 1))
            continue

        # Docker Desktop may serve its internal health probe before the host
        # port forwards. Require both signals, with a bounded retry under load.
        deadline = time.time() + 120
        ready_inside = False
        while time.time() < deadline:
            if not ready_inside:
                ready_inside = "accepting connections" in _docker(
                    "exec", name, "pg_isready", "-U", DB_USER
                ).stdout
            mapping = _docker("port", name, "5432").stdout.strip().splitlines()
            if ready_inside and mapping:
                port = mapping[0].rsplit(":", 1)[1]
                dsn = f"postgresql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:{port}/{DB_NAME}"
                try:
                    with psycopg.connect(dsn, connect_timeout=2):
                        return name, dsn
                except psycopg.OperationalError:
                    pass
            time.sleep(1)
        last_error = "postgres container or host port did not become ready"
        _docker("rm", "-f", name)
    _unavailable(last_error)
    raise AssertionError("unreachable")

@pytest.fixture(scope="session")
def pg_dsn():
    env_dsn = os.environ.get("BUYEROS_TEST_DATABASE_URL")
    if env_dsn:
        _require_disposable_test_dsn(env_dsn)
        yield env_dsn
        return

    if shutil.which("docker") is None:
        _unavailable("set BUYEROS_TEST_DATABASE_URL or install docker for DB tests")

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
    global _MIGRATED_DSN
    _MIGRATED_DSN = pg_dsn
    return pg_dsn


@pytest.fixture
def seeded(migrated):
    """Insert two workspaces/projects and grant the runtime role login."""
    import psycopg

    with psycopg.connect(migrated, autocommit=True) as conn:
        conn.execute("DELETE FROM api_rate_windows WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("DELETE FROM workspace_preferences WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("DELETE FROM audit_events WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("UPDATE projects SET active_icp_version_id = NULL WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("DELETE FROM icp_versions WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        for table in ("budget_reservation_allocations", "cost_events", "budget_reservations", "budget_accounts"):
            conn.execute(f"DELETE FROM {table} WHERE workspace_id IN (%s, %s)",
                         ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("DELETE FROM offer_documents WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("DELETE FROM projects WHERE workspace_id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute("DELETE FROM workspaces WHERE id IN (%s, %s)",
                     ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"))
        conn.execute(
            "INSERT INTO workspaces(id, name, data_mode) VALUES (%s, 'A', 'live'), (%s, 'B', 'live')",
            ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"),
        )
        conn.execute(
            "INSERT INTO projects"
            "(id, workspace_id, name, company_name, offer, markets, language_preferences, version) VALUES "
            "('a0000000-0000-4000-8000-000000000001', '11111111-1111-4111-8111-111111111111', 'ProjectA', "
            "'ProjectA Co', 'Seeded offer A', '{US}', '{en}', 1),"
            "('b0000000-0000-4000-8000-000000000002', '22222222-2222-4222-8222-222222222222', 'ProjectB', "
            "'ProjectB Co', 'Seeded offer B', '{US}', '{en}', 1)"
        )
        conn.execute(f"ALTER ROLE {API_ROLE} LOGIN PASSWORD '{API_ROLE_PASSWORD}'")
        conn.execute(f"GRANT USAGE ON SCHEMA public TO {API_ROLE}")
    return migrated


@pytest.fixture(autouse=True)
def _dispose_api_engines(request):
    """Release the per-test async engines cached by ``api.deps``.

    A bare ``starlette`` ``TestClient`` starts a fresh event loop per request, and
    ``deps.get_engine()`` caches one async engine per loop forever, so every DB-hitting
    request retains a connection. Disposing after each test keeps the suite from
    exhausting the test database's connection slots. ``dispose_engines`` is async, so
    run it on a throwaway loop; a fresh loop is fine because the cache is global.
    """
    yield
    import asyncio

    from buyeros_api.api.deps import dispose_engines

    try:
        asyncio.run(dispose_engines())
    except RuntimeError:
        pass
    if _MIGRATED_DSN and "migrated" in request.fixturenames:
        # Clean test traffic after releasing route connections. This also covers
        # direct migrated tests, not only the seeded HTTP fixture.
        import psycopg

        with psycopg.connect(_MIGRATED_DSN, autocommit=True) as conn:
            if conn.execute("SELECT to_regclass('public.api_rate_windows')").fetchone()[0]:
                conn.execute("DELETE FROM api_rate_windows")


def runtime_role_dsn(dsn: str) -> str:
    """DSN for the non-owner, NOBYPASSRLS runtime role."""
    return dsn.replace(f"{DB_USER}:{DB_PASSWORD}", f"{API_ROLE}:{API_ROLE_PASSWORD}", 1)
