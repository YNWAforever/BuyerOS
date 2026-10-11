BEGIN;

-- Running upgrade 0033_api_rate_windows -> 0034_worker_execution

CREATE TABLE worker_runtime_control (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        backend VARCHAR(16) NOT NULL DEFAULT 'celery' CHECK(backend IN ('celery','cloudflare')),
        enabled BOOLEAN NOT NULL DEFAULT false,
        epoch BIGINT NOT NULL DEFAULT 1 CHECK(epoch BETWEEN 1 AND 9007199254740991),
        cursor UUID, active_owner UUID, active_until TIMESTAMPTZ,
        CHECK((active_owner IS NULL) = (active_until IS NULL)));

INSERT INTO worker_runtime_control(singleton) VALUES(1);

CREATE FUNCTION enforce_worker_runtime_epoch() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        IF NEW.epoch < OLD.epoch OR ((NEW.backend<>OLD.backend OR NEW.enabled<>OLD.enabled)
             AND NEW.epoch<=OLD.epoch) THEN
            RAISE EXCEPTION 'runtime selector changes require a newer epoch';
        END IF; RETURN NEW; END $$;

CREATE TRIGGER worker_runtime_epoch BEFORE UPDATE ON worker_runtime_control FOR EACH ROW EXECUTE FUNCTION enforce_worker_runtime_epoch();

CREATE TABLE worker_bridge_nonces (
        key_id VARCHAR(64) NOT NULL, nonce UUID NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY(key_id,nonce));

CREATE INDEX ix_worker_bridge_nonces_expiry ON worker_bridge_nonces(expires_at);

CREATE TABLE worker_steps (
        id UUID PRIMARY KEY, workspace_id UUID NOT NULL, outbox_id UUID NOT NULL,
        generation BIGINT NOT NULL CHECK(generation BETWEEN 1 AND 9007199254740991),
        step_key VARCHAR(64) NOT NULL, runtime_epoch BIGINT NOT NULL,
        owner UUID NOT NULL, expires_at TIMESTAMPTZ NOT NULL,
        state VARCHAR(16) NOT NULL CHECK(state IN ('running','done','blocked','reconcile')),
        outcome JSONB, attempts INTEGER NOT NULL DEFAULT 1 CHECK(attempts BETWEEN 1 AND 512),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(workspace_id,id), UNIQUE(workspace_id,outbox_id,generation,step_key),
        FOREIGN KEY(workspace_id,outbox_id) REFERENCES outbox_events(workspace_id,id),
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id));

CREATE INDEX ix_worker_steps_workspace_id ON worker_steps(workspace_id);

ALTER TABLE worker_steps ENABLE ROW LEVEL SECURITY;

ALTER TABLE worker_steps FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON worker_steps
        USING(workspace_id=current_setting('app.workspace_id',true)::uuid)
        WITH CHECK(workspace_id=current_setting('app.workspace_id',true)::uuid);

ALTER TABLE outbox_events ADD COLUMN runtime_backend VARCHAR(16) DEFAULT 'celery' NOT NULL;

ALTER TABLE outbox_events ADD COLUMN runtime_epoch BIGINT DEFAULT '1' NOT NULL;

ALTER TABLE outbox_events ADD CONSTRAINT ck_outbox_events_ck_outbox_events_runtime_backend CHECK (runtime_backend IN ('celery','cloudflare'));

ALTER TABLE outbox_events ADD CONSTRAINT ck_outbox_events_ck_outbox_events_runtime_epoch CHECK (runtime_epoch BETWEEN 1 AND 9007199254740991);

GRANT SELECT ON worker_runtime_control TO buyeros_worker;

GRANT UPDATE(cursor,active_owner,active_until) ON worker_runtime_control TO buyeros_worker;

GRANT SELECT,INSERT,UPDATE,DELETE ON worker_steps,worker_bridge_nonces TO buyeros_worker;

UPDATE alembic_version SET version_num='0034_worker_execution' WHERE alembic_version.version_num = '0033_api_rate_windows';

-- Running upgrade 0034_worker_execution -> 0035_worker_recovery_probe

ALTER TABLE worker_runtime_control ADD COLUMN recovery_cursor UUID;

GRANT UPDATE(recovery_cursor) ON worker_runtime_control TO buyeros_worker;

GRANT SELECT(backend,enabled,epoch) ON worker_runtime_control TO buyeros_api;

CREATE TABLE worker_runtime_probe (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        runtime_epoch BIGINT NOT NULL DEFAULT 1 CHECK(runtime_epoch BETWEEN 1 AND 9007199254740991),
        last_probe_id UUID, last_probe_at TIMESTAMPTZ,
        metrics_epoch BIGINT NOT NULL DEFAULT 1 CHECK(metrics_epoch BETWEEN 1 AND 9007199254740991),
        oldest_work_at TIMESTAMPTZ, scan_oldest_at TIMESTAMPTZ,
        CHECK((last_probe_id IS NULL) = (last_probe_at IS NULL)));

INSERT INTO worker_runtime_probe(singleton) VALUES(1);

GRANT SELECT,UPDATE ON worker_runtime_probe TO buyeros_worker;

GRANT SELECT ON worker_runtime_probe TO buyeros_api;

UPDATE alembic_version SET version_num='0035_worker_recovery_probe' WHERE alembic_version.version_num = '0034_worker_execution';

-- Running upgrade 0035_worker_recovery_probe -> 0036_checkpoint_schema_grants

REVOKE ALL ON buyeros_graph.checkpoint_migrations FROM buyeros_worker;

GRANT SELECT ON buyeros_graph.checkpoint_migrations TO buyeros_worker;

UPDATE alembic_version SET version_num='0036_checkpoint_schema_grants' WHERE alembic_version.version_num = '0035_worker_recovery_probe';

-- Running upgrade 0036_checkpoint_schema_grants -> 0037_bulk_manifests

CREATE TABLE bulk_manifests (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    project_id UUID NOT NULL,
    actor_user_id UUID NOT NULL,
    specification JSONB NOT NULL,
    operation VARCHAR(40) NOT NULL,
    command JSONB NOT NULL,
    digest VARCHAR(64) NOT NULL,
    count INTEGER NOT NULL,
    version INTEGER NOT NULL,
    status VARCHAR(16) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    job_id UUID,
    result JSONB,
    CONSTRAINT pk_bulk_manifests PRIMARY KEY (id),
    CONSTRAINT uq_bulk_manifests_workspace_id UNIQUE (workspace_id, id),
    CONSTRAINT fk_bulk_manifests_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    CONSTRAINT fk_bulk_manifests_project FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id),
    CONSTRAINT fk_bulk_manifests_actor FOREIGN KEY(actor_user_id) REFERENCES users (id),
    CONSTRAINT ck_bulk_manifests_ck_bulk_manifests_count_range CHECK (count BETWEEN 0 AND 10000),
    CONSTRAINT ck_bulk_manifests_ck_bulk_manifests_version_positive CHECK (version > 0),
    CONSTRAINT ck_bulk_manifests_ck_bulk_manifests_status CHECK (status IN ('preparing','ready','executed'))
);

CREATE TABLE bulk_manifest_items (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    manifest_id UUID NOT NULL,
    buyer_id UUID NOT NULL,
    ordinal INTEGER NOT NULL,
    expected_version INTEGER NOT NULL,
    CONSTRAINT pk_bulk_manifest_items PRIMARY KEY (id),
    CONSTRAINT uq_bulk_manifest_items_workspace_id UNIQUE (workspace_id, id),
    CONSTRAINT uq_bulk_manifest_items_buyer UNIQUE (workspace_id, manifest_id, buyer_id),
    CONSTRAINT uq_bulk_manifest_items_ordinal UNIQUE (workspace_id, manifest_id, ordinal),
    CONSTRAINT fk_bulk_manifest_items_manifest FOREIGN KEY(workspace_id, manifest_id) REFERENCES bulk_manifests (workspace_id, id),
    CONSTRAINT ck_bulk_manifest_items_ck_bulk_manifest_items_position_version CHECK (ordinal BETWEEN 0 AND 9999 AND expected_version > 0)
);

CREATE INDEX ix_bulk_manifests_workspace_id ON bulk_manifests (workspace_id);

ALTER TABLE bulk_manifests ENABLE ROW LEVEL SECURITY;

ALTER TABLE bulk_manifests FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON bulk_manifests USING (workspace_id=current_setting('app.workspace_id')::uuid) WITH CHECK (workspace_id=current_setting('app.workspace_id')::uuid);

GRANT SELECT,INSERT ON bulk_manifests TO buyeros_api;

GRANT SELECT ON bulk_manifests TO buyeros_worker;

