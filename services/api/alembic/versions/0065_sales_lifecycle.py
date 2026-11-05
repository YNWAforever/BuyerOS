"""Separate financial evidence and bounded irreversible private-content purge."""
from pathlib import Path
from runpy import run_path
from alembic import op
import sqlalchemy as sa

revision = '0065_sales_lifecycle'
down_revision = '0064_xverum_enrichment'
branch_labels = depends_on = None
TABLES = ('sales_financial_evidence', 'sales_accounting_receipts', 'sales_content_tombstones', 'xverum_enrichment_dependencies')


def fences():
    prior = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    prior['fences'](revision)
    tables = prior['TABLES'] + run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES'] + ('xverum_enrichments',) + TABLES
    checks = ''.join(f" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.{t}') AND relrowsecurity AND relforcerowsecurity)" for t in tables)
    op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{revision}' FROM public.alembic_version),false){checks} $$")


def upgrade():
    op.execute('''ALTER TABLE sales_executions
      ADD COLUMN accounting_revision integer NOT NULL DEFAULT 0 CHECK(accounting_revision>=0),
      ADD COLUMN accounted_bound numeric(20,6) NOT NULL DEFAULT 0 CHECK(accounted_bound BETWEEN 0 AND upper_bound),
      ADD COLUMN settled_usd numeric(20,6) NOT NULL DEFAULT 0 CHECK(settled_usd BETWEEN 0 AND accounted_bound),
      ADD COLUMN provider_account_hash varchar(64) CHECK(provider_account_hash ~ '^[a-f0-9]{64}$');''')
    common = 'id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),'
    op.execute(f'''CREATE TABLE sales_financial_evidence ({common}
      execution_id uuid NOT NULL, step_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
      fingerprint varchar(64) NOT NULL CHECK(fingerprint ~ '^[a-f0-9]{{64}}$'),
      observation jsonb NOT NULL CHECK(jsonb_typeof(observation)='object' AND octet_length(observation::text)<=4096),
      UNIQUE(workspace_id,execution_id,step_id));
    CREATE UNIQUE INDEX sales_supplier_observation_once ON sales_financial_evidence
      (workspace_id,(observation->>'account_hash'),(observation->>'request_hash'),(observation->>'evidence_hash'));
    CREATE TABLE sales_accounting_receipts ({common}
      execution_id uuid NOT NULL, reservation_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id),
      revision integer NOT NULL CHECK(revision>0), fingerprint varchar(64) NOT NULL,
      evidence_ids jsonb NOT NULL CHECK(jsonb_typeof(evidence_ids)='array' AND jsonb_array_length(evidence_ids)<=16),
      settled_usd numeric(20,6) NOT NULL CHECK(settled_usd>=0),
      remaining_hold numeric(20,6) NOT NULL CHECK(remaining_hold>=0), cost_event_id uuid,
      FOREIGN KEY(workspace_id,reservation_id) REFERENCES budget_reservations(workspace_id,id),
      UNIQUE(workspace_id,execution_id,revision));
    CREATE TABLE sales_content_tombstones ({common}
      project_id uuid NOT NULL, target_id uuid NOT NULL, kind varchar(16) NOT NULL CHECK(kind IN ('source','task','output','provider','enrichment')),
      completed_at timestamptz, UNIQUE(workspace_id,target_id,kind),
      FOREIGN KEY(workspace_id,project_id) REFERENCES projects(workspace_id,id));''')
    op.execute('''CREATE TABLE xverum_enrichment_dependencies (
      workspace_id uuid NOT NULL, enrichment_id uuid NOT NULL, source_id uuid NOT NULL,
      PRIMARY KEY(workspace_id,enrichment_id,source_id),
      FOREIGN KEY(workspace_id,enrichment_id) REFERENCES xverum_enrichments(workspace_id,id),
      FOREIGN KEY(workspace_id,source_id) REFERENCES xverum_tool_receipts(workspace_id,id));
      CREATE INDEX enrichment_source_closure ON xverum_enrichment_dependencies(workspace_id,source_id);
      INSERT INTO xverum_enrichment_dependencies SELECT e.workspace_id,e.id,(r->>'id')::uuid
        FROM xverum_enrichments e CROSS JOIN LATERAL jsonb_array_elements(e.proposal->'source_refs') r;''')
    for table in TABLES:
        op.execute(f'''ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
          ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
          CREATE POLICY tenant_isolation ON {table}
          USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)
          WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);
          REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker;
          GRANT SELECT ON {table} TO buyeros_api,buyeros_worker;
          GRANT INSERT ON {table} TO buyeros_api;''')
    op.execute('GRANT UPDATE(accounting_revision,accounted_bound,settled_usd) ON sales_executions TO buyeros_api')
    op.execute('GRANT INSERT,UPDATE(completed_at) ON sales_content_tombstones TO buyeros_api,buyeros_worker')
    op.execute('GRANT SELECT ON sales_task_dependencies TO buyeros_worker')
    op.execute('''CREATE FUNCTION public.buyeros_purge_xverum_stage(target uuid) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE ws uuid := NULLIF(current_setting('app.workspace_id',true),'')::uuid;
      BEGIN
        IF ws IS NULL OR NOT EXISTS(SELECT 1 FROM public.sales_content_tombstones
          WHERE workspace_id=ws AND target_id=target AND kind='provider') THEN
          RAISE EXCEPTION 'purge tombstone required';
        END IF;
        UPDATE public.xverum_stages SET cancelled=true WHERE workspace_id=ws AND id=target;
        UPDATE public.xverum_tool_receipts SET projection=NULL,arguments='{}',expires_at=now(),
          state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END WHERE workspace_id=ws AND stage_id=target;
        UPDATE public.xverum_quotes SET payload=payload-'query'-'provider_ids'-'tool_plan',expires_at=now()
          WHERE workspace_id=ws AND id IN(SELECT z.quote_id FROM public.xverum_credit_reservations z
            JOIN public.xverum_receipts r ON r.workspace_id=z.workspace_id AND r.reservation_id=z.id
            WHERE r.workspace_id=ws AND r.id=target);
        UPDATE public.sales_content_tombstones SET completed_at=now() WHERE workspace_id=ws AND target_id=target AND kind='provider';
      END $$;
      REVOKE ALL ON FUNCTION public.buyeros_purge_xverum_stage(uuid) FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION public.buyeros_purge_xverum_stage(uuid) TO buyeros_api,buyeros_worker;''')
    # Immutable output tables remain immutable to runtime roles. Only this fixed
    # tenant-scoped tombstoning operation may physically erase retained content.
    op.execute('''CREATE FUNCTION public.buyeros_purge_sales_task(target uuid) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE ws uuid := NULLIF(current_setting('app.workspace_id',true),'')::uuid;
      BEGIN
        IF ws IS NULL OR NOT EXISTS(SELECT 1 FROM public.sales_content_tombstones
          WHERE workspace_id=ws AND target_id=target AND kind='task') THEN
          RAISE EXCEPTION 'purge tombstone required';
        END IF;
        UPDATE public.sales_tasks SET user_message='Content purged',arguments='{}',source_refs='[]',intake_history='[]',
          pending_review=NULL,context_digest=NULL,state='cancelled',revision=revision+1,updated_at=now()
          WHERE workspace_id=ws AND id=target;
        DELETE FROM public.sales_task_events WHERE workspace_id=ws AND task_id=target;
        UPDATE public.sales_reviews SET revoked=true WHERE workspace_id=ws AND task_id=target;
        UPDATE public.sales_executions AS parent SET cancelled=true,proposal='{}',plan=jsonb_build_object('steps',
          (SELECT jsonb_agg(jsonb_build_object('section',s.section)) FROM public.sales_steps s
           WHERE s.workspace_id=ws AND s.execution_id=parent.id))
          WHERE workspace_id=ws AND task_id=target;
        UPDATE public.sales_steps SET state='cancelled' WHERE workspace_id=ws AND state='queued'
          AND execution_id IN (SELECT id FROM public.sales_executions WHERE workspace_id=ws AND task_id=target);
        DELETE FROM public.sales_output_sections WHERE workspace_id=ws AND execution_id IN
          (SELECT id FROM public.sales_executions WHERE workspace_id=ws AND task_id=target);
        UPDATE public.sales_output_versions SET candidate=jsonb_build_object('kind',candidate->>'kind','purged',true),source_refs='[]'
          WHERE workspace_id=ws AND output_id IN (SELECT id FROM public.sales_outputs WHERE workspace_id=ws AND task_id=target);
        UPDATE public.xverum_enrichments SET proposal='{}',proof='{}',applied=NULL
          WHERE workspace_id=ws AND task_id=target;
        UPDATE public.xverum_stages SET cancelled=true WHERE workspace_id=ws AND task_id=target;
        UPDATE public.xverum_tool_receipts SET projection=NULL,arguments='{}',expires_at=now(),
          state=CASE WHEN state='queued' THEN 'cancelled' ELSE state END
          WHERE workspace_id=ws AND stage_id IN (SELECT id FROM public.xverum_stages WHERE workspace_id=ws AND task_id=target);
        UPDATE public.export_jobs SET state='revoked',selection_manifest=NULL,redaction_summary=NULL,
          expires_at=now(),version=version+1 WHERE workspace_id=ws AND kind='sales_output'
          AND selection_manifest->>'output_id' IN (SELECT id::text FROM public.sales_outputs WHERE workspace_id=ws AND task_id=target);
        UPDATE public.sales_content_tombstones SET completed_at=now() WHERE workspace_id=ws AND target_id=target AND kind='task';
      END $$;
      REVOKE ALL ON FUNCTION public.buyeros_purge_sales_task(uuid) FROM PUBLIC,buyeros_worker;
      GRANT EXECUTE ON FUNCTION public.buyeros_purge_sales_task(uuid) TO buyeros_api,buyeros_worker;''')
    op.execute('''CREATE FUNCTION public.buyeros_purge_xverum_enrichment(target uuid) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE ws uuid := NULLIF(current_setting('app.workspace_id',true),'')::uuid;
      BEGIN
        IF ws IS NULL OR NOT EXISTS(SELECT 1 FROM public.sales_content_tombstones
          WHERE workspace_id=ws AND target_id=target AND kind='enrichment') THEN
          RAISE EXCEPTION 'purge tombstone required';
        END IF;
        UPDATE public.xverum_enrichments SET proposal='{}',proof='{}',applied=NULL
          WHERE workspace_id=ws AND id=target;
        UPDATE public.sales_content_tombstones SET completed_at=now()
          WHERE workspace_id=ws AND target_id=target AND kind='enrichment';
      END $$;
      REVOKE ALL ON FUNCTION public.buyeros_purge_xverum_enrichment(uuid) FROM PUBLIC;
      GRANT EXECUTE ON FUNCTION public.buyeros_purge_xverum_enrichment(uuid) TO buyeros_api,buyeros_worker;''')
    fences()


def downgrade():
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    if any(op.get_bind().execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {t})')).scalar_one() for t in TABLES):
        raise RuntimeError('0065 downgrade blocked: preserve financial and purge tombstones')
    op.execute('DROP FUNCTION public.buyeros_purge_xverum_enrichment(uuid)')
    op.execute('DROP FUNCTION public.buyeros_purge_sales_task(uuid)')
    op.execute('DROP FUNCTION public.buyeros_purge_xverum_stage(uuid)')
    op.execute('REVOKE SELECT ON sales_task_dependencies FROM buyeros_worker')
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE {table}')
    for column in ('accounting_revision','accounted_bound','settled_usd','provider_account_hash'):
        op.execute(f'ALTER TABLE sales_executions DROP COLUMN {column}')
    previous = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    previous['fences'](down_revision)
    tables=previous['TABLES']+run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']+('xverum_enrichments',)
    checks=''.join(f" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.{t}') AND relrowsecurity AND relforcerowsecurity)" for t in tables)
    op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{down_revision}' FROM public.alembic_version),false){checks} $$")


