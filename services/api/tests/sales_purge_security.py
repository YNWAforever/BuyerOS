"""Harmless runtime TEMP shadow probe; never executes privileged side effects."""
import uuid
import psycopg
import pytest
from tests.test_native_model_completion_db import role_dsn


def check_shadowing(c,role,table,function,target,kind):
    with psycopg.connect(role_dsn(c.dsn,role)) as db:
        assert db.execute('SELECT current_user,has_database_privilege(current_database(),\'TEMP\')').fetchone()==(role,True)
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c.ws),))
        db.execute('CREATE TEMP TABLE sales_content_tombstones(workspace_id uuid,target_id uuid,kind text,completed_at timestamptz)')
        db.execute('INSERT INTO pg_temp.sales_content_tombstones VALUES(%s,%s,%s,NULL)',(c.ws,target,kind))
        tables=('sales_tasks','sales_task_events','sales_reviews','sales_executions','sales_steps',
            'sales_output_sections','sales_output_versions','sales_outputs','xverum_enrichments',
            'xverum_stages','xverum_tool_receipts','xverum_quotes','xverum_credit_reservations',
            'xverum_receipts','export_jobs')
        for relation in tables:
            db.execute(f'CREATE TEMP TABLE {relation} (LIKE public.{relation} INCLUDING DEFAULTS)')
            db.execute(f'INSERT INTO pg_temp.{relation} SELECT * FROM public.{relation} WHERE workspace_id=%s',(c.ws,))
        db.execute('CREATE TEMP TABLE purge_probe(invoker text)')
        db.execute('''CREATE FUNCTION pg_temp.purge_probe_trigger() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN INSERT INTO pg_temp.purge_probe VALUES(current_user);
          IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW; END $$''')
        for relation in (*tables,'sales_content_tombstones'):
            db.execute(f'CREATE TRIGGER shadow_probe BEFORE UPDATE OR DELETE ON pg_temp.{relation} FOR EACH ROW EXECUTE FUNCTION pg_temp.purge_probe_trigger()')
        db.execute(f'UPDATE pg_temp.{table} SET updated_at=updated_at WHERE id=%s',(target,))
        assert db.execute('SELECT * FROM pg_temp.purge_probe').fetchall()==[(role,)]
        db.execute('TRUNCATE pg_temp.purge_probe')
        # A fabricated TEMP guard cannot authorize any persistent mutation.
        with pytest.raises(psycopg.errors.RaiseException,match='purge tombstone required'):
            with db.transaction():db.execute(f'SELECT public.{function}(%s)',(target,))
        db.execute('''INSERT INTO public.sales_content_tombstones(id,workspace_id,project_id,target_id,kind)
          VALUES(%s,%s,%s,%s,%s)''',(uuid.uuid4(),c.ws,c.project,target,kind))
        # The caller's guard can also be empty; only the public guard is authority.
        db.execute('TRUNCATE pg_temp.sales_content_tombstones')
        db.execute(f'SELECT public.{function}(%s)',(target,))
        assert db.execute('SELECT * FROM pg_temp.purge_probe').fetchall()==[]
        if table=='sales_tasks':
            assert db.execute('SELECT user_message FROM public.sales_tasks WHERE id=%s',(target,)).fetchone()[0]=='Content purged'
            assert db.execute('SELECT user_message FROM pg_temp.sales_tasks WHERE id=%s',(target,)).fetchone()[0]!='Content purged'
        elif table=='xverum_enrichments':
            assert db.execute('SELECT proposal,proof,applied FROM public.xverum_enrichments WHERE id=%s',(target,)).fetchone()==({}, {}, None)
            assert db.execute('SELECT proposal FROM pg_temp.xverum_enrichments WHERE id=%s',(target,)).fetchone()[0]
        else:
            assert db.execute('SELECT cancelled FROM public.xverum_stages WHERE id=%s',(target,)).fetchone()[0] is True
            assert db.execute('SELECT cancelled FROM pg_temp.xverum_stages WHERE id=%s',(target,)).fetchone()[0] is False
        # A real tombstone from this tenant does not authorize a different tenant.
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(uuid.uuid4()),))
        with pytest.raises(psycopg.errors.RaiseException,match='purge tombstone required'):
            with db.transaction():db.execute(f'SELECT public.{function}(%s)',(target,))
        assert db.execute('SELECT * FROM pg_temp.purge_probe').fetchall()==[]
