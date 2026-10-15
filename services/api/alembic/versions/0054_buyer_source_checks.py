"""Append-only, tenant-scoped manual public-source checks for buyers."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0054_buyer_source_checks"
down_revision = "0053_resumable_documents"
branch_labels = depends_on = None


def _receipt_fences(head: str) -> None:
    for service in ("search", "model", "contact"):
        op.execute(
            f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
            "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER "
            "SET search_path=pg_catalog,public AS "
            f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$"
        )


def upgrade() -> None:
    op.create_table(
        "buyer_source_checks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column("grade", sa.String(1), nullable=False),
        sa.Column("rationale", sa.String(4000), nullable=False),
        sa.Column("limitations", sa.String(4000), nullable=True),
        sa.Column("sources", JSONB, nullable=False),
        sa.Column("recorded_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "id", name="uq_buyer_source_checks_workspace_id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_buyer_source_checks_workspace"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"],
            name="fk_buyer_source_checks_project",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id", "buyer_id"],
            ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"],
            name="fk_buyer_source_checks_buyer",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"], ["users.id"], name="fk_buyer_source_checks_actor"
        ),
        sa.CheckConstraint("grade IN ('A', 'B', 'C')", name="buyer_source_checks_grade"),
        sa.CheckConstraint(
            "jsonb_typeof(sources) = 'array' AND jsonb_array_length(sources) BETWEEN 1 AND 10",
            name="buyer_source_checks_sources",
        ),
        sa.CheckConstraint("length(btrim(rationale)) BETWEEN 1 AND 4000", name="buyer_source_checks_rationale"),
    )
    op.create_index(
        "ix_buyer_source_checks_buyer_created",
        "buyer_source_checks",
        ["workspace_id", "project_id", "buyer_id", "created_at"],
    )
    op.execute("ALTER TABLE buyer_source_checks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE buyer_source_checks FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON buyer_source_checks "
        "USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) "
        "WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)"
    )
    op.execute("REVOKE ALL ON buyer_source_checks FROM PUBLIC,buyeros_api,buyeros_worker")
    op.execute("GRANT SELECT,INSERT ON buyer_source_checks TO buyeros_api")
    _receipt_fences(revision)


def downgrade() -> None:
    op.execute("ALTER TABLE buyer_source_checks NO FORCE ROW LEVEL SECURITY")
    db = op.get_bind()
    if db.execute(sa.text("SELECT EXISTS(SELECT 1 FROM buyer_source_checks)")).scalar_one():
        raise RuntimeError("0054 downgrade blocked: preserve append-only buyer source checks")
    op.drop_table("buyer_source_checks")
    _receipt_fences(down_revision)
