"""Immutable authored revisions and DB-only section receipts."""
from alembic import op
import sqlalchemy as sa

revision = '0061_sales_outputs'
down_revision = '0060_sales_tasks'
branch_labels = depends_on = None
TABLES = ('sales_outputs','sales_output_versions','sales_output_sections','sales_output_dependencies','sales_output_native_links')


def fences(head):
    for service in ('search','model','contact'):
        op.execute(f"CREATE OR REPLACE FUNCTION public.buyeros_{service}_receipts_writable() "
            "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,public AS "
            f"$$ SELECT COALESCE((SELECT version_num='{head}' FROM public.alembic_version),false) $$")


def upgrade():
    # Explicit migration DDL independent of future ORM definitions.
    op.execute('ALTER TABLE sales_steps ADD CONSTRAINT uq_sales_steps_output_receipt_identity UNIQUE(workspace_id,execution_id,id)')
    common = 'id uuid PRIMARY KEY, workspace_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),'
    op.execute(f'''CREATE TABLE sales_outputs ({common}
        project_id uuid NOT NULL, thread_id uuid NOT NULL, task_id uuid NOT NULL, revision integer NOT NULL CHECK(revision>0),
        UNIQUE(workspace_id,id), UNIQUE(workspace_id,task_id),
        FOREIGN KEY(workspace_id,project_id,thread_id,task_id) REFERENCES sales_tasks(workspace_id,project_id,thread_id,id) ON DELETE CASCADE);
    CREATE TABLE sales_output_versions ({common}
        output_id uuid NOT NULL, revision integer NOT NULL CHECK(revision>0),
        visibility varchar(16) NOT NULL CHECK(visibility IN ('thread','project')),
        candidate jsonb NOT NULL CHECK(jsonb_typeof(candidate)='object' AND octet_length(candidate::text)<=131072),
        source_refs jsonb NOT NULL CHECK(jsonb_typeof(source_refs)='array' AND jsonb_array_length(source_refs)<=20),
        context_digest varchar(64) NOT NULL CHECK(context_digest ~ '^[a-f0-9]{{64}}$'),
        intake_revision integer NOT NULL CHECK(intake_revision>0),
        UNIQUE(workspace_id,output_id,revision),
        FOREIGN KEY(workspace_id,output_id) REFERENCES sales_outputs(workspace_id,id) ON DELETE CASCADE);
    CREATE TABLE sales_output_sections ({common}
        execution_id uuid NOT NULL, step_id uuid NOT NULL,
        claim_id uuid NOT NULL, section varchar(240) NOT NULL,
        basis_hash varchar(64) NOT NULL CHECK(basis_hash ~ '^[a-f0-9]{{64}}$'),
        projection_hash varchar(64) NOT NULL CHECK(projection_hash ~ '^[a-f0-9]{{64}}$'),
        result_digest varchar(64) NOT NULL CHECK(result_digest ~ '^[a-f0-9]{{64}}$'),
        candidate jsonb NOT NULL CHECK(jsonb_typeof(candidate)='object' AND candidate ?& ARRAY['kind','section','content','citations','complete'] AND candidate->'complete'='false'::jsonb AND octet_length(candidate::text)<=8192),
        UNIQUE(workspace_id,step_id), UNIQUE(workspace_id,execution_id,section),
        FOREIGN KEY(workspace_id,execution_id,step_id) REFERENCES sales_steps(workspace_id,execution_id,id) ON DELETE CASCADE,
        FOREIGN KEY(workspace_id,execution_id) REFERENCES sales_executions(workspace_id,id) ON DELETE CASCADE);
    CREATE TABLE sales_output_dependencies ({common}
        output_id uuid NOT NULL, revision integer NOT NULL, kind varchar(32) NOT NULL,
        source_id uuid NOT NULL, source_revision integer NOT NULL CHECK(source_revision>0),
        UNIQUE(workspace_id,output_id,revision,kind,source_id,source_revision),
        FOREIGN KEY(workspace_id,output_id,revision) REFERENCES sales_output_versions(workspace_id,output_id,revision) ON DELETE CASCADE);
    CREATE TABLE sales_output_native_links ({common}
        output_id uuid NOT NULL, revision integer NOT NULL, surface varchar(16) NOT NULL,
        native_id uuid NOT NULL, native_revision integer NOT NULL CHECK(native_revision>0),
        UNIQUE(workspace_id,output_id,revision,surface,native_id),
        FOREIGN KEY(workspace_id,output_id,revision) REFERENCES sales_output_versions(workspace_id,output_id,revision) ON DELETE CASCADE);
    CREATE INDEX ix_sales_output_source ON sales_output_dependencies(workspace_id,kind,source_id);
    CREATE INDEX ix_sales_output_native ON sales_output_native_links(workspace_id,surface,native_id);
    ''')
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid) WITH CHECK (workspace_id=NULLIF(current_setting('app.workspace_id',true),'')::uuid)")
        op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,buyeros_api,buyeros_worker')
        op.execute(f'GRANT SELECT,INSERT ON {table} TO buyeros_api')
        op.execute(f'GRANT SELECT ON {table} TO buyeros_worker')
    op.execute('GRANT UPDATE(revision,updated_at) ON sales_outputs TO buyeros_api')
    op.execute('GRANT INSERT ON sales_output_sections TO buyeros_worker')
    fences(revision)


def downgrade():
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
    if any(op.get_bind().execute(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')).scalar_one() for table in TABLES):
        raise RuntimeError('0061 downgrade blocked: preserve populated outputs and section receipts')
    for table in reversed(TABLES):
        op.execute(f'DROP TABLE {table}')
    op.execute('ALTER TABLE sales_steps DROP CONSTRAINT uq_sales_steps_output_receipt_identity')
    fences(down_revision)
