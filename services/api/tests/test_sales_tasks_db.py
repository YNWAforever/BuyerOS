"""Real PostgreSQL acceptance; requires an independently owned disposable fixture."""
from alembic.script import ScriptDirectory
from tests.conftest import SERVICE_ROOT
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
import psycopg
import pytest
from alembic import command
from tests.conftest import runtime_role_dsn
from tests.test_conversation_threads_db import thread_rows, config
from tests.test_buyer_review_db import WORKSPACE_A, WORKSPACE_B, PROJECT_A, PROJECT_B

TABLES = ('sales_tasks','sales_task_events','sales_task_dependencies','conversation_thread_preferences','sales_reviews','sales_executions','sales_steps')


@pytest.fixture
def seeded(isolated_seeded):
    return isolated_seeded


@pytest.fixture
def migrated(isolated_migrated):
    return isolated_migrated


@pytest.fixture
def task_rows(thread_rows):
    dsn, user, first, second = thread_rows
    ids = [uuid.uuid4(), uuid.uuid4()]
    with psycopg.connect(dsn) as db:
        for task, thread, workspace, project in zip(ids, (first,second), (WORKSPACE_A,WORKSPACE_B), (PROJECT_A,PROJECT_B)):
            db.execute("""INSERT INTO sales_tasks(id,workspace_id,project_id,thread_id,owner_user_id,actor_id,
                client_message_id,intent_fingerprint,message_sequence,skill_id,skill_version,user_message,arguments)
                VALUES(%s,%s,%s,%s,%s,%s,%s,repeat('a',64),1,'sales-research','1','SYNTHETIC','{}')""",
                (task,workspace,project,thread,user,user,uuid.uuid4()))
    yield dsn, user, first, ids
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE sales_tasks SET state='cancelled'")


@pytest.mark.parametrize('table', TABLES)
def test_postgres_force_rls_and_minimal_grants(migrated, table):
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone() == (True,True)
        for verb in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
            worker_allowed=(verb=='SELECT' and table in {'sales_tasks','sales_task_events','sales_task_dependencies','sales_reviews','sales_executions','sales_steps'}) or (verb=='INSERT' and table=='sales_task_events')
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',('buyeros_worker',table,verb)).fetchone()[0] == worker_allowed
            allowed = {'SELECT','INSERT','UPDATE','DELETE'} if table.endswith('preferences') else ({'SELECT','INSERT','UPDATE'} if table in {'sales_tasks','sales_reviews','sales_executions','sales_steps'} else {'SELECT','INSERT'})
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',('buyeros_api',table,verb)).fetchone()[0] == (verb in allowed)


@pytest.mark.parametrize('scope', [None, '', WORKSPACE_A, WORKSPACE_B])
def test_postgres_task_tenant_rls(task_rows, scope):
    dsn, _, _, ids = task_rows
    with psycopg.connect(runtime_role_dsn(dsn)) as db:
        if scope is not None:
            db.execute("SELECT set_config('app.workspace_id',%s,true)",(scope,))
        assert {row[0] for row in db.execute('SELECT id FROM sales_tasks')} == ({ids[0]} if scope == WORKSPACE_A else {ids[1]} if scope == WORKSPACE_B else set())
        foreign = ids[1] if scope == WORKSPACE_A else ids[0]
        assert db.execute("UPDATE sales_tasks SET user_message='forged' WHERE id=%s",(foreign,)).rowcount == 0


def test_postgres_dependency_composite_fk_rejects_other_project(task_rows):
    dsn, _, thread, ids = task_rows
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute("""INSERT INTO sales_task_dependencies(id,workspace_id,project_id,thread_id,task_id,source_id,source_version,kind,retention_class)
                VALUES(%s,%s,%s,%s,%s,%s,1,'document','durable')""",
                (uuid.uuid4(),WORKSPACE_A,PROJECT_B,thread,ids[0],uuid.uuid4()))


@pytest.mark.parametrize('payload', [{'text':'PRIVATE'}, {'state':'running','revision':None}, {'state':'running','revision':1,'body':'PRIVATE'}])
def test_postgres_event_rejects_untyped_or_private_payload(task_rows, payload):
    from psycopg.types.json import Jsonb
    dsn, _, thread, ids = task_rows
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("""INSERT INTO sales_task_events(id,workspace_id,project_id,thread_id,task_id,sequence,kind,payload)
                VALUES(%s,%s,%s,%s,%s,1,'state',%s)""",(uuid.uuid4(),WORKSPACE_A,PROJECT_A,thread,ids[0],Jsonb(payload)))


