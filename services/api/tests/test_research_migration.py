"""T17 sole Alembic owner: empty rollback and retained-provenance refusal."""
import os
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _docker, _start_container


def test_0020_empty_round_trip_and_populated_refusal():
    name, dsn = _start_container()
    previous = os.environ.get("BUYEROS_DATABASE_URL")
    os.environ["BUYEROS_DATABASE_URL"] = dsn
    get_settings.cache_clear()
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    try:
        command.upgrade(config, "0020_research_provenance")
        with psycopg.connect(dsn) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0020_research_provenance"
            assert conn.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='raw_candidates' AND column_name='candidate_fingerprint'"
            ).fetchone()[0] == 1
        command.downgrade(config, "0019_offer_documents")
        with psycopg.connect(dsn) as conn:
            assert conn.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='evidence' AND column_name='run_id'"
            ).fetchone()[0] == 0
        command.upgrade(config, "0020_research_provenance")

        workspace, project, source = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("INSERT INTO workspaces(id,name) VALUES (%s,'T17 rollback fixture')", (workspace,))
            conn.execute(
                "INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version)"
                " VALUES (%s,%s,'T17 project','T17 company','T17 offer','{US}','{en}',1)",
                (project, workspace),
            )
            conn.execute(
                "INSERT INTO source_documents(id,workspace_id,project_id,permission_purpose,canonical_url,digest,storage_mode)"
                " VALUES (%s,%s,%s,'account_research','https://example.org',%s,'excerpt_only')",
                (source, workspace, project, "a" * 64),
            )
        with pytest.raises(RuntimeError, match="retained source_documents provenance"):
            command.downgrade(config, "0019_offer_documents")
        with psycopg.connect(dsn) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0020_research_provenance"
            assert conn.execute("SELECT project_id FROM source_documents WHERE id=%s", (source,)).fetchone()[0] == project
    finally:
        if previous is None:
            os.environ.pop("BUYEROS_DATABASE_URL", None)
        else:
            os.environ["BUYEROS_DATABASE_URL"] = previous
        get_settings.cache_clear()
        _docker("rm", "-f", name)
