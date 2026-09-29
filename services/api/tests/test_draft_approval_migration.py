"""T25 review/approval schema rollback retains evidence."""
import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
from tests.test_api_projects_db import api
from tests.test_draft_approval_context_db import _addressed_case, _approval_payload, _approve, _review
from tests.test_lookup_quotes_db import quote_case

HEAD = "0033_api_rate_windows"


def _config():
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return config


def _head(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_0028_empty_downgrade_and_reupgrade(migrated, monkeypatch):
    assert _head(migrated) == HEAD
    monkeypatch.setenv("BUYEROS_DATABASE_URL", migrated)
    get_settings.cache_clear()
    try:
        command.downgrade(_config(), "0027_draft_integrity")
        assert _head(migrated) == "0027_draft_integrity"
        with psycopg.connect(migrated) as db:
            columns = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='approvals'")}
            assert "context_snapshot" not in columns
    finally:
        command.upgrade(_config(), "head")
    assert _head(migrated) == HEAD


def test_0028_refuses_populated_approval_downgrade(quote_case, monkeypatch):
    api, dsn, buyers = quote_case
    draft_id, _ = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    assert review.status_code == 200, review.text
    approval = _approve(api, draft_id, _approval_payload(review))
    assert approval.status_code == 201, approval.text
    monkeypatch.setenv("BUYEROS_DATABASE_URL", dsn)
    get_settings.cache_clear()
    # The API calls above create short-lived rate windows. Clear only those
    # disposable counters so this rollback reaches its retained-history guard.
    with psycopg.connect(dsn, autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM api_rate_windows").fetchone()[0] > 0
        db.execute("DELETE FROM api_rate_windows")
    with pytest.raises(RuntimeError, match="retained approval history"):
        command.downgrade(_config(), "0027_draft_integrity")
    assert _head(dsn) == HEAD
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT count(*) FROM approvals WHERE draft_id=%s",
                          (draft_id,)).fetchone()[0] == 1



def test_0028_approval_material_and_invalidation_are_one_way(quote_case):
    api, dsn, buyers = quote_case
    draft_id, _ = _addressed_case(api, dsn, buyers)
    review = _review(api, draft_id)
    approval = _approve(api, draft_id, _approval_payload(review))
    assert approval.status_code == 201, approval.text
    approval_id = approval.json()["data"]["id"]
    with psycopg.connect(dsn, autocommit=True) as db:
        with pytest.raises(psycopg.Error, match="approval material is immutable"):
            db.execute("UPDATE approvals SET context_fingerprint=%s WHERE id=%s",
                       ("sha256:" + "0" * 64, approval_id))
        db.execute("UPDATE approvals SET invalidated_reason='fixture_revoked',"
                   "invalidated_at=now() WHERE id=%s", (approval_id,))
        with pytest.raises(psycopg.Error, match="cannot reactivate"):
            db.execute("UPDATE approvals SET invalidated_reason=NULL WHERE id=%s", (approval_id,))
        row = db.execute("SELECT invalidated_reason,invalidated_at FROM approvals WHERE id=%s",
                         (approval_id,)).fetchone()
        assert row[0] == "fixture_revoked" and row[1] is not None
