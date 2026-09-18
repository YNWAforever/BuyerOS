"""BO-007: the project/profile columns exist and the migration round-trips."""
import uuid

import psycopg
import pytest

from tests.conftest import ALEMBIC_INI, SERVICE_ROOT

PROJECT_COLUMNS = {"company_name", "offer", "website", "markets", "language_preferences", "version", "active_icp_version_id"}


def test_project_profile_columns_exist(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'projects'"
        ).fetchall()
    present = {r[0] for r in rows}
    assert PROJECT_COLUMNS <= present, PROJECT_COLUMNS - present


def test_icp_versions_has_superseded_at(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'icp_versions'"
        ).fetchall()
    assert "superseded_at" in {r[0] for r in rows}


def test_new_project_columns_are_not_nullable(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name = 'projects' AND column_name = ANY(%s)",
            (sorted(PROJECT_COLUMNS),),
        ).fetchall()
    nullable = {r[0] for r in rows if r[1] == "YES"}
    assert nullable == {"website", "active_icp_version_id"}, nullable


def test_0009_downgrade_then_upgrade_backfills_existing_rows(migrated):
    """0009 is reversible, and rows written before it are backfilled on re-upgrade."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))

    workspace_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    try:
        command.downgrade(config, "0008_grant_users_select")
        with psycopg.connect(migrated, autocommit=True) as conn:
            conn.execute("INSERT INTO workspaces(id, name) VALUES (%s, 'legacy')", (workspace_id,))
            conn.execute(
                "INSERT INTO projects(id, workspace_id, name) VALUES (%s, %s, 'Legacy project')",
                (project_id, workspace_id),
            )

        command.upgrade(config, "head")

        with psycopg.connect(migrated) as conn:
            row = conn.execute(
                "SELECT company_name, offer, markets, language_preferences, version, "
                "website, active_icp_version_id FROM projects WHERE id = %s",
                (project_id,),
            ).fetchone()
        assert row is not None
        company_name, offer, markets, language_preferences, version, website, active_icp = row
        assert company_name == ""
        assert offer == ""
        assert markets == []
        assert language_preferences == []
        assert version == 1
        assert website is None
        assert active_icp is None
    finally:
        command.upgrade(config, "head")
        with psycopg.connect(migrated, autocommit=True) as conn:
            conn.execute("DELETE FROM projects WHERE id = %s", (project_id,))
            conn.execute("DELETE FROM workspaces WHERE id = %s", (workspace_id,))
