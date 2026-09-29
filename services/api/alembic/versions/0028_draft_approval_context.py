"""Bind draft approval review and recipient context without rewriting historical approvals.

Revision ID: 0028_draft_approval_context
Revises: 0027_draft_integrity
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0028_draft_approval_context"
down_revision: str | None = "0027_draft_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contact_points", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("outreach_drafts", sa.Column("state_version", sa.Integer(), nullable=False, server_default="1"))
    op.execute("UPDATE outreach_drafts SET state_version=current_revision")
    op.add_column("outreach_drafts", sa.Column("review_context_hash", sa.String(64), nullable=True))
    op.add_column("outreach_drafts", sa.Column("review_revision_id", UUID(as_uuid=True), nullable=True))
    op.add_column("outreach_drafts", sa.Column("review_context", JSONB, nullable=True))
    op.add_column("approvals", sa.Column("draft_revision_id", UUID(as_uuid=True), nullable=True))
    op.add_column("approvals", sa.Column("recipient_contact_id", UUID(as_uuid=True), nullable=True))
    op.add_column("approvals", sa.Column("recipient_contact_version", sa.Integer(), nullable=True))
    op.add_column("approvals", sa.Column("evidence_set_hash", sa.String(64), nullable=True))
    op.add_column("approvals", sa.Column("icp_version_id", UUID(as_uuid=True), nullable=True))
    op.add_column("approvals", sa.Column("policy_decision_ids", JSONB, nullable=True))
    op.add_column("approvals", sa.Column("sender_identity_version", sa.String(100), nullable=True))
    op.add_column("approvals", sa.Column("context_snapshot", JSONB, nullable=True))
    op.add_column("approvals", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("approvals", sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True))
    duplicate = op.get_bind().execute(sa.text("""
        SELECT workspace_id, draft_id FROM approvals WHERE invalidated_reason IS NULL
        GROUP BY workspace_id, draft_id HAVING count(*) > 1 LIMIT 5
    """)).all()
    if duplicate:
        raise RuntimeError(f"duplicate current approvals require remediation: {duplicate}")
    op.create_unique_constraint("uq_draft_revision_exact_binding", "draft_revisions",
                                ["workspace_id", "draft_id", "revision_number", "id"])
    op.create_foreign_key("fk_approvals_exact_revision", "approvals", "draft_revisions",
                          ["workspace_id", "draft_id", "revision_number", "draft_revision_id"],
                          ["workspace_id", "draft_id", "revision_number", "id"])
    op.create_foreign_key("fk_approvals_contact_workspace", "approvals", "contact_points",
                          ["workspace_id", "recipient_contact_id"], ["workspace_id", "id"])
    op.create_index("uq_approvals_current_draft", "approvals", ["workspace_id", "draft_id"],
                    unique=True, postgresql_where=sa.text("invalidated_reason IS NULL"))
    op.execute("""
        CREATE FUNCTION reject_approval_material_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.invalidated_reason IS NOT NULL AND
             (NEW.invalidated_reason IS DISTINCT FROM OLD.invalidated_reason OR
              NEW.invalidated_at IS DISTINCT FROM OLD.invalidated_at)
          THEN RAISE EXCEPTION 'invalidated approval cannot reactivate'; END IF;
          IF OLD.invalidated_reason IS NULL AND NEW.invalidated_reason IS NOT NULL
             AND NEW.invalidated_at IS NULL
          THEN RAISE EXCEPTION 'approval invalidation requires timestamp'; END IF;
          IF (to_jsonb(NEW) - 'invalidated_reason' - 'invalidated_at' - 'updated_at')
             IS DISTINCT FROM
             (to_jsonb(OLD) - 'invalidated_reason' - 'invalidated_at' - 'updated_at')
          THEN RAISE EXCEPTION 'approval material is immutable'; END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER approval_material_immutable BEFORE UPDATE ON approvals
        FOR EACH ROW EXECUTE FUNCTION reject_approval_material_update()
    """)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS(SELECT 1 FROM approvals LIMIT 1)")).scalar_one():
        raise RuntimeError("0028 downgrade blocked: retained approval history")
    if connection.execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM outreach_drafts WHERE review_context_hash IS NOT NULL)"
    )).scalar_one():
        raise RuntimeError("0028 downgrade blocked: retained review requests")
    op.execute("DROP TRIGGER approval_material_immutable ON approvals")
    op.execute("DROP FUNCTION reject_approval_material_update()")
    op.drop_index("uq_approvals_current_draft", table_name="approvals")
    op.drop_constraint("fk_approvals_contact_workspace", "approvals", type_="foreignkey")
    op.drop_constraint("fk_approvals_exact_revision", "approvals", type_="foreignkey")
    op.drop_constraint("uq_draft_revision_exact_binding", "draft_revisions", type_="unique")
    for column in ("invalidated_at", "approved_at", "context_snapshot", "sender_identity_version",
                   "policy_decision_ids", "icp_version_id", "evidence_set_hash",
                   "recipient_contact_version", "recipient_contact_id", "draft_revision_id"):
        op.drop_column("approvals", column)
    op.drop_column("outreach_drafts", "review_context")
    op.drop_column("outreach_drafts", "review_revision_id")
    op.drop_column("outreach_drafts", "review_context_hash")
    op.drop_column("outreach_drafts", "state_version")
    op.drop_column("contact_points", "version")
