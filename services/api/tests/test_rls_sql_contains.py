from pathlib import Path

MIGRATION = Path("alembic/versions/0002_rls_and_roles.py")


def test_rls_migration_exists():
    assert MIGRATION.exists()


def test_rls_migration_enforces_tenant_context():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "current_setting('app.workspace_id')" in src
    assert "NOBYPASSRLS" in src


def test_rls_migration_downgrade_reverses_policy():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "DROP POLICY IF EXISTS tenant_isolation" in src
