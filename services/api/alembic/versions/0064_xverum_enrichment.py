"""Reviewed enrichment producer, immutable input and single native result proof."""
from alembic import op
import sqlalchemy as sa
from pathlib import Path
from runpy import run_path

revision = '0064_xverum_enrichment'
down_revision = '0063_xverum_dispatch'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE xverum_enrichments (
        id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id),
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
        project_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), buyer_id uuid NOT NULL, task_id uuid, thread_id uuid,
        CHECK((task_id IS NULL)=(thread_id IS NULL)),
        proposal jsonb NOT NULL CHECK(jsonb_typeof(proposal)='object' AND octet_length(proposal::text)<=65536),
        proof jsonb NOT NULL CHECK(jsonb_typeof(proof)='object' AND octet_length(proof::text)<=65536),
        applied jsonb CHECK(jsonb_typeof(applied)='object' AND octet_length(applied::text)<=65536),
        output_revision integer CHECK(output_revision>0), UNIQUE(workspace_id,id),
        FOREIGN KEY(workspace_id,project_id,buyer_id) REFERENCES project_buyers(workspace_id,project_id,id),
        FOREIGN KEY(workspace_id,project_id,thread_id,task_id) REFERENCES sales_tasks(workspace_id,project_id,thread_id,id));
        ALTER TABLE xverum_enrichments ENABLE ROW LEVEL SECURITY;
        ALTER TABLE xverum_enrichments FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON xverum_enrichments
          USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)
          WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid);
        REVOKE ALL ON xverum_enrichments FROM PUBLIC,buyeros_api,buyeros_worker;
        GRANT SELECT ON xverum_enrichments TO buyeros_api,buyeros_worker;
        GRANT INSERT ON xverum_enrichments TO buyeros_api;
        GRANT UPDATE(applied,output_revision,updated_at) ON xverum_enrichments TO buyeros_api;
    ''')
    previous=run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    previous['fences'](revision)
    tables=previous['TABLES']+run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['TABLES']+('xverum_enrichments',)
    checks=''.join(f" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.{t}') AND relrowsecurity AND relforcerowsecurity)" for t in tables)
    op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{revision}' FROM public.alembic_version),false){checks} $$")


def downgrade():
    op.execute('ALTER TABLE xverum_enrichments NO FORCE ROW LEVEL SECURITY')
    if op.get_bind().execute(sa.text('SELECT EXISTS(SELECT 1 FROM xverum_enrichments)')).scalar_one():
        raise RuntimeError('0064 downgrade blocked: preserve reviewed enrichment proof')
    op.execute('DROP TABLE xverum_enrichments')
    run_path(str(Path(__file__).with_name('0063_xverum_dispatch.py')))['fences']()
