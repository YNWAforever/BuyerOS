from pathlib import Path

from buyeros_api.db import budget, buyers, contact, drafts, icp, models, outcomes, outbox, policy  # noqa: F401
from buyeros_api.db.base import Base

MIGRATION = Path("alembic/versions/0004_p4_p5_tables.py")

P4_P5_TABLES = {
    "enrichment_quotes",
    "enrichment_jobs",
    "provider_operations",
    "provider_events",
    "idempotency_records",
    "sender_identity_versions",
    "outreach_drafts",
    "draft_revisions",
    "approvals",
    "outcome_events",
    "export_jobs",
    "audit_events",
}


def test_p4_p5_tables_are_declared():
    assert P4_P5_TABLES.issubset(set(Base.metadata.tables))


def test_p4_p5_tenant_tables_have_workspace_id():
    for name in P4_P5_TABLES:
        assert "workspace_id" in Base.metadata.tables[name].columns, name


def test_migration_enables_rls_on_p4_p5_tables():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in src
    for table in P4_P5_TABLES:
        assert f'"{table}"' in src, table


def test_only_quote_table_holds_money():
    assert "max_cost" in Base.metadata.tables["enrichment_quotes"].columns
    assert "amount" in Base.metadata.tables["cost_events"].columns
