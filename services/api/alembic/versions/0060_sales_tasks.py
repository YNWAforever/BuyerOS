"""Durable discussion task identity, events, dependencies and actor preferences."""
from alembic import op
import sqlalchemy as sa

revision = '0060_sales_tasks'
down_revision = '0059_conversation_connections'
branch_labels = depends_on = None
TABLES = ('sales_tasks','sales_task_events','sales_task_dependencies','conversation_thread_preferences','sales_reviews','sales_executions','sales_steps')


def _fences(head):
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
            "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
            f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    op.execute("""
    CREATE FUNCTION public.buyeros_sales_event_valid(kind text, payload jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
    DECLARE keys text[]; number_key text;
    BEGIN
      IF jsonb_typeof(payload)<>'object' THEN RETURN false; END IF;
      keys := CASE kind WHEN 'state' THEN ARRAY['state','revision']
        WHEN 'progress' THEN ARRAY['step_id','completed_steps','total_steps']
        WHEN 'output' THEN ARRAY['output_id','revision'] WHEN 'review' THEN ARRAY['id','kind','revision']
        WHEN 'error' THEN ARRAY['code','retryable'] ELSE NULL END;
      IF keys IS NULL OR NOT payload ?& keys OR payload - keys <> '{}'::jsonb THEN RETURN false; END IF;
      IF kind IN ('state','output','review') AND
        (jsonb_typeof(payload->'revision')<>'number' OR payload->>'revision' !~ '^[1-9][0-9]*$') THEN RETURN false; END IF;
      IF kind='state' THEN
        RETURN payload->>'state' IN ('needs_input','ready_for_review','queued','running','partially_completed',
          'completed','failed','cancel_requested','cancelled','outcome_unknown');
      ELSIF kind='progress' THEN
        IF jsonb_typeof(payload->'completed_steps')<>'number' OR jsonb_typeof(payload->'total_steps')<>'number'
          OR payload->>'completed_steps' !~ '^(0|[1-9][0-9]*)$' OR payload->>'total_steps' !~ '^[1-9][0-9]*$' THEN RETURN false; END IF;
        RETURN payload->>'step_id' ~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
          AND (payload->>'completed_steps')::numeric <= (payload->>'total_steps')::numeric
          AND (payload->>'total_steps')::numeric BETWEEN 1 AND 16;
      ELSIF kind='output' THEN
        RETURN payload->>'output_id' ~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$';
      ELSIF kind='review' THEN
        RETURN payload->>'id' ~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
          AND payload->>'kind' IN ('scope','cost','identity','fields','profile','draft');
      ELSE
        RETURN payload->>'code' IN ('configuration_required','source_unavailable','permission_revoked',
          'stale_revision','budget_exhausted','provider_unavailable','invalid_output','outcome_unknown')
          AND jsonb_typeof(payload->'retryable')='boolean';
      END IF;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_sales_event_valid(text,jsonb) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.buyeros_sales_event_valid(text,jsonb) TO buyeros_api;

    CREATE TABLE sales_tasks (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL,
      owner_user_id uuid NOT NULL REFERENCES users(id), actor_id uuid NOT NULL REFERENCES users(id),
      client_message_id uuid NOT NULL, message_sequence integer NOT NULL CHECK(message_sequence>0),
      intent_fingerprint varchar(64) NOT NULL CHECK(intent_fingerprint ~ '^[a-f0-9]{64}$'),
      skill_id varchar(240) NOT NULL, skill_version varchar(240) NOT NULL,
      user_message text NOT NULL CHECK(length(user_message) BETWEEN 1 AND 4000 AND user_message ~ '\\S'),
      arguments jsonb NOT NULL CHECK(jsonb_typeof(arguments)='object' AND octet_length(arguments::text)<=131072),
      source_refs jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(source_refs)='array' AND jsonb_array_length(source_refs)<=20 AND octet_length(source_refs::text)<=16384),
      intake_history jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(intake_history)='array' AND jsonb_array_length(intake_history)<=33 AND octet_length(intake_history::text)<=262144),
      state varchar(32) NOT NULL DEFAULT 'needs_input' CHECK(state IN
        ('needs_input','ready_for_review','queued','running','partially_completed','completed','failed','cancel_requested','cancelled','outcome_unknown')),
      revision integer NOT NULL DEFAULT 1 CHECK(revision>0), event_sequence integer NOT NULL DEFAULT 0 CHECK(event_sequence>=0),
      context_digest varchar(64) CHECK(context_digest ~ '^[a-f0-9]{64}$'),
      output_ids jsonb NOT NULL DEFAULT '[]' CHECK(jsonb_typeof(output_ids)='array' AND jsonb_array_length(output_ids)<=64),
      pending_review jsonb,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CHECK(state<>'completed' OR (jsonb_array_length(output_ids)>0 AND pending_review IS NULL)),
      UNIQUE(workspace_id,project_id,thread_id,id),
      UNIQUE(workspace_id,actor_id,client_message_id), UNIQUE(workspace_id,thread_id,message_sequence),
      FOREIGN KEY(workspace_id,project_id,thread_id,owner_user_id)
        REFERENCES conversation_threads(workspace_id,project_id,id,owner_user_id) ON DELETE CASCADE
    );
    CREATE TABLE sales_task_events (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL, task_id uuid NOT NULL,
      sequence integer NOT NULL CHECK(sequence>0), kind varchar(16) NOT NULL CHECK(kind IN ('state','progress','output','review','error')),
      payload jsonb NOT NULL CHECK(public.buyeros_sales_event_valid(kind,payload) IS TRUE AND octet_length(payload::text)<=4096),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,task_id,sequence),
      FOREIGN KEY(workspace_id,project_id,thread_id,task_id) REFERENCES sales_tasks(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );
    CREATE TABLE sales_task_dependencies (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL, task_id uuid NOT NULL,
      source_id uuid NOT NULL, source_version integer NOT NULL CHECK(source_version>0),
      kind varchar(32) NOT NULL CHECK(kind IN ('project_fact','profile','buyer','document','output','run','provider_evidence','drive')),
      retention_class varchar(16) NOT NULL CHECK(retention_class IN ('durable','metadata_only','zero_content')),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,task_id,source_id,kind,source_version),
      FOREIGN KEY(workspace_id,project_id,thread_id,task_id) REFERENCES sales_tasks(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );
    CREATE INDEX ix_sales_dependencies_source ON sales_task_dependencies(workspace_id,project_id,kind,source_id);
    CREATE TABLE conversation_thread_preferences (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL,
      owner_user_id uuid NOT NULL REFERENCES users(id), actor_id uuid NOT NULL REFERENCES users(id),
      pinned boolean NOT NULL DEFAULT false, archived boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,thread_id,actor_id),
      FOREIGN KEY(workspace_id,project_id,thread_id,owner_user_id)
        REFERENCES conversation_threads(workspace_id,project_id,id,owner_user_id) ON DELETE CASCADE
    );

    CREATE FUNCTION public.buyeros_sales_delete_guard() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      PERFORM id FROM public.sales_tasks WHERE workspace_id=OLD.workspace_id AND thread_id=OLD.id FOR UPDATE;
      IF EXISTS(SELECT 1 FROM public.sales_tasks WHERE workspace_id=OLD.workspace_id AND thread_id=OLD.id
        AND state NOT IN ('needs_input','ready_for_review','completed','failed','cancelled')) THEN
        RAISE EXCEPTION 'cancel and reconcile active discussion tasks before deletion' USING ERRCODE='23514';
      END IF;
      RETURN OLD;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_sales_delete_guard() FROM PUBLIC;
    CREATE TRIGGER sales_thread_delete_guard BEFORE DELETE ON conversation_threads
      FOR EACH ROW EXECUTE FUNCTION public.buyeros_sales_delete_guard();
    """)
    _execution_upgrade()
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} "
            "USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) "
            "WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker")
        verbs = 'SELECT,INSERT,UPDATE' if table in {'sales_tasks','sales_reviews','sales_executions','sales_steps'} else ('SELECT,INSERT,UPDATE,DELETE' if table == 'conversation_thread_preferences' else 'SELECT,INSERT')
        op.execute(f"GRANT {verbs} ON {table} TO buyeros_api")
    # Worker can consume approved work, never create approval, parent budget or intake.
    op.execute("GRANT SELECT ON sales_tasks,sales_reviews,sales_executions,sales_steps,conversation_threads,conversation_thread_shares TO buyeros_worker")
    op.execute("GRANT UPDATE(state,revision,event_sequence,updated_at) ON sales_tasks TO buyeros_worker")
    op.execute("GRANT UPDATE(version) ON conversation_threads TO buyeros_worker")
    op.execute("GRANT UPDATE(calls_started,consumed_usd,unused_released,updated_at) ON sales_executions TO buyeros_worker")
    op.execute("GRANT UPDATE(state,definitely_unsubmitted,claim_id,claimed_at,usage,result_digest,native_operation_id,updated_at) ON sales_steps TO buyeros_worker")
    op.execute("GRANT SELECT,INSERT ON sales_task_events TO buyeros_worker")
    op.execute("GRANT EXECUTE ON FUNCTION public.buyeros_sales_event_valid(text,jsonb) TO buyeros_worker")
    _fences(revision)


