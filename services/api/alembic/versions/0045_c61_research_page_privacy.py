"""Retain and atomically erase permitted research page excerpt copies; no grants."""
from alembic import op
revision='0045_c61_research_page_privacy'
down_revision='0044_c61_search_intake'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_erase_provider_receipt(ws uuid, service_name text, receipt uuid, policy text)
      RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public SET lock_timeout='1s' AS $erase$
    DECLARE affected integer;
    BEGIN
      IF ws IS NULL OR receipt IS NULL OR policy IS NULL OR service_name IS NULL
        OR ws IS DISTINCT FROM current_setting('app.workspace_id',true)::uuid
        OR service_name NOT IN ('search','model','contact') OR policy !~ '^[A-Za-z0-9._-]{1,64}$'
        OR NOT (pg_has_role(session_user,'buyeros_api','MEMBER') OR pg_has_role(session_user,'buyeros_worker','MEMBER'))
        THEN RAISE EXCEPTION USING ERRCODE='42501',MESSAGE='scoped finite receipt erase permission required'; END IF;
      IF service_name='search' THEN
        UPDATE public.search_receipts r SET request=jsonb_build_object('redacted',true),response=NULL,redacted_at=now(),redaction_policy=policy,updated_at=now()
          WHERE r.workspace_id=ws AND r.id=receipt AND r.redacted_at IS NULL
          AND (r.retention_until<=now() OR public.buyeros_receipt_dependency_expired(ws,service_name,receipt,r.request));
      ELSIF service_name='model' THEN
        UPDATE public.model_receipts r SET request=jsonb_build_object('redacted',true),response=NULL,redacted_at=now(),redaction_policy=policy,updated_at=now()
          WHERE r.workspace_id=ws AND r.id=receipt AND r.redacted_at IS NULL
          AND (r.retention_until<=now() OR public.buyeros_receipt_dependency_expired(ws,service_name,receipt,r.request));
      ELSIF service_name='contact' THEN
        UPDATE public.contact_receipts r SET request=jsonb_build_object('redacted',true),response_ciphertext=NULL,redacted_at=now(),redaction_policy=policy,updated_at=now()
          WHERE r.workspace_id=ws AND r.id=receipt AND r.redacted_at IS NULL
          AND (r.retention_until<=now() OR public.buyeros_receipt_dependency_expired(ws,service_name,receipt,r.request));
      END IF;
      GET DIAGNOSTICS affected=ROW_COUNT;
      IF affected=1 THEN
        IF service_name='search' THEN
          UPDATE public.source_documents s SET excerpt=NULL,
            canonical_url='https://redacted.invalid/'||s.id::text,
            retention_until=LEAST(s.retention_until,now())
            WHERE s.workspace_id=ws AND s.storage_mode IN ('search_result_metadata','research_page_excerpt') AND s.object_key IS NULL
              AND EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws
                AND b.source_id=s.id AND b.service='search' AND b.receipt_id=receipt);
          UPDATE public.raw_candidates c SET source_url=s.canonical_url,normalized_url=s.canonical_url,
            raw_payload=jsonb_build_object('source_document_id',s.id::text,'content_kind','search_result_metadata','redacted',true)
            FROM public.source_documents s WHERE c.workspace_id=ws AND s.workspace_id=ws
              AND c.raw_payload->>'source_document_id'=s.id::text
              AND c.raw_payload->>'content_kind'='search_result_metadata'
              AND s.storage_mode IN ('search_result_metadata','research_page_excerpt') AND s.object_key IS NULL
              AND EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws
                AND b.source_id=s.id AND b.service='search' AND b.receipt_id=receipt);
        END IF;
        INSERT INTO public.audit_events(id,workspace_id,action,subject_type,subject_id,detail_digest,reason)
          VALUES(gen_random_uuid(),ws,'provider_receipt.expired',service_name||'_receipt',receipt::text,
            'sha256:'||encode(sha256(convert_to(policy,'UTF8')),'hex'),'retention_expired');
      END IF;
      RETURN affected=1;
    END $erase$;
    REVOKE ALL ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) TO buyeros_api,buyeros_worker;
    """)

    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0045_c61_research_page_privacy' FROM public.alembic_version),false) $$")

def downgrade():
    # Keep the eraser, narrow runtime/receipt lock, sources/bindings/checkpoints
    # and every hash/UUID/FK/hold. Compatible readers remain required.
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT false $$")
