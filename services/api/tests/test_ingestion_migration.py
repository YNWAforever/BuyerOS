"""T16 isolated Alembic rollback proof; never uses a shared working DB."""
import os
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _docker, _start_container


def test_0019_empty_round_trip_and_nonempty_refusal():
    name, dsn = _start_container()
    previous = os.environ.get("BUYEROS_DATABASE_URL")
    os.environ["BUYEROS_DATABASE_URL"] = dsn
    get_settings.cache_clear()
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    try:
        command.upgrade(config, "0019_offer_documents")
        with psycopg.connect(dsn) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0019_offer_documents"
            assert conn.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='offer_documents'"
            ).fetchone() == (True, True)
        command.downgrade(config, "0018_budget_ledger")
        with psycopg.connect(dsn) as conn:
            assert conn.execute("SELECT to_regclass('offer_documents')").fetchone()[0] is None
            assert conn.execute(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name='source_documents' AND column_name='object_key'"
            ).fetchone()[0] == 0
        command.upgrade(config, "0019_offer_documents")

        workspace, project, document = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("INSERT INTO workspaces(id,name) VALUES (%s,'T16 rollback fixture')", (workspace,))
            conn.execute(
                 "INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version)"
                " VALUES (%s,%s,'T16 project','T16 company','T16 offer','{US}','{en}',1)",
                (project, workspace),
            )
            conn.execute(
                "INSERT INTO offer_documents"
                "(id,workspace_id,project_id,kind,filename,media_type,sha256,status)"
                " VALUES (%s,%s,%s,'upload','offer.txt','text/plain',%s,'quarantined')",
                (document, workspace, project, "a" * 64),
            )
        with pytest.raises(RuntimeError, match="offer documents"):
            command.downgrade(config, "0018_budget_ledger")
        with psycopg.connect(dsn) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0019_offer_documents"
            assert conn.execute("SELECT count(*) FROM offer_documents WHERE id=%s", (document,)).fetchone()[0] == 1
    finally:
        if previous is None:
            os.environ.pop("BUYEROS_DATABASE_URL", None)
        else:
            os.environ["BUYEROS_DATABASE_URL"] = previous
        get_settings.cache_clear()
        _docker("rm", "-f", name)
