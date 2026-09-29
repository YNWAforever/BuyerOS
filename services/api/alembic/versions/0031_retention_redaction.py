"""Allow narrow, irreversible retention redaction of derived draft and approval payloads.

Revision ID: 0031_retention_redaction
Revises: 0030_manual_outcome_provenance
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0031_retention_redaction"
down_revision: str | None = "0030_manual_outcome_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_approval_material_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.invalidated_reason IS NOT NULL AND
             (NEW.invalidated_reason IS DISTINCT FROM OLD.invalidated_reason OR
              NEW.invalidated_at IS DISTINCT FROM OLD.invalidated_at)
          THEN RAISE EXCEPTION 'invalidated approval cannot reactivate'; END IF;
          IF OLD.invalidated_reason IS NULL AND NEW.invalidated_reason IS NOT NULL
             AND NEW.invalidated_at IS NULL
          THEN RAISE EXCEPTION 'approval invalidation requires timestamp'; END IF;
          IF OLD.context_snapshot IS NOT NULL AND NEW.context_snapshot IS NULL
             AND NEW.invalidated_reason IS NOT NULL
             AND (to_jsonb(NEW) - 'invalidated_reason' - 'invalidated_at' - 'updated_at' - 'context_snapshot') =
                 (to_jsonb(OLD) - 'invalidated_reason' - 'invalidated_at' - 'updated_at' - 'context_snapshot')
          THEN RETURN NEW; END IF;
          IF (to_jsonb(NEW) - 'invalidated_reason' - 'invalidated_at' - 'updated_at')
             IS DISTINCT FROM
             (to_jsonb(OLD) - 'invalidated_reason' - 'invalidated_at' - 'updated_at')
          THEN RAISE EXCEPTION 'approval material is immutable'; END IF;
          RETURN NEW;
        END $$
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_draft_revision_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'draft revision is immutable'; END $$
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_approval_material_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.invalidated_reason IS NOT NULL AND
             (NEW.invalidated_reason IS DISTINCT FROM OLD.invalidated_reason OR
              NEW.invalidated_at IS DISTINCT FROM OLD.invalidated_at)
          THEN RAISE EXCEPTION 'invalidated approval cannot reactivate'; END IF;
          IF OLD.invalidated_reason IS NULL AND NEW.invalidated_reason IS NOT NULL
             AND NEW.invalidated_at IS NULL
          THEN RAISE EXCEPTION 'approval invalidation requires timestamp'; END IF;
          IF (to_jsonb(NEW) - 'invalidated_reason' - 'invalidated_at' - 'updated_at')
             IS DISTINCT FROM
             (to_jsonb(OLD) - 'invalidated_reason' - 'invalidated_at' - 'updated_at')
          THEN RAISE EXCEPTION 'approval material is immutable'; END IF;
          RETURN NEW;
        END $$
    """)
