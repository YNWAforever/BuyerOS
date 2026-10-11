"""Repair older scoped receipt tombstones' retained source and raw copies."""
from alembic import op
revision='0047_c61_legacy_source_privacy'
down_revision='0046_c61_derived_privacy'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_erase_search_derived(ws uuid, receipt uuid, policy text)
      RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,public SET lock_timeout='1s' AS $derived$
    DECLARE source_ids uuid[]; derived_evidence_ids text[]; project_ids uuid[]; item record; safe jsonb; canonical text; model_id uuid;
    BEGIN
      -- Owner-only helper. The public finite eraser has already performed the
      -- tenant/role/due CAS and source tombstone in this same transaction.
      SELECT array_agg(s.id ORDER BY s.id),array_agg(DISTINCT s.project_id)
        INTO source_ids,project_ids FROM public.source_documents s
        WHERE s.workspace_id=ws AND s.storage_mode IN ('search_result_metadata','research_page_excerpt')
          AND s.object_key IS NULL
          AND EXISTS(SELECT 1 FROM public.search_receipts r WHERE r.workspace_id=ws
            AND r.id=receipt AND r.redacted_at IS NOT NULL)
          AND EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws
            AND b.source_id=s.id AND b.service='search' AND b.receipt_id=receipt);
      IF source_ids IS NULL THEN RETURN; END IF;
      -- Earlier receipt tombstones may predate source/raw privacy. The parent
      -- receipt's irreversible redaction is proof that all its bound copies
      -- must now erase, even if an older source deadline was longer.
      UPDATE public.source_documents s SET excerpt=NULL,
        canonical_url='https://redacted.invalid/'||s.id::text,retention_until=LEAST(s.retention_until,now())
        WHERE s.workspace_id=ws AND s.id=ANY(source_ids)
          AND (s.excerpt IS NOT NULL OR s.canonical_url IS DISTINCT FROM 'https://redacted.invalid/'||s.id::text
            OR s.retention_until>now());
      UPDATE public.raw_candidates c SET source_url=s.canonical_url,normalized_url=s.canonical_url,
        raw_payload=jsonb_build_object('source_document_id',s.id::text,'content_kind','search_result_metadata','redacted',true)
        FROM public.source_documents s WHERE c.workspace_id=ws AND s.workspace_id=ws AND s.id=ANY(source_ids)
          AND c.raw_payload->>'source_document_id'=s.id::text AND c.raw_payload->>'content_kind'='search_result_metadata'
          AND (c.raw_payload IS DISTINCT FROM jsonb_build_object('source_document_id',s.id::text,'content_kind','search_result_metadata','redacted',true)
            OR c.source_url IS DISTINCT FROM s.canonical_url OR c.normalized_url IS DISTINCT FROM s.canonical_url);

      SELECT array_agg(e.id::text ORDER BY e.id) INTO derived_evidence_ids FROM public.evidence e
        WHERE e.workspace_id=ws AND e.source_document_id=ANY(source_ids);
      IF derived_evidence_ids IS NOT NULL THEN
        UPDATE public.fit_assessments f SET verdict='needs_review',rationale='Source expired',assessment_details='{}'::jsonb,updated_at=now()
          WHERE f.workspace_id=ws AND f.evidence_ids ?| derived_evidence_ids
            AND (f.verdict IS DISTINCT FROM 'needs_review' OR f.rationale IS DISTINCT FROM 'Source expired' OR f.assessment_details IS DISTINCT FROM '{}'::jsonb);
        FOR item IN SELECT d.id,d.content FROM public.draft_revisions d
          WHERE d.workspace_id=ws AND d.evidence_ids ?| derived_evidence_ids
            AND d.content->>'grounding_status' IS DISTINCT FROM 'source_expired'
          ORDER BY d.id FOR UPDATE
        LOOP
          -- Retain only existing opaque grounding references. Invalid legacy
          -- shapes fail the entire CAS; they never acquire a generic JSON edit.
          IF COALESCE(jsonb_typeof(item.content->'icp_version_id'),'null') NOT IN ('string','null')
            OR COALESCE(jsonb_typeof(item.content->'evidence_set_hash'),'null') NOT IN ('string','null')
            THEN RAISE EXCEPTION 'invalid retained draft grounding reference'; END IF;
          safe:=jsonb_build_object(
            'subject','Source expired','body','Source expired',
            'kind',CASE WHEN item.content->>'kind' IN ('initial','follow_up') THEN item.content->>'kind' ELSE 'initial' END,
            'language',CASE WHEN item.content->>'language' IN ('en','zh-HK') THEN item.content->>'language' ELSE 'en' END,
            'icp_version_id',item.content->'icp_version_id','evidence_set_hash',item.content->'evidence_set_hash',
            'value_proposition_fact_ids','[]'::jsonb,'policy_decision_ids','[]'::jsonb,
            'context_hash',repeat('0',64),'grounding_status','source_expired','claims','[]'::jsonb,'evidence_refs','[]'::jsonb);
          -- This closed shape contains strings/null/empty arrays only. Compact
          -- sorted UTF-8 equals the existing Python canonical content hash.
          SELECT '{'||string_agg(to_jsonb(j.key)::text||':'||j.value::text,',' ORDER BY j.key COLLATE "C")||'}'
            INTO canonical FROM jsonb_each(safe) j;
          UPDATE public.draft_revisions SET content=safe,content_hash=encode(sha256(convert_to(canonical,'UTF8')),'hex'),updated_at=now()
            WHERE workspace_id=ws AND id=item.id;
        END LOOP;
        UPDATE public.outreach_drafts d SET state='stale',review_context=NULL,review_context_hash=NULL,
          review_revision_id=NULL,state_version=d.state_version+1,updated_at=now()
          WHERE d.workspace_id=ws AND EXISTS(SELECT 1 FROM public.draft_revisions v
            WHERE v.workspace_id=ws AND v.draft_id=d.id AND v.evidence_ids ?| derived_evidence_ids)
            AND (d.state IS DISTINCT FROM 'stale' OR d.review_context IS NOT NULL
              OR d.review_context_hash IS NOT NULL OR d.review_revision_id IS NOT NULL);
        UPDATE public.evidence e SET excerpt='Source expired',translation=NULL,version=e.version+1,updated_at=now()
          WHERE e.workspace_id=ws AND e.source_document_id=ANY(source_ids)
            AND (e.excerpt IS DISTINCT FROM 'Source expired' OR e.translation IS NOT NULL);
      END IF;
      -- Match existing project-wide source-expiry approval/export invalidation;
      -- preserve immutable IDs, material hashes, prior invalidation and ledger.
      UPDATE public.approvals a SET invalidated_reason=COALESCE(a.invalidated_reason,'SOURCE_EXPIRED'),
        invalidated_at=COALESCE(a.invalidated_at,now()),context_snapshot=NULL,updated_at=now()
        WHERE a.workspace_id=ws AND EXISTS(SELECT 1 FROM public.outreach_drafts d
          WHERE d.workspace_id=ws AND d.id=a.draft_id AND d.project_id=ANY(project_ids))
          AND (a.invalidated_reason IS NULL OR a.context_snapshot IS NOT NULL);
      UPDATE public.export_jobs e SET state=CASE WHEN e.state='ready' THEN 'revoked' ELSE e.state END,
        expires_at=LEAST(e.expires_at,now()),selection_manifest=jsonb_build_object('redacted',true,'reason','SOURCE_EXPIRED'),
        version=e.version+1,updated_at=now()
        WHERE e.workspace_id=ws AND e.project_id=ANY(project_ids)
          AND e.selection_manifest IS DISTINCT FROM jsonb_build_object('redacted',true,'reason','SOURCE_EXPIRED');
      FOR model_id IN SELECT m.id FROM public.model_receipts m
        WHERE m.workspace_id=ws AND m.redacted_at IS NULL AND (
          EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws
            AND b.service='model' AND b.receipt_id=m.id AND b.source_id=ANY(source_ids))
          OR EXISTS(SELECT 1 FROM jsonb_array_elements(COALESCE(m.request#>'{basis,evidence}','[]'::jsonb)) e
            WHERE e->>'source_id'=ANY(source_ids::text[]))) ORDER BY m.id FOR UPDATE
      LOOP
        PERFORM public.buyeros_erase_provider_receipt(ws,'model',model_id,policy);
      END LOOP;
    END $derived$;
    REVOKE ALL ON FUNCTION public.buyeros_erase_search_derived(uuid,uuid,text) FROM PUBLIC,buyeros_api,buyeros_worker;
        """)
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0047_c61_legacy_source_privacy' FROM public.alembic_version),false) $$")

def downgrade():
    # Keep completed one-way repairs and the owner-only helper for compatible
    # expiry/readers. No destructive rollback, data resurrection or new grants.
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT false $$")