CREATE INDEX ix_bulk_manifest_items_workspace_id ON bulk_manifest_items (workspace_id);

ALTER TABLE bulk_manifest_items ENABLE ROW LEVEL SECURITY;

ALTER TABLE bulk_manifest_items FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON bulk_manifest_items USING (workspace_id=current_setting('app.workspace_id')::uuid) WITH CHECK (workspace_id=current_setting('app.workspace_id')::uuid);

GRANT SELECT,INSERT ON bulk_manifest_items TO buyeros_api;

GRANT SELECT ON bulk_manifest_items TO buyeros_worker;

GRANT UPDATE ON bulk_manifests TO buyeros_api;

CREATE INDEX ix_bulk_manifests_actor_project ON bulk_manifests (workspace_id, actor_user_id, project_id, created_at);

CREATE FUNCTION guard_bulk_manifest_item_insert() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM bulk_manifests WHERE workspace_id=NEW.workspace_id AND id=NEW.manifest_id AND status='preparing') THEN
        RAISE EXCEPTION 'bulk manifest item can only be appended while preparing';
      END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER bulk_manifest_item_insert BEFORE INSERT ON bulk_manifest_items FOR EACH ROW EXECUTE FUNCTION guard_bulk_manifest_item_insert();

ALTER TABLE async_jobs ADD COLUMN manifest_id UUID;

ALTER TABLE async_jobs ADD CONSTRAINT fk_async_jobs_manifest FOREIGN KEY(workspace_id, manifest_id) REFERENCES bulk_manifests (workspace_id, id);

ALTER TABLE async_jobs DROP CONSTRAINT ck_async_jobs_ck_async_jobs_requested_range;

ALTER TABLE async_jobs ADD CONSTRAINT ck_async_jobs_ck_async_jobs_requested_range CHECK (requested BETWEEN 1 AND 1000 OR (manifest_id IS NOT NULL AND requested BETWEEN 1 AND 10000));

CREATE FUNCTION guard_bulk_manifest_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NEW.workspace_id <> OLD.workspace_id OR NEW.project_id <> OLD.project_id OR NEW.actor_user_id <> OLD.actor_user_id
        OR NEW.specification <> OLD.specification OR NEW.command <> OLD.command OR NEW.operation <> OLD.operation OR NEW.expires_at <> OLD.expires_at
        OR (OLD.status <> 'preparing' AND (NEW.digest <> OLD.digest OR NEW.count <> OLD.count)) THEN
        RAISE EXCEPTION 'bulk manifest frozen basis is immutable';
      END IF;
      IF (OLD.status = 'ready' AND NEW.status NOT IN ('ready','executed')) OR (OLD.status = 'executed' AND NEW IS DISTINCT FROM OLD) THEN
        RAISE EXCEPTION 'bulk manifest cannot be reopened or rewritten after execution';
      END IF;
      RETURN NEW;
    END $$;

CREATE TRIGGER bulk_manifest_frozen BEFORE UPDATE ON bulk_manifests FOR EACH ROW EXECUTE FUNCTION guard_bulk_manifest_frozen();

UPDATE alembic_version SET version_num='0037_bulk_manifests' WHERE alembic_version.version_num = '0036_checkpoint_schema_grants';

-- Running upgrade 0037_bulk_manifests -> 0038_c61_workspace_directory

DO $owner_check$
    BEGIN
        IF current_user IN ('buyeros_api','buyeros_worker') OR NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=current_user
                AND (rolsuper OR rolbypassrls)
        ) THEN
            RAISE EXCEPTION 'directory requires an existing privileged migration owner'
                USING ERRCODE='42501';
        END IF;
    END $owner_check$;;

CREATE INDEX ix_memberships_active_user_workspace ON public.memberships (user_id, workspace_id) WHERE active IS TRUE;

CREATE FUNCTION public.buyeros_workspace_directory(p_actor uuid, p_offset bigint, p_limit integer)
    RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $directory$
    DECLARE result jsonb;
    BEGIN
        IF session_user <> 'buyeros_api' OR p_actor IS NULL
            OR current_setting('app.user_id', true) IS DISTINCT FROM p_actor::text THEN
            RAISE EXCEPTION 'trusted canonical actor binding required' USING ERRCODE='42501';
        END IF;
        IF current_setting('transaction_read_only') <> 'on' THEN
            RAISE EXCEPTION 'directory requires a read-only transaction' USING ERRCODE='25006';
        END IF;
        IF p_offset IS NULL OR p_offset < 0 OR p_limit IS NULL OR p_limit < 1 OR p_limit > 100 THEN
            RAISE EXCEPTION 'bounded pagination required' USING ERRCODE='22023';
        END IF;
        WITH visible AS MATERIALIZED (
            SELECT w.id, w.name, m.id AS membership_id, m.roles
            FROM public.memberships AS m JOIN public.workspaces AS w ON w.id=m.workspace_id
            WHERE m.user_id=p_actor AND m.active IS TRUE
        ), page AS (
            SELECT * FROM visible ORDER BY id OFFSET p_offset LIMIT p_limit
        )
        SELECT jsonb_build_object(
            'items', COALESCE((SELECT jsonb_agg(jsonb_build_object(
                'id',id::text,'name',name,'membership_id',membership_id::text,
                'roles',to_jsonb(roles),'data_mode','live') ORDER BY id) FROM page),'[]'::jsonb),
            'offset',p_offset,'limit',p_limit,'total',(SELECT count(*) FROM visible)
        ) INTO result;
        RETURN result;
    END $directory$;;

REVOKE ALL ON FUNCTION public.buyeros_workspace_directory(uuid,bigint,integer) FROM PUBLIC, buyeros_worker;

GRANT EXECUTE ON FUNCTION public.buyeros_workspace_directory(uuid,bigint,integer) TO buyeros_api;

UPDATE alembic_version SET version_num='0038_c61_workspace_directory' WHERE alembic_version.version_num = '0037_bulk_manifests';

-- Running upgrade 0038_c61_workspace_directory -> 0039_c61_user_identities

CREATE TABLE IF NOT EXISTS public.user_identities (
      issuer varchar(255) NOT NULL, subject varchar(255) NOT NULL,
      user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
      status varchar(16) NOT NULL DEFAULT 'active', proof_ref varchar(200) NOT NULL,
      version integer NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT pk_user_identities PRIMARY KEY(issuer,subject),
      CONSTRAINT ck_user_identities_status CHECK (status IN ('active','revoked')),
      CONSTRAINT ck_user_identities_version CHECK (version>=1),
      CONSTRAINT ck_user_identities_nonempty CHECK (issuer<>'' AND subject<>'' AND proof_ref<>'')
    );
    CREATE INDEX IF NOT EXISTS ix_user_identities_user ON public.user_identities(user_id);
    REVOKE ALL ON public.user_identities FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT(issuer,subject,user_id,status) ON public.user_identities TO buyeros_api;
    INSERT INTO public.user_identities(issuer,subject,user_id,proof_ref)
      SELECT issuer,subject,id,'legacy-backfill:'||id::text FROM public.users
      ON CONFLICT(issuer,subject) DO NOTHING;
    DO $verify$ BEGIN
      IF EXISTS (SELECT 1 FROM public.users u LEFT JOIN public.user_identities i
          ON i.issuer=u.issuer AND i.subject=u.subject AND i.user_id=u.id WHERE i.user_id IS NULL)
      THEN RAISE EXCEPTION 'legacy canonical mapping conflict'; END IF;
    END $verify$;;

CREATE OR REPLACE FUNCTION public.buyeros_primary_identity() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $primary$
    BEGIN
      INSERT INTO public.user_identities(issuer,subject,user_id,proof_ref)
        VALUES(NEW.issuer,NEW.subject,NEW.id,COALESCE(NULLIF(current_setting('app.identity_proof_ref',true),''),'canonical-primary:'||NEW.id::text))
        ON CONFLICT(issuer,subject) DO NOTHING;
      IF NOT EXISTS(SELECT 1 FROM public.user_identities WHERE issuer=NEW.issuer
          AND subject=NEW.subject AND user_id=NEW.id AND status='active')
      THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='principal already bound'; END IF;
      RETURN NEW;
    END $primary$;
    REVOKE ALL ON FUNCTION public.buyeros_primary_identity() FROM PUBLIC,buyeros_api,buyeros_worker;
    DROP TRIGGER IF EXISTS buyeros_primary_identity ON public.users;
    CREATE TRIGGER buyeros_primary_identity AFTER INSERT ON public.users
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_primary_identity();
    CREATE OR REPLACE FUNCTION public.buyeros_identity_immutable() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $immutable$
    BEGIN
      IF (NEW.issuer,NEW.subject,NEW.user_id,NEW.proof_ref,NEW.created_at)
          IS DISTINCT FROM (OLD.issuer,OLD.subject,OLD.user_id,OLD.proof_ref,OLD.created_at)
        OR NEW.version<>OLD.version+1 OR OLD.status<>'active' OR NEW.status<>'revoked'
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable identity association'; END IF;
      RETURN NEW;
    END $immutable$;
    REVOKE ALL ON FUNCTION public.buyeros_identity_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
    DROP TRIGGER IF EXISTS buyeros_identity_immutable ON public.user_identities;
    CREATE TRIGGER buyeros_identity_immutable BEFORE UPDATE ON public.user_identities
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_identity_immutable();;

