"""Constrain project-bound links across a shared workspace.

Revision ID: 0013_project_link_constraints
Revises: 0012_offer_basis_revision

A preflight aborts on legacy violations with counts and sample opaque IDs. It
never deletes or rewrites conflicting relationships. Newly added project_id
columns are derived only from their existing owner row.
"""

from collections.abc import Sequence
import logging

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0013_project_link_constraints"
down_revision: str | None = "0012_offer_basis_revision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger(__name__)

_VIOLATIONS = {
    "active_icp": """SELECT p.id FROM projects p LEFT JOIN icp_versions i
        ON i.workspace_id=p.workspace_id AND i.id=p.active_icp_version_id
        WHERE p.active_icp_version_id IS NOT NULL
        AND (i.id IS NULL OR i.project_id<>p.id)""",
    "icp_parent": """SELECT child.id FROM icp_versions child
        LEFT JOIN icp_versions parent ON parent.workspace_id=child.workspace_id
          AND parent.id=child.parent_id
        WHERE child.parent_id IS NOT NULL
        AND (parent.id IS NULL OR parent.project_id<>child.project_id)""",
    "evidence_source": """SELECT e.id FROM evidence e
        LEFT JOIN source_documents d ON d.workspace_id=e.workspace_id AND d.id=e.source_document_id
        WHERE e.source_document_id IS NOT NULL AND d.id IS NULL""",
    "list_buyer": """SELECT lm.id FROM list_memberships lm
        JOIN buyer_lists bl ON bl.workspace_id=lm.workspace_id AND bl.id=lm.list_id
        LEFT JOIN project_buyers pb ON pb.workspace_id=lm.workspace_id AND pb.id=lm.buyer_id
        WHERE pb.id IS NULL OR pb.project_id<>bl.project_id""",
    "fit_buyer_icp": """SELECT fa.id FROM fit_assessments fa
        JOIN project_buyers pb ON pb.workspace_id=fa.workspace_id AND pb.id=fa.project_buyer_id
        LEFT JOIN icp_versions i ON i.workspace_id=fa.workspace_id AND i.id=fa.icp_version_id
        WHERE i.id IS NULL OR i.project_id<>pb.project_id""",
    "run_icp": """SELECT r.id FROM search_runs r
        LEFT JOIN icp_versions i ON i.workspace_id=r.workspace_id AND i.id=r.icp_version_id
        WHERE i.id IS NULL OR i.project_id<>r.project_id""",
    "snapshot_project": """SELECT s.id FROM buyer_snapshots s
        LEFT JOIN projects p ON p.workspace_id=s.workspace_id AND p.id=s.project_id
        WHERE p.id IS NULL""",
    "snapshot_buyer": """SELECT si.id FROM buyer_snapshot_items si
        JOIN buyer_snapshots s ON s.workspace_id=si.workspace_id AND s.id=si.snapshot_id
        LEFT JOIN project_buyers pb ON pb.workspace_id=si.workspace_id AND pb.id=si.buyer_id
        WHERE pb.id IS NULL OR pb.project_id<>s.project_id""",
    "review_fit": """SELECT hr.id FROM human_reviews hr
        LEFT JOIN fit_assessments fa ON fa.workspace_id=hr.workspace_id AND fa.id=hr.fit_assessment_id
        WHERE hr.fit_assessment_id IS NOT NULL
        AND (fa.id IS NULL OR fa.project_buyer_id<>hr.project_buyer_id)""",
    "fit_evidence_shape": """SELECT fa.id FROM fit_assessments fa
        WHERE jsonb_typeof(fa.evidence_ids) IS DISTINCT FROM 'array'""",
    "fit_evidence_scope": """SELECT DISTINCT fa.id FROM fit_assessments fa
        JOIN project_buyers pb ON pb.workspace_id=fa.workspace_id AND pb.id=fa.project_buyer_id
        CROSS JOIN LATERAL jsonb_array_elements_text(
          CASE WHEN jsonb_typeof(fa.evidence_ids)='array' THEN fa.evidence_ids ELSE '[]'::jsonb END
        ) AS ref(value)
        LEFT JOIN evidence e ON e.workspace_id=fa.workspace_id AND e.id::text=ref.value
          AND e.project_id=pb.project_id AND e.company_id=pb.company_id
        WHERE e.id IS NULL""",
}


def _preflight() -> None:
    bind = op.get_bind()
    violations = []
    for name, query in _VIOLATIONS.items():
        count = bind.execute(sa.text(f"SELECT count(*) FROM ({query}) AS violations")).scalar_one()
        log.info("project link preflight %s: %d violating rows", name, count)
        if count:
            examples = bind.execute(sa.text(f"SELECT id FROM ({query}) AS violations LIMIT 5")).scalars().all()
            violations.append(f"{name}={count} sample_ids={[str(value) for value in examples]}")
    if violations:
        raise RuntimeError("project link remediation required before migration: " + "; ".join(violations))


