"""Encrypted private single-claim contact receipts; preserve acceptance on rollback."""
from alembic import op, context

revision = '0042_c61_contact_receipts'
down_revision = '0041_c61_model_receipts'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num IN ('0040_c61_search_receipts','0041_c61_model_receipts','0042_c61_contact_receipts') FROM public.alembic_version),false) $$")
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num IN ('0041_c61_model_receipts','0042_c61_contact_receipts') FROM public.alembic_version),false) $$")
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $schema$
      SELECT COALESCE((SELECT version_num='0042_c61_contact_receipts' FROM public.alembic_version),false)
    $schema$;
    REVOKE ALL ON FUNCTION public.buyeros_contact_receipts_writable() FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_contact_receipts_writable() TO buyeros_api,buyeros_worker;
    CREATE TABLE IF NOT EXISTS public.contact_receipts (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES public.workspaces(id),
      project_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES public.users(id),
      buyer_id uuid NOT NULL, company_id uuid NOT NULL, quote_id uuid NOT NULL,
      operation_id uuid NOT NULL, outbox_id uuid NOT NULL, intent_key varchar(128) NOT NULL,
      request jsonb NOT NULL, request_hash varchar(64) NOT NULL,
      contract_hash varchar(64) NOT NULL, pricing_version varchar(64) NOT NULL,
      generation bigint NOT NULL CHECK(generation BETWEEN 1 AND 9007199254740991),
      runtime_epoch bigint NOT NULL CHECK(runtime_epoch BETWEEN 1 AND 9007199254740991),
      runtime_backend varchar(16) NOT NULL CHECK(runtime_backend IN ('celery','cloudflare')),
      state varchar(16) NOT NULL DEFAULT 'prepared' CHECK(state IN ('prepared','submitting','received','unknown')),
      response_ciphertext bytea, response_hash varchar(64), retention_until timestamptz NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,intent_key), UNIQUE(workspace_id,operation_id),
      FOREIGN KEY(workspace_id,project_id) REFERENCES public.projects(workspace_id,id),
      FOREIGN KEY(workspace_id,buyer_id) REFERENCES public.project_buyers(workspace_id,id),
      FOREIGN KEY(workspace_id,company_id) REFERENCES public.companies(workspace_id,id),
      FOREIGN KEY(workspace_id,quote_id) REFERENCES public.enrichment_quotes(workspace_id,id),
      FOREIGN KEY(workspace_id,operation_id) REFERENCES public.provider_operations(workspace_id,id),
      FOREIGN KEY(workspace_id,outbox_id) REFERENCES public.outbox_events(workspace_id,id),
      CHECK(jsonb_typeof(request)='object' AND octet_length(request::text)<=262144),
      CHECK(request_hash ~ '^[0-9a-f]{64}$' AND contract_hash ~ '^[0-9a-f]{64}$'),
      CHECK((state='received' AND response_ciphertext IS NOT NULL
             AND octet_length(response_ciphertext) BETWEEN 47 AND 262272 AND response_hash ~ '^[0-9a-f]{64}$')
         OR (state<>'received' AND response_ciphertext IS NULL AND response_hash IS NULL))
    );
    CREATE INDEX IF NOT EXISTS ix_contact_receipts_workspace ON public.contact_receipts(workspace_id);
    ALTER TABLE public.contact_receipts ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.contact_receipts FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON public.contact_receipts;
    CREATE POLICY tenant_isolation ON public.contact_receipts
      USING(workspace_id=current_setting('app.workspace_id',true)::uuid)
      WITH CHECK(workspace_id=current_setting('app.workspace_id',true)::uuid);
    REVOKE ALL ON public.contact_receipts FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT ON public.contact_receipts TO buyeros_api;
    GRANT SELECT,UPDATE ON public.contact_receipts TO buyeros_worker;
    CREATE OR REPLACE FUNCTION public.buyeros_contact_receipt_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $receipt$
    BEGIN
      IF (NEW.id,NEW.workspace_id,NEW.project_id,NEW.actor_id,NEW.buyer_id,NEW.company_id,NEW.quote_id,NEW.retention_until,NEW.operation_id,NEW.outbox_id,
          NEW.intent_key,NEW.request,NEW.request_hash,NEW.contract_hash,NEW.pricing_version,
          NEW.generation,NEW.runtime_epoch,NEW.runtime_backend,NEW.created_at)
          IS DISTINCT FROM
         (OLD.id,OLD.workspace_id,OLD.project_id,OLD.actor_id,OLD.buyer_id,OLD.company_id,OLD.quote_id,OLD.retention_until,OLD.operation_id,OLD.outbox_id,
          OLD.intent_key,OLD.request,OLD.request_hash,OLD.contract_hash,OLD.pricing_version,
          OLD.generation,OLD.runtime_epoch,OLD.runtime_backend,OLD.created_at)
        OR NOT ((OLD.state='prepared' AND NEW.state='submitting')
                 OR (OLD.state='submitting' AND NEW.state IN ('received','unknown')))
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable contact receipt'; END IF;
      RETURN NEW;
    END $receipt$;
    REVOKE ALL ON FUNCTION public.buyeros_contact_receipt_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
    DROP TRIGGER IF EXISTS buyeros_contact_receipt_immutable ON public.contact_receipts;
    CREATE TRIGGER buyeros_contact_receipt_immutable BEFORE UPDATE ON public.contact_receipts
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_contact_receipt_immutable();
    """)


def downgrade():
    # Unknown/received data is an acceptance record. Never delete it to roll back
    # metadata. Compatible readers remain available, but new claims require 0042.
    if context.is_offline_mode():
        # Without inspecting a database, conservatively retain every receipt.
        # The emitted rollback explicitly closes writes; re-upgrade reinstates
        # the exact-revision probe without changing rows or frozen payloads.
        op.execute("CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT false $$")
        return
    if not op.get_bind().exec_driver_sql('SELECT EXISTS(SELECT 1 FROM public.contact_receipts)').scalar():
        op.execute('DROP TABLE public.contact_receipts')
        op.execute('DROP FUNCTION public.buyeros_contact_receipt_immutable()')
        op.execute('DROP FUNCTION public.buyeros_contact_receipts_writable()')