UPDATE alembic_version SET version_num='0039_c61_user_identities' WHERE alembic_version.version_num = '0038_c61_workspace_directory';

-- Running upgrade 0039_c61_user_identities -> 0040_c61_search_receipts

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $schema$
      SELECT COALESCE((SELECT version_num='0040_c61_search_receipts' FROM public.alembic_version),false)
    $schema$;
    REVOKE ALL ON FUNCTION public.buyeros_search_receipts_writable() FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_search_receipts_writable() TO buyeros_api,buyeros_worker;
    CREATE TABLE IF NOT EXISTS public.search_receipts (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES public.workspaces(id),
      project_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES public.users(id),
      operation_id uuid NOT NULL, outbox_id uuid NOT NULL, intent_key varchar(128) NOT NULL,
      request jsonb NOT NULL, request_hash varchar(64) NOT NULL,
      contract_hash varchar(64) NOT NULL, pricing_version varchar(64) NOT NULL,
      generation bigint NOT NULL CHECK(generation BETWEEN 1 AND 9007199254740991),
      runtime_epoch bigint NOT NULL CHECK(runtime_epoch BETWEEN 1 AND 9007199254740991),
      runtime_backend varchar(16) NOT NULL CHECK(runtime_backend IN ('celery','cloudflare')),
      state varchar(16) NOT NULL DEFAULT 'prepared' CHECK(state IN ('prepared','submitting','received','unknown')),
      response jsonb, response_hash varchar(64),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,intent_key), UNIQUE(workspace_id,operation_id),
      FOREIGN KEY(workspace_id,project_id) REFERENCES public.projects(workspace_id,id),
      FOREIGN KEY(workspace_id,operation_id) REFERENCES public.provider_operations(workspace_id,id),
      FOREIGN KEY(workspace_id,outbox_id) REFERENCES public.outbox_events(workspace_id,id),
      CHECK(jsonb_typeof(request)='object' AND octet_length(request::text)<=16384),
      CHECK(request_hash ~ '^[0-9a-f]{64}$' AND contract_hash ~ '^[0-9a-f]{64}$'),
      CHECK((state='received' AND jsonb_typeof(response)='array' AND jsonb_array_length(response)<=20
             AND octet_length(response::text)<=262144 AND response_hash ~ '^[0-9a-f]{64}$')
         OR (state<>'received' AND response IS NULL AND response_hash IS NULL))
    );
    CREATE INDEX IF NOT EXISTS ix_search_receipts_workspace ON public.search_receipts(workspace_id);
    ALTER TABLE public.search_receipts ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.search_receipts FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON public.search_receipts;
    CREATE POLICY tenant_isolation ON public.search_receipts
      USING(workspace_id=current_setting('app.workspace_id',true)::uuid)
      WITH CHECK(workspace_id=current_setting('app.workspace_id',true)::uuid);
    REVOKE ALL ON public.search_receipts FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT ON public.search_receipts TO buyeros_api;
    GRANT SELECT,UPDATE ON public.search_receipts TO buyeros_worker;
    CREATE OR REPLACE FUNCTION public.buyeros_search_receipt_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $receipt$
    BEGIN
      IF (NEW.id,NEW.workspace_id,NEW.project_id,NEW.actor_id,NEW.operation_id,NEW.outbox_id,
          NEW.intent_key,NEW.request,NEW.request_hash,NEW.contract_hash,NEW.pricing_version,
          NEW.generation,NEW.runtime_epoch,NEW.runtime_backend,NEW.created_at)
          IS DISTINCT FROM
         (OLD.id,OLD.workspace_id,OLD.project_id,OLD.actor_id,OLD.operation_id,OLD.outbox_id,
          OLD.intent_key,OLD.request,OLD.request_hash,OLD.contract_hash,OLD.pricing_version,
          OLD.generation,OLD.runtime_epoch,OLD.runtime_backend,OLD.created_at)
        OR NOT ((OLD.state='prepared' AND NEW.state='submitting')
                 OR (OLD.state='submitting' AND NEW.state IN ('received','unknown')))
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable search receipt'; END IF;
      RETURN NEW;
    END $receipt$;
    REVOKE ALL ON FUNCTION public.buyeros_search_receipt_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
    DROP TRIGGER IF EXISTS buyeros_search_receipt_immutable ON public.search_receipts;
    CREATE TRIGGER buyeros_search_receipt_immutable BEFORE UPDATE ON public.search_receipts
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_search_receipt_immutable();;

UPDATE alembic_version SET version_num='0040_c61_search_receipts' WHERE alembic_version.version_num = '0039_c61_user_identities';

-- Running upgrade 0040_c61_search_receipts -> 0041_c61_model_receipts

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num IN ('0040_c61_search_receipts','0041_c61_model_receipts') FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean
      LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $schema$
      SELECT COALESCE((SELECT version_num='0041_c61_model_receipts' FROM public.alembic_version),false)
    $schema$;
    REVOKE ALL ON FUNCTION public.buyeros_model_receipts_writable() FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_model_receipts_writable() TO buyeros_api,buyeros_worker;
    CREATE TABLE IF NOT EXISTS public.model_receipts (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES public.workspaces(id),
      project_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES public.users(id),
      operation_id uuid NOT NULL, outbox_id uuid NOT NULL, intent_key varchar(128) NOT NULL,
      request jsonb NOT NULL, request_hash varchar(64) NOT NULL,
      contract_hash varchar(64) NOT NULL, pricing_version varchar(64) NOT NULL,
      generation bigint NOT NULL CHECK(generation BETWEEN 1 AND 9007199254740991),
      runtime_epoch bigint NOT NULL CHECK(runtime_epoch BETWEEN 1 AND 9007199254740991),
      runtime_backend varchar(16) NOT NULL CHECK(runtime_backend IN ('celery','cloudflare')),
      state varchar(16) NOT NULL DEFAULT 'prepared' CHECK(state IN ('prepared','submitting','received','unknown')),
      response jsonb, response_hash varchar(64),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,intent_key), UNIQUE(workspace_id,operation_id),
      FOREIGN KEY(workspace_id,project_id) REFERENCES public.projects(workspace_id,id),
      FOREIGN KEY(workspace_id,operation_id) REFERENCES public.provider_operations(workspace_id,id),
      FOREIGN KEY(workspace_id,outbox_id) REFERENCES public.outbox_events(workspace_id,id),
      CHECK(jsonb_typeof(request)='object' AND octet_length(request::text)<=262144),
      CHECK(request_hash ~ '^[0-9a-f]{64}$' AND contract_hash ~ '^[0-9a-f]{64}$'),
      CHECK((state='received' AND jsonb_typeof(response)='object'
             AND octet_length(response::text)<=262144 AND response_hash ~ '^[0-9a-f]{64}$')
         OR (state<>'received' AND response IS NULL AND response_hash IS NULL))
    );
    CREATE INDEX IF NOT EXISTS ix_model_receipts_workspace ON public.model_receipts(workspace_id);
    ALTER TABLE public.model_receipts ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.model_receipts FORCE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS tenant_isolation ON public.model_receipts;
    CREATE POLICY tenant_isolation ON public.model_receipts
      USING(workspace_id=current_setting('app.workspace_id',true)::uuid)
      WITH CHECK(workspace_id=current_setting('app.workspace_id',true)::uuid);
    REVOKE ALL ON public.model_receipts FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT ON public.model_receipts TO buyeros_api;
    GRANT SELECT,UPDATE ON public.model_receipts TO buyeros_worker;
    CREATE OR REPLACE FUNCTION public.buyeros_model_receipt_immutable() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public AS $receipt$
    BEGIN
      IF (NEW.id,NEW.workspace_id,NEW.project_id,NEW.actor_id,NEW.operation_id,NEW.outbox_id,
          NEW.intent_key,NEW.request,NEW.request_hash,NEW.contract_hash,NEW.pricing_version,
          NEW.generation,NEW.runtime_epoch,NEW.runtime_backend,NEW.created_at)
          IS DISTINCT FROM
         (OLD.id,OLD.workspace_id,OLD.project_id,OLD.actor_id,OLD.operation_id,OLD.outbox_id,
          OLD.intent_key,OLD.request,OLD.request_hash,OLD.contract_hash,OLD.pricing_version,
          OLD.generation,OLD.runtime_epoch,OLD.runtime_backend,OLD.created_at)
        OR NOT ((OLD.state='prepared' AND NEW.state='submitting')
                 OR (OLD.state='submitting' AND NEW.state IN ('received','unknown')))
      THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable model receipt'; END IF;
      RETURN NEW;
    END $receipt$;
    REVOKE ALL ON FUNCTION public.buyeros_model_receipt_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
    DROP TRIGGER IF EXISTS buyeros_model_receipt_immutable ON public.model_receipts;
    CREATE TRIGGER buyeros_model_receipt_immutable BEFORE UPDATE ON public.model_receipts
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_model_receipt_immutable();;

