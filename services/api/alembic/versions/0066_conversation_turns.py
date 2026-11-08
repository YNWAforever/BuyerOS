"""Bounded conversation turns, typed message parts and inline proposals.

Additive only: legacy notes migrate to ``role='user'`` with a monotonic ``seq``;
parts/decision rows live under the discussion's deletion boundary. No worker
grants and no seeded data.

App-rollback compatibility: the previous application revision inserts messages
with only ``(…, text)``. A BEFORE INSERT trigger supplies the monotonic ``seq``
(and the ``role``/``parts`` defaults) for those inserts, so a rollback to the
previous code keeps writing. Downgrade refuses when any assistant turn, typed
part, client message id or turn id exists; for legacy-only data the added
columns are dropped and ordering falls back to ``created_at, id`` (the text and
note semantics are unchanged).
"""
from pathlib import Path
from runpy import run_path

from alembic import op
import sqlalchemy as sa

revision = '0066_conversation_turns'
down_revision = '0065_sales_lifecycle'
branch_labels = depends_on = None
TABLES = ('conversation_turns', 'conversation_turn_proposals', 'conversation_turn_decisions')
MESSAGE_CONSTRAINTS = (
    'ck_conversation_thread_messages_role',
    'ck_conversation_thread_messages_parts',
    'ck_conversation_thread_messages_seq',
    'uq_conversation_thread_messages_workspace_id_thread_id_seq',
    'fk_conversation_thread_messages_turn',
)
UUID_RE = "'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'"


def fences():
    """Re-point every readiness fence at this revision (single migration head)."""
    prior = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    prior['fences'](revision)
    tables = (prior['TABLES']
        + run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']
        + ('xverum_enrichments',)
        + run_path(str(Path(__file__).with_name('0065_sales_lifecycle.py')))['TABLES']
        + TABLES)
    checks = ''.join(f" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.{table}') "
        "AND relrowsecurity AND relforcerowsecurity)" for table in tables)
    op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
        f"$$ SELECT COALESCE((SELECT version_num='{revision}' FROM public.alembic_version),false){checks} $$")


