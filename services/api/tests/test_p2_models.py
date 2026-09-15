from pathlib import Path

from buyeros_api.db import budget, buyers, icp, models, outbox, policy  # noqa: F401
from buyeros_api.db.base import Base

MIGRATION = Path("alembic/versions/0003_p2_tables.py")

EXPECTED_TABLES = {
    "workspaces",
    "users",
    "memberships",
    "projects",
    "icp_versions",
    "companies",
    "project_buyers",
    "source_documents",
    "evidence",
    "fit_assessments",
    "human_reviews",
    "buyer_lists",
    "list_memberships",
    "buyer_snapshots",
    "buyer_snapshot_items",
    "policy_decisions",
    "suppressions",
    "budget_accounts",
    "budget_reservations",
    "cost_events",
    "outbox_events",
}


def test_all_domain_tables_are_declared():
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables))


def test_every_p2_tenant_table_has_workspace_id():
    for name in EXPECTED_TABLES - {"workspaces", "users"}:
        assert "workspace_id" in Base.metadata.tables[name].columns, name


def test_p2_migration_enables_rls_on_every_new_tenant_table():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in src
    assert "current_setting('app.workspace_id')" in src
    for table in EXPECTED_TABLES - {"workspaces", "users", "memberships"}:
        assert f'"{table}"' in src, table


def test_money_columns_are_numeric_20_6():
    col = Base.metadata.tables["budget_accounts"].columns["approved_limit"]
    assert (col.type.precision, col.type.scale) == (20, 6)
