"""Actor-bound frozen maintenance manifests, preserving ordinary snapshot bounds."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision = "0037_bulk_manifests"
down_revision = "0036_checkpoint_schema_grants"
branch_labels = depends_on = None
UUID = pg.UUID(as_uuid=True)


def _base():
    return [sa.Column("id",UUID,primary_key=True),sa.Column("workspace_id",UUID,nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]


def upgrade():
    op.create_table("bulk_manifests",*_base(),
        sa.Column("project_id",UUID,nullable=False),sa.Column("actor_user_id",UUID,nullable=False),
        sa.Column("specification",pg.JSONB(),nullable=False),sa.Column("operation",sa.String(40),nullable=False),
        sa.Column("command",pg.JSONB(),nullable=False),sa.Column("digest",sa.String(64),nullable=False),
        sa.Column("count",sa.Integer,nullable=False),sa.Column("version",sa.Integer,nullable=False),
        sa.Column("status",sa.String(16),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("job_id",UUID),sa.Column("result",pg.JSONB()),
        sa.UniqueConstraint("workspace_id","id",name="uq_bulk_manifests_workspace_id"),
        sa.ForeignKeyConstraint(["workspace_id"],["workspaces.id"],name="fk_bulk_manifests_workspace"),
        sa.ForeignKeyConstraint(["workspace_id","project_id"],["projects.workspace_id","projects.id"],name="fk_bulk_manifests_project"),
        sa.ForeignKeyConstraint(["actor_user_id"],["users.id"],name="fk_bulk_manifests_actor"),
        sa.CheckConstraint("count BETWEEN 0 AND 10000",name="ck_bulk_manifests_count_range"),
        sa.CheckConstraint("version > 0",name="ck_bulk_manifests_version_positive"),
        sa.CheckConstraint("status IN ('preparing','ready','executed')",name="ck_bulk_manifests_status"))
    op.create_table("bulk_manifest_items",*_base(),sa.Column("manifest_id",UUID,nullable=False),
        sa.Column("buyer_id",UUID,nullable=False),sa.Column("ordinal",sa.Integer,nullable=False),sa.Column("expected_version",sa.Integer,nullable=False),
        sa.UniqueConstraint("workspace_id","id",name="uq_bulk_manifest_items_workspace_id"),
        sa.UniqueConstraint("workspace_id","manifest_id","buyer_id",name="uq_bulk_manifest_items_buyer"),
        sa.UniqueConstraint("workspace_id","manifest_id","ordinal",name="uq_bulk_manifest_items_ordinal"),
        sa.ForeignKeyConstraint(["workspace_id","manifest_id"],["bulk_manifests.workspace_id","bulk_manifests.id"],name="fk_bulk_manifest_items_manifest"),
        sa.CheckConstraint("ordinal BETWEEN 0 AND 9999 AND expected_version > 0",name="ck_bulk_manifest_items_position_version"))
    for table in ["bulk_manifests","bulk_manifest_items"]:
        op.create_index(f"ix_{table}_workspace_id",table,["workspace_id"])
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (workspace_id=current_setting('app.workspace_id')::uuid) WITH CHECK (workspace_id=current_setting('app.workspace_id')::uuid)")
        op.execute(f"GRANT SELECT,INSERT ON {table} TO buyeros_api")
        op.execute(f"GRANT SELECT ON {table} TO buyeros_worker")
    op.execute("GRANT UPDATE ON bulk_manifests TO buyeros_api")
    op.create_index("ix_bulk_manifests_actor_project","bulk_manifests",["workspace_id","actor_user_id","project_id","created_at"])
    op.execute("""CREATE FUNCTION guard_bulk_manifest_item_insert() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM bulk_manifests WHERE workspace_id=NEW.workspace_id AND id=NEW.manifest_id AND status='preparing') THEN
        RAISE EXCEPTION 'bulk manifest item can only be appended while preparing';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("CREATE TRIGGER bulk_manifest_item_insert BEFORE INSERT ON bulk_manifest_items FOR EACH ROW EXECUTE FUNCTION guard_bulk_manifest_item_insert()")
    op.add_column("async_jobs",sa.Column("manifest_id",UUID))
    op.create_foreign_key("fk_async_jobs_manifest","async_jobs","bulk_manifests",["workspace_id","manifest_id"],["workspace_id","id"])
    op.drop_constraint("ck_async_jobs_requested_range","async_jobs",type_="check")
    op.create_check_constraint("ck_async_jobs_requested_range","async_jobs","requested BETWEEN 1 AND 1000 OR (manifest_id IS NOT NULL AND requested BETWEEN 1 AND 10000)")
    op.execute("""CREATE FUNCTION guard_bulk_manifest_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.workspace_id <> OLD.workspace_id OR NEW.project_id <> OLD.project_id OR NEW.actor_user_id <> OLD.actor_user_id
        OR NEW.specification <> OLD.specification OR NEW.command <> OLD.command OR NEW.operation <> OLD.operation OR NEW.expires_at <> OLD.expires_at
        OR (OLD.status <> 'preparing' AND (NEW.digest <> OLD.digest OR NEW.count <> OLD.count)) THEN
        RAISE EXCEPTION 'bulk manifest frozen basis is immutable';
      END IF;
      IF (OLD.status = 'ready' AND NEW.status NOT IN ('ready','executed')) OR (OLD.status = 'executed' AND NEW IS DISTINCT FROM OLD) THEN
        RAISE EXCEPTION 'bulk manifest cannot be reopened or rewritten after execution';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("CREATE TRIGGER bulk_manifest_frozen BEFORE UPDATE ON bulk_manifests FOR EACH ROW EXECUTE FUNCTION guard_bulk_manifest_frozen()")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM bulk_manifests")).scalar_one():
        raise RuntimeError("0037 downgrade blocked: durable manifests and outcomes must be retained")
    op.drop_constraint("fk_async_jobs_manifest","async_jobs",type_="foreignkey")
    op.drop_constraint("ck_async_jobs_requested_range","async_jobs",type_="check")
    op.create_check_constraint("ck_async_jobs_requested_range","async_jobs","requested BETWEEN 1 AND 1000")
    op.drop_column("async_jobs","manifest_id")
    op.execute("DROP TRIGGER bulk_manifest_frozen ON bulk_manifests")
    op.execute("DROP FUNCTION guard_bulk_manifest_frozen()")
    op.execute("DROP TRIGGER bulk_manifest_item_insert ON bulk_manifest_items")
    op.execute("DROP FUNCTION guard_bulk_manifest_item_insert()")
    op.drop_table("bulk_manifest_items")
    op.drop_table("bulk_manifests")
