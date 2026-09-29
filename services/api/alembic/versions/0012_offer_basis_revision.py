"""Track the offer revision used by immutable ICP versions.

Revision ID: 0012_offer_basis_revision
Revises: 0011_project_buyer_version

Existing projects start at offer revision 1. Existing ICP versions have an
unknown basis (NULL) and must not be treated as freshly basis-verified.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_offer_basis_revision"
down_revision: str | None = "0011_project_buyer_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("offer_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "icp_versions",
        sa.Column("basis_offer_revision", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_icp_versions_basis_positive",
        "icp_versions",
        "basis_offer_revision IS NULL OR basis_offer_revision >= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_icp_versions_basis_positive", "icp_versions", type_="check")
    op.drop_column("icp_versions", "basis_offer_revision")
    op.drop_column("projects", "offer_revision")
