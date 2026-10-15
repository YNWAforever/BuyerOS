"""Private bytes survive a refused downgrade; empty rollback restores guards."""
import uuid
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT


def test_private_storage_empty_roundtrip_and_populated_refusal(isolated_migrated, monkeypatch):
    dsn = isolated_migrated
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    monkeypatch.setenv("BUYEROS_DATABASE_URL", dsn)
    monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", dsn)
    get_settings.cache_clear()
    workspace, object_id = uuid.uuid4(), uuid.uuid4()
    try:
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='private_document_objects'").fetchone() == (True, True)
            assert db.execute("SELECT has_table_privilege('buyeros_api','private_document_objects','UPDATE'),has_table_privilege('buyeros_worker','private_document_objects','UPDATE')").fetchone() == (False, False)
            db.execute("INSERT INTO workspaces(id,name) VALUES(%s,'Private storage rollback fixture')", (workspace,))
            db.execute("INSERT INTO private_document_objects(id,workspace_id,body,source_sha256,retention_until) VALUES(%s,%s,'hello'::bytea,'2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',now()+interval '1 hour')", (object_id, workspace))
        with pytest.raises(RuntimeError, match="retain private document bytes"):
            command.downgrade(config, "0051_buyer_imports")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0055_lead_workflow",)
            assert bytes(db.execute("SELECT body FROM private_document_objects WHERE id=%s", (object_id,)).fetchone()[0]) == b"hello"
            db.execute("DELETE FROM private_document_objects WHERE id=%s", (object_id,))
        command.downgrade(config, "0051_buyer_imports")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT to_regclass('private_document_objects')").fetchone() == (None,)
            assert db.execute("SELECT buyeros_search_receipts_writable(),buyeros_model_receipts_writable(),buyeros_contact_receipts_writable()").fetchone() == (True, True, True)
        command.upgrade(config, "head")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT buyeros_search_receipts_writable(),buyeros_model_receipts_writable(),buyeros_contact_receipts_writable()").fetchone() == (True, True, True)
    finally:
        get_settings.cache_clear()


def test_non_bypass_table_owner_cannot_drop_hidden_private_bytes(isolated_migrated, monkeypatch):
    dsn = isolated_migrated
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    # Exercise the original 0052 guard with its non-bypass private-table owner.
    monkeypatch.setenv("BUYEROS_DATABASE_URL", dsn)
    monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", dsn)
    get_settings.cache_clear()
    command.downgrade(config, "0052_private_document_storage")
    role = "private_owner_" + uuid.uuid4().hex[:12]
    workspace, object_id = uuid.uuid4(), uuid.uuid4()
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute(psycopg.sql.SQL("CREATE ROLE {} LOGIN PASSWORD 'test-only' NOSUPERUSER NOBYPASSRLS").format(psycopg.sql.Identifier(role)))
        db.execute(psycopg.sql.SQL("GRANT USAGE,CREATE ON SCHEMA public TO {}").format(psycopg.sql.Identifier(role)))
        db.execute(psycopg.sql.SQL("GRANT SELECT,UPDATE,DELETE ON alembic_version TO {}").format(psycopg.sql.Identifier(role)))
        db.execute("INSERT INTO workspaces(id,name) VALUES(%s,'Non-bypass migration fixture')", (workspace,))
        db.execute("INSERT INTO private_document_objects(id,workspace_id,body,source_sha256,retention_until) VALUES(%s,%s,'hello'::bytea,'2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',now()+interval '1 hour')", (object_id, workspace))
        db.execute(psycopg.sql.SQL("ALTER TABLE private_document_objects OWNER TO {}").format(psycopg.sql.Identifier(role)))
        for service in ("search", "model", "contact"):
            db.execute(psycopg.sql.SQL("ALTER FUNCTION {}() OWNER TO {}").format(psycopg.sql.Identifier(f"buyeros_{service}_receipts_writable"), psycopg.sql.Identifier(role)))
    parts = urlsplit(dsn)
    owner_dsn = urlunsplit(parts._replace(netloc=f"{role}:test-only@{parts.hostname}:{parts.port}"))
    with psycopg.connect(owner_dsn) as db:
        assert db.execute("SELECT count(*) FROM private_document_objects").fetchone() == (0,)
    monkeypatch.setenv("BUYEROS_DATABASE_URL", owner_dsn)
    monkeypatch.setenv("BUYEROS_DATABASE_MIGRATION_URL", owner_dsn)
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="retain private document bytes"):
            command.downgrade(config, "0051_buyer_imports")
        with psycopg.connect(dsn) as db:
            assert db.execute("SELECT version_num FROM alembic_version").fetchone() == ("0052_private_document_storage",)
            assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='private_document_objects'").fetchone() == (True, True)
            assert bytes(db.execute("SELECT body FROM private_document_objects WHERE id=%s", (object_id,)).fetchone()[0]) == b"hello"
    finally:
        get_settings.cache_clear()
