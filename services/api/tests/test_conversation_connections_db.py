"""Drive schema fences, data class, and two-tenant forced RLS."""
import uuid
from urllib.parse import urlsplit, urlunsplit
import psycopg
import pytest
from psycopg.types.json import Jsonb
from alembic import command
from tests.conftest import runtime_role_dsn
from tests.test_conversation_threads_db import config
from tests.test_buyer_review_db import WORKSPACE_A,WORKSPACE_B,PROJECT_A,PROJECT_B

TABLE='conversation_drive_connections'
HEAD='0059_conversation_connections'


@pytest.fixture
def rows(seeded):
    user=uuid.uuid4();ids=[uuid.uuid4(),uuid.uuid4()]
    with psycopg.connect(seeded) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'drive-fixture',%s)",(user,str(user)))
        for ident,ws,project in [(ids[0],WORKSPACE_A,PROJECT_A),(ids[1],WORKSPACE_B,PROJECT_B)]:
            db.execute(f'INSERT INTO {TABLE}(id,workspace_id,project_id,configured_by,generation) VALUES(%s,%s,%s,%s,%s)',(ident,ws,project,user,uuid.uuid4()))
    yield seeded,user,ids
    with psycopg.connect(seeded) as db:
        db.execute(f'DELETE FROM {TABLE}');db.execute('DELETE FROM users WHERE id=%s',(user,))


def test_force_rls_exact_privileges_and_receipt_fences(migrated):
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(TABLE,)).fetchone()==(True,True)
        policy=db.execute('SELECT qual,with_check FROM pg_policies WHERE tablename=%s',(TABLE,)).fetchone()
        assert all("NULLIF(current_setting('app.workspace_id'" in part for part in policy)
        for role in ['buyeros_api','buyeros_worker']:
            for verb in ['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']:
                assert db.execute('SELECT has_table_privilege(%s,%s,%s)',(role,TABLE,verb)).fetchone()[0]==(role=='buyeros_api' and verb in {'SELECT','INSERT','UPDATE','DELETE'})
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]==HEAD
        assert all(db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0] for service in ['search','model','contact'])


@pytest.mark.parametrize('scope',[None,'',WORKSPACE_A,WORKSPACE_B])
def test_two_tenant_isolation_forged_read_write_and_insert(rows,scope):
    dsn,user,ids=rows
    with psycopg.connect(runtime_role_dsn(dsn)) as db:
        if scope is not None:db.execute("SELECT set_config('app.workspace_id',%s,true)",(scope,))
        expected={ids[0]} if scope==WORKSPACE_A else {ids[1]} if scope==WORKSPACE_B else set()
        assert {row[0] for row in db.execute(f'SELECT id FROM {TABLE}')}==expected
        other=ids[1] if scope==WORKSPACE_A else ids[0]
        assert db.execute(f'UPDATE {TABLE} SET connected=true WHERE id=%s',(other,)).rowcount==0
        assert db.execute(f'DELETE FROM {TABLE} WHERE id=%s',(other,)).rowcount==0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute(f'INSERT INTO {TABLE}(id,workspace_id,project_id,configured_by,generation) VALUES(%s,%s,%s,%s,%s)',(uuid.uuid4(),WORKSPACE_B if scope==WORKSPACE_A else WORKSPACE_A,PROJECT_B if scope==WORKSPACE_A else PROJECT_A,user,uuid.uuid4()))


def test_composite_project_fk_rejects_forged_tenant(rows):
    dsn,_,ids=rows
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):db.execute(f'UPDATE {TABLE} SET project_id=%s WHERE id=%s',(PROJECT_B,ids[0]))


@pytest.mark.parametrize('value',[
    {},[{'id':'one','label':'private.pdf'}],[{'id':'one','label':'Google Drive folder','token':'secret'}],
    [{'id':'one','label':'Google Drive folder','body':'private'}],[{'id':'https://public.invalid','label':'Google Drive folder'}],
    [{'id':'one','label':'Google Drive folder'}]*2,[{'id':str(i),'label':'Google Drive folder'} for i in range(21)],
    [{'id':None,'label':'Google Drive folder'}],[{'id':'one'}],['one'],
])
def test_db_rejects_private_content_unknown_fields_bad_ids_and_caps(rows,value):
    dsn,_,ids=rows
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.CheckViolation):db.execute(f'UPDATE {TABLE} SET connected=true,folders=%s WHERE id=%s',(Jsonb(value),ids[0]))


def test_empty_up_down_up_restores_validator_and_fences(isolated_migrated):
    command.downgrade(config(),'0058_conversation_threads')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT to_regclass(%s)',(TABLE,)).fetchone()[0] is None
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0058_conversation_threads'
        assert all(db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0] for service in ['search','model','contact'])
    command.upgrade(config(),'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]==HEAD
        assert all(db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0] for service in ['search','model','contact'])


