"""Atomic search metadata read lock and retained-copy erasure; no table grants."""
from alembic import op
revision='0044_c61_search_intake'
down_revision='0043_c61_receipt_retention'
branch_labels=None
depends_on=None

def upgrade():
    # Keep the original finite tenant/session-role erase gate, adding only the
    # code-owned metadata copies bound to the erased search receipt.
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
            WHERE s.workspace_id=ws AND s.storage_mode='search_result_metadata' AND s.object_key IS NULL
              AND EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws
                AND b.source_id=s.id AND b.service='search' AND b.receipt_id=receipt);
          UPDATE public.raw_candidates c SET source_url=s.canonical_url,normalized_url=s.canonical_url,
            raw_payload=jsonb_build_object('source_document_id',s.id::text,'content_kind','search_result_metadata','redacted',true)
            FROM public.source_documents s WHERE c.workspace_id=ws AND s.workspace_id=ws
              AND c.raw_payload->>'source_document_id'=s.id::text
              AND c.raw_payload->>'content_kind'='search_result_metadata'
              AND s.storage_mode='search_result_metadata' AND s.object_key IS NULL
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
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_lock_search_receipt(ws uuid,receipt uuid)
      RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public SET lock_timeout='1s' AS $read_lock$
    DECLARE receipt_backend text; receipt_epoch bigint;
    BEGIN
      IF ws IS NULL OR receipt IS NULL OR ws IS DISTINCT FROM current_setting('app.workspace_id',true)::uuid
        OR NOT pg_has_role(session_user,'buyeros_api','MEMBER') THEN RETURN false; END IF;
      SELECT r.runtime_backend,r.runtime_epoch INTO receipt_backend,receipt_epoch
        FROM public.search_receipts r WHERE r.workspace_id=ws AND r.id=receipt;
      IF NOT FOUND THEN RETURN false; END IF;
      -- Runtime lock precedes the receipt lock, matching native executor CAS.
      -- No API role receives UPDATE/table-owner/BYPASSRLS privileges.
      PERFORM singleton FROM public.worker_runtime_control c WHERE c.singleton=1
        AND c.backend=receipt_backend AND c.epoch=receipt_epoch FOR SHARE;
      IF NOT FOUND THEN RETURN false; END IF;
      PERFORM id FROM public.search_receipts r WHERE r.workspace_id=ws AND r.id=receipt
        AND public.buyeros_search_receipts_writable() AND r.state='received' AND r.redacted_at IS NULL
        AND r.retention_until>now() AND NOT public.buyeros_receipt_dependency_expired(ws,'search',receipt,r.request)
        FOR SHARE;
      RETURN FOUND;
    END $read_lock$;
    REVOKE ALL ON FUNCTION public.buyeros_lock_search_receipt(uuid,uuid) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_lock_search_receipt(uuid,uuid) TO buyeros_api;
    """)
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0044_c61_search_intake' FROM public.alembic_version),false) $$")

def downgrade():
    # Retain erasure, narrow lock and every source/binding/hash/hold. A compatible
    # reader is required; downgraded admission/paid receipt writes stay closed.
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT false $$")
