"""Durable actor-bound bulk jobs and per-buyer results.

Revision ID: 0016_bulk_jobs
Revises: 0015_policy_lifecycle
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_bulk_jobs"
down_revision: str | None = "0015_policy_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
UUID = postgresql.UUID(as_uuid=True)


def _tenant_table(name: str) -> None:
    op.create_index(f"ix_{name}_workspace_id", name, ["workspace_id"])
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {name} "
        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid)"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {name} TO buyeros_api, buyeros_worker")


def upgrade() -> None:
    op.create_table(
        "async_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("command", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflicts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "id", name="uq_async_jobs_workspace_id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_async_jobs_workspace"),
        sa.ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_async_jobs_project"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_async_jobs_actor"),
        sa.CheckConstraint("requested BETWEEN 1 AND 1000", name="ck_async_jobs_requested_range"),
        sa.CheckConstraint("processed >= 0 AND processed <= requested", name="ck_async_jobs_processed_range"),
        sa.CheckConstraint("status IN ('queued','running','cancel_requested','cancelled','completed','failed')", name="ck_async_jobs_status"),
    )
    _tenant_table("async_jobs")
    op.create_index("ix_async_jobs_actor_project", "async_jobs", ["workspace_id", "actor_user_id", "project_id", "created_at"])
    op.create_table(
        "async_job_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("job_id", UUID, nullable=False),
        sa.Column("buyer_id", UUID, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("resulting_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "id", name="uq_async_job_items_workspace_id"),
        sa.UniqueConstraint("workspace_id", "job_id", "buyer_id", name="uq_async_job_items_job_buyer"),
        sa.UniqueConstraint("workspace_id", "job_id", "ordinal", name="uq_async_job_items_job_ordinal"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_async_job_items_workspace"),
        sa.ForeignKeyConstraint(["workspace_id", "job_id"], ["async_jobs.workspace_id", "async_jobs.id"], name="fk_async_job_items_job"),
        sa.CheckConstraint("ordinal >= 0 AND expected_version > 0", name="ck_async_job_items_position_version"),
        sa.CheckConstraint("status IN ('pending','updated','unchanged','blocked','conflict','cancelled')", name="ck_async_job_items_status"),
    )
    _tenant_table("async_job_items")
    op.create_index("ix_async_job_items_next", "async_job_items", ["workspace_id", "job_id", "status", "ordinal"])


def downgrade() -> None:
    bind = op.get_bind()
    jobs = bind.execute(sa.text("SELECT count(*) FROM async_jobs")).scalar_one()
    if jobs:
        raise RuntimeError(f"0016 downgrade blocked: {jobs} durable jobs would be lost")
    for name in ("async_job_items", "async_jobs"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {name}")
        op.execute(f"REVOKE ALL ON {name} FROM buyeros_api, buyeros_worker")
    op.drop_index("ix_async_job_items_next", table_name="async_job_items")
    op.drop_index("ix_async_job_items_workspace_id", table_name="async_job_items")
    op.drop_table("async_job_items")
    op.drop_index("ix_async_jobs_actor_project", table_name="async_jobs")
    op.drop_index("ix_async_jobs_workspace_id", table_name="async_jobs")
    op.drop_table("async_jobs")
