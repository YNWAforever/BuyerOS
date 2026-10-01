"""0034 rollback proof on a separately owned fresh PostgreSQL cluster."""
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _start_container, _docker


def test_0034_empty_upgrade_downgrade_reupgrade_and_populated_refusal(monkeypatch):
    from buyeros_api.settings import get_settings
    name, dsn = _start_container()
    try:
        monkeypatch.setenv("BUYEROS_DATABASE_URL", dsn)
        get_settings.cache_clear()
        config = Config(str(ALEMBIC_INI))
        config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
        command.upgrade(config, "head")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT backend,enabled,epoch FROM worker_runtime_control").fetchone() == ("celery", False, 1)
        command.downgrade(config, "0033_api_rate_windows")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT to_regclass('worker_steps')").fetchone()[0] is None
        command.upgrade(config, "head")
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("INSERT INTO worker_bridge_nonces VALUES('fixture',%s,now()+interval '120 seconds')", (uuid.uuid4(),))
        with pytest.raises(RuntimeError, match="retained execution/replay/fencing state"):
            command.downgrade(config, "0033_api_rate_windows")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0034_worker_execution"
            assert db.execute("SELECT count(*) FROM worker_bridge_nonces").fetchone()[0] == 1
            assert db.execute("SELECT to_regclass('budget_reservations')").fetchone()[0] is not None
    finally:
        get_settings.cache_clear()
        _docker("rm", "-f", name)