def upgrade():
    op.execute(f"""
    CREATE FUNCTION public.buyeros_turn_parts_valid(items jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
    DECLARE item jsonb; sub jsonb; kind text; keys text[];
    BEGIN
      IF jsonb_typeof(items)<>'array' OR jsonb_array_length(items)>24 THEN RETURN false; END IF;
      FOR item IN SELECT value FROM jsonb_array_elements(items) LOOP
        IF jsonb_typeof(item)<>'object' OR octet_length(item::text)>16384 THEN RETURN false; END IF;
        kind := item->>'kind';
        keys := CASE kind
          WHEN 'text' THEN ARRAY['kind','text','language']
          WHEN 'citations' THEN ARRAY['kind','items']
          WHEN 'tool_activity' THEN ARRAY['kind','call_id','capability','title','state','started_at','finished_at','summary','error_code']
          WHEN 'proposal' THEN ARRAY['kind','proposal_id','capability','title','rationale','arguments_preview','cost','requires_approval']
          WHEN 'output_link' THEN ARRAY['kind','output','title','href']
          WHEN 'notice' THEN ARRAY['kind','code','message','recovery']
          ELSE NULL END;
        IF keys IS NULL OR NOT item ?& keys OR item - keys <> '{{}}'::jsonb THEN RETURN false; END IF;
        IF kind='text' THEN
          IF jsonb_typeof(item->'text')<>'string' OR length(item->>'text') NOT BETWEEN 1 AND 4000
            OR item->>'language' NOT IN ('en','zh-HK') THEN RETURN false; END IF;
        ELSIF kind='citations' THEN
          IF jsonb_typeof(item->'items')<>'array'
            OR jsonb_array_length(item->'items') NOT BETWEEN 1 AND 20 THEN RETURN false; END IF;
          FOR sub IN SELECT value FROM jsonb_array_elements(item->'items') LOOP
            IF jsonb_typeof(sub)<>'object' OR NOT sub ?& ARRAY['id','label','kind']
              OR sub - ARRAY['id','label','kind','href'] <> '{{}}'::jsonb
              OR jsonb_typeof(sub->'id')<>'string' OR length(sub->>'id') NOT BETWEEN 1 AND 200
              OR jsonb_typeof(sub->'label')<>'string' OR length(sub->>'label') NOT BETWEEN 1 AND 120
              OR sub->>'kind' NOT IN ('document','fact','drive','run','results') THEN RETURN false; END IF;
          END LOOP;
        ELSIF kind='tool_activity' THEN
          IF (item->>'call_id') !~ {UUID_RE}
            OR item->>'state' NOT IN ('proposed','approved','running','completed','failed','skipped','outcome_unknown')
            OR item->>'capability' !~ '^[a-z][a-z0-9_.]{{2,63}}$'
            OR jsonb_typeof(item->'title')<>'string' OR length(item->>'title') NOT BETWEEN 1 AND 240
            OR jsonb_typeof(item->'started_at')<>'string' THEN RETURN false; END IF;
          IF jsonb_typeof(item->'finished_at') NOT IN ('string','null') THEN RETURN false; END IF;
          IF item ? 'summary' AND item->'summary' <> 'null'::jsonb
            AND (jsonb_typeof(item->'summary')<>'string' OR length(item->>'summary')>500) THEN RETURN false; END IF;
          IF item ? 'error_code' AND item->'error_code' <> 'null'::jsonb
            AND (jsonb_typeof(item->'error_code')<>'string' OR length(item->>'error_code')>64) THEN RETURN false; END IF;
        ELSIF kind='proposal' THEN
          IF (item->>'proposal_id') !~ {UUID_RE} OR item->>'requires_approval' <> 'true'
            OR item->>'capability' !~ '^[a-z][a-z0-9_.]{{2,63}}$'
            OR jsonb_typeof(item->'title')<>'string' OR length(item->>'title') NOT BETWEEN 1 AND 240
            OR jsonb_typeof(item->'rationale')<>'string' OR length(item->>'rationale') NOT BETWEEN 1 AND 1000
            OR jsonb_typeof(item->'arguments_preview')<>'object'
            OR octet_length((item->'arguments_preview')::text)>4096 THEN RETURN false; END IF;
          IF item ? 'cost' AND item->'cost' <> 'null'::jsonb THEN
            sub := item->'cost';
            IF jsonb_typeof(sub)<>'object'
              OR NOT sub ?& ARRAY['kind','amount','unit','may_incur_provider_charges']
              OR sub - ARRAY['kind','amount','unit','may_incur_provider_charges'] <> '{{}}'::jsonb
              OR sub->>'kind' NOT IN ('nonbillable','provider_credits')
              OR sub->>'unit' NOT IN ('USD','credits')
              OR jsonb_typeof(sub->'may_incur_provider_charges')<>'boolean' THEN RETURN false; END IF;
          END IF;
        ELSIF kind='output_link' THEN
          sub := item->'output';
          IF jsonb_typeof(sub)<>'object' OR NOT sub ?& ARRAY['output_id','kind','revision','status']
            OR sub - ARRAY['output_id','kind','revision','status'] <> '{{}}'::jsonb
            OR (sub->>'output_id') !~ {UUID_RE} OR jsonb_typeof(sub->'revision')<>'number'
            OR (sub->>'revision') !~ '^[1-9][0-9]*$'
            OR sub->>'status' NOT IN ('available','needs_review','unavailable')
            OR sub->>'kind' NOT IN ('profile_proposal','research_report','qualification_assessment',
              'enrichment_proposal','competitive_document','outreach_preparation','followup_preparation',
              'meeting_brief','sales_proposal','objection_playbook','pipeline_report','report_export',
              'project_setup','document_understanding','buyer_review') THEN RETURN false; END IF;
          IF jsonb_typeof(item->'title')<>'string' OR length(item->>'title') NOT BETWEEN 1 AND 240
            OR jsonb_typeof(item->'href') NOT IN ('string','null') THEN RETURN false; END IF;
        ELSE
          IF (item->>'code') !~ '^[A-Z][A-Z0-9_]{{2,63}}$'
            OR jsonb_typeof(item->'message')<>'string'
            OR length(item->>'message') NOT BETWEEN 1 AND 500 THEN RETURN false; END IF;
          IF item ? 'recovery' AND item->'recovery' <> 'null'::jsonb THEN
            sub := item->'recovery';
            IF jsonb_typeof(sub)<>'object' OR NOT sub ?& ARRAY['label']
              OR sub - ARRAY['label','href'] <> '{{}}'::jsonb
              OR jsonb_typeof(sub->'label')<>'string'
              OR length(sub->>'label') NOT BETWEEN 1 AND 240
              OR jsonb_typeof(sub->'href') NOT IN ('string','null') THEN RETURN false; END IF;
          END IF;
        END IF;
      END LOOP;
      RETURN true;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_turn_parts_valid(jsonb) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.buyeros_turn_parts_valid(jsonb) TO buyeros_api;

    CREATE FUNCTION public.buyeros_turn_notices_valid(items jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
    DECLARE item jsonb; sub jsonb;
    BEGIN
      IF jsonb_typeof(items)<>'array' OR jsonb_array_length(items)>8 THEN RETURN false; END IF;
      FOR item IN SELECT value FROM jsonb_array_elements(items) LOOP
        IF jsonb_typeof(item)<>'object' OR NOT item ?& ARRAY['code','message']
          OR item - ARRAY['code','message','recovery'] <> '{{}}'::jsonb
          OR (item->>'code') !~ '^[A-Z][A-Z0-9_]{{2,63}}$'
          OR jsonb_typeof(item->'message')<>'string'
          OR length(item->>'message') NOT BETWEEN 1 AND 500 THEN RETURN false; END IF;
        IF item ? 'recovery' AND item->'recovery' <> 'null'::jsonb THEN
          sub := item->'recovery';
          IF jsonb_typeof(sub)<>'object' OR NOT sub ?& ARRAY['label']
            OR sub - ARRAY['label','href'] <> '{{}}'::jsonb
            OR jsonb_typeof(sub->'label')<>'string'
            OR length(sub->>'label') NOT BETWEEN 1 AND 240
            OR jsonb_typeof(sub->'href') NOT IN ('string','null') THEN RETURN false; END IF;
        END IF;
      END LOOP;
      RETURN true;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_turn_notices_valid(jsonb) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.buyeros_turn_notices_valid(jsonb) TO buyeros_api;

    ALTER TABLE conversation_thread_messages
      ADD COLUMN role varchar(16) NOT NULL DEFAULT 'user',
      ADD COLUMN seq integer,
      ADD COLUMN client_message_id uuid,
      ADD COLUMN turn_id uuid,
      ADD COLUMN parts jsonb NOT NULL DEFAULT '[]'::jsonb;
    UPDATE conversation_thread_messages AS message SET seq = ranked.seq_no
      FROM (SELECT id, row_number() OVER (PARTITION BY workspace_id, thread_id
        ORDER BY created_at, id) AS seq_no FROM conversation_thread_messages) AS ranked
      WHERE message.id = ranked.id;
    ALTER TABLE conversation_thread_messages ALTER COLUMN seq SET NOT NULL;
    ALTER TABLE conversation_thread_messages
      ADD CONSTRAINT ck_conversation_thread_messages_seq CHECK(seq>0),
      ADD CONSTRAINT ck_conversation_thread_messages_role CHECK(role IN ('user','assistant')),
      ADD CONSTRAINT ck_conversation_thread_messages_parts CHECK(
        (role='user' AND parts='[]'::jsonb) OR
        (role='assistant' AND public.buyeros_turn_parts_valid(parts) IS TRUE)),
      ADD CONSTRAINT uq_conversation_thread_messages_workspace_id_thread_id_seq
        UNIQUE(workspace_id,thread_id,seq);
    CREATE UNIQUE INDEX uq_conversation_thread_messages_client
      ON conversation_thread_messages(workspace_id,thread_id,client_message_id)
      WHERE client_message_id IS NOT NULL;

    CREATE TABLE conversation_turns (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL,
      owner_user_id uuid NOT NULL REFERENCES users(id), actor_id uuid NOT NULL REFERENCES users(id),
      client_message_id uuid,
      request_fingerprint varchar(64) NOT NULL CHECK(request_fingerprint ~ '^[a-f0-9]{{64}}$'),
      parent_turn_id uuid, language varchar(8) NOT NULL CHECK(language IN ('en','zh-HK')),
      skill_id varchar(240), skill_version varchar(240),
      status varchar(24) NOT NULL CHECK(status IN ('completed','needs_input','needs_approval',
        'failed','outcome_unknown','cancelled')),
      step_count integer NOT NULL DEFAULT 0 CHECK(step_count BETWEEN 0 AND 3),
      expected_thread_version integer CHECK(expected_thread_version>0),
      parts jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(public.buyeros_turn_parts_valid(parts) IS TRUE),
      notices jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(public.buyeros_turn_notices_valid(notices) IS TRUE),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,project_id,thread_id,id),
      UNIQUE(workspace_id,thread_id,client_message_id),
      FOREIGN KEY(workspace_id,project_id,thread_id,owner_user_id)
        REFERENCES conversation_threads(workspace_id,project_id,id,owner_user_id) ON DELETE CASCADE,
      FOREIGN KEY(workspace_id,project_id,thread_id,parent_turn_id)
        REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );
    CREATE UNIQUE INDEX uq_conversation_turns_actor_client
      ON conversation_turns(workspace_id,actor_id,client_message_id)
      WHERE client_message_id IS NOT NULL;
    CREATE INDEX ix_conversation_turns_thread
      ON conversation_turns(workspace_id,thread_id,created_at,id);

    CREATE TABLE conversation_turn_proposals (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL,
      thread_id uuid NOT NULL, turn_id uuid NOT NULL,
      actor_id uuid NOT NULL REFERENCES users(id),
      capability varchar(64) NOT NULL CHECK(capability IN ('documents.read','research.read')),
      skill_id varchar(240) NOT NULL, skill_version varchar(240) NOT NULL,
      title varchar(240) NOT NULL CHECK(length(btrim(title))>0),
      rationale varchar(1000) NOT NULL CHECK(length(btrim(rationale))>0),
      arguments jsonb NOT NULL CHECK(jsonb_typeof(arguments)='object' AND octet_length(arguments::text)<=131072),
      source_refs jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(source_refs)='array'
        AND jsonb_array_length(source_refs)<=20 AND octet_length(source_refs::text)<=16384),
      arguments_preview jsonb NOT NULL CHECK(jsonb_typeof(arguments_preview)='object'
        AND octet_length(arguments_preview::text)<=4096),
      cost jsonb CHECK(cost IS NULL OR (jsonb_typeof(cost)='object' AND octet_length(cost::text)<=1024)),
      requires_approval boolean NOT NULL DEFAULT true,
      status varchar(24) NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved',
        'rejected','executed','failed','outcome_unknown','cancelled')),
      revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
      result jsonb CHECK(result IS NULL OR (jsonb_typeof(result)='object' AND octet_length(result::text)<=4096)),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CHECK(requires_approval),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,project_id,thread_id,turn_id,id),
      FOREIGN KEY(workspace_id,project_id,thread_id,turn_id)
        REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );

    CREATE TABLE conversation_turn_decisions (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL,
      thread_id uuid NOT NULL, turn_id uuid NOT NULL, proposal_id uuid NOT NULL,
      actor_id uuid NOT NULL REFERENCES users(id),
      decision varchar(8) NOT NULL CHECK(decision IN ('approve','reject')),
      request_fingerprint varchar(64) NOT NULL CHECK(request_fingerprint ~ '^[a-f0-9]{{64}}$'),
      continuation_turn_id uuid NOT NULL,
      status varchar(16) NOT NULL DEFAULT 'applied' CHECK(status IN ('applied','failed')),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,proposal_id),
      UNIQUE(workspace_id,project_id,thread_id,id),
      FOREIGN KEY(workspace_id,proposal_id)
        REFERENCES conversation_turn_proposals(workspace_id,id) ON DELETE CASCADE,
      FOREIGN KEY(workspace_id,project_id,thread_id,turn_id)
        REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE,
      FOREIGN KEY(workspace_id,project_id,thread_id,continuation_turn_id)
        REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );
    ALTER TABLE conversation_thread_messages
      ADD CONSTRAINT fk_conversation_thread_messages_turn
      FOREIGN KEY(workspace_id,project_id,thread_id,turn_id)
      REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE;

    -- Previous-app-revision inserts provide no seq/role/parts. Allocate the
    -- per-thread monotonic sequence inside the database so a code rollback
    -- remains writable; the current revision always supplies seq explicitly.
    CREATE FUNCTION public.buyeros_thread_message_seq() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      IF NEW.seq IS NULL OR NEW.seq<=0 THEN
        SELECT COALESCE(MAX(m.seq),0)+1 INTO NEW.seq
          FROM public.conversation_thread_messages m
          WHERE m.workspace_id=NEW.workspace_id AND m.thread_id=NEW.thread_id;
      END IF;
      RETURN NEW;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_thread_message_seq() FROM PUBLIC,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_thread_message_seq() TO buyeros_api;
    CREATE TRIGGER conversation_thread_message_seq BEFORE INSERT ON conversation_thread_messages
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_thread_message_seq();
    """)
    for table in TABLES:
        op.execute(f'''ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
          ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
          CREATE POLICY tenant_isolation ON {table}
          USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)
          WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);
          REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker;
          GRANT SELECT,INSERT ON {table} TO buyeros_api;''')
    op.execute('GRANT UPDATE(status,revision,result,updated_at) ON conversation_turn_proposals TO buyeros_api')
    fences()