def downgrade():
    # Transactional owner visibility; refusal rolls FORCE changes back as well.
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    db = op.get_bind()
    if any(db.execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one() for table in TABLES):
        raise RuntimeError('0060 downgrade blocked: preserve populated sales tasks/events/dependencies/preferences')
    op.execute('REVOKE SELECT,UPDATE(version) ON conversation_threads FROM buyeros_worker')
    op.execute('REVOKE SELECT ON conversation_thread_shares FROM buyeros_worker')
    op.execute('DROP TRIGGER sales_thread_delete_guard ON conversation_threads')
    op.execute('DROP FUNCTION public.buyeros_sales_delete_guard()')
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE {table}')
    op.execute('DROP FUNCTION public.buyeros_sales_event_valid(text,jsonb)')
    _fences(down_revision)


def _execution_upgrade():
    op.execute("""
    CREATE TABLE sales_reviews (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL,
      task_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), task_revision integer NOT NULL CHECK(task_revision>0),
      fingerprint varchar(64) NOT NULL CHECK(fingerprint ~ '^[a-f0-9]{64}$'),
      expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id),
      FOREIGN KEY(workspace_id,project_id,thread_id,task_id)
        REFERENCES sales_tasks(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );
    CREATE TABLE sales_executions (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL, thread_id uuid NOT NULL,
      task_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), review_id uuid NOT NULL,
      task_revision integer NOT NULL CHECK(task_revision>0), intake_revision integer NOT NULL CHECK(intake_revision>0),
      fingerprint varchar(64) NOT NULL CHECK(fingerprint ~ '^[a-f0-9]{64}$'),
      intake_hash varchar(64) NOT NULL CHECK(intake_hash ~ '^[a-f0-9]{64}$'),
      registration_hash varchar(64) NOT NULL CHECK(registration_hash ~ '^[a-f0-9]{64}$'),
      reservation_id uuid NOT NULL REFERENCES budget_reservations(id),
      proposal jsonb NOT NULL CHECK(jsonb_typeof(proposal)='object' AND octet_length(proposal::text)<=16384),
      plan jsonb NOT NULL CHECK(jsonb_typeof(plan)='object' AND octet_length(plan::text)<=8192 AND jsonb_typeof(plan->'steps')='array' AND jsonb_array_length(plan->'steps') BETWEEN 1 AND 8),
      market varchar(32) NOT NULL, language varchar(32) NOT NULL,
      max_calls integer NOT NULL CHECK(max_calls BETWEEN 1 AND 8),
      max_concurrency integer NOT NULL CHECK(max_concurrency BETWEEN 1 AND 2),
      calls_started integer NOT NULL DEFAULT 0 CHECK(calls_started BETWEEN 0 AND max_calls),
      upper_bound numeric(20,6) NOT NULL CHECK(upper_bound>0),
      unused_released boolean NOT NULL DEFAULT false CHECK(NOT unused_released OR (calls_started=0 AND consumed_usd=0)),
      consumed_usd numeric(20,6) NOT NULL DEFAULT 0 CHECK(consumed_usd BETWEEN 0 AND upper_bound),
      cancelled boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,id), UNIQUE(workspace_id,task_id),
      FOREIGN KEY(workspace_id,project_id,thread_id,task_id)
        REFERENCES sales_tasks(workspace_id,project_id,thread_id,id) ON DELETE CASCADE,
      FOREIGN KEY(workspace_id,review_id) REFERENCES sales_reviews(workspace_id,id)
    );
    CREATE TABLE sales_steps (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, execution_id uuid NOT NULL, outbox_id uuid NOT NULL,
      section varchar(240) NOT NULL,
      state varchar(32) NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','submitting','received','failed','cancelled','unknown')),
      basis_hash varchar(64) NOT NULL CHECK(basis_hash ~ '^[a-f0-9]{64}$'),
      projection_hash varchar(64) NOT NULL CHECK(projection_hash ~ '^[a-f0-9]{64}$'),
      definitely_unsubmitted boolean NOT NULL DEFAULT false,
      liability numeric(20,6) NOT NULL CHECK(liability>0), claim_id uuid, claimed_at timestamptz,
      native_operation_id uuid, usage jsonb, result_digest varchar(64),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(workspace_id,execution_id,section),
      FOREIGN KEY(workspace_id,execution_id) REFERENCES sales_executions(workspace_id,id) ON DELETE CASCADE,
      FOREIGN KEY(workspace_id,outbox_id) REFERENCES outbox_events(workspace_id,id),
      CHECK (NOT definitely_unsubmitted OR (state='failed' AND claim_id IS NOT NULL AND usage IS NULL AND result_digest IS NULL AND native_operation_id IS NULL)),
      CHECK ((state NOT IN ('submitting','received','unknown')) OR (claim_id IS NOT NULL AND claimed_at IS NOT NULL)),
      CHECK ((state<>'received') OR (usage IS NOT NULL AND result_digest IS NOT NULL)),
      CHECK (usage IS NULL OR (jsonb_typeof(usage)='object' AND octet_length(usage::text)<=4096
        AND usage ?& ARRAY['task_id','step_id','context_digest','model_id','prompt_version','provider_ref','usage']
        AND usage - ARRAY['task_id','step_id','context_digest','model_id','prompt_version','provider_ref','usage']='{}'::jsonb
        AND jsonb_typeof(usage->'usage')='object'
        AND (usage->'usage') - ARRAY['input_tokens','output_tokens','cost']='{}'::jsonb
        AND usage->'usage'->'cost'='null'::jsonb
        AND (usage->'usage'->>'input_tokens')::integer BETWEEN 0 AND 6000
        AND (usage->'usage'->>'output_tokens')::integer BETWEEN 0 AND 1000))
    );
    CREATE OR REPLACE FUNCTION public.buyeros_sales_delete_guard() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
    BEGIN
      PERFORM id FROM public.sales_tasks WHERE workspace_id=OLD.workspace_id AND thread_id=OLD.id FOR UPDATE;
      IF EXISTS(SELECT 1 FROM public.sales_tasks WHERE workspace_id=OLD.workspace_id AND thread_id=OLD.id
        AND state NOT IN ('needs_input','ready_for_review','completed','failed','cancelled'))
        OR EXISTS(SELECT 1 FROM public.sales_executions WHERE workspace_id=OLD.workspace_id AND thread_id=OLD.id AND NOT unused_released) THEN
        RAISE EXCEPTION 'retain admitted execution and liability evidence until reconciliation' USING ERRCODE='23514';
      END IF;
      RETURN OLD;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_sales_delete_guard() FROM PUBLIC;
    """)
