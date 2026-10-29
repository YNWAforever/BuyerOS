"""Google Drive authorization metadata; no content, filenames, or credentials."""
from alembic import op
import sqlalchemy as sa

revision = '0059_conversation_connections'
down_revision = '0058_conversation_threads'
branch_labels = depends_on = None


def _fences(head):
    for service in ('search', 'model', 'contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
            "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
            f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_thread_refs_valid(items jsonb, kind text) RETURNS boolean
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
            OR ident !~ '^(document|fact|run|results|drive):[A-Za-z0-9][A-Za-z0-9._:-]*$'
            OR NOT (CASE split_part(ident,':',1)
              WHEN 'drive' THEN label='Google Drive item' AND ident ~ '^drive:[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}:[A-Za-z0-9_-]{1,128}$'
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


    CREATE FUNCTION public.buyeros_drive_folders_valid(items jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
    DECLARE item jsonb; seen text[] := '{}';
    BEGIN
      IF jsonb_typeof(items)<>'array' OR jsonb_array_length(items)>20 THEN RETURN false; END IF;
      FOR item IN SELECT value FROM jsonb_array_elements(items) LOOP
        IF jsonb_typeof(item)<>'object' OR item - 'id' - 'label'<>'{}'::jsonb
          OR NOT item ?& ARRAY['id','label'] OR jsonb_typeof(item->'id')<>'string'
          OR jsonb_typeof(item->'label')<>'string' OR item->>'id' !~ '^[A-Za-z0-9_-]{1,128}$'
          OR item->>'label'<>'Google Drive folder' OR item->>'id'=ANY(seen) THEN RETURN false; END IF;
        seen := array_append(seen,item->>'id');
      END LOOP;
      RETURN true;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_drive_folders_valid(jsonb) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.buyeros_drive_folders_valid(jsonb) TO buyeros_api;
    CREATE TABLE conversation_drive_connections (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL,
      configured_by uuid NOT NULL REFERENCES users(id), connected boolean NOT NULL DEFAULT false,
      version integer NOT NULL DEFAULT 1 CHECK(version>0), generation uuid NOT NULL,
      folders jsonb NOT NULL DEFAULT '[]' CHECK(public.buyeros_drive_folders_valid(folders)),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,project_id),
      FOREIGN KEY(workspace_id,project_id) REFERENCES projects(workspace_id,id),
      CHECK(connected OR folders='[]'::jsonb)
    );
    ALTER TABLE conversation_drive_connections ENABLE ROW LEVEL SECURITY;
    ALTER TABLE conversation_drive_connections FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON conversation_drive_connections
      USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)
      WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);
    REVOKE ALL ON conversation_drive_connections FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT,UPDATE,DELETE ON conversation_drive_connections TO buyeros_api;
    """)
    _fences(revision)


def downgrade():
    op.execute('ALTER TABLE conversation_drive_connections NO FORCE ROW LEVEL SECURITY')
    db=op.get_bind()
    if (db.execute(sa.text('SELECT EXISTS(SELECT 1 FROM conversation_drive_connections)')).scalar_one()
        or db.execute(sa.text("SELECT EXISTS(SELECT 1 FROM conversation_threads t, jsonb_array_elements(t.sources) s WHERE s->>'id' LIKE 'drive:%')")).scalar_one()):
        raise RuntimeError('0059 downgrade blocked: preserve populated Drive connections/references')
    op.execute('DROP TABLE conversation_drive_connections')
    op.execute('DROP FUNCTION public.buyeros_drive_folders_valid(jsonb)')
    # Restore the historical validator after proving no Drive references remain.
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_thread_refs_valid(items jsonb, kind text) RETURNS boolean
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

    """)
    _fences(down_revision)