def downgrade():
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    db = op.get_bind()
    if any(db.execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one() for table in TABLES):
        raise RuntimeError('0066 downgrade blocked: preserve populated conversation turns/decisions')
    typed = db.execute(sa.text("SELECT EXISTS(SELECT 1 FROM conversation_thread_messages "
        "WHERE role<>'user' OR parts<>'[]'::jsonb OR client_message_id IS NOT NULL "
        "OR turn_id IS NOT NULL)")).scalar_one()
    if typed:
        raise RuntimeError('0066 downgrade blocked: preserve assistant turns and typed message parts')
    op.execute('DROP TRIGGER conversation_thread_message_seq ON conversation_thread_messages')
    op.execute('DROP FUNCTION public.buyeros_thread_message_seq()')
    op.execute('ALTER TABLE conversation_thread_messages DROP CONSTRAINT fk_conversation_thread_messages_turn')
    op.execute('DROP INDEX uq_conversation_thread_messages_client')
    for constraint in MESSAGE_CONSTRAINTS[1:4]:
        op.execute(f'ALTER TABLE conversation_thread_messages DROP CONSTRAINT {constraint}')
    for column in ('parts', 'turn_id', 'client_message_id', 'role', 'seq'):
        op.execute(f'ALTER TABLE conversation_thread_messages DROP COLUMN {column}')
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE {table}')
    op.execute('DROP FUNCTION public.buyeros_turn_notices_valid(jsonb)')
    op.execute('DROP FUNCTION public.buyeros_turn_parts_valid(jsonb)')
    previous = run_path(str(Path(__file__).with_name('0065_sales_lifecycle.py')))
    previous['fences']()
