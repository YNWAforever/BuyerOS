"""Constrain draft buyer scope and make written revisions immutable.

Revision ID: 0027_draft_integrity
Revises: 0026_sender_identity_versions
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_draft_integrity"
down_revision: str | None = "0026_sender_identity_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    invalid = op.get_bind().execute(sa.text("""
        SELECT d.id FROM outreach_drafts d LEFT JOIN project_buyers b
          ON b.workspace_id=d.workspace_id AND b.project_id=d.project_id AND b.id=d.buyer_id
        WHERE b.id IS NULL LIMIT 5
    """)).scalars().all()
    if invalid:
        raise RuntimeError(f"draft buyer scope remediation required: {invalid}")
    op.create_foreign_key("fk_outreach_drafts_buyer_project", "outreach_drafts", "project_buyers",
                          ["workspace_id", "project_id", "buyer_id"],
                          ["workspace_id", "project_id", "id"])
    op.create_index("ix_outreach_drafts_project_page", "outreach_drafts",
                    ["workspace_id", "project_id", "created_at", "id"])
    op.execute("""
        CREATE FUNCTION reject_draft_revision_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'draft revision is immutable'; END $$
    """)
    op.execute("""
        CREATE TRIGGER draft_revision_immutable BEFORE UPDATE ON draft_revisions
        FOR EACH ROW EXECUTE FUNCTION reject_draft_revision_update()
    """)


def downgrade() -> None:
    retained = op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM outreach_drafts LIMIT 1)"))
    if retained.scalar_one():
        raise RuntimeError("0027 downgrade blocked: retained drafts")
    op.execute("DROP TRIGGER draft_revision_immutable ON draft_revisions")
    op.execute("DROP FUNCTION reject_draft_revision_update()")
    op.drop_index("ix_outreach_drafts_project_page", table_name="outreach_drafts")
    op.drop_constraint("fk_outreach_drafts_buyer_project", "outreach_drafts", type_="foreignkey")
