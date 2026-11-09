"""Durable conversation-turn events (derived, replayable, tenant scoped).

Additive: events are derived data, so pruning them never changes the persisted
turn status or parts. Append-only for the API role; forced RLS; no worker
grants. The predicate function bounds each payload by kind and embeds the
existing MessagePart validator for ``part`` events.

Downgrade refuses while events exist (they are the recovery/streaming evidence
for a turn) and is empty-table safe otherwise.
"""
from pathlib import Path
from runpy import run_path

from alembic import op
import sqlalchemy as sa

revision = '0068_conversation_turn_events'
down_revision = '0067_conversation_buyer'
branch_labels = depends_on = None
TABLES = ('conversation_turn_events',)
UUID_RE = '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'


def fences():
    prior = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    prior['fences'](revision)
    tables = (prior['TABLES']
        + run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']
        + ('xverum_enrichments',)
        + run_path(str(Path(__file__).with_name('0065_sales_lifecycle.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0066_conversation_turns.py')))['TABLES']
        + TABLES)
    checks = ''.join(" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public." + table +
        "') AND relrowsecurity AND relforcerowsecurity)" for table in tables)
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT "
        "COALESCE((SELECT version_num='" + revision + "' FROM public.alembic_version),false)" + checks + " $$")


def upgrade():
    op.execute("""
    CREATE FUNCTION public.buyeros_turn_event_valid(kind text, payload jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
    DECLARE keys text[];
    BEGIN
      IF payload IS NULL OR jsonb_typeof(payload)<>'object'
        OR octet_length(payload::text)>32768 THEN RETURN false; END IF;
      IF kind='turn.started' THEN
        keys := ARRAY['status'];
        IF NOT payload ?& keys OR payload - keys <> '{}'::jsonb THEN RETURN false; END IF;
        RETURN payload->>'status'='running';
      ELSIF kind='part' THEN
        keys := ARRAY['index','part'];
        IF NOT payload ?& keys OR payload - keys <> '{}'::jsonb THEN RETURN false; END IF;
        IF jsonb_typeof(payload->'index')<>'number'
          OR (payload->>'index') !~ '^(0|[1-9][0-9]?)$'
          OR (payload->>'index')::int > 23
          OR jsonb_typeof(payload->'part')<>'object' THEN RETURN false; END IF;
        RETURN public.buyeros_turn_parts_valid(jsonb_build_array(payload->'part')) IS TRUE;
      ELSIF kind='tool' THEN
        keys := ARRAY['call_id','capability','state','summary','error_code'];
        IF NOT payload ?& keys OR payload - keys <> '{}'::jsonb THEN RETURN false; END IF;
        IF (payload->>'call_id') !~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
          OR (payload->>'capability') !~ '^[a-z][a-z0-9_.]{2,63}$'
          OR payload->>'state' NOT IN ('proposed','approved','running','completed',
            'failed','skipped','outcome_unknown') THEN RETURN false; END IF;
        IF jsonb_typeof(payload->'summary') NOT IN ('string','null')
          OR (jsonb_typeof(payload->'summary')='string'
              AND length(payload->>'summary')>500) THEN RETURN false; END IF;
        IF jsonb_typeof(payload->'error_code') NOT IN ('string','null')
          OR (jsonb_typeof(payload->'error_code')='string'
              AND length(payload->>'error_code')>64) THEN RETURN false; END IF;
        RETURN true;
      ELSIF kind='proposal' THEN
        keys := ARRAY['proposal_id','capability','requires_approval'];
        IF NOT payload ?& keys OR payload - keys <> '{}'::jsonb THEN RETURN false; END IF;
        RETURN (payload->>'proposal_id') ~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
          AND (payload->>'capability') ~ '^[a-z][a-z0-9_.]{2,63}$'
          AND payload->>'requires_approval'='true';
      ELSIF kind='notice' THEN
        keys := ARRAY['code','message'];
        IF NOT payload ?& keys OR payload - keys <> '{}'::jsonb THEN RETURN false; END IF;
        RETURN (payload->>'code') ~ '^[A-Z][A-Z0-9_]{2,63}$'
          AND jsonb_typeof(payload->'message')='string'
          AND length(payload->>'message') BETWEEN 1 AND 500;
      ELSIF kind='turn.final' THEN
        keys := ARRAY['status'];
        IF NOT payload ?& keys OR payload - keys <> '{}'::jsonb THEN RETURN false; END IF;
        RETURN payload->>'status' IN ('completed','needs_input','needs_approval',
          'failed','outcome_unknown','cancelled');
      ELSE
        RETURN false;
      END IF;
    END $$;
    REVOKE ALL ON FUNCTION public.buyeros_turn_event_valid(text,jsonb) FROM PUBLIC,buyeros_worker;
    GRANT EXECUTE ON FUNCTION public.buyeros_turn_event_valid(text,jsonb) TO buyeros_api;

    CREATE TABLE conversation_turn_events (
      id uuid PRIMARY KEY, workspace_id uuid NOT NULL, project_id uuid NOT NULL,
      thread_id uuid NOT NULL, turn_id uuid NOT NULL,
      seq integer NOT NULL CHECK(seq>0),
      kind varchar(16) NOT NULL CHECK(kind IN ('turn.started','part','tool',
        'proposal','notice','turn.final')),
      payload jsonb NOT NULL CHECK(public.buyeros_turn_event_valid(kind,payload) IS TRUE),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(turn_id,seq),
      FOREIGN KEY(workspace_id,project_id,thread_id,turn_id)
        REFERENCES conversation_turns(workspace_id,project_id,thread_id,id) ON DELETE CASCADE
    );
    CREATE INDEX ix_conversation_turn_events_turn
      ON conversation_turn_events(workspace_id,turn_id,seq);

    ALTER TABLE conversation_turn_events ENABLE ROW LEVEL SECURITY;
    ALTER TABLE conversation_turn_events FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON conversation_turn_events
      USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)
      WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);
    REVOKE ALL ON conversation_turn_events FROM PUBLIC,buyeros_api,buyeros_worker;
    GRANT SELECT,INSERT ON conversation_turn_events TO buyeros_api;
    """)
    fences()


def downgrade():
    db = op.get_bind()
    op.execute('ALTER TABLE conversation_turn_events NO FORCE ROW LEVEL SECURITY')
    if db.execute(sa.text('SELECT EXISTS(SELECT 1 FROM conversation_turn_events)')).scalar_one():
        raise RuntimeError('0068 downgrade blocked: preserve conversation turn event evidence')
    op.execute('ALTER TABLE conversation_turn_events DISABLE ROW LEVEL SECURITY')
    op.execute('DROP TABLE conversation_turn_events')
    op.execute('DROP FUNCTION public.buyeros_turn_event_valid(text,jsonb)')
    run_path(str(Path(__file__).with_name('0067_conversation_buyer.py')))['fences']()
