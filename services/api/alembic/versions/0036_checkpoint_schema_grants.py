"""Keep the pinned saver schema-version table read-only for native workers.

Revision ID: 0036_checkpoint_schema_grants
Revises: 0035_worker_recovery_probe
"""
from alembic import op

revision = '0036_checkpoint_schema_grants'
down_revision = '0035_worker_recovery_probe'
branch_labels = None
depends_on = None


def upgrade():
    # 0022's ALL TABLES grant included version bookkeeping. Native savers need
    # SELECT here; only the Alembic owner may change the schema-version rows.
    op.execute('REVOKE ALL ON buyeros_graph.checkpoint_migrations FROM buyeros_worker')
    op.execute('GRANT SELECT ON buyeros_graph.checkpoint_migrations TO buyeros_worker')


def downgrade():
    # Older compatible savers also use only SELECT. Keep this security fix and
    # every checkpoint row when rolling back the application/revision marker.
    # Restoring unnecessary version-write privileges is not a safe rollback.
    pass
