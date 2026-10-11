"""Add exact principal mappings; preserve canonical users, history and existing RLS."""
from alembic import op
revision='0039_c61_user_identities'
down_revision='0038_c61_workspace_directory'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""
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
    END $verify$;
    """)
    # Legacy insertion creates one new canonical user, never links by email.
    # Refuse creation if this exact alias is already bound to another UUID.
    op.execute("""
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
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_identity_immutable();
    """)

def downgrade():
    # Route/verifier rollback uses legacy User columns. Keep additive mappings,
    # revoked identities and Neon-only users; never delete history for rollback.
    pass
