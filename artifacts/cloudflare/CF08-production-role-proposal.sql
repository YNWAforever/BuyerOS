-- PROPOSED ONLY. Exact target neondb; apply only after separate production approval.
-- No password in this artifact. Assign it privately and enable LOGIN only at the approved probe phase.
BEGIN;
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='buyeros_cf_runtime') THEN
        RAISE EXCEPTION 'Role exists; inspect rather than overwrite';
    END IF;
END $$;
CREATE ROLE buyeros_cf_runtime NOLOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT buyeros_worker TO buyeros_cf_runtime;
GRANT CONNECT ON DATABASE neondb TO buyeros_cf_runtime;
COMMIT;
