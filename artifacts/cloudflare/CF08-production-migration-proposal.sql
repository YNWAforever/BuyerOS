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

COMMIT;