UPDATE alembic_version SET version_num='0041_c61_model_receipts' WHERE alembic_version.version_num = '0040_c61_search_receipts';

-- Running upgrade 0041_c61_model_receipts -> 0042_c61_contact_receipts

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num IN ('0040_c61_search_receipts','0041_c61_model_receipts','0042_c61_contact_receipts') FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num IN ('0041_c61_model_receipts','0042_c61_contact_receipts') FROM public.alembic_version),false) $$;

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
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_contact_receipt_immutable();;

UPDATE alembic_version SET version_num='0042_c61_contact_receipts' WHERE alembic_version.version_num = '0041_c61_model_receipts';

-- Running upgrade 0042_c61_contact_receipts -> 0043_c61_receipt_retention

ALTER TABLE public.search_receipts ADD COLUMN IF NOT EXISTS retention_until timestamptz;

UPDATE public.search_receipts SET retention_until=created_at+interval '1 day' WHERE retention_until IS NULL;

ALTER TABLE public.search_receipts ALTER COLUMN retention_until SET NOT NULL, ALTER COLUMN retention_until SET DEFAULT (now()+interval '1 day');

ALTER TABLE public.search_receipts ADD COLUMN IF NOT EXISTS redacted_at timestamptz, ADD COLUMN IF NOT EXISTS redaction_policy varchar(64);

CREATE INDEX IF NOT EXISTS ix_search_receipt_expiry ON public.search_receipts(workspace_id,retention_until,id) WHERE redacted_at IS NULL;

ALTER TABLE public.model_receipts ADD COLUMN IF NOT EXISTS retention_until timestamptz;

UPDATE public.model_receipts SET retention_until=created_at+interval '1 day' WHERE retention_until IS NULL;

ALTER TABLE public.model_receipts ALTER COLUMN retention_until SET NOT NULL, ALTER COLUMN retention_until SET DEFAULT (now()+interval '1 day');

ALTER TABLE public.model_receipts ADD COLUMN IF NOT EXISTS redacted_at timestamptz, ADD COLUMN IF NOT EXISTS redaction_policy varchar(64);

CREATE INDEX IF NOT EXISTS ix_model_receipt_expiry ON public.model_receipts(workspace_id,retention_until,id) WHERE redacted_at IS NULL;

ALTER TABLE public.contact_receipts ADD COLUMN IF NOT EXISTS redacted_at timestamptz, ADD COLUMN IF NOT EXISTS redaction_policy varchar(64);

CREATE INDEX IF NOT EXISTS ix_contact_receipt_expiry ON public.contact_receipts(workspace_id,retention_until,id) WHERE redacted_at IS NULL;

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
        AND (s.retention_until<=now() OR (s.excerpt IS NULL AND s.canonical_url LIKE 'https://redacted.invalid/%%'))
        AND (EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws AND b.source_id=s.id AND b.service=service_name AND b.receipt_id=receipt)
          OR (service_name='model' AND EXISTS(SELECT 1 FROM jsonb_array_elements(
            CASE WHEN jsonb_typeof(payload#>'{basis,evidence}')='array' THEN payload#>'{basis,evidence}' ELSE '[]'::jsonb END
          ) e WHERE e->>'source_id'=s.id::text))))
    $dependency$;
    REVOKE ALL ON FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_receipt_dependency_expired(uuid,text,uuid,jsonb) TO buyeros_api,buyeros_worker;;

DO $checks$ DECLARE c record; BEGIN
          FOR c IN SELECT conname FROM pg_catalog.pg_constraint WHERE conrelid='public.search_receipts'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%%state%%' AND pg_get_constraintdef(oid) LIKE '%%response_hash%%'
          LOOP EXECUTE format('ALTER TABLE public.search_receipts DROP CONSTRAINT %%I',c.conname); END LOOP;
        END $checks$;

ALTER TABLE public.search_receipts DROP CONSTRAINT IF EXISTS c61_search_receipt_payload;
          ALTER TABLE public.search_receipts ADD CONSTRAINT c61_search_receipt_payload CHECK((
            (redacted_at IS NOT NULL AND redaction_policy ~ '^[A-Za-z0-9._-]{1,64}$' AND request=jsonb_build_object('redacted',true) AND response IS NULL)
            OR (redacted_at IS NULL AND redaction_policy IS NULL AND ((state='received' AND jsonb_typeof(response)='array' AND jsonb_array_length(response)<=20 AND octet_length(response::text)<=262144 AND response_hash ~ '^[0-9a-f]{64}$') OR (state<>'received' AND response IS NULL AND response_hash IS NULL)))
          ) IS TRUE);

CREATE OR REPLACE FUNCTION public.buyeros_search_receipt_immutable() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog,public AS $receipt$
        BEGIN
          IF TG_OP='INSERT' THEN
            IF NEW.redacted_at IS NOT NULL OR NEW.redaction_policy IS NOT NULL OR NEW.retention_until<=now()
              OR NEW.retention_until>now()+interval '30 days' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='current finite private receipt required'; END IF;
            RETURN NEW;
          END IF;
          IF NEW.redacted_at IS NOT NULL THEN
            IF OLD.redacted_at IS NOT NULL OR NEW.redacted_at>now() OR NEW.redaction_policy IS NULL
              OR NEW.request<>jsonb_build_object('redacted',true) OR NEW.response IS NOT NULL
              OR (to_jsonb(NEW)-ARRAY['request','response','redacted_at','redaction_policy','updated_at']) IS DISTINCT FROM
                 (to_jsonb(OLD)-ARRAY['request','response','redacted_at','redaction_policy','updated_at'])
              OR NOT (OLD.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'search',OLD.id,OLD.request))
              THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable receipt erasure metadata or deadline'; END IF;
            RETURN NEW;
          END IF;
          IF OLD.redacted_at IS NOT NULL OR NEW.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'search',OLD.id,OLD.request)
            OR (to_jsonb(NEW)-ARRAY['state','response','response_hash','updated_at']) IS DISTINCT FROM
               (to_jsonb(OLD)-ARRAY['state','response','response_hash','updated_at'])
            OR NOT ((OLD.state='prepared' AND NEW.state='submitting') OR (OLD.state='submitting' AND NEW.state IN ('received','unknown')))
            THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable search receipt'; END IF;
          RETURN NEW;
        END $receipt$;
        REVOKE ALL ON FUNCTION public.buyeros_search_receipt_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
        DROP TRIGGER IF EXISTS buyeros_search_receipt_immutable ON public.search_receipts;
        CREATE TRIGGER buyeros_search_receipt_immutable BEFORE INSERT OR UPDATE ON public.search_receipts FOR EACH ROW EXECUTE FUNCTION public.buyeros_search_receipt_immutable();
        CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
          SELECT COALESCE((SELECT version_num='0043_c61_receipt_retention' FROM public.alembic_version),false) $$;;

DO $checks$ DECLARE c record; BEGIN
          FOR c IN SELECT conname FROM pg_catalog.pg_constraint WHERE conrelid='public.model_receipts'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%%state%%' AND pg_get_constraintdef(oid) LIKE '%%response_hash%%'
          LOOP EXECUTE format('ALTER TABLE public.model_receipts DROP CONSTRAINT %%I',c.conname); END LOOP;
        END $checks$;

ALTER TABLE public.model_receipts DROP CONSTRAINT IF EXISTS c61_model_receipt_payload;
          ALTER TABLE public.model_receipts ADD CONSTRAINT c61_model_receipt_payload CHECK((
            (redacted_at IS NOT NULL AND redaction_policy ~ '^[A-Za-z0-9._-]{1,64}$' AND request=jsonb_build_object('redacted',true) AND response IS NULL)
            OR (redacted_at IS NULL AND redaction_policy IS NULL AND ((state='received' AND jsonb_typeof(response)='object' AND octet_length(response::text)<=262144 AND response_hash ~ '^[0-9a-f]{64}$') OR (state<>'received' AND response IS NULL AND response_hash IS NULL)))
          ) IS TRUE);

