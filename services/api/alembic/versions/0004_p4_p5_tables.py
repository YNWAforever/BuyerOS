"""P4/P5 tables (quotes, provider ops, drafts, approvals, outcomes) + RLS

Revision ID: 0004_p4_p5_tables
Revises: 0003_p2_tables
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_p4_p5_tables"
down_revision: str | None = "0003_p2_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
MONEY = sa.Numeric(20, 6)

TENANT_TABLES = (
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
        "enrichment_quotes",
        *_common("enrichment_quotes"),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("selection", JSONB, nullable=False),
        sa.Column("request_hash", sa.String(80), nullable=False),
        sa.Column("quote_hash", sa.String(80), nullable=False),
        sa.Column("price_version", sa.String(64), nullable=False),
        sa.Column("max_cost", MONEY, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="quoted"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reservation_id", UUID, nullable=True),
        sa.Column("consumed_job_id", UUID, nullable=True),
    )
    op.create_table(
        "enrichment_jobs",
        *_common("enrichment_jobs"),
        sa.Column("quote_id", UUID, nullable=False),
        sa.Column("reservation_id", UUID, nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="reserved"),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("workspace_id", "quote_id", name="uq_enrichment_jobs_quote"),
    )
    op.create_table(
        "provider_operations",
        *_common("provider_operations"),
        sa.Column("intent_key", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("input_hash", sa.String(80), nullable=False),
        sa.Column("provider_ref", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="intent"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("workspace_id", "intent_key", name="uq_provider_operations_intent"),
    )
    op.create_table(
        "provider_events",
        *_common("provider_events"),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("account_reference", sa.String(128), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("digest", sa.String(80), nullable=False),
        sa.Column("operation_id", UUID, nullable=True),
        sa.Column("processing_state", sa.String(32), nullable=False, server_default="received"),
        sa.UniqueConstraint("provider", "account_reference", "event_id", name="uq_provider_events_identity"),
    )
    op.create_table(
        "idempotency_records",
        *_common("idempotency_records"),
        sa.Column("actor_id", UUID, nullable=False),
        sa.Column("operation_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(80), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_progress"),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.UniqueConstraint("workspace_id", "actor_id", "operation_id", "key", name="uq_idempotency_records_scope"),
    )
    op.create_table(
        "sender_identity_versions",
        *_common("sender_identity_versions"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("version_key", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(200), nullable=True),
        sa.Column("organization", sa.String(200), nullable=True),
        sa.Column("business_email", sa.String(255), nullable=False),
        sa.Column("retired", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_sender_versions_project"
        ),
        sa.UniqueConstraint("workspace_id", "project_id", "version_key", name="uq_sender_identity_versions_key"),
    )
    op.create_table(
        "outreach_drafts",
        *_common("outreach_drafts"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("buyer_id", UUID, nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(32), nullable=False, server_default="draft"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_outreach_drafts_project"
        ),
    )
    op.create_table(
        "draft_revisions",
        *_common("draft_revisions"),
        sa.Column("draft_id", UUID, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("offer_fact_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.ForeignKeyConstraint(
            ["workspace_id", "draft_id"], ["outreach_drafts.workspace_id", "outreach_drafts.id"], name="fk_draft_revisions_draft"
        ),
        sa.UniqueConstraint("workspace_id", "draft_id", "revision_number", name="uq_draft_revisions_number"),
    )
    op.create_table(
        "approvals",
        *_common("approvals"),
        sa.Column("draft_id", UUID, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(80), nullable=False),
        sa.Column("context_fingerprint", sa.String(80), nullable=False),
        sa.Column("serializer_version", sa.String(32), nullable=False, server_default="approval-cjson-v1"),
        sa.Column("approver_id", UUID, nullable=False),
        sa.Column("invalidated_reason", sa.String(400), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "draft_id"], ["outreach_drafts.workspace_id", "outreach_drafts.id"], name="fk_approvals_draft"
        ),
    )
    op.create_table(
        "outcome_events",
        *_common("outcome_events"),
        sa.Column("buyer_id", UUID, nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("supersedes_id", UUID, nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "buyer_id"], ["project_buyers.workspace_id", "project_buyers.id"], name="fk_outcome_events_buyer"
        ),
    )
    op.create_table(
        "export_jobs",
        *_common("export_jobs"),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("scope_hash", sa.String(80), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="ready"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redaction_summary", JSONB, nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_export_jobs_project"
        ),
    )
    op.create_table(
        "audit_events",
        *_common("audit_events"),
        sa.Column("actor_id", UUID, nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("detail_digest", sa.String(80), nullable=True),
        sa.Column("reason", sa.String(400), nullable=True),
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
