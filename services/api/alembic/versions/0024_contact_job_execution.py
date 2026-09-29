"""Persist contact job versions and provider intent/result ownership.

Revision ID: 0024_contact_job_execution
Revises: 0023_contact_quote_basis
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_contact_job_execution"
down_revision: str | None = "0023_contact_quote_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("enrichment_jobs", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint("ck_enrichment_jobs_version", "enrichment_jobs", "version > 0")
    op.add_column("provider_operations", sa.Column("job_id", UUID, nullable=True))
    op.add_column("provider_operations", sa.Column("buyer_id", UUID, nullable=True))
    op.add_column("provider_operations", sa.Column("provider_name", sa.String(64), nullable=True))
    op.add_column("provider_operations", sa.Column("account_reference", sa.String(128), nullable=True))
    op.add_column("provider_operations", sa.Column("observed_cost", sa.Numeric(20, 6), nullable=True))
    op.add_column("provider_operations", sa.Column("external_event_id", sa.String(200), nullable=True))
    op.add_column("provider_operations", sa.Column("result_contact_id", UUID, nullable=True))
    op.create_foreign_key("fk_provider_operations_job", "provider_operations", "enrichment_jobs",
                          ["workspace_id", "job_id"], ["workspace_id", "id"])
    op.create_foreign_key("fk_provider_operations_buyer", "provider_operations", "project_buyers",
                          ["workspace_id", "buyer_id"], ["workspace_id", "id"])
    op.create_unique_constraint("uq_provider_operations_job_buyer", "provider_operations",
                                ["workspace_id", "job_id", "buyer_id"])
    op.create_index("ix_provider_operations_provider_reference", "provider_operations",
                    ["provider_name", "account_reference", "provider_ref"], unique=True,
                    postgresql_where=sa.text("provider_ref IS NOT NULL AND provider_name IS NOT NULL AND account_reference IS NOT NULL"))
    op.create_check_constraint("ck_provider_operations_observed_cost", "provider_operations",
                               "observed_cost IS NULL OR observed_cost >= 0")


def downgrade() -> None:
    retained = op.get_bind().execute(sa.text(
        "SELECT EXISTS(SELECT 1 FROM provider_operations WHERE job_id IS NOT NULL OR provider_ref IS NOT NULL LIMIT 1)"
    )).scalar_one()
    if retained:
        raise RuntimeError("0024 downgrade blocked: retained provider intents or references")
    op.drop_constraint("ck_provider_operations_observed_cost", "provider_operations", type_="check")
    op.drop_index("ix_provider_operations_provider_reference", table_name="provider_operations")
    op.drop_constraint("uq_provider_operations_job_buyer", "provider_operations", type_="unique")
    op.drop_constraint("fk_provider_operations_buyer", "provider_operations", type_="foreignkey")
    op.drop_constraint("fk_provider_operations_job", "provider_operations", type_="foreignkey")
    for name in ("result_contact_id", "external_event_id", "observed_cost", "account_reference",
                 "provider_name", "buyer_id", "job_id"):
        op.drop_column("provider_operations", name)
    op.drop_constraint("ck_enrichment_jobs_version", "enrichment_jobs", type_="check")
    op.drop_column("enrichment_jobs", "version")