CREATE OR REPLACE FUNCTION public.buyeros_model_receipt_immutable() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog,public AS $receipt$
        BEGIN
          IF TG_OP='INSERT' THEN
            IF NEW.redacted_at IS NOT NULL OR NEW.redaction_policy IS NOT NULL OR NEW.retention_until<=now()
              OR NEW.retention_until>now()+interval '30 days' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='current finite private receipt required'; END IF;
            RETURN NEW;
          END IF;
          IF NEW.redacted_at IS NOT NULL THEN
            IF OLD.redacted_at IS NOT NULL OR NEW.redacted_at>now() OR NEW.redaction_policy IS NULL
              OR NEW.request<>jsonb_build_object('redacted',true) OR NEW.response IS NOT NULL
              OR (to_jsonb(NEW)-ARRAY['request','response','redacted_at','redaction_policy','updated_at']) IS DISTINCT FROM
                 (to_jsonb(OLD)-ARRAY['request','response','redacted_at','redaction_policy','updated_at'])
              OR NOT (OLD.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'model',OLD.id,OLD.request))
              THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable receipt erasure metadata or deadline'; END IF;
            RETURN NEW;
          END IF;
          IF OLD.redacted_at IS NOT NULL OR NEW.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'model',OLD.id,OLD.request)
            OR (to_jsonb(NEW)-ARRAY['state','response','response_hash','updated_at']) IS DISTINCT FROM
               (to_jsonb(OLD)-ARRAY['state','response','response_hash','updated_at'])
            OR NOT ((OLD.state='prepared' AND NEW.state='submitting') OR (OLD.state='submitting' AND NEW.state IN ('received','unknown')))
            THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable model receipt'; END IF;
          RETURN NEW;
        END $receipt$;
        REVOKE ALL ON FUNCTION public.buyeros_model_receipt_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
        DROP TRIGGER IF EXISTS buyeros_model_receipt_immutable ON public.model_receipts;
        CREATE TRIGGER buyeros_model_receipt_immutable BEFORE INSERT OR UPDATE ON public.model_receipts FOR EACH ROW EXECUTE FUNCTION public.buyeros_model_receipt_immutable();
        CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
          SELECT COALESCE((SELECT version_num='0043_c61_receipt_retention' FROM public.alembic_version),false) $$;;

DO $checks$ DECLARE c record; BEGIN
          FOR c IN SELECT conname FROM pg_catalog.pg_constraint WHERE conrelid='public.contact_receipts'::regclass AND contype='c'
            AND pg_get_constraintdef(oid) LIKE '%%state%%' AND pg_get_constraintdef(oid) LIKE '%%response_hash%%'
          LOOP EXECUTE format('ALTER TABLE public.contact_receipts DROP CONSTRAINT %%I',c.conname); END LOOP;
        END $checks$;

ALTER TABLE public.contact_receipts DROP CONSTRAINT IF EXISTS c61_contact_receipt_payload;
          ALTER TABLE public.contact_receipts ADD CONSTRAINT c61_contact_receipt_payload CHECK((
            (redacted_at IS NOT NULL AND redaction_policy ~ '^[A-Za-z0-9._-]{1,64}$' AND request=jsonb_build_object('redacted',true) AND response_ciphertext IS NULL)
            OR (redacted_at IS NULL AND redaction_policy IS NULL AND ((state='received' AND response_ciphertext IS NOT NULL AND octet_length(response_ciphertext) BETWEEN 47 AND 262272 AND response_hash ~ '^[0-9a-f]{64}$') OR (state<>'received' AND response_ciphertext IS NULL AND response_hash IS NULL)))
          ) IS TRUE);

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipt_immutable() RETURNS trigger
          LANGUAGE plpgsql SET search_path=pg_catalog,public AS $receipt$
        BEGIN
          IF TG_OP='INSERT' THEN
            IF NEW.redacted_at IS NOT NULL OR NEW.redaction_policy IS NOT NULL OR NEW.retention_until<=now()
              OR NEW.retention_until>now()+interval '30 days' THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='current finite private receipt required'; END IF;
            RETURN NEW;
          END IF;
          IF NEW.redacted_at IS NOT NULL THEN
            IF OLD.redacted_at IS NOT NULL OR NEW.redacted_at>now() OR NEW.redaction_policy IS NULL
              OR NEW.request<>jsonb_build_object('redacted',true) OR NEW.response_ciphertext IS NOT NULL
              OR (to_jsonb(NEW)-ARRAY['request','response_ciphertext','redacted_at','redaction_policy','updated_at']) IS DISTINCT FROM
                 (to_jsonb(OLD)-ARRAY['request','response_ciphertext','redacted_at','redaction_policy','updated_at'])
              OR NOT (OLD.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'contact',OLD.id,OLD.request))
              THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable receipt erasure metadata or deadline'; END IF;
            RETURN NEW;
          END IF;
          IF OLD.redacted_at IS NOT NULL OR NEW.retention_until<=now() OR public.buyeros_receipt_dependency_expired(OLD.workspace_id,'contact',OLD.id,OLD.request)
            OR (to_jsonb(NEW)-ARRAY['state','response_ciphertext','response_hash','updated_at']) IS DISTINCT FROM
               (to_jsonb(OLD)-ARRAY['state','response_ciphertext','response_hash','updated_at'])
            OR NOT ((OLD.state='prepared' AND NEW.state='submitting') OR (OLD.state='submitting' AND NEW.state IN ('received','unknown')))
            THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='immutable contact receipt'; END IF;
          RETURN NEW;
        END $receipt$;
        REVOKE ALL ON FUNCTION public.buyeros_contact_receipt_immutable() FROM PUBLIC,buyeros_api,buyeros_worker;
        DROP TRIGGER IF EXISTS buyeros_contact_receipt_immutable ON public.contact_receipts;
        CREATE TRIGGER buyeros_contact_receipt_immutable BEFORE INSERT OR UPDATE ON public.contact_receipts FOR EACH ROW EXECUTE FUNCTION public.buyeros_contact_receipt_immutable();
        CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$
          SELECT COALESCE((SELECT version_num='0043_c61_receipt_retention' FROM public.alembic_version),false) $$;;

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
    GRANT EXECUTE ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) TO buyeros_api,buyeros_worker;;

UPDATE alembic_version SET version_num='0043_c61_receipt_retention' WHERE alembic_version.version_num = '0042_c61_contact_receipts';

-- Running upgrade 0043_c61_receipt_retention -> 0044_c61_search_intake

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
    GRANT EXECUTE ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) TO buyeros_api,buyeros_worker;;

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
    GRANT EXECUTE ON FUNCTION public.buyeros_lock_search_receipt(uuid,uuid) TO buyeros_api;;

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0044_c61_search_intake' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0044_c61_search_intake' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0044_c61_search_intake' FROM public.alembic_version),false) $$;

UPDATE alembic_version SET version_num='0044_c61_search_intake' WHERE alembic_version.version_num = '0043_c61_receipt_retention';

-- Running upgrade 0044_c61_search_intake -> 0045_c61_research_page_privacy

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
    GRANT EXECUTE ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) TO buyeros_api,buyeros_worker;;

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0045_c61_research_page_privacy' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0045_c61_research_page_privacy' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0045_c61_research_page_privacy' FROM public.alembic_version),false) $$;

UPDATE alembic_version SET version_num='0045_c61_research_page_privacy' WHERE alembic_version.version_num = '0044_c61_search_intake';

-- Running upgrade 0045_c61_research_page_privacy -> 0046_c61_derived_privacy

