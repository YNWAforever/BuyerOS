"""Database-backed tenant isolation tests (RLS under a non-owner role).

These run against the disposable PostgreSQL from ``conftest.pg_dsn`` and skip
when no database is available.
"""

import psycopg
import pytest

from tests.conftest import runtime_role_dsn

WORKSPACE_A = "11111111-1111-4111-8111-111111111111"
WORKSPACE_B = "22222222-2222-4222-8222-222222222222"


def _names(conn) -> list[str]:
    return [row[0] for row in conn.execute("SELECT name FROM projects ORDER BY name").fetchall()]


def test_missing_tenant_context_fails_closed(seeded):
    with psycopg.connect(runtime_role_dsn(seeded)) as conn:
        with pytest.raises(psycopg.errors.UndefinedObject):
            conn.execute("SELECT count(*) FROM projects").fetchall()


def test_snapshot_less_reads_are_workspace_scoped(seeded):
    with psycopg.connect(runtime_role_dsn(seeded)) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_A,))
        assert _names(conn) == ["ProjectA"]

    with psycopg.connect(runtime_role_dsn(seeded)) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_B,))
        assert _names(conn) == ["ProjectB"]


def test_cross_tenant_write_is_rejected(seeded):
    with psycopg.connect(runtime_role_dsn(seeded)) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_A,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO projects(id, workspace_id, name) VALUES (%s, %s, %s)",
                ("c0000000-0000-4000-8000-000000000003", WORKSPACE_B, "Sneaky"),
            )


def test_runtime_role_cannot_read_other_workspace_rows(seeded):
    with psycopg.connect(runtime_role_dsn(seeded)) as conn:
        conn.execute("SELECT set_config('app.workspace_id', %s, false)", (WORKSPACE_A,))
        rows = conn.execute("SELECT workspace_id FROM projects").fetchall()
        assert {str(r[0]) for r in rows} == {WORKSPACE_A}


def test_rls_is_forced_on_p4_p5_tables(seeded):
    with psycopg.connect(seeded) as conn:
        rows = conn.execute(
            "SELECT relname FROM pg_class WHERE relrowsecurity AND relforcerowsecurity"
        ).fetchall()
    protected = {row[0] for row in rows}
    expected = {
        "projects",
        "evidence",
        "budget_accounts",
        "outbox_events",
        "enrichment_quotes",
        "enrichment_jobs",
        "provider_operations",
        "provider_events",
        "outreach_drafts",
        "draft_revisions",
        "approvals",
        "outcome_events",
        "export_jobs",
        "audit_events",
        "search_runs",
        "run_events",
        "raw_candidates",
        "company_aliases",
        "people",
        "contact_points",
        "worker_leases",
    }
    assert expected <= protected, expected - protected