@pytest.mark.parametrize('kind',['connection','reference'])
def test_populated_downgrade_refuses_and_keeps_force_rls(isolated_seeded,kind):
    user=uuid.uuid4()
    with psycopg.connect(isolated_seeded) as db:
        db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'drive-rollback',%s)",(user,str(user)))
        if kind=='connection':
            db.execute(f'INSERT INTO {TABLE}(id,workspace_id,project_id,configured_by,generation) VALUES(%s,%s,%s,%s,%s)',(uuid.uuid4(),WORKSPACE_A,PROJECT_A,user,uuid.uuid4()))
        else:
            db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,template_id,title,sources) VALUES(%s,%s,%s,%s,'custom','synthetic',%s)",(uuid.uuid4(),WORKSPACE_A,PROJECT_A,user,Jsonb([{'id':f'drive:{uuid.uuid4()}:file_one','label':'Google Drive item'}])))
    with pytest.raises(RuntimeError,match='preserve populated'):command.downgrade(config(),'0058_conversation_threads')
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]==HEAD
        assert db.execute('SELECT relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(TABLE,)).fetchone()[0]


@pytest.mark.parametrize('retained_reference',[False,True])
def test_non_bypass_owner_downgrade_checks_hidden_references_and_preserves_rls(isolated_seeded,monkeypatch,retained_reference):
    from buyeros_api.settings import get_settings
    dsn=isolated_seeded
    role='drive_owner_'+uuid.uuid4().hex[:12]
    thread_id,user=uuid.uuid4(),uuid.uuid4()
    source=[{'id':f'drive:{uuid.uuid4()}:file_one','label':'Google Drive item'}]
    with psycopg.connect(dsn) as db:
        db.execute(psycopg.sql.SQL("CREATE ROLE {} LOGIN PASSWORD 'test-only' NOSUPERUSER NOBYPASSRLS").format(psycopg.sql.Identifier(role)))
        db.execute(psycopg.sql.SQL('GRANT USAGE,CREATE ON SCHEMA public TO {}').format(psycopg.sql.Identifier(role)))
        db.execute(psycopg.sql.SQL('GRANT SELECT,UPDATE,DELETE ON alembic_version TO {}').format(psycopg.sql.Identifier(role)))
        if retained_reference:
            db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'drive-owner-rollback',%s)",(user,str(user)))
            db.execute("INSERT INTO conversation_threads(id,workspace_id,project_id,owner_user_id,template_id,title,sources) VALUES(%s,%s,%s,%s,'custom','synthetic',%s)",(thread_id,WORKSPACE_A,PROJECT_A,user,Jsonb(source)))
        for table in [TABLE,'conversation_threads']:
            db.execute(psycopg.sql.SQL('ALTER TABLE {} OWNER TO {}').format(psycopg.sql.Identifier(table),psycopg.sql.Identifier(role)))
        for name,signature in [('buyeros_drive_folders_valid','jsonb'),('buyeros_thread_refs_valid','jsonb,text'),
                *[(f'buyeros_{service}_receipts_writable','') for service in ['search','model','contact']]]:
            db.execute(psycopg.sql.SQL('ALTER FUNCTION {}({}) OWNER TO {}').format(psycopg.sql.Identifier(name),psycopg.sql.SQL(signature),psycopg.sql.Identifier(role)))
    parts=urlsplit(dsn)
    owner_dsn=urlunsplit(parts._replace(netloc=f'{role}:test-only@{parts.hostname}:{parts.port}'))
    with psycopg.connect(owner_dsn) as db:
        assert db.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()==(False,False)
        assert db.execute("SELECT relowner=current_user::regrole FROM pg_class WHERE oid='conversation_threads'::regclass").fetchone()==(True,)
        assert db.execute('SELECT count(*) FROM conversation_threads').fetchone()==(0,)
    monkeypatch.setenv('BUYEROS_DATABASE_MIGRATION_URL',owner_dsn)
    get_settings.cache_clear()
    try:
        if retained_reference:
            with pytest.raises(RuntimeError,match='preserve populated'):
                command.downgrade(config(),'0058_conversation_threads')
        else:
            command.downgrade(config(),'0058_conversation_threads')
        with psycopg.connect(dsn) as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]==(HEAD if retained_reference else '0058_conversation_threads')
            assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='conversation_threads'::regclass").fetchone()==(True,True)
            if retained_reference:
                assert db.execute('SELECT sources FROM conversation_threads WHERE id=%s',(thread_id,)).fetchone()[0]==source
                assert db.execute('SELECT relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(TABLE,)).fetchone()==(True,)
            assert all(db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0] for service in ['search','model','contact'])
    finally:
        get_settings.cache_clear()
