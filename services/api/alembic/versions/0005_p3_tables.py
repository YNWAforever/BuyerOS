"""P3 tables (runs, events, candidates, aliases, contacts) + RLS

Revision ID: 0005_p3_tables
Revises: 0004_p4_p5_tables
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_p3_tables"
down_revision: str | None = "0004_p4_p5_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB

TENANT_TABLES = (
    "search_runs",
    "run_events",
    "raw_candidates",
    "company_aliases",
    "people",
    "contact_points",
)


def _common(table: str):
    return [
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name=f"fk_{table}_workspace"),
        sa.UniqueConstraint("workspace_id", "id", name=f"uq_{table}_workspace_id"),
    ]


def upgrade() -> None:
    op.create_table(
        "search_runs",
        *_common("search_runs"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("icp_version_id", UUID, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("limits", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("target_companies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("terminal_reason", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_search_runs_project"
        ),
    )
    op.create_table(
        "run_events",
        *_common("run_events"),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id"], ["search_runs.workspace_id", "search_runs.id"], name="fk_run_events_run"
        ),
        sa.UniqueConstraint("workspace_id", "run_id", "sequence", name="uq_run_events_sequence"),
    )
    op.create_table(
        "raw_candidates",
        *_common("raw_candidates"),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("normalized_url", sa.String(2000), nullable=False),
        sa.Column("external_ref", sa.String(255), nullable=True),
        sa.Column("raw_digest", sa.String(80), nullable=True),
        sa.Column("canonical_company_id", UUID, nullable=True),
        sa.Column("merge_state", sa.String(16), nullable=False, server_default="unmapped"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "run_id"], ["search_runs.workspace_id", "search_runs.id"], name="fk_raw_candidates_run"
        ),
        sa.UniqueConstraint("workspace_id", "run_id", "normalized_url", name="uq_raw_candidates_run_url"),
    )
    op.create_table(
        "company_aliases",
        *_common("company_aliases"),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("alias_type", sa.String(32), nullable=False),
        sa.Column("normalized_value", sa.String(400), nullable=False),
        sa.Column("provenance", sa.String(400), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_company_aliases_company"
        ),
    )
    op.create_table(
        "people",
        *_common("people"),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("full_name", sa.String(200), nullable=True),
        sa.Column("role", sa.String(200), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_people_company"
        ),
    )
    op.create_table(
        "contact_points",
        *_common("contact_points"),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("person_id", UUID, nullable=True),
        sa.Column("type", sa.String(32), nullable=False, server_default="business_email"),
        sa.Column("normalized_value", sa.String(400), nullable=False),
        sa.Column("validity", sa.String(32), nullable=False, server_default="unverified_public"),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quarantined", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_contact_points_company"
        ),
        sa.UniqueConstraint("workspace_id", "company_id", "type", "normalized_value", name="uq_contact_points_value"),
    )

    for table in TENANT_TABLES:
        op.create_index(f"ix_{table}_workspace_id", table, ["workspace_id"])
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
            "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO buyeros_api, buyeros_worker;")


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"REVOKE ALL ON {table} FROM buyeros_api, buyeros_worker;")
    for table in reversed(TENANT_TABLES):
        op.drop_table(table)
