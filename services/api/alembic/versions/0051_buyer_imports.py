"""Stage bounded buyer files and retain private provenance under existing tenant RLS."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0051_buyer_imports"
down_revision = "0050_c61_delivery_authorizations"
branch_labels = depends_on = None


def _receipt_guard(head):
    for service in ("search", "model", "contact"):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def _base_columns():
    return [sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("workspace_id", UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    op.create_table("buyer_imports", *_base_columns(),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("preview_digest", sa.String(71), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", JSONB, nullable=True),
        sa.UniqueConstraint("workspace_id", "project_id", "id", name="uq_buyer_imports_project_id"),
        sa.ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], ondelete="CASCADE", name="fk_buyer_imports_project"),
        sa.CheckConstraint("status IN ('previewed','completed')", name="buyer_imports_status"),
        sa.CheckConstraint("preview_digest ~ '^sha256:[0-9a-f]{64}$'", name="buyer_imports_digest"),
        sa.CheckConstraint("jsonb_typeof(manifest)='object' AND octet_length(manifest::text)<=16777216", name="buyer_imports_manifest"),
        sa.CheckConstraint("(status='previewed' AND result IS NULL) OR (status='completed' AND jsonb_typeof(result)='object')", name="buyer_imports_result"),
    )
    op.create_index("ix_buyer_imports_workspace_id", "buyer_imports", ["workspace_id"])
    op.create_index("ix_buyer_imports_scope_actor", "buyer_imports", ["workspace_id", "project_id", "actor_user_id", "created_at"])
    op.create_table("buyer_import_rows", *_base_columns(),
        sa.Column("import_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_buyer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("row_index", sa.Integer, nullable=False),
        sa.UniqueConstraint("workspace_id", "project_buyer_id", name="uq_buyer_import_rows_buyer"),
        sa.UniqueConstraint("workspace_id", "import_id", "row_index", name="uq_buyer_import_rows_source"),
        sa.ForeignKeyConstraint(["workspace_id", "project_id", "import_id"], ["buyer_imports.workspace_id", "buyer_imports.project_id", "buyer_imports.id"], ondelete="CASCADE", name="fk_buyer_import_rows_import"),
        sa.ForeignKeyConstraint(["workspace_id", "project_id", "project_buyer_id"], ["project_buyers.workspace_id", "project_buyers.project_id", "project_buyers.id"], ondelete="CASCADE", name="fk_buyer_import_rows_buyer"),
        sa.CheckConstraint("row_index BETWEEN 0 AND 499", name="buyer_import_rows_index"),
    )
    op.create_index("ix_buyer_import_rows_workspace_id", "buyer_import_rows", ["workspace_id"])
    for table in ("buyer_imports", "buyer_import_rows"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO buyeros_api")
    # The runtime cannot rewrite source cells, scope, digest or expiry after staging.
    op.execute("GRANT UPDATE(status,result,updated_at) ON buyer_imports TO buyeros_api")
    _receipt_guard(revision)


def downgrade():
    # A NOBYPASSRLS migration owner otherwise sees no tenant rows under FORCE.
    # A refusal rolls this DDL back with the surrounding Alembic transaction.
    op.execute("ALTER TABLE buyer_imports NO FORCE ROW LEVEL SECURITY")
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM buyer_imports)")).scalar_one():
        raise RuntimeError("0051 downgrade refused: retained import provenance must not be erased")
    op.drop_table("buyer_import_rows")
    op.drop_table("buyer_imports")
    _receipt_guard(down_revision)
