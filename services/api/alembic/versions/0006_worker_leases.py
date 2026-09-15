"""worker leases and outbox dispatch columns"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_worker_leases"
down_revision: str | None = "0005_p3_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("outbox_events", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox_events", sa.Column("lease_owner", sa.String(128), nullable=True))
    op.add_column("outbox_events", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "outbox_events",
        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "worker_leases",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("intent_key", sa.String(128), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(16), nullable=False, server_default="free"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
        sa.UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
    )
    op.create_index("ix_worker_leases_workspace_id", "worker_leases", ["workspace_id"])
    op.execute("ALTER TABLE worker_leases ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE worker_leases FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY tenant_isolation ON worker_leases "
        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON worker_leases TO buyeros_api, buyeros_worker;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON worker_leases;")
    op.drop_table("worker_leases")
    for column in ("fencing_generation", "lease_expires_at", "lease_owner", "dispatched_at"):
        op.drop_column("outbox_events", column)