def test_postgres_preferences_alone_block_downgrade(thread_rows):
    dsn, user, thread, _ = thread_rows
    with psycopg.connect(dsn) as db:
        db.execute('''INSERT INTO conversation_thread_preferences(id,workspace_id,project_id,thread_id,owner_user_id,actor_id,pinned)
            VALUES(%s,%s,%s,%s,%s,%s,true)''',(uuid.uuid4(),WORKSPACE_A,PROJECT_A,thread,user,user))
    with pytest.raises(RuntimeError, match='preserve populated'):
        command.downgrade(config(),'0059_conversation_connections')
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT pinned FROM conversation_thread_preferences').fetchone()[0] is True
        assert db.execute("SELECT relforcerowsecurity FROM pg_class WHERE oid='conversation_thread_preferences'::regclass").fetchone()[0]


def append_in_transaction(dsn, task_id):
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.sales_tasks import append_event
    async def run():
        engine = create_async_engine(runtime_role_dsn(dsn).replace('postgresql://','postgresql+psycopg://'))
        try:
            async with tenant_session(engine, uuid.UUID(WORKSPACE_A)) as session:
                event = await append_event(session, task_id, 'error', {'code':'configuration_required','retryable':False})
                return event.sequence
        finally:
            await engine.dispose()
    return asyncio.run(run())


def test_postgres_simultaneous_append_has_unique_monotonic_sequences(task_rows):
    dsn, _, _, ids = task_rows
    with ThreadPoolExecutor(max_workers=4) as pool:
        sequences = list(pool.map(lambda _: append_in_transaction(dsn, ids[0]), range(8)))
    assert sorted(sequences) == list(range(1,9))
    with psycopg.connect(dsn) as db:
        event_sequences = [row[0] for row in db.execute('SELECT sequence FROM sales_task_events WHERE task_id=%s ORDER BY sequence',(ids[0],))]
        assert event_sequences == sorted(set(event_sequences)) == list(range(1,9))


def test_postgres_append_and_delete_running_task_preserves_events(task_rows):
    dsn, _, thread, ids = task_rows
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE sales_tasks SET state='running' WHERE id=%s",(ids[0],))
    def delete():
        with psycopg.connect(dsn) as db:
            with pytest.raises(psycopg.errors.CheckViolation):
                db.execute('DELETE FROM conversation_threads WHERE id=%s',(thread,))
    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(append_in_transaction, dsn, ids[0])
        deleter = pool.submit(delete)
        assert writer.result(timeout=15) == 1
        deleter.result(timeout=15)
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_task_events WHERE task_id=%s',(ids[0],)).fetchone()[0] == 1


def test_postgres_empty_downgrade_upgrade_fences(isolated_migrated):
    command.downgrade(config(),'0059_conversation_connections')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0059_conversation_connections'
        for service in ('search','model','contact'):
            assert db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0]
        assert all(db.execute('SELECT to_regclass(%s)',(table,)).fetchone()[0] is None for table in TABLES)
    command.upgrade(config(),'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == ScriptDirectory.from_config(config()).get_current_head()
        for service in ('search','model','contact'):
            assert db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0]


