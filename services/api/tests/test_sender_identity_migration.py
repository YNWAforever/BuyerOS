"""T24 sender metadata migration preserves reviewed identity history."""
import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
from tests.test_api_projects_db import WORKSPACE_A

HEAD = "0034_worker_execution"
PROJECT_A = "a0000000-0000-4000-8000-000000000001"


def _config():
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return config


def _head(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_0026_empty_downgrade_and_reupgrade(migrated):
    assert _head(migrated) == HEAD
    try:
        command.downgrade(_config(), "0025_provider_callback_route")
        assert _head(migrated) == "0025_provider_callback_route"
        with psycopg.connect(migrated) as db:
            names = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='projects'")}
            assert "active_sender_identity_version_id" not in names
    finally:
        command.upgrade(_config(), "head")
    assert _head(migrated) == HEAD


def test_0026_refuses_to_drop_reviewed_sender(seeded):
    sender_id = uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("INSERT INTO sender_identity_versions(id,workspace_id,project_id,version_key,display_name,"
                   "organization,business_email,country,reviewed_at) "
                   "VALUES (%s,%s,%s,%s,'Alex','ProjectA Co','alex@example.test','US',now())",
                   (sender_id, WORKSPACE_A, PROJECT_A, f"sender:{sender_id}:1"))
        db.execute("UPDATE projects SET active_sender_identity_version_id=%s WHERE id=%s",
                   (sender_id, PROJECT_A))
    try:
        with pytest.raises(RuntimeError, match="retained reviewed sender versions"):
            command.downgrade(_config(), "0025_provider_callback_route")
        assert _head(seeded) == HEAD
        with psycopg.connect(seeded) as db:
            assert db.execute("SELECT active_sender_identity_version_id FROM projects WHERE id=%s",
                              (PROJECT_A,)).fetchone()[0] == sender_id
    finally:
        with psycopg.connect(seeded, autocommit=True) as db:
            db.execute("UPDATE projects SET active_sender_identity_version_id=NULL WHERE id=%s", (PROJECT_A,))
            db.execute("DELETE FROM sender_identity_versions WHERE id=%s", (sender_id,))
