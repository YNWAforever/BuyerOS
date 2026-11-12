"""Application-observed boundary instants for derived turn events (Phase 3.6).

Every event of one turn is appended inside the transaction that persists the
turn, and ``created_at`` defaults to ``now()`` (transaction timestamp). All
events of a turn therefore share one instant, so per-turn latency cannot be
derived from ``created_at`` alone. This migration adds *optional*
``started_at`` / ``finished_at`` string fields to the ``turn.started`` and
``turn.final`` event payloads (no table or column change) and re-fences schema
readiness to this revision.

Old events without boundary fields stay valid and contribute no latency
sample; new turns carry application-observed UTC instants. Nothing is
rewritten on upgrade. Downgrade removes the boundary fields before restoring
the 0068 validator, so no row is left violating its own contract.
"""
from pathlib import Path
from runpy import run_path

from alembic import op

revision = '0072_turn_event_boundaries'
down_revision = '0071_conversation_retention'
branch_labels = depends_on = None
TABLES = ()
# Same bounded UTC instant shape the pydantic payload contract accepts.
INSTANT = (r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}'
           r'(\.[0-9]{1,6})?(Z|[+-][0-9]{2}:[0-9]{2})$')


def fences():
    prior = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    prior['fences'](revision)
    tables = (prior['TABLES']
        + run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']
        + ('xverum_enrichments',)
        + run_path(str(Path(__file__).with_name('0065_sales_lifecycle.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0066_conversation_turns.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0068_conversation_turn_events.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0069_conversation_turn_reconciliations.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0070_turn_rate_windows.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0071_conversation_retention.py')))['TABLES'])
    checks = ''.join(" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public." + table +
        "') AND relrowsecurity AND relforcerowsecurity)" for table in tables)
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT "
        "COALESCE((SELECT version_num='" + revision + "' FROM public.alembic_version),false)" + checks + " $$")


def _install(boundaries: bool):
    # The validator is a table CHECK dependency; CREATE OR REPLACE keeps the
    # existing function OID and therefore its execute grants.
    if boundaries:
        started = ("IF NOT payload ? 'status' OR payload - ARRAY['status','started_at'] "
                   "<> '{}'::jsonb THEN RETURN false; END IF;\n"
                   "        IF payload ? 'started_at' AND (jsonb_typeof(payload->'started_at')<>'string' OR "
                   "(payload->>'started_at') !~ '" + INSTANT + "') THEN RETURN false; END IF;\n"
                   "        RETURN payload->>'status'='running';")
        final = ("IF NOT payload ? 'status' OR payload - ARRAY['status','finished_at'] "
                 "<> '{}'::jsonb THEN RETURN false; END IF;\n"
                 "        IF payload ? 'finished_at' AND (jsonb_typeof(payload->'finished_at')<>'string' OR "
                 "(payload->>'finished_at') !~ '" + INSTANT + "') THEN RETURN false; END IF;\n"
                 "        RETURN payload->>'status' IN ('completed','needs_input','needs_approval',\n"
                 "          'failed','outcome_unknown','cancelled');")
    else:
        started = ("IF NOT payload ?& ARRAY['status'] OR payload - ARRAY['status'] "
                   "<> '{}'::jsonb THEN RETURN false; END IF;\n"
                   "        RETURN payload->>'status'='running';")
        final = ("IF NOT payload ?& ARRAY['status'] OR payload - ARRAY['status'] "
                 "<> '{}'::jsonb THEN RETURN false; END IF;\n"
                 "        RETURN payload->>'status' IN ('completed','needs_input','needs_approval',\n"
                 "          'failed','outcome_unknown','cancelled');")
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_turn_event_valid(kind text, payload jsonb) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
    DECLARE keys text[];
    BEGIN
      IF payload IS NULL OR jsonb_typeof(payload)<>'object'
        OR octet_length(payload::text)>32768 THEN RETURN false; END IF;
      IF kind='turn.started' THEN
        """ + started + """
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
        """ + final + """
      ELSE
        RETURN false;
      END IF;
    END $$;
    """)


def upgrade():
    _install(boundaries=True)
    fences()


def downgrade():
    # Remove boundary observations before the old validator forbids the keys.
    op.execute("UPDATE conversation_turn_events SET payload = payload - 'started_at' "
               "WHERE kind='turn.started' AND payload ? 'started_at'")
    op.execute("UPDATE conversation_turn_events SET payload = payload - 'finished_at' "
               "WHERE kind='turn.final' AND payload ? 'finished_at'")
    _install(boundaries=False)
    run_path(str(Path(__file__).with_name('0071_conversation_retention.py')))['fences']()
