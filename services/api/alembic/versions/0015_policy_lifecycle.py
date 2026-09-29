"""Give policy and suppression the full purpose/subject lifecycle contract.

Revision ID: 0015_policy_lifecycle
Revises: 0014_buyer_management
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_policy_lifecycle"
down_revision: str | None = "0014_buyer_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def _counts(bind) -> tuple[int, int]:
    return (
        bind.execute(sa.text("SELECT count(*) FROM policy_decisions")).scalar_one(),
        bind.execute(sa.text("SELECT count(*) FROM suppressions")).scalar_one(),
    )


def upgrade() -> None:
    policies, suppressions = _counts(op.get_bind())
    if policies or suppressions:
        raise RuntimeError(f"0015 upgrade blocked: {policies} legacy policy decisions and {suppressions} legacy suppressions need reviewed mapping")
    op.alter_column("policy_decisions", "version", new_column_name="policy_version", existing_type=sa.String(64), existing_nullable=False)
    op.alter_column("policy_decisions", "basis", new_column_name="basis_reference", existing_type=sa.String(400), existing_nullable=True)
    op.alter_column("policy_decisions", "basis_reference", type_=sa.String(1000), existing_type=sa.String(400), nullable=False)
    op.alter_column("policy_decisions", "review_expires_at", new_column_name="expires_at", existing_type=sa.DateTime(timezone=True), existing_nullable=True)
    op.alter_column("policy_decisions", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    for column in (
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("controller_scope_id", UUID, nullable=False),
        sa.Column("provenance", sa.String(1000), nullable=False),
        sa.Column("countries", postgresql.ARRAY(sa.String(2)), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("decision_author_id", UUID, nullable=False),
    ): op.add_column("policy_decisions", column)
    op.create_check_constraint("ck_policy_decisions_version_positive", "policy_decisions", "version > 0")
    op.create_check_constraint("ck_policy_decisions_retention_days", "policy_decisions", "retention_days BETWEEN 1 AND 3650")
    op.create_check_constraint("ck_policy_decisions_status", "policy_decisions", "status IN ('requires_review','permitted','blocked')")
    op.create_index("ix_policy_decisions_subject_purpose", "policy_decisions", ["workspace_id", "controller_scope_id", "subject_type", "subject_id", "purpose", "created_at"])
    op.alter_column("suppressions", "reason", type_=sa.String(2000), existing_type=sa.String(400), existing_nullable=False)
    op.alter_column("suppressions", "removed_reason", type_=sa.String(2000), existing_type=sa.String(400), existing_nullable=True)
    for column in (
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", UUID, nullable=True),
        sa.Column("normalized_domain", sa.String(255), nullable=True),
        sa.Column("controller_scope_id", UUID, nullable=False),
        sa.Column("purposes", postgresql.ARRAY(sa.String(32)), nullable=False),
        sa.Column("source_reference", sa.String(1000), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_id", UUID, nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    ): op.add_column("suppressions", column)
    op.create_check_constraint("ck_suppressions_version_positive", "suppressions", "version > 0")
    op.create_check_constraint("ck_suppressions_subject", "suppressions", "(subject_type = 'domain' AND subject_id IS NULL AND normalized_domain IS NOT NULL) OR (subject_type IN ('company','contact_point') AND subject_id IS NOT NULL AND normalized_domain IS NULL)")
    op.create_index("ix_suppressions_subject_active", "suppressions", ["workspace_id", "controller_scope_id", "subject_type", "subject_id", "active"])
    op.create_index("ix_suppressions_domain_active", "suppressions", ["workspace_id", "controller_scope_id", "normalized_domain", "active"])


def downgrade() -> None:
    policies, suppressions = _counts(op.get_bind())
    if policies or suppressions:
        raise RuntimeError(f"0015 downgrade blocked: {policies} policy decisions and {suppressions} suppressions would lose purpose/subject history")
    op.drop_index("ix_suppressions_domain_active", table_name="suppressions")
    op.drop_index("ix_suppressions_subject_active", table_name="suppressions")
    op.drop_constraint("ck_suppressions_subject", "suppressions", type_="check")
    op.drop_constraint("ck_suppressions_version_positive", "suppressions", type_="check")
    for name in ("version", "removed_at", "actor_id", "expires_at", "source_reference", "purposes", "controller_scope_id", "normalized_domain", "subject_id", "subject_type"):
        op.drop_column("suppressions", name)
    op.alter_column("suppressions", "reason", type_=sa.String(400), existing_type=sa.String(2000), existing_nullable=False)
    op.alter_column("suppressions", "removed_reason", type_=sa.String(400), existing_type=sa.String(2000), existing_nullable=True)
    op.drop_index("ix_policy_decisions_subject_purpose", table_name="policy_decisions")
    for name in ("ck_policy_decisions_status", "ck_policy_decisions_retention_days", "ck_policy_decisions_version_positive"):
        op.drop_constraint(name, "policy_decisions", type_="check")
    for name in ("decision_author_id", "retention_days", "countries", "provenance", "controller_scope_id", "subject_id", "subject_type", "version"):
        op.drop_column("policy_decisions", name)
    op.alter_column("policy_decisions", "expires_at", new_column_name="review_expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("policy_decisions", "basis_reference", type_=sa.String(400), existing_type=sa.String(1000), nullable=True)
    op.alter_column("policy_decisions", "basis_reference", new_column_name="basis", existing_type=sa.String(400), existing_nullable=True)
    op.alter_column("policy_decisions", "policy_version", new_column_name="version", existing_type=sa.String(64), existing_nullable=False)
