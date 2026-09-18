"""project profile columns and ICP supersession

Revision ID: 0009_project_profile_columns
Revises: 0008_grant_users_select
Create Date: 2026-09-18

The contract's `Project` requires company_name, offer, markets, language_preferences and a
monotonic `version` (the strong ETag used by If-Match on update/archive), and approval needs a
pointer to the active ICP version. `icp_versions.superseded_at` makes the contract's status
(saved | approved | superseded) derivable without rewriting history.

Existing rows are backfilled with empty defaults so the migration applies to a populated
database; the defaults are then dropped so new inserts must supply the values.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_project_profile_columns"
down_revision: str | None = "0008_grant_users_select"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADDED = (
    ("company_name", sa.String(200), ""),
    ("offer", sa.Text(), ""),
    ("markets", postgresql.ARRAY(sa.String(2)), "{}"),
    ("language_preferences", postgresql.ARRAY(sa.String(16)), "{}"),
    ("version", sa.Integer(), "1"),
)


def upgrade() -> None:
    for name, type_, default in _ADDED:
        op.add_column("projects", sa.Column(name, type_, nullable=False, server_default=default))
    op.add_column("projects", sa.Column("website", sa.String(2000), nullable=True))
    op.add_column("projects", sa.Column("active_icp_version_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("icp_versions", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    for name, _, _ in _ADDED:
        op.alter_column("projects", name, server_default=None)


def downgrade() -> None:
    op.drop_column("icp_versions", "superseded_at")
    op.drop_column("projects", "active_icp_version_id")
    op.drop_column("projects", "website")
    for name, _, _ in reversed(_ADDED):
        op.drop_column("projects", name)
