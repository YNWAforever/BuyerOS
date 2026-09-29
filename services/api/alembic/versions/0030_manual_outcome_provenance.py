"""Bind manual outcomes to project and make runtime writes append-only.

Revision ID: 0030_manual_outcome_provenance
Revises: 0029_export_authorization
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0030_manual_outcome_provenance"
down_revision: str | None = "0029_export_authorization"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    invalid = connection.execute(sa.text("""
        SELECT id FROM outcome_events
        WHERE occurred_at IS NULL OR notes IS NULL OR length(trim(notes)) < 3
           OR source <> 'manual' OR stage NOT IN ('reply','meeting','opportunity','disqualified')
        LIMIT 5
    """)).all()
    if invalid:
        raise RuntimeError(f"legacy outcomes need owner remediation before 0030: {invalid}")
    forked = connection.execute(sa.text("""
        SELECT supersedes_id FROM outcome_events WHERE supersedes_id IS NOT NULL
        GROUP BY supersedes_id HAVING count(*) > 1 LIMIT 5
    """)).all()
    if forked:
        raise RuntimeError(f"forked outcome corrections need remediation: {forked}")
    op.add_column("outcome_events", sa.Column("project_id", UUID(as_uuid=True), nullable=True))
    op.add_column("outcome_events", sa.Column("provenance_reference", sa.String(1000), nullable=True))
    op.add_column("outcome_events", sa.Column("correction_reason", sa.String(1000), nullable=True))
    op.add_column("outcome_events", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.execute("""
        UPDATE outcome_events AS outcome SET project_id=buyer.project_id
        FROM project_buyers AS buyer
        WHERE outcome.workspace_id=buyer.workspace_id AND outcome.buyer_id=buyer.id
    """)
    if connection.execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM outcome_events WHERE project_id IS NULL)"
    )).scalar_one():
        raise RuntimeError("outcome project backfill incomplete; no relationship may be guessed")
    op.alter_column("outcome_events", "project_id", nullable=False)
    op.create_foreign_key("fk_outcomes_project_buyer", "outcome_events", "project_buyers",
                          ["workspace_id", "project_id", "buyer_id"],
                          ["workspace_id", "project_id", "id"])
    op.create_unique_constraint("uq_outcomes_buyer_id", "outcome_events",
                                ["workspace_id", "buyer_id", "id"])
    op.create_foreign_key("fk_outcomes_supersedes_same_buyer", "outcome_events", "outcome_events",
                          ["workspace_id", "buyer_id", "supersedes_id"],
                          ["workspace_id", "buyer_id", "id"])
    op.create_index("uq_outcomes_one_successor", "outcome_events",
                    ["workspace_id", "supersedes_id"], unique=True,
                    postgresql_where=sa.text("supersedes_id IS NOT NULL"))
    op.create_index("ix_outcomes_project_page", "outcome_events",
                    ["workspace_id", "project_id", "created_at", "id"])
    op.execute("REVOKE UPDATE, DELETE ON outcome_events FROM buyeros_api, buyeros_worker")


def downgrade() -> None:
    if op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM outcome_events LIMIT 1)"
    )).scalar_one():
        raise RuntimeError("0030 downgrade blocked: retained manual outcome history")
    op.execute("GRANT UPDATE, DELETE ON outcome_events TO buyeros_api, buyeros_worker")
    op.drop_index("ix_outcomes_project_page", table_name="outcome_events")
    op.drop_index("uq_outcomes_one_successor", table_name="outcome_events")
    op.drop_constraint("fk_outcomes_supersedes_same_buyer", "outcome_events", type_="foreignkey")
    op.drop_constraint("uq_outcomes_buyer_id", "outcome_events", type_="unique")
    op.drop_constraint("fk_outcomes_project_buyer", "outcome_events", type_="foreignkey")
    for column in ("version", "correction_reason", "provenance_reference", "project_id"):
        op.drop_column("outcome_events", column)
