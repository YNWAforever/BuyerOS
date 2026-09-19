"""buyer version and idempotency response storage

Revision ID: 0011_project_buyer_version
Revises: 0010_widen_idempotency_key
Create Date: 2026-09-19

`project_buyers.version` is the buyer's optimistic-concurrency token (If-Match on updateBuyer and each
Selection item). It keeps a server default so a raw insert still starts at 1.

`idempotency_records.response` stores a committed bulk result so a same-key/same-body replay returns the
original response, which a single `resource_id` cannot express for a bulk operation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_project_buyer_version"
down_revision: str | None = "0010_widen_idempotency_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("project_buyers", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("idempotency_records", sa.Column("response", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("idempotency_records", "response")
    op.drop_column("project_buyers", "version")