CREATE OR REPLACE FUNCTION public.buyeros_erase_search_derived(ws uuid, receipt uuid, policy text)
      RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,public SET lock_timeout='1s' AS $derived$
    DECLARE source_ids uuid[]; derived_evidence_ids text[]; project_ids uuid[]; item record; safe jsonb; canonical text; model_id uuid;
    BEGIN
      -- Owner-only helper. The public finite eraser has already performed the
      -- tenant/role/due CAS and source tombstone in this same transaction.
      SELECT array_agg(s.id ORDER BY s.id),array_agg(DISTINCT s.project_id)
        INTO source_ids,project_ids FROM public.source_documents s
        WHERE s.workspace_id=ws AND s.storage_mode IN ('search_result_metadata','research_page_excerpt')
          AND s.object_key IS NULL AND s.excerpt IS NULL AND s.retention_until<=now()
          AND s.canonical_url='https://redacted.invalid/'||s.id::text
          AND EXISTS(SELECT 1 FROM public.receipt_source_bindings b WHERE b.workspace_id=ws
            AND b.source_id=s.id AND b.service='search' AND b.receipt_id=receipt);
      IF source_ids IS NULL THEN RETURN; END IF;
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
    REVOKE ALL ON FUNCTION public.buyeros_erase_search_derived(uuid,uuid,text) FROM PUBLIC,buyeros_api,buyeros_worker;;

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
      IF affected=0 AND service_name='search' AND EXISTS(SELECT 1 FROM public.search_receipts r
        WHERE r.workspace_id=ws AND r.id=receipt AND r.redacted_at IS NOT NULL) THEN
        -- Compatible repair of retained pre-0046 tombstones. Return false:
        -- no new receipt redaction, audit, acceptance or economic mutation.
        PERFORM public.buyeros_erase_search_derived(ws,receipt,policy);
      END IF;
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
          PERFORM public.buyeros_erase_search_derived(ws,receipt,policy);
        END IF;
        INSERT INTO public.audit_events(id,workspace_id,action,subject_type,subject_id,detail_digest,reason)
          VALUES(gen_random_uuid(),ws,'provider_receipt.expired',service_name||'_receipt',receipt::text,
            'sha256:'||encode(sha256(convert_to(policy,'UTF8')),'hex'),'retention_expired');
      END IF;
      RETURN affected=1;
    END $erase$;
    REVOKE ALL ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_erase_provider_receipt(uuid,text,uuid,text) TO buyeros_api,buyeros_worker;;

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0046_c61_derived_privacy' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0046_c61_derived_privacy' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0046_c61_derived_privacy' FROM public.alembic_version),false) $$;

UPDATE alembic_version SET version_num='0046_c61_derived_privacy' WHERE alembic_version.version_num = '0045_c61_research_page_privacy';

-- Running upgrade 0046_c61_derived_privacy -> 0047_c61_legacy_source_privacy

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
    REVOKE ALL ON FUNCTION public.buyeros_erase_search_derived(uuid,uuid,text) FROM PUBLIC,buyeros_api,buyeros_worker;;

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0047_c61_legacy_source_privacy' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0047_c61_legacy_source_privacy' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0047_c61_legacy_source_privacy' FROM public.alembic_version),false) $$;

UPDATE alembic_version SET version_num='0047_c61_legacy_source_privacy' WHERE alembic_version.version_num = '0046_c61_derived_privacy';

-- Running upgrade 0047_c61_legacy_source_privacy -> 0048_c61_delivery_ledger

CREATE TABLE delivery_messages (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    project_id UUID NOT NULL,
    draft_id UUID NOT NULL,
    draft_revision_id UUID NOT NULL,
    revision_number INTEGER NOT NULL,
    recipient_ref UUID NOT NULL,
    sender_identity_id UUID NOT NULL,
    approval_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    intent_key VARCHAR(128) NOT NULL,
    provider_name VARCHAR(64) NOT NULL,
    account_reference VARCHAR(128) NOT NULL,
    payload_digest VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL,
    provider_ref VARCHAR(200),
    CONSTRAINT pk_delivery_messages PRIMARY KEY (id),
    CONSTRAINT uq_delivery_messages_workspace_id UNIQUE (workspace_id, id),
    CONSTRAINT uq_delivery_messages_intent UNIQUE (workspace_id, intent_key),
    CONSTRAINT uq_delivery_messages_operation UNIQUE (workspace_id, operation_id),
    CONSTRAINT uq_delivery_messages_provider_ref UNIQUE (provider_name, account_reference, provider_ref),
    CONSTRAINT fk_delivery_messages_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    CONSTRAINT fk_delivery_messages_project FOREIGN KEY(workspace_id, project_id) REFERENCES projects (workspace_id, id),
    CONSTRAINT fk_delivery_messages_draft FOREIGN KEY(workspace_id, draft_id) REFERENCES outreach_drafts (workspace_id, id),
    CONSTRAINT fk_delivery_messages_exact_revision FOREIGN KEY(workspace_id, draft_id, revision_number, draft_revision_id) REFERENCES draft_revisions (workspace_id, draft_id, revision_number, id),
    CONSTRAINT fk_delivery_messages_recipient FOREIGN KEY(workspace_id, recipient_ref) REFERENCES contact_points (workspace_id, id),
    CONSTRAINT fk_delivery_messages_sender FOREIGN KEY(workspace_id, project_id, sender_identity_id) REFERENCES sender_identity_versions (workspace_id, project_id, id),
    CONSTRAINT fk_delivery_messages_approval FOREIGN KEY(workspace_id, approval_id) REFERENCES approvals (workspace_id, id),
    CONSTRAINT fk_delivery_messages_operation FOREIGN KEY(workspace_id, operation_id) REFERENCES provider_operations (workspace_id, id),
    CONSTRAINT fk_delivery_messages_actor FOREIGN KEY(actor_id) REFERENCES users (id),
    CONSTRAINT ck_delivery_messages_state CHECK (state IN ('prepared','submitting','unknown','accepted','delivered','bounced','complained','unsubscribed','failed','rejected')),
    CONSTRAINT ck_delivery_messages_revision CHECK (revision_number>0),
    CONSTRAINT ck_delivery_messages_digest CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_delivery_messages_opaque CHECK (intent_key ~ '^[A-Za-z0-9:_/-]{1,128}$' AND provider_name ~ '^[A-Za-z0-9_-]{1,64}$' AND account_reference ~ '^[A-Za-z0-9:_/-]{1,128}$' AND (provider_ref IS NULL OR provider_ref ~ '^[A-Za-z0-9:_/-]{1,200}$'))
);

CREATE INDEX ix_delivery_messages_approval ON delivery_messages (workspace_id, approval_id);

CREATE INDEX ix_delivery_messages_recipient ON delivery_messages (workspace_id, recipient_ref);

CREATE INDEX ix_delivery_messages_actor ON delivery_messages (actor_id);

CREATE INDEX ix_delivery_messages_sender ON delivery_messages (workspace_id, project_id, sender_identity_id);

CREATE INDEX ix_delivery_messages_draft ON delivery_messages (workspace_id, draft_id, revision_number, draft_revision_id);

CREATE INDEX ix_delivery_messages_project ON delivery_messages (workspace_id, project_id);

CREATE TABLE delivery_events (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    message_id UUID NOT NULL,
    provider_name VARCHAR(64) NOT NULL,
    account_reference VARCHAR(128) NOT NULL,
    external_event_id VARCHAR(200) NOT NULL,
    provider_ref VARCHAR(200) NOT NULL,
    state VARCHAR(32) NOT NULL,
    body_digest VARCHAR(64) NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_delivery_events PRIMARY KEY (id),
    CONSTRAINT uq_delivery_events_workspace_id UNIQUE (workspace_id, id),
    CONSTRAINT uq_delivery_events_external UNIQUE (provider_name, account_reference, external_event_id),
    CONSTRAINT fk_delivery_events_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    CONSTRAINT fk_delivery_events_message FOREIGN KEY(workspace_id, message_id) REFERENCES delivery_messages (workspace_id, id),
    CONSTRAINT ck_delivery_events_state CHECK (state IN ('accepted','delivered','bounced','complained','unsubscribed','failed','rejected')),
    CONSTRAINT ck_delivery_events_digest CHECK (body_digest ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_delivery_events_opaque CHECK (provider_name ~ '^[A-Za-z0-9_-]{1,64}$' AND account_reference ~ '^[A-Za-z0-9:_/-]{1,128}$' AND external_event_id ~ '^[A-Za-z0-9:_/-]{1,200}$' AND provider_ref ~ '^[A-Za-z0-9:_/-]{1,200}$')
);

CREATE INDEX ix_delivery_events_message ON delivery_events (workspace_id, message_id);

CREATE TABLE delivery_liabilities (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    message_id UUID NOT NULL,
    operation_id UUID NOT NULL,
    reservation_id UUID NOT NULL,
    max_liability NUMERIC(18, 6) NOT NULL,
    currency VARCHAR(8) NOT NULL,
    pricing_version VARCHAR(64) NOT NULL,
    CONSTRAINT pk_delivery_liabilities PRIMARY KEY (id),
    CONSTRAINT uq_delivery_liabilities_workspace_id UNIQUE (workspace_id, id),
    CONSTRAINT uq_delivery_liabilities_message UNIQUE (workspace_id, message_id),
    CONSTRAINT uq_delivery_liabilities_reservation UNIQUE (workspace_id, reservation_id),
    CONSTRAINT fk_delivery_liabilities_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    CONSTRAINT fk_delivery_liabilities_message FOREIGN KEY(workspace_id, message_id) REFERENCES delivery_messages (workspace_id, id),
    CONSTRAINT fk_delivery_liabilities_operation FOREIGN KEY(workspace_id, operation_id) REFERENCES provider_operations (workspace_id, id),
    CONSTRAINT fk_delivery_liabilities_reservation FOREIGN KEY(workspace_id, reservation_id) REFERENCES budget_reservations (workspace_id, id),
    CONSTRAINT ck_delivery_liabilities_money CHECK (max_liability>=0 AND currency='USD'),
    CONSTRAINT ck_delivery_liabilities_pricing CHECK (pricing_version ~ '^[A-Za-z0-9:_/-]{1,64}$')
);

CREATE INDEX ix_delivery_liabilities_operation ON delivery_liabilities (workspace_id, operation_id);

CREATE INDEX ix_delivery_messages_workspace_id ON delivery_messages(workspace_id);

ALTER TABLE delivery_messages ENABLE ROW LEVEL SECURITY;

ALTER TABLE delivery_messages FORCE ROW LEVEL SECURITY;

CREATE POLICY delivery_messages_tenant ON delivery_messages USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);