def upgrade() -> None:
    _preflight()
    uuid_type = UUID(as_uuid=True)
    op.create_unique_constraint("uq_icp_versions_project_id", "icp_versions", ["workspace_id", "project_id", "id"])
    op.create_unique_constraint("uq_project_buyers_project_id", "project_buyers", ["workspace_id", "project_id", "id"])
    op.create_unique_constraint("uq_buyer_lists_project_id", "buyer_lists", ["workspace_id", "project_id", "id"])
    op.create_unique_constraint("uq_buyer_snapshots_project_id", "buyer_snapshots", ["workspace_id", "project_id", "id"])
    op.create_unique_constraint("uq_fit_assessments_buyer_id", "fit_assessments", ["workspace_id", "project_buyer_id", "id"])

    for table in ("list_memberships", "fit_assessments", "buyer_snapshot_items"):
        op.add_column(table, sa.Column("project_id", uuid_type, nullable=True))
    op.execute("""UPDATE list_memberships lm SET project_id=bl.project_id
        FROM buyer_lists bl WHERE bl.workspace_id=lm.workspace_id AND bl.id=lm.list_id""")
    op.execute("""UPDATE fit_assessments fa SET project_id=pb.project_id
        FROM project_buyers pb WHERE pb.workspace_id=fa.workspace_id AND pb.id=fa.project_buyer_id""")
    op.execute("""UPDATE buyer_snapshot_items si SET project_id=s.project_id
        FROM buyer_snapshots s WHERE s.workspace_id=si.workspace_id AND s.id=si.snapshot_id""")
    for table in ("list_memberships", "fit_assessments", "buyer_snapshot_items"):
        op.alter_column(table, "project_id", nullable=False)

    op.create_foreign_key("fk_icp_versions_parent_same_project", "icp_versions", "icp_versions",
        ["workspace_id", "project_id", "parent_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_projects_active_icp_same_project", "projects", "icp_versions",
        ["workspace_id", "id", "active_icp_version_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_list_memberships_list_project", "list_memberships", "buyer_lists",
        ["workspace_id", "project_id", "list_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_list_memberships_buyer_project", "list_memberships", "project_buyers",
        ["workspace_id", "project_id", "buyer_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_fit_assessments_buyer_project", "fit_assessments", "project_buyers",
        ["workspace_id", "project_id", "project_buyer_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_fit_assessments_icp_project", "fit_assessments", "icp_versions",
        ["workspace_id", "project_id", "icp_version_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_search_runs_icp_project", "search_runs", "icp_versions",
        ["workspace_id", "project_id", "icp_version_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_buyer_snapshots_project", "buyer_snapshots", "projects",
        ["workspace_id", "project_id"], ["workspace_id", "id"])
    op.create_foreign_key("fk_buyer_snapshot_items_snapshot_project", "buyer_snapshot_items", "buyer_snapshots",
        ["workspace_id", "project_id", "snapshot_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_buyer_snapshot_items_buyer_project", "buyer_snapshot_items", "project_buyers",
        ["workspace_id", "project_id", "buyer_id"], ["workspace_id", "project_id", "id"])
    op.create_foreign_key("fk_human_reviews_fit_buyer", "human_reviews", "fit_assessments",
        ["workspace_id", "project_buyer_id", "fit_assessment_id"],
        ["workspace_id", "project_buyer_id", "id"])
    op.create_foreign_key("fk_evidence_source_document", "evidence", "source_documents",
        ["workspace_id", "source_document_id"], ["workspace_id", "id"])

    op.execute("""CREATE FUNCTION check_fit_evidence_project() RETURNS trigger AS $$
      BEGIN
        IF jsonb_typeof(NEW.evidence_ids) IS DISTINCT FROM 'array' THEN
          RAISE EXCEPTION 'fit evidence_ids must be an array' USING ERRCODE='23503';
        END IF;
        IF EXISTS (
          SELECT 1 FROM jsonb_array_elements_text(NEW.evidence_ids) AS ref(value)
          JOIN project_buyers pb ON pb.workspace_id=NEW.workspace_id AND pb.id=NEW.project_buyer_id
          LEFT JOIN evidence e ON e.workspace_id=NEW.workspace_id AND e.id::text=ref.value
            AND e.project_id=NEW.project_id AND e.company_id=pb.company_id
          WHERE e.id IS NULL
        ) THEN
          RAISE EXCEPTION 'fit evidence must belong to the buyer project and company' USING ERRCODE='23503';
        END IF;
        RETURN NEW;
      END;
    $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER trg_fit_evidence_project BEFORE INSERT OR UPDATE
      ON fit_assessments FOR EACH ROW EXECUTE FUNCTION check_fit_evidence_project()""")


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_fit_evidence_project ON fit_assessments")
    op.execute("DROP FUNCTION check_fit_evidence_project()")
    for table, name in (
        ("evidence", "fk_evidence_source_document"),
        ("human_reviews", "fk_human_reviews_fit_buyer"),
        ("buyer_snapshot_items", "fk_buyer_snapshot_items_buyer_project"),
        ("buyer_snapshot_items", "fk_buyer_snapshot_items_snapshot_project"),
        ("buyer_snapshots", "fk_buyer_snapshots_project"),
        ("search_runs", "fk_search_runs_icp_project"),
        ("fit_assessments", "fk_fit_assessments_icp_project"),
        ("fit_assessments", "fk_fit_assessments_buyer_project"),
        ("list_memberships", "fk_list_memberships_buyer_project"),
        ("list_memberships", "fk_list_memberships_list_project"),
        ("projects", "fk_projects_active_icp_same_project"),
        ("icp_versions", "fk_icp_versions_parent_same_project"),
    ):
        op.drop_constraint(name, table, type_="foreignkey")
    for table in ("buyer_snapshot_items", "fit_assessments", "list_memberships"):
        op.drop_column(table, "project_id")
    for table, name in (
        ("fit_assessments", "uq_fit_assessments_buyer_id"),
        ("buyer_snapshots", "uq_buyer_snapshots_project_id"),
        ("buyer_lists", "uq_buyer_lists_project_id"),
        ("project_buyers", "uq_project_buyers_project_id"),
        ("icp_versions", "uq_icp_versions_project_id"),
    ):
        op.drop_constraint(name, table, type_="unique")
