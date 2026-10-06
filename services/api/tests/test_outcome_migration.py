"""T27 outcome provenance, append-only runtime grants and rollback boundaries."""
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
from tests.test_api_projects_db import api
from tests.test_lookup_quotes_db import OPERATOR, WORKSPACE_A, PROJECT, quote_case

HEAD = "0037_bulk_manifests"


def _config():
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return cfg


def _head(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_0030_empty_downgrade_reupgrade_and_runtime_grants(migrated, monkeypatch):
    assert _head(migrated) == HEAD
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT has_table_privilege('buyeros_api','outcome_events','UPDATE')").fetchone()[0] is False
        assert db.execute("SELECT has_table_privilege('buyeros_api','outcome_events','INSERT')").fetchone()[0] is True
    monkeypatch.setenv("BUYEROS_DATABASE_URL", migrated)
    try:
        command.downgrade(_config(), "0029_export_authorization")
        assert _head(migrated) == "0029_export_authorization"
        with psycopg.connect(migrated) as db:
            columns = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='outcome_events'")}
            assert "project_id" not in columns and "provenance_reference" not in columns and "correction_reason" not in columns
    finally:
        command.upgrade(_config(), "head")
    assert _head(migrated) == HEAD


def test_0030_retained_outcome_refuses_downgrade(quote_case, monkeypatch):
    _client, dsn, buyers = quote_case
    event_id = uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO outcome_events(id,workspace_id,buyer_id,project_id,stage,source,actor_user_id,"
                   "occurred_at,notes) VALUES (%s,%s,%s,%s,'reply','manual',%s,now(),'Fixture manual note')",
                   (event_id, WORKSPACE_A, buyers[0][0], PROJECT,
                    uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)))
    monkeypatch.setenv("BUYEROS_DATABASE_URL", dsn)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="retained manual outcome history"):
        command.downgrade(_config(), "0029_export_authorization")
    assert _head(dsn) == HEAD