REVOKE ALL ON delivery_messages FROM PUBLIC,buyeros_api,buyeros_worker;

GRANT SELECT,INSERT ON delivery_messages TO buyeros_api,buyeros_worker;

CREATE INDEX ix_delivery_events_workspace_id ON delivery_events(workspace_id);

ALTER TABLE delivery_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE delivery_events FORCE ROW LEVEL SECURITY;

CREATE POLICY delivery_events_tenant ON delivery_events USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);

REVOKE ALL ON delivery_events FROM PUBLIC,buyeros_api,buyeros_worker;

GRANT SELECT,INSERT ON delivery_events TO buyeros_api,buyeros_worker;

CREATE INDEX ix_delivery_liabilities_workspace_id ON delivery_liabilities(workspace_id);

ALTER TABLE delivery_liabilities ENABLE ROW LEVEL SECURITY;

ALTER TABLE delivery_liabilities FORCE ROW LEVEL SECURITY;

CREATE POLICY delivery_liabilities_tenant ON delivery_liabilities USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);

REVOKE ALL ON delivery_liabilities FROM PUBLIC,buyeros_api,buyeros_worker;

GRANT SELECT,INSERT ON delivery_liabilities TO buyeros_api,buyeros_worker;

GRANT UPDATE(state,provider_ref,updated_at) ON delivery_messages TO buyeros_api,buyeros_worker;

CREATE FUNCTION guard_delivery_message() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.state<>'prepared' OR NEW.provider_ref IS NOT NULL THEN
          RAISE EXCEPTION 'delivery starts prepared without provider acceptance' USING ERRCODE='23514';
        END IF;
        IF NOT EXISTS(SELECT 1 FROM public.approvals a JOIN public.outreach_drafts d ON d.workspace_id=a.workspace_id AND d.id=a.draft_id
          WHERE a.workspace_id=NEW.workspace_id AND a.id=NEW.approval_id AND a.draft_id=NEW.draft_id
          AND a.draft_revision_id=NEW.draft_revision_id AND a.revision_number=NEW.revision_number
          AND a.recipient_contact_id=NEW.recipient_ref AND a.context_snapshot#>>'{sender,id}'=NEW.sender_identity_id::text
          AND a.invalidated_reason IS NULL AND a.invalidated_at IS NULL AND a.approved_at IS NOT NULL
          AND d.project_id=NEW.project_id AND d.current_revision=NEW.revision_number AND d.state='approved')
        THEN RAISE EXCEPTION 'delivery requires exact current approval' USING ERRCODE='23514'; END IF;
        IF NOT EXISTS(SELECT 1 FROM public.provider_operations p WHERE p.workspace_id=NEW.workspace_id AND p.id=NEW.operation_id
          AND p.capability='delivery' AND p.intent_key=NEW.intent_key AND p.input_hash=NEW.payload_digest
          AND p.provider_name=NEW.provider_name AND p.account_reference=NEW.account_reference AND p.status='intent')
        THEN RAISE EXCEPTION 'delivery requires original operation binding' USING ERRCODE='23514'; END IF;
      ELSE
        IF (to_jsonb(NEW)-'state'-'provider_ref'-'updated_at') IS DISTINCT FROM (to_jsonb(OLD)-'state'-'provider_ref'-'updated_at')
          OR (OLD.provider_ref IS NOT NULL AND NEW.provider_ref IS DISTINCT FROM OLD.provider_ref)
        THEN RAISE EXCEPTION 'delivery original binding is immutable' USING ERRCODE='23514'; END IF;
        IF NEW.state IS DISTINCT FROM OLD.state AND NOT (CASE OLD.state
          WHEN 'prepared' THEN NEW.state IN ('submitting','rejected')
          WHEN 'submitting' THEN NEW.state IN ('unknown','accepted','delivered','bounced','complained','failed','rejected')
          WHEN 'unknown' THEN NEW.state IN ('accepted','delivered','bounced','complained','unsubscribed','failed')
          WHEN 'accepted' THEN NEW.state IN ('delivered','bounced','complained','unsubscribed','failed')
          WHEN 'delivered' THEN NEW.state IN ('bounced','complained','unsubscribed')
          WHEN 'bounced' THEN NEW.state IN ('complained','unsubscribed')
          WHEN 'complained' THEN NEW.state='unsubscribed' ELSE false END)
        THEN RAISE EXCEPTION 'delivery state cannot regress or resubmit' USING ERRCODE='23514'; END IF;
        IF NEW.state IN ('prepared','submitting','rejected') AND NEW.provider_ref IS NOT NULL
          OR NEW.state IN ('accepted','delivered','bounced','complained','unsubscribed') AND NEW.provider_ref IS NULL
        THEN RAISE EXCEPTION 'delivery acceptance requires original provider reference' USING ERRCODE='23514'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_message_guard BEFORE INSERT OR UPDATE ON delivery_messages FOR EACH ROW EXECUTE FUNCTION guard_delivery_message();
    REVOKE ALL ON FUNCTION guard_delivery_message() FROM PUBLIC,buyeros_api,buyeros_worker;

    CREATE FUNCTION guard_delivery_event() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.delivery_messages m WHERE m.workspace_id=NEW.workspace_id AND m.id=NEW.message_id
        AND m.provider_name=NEW.provider_name AND m.account_reference=NEW.account_reference AND m.provider_ref=NEW.provider_ref)
      THEN RAISE EXCEPTION 'delivery event requires original scoped provider reference' USING ERRCODE='23503'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_event_guard BEFORE INSERT ON delivery_events FOR EACH ROW EXECUTE FUNCTION guard_delivery_event();
    REVOKE ALL ON FUNCTION guard_delivery_event() FROM PUBLIC,buyeros_api,buyeros_worker;

    CREATE FUNCTION guard_delivery_liability() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      IF NOT EXISTS(SELECT 1 FROM public.delivery_messages m JOIN public.budget_reservations b
        ON b.workspace_id=m.workspace_id AND b.operation_id=m.operation_id WHERE m.workspace_id=NEW.workspace_id
        AND m.id=NEW.message_id AND m.operation_id=NEW.operation_id AND b.id=NEW.reservation_id
        AND b.upper_bound=NEW.max_liability AND b.currency=NEW.currency AND b.price_version=NEW.pricing_version)
      THEN RAISE EXCEPTION 'delivery liability requires exact reserved operation' USING ERRCODE='23503'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_liability_guard BEFORE INSERT ON delivery_liabilities FOR EACH ROW EXECUTE FUNCTION guard_delivery_liability();
    REVOKE ALL ON FUNCTION guard_delivery_liability() FROM PUBLIC,buyeros_api,buyeros_worker;;

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0048_c61_delivery_ledger' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0048_c61_delivery_ledger' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0048_c61_delivery_ledger' FROM public.alembic_version),false) $$;

UPDATE alembic_version SET version_num='0048_c61_delivery_ledger' WHERE alembic_version.version_num = '0047_c61_legacy_source_privacy';

-- Running upgrade 0048_c61_delivery_ledger -> 0049_c61_delivery_money

ALTER TABLE delivery_liabilities ALTER COLUMN max_liability TYPE NUMERIC(20, 6);

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0049_c61_delivery_money' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0049_c61_delivery_money' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0049_c61_delivery_money' FROM public.alembic_version),false) $$;

UPDATE alembic_version SET version_num='0049_c61_delivery_money' WHERE alembic_version.version_num = '0048_c61_delivery_ledger';

