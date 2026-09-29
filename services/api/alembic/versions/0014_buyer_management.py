"""Version buyer lists and persist actor-scoped presets under tenant RLS.

Revision ID: 0014_buyer_management
Revises: 0013_project_link_constraints
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_buyer_management"
down_revision: str | None = "0013_project_link_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    bind = op.get_bind()
    long_names = bind.execute(sa.text("SELECT count(*) FROM buyer_lists WHERE length(name) > 160")).scalar_one()
    if long_names:
        raise RuntimeError(f"0014 upgrade blocked: {long_names} buyer list names exceed 160")
    op.alter_column("project_buyers", "note", type_=sa.String(20000), existing_type=sa.String(4000), existing_nullable=True)
    op.alter_column("buyer_lists", "name", type_=sa.String(160), existing_type=sa.String(200), existing_nullable=False)
    op.add_column("buyer_lists", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_buyer_lists_version_positive", "buyer_lists", "version > 0")
    op.create_table(
        "filter_presets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("actor_user_id", UUID, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        sa.Column("sort", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("workspace_id", "id", name="uq_filter_presets_workspace_id"),
        sa.UniqueConstraint("workspace_id", "project_id", "actor_user_id", "name", name="uq_filter_presets_actor_name"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_filter_presets_workspace"),
        sa.ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], name="fk_filter_presets_project"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_filter_presets_actor"),
        sa.CheckConstraint("version > 0", name="ck_filter_presets_version_positive"),
        sa.CheckConstraint("sort IN ('best_fit', 'name_asc')", name="ck_filter_presets_sort"),
    )
    op.create_index("ix_filter_presets_workspace_id", "filter_presets", ["workspace_id"])
    op.create_index("ix_filter_presets_scope", "filter_presets", ["workspace_id", "project_id", "actor_user_id", "created_at"])
    op.execute("ALTER TABLE filter_presets ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE filter_presets FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON filter_presets "
        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid)"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON filter_presets TO buyeros_api, buyeros_worker")


def downgrade() -> None:
    bind = op.get_bind()
    long_notes = bind.execute(sa.text("SELECT count(*) FROM project_buyers WHERE length(note) > 4000")).scalar_one()
    long_names = bind.execute(sa.text("SELECT count(*) FROM buyer_lists WHERE length(name) > 160")).scalar_one()
    if long_notes or long_names:
        raise RuntimeError(f"0014 downgrade blocked: {long_notes} notes exceed 4000, {long_names} names exceed 160")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON filter_presets")
    op.execute("REVOKE ALL ON filter_presets FROM buyeros_api, buyeros_worker")
    op.drop_index("ix_filter_presets_scope", table_name="filter_presets")
    op.drop_index("ix_filter_presets_workspace_id", table_name="filter_presets")
    op.drop_table("filter_presets")
    op.drop_constraint("ck_buyer_lists_version_positive", "buyer_lists", type_="check")
    op.drop_column("buyer_lists", "version")
    op.alter_column("buyer_lists", "name", type_=sa.String(200), existing_type=sa.String(160), existing_nullable=False)
    op.alter_column("project_buyers", "note", type_=sa.String(4000), existing_type=sa.String(20000), existing_nullable=True)
