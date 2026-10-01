"""T19 sole migration owner: pinned saver schema and nondestructive rollback."""

import os
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _docker, _start_container


def test_0022_empty_round_trip_and_retained_checkpoint_refusal():
    name, dsn = _start_container()
    previous = os.environ.get("BUYEROS_DATABASE_URL")
    os.environ["BUYEROS_DATABASE_URL"] = dsn
    get_settings.cache_clear()
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    try:
        command.upgrade(config, "head")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0036_checkpoint_schema_grants"
            assert db.execute("SELECT max(v) FROM buyeros_graph.checkpoint_migrations").fetchone()[0] == 9
            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                                  "WHERE relname=%s", (table,)).fetchone() == (True, True)
            assert db.execute("SELECT count(*) FROM information_schema.columns WHERE "
                              "table_name='fit_assessments' AND column_name='assessment_details'").fetchone()[0] == 1
        command.downgrade(config, "0021_run_bounds")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT to_regnamespace('buyeros_graph')").fetchone()[0] is None
        command.upgrade(config, "head")
        thread_id = f"{uuid.uuid4()}:{uuid.uuid4()}:fit-v1:1:{uuid.uuid4()}"
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("INSERT INTO buyeros_graph.checkpoints"
                       "(thread_id,checkpoint_ns,checkpoint_id,checkpoint,metadata) "
                       "VALUES (%s,'',%s,'{}'::jsonb,'{}'::jsonb)",
                       (thread_id, str(uuid.uuid4())))
        with pytest.raises(RuntimeError, match="retained research checkpoint state"):
            command.downgrade(config, "0021_run_bounds")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0036_checkpoint_schema_grants"
            assert db.execute("SELECT count(*) FROM buyeros_graph.checkpoints").fetchone()[0] == 1
    finally:
        if previous is None:
            os.environ.pop("BUYEROS_DATABASE_URL", None)
        else:
            os.environ["BUYEROS_DATABASE_URL"] = previous
        get_settings.cache_clear()
        _docker("rm", "-f", name)
