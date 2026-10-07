"""T24 draft scope and immutable revision migration safety."""
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import PROJECT, WORKSPACE_A, quote_case

HEAD = "0038_c61_workspace_directory"


def _config():
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return config


def _head(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_0027_empty_downgrade_and_reupgrade(migrated):
    assert _head(migrated) == HEAD
    try:
        command.downgrade(_config(), "0026_sender_identity_versions")
        assert _head(migrated) == "0026_sender_identity_versions"
        with psycopg.connect(migrated) as db:
            assert db.execute("SELECT count(*) FROM pg_trigger WHERE tgname='draft_revision_immutable'").fetchone()[0] == 0
    finally:
        command.upgrade(_config(), "head")
    assert _head(migrated) == HEAD


def test_0027_refuses_populated_downgrade(quote_case, monkeypatch):
    _, dsn, buyers = quote_case
    draft_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) "
                   "VALUES (%s,%s,%s,%s,1,'draft')",
                   (draft_id, WORKSPACE_A, PROJECT, buyers[0][0]))
    monkeypatch.setenv("BUYEROS_DATABASE_URL", dsn)
    from buyeros_api.settings import get_settings
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="retained drafts"):
            command.downgrade(_config(), "0026_sender_identity_versions")
        assert _head(dsn) == HEAD
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT count(*) FROM outreach_drafts WHERE id=%s", (draft_id,)).fetchone()[0] == 1
    finally:
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute("DELETE FROM outreach_drafts WHERE id=%s", (draft_id,))
