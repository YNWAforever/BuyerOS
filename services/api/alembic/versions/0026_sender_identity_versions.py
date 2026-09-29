"""Bind reviewed sender metadata to an active project-owned version.

Revision ID: 0026_sender_identity_versions
Revises: 0025_provider_callback_route
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0026_sender_identity_versions"
down_revision: str | None = "0025_provider_callback_route"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sender_identity_versions", sa.Column("country", sa.String(2), nullable=True))
    op.add_column("sender_identity_versions", sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True))
    op.add_column("sender_identity_versions", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sender_identity_versions", sa.Column("review_reason", sa.String(400), nullable=True))
    op.create_unique_constraint("uq_sender_versions_project_id", "sender_identity_versions",
                                ["workspace_id", "project_id", "id"])
    op.add_column("projects", sa.Column("active_sender_identity_version_id", UUID(as_uuid=True), nullable=True))
    op.add_column("projects", sa.Column("sender_identity_epoch", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key("fk_projects_active_sender_same_project", "projects", "sender_identity_versions",
                          ["workspace_id", "id", "active_sender_identity_version_id"],
                          ["workspace_id", "project_id", "id"])
    op.execute("""
        CREATE FUNCTION reject_sender_content_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF ROW(NEW.workspace_id, NEW.project_id, NEW.version_key, NEW.display_name,
                 NEW.role, NEW.organization, NEW.business_email, NEW.country,
                 NEW.reviewed_by, NEW.reviewed_at, NEW.review_reason)
             IS DISTINCT FROM
             ROW(OLD.workspace_id, OLD.project_id, OLD.version_key, OLD.display_name,
                 OLD.role, OLD.organization, OLD.business_email, OLD.country,
                 OLD.reviewed_by, OLD.reviewed_at, OLD.review_reason) THEN
            RAISE EXCEPTION 'sender identity content is immutable';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER sender_content_immutable BEFORE UPDATE ON sender_identity_versions
        FOR EACH ROW EXECUTE FUNCTION reject_sender_content_update()
    """)


def downgrade() -> None:
    retained = op.get_bind().execute(sa.text("""
        SELECT EXISTS(SELECT 1 FROM projects WHERE active_sender_identity_version_id IS NOT NULL)
            OR EXISTS(SELECT 1 FROM sender_identity_versions WHERE reviewed_at IS NOT NULL)
    """)).scalar_one()
    if retained:
        raise RuntimeError("0026 downgrade blocked: retained reviewed sender versions")
    op.execute("DROP TRIGGER sender_content_immutable ON sender_identity_versions")
    op.execute("DROP FUNCTION reject_sender_content_update()")
    op.drop_constraint("fk_projects_active_sender_same_project", "projects", type_="foreignkey")
    op.drop_column("projects", "sender_identity_epoch")
    op.drop_column("projects", "active_sender_identity_version_id")
    op.drop_constraint("uq_sender_versions_project_id", "sender_identity_versions", type_="unique")
    for column in ("review_reason", "reviewed_at", "reviewed_by", "country"):
        op.drop_column("sender_identity_versions", column)
