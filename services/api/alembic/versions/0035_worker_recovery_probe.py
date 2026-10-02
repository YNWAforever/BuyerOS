"""Bounded recovery cursor and minimal Queue/Workflow operational receipt.

Revision ID: 0035_worker_recovery_probe
Revises: 0034_worker_execution
"""
from alembic import op
import sqlalchemy as sa

revision = '0035_worker_recovery_probe'
down_revision = '0034_worker_execution'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('worker_runtime_control', sa.Column('recovery_cursor', sa.UUID(), nullable=True))
    op.execute('GRANT UPDATE(recovery_cursor) ON worker_runtime_control TO buyeros_worker')
    op.execute('GRANT SELECT(backend,enabled,epoch) ON worker_runtime_control TO buyeros_api')
    op.execute("""CREATE TABLE worker_runtime_probe (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        runtime_epoch BIGINT NOT NULL DEFAULT 1 CHECK(runtime_epoch BETWEEN 1 AND 9007199254740991),
        last_probe_id UUID, last_probe_at TIMESTAMPTZ,
        metrics_epoch BIGINT NOT NULL DEFAULT 1 CHECK(metrics_epoch BETWEEN 1 AND 9007199254740991),
        oldest_work_at TIMESTAMPTZ, scan_oldest_at TIMESTAMPTZ,
        CHECK((last_probe_id IS NULL) = (last_probe_at IS NULL)))""")
    op.execute('INSERT INTO worker_runtime_probe(singleton) VALUES(1)')
    op.execute('GRANT SELECT,UPDATE ON worker_runtime_probe TO buyeros_worker')
    op.execute('GRANT SELECT ON worker_runtime_probe TO buyeros_api')


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM worker_runtime_probe "
        "WHERE last_probe_id IS NOT NULL OR oldest_work_at IS NOT NULL OR scan_oldest_at IS NOT NULL) "
        "OR EXISTS(SELECT 1 FROM worker_runtime_control WHERE recovery_cursor IS NOT NULL)")).scalar_one():
        raise RuntimeError('0035 downgrade blocked: retained operational recovery/probe evidence; pause and roll forward')
    op.execute('DROP TABLE worker_runtime_probe')
    op.execute('REVOKE SELECT(backend,enabled,epoch) ON worker_runtime_control FROM buyeros_api')
    op.drop_column('worker_runtime_control', 'recovery_cursor')
