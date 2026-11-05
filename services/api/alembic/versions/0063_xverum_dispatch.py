"""Bounded staged dispatch, sanitized evidence and content-free repair journal."""
from alembic import op
import sqlalchemy as sa
from runpy import run_path
from pathlib import Path

revision = '0063_xverum_dispatch'
down_revision = '0062_xverum_credits'
branch_labels = depends_on = None
TABLES = ('xverum_stages', 'xverum_tool_receipts', 'xverum_reconciliations')


def fences():
    previous = run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))
    previous['fences'](revision)
    tables = previous['TABLES'] + TABLES
    checks = ''.join(f" AND EXISTS(SELECT 1 FROM pg_class WHERE oid=to_regclass('public.{t}') AND relrowsecurity AND relforcerowsecurity)" for t in tables)
    op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_xverum_connections_ready() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS $$ SELECT COALESCE((SELECT version_num='{revision}' FROM public.alembic_version),false){checks} $$")


def upgrade():
    common = 'id uuid PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES workspaces(id), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(workspace_id,id),'
    op.execute(f'''
    CREATE TABLE xverum_stages ({common}
        project_id uuid NOT NULL, task_id uuid, task_revision integer, thread_id uuid,
        context_digest varchar(64), intake_hash varchar(64),
        binding jsonb NOT NULL CHECK(jsonb_typeof(binding)='object' AND octet_length(binding::text)<=32768),
        cancelled boolean NOT NULL DEFAULT false,
        CHECK ((task_id IS NULL AND task_revision IS NULL AND thread_id IS NULL AND context_digest IS NULL AND intake_hash IS NULL)
            OR (task_id IS NOT NULL AND task_revision IS NOT NULL AND task_revision>0 AND thread_id IS NOT NULL
                AND context_digest IS NOT NULL AND intake_hash IS NOT NULL
                AND context_digest ~ '^[a-f0-9]{{64}}$' AND intake_hash ~ '^[a-f0-9]{{64}}$')),
        FOREIGN KEY(workspace_id,project_id,id) REFERENCES xverum_receipts(workspace_id,project_id,id),
        FOREIGN KEY(workspace_id,project_id,thread_id,task_id) REFERENCES sales_tasks(workspace_id,project_id,thread_id,id));
    CREATE INDEX ix_xverum_stage_task ON xverum_stages(workspace_id,task_id);
    CREATE TABLE xverum_tool_receipts ({common}
        stage_id uuid NOT NULL, ordinal integer NOT NULL CHECK(ordinal BETWEEN 0 AND 5),
        tool varchar(64) NOT NULL CHECK(tool IN ('search_company_xverum','search_people_xverum','enrich_company_xverum','enrich_person_xverum','get_email_xverum')),
        arguments jsonb NOT NULL CHECK(jsonb_typeof(arguments)='object' AND octet_length(arguments::text)<=8192),
        state varchar(24) NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','submitting','unknown','received','nonaccepted','cancelled')),
        attempts integer NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 2), claim_id uuid,
        request_id varchar(128) CHECK(request_id ~ '^[A-Za-z0-9_-]{{1,128}}$'),
        credits_used integer CHECK(credits_used>=0),
        projection jsonb CHECK(jsonb_typeof(projection)='object' AND octet_length(projection::text)<=65536),
        projection_digest varchar(64) CHECK(projection_digest ~ '^[a-f0-9]{{64}}$'), expires_at timestamptz,
        UNIQUE(workspace_id,stage_id,ordinal),
        FOREIGN KEY(workspace_id,stage_id) REFERENCES xverum_stages(workspace_id,id));
    CREATE TABLE xverum_reconciliations ({common}
        receipt_id uuid NOT NULL, actor_id uuid NOT NULL REFERENCES users(id), evidence_ref uuid NOT NULL,
        fingerprint varchar(64) NOT NULL, expected_version integer NOT NULL CHECK(expected_version>0),
        resolution varchar(24) NOT NULL CHECK(resolution IN ('usage','non_dispatch','unknown')),
        UNIQUE(workspace_id,receipt_id,evidence_ref),
        FOREIGN KEY(workspace_id,receipt_id) REFERENCES xverum_receipts(workspace_id,id));
    ''')
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker')
        op.execute(f'GRANT SELECT ON {table} TO buyeros_api,buyeros_worker')
        op.execute(f'GRANT INSERT ON {table} TO buyeros_api')
    op.execute('GRANT UPDATE(cancelled,updated_at) ON xverum_stages TO buyeros_api,buyeros_worker')
    op.execute('GRANT UPDATE(state,attempts,claim_id,request_id,credits_used,projection,projection_digest,expires_at,updated_at) ON xverum_tool_receipts TO buyeros_api,buyeros_worker')
    fences()


def downgrade():
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    if any(op.get_bind().execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {t})')).scalar_one() for t in TABLES):
        raise RuntimeError('0063 downgrade blocked: preserve dispatch and reconciliation proof')
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE {table}')
    run_path(str(Path(__file__).with_name('0062_xverum_credits.py')))['fences'](down_revision)
