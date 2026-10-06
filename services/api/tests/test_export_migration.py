"""T26 export manifest migration and retained-history rollback boundary."""
import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
from tests.test_api_projects_db import api
from tests.test_exports_authorization_db import _buyer_body, _permit
from tests.test_lookup_quotes_db import OPERATOR, WORKSPACE_A, PROJECT, _h, quote_case

HEAD = "0037_bulk_manifests"


def _config():
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return cfg


def _head(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_0029_empty_downgrade_and_reupgrade(migrated, monkeypatch):
    assert _head(migrated) == HEAD
    monkeypatch.setenv("BUYEROS_DATABASE_URL", migrated)
    get_settings.cache_clear()
    try:
        command.downgrade(_config(), "0028_draft_approval_context")
        assert _head(migrated) == "0028_draft_approval_context"
        with psycopg.connect(migrated) as db:
            columns = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='export_jobs'")}
            assert "actor_user_id" not in columns and "selection_manifest" not in columns
    finally:
        command.upgrade(_config(), "head")
    assert _head(migrated) == HEAD


def test_0029_populated_history_refuses_downgrade(quote_case, monkeypatch):
    client, dsn, buyers = quote_case
    with psycopg.connect(dsn, autocommit=True) as db:
        _permit(db, "export_accounts")
    response = client.post(f"/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/exports",
                           json=_buyer_body(buyers), headers=_h(OPERATOR, key="export-migration-001"))
    assert response.status_code == 202, response.text
    monkeypatch.setenv("BUYEROS_DATABASE_URL", dsn)
    get_settings.cache_clear()
    # The API calls above create short-lived rate windows. Clear only those
    # disposable counters so this rollback reaches its retained-history guard.
    with psycopg.connect(dsn, autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM api_rate_windows").fetchone()[0] > 0
        db.execute("DELETE FROM api_rate_windows")
    with pytest.raises(RuntimeError, match="retained export history"):
        command.downgrade(_config(), "0028_draft_approval_context")
    assert _head(dsn) == HEAD
