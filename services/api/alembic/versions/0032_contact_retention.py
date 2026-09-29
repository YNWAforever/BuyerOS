"""Add explicit contact expiry and one-way addressed-draft redaction.

Revision ID: 0032_contact_retention
Revises: 0031_retention_redaction
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_contact_retention"
down_revision: str | None = "0031_retention_redaction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contact_points", sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_contact_points_retention", "contact_points", ["workspace_id", "retention_expires_at"],
                    postgresql_where=sa.text("retention_expires_at IS NOT NULL"))
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_draft_revision_update() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE safe_content jsonb; label text; marker text;
        BEGIN
          marker := NEW.content->>'grounding_status';
          label := CASE marker WHEN 'source_expired' THEN 'Source expired'
                               WHEN 'contact_expired' THEN 'Contact expired'
                               ELSE NULL END;
          safe_content := jsonb_build_object(
            'subject', label, 'body', label,
            'kind', CASE WHEN OLD.content->>'kind' IN ('initial','follow_up')
                         THEN OLD.content->>'kind' ELSE 'initial' END,
            'language', CASE WHEN OLD.content->>'language' IN ('en','zh-HK')
                             THEN OLD.content->>'language' ELSE 'en' END,
            'icp_version_id', OLD.content->'icp_version_id',
            'evidence_set_hash', OLD.content->'evidence_set_hash',
            'value_proposition_fact_ids', '[]'::jsonb,
            'policy_decision_ids', '[]'::jsonb,
            'context_hash', repeat('0', 64),
            'grounding_status', marker,
            'claims', '[]'::jsonb, 'evidence_refs', '[]'::jsonb
          );
          IF OLD.content->>'grounding_status' IS DISTINCT FROM 'source_expired'
             AND OLD.content->>'grounding_status' IS DISTINCT FROM 'contact_expired'
             AND marker IN ('source_expired','contact_expired')
             AND NEW.content = safe_content
             AND NEW.content_hash ~ '^[0-9a-f]{64}$'
             AND (to_jsonb(NEW) - 'content' - 'content_hash' - 'updated_at') =
                 (to_jsonb(OLD) - 'content' - 'content_hash' - 'updated_at')
             AND (
                 (marker = 'source_expired' AND EXISTS (
                    SELECT 1 FROM evidence e JOIN source_documents s
                      ON s.workspace_id=e.workspace_id AND s.id=e.source_document_id
                    WHERE e.workspace_id=OLD.workspace_id
                      AND e.id::text IN (SELECT jsonb_array_elements_text(OLD.evidence_ids))
                      AND s.excerpt IS NULL
                      AND s.canonical_url LIKE 'https://redacted.invalid/%'
                 ))
                 OR (marker = 'contact_expired' AND EXISTS (
                    SELECT 1 FROM contact_points c
                    WHERE c.workspace_id=OLD.workspace_id
                      AND c.id::text=OLD.content->>'recipient_contact_id'
                      AND c.quarantined AND c.validity='unavailable'
                      AND c.normalized_value LIKE 'expired+%@redacted.invalid'
                 ))
             )
          THEN RETURN NEW; END IF;
          RAISE EXCEPTION 'draft revision is immutable';
        END $$
    """)


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS(SELECT 1 FROM contact_points "
                                     "WHERE retention_expires_at IS NOT NULL)")).scalar_one():
        raise RuntimeError("0032 downgrade blocked: contact retention dates are retained")
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_draft_revision_update() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE safe_content jsonb;
        BEGIN
          safe_content := jsonb_build_object(
            'subject', 'Source expired', 'body', 'Source expired',
            'kind', CASE WHEN OLD.content->>'kind' IN ('initial','follow_up')
                         THEN OLD.content->>'kind' ELSE 'initial' END,
            'language', CASE WHEN OLD.content->>'language' IN ('en','zh-HK')
                             THEN OLD.content->>'language' ELSE 'en' END,
            'icp_version_id', OLD.content->'icp_version_id',
            'evidence_set_hash', OLD.content->'evidence_set_hash',
            'value_proposition_fact_ids', '[]'::jsonb,
            'policy_decision_ids', '[]'::jsonb,
            'context_hash', repeat('0', 64),
            'grounding_status', 'source_expired',
            'claims', '[]'::jsonb, 'evidence_refs', '[]'::jsonb
          );
          IF OLD.content->>'grounding_status' IS DISTINCT FROM 'source_expired'
             AND NEW.content = safe_content
             AND NEW.content_hash ~ '^[0-9a-f]{64}$'
             AND (to_jsonb(NEW) - 'content' - 'content_hash' - 'updated_at') =
                 (to_jsonb(OLD) - 'content' - 'content_hash' - 'updated_at')
             AND EXISTS (
                SELECT 1 FROM evidence e JOIN source_documents s
                  ON s.workspace_id=e.workspace_id AND s.id=e.source_document_id
                WHERE e.workspace_id=OLD.workspace_id
                  AND e.id::text IN (SELECT jsonb_array_elements_text(OLD.evidence_ids))
                  AND s.excerpt IS NULL
                  AND s.canonical_url LIKE 'https://redacted.invalid/%'
             )
          THEN RETURN NEW; END IF;
          RAISE EXCEPTION 'draft revision is immutable';
        END $$
    """)
    op.drop_index("ix_contact_points_retention", table_name="contact_points")
    op.drop_column("contact_points", "retention_expires_at")
