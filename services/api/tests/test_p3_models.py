from pathlib import Path

from buyeros_api.db import (  # noqa: F401
    budget,
    buyers,
    contact,
    drafts,
    icp,
    models,
    outcomes,
    outbox,
    policy,
    runs,
)
from buyeros_api.db.base import Base

MIGRATION = Path("alembic/versions/0005_p3_tables.py")

P3_TABLES = {"search_runs", "run_events", "raw_candidates", "company_aliases", "people", "contact_points"}


def test_p3_tables_are_declared():
    assert P3_TABLES.issubset(set(Base.metadata.tables))


def test_p3_tenant_tables_have_workspace_id():
    for name in P3_TABLES:
        assert "workspace_id" in Base.metadata.tables[name].columns, name


def test_run_events_have_monotonic_unique_sequence():
    table = Base.metadata.tables["run_events"]
    uniques = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("run_id", "sequence", "workspace_id") in uniques


def test_migration_enables_rls_on_p3_tables():
    src = MIGRATION.read_text(encoding="utf-8")
    assert "FORCE ROW LEVEL SECURITY" in src
    for table in P3_TABLES:
        assert f'"{table}"' in src, table
