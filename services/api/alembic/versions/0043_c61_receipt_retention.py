"""Erase receipt payloads while retaining immutable acceptance and hold metadata."""
from alembic import op

revision='0043_c61_receipt_retention'
down_revision='0042_c61_contact_receipts'
branch_labels=None
depends_on=None

SERVICES=('search','model','contact')

def upgrade():
    for service in SERVICES:
        table=service+'_receipts'
        if service!='contact':
            op.execute(f"ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS retention_until timestamptz")
            op.execute(f"UPDATE public.{table} SET retention_until=created_at+interval '1 day' WHERE retention_until IS NULL")
            op.execute(f"ALTER TABLE public.{table} ALTER COLUMN retention_until SET NOT NULL, ALTER COLUMN retention_until SET DEFAULT (now()+interval '1 day')")
        op.execute(f"ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS redacted_at timestamptz, ADD COLUMN IF NOT EXISTS redaction_policy varchar(64)")
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{service}_receipt_expiry ON public.{table}(workspace_id,retention_until,id) WHERE redacted_at IS NULL")
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.receipt_source_bindings(
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES public.workspaces(id),
      source_id uuid NOT NULL, service varchar(16) NOT NULL CHECK(service IN ('search','model','contact')),
      receipt_id uuid NOT NULL, UNIQUE(workspace_id,source_id,service,receipt_id),
      FOREIGN KEY(workspace_id,source_id) REFERENCES public.source_documents(workspace_id,id)
    );
    CREATE INDEX IF NOT EXISTS ix_receipt_source_binding ON public.receipt_source_bindings(workspace_id,service,receipt_id);
    ALTER TABLE public.receipt_source_bindings ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.receipt_source_bindings FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON public.receipt_source_bindings;
    CREATE POLICY tenant_isolation ON public.receipt_source_bindings
      USING(workspace_id=current_setting('app.workspace_id',true)::uuid)
      WITH CHECK(workspace_id=current_setting('app.workspace_id',true)::uuid);
    REVOKE ALL ON public.receipt_source_bindings FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT ON public.receipt_source_bindings TO buyeros_api;
    GRANT SELECT ON public.receipt_source_bindings TO buyeros_worker;
    CREATE OR REPLACE FUNCTION public.buyeros_receipt_source_guard() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $guard$
    DECLARE receipt_project uuid; found_receipt boolean;
    BEGIN
      CASE NEW.service
      WHEN 'search' THEN SELECT project_id INTO receipt_project FROM public.search_receipts WHERE workspace_id=NEW.workspace_id AND id=NEW.receipt_id AND redacted_at IS NULL; found_receipt=FOUND;
      WHEN 'model' THEN SELECT project_id INTO receipt_project FROM public.model_receipts WHERE workspace_id=NEW.workspace_id AND id=NEW.receipt_id AND redacted_at IS NULL; found_receipt=FOUND;
      WHEN 'contact' THEN SELECT project_id INTO receipt_project FROM public.contact_receipts WHERE workspace_id=NEW.workspace_id AND id=NEW.receipt_id AND redacted_at IS NULL; found_receipt=FOUND;
      ELSE found_receipt=false;
      END CASE;
      IF found_receipt IS TRUE THEN
        SELECT EXISTS(SELECT 1 FROM public.source_documents s WHERE s.workspace_id=NEW.workspace_id AND s.id=NEW.source_id
          AND (s.project_id IS NULL OR s.project_id=receipt_project)
          AND s.permission_purpose=CASE WHEN NEW.service='contact' THEN 'contact_research' ELSE 'account_research' END) INTO found_receipt;
      END IF;
      IF found_receipt IS NOT TRUE THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='current scoped receipt required'; END IF;
      RETURN NEW;
    END $guard$;
    REVOKE ALL ON FUNCTION public.buyeros_receipt_source_guard() FROM PUBLIC,buyeros_api,buyeros_worker;
    DROP TRIGGER IF EXISTS buyeros_receipt_source_guard ON public.receipt_source_bindings;
    CREATE TRIGGER buyeros_receipt_source_guard BEFORE INSERT ON public.receipt_source_bindings FOR EACH ROW EXECUTE FUNCTION public.buyeros_receipt_source_guard();
    CREATE OR REPLACE FUNCTION public.buyeros_receipt_dependency_expired(ws uuid, service_name text, receipt uuid, payload jsonb)
      RETURNS boolean LANGUAGE sql STABLE SET search_path=pg_catalog,public AS $dependency$
      SELECT ws=current_setting('app.workspace_id',true)::uuid AND EXISTS(
        SELECT 1 FROM public.source_documents s WHERE s.workspace_id=ws
        AND (s.retention_until<=now() OR (s.excerpt IS NULL AND s.canonical_url LIKE 'https://redacted.invalid/%'))
        AND (EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws AND b.source_id=s.id AND b.service=service_name AND b.receipt_id=receipt)
          OR (service_name='model' AND EXISTS(SELECT 1 FROM jsonb_array_elements(
            CASE WHEN jsonb_typeof(payload#>'{basis,evidence}')='array' THEN payload#>'{basis,evidence}' ELSE '[]'::jsonb END
          ) e WHERE e->>'source_id'=s.id::text))))
    $dependency$;
    REVOKE ALL ON FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb) TO buyeros_api,buyeros_worker;
    """)
    for service in SERVICES:
        table=service+'_receipts';payload='response_ciphertext' if service=='contact' else 'response'
        # Replace only the prior received/response consistency check. Request,
        # hashes, enums, scope/FKs and RLS remain in force, including on rollback.
        op.execute(f"""DO $checks$ DECLARE c record; BEGIN
          FOR c IN SELECT conname FROM pg_catalog.pg_constraint WHERE conrelid='public.{table}'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%state%' AND pg_get_constraintdef(oid) LIKE '%response_hash%'
          LOOP EXECUTE format('ALTER TABLE public.{table} DROP CONSTRAINT %I',c.conname); END LOOP;
        END $checks$""")
        if service=='contact':known="response_ciphertext IS NOT NULL AND octet_length(response_ciphertext) BETWEEN 47 AND 262272"
        elif service=='search':known="jsonb_typeof(response)='array' AND jsonb_array_length(response)<=20 AND octet_length(response::text)<=262144"
        else:known="jsonb_typeof(response)='object' AND octet_length(response::text)<=262144"
        op.execute(f"""ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS c61_{service}_receipt_payload;
          ALTER TABLE public.{table} ADD CONSTRAINT c61_{service}_receipt_payload CHECK((
            (redacted_at IS NOT NULL AND redaction_policy ~ '^[A-Za-z0-9._-]{{1,64}}$' AND request=jsonb_build_object('redacted',true) AND {payload} IS NULL)
            OR (redacted_at IS NULL AND redaction_policy IS NULL AND ((state='received' AND {known} AND response_hash ~ '^[0-9a-f]{{64}}$') OR (state<>'received' AND {payload} IS NULL AND response_hash IS NULL)))
          ) IS TRUE)""")
        op.execute(f"""
        CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipt_immutable() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog,public AS $receipt$
        BEGIN
          IF TG_OP='INSERT' THEN
            IF NEW.redacted_at IS NOT NULL OR NEW.redaction_policy IS NOT NULL OR NEW.retention_until<=now()
              OR NEW.retention_until>now()+interval '30 days' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='current finite private receipt required'; END IF;
            RETURN NEW;
          END IF;
          IF NEW.redacted_at IS NOT NULL THEN
            IF OLD.redacted_at IS NOT NULL OR NEW.redacted_at>now() OR NEW.redaction_policy IS NULL
              OR NEW.request<>jsonb_build_object('redacted',true) OR NEW.{payload} IS NOT NULL
              OR (to_jsonb(NEW)-ARRAY['request','{payload}','redacted_at','redaction_policy','updated_at']) IS DISTINCT FROM
                 (to_jsonb(OLD)-ARRAY['request','{payload}','redacted_at','redaction_policy','updated_at'])
              OR NOT (OLD.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'{service}',OLD.id,OLD.request))
              THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable receipt erasure metadata or deadline'; END IF;
            RETURN NEW;
          END IF;
          IF OLD.redacted_at IS NOT NULL OR NEW.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'{service}',OLD.id,OLD.request)
            OR (to_jsonb(NEW)-ARRAY['state','{payload}','response_hash','updated_at']) IS DISTINCT FROM
               (to_jsonb(OLD)-ARRAY['state','{payload}','response_hash','updated_at'])
            OR NOT ((OLD.state='prepared' AND NEW.state='submitting') OR (OLD.state='submitting' AND NEW.state IN ('received','unknown')))
            THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable {service} receipt'; END IF;
          RETURN NEW;
        END $receipt$;
        REVOKE ALL ON FUNCTION public.buyeros_{service}_receipt_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
        DROP TRIGGER IF EXISTS buyeros_{service}_receipt_immutable ON public.{table};
        CREATE TRIGGER buyeros_{service}_receipt_immutable BEFORE INSERT OR UPDATE ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.buyeros_{service}_receipt_immutable();
        CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
          SELECT COALESCE((SELECT version_num='0043_c61_receipt_retention' FROM public.alembic_version),false) $$;
        """)

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
        INSERT INTO public.audit_events(id,workspace_id,action,subject_type,subject_id,detail_digest,reason)
          VALUES(gen_random_uuid(),ws,'provider_receipt.expired',service_name||'_receipt',receipt::text,
            'sha256:'||encode(sha256(convert_to(policy,'UTF8')),'hex'),'retention_expired');
      END IF;
      RETURN affected=1;
    END $erase$;
    REVOKE ALL ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) TO buyeros_api,buyeros_worker;
    """)

def downgrade():
    # Preserve tombstones, payload erasure guards, bindings and acceptance hashes.
    # A compatible reader is part of the rollback payload; no payload resurrection.
    for service in SERVICES:
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT false $$")
