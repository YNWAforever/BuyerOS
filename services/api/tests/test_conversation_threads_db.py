"""Stage 3 schema invariants exercised through PostgreSQL and runtime roles."""
import uuid
import psycopg
import pytest
from psycopg.types.json import Jsonb
from alembic import command
from alembic.config import Config
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, runtime_role_dsn
from tests.test_buyer_review_db import WORKSPACE_A, WORKSPACE_B, PROJECT_A, PROJECT_B

TABLES=('conversation_threads','conversation_thread_messages','conversation_thread_shares')


def config():
    value=Config(str(ALEMBIC_INI));value.set_main_option('script_location',str(SERVICE_ROOT/'alembic'));return value


@pytest.fixture
def thread_rows(seeded):
    user,first,second=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    grantee=uuid.uuid4()
    with psycopg.connect(seeded) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'thread-db-fixture',%s)",(grantee,str(grantee)))
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'thread-db-fixture',%s)",(user,str(user)))
        for ident,workspace,project in [(first,WORKSPACE_A,PROJECT_A),(second,WORKSPACE_B,PROJECT_B)]:
            db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,template_id,title) VALUES(%s,%s,%s,%s,'custom','synthetic')",(ident,workspace,project,user))
            db.execute("INSERT INTO conversation_thread_messages(id,workspace_id,project_id,thread_id,owner_user_id,author_user_id,text) VALUES(gen_random_uuid(),%s,%s,%s,%s,%s,'synthetic')",(workspace,project,ident,user,user))
            db.execute("INSERT INTO conversation_thread_shares(id,workspace_id,project_id,thread_id,owner_user_id,grantee_user_id,granted_by,role) VALUES(gen_random_uuid(),%s,%s,%s,%s,%s,%s,'viewer')",(workspace,project,ident,user,grantee,user))
    yield seeded,user,first,second
    with psycopg.connect(seeded) as db:
        db.execute('DELETE FROM conversation_threads');db.execute('DELETE FROM users WHERE id IN (%s,%s)',(user,grantee))


@pytest.mark.parametrize('table',TABLES)
def test_force_rls_policy_and_exact_grants(migrated,table):
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()==(True,True)
        policy=db.execute('SELECT qual,with_check FROM pg_policies WHERE tablename=%s AND policyname=%s',(table,'tenant_isolation')).fetchone()
        assert policy and all("NULLIF(current_setting('app.workspace_id'" in value for value in policy)
        for verb in ['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']:
            assert not db.execute('SELECT has_table_privilege(%s,%s,%s)',('buyeros_worker',table,verb)).fetchone()[0]
            expected=verb in ({'SELECT','INSERT'} if table=='conversation_thread_messages' else {'SELECT','INSERT','UPDATE','DELETE'})
            assert db.execute('SELECT has_table_privilege(%s,%s,%s)',('buyeros_api',table,verb)).fetchone()[0]==expected


@pytest.mark.parametrize('scope',[None,'',WORKSPACE_A,WORKSPACE_B])
def test_two_tenant_rls_and_forged_read_update_delete(thread_rows,scope):
    dsn,user,first,second=thread_rows
    with psycopg.connect(runtime_role_dsn(dsn)) as db:
        if scope is not None:db.execute("SELECT set_config('app.workspace_id',%s,true)",(scope,))
        ids={row[0] for row in db.execute('SELECT id FROM conversation_threads')}
        assert ids==({first} if scope==WORKSPACE_A else {second} if scope==WORKSPACE_B else set())
        for table in TABLES[1:]:
            child_ids={row[0] for row in db.execute(f'SELECT thread_id FROM {table}')}
            assert child_ids==ids
        foreign=second if scope==WORKSPACE_A else first
        assert db.execute('UPDATE conversation_threads SET title=%s WHERE id=%s',('forged',foreign)).rowcount==0
        assert db.execute('DELETE FROM conversation_threads WHERE id=%s',(foreign,)).rowcount==0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,template_id,title) VALUES(%s,%s,%s,%s,'custom','forged')",(uuid.uuid4(),WORKSPACE_B if scope==WORKSPACE_A else WORKSPACE_A,PROJECT_B if scope==WORKSPACE_A else PROJECT_A,user))


