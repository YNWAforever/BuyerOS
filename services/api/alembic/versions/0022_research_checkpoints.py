"""Own LangGraph Postgres saver 3.1.2 schema in Alembic, never at runtime.

Revision ID: 0022_research_checkpoints
Revises: 0021_run_bounds

The table layout matches saver MIGRATIONS 0..9. Indexes are created inside
this empty-schema migration without CONCURRENTLY. Only primitive workflow
references are stored, with workspace isolation enforced on thread_id.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_research_checkpoints"
down_revision: str | None = "0021_run_bounds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "buyeros_graph"
TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
TENANT = "split_part(thread_id, ':', 1) = current_setting('app.workspace_id', true)"


def upgrade() -> None:
    op.add_column("fit_assessments", sa.Column("fit_algorithm_version", sa.String(30),
                                            nullable=False, server_default="legacy"))
    op.add_column("fit_assessments", sa.Column("assessment_details", postgresql.JSONB(),
                                            nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.execute(f"CREATE SCHEMA {SCHEMA}")
    op.execute(f"CREATE TABLE {SCHEMA}.checkpoint_migrations (v INTEGER PRIMARY KEY)")
    op.execute(f"""CREATE TABLE {SCHEMA}.checkpoints (
        thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL, parent_checkpoint_id TEXT, type TEXT,
        checkpoint JSONB NOT NULL, metadata JSONB NOT NULL DEFAULT '{{}}',
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id))""")
    op.execute(f"""CREATE TABLE {SCHEMA}.checkpoint_blobs (
        thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
        channel TEXT NOT NULL, version TEXT NOT NULL, type TEXT, blob BYTEA,
        PRIMARY KEY (thread_id, checkpoint_ns, channel, version))""")
    op.execute(f"""CREATE TABLE {SCHEMA}.checkpoint_writes (
        thread_id TEXT NOT NULL, checkpoint_ns TEXT NOT NULL DEFAULT '',
        checkpoint_id TEXT NOT NULL, task_id TEXT NOT NULL, idx INTEGER NOT NULL,
        channel TEXT NOT NULL, type TEXT, blob BYTEA NOT NULL,
        task_path TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx))""")
    for name in TABLES:
        op.execute(f"CREATE INDEX {name}_thread_id_idx ON {SCHEMA}.{name}(thread_id)")
        op.execute(f"ALTER TABLE {SCHEMA}.{name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {SCHEMA}.{name} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {SCHEMA}.{name} "
                   f"USING ({TENANT}) WITH CHECK ({TENANT})")
    op.execute(f"INSERT INTO {SCHEMA}.checkpoint_migrations(v) SELECT generate_series(0, 9)")
    op.execute(f"GRANT SELECT ON {SCHEMA}.checkpoint_migrations TO buyeros_worker")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {SCHEMA} TO buyeros_worker")
    op.execute(f"GRANT USAGE ON SCHEMA {SCHEMA} TO buyeros_worker")


def downgrade() -> None:
    bind = op.get_bind()
    retained_fit = bind.execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM fit_assessments WHERE fit_algorithm_version <> 'legacy' "
        "OR assessment_details <> '{}'::jsonb LIMIT 1)"
    )).scalar_one()
    if retained_fit:
        raise RuntimeError("0022 downgrade blocked: retained structured fit assessments")
    for name in TABLES:
        retained = bind.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {SCHEMA}.{name} LIMIT 1)")).scalar_one()
        if retained:
            raise RuntimeError("0022 downgrade blocked: retained research checkpoint state")
    for name in reversed(TABLES):
        op.execute(f"DROP TABLE {SCHEMA}.{name}")
    op.execute(f"DROP TABLE {SCHEMA}.checkpoint_migrations")
    op.execute(f"DROP SCHEMA {SCHEMA}")
    op.drop_column("fit_assessments", "assessment_details")
    op.drop_column("fit_assessments", "fit_algorithm_version")
