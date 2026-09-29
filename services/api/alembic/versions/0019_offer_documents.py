"""Private offer documents and fetched-source retention metadata.

Revision ID: 0019_offer_documents
Revises: 0018_budget_ledger
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_offer_documents"
down_revision: str | None = "0018_budget_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "offer_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(128), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("fact_candidates", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("object_key", sa.String(500), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "id", name="uq_offer_documents_workspace_id"),
        sa.UniqueConstraint("workspace_id", "project_id", "id", name="uq_offer_documents_project_id"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_offer_documents_workspace"),
        sa.ForeignKeyConstraint(
            ["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"],
            name="fk_offer_documents_project",
        ),
        sa.CheckConstraint("kind IN ('upload','url')", name="ck_offer_documents_kind"),
        sa.CheckConstraint(
            "status IN ('quarantined','queued','parsing','ready','failed','deleted')",
            name="ck_offer_documents_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_offer_documents_version_positive"),
    )
    op.create_index("ix_offer_documents_workspace_id", "offer_documents", ["workspace_id"])
    op.create_index("ix_offer_documents_project_status", "offer_documents",
                    ["workspace_id", "project_id", "status", "created_at"])
    op.execute("ALTER TABLE offer_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE offer_documents FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON offer_documents "
        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON offer_documents TO buyeros_api, buyeros_worker")

    op.add_column("source_documents", sa.Column("object_key", sa.String(500), nullable=True))
    op.add_column("source_documents", sa.Column("excerpt", sa.String(4000), nullable=True))
    op.add_column("source_documents", sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    docs = bind.execute(sa.text("SELECT count(*) FROM offer_documents")).scalar_one()
    sources = bind.execute(sa.text(
        "SELECT count(*) FROM source_documents "
        "WHERE object_key IS NOT NULL OR excerpt IS NOT NULL OR retention_until IS NOT NULL"
    )).scalar_one()
    if docs or sources:
        raise RuntimeError(
            f"0019 downgrade blocked: {docs} offer documents and {sources} enriched sources require retention"
        )
    op.drop_column("source_documents", "retention_until")
    op.drop_column("source_documents", "excerpt")
    op.drop_column("source_documents", "object_key")
    op.execute("DROP POLICY tenant_isolation ON offer_documents")
    op.execute("REVOKE ALL ON offer_documents FROM buyeros_api, buyeros_worker")
    op.drop_index("ix_offer_documents_project_status", table_name="offer_documents")
    op.drop_index("ix_offer_documents_workspace_id", table_name="offer_documents")
    op.drop_table("offer_documents")
