"""C61-06 restricted discovery function never changes tenant RLS."""
import asyncio
import uuid
import psycopg
import pytest
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from tests.conftest import runtime_role_dsn
from tests.test_workspace_listing_db import directory_case

FUNCTION='public.buyeros_workspace_directory(uuid,bigint,integer)'


def test_directory_function_acl_keeps_tenant_policy_and_runtime_nonprivileged(directory_case):
    case=directory_case
    with psycopg.connect(case['dsn']) as owner:
        function=owner.execute("SELECT p.prosecdef,p.provolatile,p.proconfig,pg_get_userbyid(p.proowner) "
            "FROM pg_proc p WHERE p.oid=to_regprocedure(%s)",(FUNCTION,)).fetchone()
        assert function is not None, 'restricted readonly directory function missing'
        assert function[0] is True and function[1]=='s'
        assert 'search_path=pg_catalog, public' in function[2]
        policies=owner.execute("SELECT policyname,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' AND tablename='memberships'").fetchall()
        assert len(policies)==1 and policies[0][:2]==('tenant_isolation','ALL')
        assert policies[0][2]==policies[0][3] and "app.workspace_id" in policies[0][2] and "app.user_id" not in policies[0][2]
        assert owner.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.memberships'::regclass").fetchone()==(True,True)
        for role,allowed in (('buyeros_api',True),('buyeros_worker',False)):
            assert owner.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=%s',(role,)).fetchone()==(False,False)
            assert owner.execute("SELECT has_function_privilege(%s,%s,'EXECUTE')",(role,FUNCTION)).fetchone()[0] is allowed
        assert owner.execute("SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND indexname='ix_memberships_active_user_workspace'").fetchone()[0]==1


@pytest.mark.parametrize('context',[None,'','not-a-uuid','different'])
def test_directory_function_rejects_missing_malformed_or_forged_actor(directory_case,context):
    case=directory_case;case['add'](0)
    with psycopg.connect(runtime_role_dsn(case['dsn'])) as runtime:
        if context is not None:
            actor=str(case['users'][1]) if context=='different' else context
            runtime.execute("SELECT set_config('app.user_id',%s,true)",(actor,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute('SELECT public.buyeros_workspace_directory(%s,0,20)',(case['users'][0],))


def test_directory_session_is_readonly_and_one_snapshot_with_next_request_revocation(directory_case):
    from buyeros_api.db.session import workspace_directory_session
    from buyeros_api.services.workspace_directory import list_authorized_workspaces
    case=directory_case;own,member=case['add'](0)
    engine=create_async_engine(runtime_role_dsn(case['dsn']).replace('postgresql://','postgresql+psycopg://',1))
    revoked=False
    def revoke_after_function(conn,cursor,statement,parameters,context,many):
        nonlocal revoked
        if 'SELECT public.buyeros_workspace_directory' in statement and not revoked:
            revoked=True
            with psycopg.connect(case['dsn'],autocommit=True) as owner:
                owner.execute('UPDATE memberships SET active=false WHERE id=%s',(member,))
    async def exercise():
        try:
            async with workspace_directory_session(engine) as session:
                assert (await session.execute(text('SHOW transaction_read_only'))).scalar_one()=='on'
                assert (await session.execute(text('SHOW transaction_isolation'))).scalar_one()=='repeatable read'
                event.listen(engine.sync_engine,'after_cursor_execute',revoke_after_function)
                try:page=await list_authorized_workspaces(session,user_id=case['users'][0],offset=0,limit=20)
                finally:event.remove(engine.sync_engine,'after_cursor_execute',revoke_after_function)
                assert revoked and page['total']==1 and [r['id'] for r in page['items']]==[str(own)]
            async with workspace_directory_session(engine) as session:
                assert (await list_authorized_workspaces(session,user_id=case['users'][0],offset=0,limit=20))['total']==0
            with pytest.raises(DBAPIError) as denied:
                async with workspace_directory_session(engine) as session:
                    await session.execute(text("UPDATE users SET display_name='forbidden' WHERE id=:actor"),{'actor':case['users'][0]})
            assert isinstance(denied.value.orig,psycopg.errors.ReadOnlySqlTransaction)
        finally:await engine.dispose()
    asyncio.run(exercise())


def test_directory_function_rejects_correct_actor_in_write_transaction(directory_case):
    case=directory_case
    with psycopg.connect(runtime_role_dsn(case['dsn'])) as runtime:
        runtime.execute("SELECT set_config('app.user_id',%s,true)",(str(case['users'][0]),))
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            runtime.execute('SELECT public.buyeros_workspace_directory(%s,0,20)',(case['users'][0],))


@pytest.mark.parametrize('offset,limit',[(-1,20),(0,0),(0,101),(None,20),(0,None)])
def test_directory_function_enforces_pagination_at_database_boundary(directory_case,offset,limit):
    case=directory_case
    with psycopg.connect(runtime_role_dsn(case['dsn'])) as runtime:
        runtime.execute('SET TRANSACTION READ ONLY')
        runtime.execute("SELECT set_config('app.user_id',%s,true)",(str(case['users'][0]),))
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            runtime.execute('SELECT public.buyeros_workspace_directory(%s,%s,%s)',(case['users'][0],offset,limit))


def test_directory_optional_expansion_round_trip_preserves_canonical_rows(directory_case,monkeypatch):
    from alembic import command
    from alembic.config import Config
    from buyeros_api.settings import get_settings
    from tests.conftest import ALEMBIC_INI,SERVICE_ROOT
    case=directory_case;case['add'](0);case['add'](1)
    config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    def snapshot():
        with psycopg.connect(case['dsn']) as owner:
            return (
                owner.execute('SELECT id,issuer,subject FROM users WHERE id=ANY(%s) ORDER BY id',(case['users'],)).fetchall(),
                owner.execute('SELECT id,workspace_id,user_id,roles,active FROM memberships WHERE user_id=ANY(%s) ORDER BY id',(case['users'],)).fetchall(),
                owner.execute("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid IN ('public.users'::regclass,'public.memberships'::regclass) ORDER BY conname").fetchall(),
                owner.execute("SELECT policyname,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' AND tablename='memberships'").fetchall())
    before=snapshot()
    with monkeypatch.context() as context:
        context.setenv('BUYEROS_DATABASE_URL',case['dsn']);get_settings.cache_clear()
        try:
            command.downgrade(config,'0037_bulk_manifests')
            with psycopg.connect(case['dsn']) as owner:
                assert owner.execute('SELECT to_regprocedure(%s)',(FUNCTION,)).fetchone()==(None,)
                assert owner.execute("SELECT to_regclass('public.ix_memberships_active_user_workspace')").fetchone()==(None,)
                assert owner.execute('SELECT version_num FROM alembic_version').fetchone()==('0037_bulk_manifests',)
            assert snapshot()==before
        finally:
            command.upgrade(config,'head');get_settings.cache_clear()
    assert snapshot()==before
    with psycopg.connect(case['dsn']) as owner:
        assert owner.execute('SELECT version_num FROM alembic_version').fetchone()==('0038_c61_workspace_directory',)
        assert owner.execute("SELECT has_function_privilege('buyeros_api',%s,'EXECUTE'),has_function_privilege('buyeros_worker',%s,'EXECUTE')",(FUNCTION,FUNCTION)).fetchone()==(True,False)
        assert owner.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.memberships'::regclass").fetchone()==(True,True)
