"""Bind optional contact quotes to actor, project and immutable eligibility basis.

Revision ID: 0023_contact_quote_basis
Revises: 0022_research_checkpoints

Legacy quote rows have no proven actor or project basis and remain unreadable by
the new quote API.  New rows carry the basis needed for exact confirmation.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_contact_quote_basis"
down_revision: str | None = "0022_research_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("enrichment_quotes", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("enrichment_quotes", sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("enrichment_quotes", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("enrichment_quotes", sa.Column("adapter_version", sa.String(64), nullable=True))
    op.add_column("enrichment_quotes", sa.Column("roles", postgresql.JSONB(), nullable=True))
    op.add_column("enrichment_quotes", sa.Column("eligibility", postgresql.JSONB(), nullable=True))
    op.add_column("enrichment_quotes", sa.Column("contact_type", sa.String(32), nullable=True))
    op.create_foreign_key("fk_enrichment_quotes_project", "enrichment_quotes", "projects",
                          ["workspace_id", "project_id"], ["workspace_id", "id"])


def downgrade() -> None:
    retained = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM enrichment_quotes WHERE project_id IS NOT NULL OR actor_id IS NOT NULL LIMIT 1)"
    )).scalar_one()
    if retained:
        raise RuntimeError("0023 downgrade blocked: retained actor-bound contact quotes")
    op.drop_constraint("fk_enrichment_quotes_project", "enrichment_quotes", type_="foreignkey")
    for name in ("contact_type", "eligibility", "roles", "adapter_version", "version", "actor_id", "project_id"):
        op.drop_column("enrichment_quotes", name)
