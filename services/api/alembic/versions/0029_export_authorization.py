"""Keep actor-bound export manifests so every content read can reauthorize live data.

Revision ID: 0029_export_authorization
Revises: 0028_draft_approval_context
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0029_export_authorization"
down_revision: str | None = "0028_draft_approval_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legacy rows have no actor/manifest; they remain unreadable rather than assigning an owner.
    op.add_column("export_jobs", sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True))
    op.add_column("export_jobs", sa.Column("selection_manifest", JSONB, nullable=True))
    op.add_column("export_jobs", sa.Column("format", sa.String(16), nullable=True))
    op.add_column("export_jobs", sa.Column("include_contact_data", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("export_jobs", sa.Column("policy_purpose", sa.String(32), nullable=True))
    op.add_column("export_jobs", sa.Column("draft_id", UUID(as_uuid=True), nullable=True))
    op.add_column("export_jobs", sa.Column("draft_revision_id", UUID(as_uuid=True), nullable=True))
    op.add_column("export_jobs", sa.Column("approval_id", UUID(as_uuid=True), nullable=True))
    op.add_column("export_jobs", sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("export_jobs", sa.Column("requested_record_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("export_jobs", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_foreign_key("fk_export_jobs_actor", "export_jobs", "users", ["actor_user_id"], ["id"])
    op.create_foreign_key("fk_export_jobs_draft", "export_jobs", "outreach_drafts",
                          ["workspace_id", "draft_id"], ["workspace_id", "id"])
    op.create_foreign_key("fk_export_jobs_revision", "export_jobs", "draft_revisions",
                          ["workspace_id", "draft_revision_id"], ["workspace_id", "id"])
    op.create_foreign_key("fk_export_jobs_approval", "export_jobs", "approvals",
                          ["workspace_id", "approval_id"], ["workspace_id", "id"])
    op.create_index("ix_export_jobs_actor_expiry", "export_jobs",
                    ["workspace_id", "actor_user_id", "expires_at"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM export_jobs LIMIT 1)")).scalar_one():
        raise RuntimeError("0029 downgrade blocked: retained export history")
    op.drop_index("ix_export_jobs_actor_expiry", table_name="export_jobs")
    for name in ("fk_export_jobs_approval", "fk_export_jobs_revision", "fk_export_jobs_draft",
                 "fk_export_jobs_actor"):
        op.drop_constraint(name, "export_jobs", type_="foreignkey")
    for name in ("version", "requested_record_count", "record_count", "approval_id",
                 "draft_revision_id", "draft_id", "policy_purpose", "include_contact_data",
                 "format", "selection_manifest", "actor_user_id"):
        op.drop_column("export_jobs", name)
