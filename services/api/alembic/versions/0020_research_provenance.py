"""Bind canonical candidates and evidence to one tenant/run/provider context.

Revision ID: 0020_research_provenance
Revises: 0019_offer_documents
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_research_provenance"
down_revision: str | None = "0019_offer_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_search_runs_workspace_project_id", "search_runs",
        ["workspace_id", "project_id", "id"],
    )
    op.create_index(
        "uq_companies_workspace_registry", "companies", ["workspace_id", "registry_id"],
        unique=True, postgresql_where=sa.text("registry_id IS NOT NULL"),
    )

    for name, column in (
        ("project_id", sa.Column("project_id", UUID, nullable=True)),
        ("run_id", sa.Column("run_id", UUID, nullable=True)),
        ("permission_purpose", sa.Column("permission_purpose", sa.String(32), nullable=True)),
    ):
        op.add_column("source_documents", column)
    op.create_foreign_key(
        "fk_source_documents_project", "source_documents", "projects",
        ["workspace_id", "project_id"], ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_source_documents_project_run", "source_documents", "search_runs",
        ["workspace_id", "project_id", "run_id"],
        ["workspace_id", "project_id", "id"],
    )

    op.drop_constraint("uq_raw_candidates_run_url", "raw_candidates", type_="unique")
    op.add_column("raw_candidates", sa.Column("provider_operation_id", UUID, nullable=True))
    op.add_column("raw_candidates", sa.Column("candidate_fingerprint", sa.String(64), nullable=True))
    op.add_column("raw_candidates", sa.Column("raw_payload", postgresql.JSONB(), nullable=True))
    op.create_foreign_key(
        "fk_raw_candidates_provider_operation", "raw_candidates", "provider_operations",
        ["workspace_id", "provider_operation_id"], ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_raw_candidates_canonical_company", "raw_candidates", "companies",
        ["workspace_id", "canonical_company_id"], ["workspace_id", "id"],
    )
    op.create_index(
        "uq_raw_candidates_intent_fingerprint", "raw_candidates",
        ["workspace_id", "run_id", "provider_operation_id", "candidate_fingerprint"],
        unique=True, postgresql_where=sa.text(
            "provider_operation_id IS NOT NULL AND candidate_fingerprint IS NOT NULL"
        ),
    )

    op.add_column("company_aliases", sa.Column("raw_candidate_id", UUID, nullable=True))
    op.add_column("company_aliases", sa.Column("decision_state", sa.String(24), nullable=True))
    op.add_column("company_aliases", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_company_aliases_raw_candidate", "company_aliases", "raw_candidates",
        ["workspace_id", "raw_candidate_id"], ["workspace_id", "id"],
    )
    op.create_index(
        "uq_company_aliases_active_raw", "company_aliases",
        ["workspace_id", "raw_candidate_id"], unique=True,
        postgresql_where=sa.text("raw_candidate_id IS NOT NULL AND superseded_at IS NULL"),
    )

    for column in (
        sa.Column("run_id", UUID, nullable=True),
        sa.Column("raw_candidate_id", UUID, nullable=True),
        sa.Column("provider_operation_id", UUID, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ):
        op.add_column("evidence", column)
    op.create_foreign_key(
        "fk_evidence_project_run", "evidence", "search_runs",
        ["workspace_id", "project_id", "run_id"],
        ["workspace_id", "project_id", "id"],
    )
    op.create_foreign_key(
        "fk_evidence_raw_candidate", "evidence", "raw_candidates",
        ["workspace_id", "raw_candidate_id"], ["workspace_id", "id"],
    )
    op.create_foreign_key(
        "fk_evidence_provider_operation", "evidence", "provider_operations",
        ["workspace_id", "provider_operation_id"], ["workspace_id", "id"],
    )
    op.add_column("fit_assessments", sa.Column("run_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_fit_assessments_project_run", "fit_assessments", "search_runs",
        ["workspace_id", "project_id", "run_id"],
        ["workspace_id", "project_id", "id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    checks = (
        ("raw_candidates", "provider_operation_id IS NOT NULL"),
        ("source_documents", "project_id IS NOT NULL OR run_id IS NOT NULL"),
        ("company_aliases", "raw_candidate_id IS NOT NULL"),
        ("evidence", "run_id IS NOT NULL"),
        ("fit_assessments", "run_id IS NOT NULL"),
    )
    for table, condition in checks:
        if bind.execute(sa.text(f"SELECT count(*) FROM {table} WHERE {condition}")).scalar_one():
            raise RuntimeError(f"0020 downgrade blocked: retained {table} provenance")
    op.drop_constraint("fk_fit_assessments_project_run", "fit_assessments", type_="foreignkey")
    op.drop_column("fit_assessments", "run_id")
    for name in (
        "fk_evidence_provider_operation", "fk_evidence_raw_candidate",
        "fk_evidence_project_run",
    ):
        op.drop_constraint(name, "evidence", type_="foreignkey")
    for column in (
        "version", "observed_at", "content_hash", "provider_operation_id",
        "raw_candidate_id", "run_id",
    ):
        op.drop_column("evidence", column)
    op.drop_index("uq_company_aliases_active_raw", table_name="company_aliases")
    op.drop_constraint("fk_company_aliases_raw_candidate", "company_aliases", type_="foreignkey")
    for column in ("superseded_at", "decision_state", "raw_candidate_id"):
        op.drop_column("company_aliases", column)
    op.drop_index("uq_raw_candidates_intent_fingerprint", table_name="raw_candidates")
    op.drop_constraint("fk_raw_candidates_canonical_company", "raw_candidates", type_="foreignkey")
    op.drop_constraint("fk_raw_candidates_provider_operation", "raw_candidates", type_="foreignkey")
    for column in ("raw_payload", "candidate_fingerprint", "provider_operation_id"):
        op.drop_column("raw_candidates", column)
    op.create_unique_constraint(
        "uq_raw_candidates_run_url", "raw_candidates",
        ["workspace_id", "run_id", "normalized_url"],
    )
    op.drop_constraint("fk_source_documents_project_run", "source_documents", type_="foreignkey")
    op.drop_constraint("fk_source_documents_project", "source_documents", type_="foreignkey")
    for column in ("permission_purpose", "run_id", "project_id"):
        op.drop_column("source_documents", column)
    op.drop_index("uq_companies_workspace_registry", table_name="companies")
    op.drop_constraint("uq_search_runs_workspace_project_id", "search_runs", type_="unique")
