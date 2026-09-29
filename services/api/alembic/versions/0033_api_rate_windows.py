"""Durable per-actor API rate windows under tenant RLS.

Revision ID: 0033_api_rate_windows
Revises: 0032_contact_retention
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0033_api_rate_windows"
down_revision: str | None = "0032_contact_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_rate_windows",
        sa.Column("workspace_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("bucket", sa.String(24), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "actor_id", "bucket", "window_start",
                                name="pk_api_rate_windows"),
        sa.CheckConstraint("hits > 0", name="ck_api_rate_windows_positive_hits"),
    )
    op.create_index("ix_api_rate_windows_expiry", "api_rate_windows", ["window_start"])
    op.execute("ALTER TABLE api_rate_windows ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE api_rate_windows FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON api_rate_windows
        USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
        WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON api_rate_windows TO buyeros_api")
    op.execute("GRANT SELECT, DELETE ON api_rate_windows TO buyeros_worker")


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM api_rate_windows LIMIT 1)" )).scalar_one():
        raise RuntimeError("0033 downgrade blocked: retained API rate windows")
    op.execute("REVOKE ALL ON api_rate_windows FROM buyeros_api, buyeros_worker")
    op.execute("DROP POLICY tenant_isolation ON api_rate_windows")
    op.drop_index("ix_api_rate_windows_expiry", table_name="api_rate_windows")
    op.drop_table("api_rate_windows")
