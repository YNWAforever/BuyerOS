"""Private workspace threads; no seeded data or worker privileges.

Hard delete is owner-controlled in the API. Downgrade refuses populated tables.
"""
from alembic import op
import sqlalchemy as sa

revision = '0058_conversation_threads'
down_revision = '0057_conversation_model'
branch_labels = depends_on = None
TABLES = ('conversation_threads', 'conversation_thread_messages', 'conversation_thread_shares')


def _fences(head):
    for service in ('search', 'model', 'contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
            "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
            f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    # A CHECK helper keeps the JSONB data class bounded even for direct SQL writes.
    op.execute("""
    CREATE FUNCTION public.buyeros_thread_refs_valid(items jsonb, kind text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
    DECLARE item jsonb; seen text[] := '{}'; ident text; label text;
    BEGIN
      IF jsonb_typeof(items)<>'array' THEN RETURN false; END IF;
      IF jsonb_array_length(items)>100 THEN RETURN false; END IF;
      FOR item IN SELECT value FROM jsonb_array_elements(items) LOOP
        IF jsonb_typeof(item)<>'object' THEN RETURN false; END IF;
        ident := item->>'id'; label := item->>'label';
        IF ident IS NULL OR label IS NULL OR jsonb_typeof(item->'id')<>'string'
          OR jsonb_typeof(item->'label')<>'string' OR ident=ANY(seen) THEN RETURN false; END IF;
        seen := array_append(seen,ident);
        IF kind='sources' THEN
          IF item - 'id' - 'label' <> '{}'::jsonb OR length(ident)>200
            OR ident !~ '^(document|fact|run|results):[A-Za-z0-9][A-Za-z0-9._:-]*$'
            OR NOT (CASE split_part(ident,':',1)
              WHEN 'document' THEN label='Offer document'
              WHEN 'fact' THEN label IN ('Offer fact','Approved offer fact','Candidate offer fact')
              WHEN 'run' THEN label='Research run' WHEN 'results' THEN label='Results summary' ELSE false END)
            THEN RETURN false; END IF;
        ELSIF kind='runs' THEN
          IF item - 'id' - 'label' - 'status' <> '{}'::jsonb
            OR ident !~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
            OR label<>'Research run' OR NOT item ? 'status' OR jsonb_typeof(item->'status')<>'string'
            OR item->>'status' NOT IN ('draft','queued','running','partial','paused_budget','cancel_requested','cancelled','failed','completed','awaiting_reconciliation')
            THEN RETURN false; END IF;
        ELSE RETURN false; END IF;
      END LOOP;
      RETURN true;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_thread_refs_valid(jsonb,text) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.buyeros_thread_refs_valid(jsonb,text) TO buyeros_api;

    CREATE TABLE conversation_threads (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL,
      owner_user_id uuid NOT NULL REFERENCES users(id), template_id varchar(40) NOT NULL,
      title varchar(80) NOT NULL CHECK(length(btrim(title))>0), version integer NOT NULL DEFAULT 1 CHECK(version>0),
      sources jsonb NOT NULL DEFAULT '[]' CHECK(public.buyeros_thread_refs_valid(sources,'sources')),
      runs jsonb NOT NULL DEFAULT '[]' CHECK(public.buyeros_thread_refs_valid(runs,'runs')),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,project_id,id,owner_user_id),
      FOREIGN KEY(workspace_id,project_id) REFERENCES projects(workspace_id,id),
      CHECK(template_id IN ('first-project','understand-documents','research-market','review-buyers','check-company','prepare-follow-up','custom'))
    );
    CREATE INDEX ix_conversation_threads_owner ON conversation_threads(workspace_id,project_id,owner_user_id,updated_at DESC,id);
    CREATE TABLE conversation_thread_messages (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL,
      owner_user_id uuid NOT NULL REFERENCES users(id), author_user_id uuid NOT NULL REFERENCES users(id),
      text text NOT NULL CHECK(length(text) BETWEEN 1 AND 4000 AND text ~ '[^[:space:]]'),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id),
      FOREIGN KEY(workspace_id,project_id,thread_id,owner_user_id)
        REFERENCES conversation_threads(workspace_id,project_id,id,owner_user_id) ON DELETE CASCADE
    );
    CREATE INDEX ix_conversation_thread_messages_thread ON conversation_thread_messages(workspace_id,thread_id,created_at,id);
    CREATE TABLE conversation_thread_shares (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL,
      owner_user_id uuid NOT NULL REFERENCES users(id), grantee_user_id uuid NOT NULL REFERENCES users(id),
      granted_by uuid NOT NULL REFERENCES users(id), role varchar(6) NOT NULL CHECK(role IN ('viewer','editor')),
      version integer NOT NULL DEFAULT 1 CHECK(version>0),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,thread_id,grantee_user_id),
      CHECK(grantee_user_id<>owner_user_id AND granted_by=owner_user_id),
      FOREIGN KEY(workspace_id,project_id,thread_id,owner_user_id)
        REFERENCES conversation_threads(workspace_id,project_id,id,owner_user_id) ON DELETE CASCADE
    );
    CREATE INDEX ix_conversation_thread_shares_grantee ON conversation_thread_shares(workspace_id,grantee_user_id,thread_id);
    """)
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker')
    op.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON conversation_threads,conversation_thread_shares TO buyeros_api')
    op.execute('GRANT SELECT,INSERT ON conversation_thread_messages TO buyeros_api')
    _fences(revision)


def downgrade():
    # The owner may also be subject to FORCE RLS. This transactional change is
    # rolled back with the refusal, so no partial weakening survives failure.
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    for table in TABLES:
        if op.get_bind().execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one():
            raise RuntimeError('0058 downgrade blocked: preserve populated conversation threads')
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE {table}')
    op.execute('DROP FUNCTION public.buyeros_thread_refs_valid(jsonb,text)')
    _fences(down_revision)
