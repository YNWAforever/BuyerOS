"""T18 sole Alembic owner: empty rollback and persisted-run refusal."""

import json
import os
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _docker, _start_container


def test_0021_empty_round_trip_and_populated_refusal():
    name, dsn = _start_container()
    previous = os.environ.get("BUYEROS_DATABASE_URL")
    os.environ["BUYEROS_DATABASE_URL"] = dsn
    get_settings.cache_clear()
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    try:
        command.upgrade(config, "0021_run_bounds")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0021_run_bounds"
        command.downgrade(config, "0020_research_provenance")
        with psycopg.connect(dsn) as db:
            assert db.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='search_runs' AND column_name='usage_counters'"
            ).fetchone()[0] == 0
        command.upgrade(config, "0021_run_bounds")
        workspace, project, icp, run = (uuid.uuid4() for _ in range(4))
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("INSERT INTO workspaces(id,name) VALUES (%s,'T18 rollback fixture')", (workspace,))
            db.execute(
                "INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version)"
                " VALUES (%s,%s,'T18 project','T18 company','T18 offer','{US}','{en}',1)",
                (project, workspace),
            )
            db.execute(
                "INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash) "
                "VALUES (%s,%s,%s,1,%s::jsonb,%s)",
                (icp, workspace, project, json.dumps({}), "sha256:" + "a" * 64),
            )
            db.execute(
                "INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,"
                "target_companies,raw_result_count,execution_snapshot) "
                "VALUES (%s,%s,%s,%s,'queued','{}'::jsonb,1,0,%s::jsonb)",
                (run, workspace, project, icp, json.dumps({"price_version": "fixture-v1"})),
            )
        with pytest.raises(RuntimeError, match="retained run admission or usage evidence"):
            command.downgrade(config, "0020_research_provenance")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0021_run_bounds"
            assert db.execute("SELECT execution_snapshot FROM search_runs WHERE id=%s", (run,)).fetchone()[0] == {"price_version": "fixture-v1"}
    finally:
        if previous is None:
            os.environ.pop("BUYEROS_DATABASE_URL", None)
        else:
            os.environ["BUYEROS_DATABASE_URL"] = previous
        get_settings.cache_clear()
        _docker("rm", "-f", name)
