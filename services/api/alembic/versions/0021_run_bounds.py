"""Persist immutable run admission basis and cumulative execution counters.

Revision ID: 0021_run_bounds
Revises: 0020_research_provenance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_run_bounds"
down_revision: str | None = "0020_research_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("search_runs", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("search_runs", sa.Column("stage", sa.String(40), nullable=False, server_default="queued"))
    op.add_column("search_runs", sa.Column("max_cost", sa.Numeric(20, 6), nullable=False, server_default="0"))
    op.add_column("search_runs", sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("search_runs", sa.Column("execution_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("search_runs", sa.Column("usage_counters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.add_column("search_runs", sa.Column("first_dispatch_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("run_target", "search_runs", "target_companies BETWEEN 0 AND 100")
    op.create_check_constraint("run_max_cost", "search_runs", "max_cost >= 0")


def downgrade() -> None:
    bind = op.get_bind()
    retained = bind.execute(sa.text(
        "SELECT count(*) FROM search_runs WHERE execution_snapshot <> '{}'::jsonb "
        "OR usage_counters <> '{}'::jsonb OR first_dispatch_at IS NOT NULL"
    )).scalar_one()
    if retained:
        raise RuntimeError("0021 downgrade blocked: retained run admission or usage evidence")
    op.drop_constraint("run_max_cost", "search_runs", type_="check")
    op.drop_constraint("run_target", "search_runs", type_="check")
    for name in ("first_dispatch_at", "usage_counters", "execution_snapshot", "attempt", "max_cost", "stage", "version"):
        op.drop_column("search_runs", name)