-- Running upgrade 0049_c61_delivery_money -> 0050_c61_delivery_authorizations

CREATE TABLE delivery_authorizations (
    id UUID NOT NULL,
    workspace_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    message_id UUID NOT NULL,
    outbox_id UUID NOT NULL,
    scope_hash VARCHAR(64) NOT NULL,
    scope_json TEXT NOT NULL,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_delivery_authorizations PRIMARY KEY (id),
    CONSTRAINT uq_delivery_authorizations_workspace_id UNIQUE (workspace_id, id),
    CONSTRAINT uq_delivery_authorizations_message UNIQUE (workspace_id, message_id),
    CONSTRAINT uq_delivery_authorizations_outbox UNIQUE (workspace_id, outbox_id),
    CONSTRAINT fk_delivery_authorizations_workspace FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
    CONSTRAINT fk_delivery_authorizations_message FOREIGN KEY(workspace_id, message_id) REFERENCES delivery_messages (workspace_id, id),
    CONSTRAINT fk_delivery_authorizations_outbox FOREIGN KEY(workspace_id, outbox_id) REFERENCES outbox_events (workspace_id, id),
    CONSTRAINT ck_delivery_authorizations_scope_digest CHECK (scope_hash ~ '^[0-9a-f]{64}$' AND octet_length(scope_json) BETWEEN 1 AND 524288 AND scope_hash=encode(sha256(convert_to(scope_json,'UTF8')),'hex'))
);

CREATE INDEX ix_delivery_authorizations_workspace_id ON delivery_authorizations (workspace_id);

ALTER TABLE delivery_authorizations ENABLE ROW LEVEL SECURITY;

ALTER TABLE delivery_authorizations FORCE ROW LEVEL SECURITY;

CREATE POLICY delivery_authorizations_tenant ON delivery_authorizations USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);

REVOKE ALL ON delivery_authorizations FROM PUBLIC,buyeros_api,buyeros_worker;

GRANT SELECT,INSERT ON delivery_authorizations TO buyeros_api,buyeros_worker;

CREATE FUNCTION guard_delivery_authorization() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    DECLARE scope jsonb; bound boolean;
    BEGIN
      IF TG_OP='UPDATE' THEN
        RAISE EXCEPTION 'original delivery authority is immutable' USING ERRCODE='23514';
      END IF;
      scope:=NEW.scope_json::jsonb;
      IF jsonb_typeof(scope) IS DISTINCT FROM 'object'
        OR (SELECT count(*) FROM json_each(NEW.scope_json::json))<>14
        OR (SELECT count(*) FROM jsonb_object_keys(scope))<>14
        OR scope-ARRAY['workspace_id','project_id','sender_identity_id','recipient_refs','provider_name','account_reference','pricing_version','upper_bound','currency','reviewed_contract_hash','selected','reviewed','sender_verified','valid_until']<>'{}'::jsonb
        OR jsonb_typeof(scope->'recipient_refs') IS DISTINCT FROM 'array'
        OR EXISTS(SELECT 1 FROM unnest(ARRAY['workspace_id','project_id','sender_identity_id','provider_name','account_reference','pricing_version','upper_bound','currency','reviewed_contract_hash','valid_until']) keys(key) WHERE jsonb_typeof(scope->key) IS DISTINCT FROM 'string')
      THEN RAISE EXCEPTION 'complete bounded delivery authority scope required' USING ERRCODE='23514'; END IF;
      IF jsonb_array_length(scope->'recipient_refs') NOT BETWEEN 1 AND 10000
        OR EXISTS(SELECT 1 FROM jsonb_array_elements(scope->'recipient_refs') x WHERE jsonb_typeof(x) IS DISTINCT FROM 'string')
        OR EXISTS(SELECT 1 FROM jsonb_array_elements_text(scope->'recipient_refs') x WHERE x!~'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' OR x='00000000-0000-0000-0000-000000000000')
        OR (SELECT count(*) FROM jsonb_array_elements_text(scope->'recipient_refs'))<>(SELECT count(DISTINCT x) FROM jsonb_array_elements_text(scope->'recipient_refs') x)
        OR scope->'selected' IS DISTINCT FROM 'true'::jsonb
        OR scope->'reviewed' IS DISTINCT FROM 'true'::jsonb
        OR scope->'sender_verified' IS DISTINCT FROM 'true'::jsonb
        OR scope->>'reviewed_contract_hash'!~'^[0-9a-f]{64}$'
        OR scope->>'upper_bound'!~'^[0-9]{1,14}\.[0-9]{6}$'
        OR scope->>'currency' IS DISTINCT FROM 'USD'
        OR scope->>'pricing_version' LIKE 'legacy-%%'
        OR NEW.valid_until IS DISTINCT FROM (scope->>'valid_until')::timestamptz
        OR NEW.valid_until<=clock_timestamp()
      THEN RAISE EXCEPTION 'selected reviewed current delivery authority required' USING ERRCODE='23514'; END IF;
      SELECT EXISTS(
        SELECT 1 FROM public.delivery_messages m
        JOIN public.provider_operations p ON p.workspace_id=m.workspace_id AND p.id=m.operation_id
        JOIN public.delivery_liabilities l ON l.workspace_id=m.workspace_id AND l.message_id=m.id AND l.operation_id=p.id
        JOIN public.budget_reservations b ON b.workspace_id=l.workspace_id AND b.id=l.reservation_id AND b.operation_id=p.id
        JOIN public.outbox_events o ON o.workspace_id=m.workspace_id AND o.id=NEW.outbox_id
        WHERE m.workspace_id=NEW.workspace_id AND m.id=NEW.message_id
          AND m.state='prepared' AND m.provider_ref IS NULL AND p.status='intent'
          AND p.capability='delivery' AND p.intent_key=m.intent_key AND p.input_hash=m.payload_digest
          AND p.provider_name=m.provider_name AND p.account_reference=m.account_reference
          AND o.event_type='delivery.submit' AND o.state='ready' AND o.intent_key=m.intent_key
          AND o.payload=jsonb_build_object('workspace_id',m.workspace_id::text,'message_id',m.id::text,'operation_id',p.id::text,'scope_hash',NEW.scope_hash)
          AND scope->>'workspace_id'=m.workspace_id::text AND scope->>'project_id'=m.project_id::text
          AND scope->>'sender_identity_id'=m.sender_identity_id::text
          AND scope->'recipient_refs' @> jsonb_build_array(m.recipient_ref::text)
          AND scope->>'provider_name'=m.provider_name AND scope->>'account_reference'=m.account_reference
          AND (scope->>'upper_bound')::numeric=l.max_liability AND l.max_liability>0
          AND scope->>'currency'=l.currency AND scope->>'pricing_version'=l.pricing_version
          AND b.state='active' AND b.upper_bound=l.max_liability AND b.remaining_hold=b.upper_bound
          AND b.currency=l.currency AND b.price_version=l.pricing_version
          AND (SELECT count(*) FROM public.budget_reservation_allocations x WHERE x.workspace_id=b.workspace_id AND x.reservation_id=b.id)=3
          AND NOT EXISTS(SELECT 1 FROM public.budget_reservation_allocations x
            JOIN public.budget_accounts a ON a.workspace_id=x.workspace_id AND a.id=x.account_id
            WHERE x.workspace_id=b.workspace_id AND x.reservation_id=b.id
              AND NOT ((a.scope='workspace' AND a.scope_id=m.workspace_id AND a.category='all')
                OR (a.scope='project' AND a.scope_id=m.project_id AND a.category='all')
                OR (a.scope='category' AND a.scope_id=m.project_id AND a.category='delivery')))
      ) INTO bound;
      IF NOT bound THEN RAISE EXCEPTION 'delivery authority requires exact original message liability and paid outbox' USING ERRCODE='23503'; END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER delivery_authorization_guard BEFORE INSERT OR UPDATE ON delivery_authorizations FOR EACH ROW EXECUTE FUNCTION guard_delivery_authorization();
    REVOKE ALL ON FUNCTION guard_delivery_authorization() FROM PUBLIC,buyeros_api,buyeros_worker;;

CREATE OR REPLACE FUNCTION public.buyeros_search_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0050_c61_delivery_authorizations' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_model_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0050_c61_delivery_authorizations' FROM public.alembic_version),false) $$;

CREATE OR REPLACE FUNCTION public.buyeros_contact_receipts_writable() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='0050_c61_delivery_authorizations' FROM public.alembic_version),false) $$;

UPDATE alembic_version SET version_num='0050_c61_delivery_authorizations' WHERE alembic_version.version_num = '0049_c61_delivery_money';

COMMIT;