def test_postgres_populated_downgrade_preserves_data_and_force_rls(task_rows):
    dsn, _, _, ids = task_rows
    with pytest.raises(RuntimeError, match='preserve populated'):
        command.downgrade(config(),'0059_conversation_connections')
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT user_message FROM sales_tasks WHERE id=%s',(ids[0],)).fetchone()[0] == 'SYNTHETIC'
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == ScriptDirectory.from_config(config()).get_current_head()
        assert all(db.execute('SELECT relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()[0] for table in TABLES)


def test_sales_schema_has_single_additive_head():
    scripts = ScriptDirectory(str(SERVICE_ROOT / 'alembic'))
    assert scripts.get_heads() == ['0070_turn_rate_windows']
    assert scripts.get_revision('0060_sales_tasks').down_revision == '0059_conversation_connections'
    assert scripts.get_revision('0061_sales_outputs').down_revision == '0060_sales_tasks'


@pytest.fixture
def sales_readiness_db(isolated_seeded):
    with psycopg.connect(isolated_seeded) as owner:
        owner.execute('GRANT SELECT(version_num) ON public.alembic_version TO buyeros_api')
    return isolated_seeded


def inspect_sales(dsn, statements=None):
    from tests.test_schema_readiness_db import contract, inspect
    return inspect(dsn,contract(dsn,required_revisions=['0060_sales_tasks','0061_sales_outputs','0062_xverum_credits','0063_xverum_dispatch','0064_xverum_enrichment','0065_sales_lifecycle','0066_conversation_turns','0067_conversation_buyer','0068_conversation_turn_events','0069_turn_reconciliations','0070_turn_rate_windows'],compatible_heads=['0070_turn_rate_windows']),statements)


def test_postgres_review_r3_valid_sales_readiness_only_reads_catalogs(sales_readiness_db):
    statements = []
    result = inspect_sales(sales_readiness_db,statements)
    assert result.compatible, result.blockers
    assert len({check.code for check in result.checks}) == len(result.checks)
    assert all(sql.lstrip().upper().startswith(('SELECT','SET TRANSACTION')) for sql in statements)
    assert not any('SELECT PUBLIC.BUYEROS_SALES_DELETE_GUARD(' in sql.upper()
        or 'SELECT PUBLIC.BUYEROS_SALES_EVENT_VALID(' in sql.upper() for sql in statements)


@pytest.mark.parametrize('column',['output_ids','pending_review','user_message','arguments','owner_user_id','created_at','updated_at'])
def test_postgres_review_r3_missing_selected_column_is_not_ready(sales_readiness_db,column):
    with psycopg.connect(sales_readiness_db) as owner:
        owner.execute(psycopg.sql.SQL('ALTER TABLE public.sales_tasks DROP COLUMN {}').format(psycopg.sql.Identifier(column)))
    result = inspect_sales(sales_readiness_db)
    assert not result.compatible
    assert 'relation_columns_missing:public.sales_tasks' in result.blockers


@pytest.mark.parametrize('table,privilege',[
    ('sales_tasks','INSERT'), ('sales_tasks','UPDATE'), ('sales_task_events','INSERT'),
    ('sales_task_dependencies','INSERT'), ('conversation_thread_preferences','INSERT'),
    ('conversation_thread_preferences','UPDATE'), ('conversation_threads','UPDATE'), ('conversation_threads','DELETE'),
])
def test_postgres_review_r3_missing_write_privilege_is_not_ready(sales_readiness_db,table,privilege):
    with psycopg.connect(sales_readiness_db) as owner:
        owner.execute(psycopg.sql.SQL('REVOKE {} ON public.{} FROM buyeros_api').format(psycopg.sql.SQL(privilege),psycopg.sql.Identifier(table)))
    result = inspect_sales(sales_readiness_db)
    assert not result.compatible
    assert f'privilege_missing:public.{table}:{privilege}' in result.blockers


@pytest.mark.parametrize('fault,blocker',[
    ('validator_execute','function_missing_or_denied:public.buyeros_sales_event_valid(text,jsonb)'),
    ('validator_security','function_contract_mismatch:public.buyeros_sales_event_valid(text,jsonb)'),
    ('validator_search_path','function_contract_mismatch:public.buyeros_sales_event_valid(text,jsonb)'),
    ('event_check','sales_event_validation_constraint_missing'),
    ('trigger_disabled','trigger_missing_or_disabled:public.conversation_threads:sales_thread_delete_guard'),
    ('trigger_missing','trigger_missing_or_disabled:public.conversation_threads:sales_thread_delete_guard'),
    ('guard_security','function_contract_mismatch:public.buyeros_sales_delete_guard()'),
])
def test_postgres_review_r3_missing_event_or_delete_prerequisite_is_not_ready(sales_readiness_db,fault,blocker):
    with psycopg.connect(sales_readiness_db) as owner:
        if fault == 'validator_execute':
            owner.execute('REVOKE EXECUTE ON FUNCTION public.buyeros_sales_event_valid(text,jsonb) FROM buyeros_api')
        elif fault == 'validator_security':
            owner.execute('ALTER FUNCTION public.buyeros_sales_event_valid(text,jsonb) SECURITY DEFINER')
        elif fault == 'validator_search_path':
            owner.execute('ALTER FUNCTION public.buyeros_sales_event_valid(text,jsonb) SET search_path=public,pg_catalog')
        elif fault == 'event_check':
            constraints = owner.execute("""SELECT conname FROM pg_constraint WHERE conrelid='public.sales_task_events'::regclass
                AND contype='c' AND pg_get_constraintdef(oid) LIKE '%buyeros_sales_event_valid%'""").fetchall()
            assert constraints
            for name, in constraints:
                owner.execute(psycopg.sql.SQL('ALTER TABLE public.sales_task_events DROP CONSTRAINT {}').format(psycopg.sql.Identifier(name)))
        elif fault == 'trigger_disabled':
            owner.execute('ALTER TABLE public.conversation_threads DISABLE TRIGGER sales_thread_delete_guard')
        elif fault == 'trigger_missing':
            owner.execute('DROP TRIGGER sales_thread_delete_guard ON public.conversation_threads')
        elif fault == 'guard_security':
            owner.execute('ALTER FUNCTION public.buyeros_sales_delete_guard() SECURITY DEFINER')
    result = inspect_sales(sales_readiness_db)
    assert not result.compatible
    assert blocker in result.blockers
