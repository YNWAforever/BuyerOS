"""T23 migrations round trip when empty and refuse to erase live references."""

import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT
from tests.test_api_projects_db import WORKSPACE_A

HEAD = "0037_bulk_manifests"


def _config():
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return config


def _head(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_0024_0025_empty_roundtrip_preserves_one_head(migrated):
    assert _head(migrated) == HEAD
    try:
        command.downgrade(_config(), "0023_contact_quote_basis")
        assert _head(migrated) == "0023_contact_quote_basis"
        with psycopg.connect(migrated) as db:
            columns = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='provider_operations'")}
            assert "job_id" not in columns and "observed_cost" not in columns
            assert db.execute("SELECT to_regclass('provider_callback_routes')").fetchone()[0] is None
    finally:
        command.upgrade(_config(), "head")
    assert _head(migrated) == HEAD


def test_0025_refuses_to_drop_a_retained_callback_route(seeded):
    operation_id = uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) "
                   "VALUES (%s,%s,%s,'contact',%s,'accepted')",
                   (operation_id, WORKSPACE_A, f"migration:{operation_id}", "a" * 64))
        db.execute("INSERT INTO provider_callback_routes(provider,account_reference,provider_ref,"
                   "workspace_id,operation_id) VALUES ('fixture','fixture-test',%s,%s,%s)",
                   (f"fixture:{operation_id}", WORKSPACE_A, operation_id))
    try:
        with pytest.raises(RuntimeError, match="retained callback routes"):
            command.downgrade(_config(), "0024_contact_job_execution")
        assert _head(seeded) == HEAD
        with psycopg.connect(seeded) as db:
            assert db.execute("SELECT count(*) FROM provider_callback_routes WHERE operation_id=%s",
                              (operation_id,)).fetchone()[0] == 1
    finally:
        with psycopg.connect(seeded, autocommit=True) as db:
            db.execute("DELETE FROM provider_callback_routes WHERE operation_id=%s", (operation_id,))
            db.execute("DELETE FROM provider_operations WHERE id=%s", (operation_id,))


def test_0024_refuses_to_drop_a_retained_provider_reference(seeded):
    operation_id = uuid.uuid4()
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,"
                   "status,provider_name,account_reference,provider_ref) "
                   "VALUES (%s,%s,%s,'contact',%s,'unknown','fixture','fixture-test',%s)",
                   (operation_id, WORKSPACE_A, f"migration:{operation_id}", "b" * 64,
                    f"fixture:{operation_id}"))
    try:
        with pytest.raises(RuntimeError, match="retained provider intents"):
            command.downgrade(_config(), "0023_contact_quote_basis")
        assert _head(seeded) == HEAD
        with psycopg.connect(seeded) as db:
            assert db.execute("SELECT provider_ref FROM provider_operations WHERE id=%s",
                              (operation_id,)).fetchone()[0] == f"fixture:{operation_id}"
    finally:
        with psycopg.connect(seeded, autocommit=True) as db:
            db.execute("DELETE FROM provider_operations WHERE id=%s", (operation_id,))
        command.upgrade(_config(), "head")
