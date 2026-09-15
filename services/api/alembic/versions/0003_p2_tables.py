"""P2 domain tables (projects, buyers, evidence, policy, budget, outbox) + RLS

Revision ID: 0003_p2_tables
Revises: 0002_rls_and_roles
Create Date: 2026-09-15

Adds the persistence slice for BO-007/008/009/010/011 and enables the same
transaction-local RLS policy on every new tenant table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_p2_tables"
down_revision: str | None = "0002_rls_and_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
MONEY = sa.Numeric(20, 6)

TENANT_TABLES = (
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
        "projects",
        *_common("projects"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    )
    op.create_table(
        "icp_versions",
        *_common("icp_versions"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("number", sa.BigInteger(), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("parent_id", UUID, nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", UUID, nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_icp_versions_project"
        ),
        sa.UniqueConstraint("workspace_id", "project_id", "number", name="uq_icp_versions_project_number"),
    )
    op.create_table(
        "companies",
        *_common("companies"),
        sa.Column("legal_name", sa.String(400), nullable=False),
        sa.Column("display_name", sa.String(400), nullable=False),
        sa.Column("domain", sa.String(255), nullable=True),
        sa.Column("registry_id", sa.String(128), nullable=True),
    )
    op.create_table(
        "project_buyers",
        *_common("project_buyers"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("owner_user_id", UUID, nullable=True),
        sa.Column("note", sa.String(4000), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_project_buyers_project"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_project_buyers_company"
        ),
        sa.UniqueConstraint("workspace_id", "project_id", "company_id", name="uq_project_buyers_project_company"),
    )
    op.create_table(
        "source_documents",
        *_common("source_documents"),
        sa.Column("canonical_url", sa.String(2000), nullable=False),
        sa.Column("digest", sa.String(80), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("storage_mode", sa.String(32), nullable=False, server_default="excerpt_only"),
    )
    op.create_table(
        "evidence",
        *_common("evidence"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("company_id", UUID, nullable=False),
        sa.Column("source_document_id", UUID, nullable=True),
        sa.Column("requirement_id", sa.String(64), nullable=True),
        sa.Column("stance", sa.String(16), nullable=False),
        sa.Column("excerpt", sa.String(4000), nullable=False),
        sa.Column("translation", sa.String(4000), nullable=True),
        sa.Column("is_inference", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_evidence_project"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "company_id"], ["companies.workspace_id", "companies.id"], name="fk_evidence_company"
        ),
    )
    op.create_table(
        "fit_assessments",
        *_common("fit_assessments"),
        sa.Column("project_buyer_id", UUID, nullable=False),
        sa.Column("icp_version_id", UUID, nullable=False),
        sa.Column("evidence_set_hash", sa.String(80), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("rationale", sa.String(4000), nullable=False),
        sa.Column("evidence_ids", JSONB, nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.id"],
            name="fk_fit_assessments_buyer",
        ),
    )
    op.create_table(
        "human_reviews",
        *_common("human_reviews"),
        sa.Column("project_buyer_id", UUID, nullable=False),
        sa.Column("fit_assessment_id", UUID, nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(400), nullable=True),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.id"],
            name="fk_human_reviews_buyer",
        ),
    )
    op.create_table(
        "buyer_lists",
        *_common("buyer_lists"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_buyer_lists_project"
        ),
    )
    op.create_table(
        "list_memberships",
        *_common("list_memberships"),
        sa.Column("list_id", UUID, nullable=False),
        sa.Column("buyer_id", UUID, nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id", "list_id"], ["buyer_lists.workspace_id", "buyer_lists.id"], name="fk_list_memberships_list"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.id"],
            name="fk_list_memberships_buyer",
        ),
        sa.UniqueConstraint("workspace_id", "list_id", "buyer_id", name="uq_list_memberships_list_buyer"),
    )
    op.create_table(
        "buyer_snapshots",
        *_common("buyer_snapshots"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("filter_hash", sa.String(80), nullable=False),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "buyer_snapshot_items",
        *_common("buyer_snapshot_items"),
        sa.Column("snapshot_id", UUID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("buyer_id", UUID, nullable=False),
        sa.Column("buyer_version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "snapshot_id"],
            ["buyer_snapshots.workspace_id", "buyer_snapshots.id"],
            name="fk_buyer_snapshot_items_snapshot",
        ),
        sa.UniqueConstraint("workspace_id", "snapshot_id", "ordinal", name="uq_buyer_snapshot_items_ordinal"),
    )
    op.create_table(
        "policy_decisions",
        *_common("policy_decisions"),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("basis", sa.String(400), nullable=True),
        sa.Column("version", sa.String(64), nullable=False, server_default="v1"),
        sa.Column("supersedes_id", UUID, nullable=True),
        sa.Column("review_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "suppressions",
        *_common("suppressions"),
        sa.Column("subject_key_hash", sa.String(80), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(400), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("removed_reason", sa.String(400), nullable=True),
    )
    op.create_table(
        "budget_accounts",
        *_common("budget_accounts"),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("approved_limit", MONEY, nullable=False, server_default="0.000000"),
        sa.Column("settled_spend", MONEY, nullable=False, server_default="0.000000"),
        sa.UniqueConstraint("workspace_id", "scope", "currency", "period", name="uq_budget_accounts_scope_period"),
    )
    op.create_table(
        "budget_reservations",
        *_common("budget_reservations"),
        sa.Column("account_id", UUID, nullable=False),
        sa.Column("intent_key", sa.String(128), nullable=False),
        sa.Column("upper_bound", MONEY, nullable=False),
        sa.Column("remaining_hold", MONEY, nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="active"),
        sa.UniqueConstraint("workspace_id", "intent_key", name="uq_budget_reservations_intent"),
    )
    op.create_table(
        "cost_events",
        *_common("cost_events"),
        sa.Column("operation_id", UUID, nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("pricing_version", sa.String(64), nullable=False, server_default="v1"),
    )
    op.create_table(
        "outbox_events",
        *_common("outbox_events"),
        sa.Column("intent_key", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(32), nullable=False, server_default="ready"),
        sa.UniqueConstraint("workspace_id", "intent_key", "event_type", name="uq_outbox_events_intent_type"),
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
