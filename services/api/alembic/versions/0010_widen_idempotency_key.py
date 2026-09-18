"""widen idempotency_records.key to the contract's 200 chars

Revision ID: 0010_widen_idempotency_key
Revises: 0009_project_profile_columns
Create Date: 2026-09-18

The contract's `IdempotencyKey` is 8..200 opaque characters, and `begin_idempotency`
enforces that bound, but `idempotency_records.key` was created as `VARCHAR(128)`
(0004_p4_p5_tables). A contract-valid 129..200-char key therefore passed the guard
and failed at INSERT with a Postgres DataError (a 500) instead of a clean result.
Widening the column to 200 makes the storage match the contract.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_widen_idempotency_key"
down_revision: str | None = "0009_project_profile_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "idempotency_records",
        "key",
        type_=sa.String(200),
        existing_type=sa.String(128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "idempotency_records",
        "key",
        type_=sa.String(128),
        existing_type=sa.String(200),
        existing_nullable=False,
    )
