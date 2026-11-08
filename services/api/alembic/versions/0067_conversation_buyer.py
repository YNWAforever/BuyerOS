"""Company-specific threads and proposal-only approved MCP capabilities.

Additive and backward compatible:

* ``conversation_threads.buyer_id`` is a nullable, tenant+project scoped FK to
  the canonical buyer record. Existing threads keep NULL (no company link).
* ``conversation_turn_proposals`` accepts two reviewed proposal-only
  capabilities: ``xverum.enrich_company`` and ``drive.read``. No executor for
  either capability dispatches to a provider in this increment.
* ``buyeros_turn_parts_valid`` becomes a superset (buyer citation kind and the
  reviewed-credit ``known`` flag). The superset is intentionally retained on
  downgrade: it accepts no new authority and old application revisions never
  write those shapes, so keeping it cannot corrupt reverted data.

Downgrade refuses when any thread carries a buyer link or any proposal uses a
new capability; otherwise the link column and capability CHECK are reverted.
"""
from pathlib import Path
from runpy import run_path

from alembic import op
import sqlalchemy as sa

revision = '0067_conversation_buyer'
down_revision = '0066_conversation_turns'
branch_labels = depends_on = None
NEW_CAPABILITIES = ('xverum.enrich_company', 'drive.read')
CAPABILITY_CHECK = "capability IN ('documents.read','research.read','xverum.enrich_company','drive.read')"
PREVIOUS_CAPABILITY_CHECK = "capability IN ('documents.read','research.read')"


def fences():
    prior = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    prior['fences'](revision)
    tables = (prior['TABLES']
        + run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']
        + ('xverum_enrichments',)
        + run_path(str(Path(__file__).with_name('0065_sales_lifecycle.py')))['TABLES']
        + run_path(str(Path(__file__).with_name('0066_conversation_turns.py')))['TABLES'])
    checks = ''.join(" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public." + table +
        "') AND relrowsecurity AND relforcerowsecurity)" for table in tables)
    op.execute("CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean "
        "LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT "
        "COALESCE((SELECT version_num='" + revision + "' FROM public.alembic_version),false)" + checks + " $$")


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION public.buyeros_turn_parts_valid(items jsonb) RETURNS boolean
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
        IF keys IS NULL OR NOT item ?& keys OR item - keys <> '{}'::jsonb THEN RETURN false; END IF;
        IF kind='text' THEN
          IF jsonb_typeof(item->'text')<>'string' OR length(item->>'text') NOT BETWEEN 1 AND 4000
            OR item->>'language' NOT IN ('en','zh-HK') THEN RETURN false; END IF;
        ELSIF kind='citations' THEN
          IF jsonb_typeof(item->'items')<>'array'
            OR jsonb_array_length(item->'items') NOT BETWEEN 1 AND 20 THEN RETURN false; END IF;
          FOR sub IN SELECT value FROM jsonb_array_elements(item->'items') LOOP
            IF jsonb_typeof(sub)<>'object' OR NOT sub ?& ARRAY['id','label','kind']
              OR sub - ARRAY['id','label','kind','href'] <> '{}'::jsonb
              OR jsonb_typeof(sub->'id')<>'string' OR length(sub->>'id') NOT BETWEEN 1 AND 200
              OR jsonb_typeof(sub->'label')<>'string' OR length(sub->>'label') NOT BETWEEN 1 AND 120
              OR sub->>'kind' NOT IN ('document','fact','drive','run','results','buyer') THEN RETURN false; END IF;
          END LOOP;
        ELSIF kind='tool_activity' THEN
          IF (item->>'call_id') !~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
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
          IF (item->>'proposal_id') !~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$' OR item->>'requires_approval' <> 'true'
            OR item->>'capability' !~ '^[a-z][a-z0-9_.]{{2,63}}$'
            OR jsonb_typeof(item->'title')<>'string' OR length(item->>'title') NOT BETWEEN 1 AND 240
            OR jsonb_typeof(item->'rationale')<>'string' OR length(item->>'rationale') NOT BETWEEN 1 AND 1000
            OR jsonb_typeof(item->'arguments_preview')<>'object'
            OR octet_length((item->'arguments_preview')::text)>4096 THEN RETURN false; END IF;
          IF item ? 'cost' AND item->'cost' <> 'null'::jsonb THEN
            sub := item->'cost';
            IF jsonb_typeof(sub)<>'object'
              OR NOT sub ?& ARRAY['kind','amount','unit','may_incur_provider_charges']
              OR sub - ARRAY['kind','amount','unit','may_incur_provider_charges'] <> '{}'::jsonb
              OR sub->>'kind' NOT IN ('nonbillable','provider_credits')
              OR sub->>'unit' NOT IN ('USD','credits')
              OR jsonb_typeof(sub->'may_incur_provider_charges')<>'boolean'
              OR jsonb_typeof(sub->'known') NOT IN ('boolean','null') THEN RETURN false; END IF;
          END IF;
        ELSIF kind='output_link' THEN
          sub := item->'output';
          IF jsonb_typeof(sub)<>'object' OR NOT sub ?& ARRAY['output_id','kind','revision','status']
            OR sub - ARRAY['output_id','kind','revision','status'] <> '{}'::jsonb
            OR (sub->>'output_id') !~ '^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$' OR jsonb_typeof(sub->'revision')<>'number'
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
              OR sub - ARRAY['label','href'] <> '{}'::jsonb
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

    ALTER TABLE conversation_threads ADD COLUMN buyer_id uuid;
    ALTER TABLE conversation_threads ADD CONSTRAINT fk_conversation_threads_buyer
      FOREIGN KEY(workspace_id,project_id,buyer_id)
      REFERENCES project_buyers(workspace_id,project_id,id)
      ON DELETE SET NULL (buyer_id);
    ALTER TABLE conversation_turn_proposals
      DROP CONSTRAINT IF EXISTS conversation_turn_proposals_capability_check;
    ALTER TABLE conversation_turn_proposals
      ADD CONSTRAINT ck_conversation_turn_proposals_capability CHECK(capability IN ('documents.read','research.read','xverum.enrich_company','drive.read'));
    """)
    fences()


def downgrade():
    db = op.get_bind()
    if db.execute(sa.text("SELECT EXISTS(SELECT 1 FROM conversation_threads WHERE buyer_id IS NOT NULL)")).scalar_one():
        raise RuntimeError('0067 downgrade blocked: preserve thread company links')
    if db.execute(sa.text("SELECT EXISTS(SELECT 1 FROM conversation_turn_proposals WHERE capability = ANY(:caps))"),
            {'caps': list(NEW_CAPABILITIES)}).scalar_one():
        raise RuntimeError('0067 downgrade blocked: preserve proposal-only MCP capability decisions')
    op.execute('ALTER TABLE conversation_turn_proposals DROP CONSTRAINT ck_conversation_turn_proposals_capability')
    op.execute("ALTER TABLE conversation_turn_proposals ADD CONSTRAINT conversation_turn_proposals_capability_check "
        "CHECK(capability IN ('documents.read','research.read'))")
    op.execute('ALTER TABLE conversation_threads DROP CONSTRAINT fk_conversation_threads_buyer')
    op.execute('ALTER TABLE conversation_threads DROP COLUMN buyer_id')
    # The parts validator superset is retained (accepts no new authority).
    run_path(str(Path(__file__).with_name('0066_conversation_turns.py')))['fences']()
