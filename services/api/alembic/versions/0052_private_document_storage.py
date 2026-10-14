"""Explicit private Postgres document storage with bounded bytes and tenant RLS."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0052_private_document_storage"
down_revision = "0051_buyer_imports"
branch_labels = depends_on = None


def _receipt_guard(head):
    for service in ("search", "model", "contact"):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    op.create_table(
        "private_document_objects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.LargeBinary(), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.CheckConstraint("octet_length(body) BETWEEN 1 AND 5242880", name="private_object_size"),
        sa.CheckConstraint("source_sha256 = encode(sha256(body), 'hex')", name="private_object_digest"),
        sa.CheckConstraint("retention_until > created_at AND retention_until <= created_at + interval '30 days'", name="private_object_retention"),
    )
    op.create_index("ix_private_document_objects_tenant_expiry", "private_document_objects", ["workspace_id", "retention_until", "id"])
    op.execute("ALTER TABLE private_document_objects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE private_document_objects FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON private_document_objects "
        "USING (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid) "
        "WITH CHECK (workspace_id = nullif(current_setting('app.workspace_id', true), '')::uuid)"
    )
    op.execute("REVOKE ALL ON private_document_objects FROM PUBLIC")
    op.execute("GRANT SELECT,INSERT,DELETE ON private_document_objects TO buyeros_api,buyeros_worker")
    _receipt_guard(revision)


def downgrade():
    # A NOBYPASSRLS migration owner otherwise sees no tenant rows under FORCE
    # RLS. Transactional DDL restores FORCE if retained bytes block rollback.
    op.execute("ALTER TABLE private_document_objects NO FORCE ROW LEVEL SECURITY")
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM private_document_objects)")).scalar_one():
        raise RuntimeError("0052 downgrade blocked: retain private document bytes until approved deletion")
    op.drop_table("private_document_objects")
    _receipt_guard(down_revision)
