"""Version existing memberships and persist actor preferences and audit request IDs.

Revision ID: 0017_settings_audit
Revises: 0016_bulk_jobs
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_settings_audit"
down_revision: str | None = "0016_bulk_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("memberships", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_memberships_version_positive", "memberships", "version > 0")
    op.add_column("audit_events", sa.Column("request_id", UUID, nullable=True))
    op.create_index("ix_audit_events_workspace_created", "audit_events", ["workspace_id", "created_at", "id"])
    op.create_table(
        "workspace_preferences",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("locale", sa.String(5), nullable=False, server_default="en"),
        sa.Column("default_markets", postgresql.ARRAY(sa.String(2)), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "id", name="uq_workspace_preferences_workspace_id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_preferences_workspace_user"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_workspace_preferences_workspace"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_workspace_preferences_user"),
        sa.CheckConstraint("locale IN ('en','zh-HK')", name="ck_workspace_preferences_locale"),
        sa.CheckConstraint("version > 0", name="ck_workspace_preferences_version"),
    )
    op.create_index("ix_workspace_preferences_workspace_id", "workspace_preferences", ["workspace_id"])
    op.execute("ALTER TABLE workspace_preferences ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspace_preferences FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON workspace_preferences "
        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON workspace_preferences TO buyeros_api")
    # Global infrastructure heartbeat contains no tenant/customer data.
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(128), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("broker_state", sa.String(16), nullable=False),
        sa.CheckConstraint("broker_state IN ('ready','unavailable')", name="ck_worker_heartbeats_broker_state"),
    )
    op.execute("GRANT SELECT ON worker_heartbeats TO buyeros_api")
    op.execute("GRANT SELECT, INSERT, UPDATE ON worker_heartbeats TO buyeros_worker")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM workspace_preferences")).scalar_one():
        raise RuntimeError("0017 downgrade blocked: persisted preferences would be lost")
    if bind.execute(sa.text("SELECT count(*) FROM memberships WHERE version <> 1")).scalar_one():
        raise RuntimeError("0017 downgrade blocked: membership version history would be lost")
    if bind.execute(sa.text("SELECT count(*) FROM audit_events WHERE request_id IS NOT NULL")).scalar_one():
        raise RuntimeError("0017 downgrade blocked: audit request IDs would be lost")
    if bind.execute(sa.text("SELECT count(*) FROM worker_heartbeats")).scalar_one():
        raise RuntimeError("0017 downgrade blocked: worker heartbeat history would be lost")
    op.drop_table("worker_heartbeats")
    op.drop_table("workspace_preferences")
    op.drop_index("ix_audit_events_workspace_created", table_name="audit_events")
    op.drop_column("audit_events", "request_id")
    op.drop_constraint("ck_memberships_version_positive", "memberships", type_="check")
    op.drop_column("memberships", "version")
