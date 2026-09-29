"""0023 rollback preserves actor-bound quote history."""

import uuid

import psycopg
import pytest
from alembic import command
from alembic.config import Config

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT

HEAD = "0033_api_rate_windows"
PREVIOUS = "0022_research_checkpoints"
WORKSPACE = "11111111-1111-4111-8111-111111111111"
PROJECT = "a0000000-0000-4000-8000-000000000001"


def _config():
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return config


def _head(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def test_0023_empty_quote_basis_roundtrip(migrated):
    config = _config()
    assert _head(migrated) == HEAD
    try:
        command.downgrade(config, PREVIOUS)
        assert _head(migrated) == PREVIOUS
        with psycopg.connect(migrated) as db:
            columns = {row[0] for row in db.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name='enrichment_quotes'")}
        assert "actor_id" not in columns and "eligibility" not in columns
    finally:
        command.upgrade(config, "head")
    assert _head(migrated) == HEAD


def test_0023_refuses_downgrade_with_actor_bound_quote(seeded):
    quote_id = str(uuid.uuid4())
    with psycopg.connect(seeded, autocommit=True) as db:
        db.execute(
            "INSERT INTO enrichment_quotes(id,workspace_id,project_id,actor_id,purpose,selection,"
            "request_hash,quote_hash,price_version,max_cost,status,expires_at,adapter_version,roles,eligibility,contact_type) "
            "VALUES (%s,%s,%s,%s,'contact_research','{}'::jsonb,%s,%s,'fixture-v1',0,'quoted',"
            "now()+interval '5 minutes','fixture-v1','[]'::jsonb,'[]'::jsonb,'business_email')",
            (quote_id, WORKSPACE, PROJECT, str(uuid.uuid4()), "a" * 64, "b" * 64),
        )
    try:
        with pytest.raises(RuntimeError, match="retained actor-bound contact quotes"):
            command.downgrade(_config(), PREVIOUS)
        assert _head(seeded) == HEAD
        with psycopg.connect(seeded) as db:
            assert db.execute("SELECT count(*) FROM enrichment_quotes WHERE id=%s", (quote_id,)).fetchone()[0] == 1
    finally:
        with psycopg.connect(seeded, autocommit=True) as db:
            db.execute("DELETE FROM enrichment_quotes WHERE id=%s", (quote_id,))
        command.upgrade(_config(), "head")