@pytest.mark.parametrize('table',TABLES[1:])
def test_children_reject_cross_project_or_tenant(thread_rows,table):
    dsn,user,first,_=thread_rows
    with psycopg.connect(dsn) as db:
        for workspace,project in [(WORKSPACE_B,PROJECT_B),(WORKSPACE_A,PROJECT_B)]:
            extra='author_user_id,text' if table.endswith('messages') else 'grantee_user_id,granted_by,role'
            values='%s,\'synthetic\'' if table.endswith('messages') else '%s,%s,\'viewer\''
            other=uuid.uuid4()
            db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'thread-db-fixture',%s)",(other,str(other)))
            args=(uuid.uuid4(),workspace,project,first,user,user) if table.endswith('messages') else (uuid.uuid4(),workspace,project,first,user,other,user)
            with pytest.raises(psycopg.errors.ForeignKeyViolation):
                with db.transaction():db.execute(f'INSERT INTO {table}(id,workspace_id,project_id,thread_id,owner_user_id,{extra}) VALUES(%s,%s,%s,%s,%s,{values})',args)
            db.execute('DELETE FROM users WHERE id=%s',(other,))


@pytest.mark.parametrize('column,value',[
    ('title',''),('title','x'*81),('template_id','unknown'),('version',0),
    ('sources',{}),('sources',[{'id':'document:d','label':'secret.pdf'}]),
    ('sources',[{'id':'document:d','label':'Offer document','text':'private'}]),
    ('sources',[{'id':'document:d','label':'Offer document'}]*2),
    ('sources',[{'id':f'document:{i}','label':'Offer document'} for i in range(101)]),
    ('runs',[{'id':str(uuid.uuid4()),'label':'Research run','status':'unknown'}]),
    ('runs',[{'id':str(uuid.uuid4()),'label':'Research run','status':'queued','body':'private'}]),
])
def test_db_checks_enforce_bounded_reference_data_class(thread_rows,column,value):
    dsn,_,first,_=thread_rows
    with psycopg.connect(dsn) as db:
        with pytest.raises((psycopg.errors.CheckViolation,psycopg.errors.StringDataRightTruncation)):
            db.execute(f'UPDATE conversation_threads SET {column}=%s WHERE id=%s',(Jsonb(value) if column in {'sources','runs'} else value,first))


@pytest.mark.parametrize('text',['','  ','x'*4001])
def test_note_bounds(thread_rows,text):
    dsn,user,first,_=thread_rows
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute('INSERT INTO conversation_thread_messages(id,workspace_id,project_id,thread_id,owner_user_id,author_user_id,text) VALUES(%s,%s,%s,%s,%s,%s,%s)',(uuid.uuid4(),WORKSPACE_A,PROJECT_A,first,user,user,text))


def test_owner_cannot_be_grantee(thread_rows):
    dsn,user,first,_=thread_rows
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("INSERT INTO conversation_thread_shares(id,workspace_id,project_id,thread_id,owner_user_id,grantee_user_id,granted_by,role) VALUES(%s,%s,%s,%s,%s,%s,%s,'viewer')",(uuid.uuid4(),WORKSPACE_A,PROJECT_A,first,user,user,user))


def test_empty_downgrade_upgrade_repoints_all_receipt_fences(isolated_migrated):
    cfg=config()
    command.downgrade(cfg,'0057_conversation_model')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0057_conversation_model'
        assert all(db.execute('SELECT to_regclass(%s)',(table,)).fetchone()[0] is None for table in TABLES)
        assert all(db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0] for service in ['search','model','contact'])
    command.upgrade(cfg,'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0059_conversation_connections'
        assert all(db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0] for service in ['search','model','contact'])


def test_populated_downgrade_refuses_and_preserves_rls(isolated_seeded):
    ident,user=uuid.uuid4(),uuid.uuid4()
    with psycopg.connect(isolated_seeded) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'thread-migration-fixture',%s)",(user,str(user)))
        db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,template_id,title) VALUES(%s,%s,%s,%s,'custom','preserved')",(ident,WORKSPACE_A,PROJECT_A,user))
    with pytest.raises(RuntimeError,match='preserve populated'):
        command.downgrade(config(),'0057_conversation_model')
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT title FROM conversation_threads WHERE id=%s',(ident,)).fetchone()[0]=='preserved'
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0059_conversation_connections'
        assert all(db.execute('SELECT relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()[0] for table in TABLES)
