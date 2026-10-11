"""Fresh owned database: real expansion, backfill, retained rollback and re-upgrade."""
import uuid
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from buyeros_api.api.auth import Principal
from buyeros_api.settings import get_settings
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, _require_disposable_test_dsn, runtime_role_dsn, _start_container, _docker, _unavailable
from tests.test_identity_linking_db import run

@pytest.fixture
def fresh_identity_db():
    # 0002 owns cluster-wide role creation, so a second database in the same
    # cluster is not a fresh-install fixture. Use a separate owned container.
    try:name,dsn=_start_container()
    except RuntimeError as error:_unavailable(str(error))
    _require_disposable_test_dsn(dsn)
    try:yield dsn
    finally:_docker('rm','-f',name)

def snapshot(dsn,user):
    with psycopg.connect(dsn) as owner:
        return (owner.execute('SELECT id,issuer,subject,display_name FROM users WHERE id=%s',(user,)).fetchall(),
                owner.execute('SELECT id,workspace_id,user_id,roles,active,version FROM memberships WHERE user_id=%s',(user,)).fetchall(),
                owner.execute('SELECT id,workspace_id,user_id,locale,default_markets,version FROM workspace_preferences WHERE user_id=%s',(user,)).fetchall(),
                owner.execute("SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE confrelid='public.users'::regclass ORDER BY conrelid,conname").fetchall(),
                owner.execute("SELECT tablename,policyname,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname").fetchall(),
                owner.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname='buyeros_api'").fetchall())

def test_fresh_0038_backfill_and_retained_rollback_preserve_canonical_history(fresh_identity_db,monkeypatch):
    from buyeros_api.services.identity_linking import create_canonical_user
    from buyeros_api.services.identity_resolver import resolve_user_id
    dsn=fresh_identity_db;legacy=uuid.uuid4();workspace=uuid.uuid4()
    config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    with monkeypatch.context() as context:
        context.setenv('BUYEROS_DATABASE_URL',dsn);get_settings.cache_clear()
        try:
            command.upgrade(config,'0038_c61_workspace_directory')
            with psycopg.connect(dsn) as owner:
                owner.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
                assert owner.execute("SELECT to_regclass('public.user_identities')").fetchone()==(None,)
                owner.execute("INSERT INTO workspaces(id,name) VALUES (%s,'Identity migration fixture')",(workspace,))
                owner.execute("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,'urn:c61:legacy','original-sub','same@example.test')",(legacy,))
                owner.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) VALUES (%s,%s,%s,'{viewer}',true,1)",(uuid.uuid4(),workspace,legacy))
                owner.execute("INSERT INTO workspace_preferences(id,workspace_id,user_id,locale,default_markets,version) VALUES (%s,%s,%s,'zh-HK','{HK}',1)",(uuid.uuid4(),workspace,legacy))
            before=snapshot(dsn,legacy)
            command.upgrade(config,'0039_c61_user_identities')
            after=snapshot(dsn,legacy)
            # The sole new FK belongs to the additive identity table. All
            # previous definitions, policies, flags and concrete history stay exact.
            assert after[:3]==before[:3] and after[4:]==before[4:]
            assert [x for x in after[3] if x[0]!='user_identities']==before[3]
            with psycopg.connect(dsn) as owner:
                assert owner.execute('SELECT issuer,subject,user_id,proof_ref FROM user_identities').fetchall()==[('urn:c61:legacy','original-sub',legacy,'legacy-backfill:'+str(legacy))]
                assert owner.execute('SELECT count(*) FROM users u LEFT JOIN user_identities i ON i.issuer=u.issuer AND i.subject=u.subject AND i.user_id=u.id WHERE i.user_id IS NULL').fetchone()==(0,)
            principal=Principal('urn:c61:neon-only','new-'+uuid.uuid4().hex)
            new=run(dsn,lambda s:create_canonical_user(s,principal=principal,proof_ref='verified-new-principal'))
            assert run(runtime_role_dsn(dsn),lambda s:resolve_user_id(s,principal))==new
            with psycopg.connect(dsn) as owner:
                ids=owner.execute('SELECT id,issuer,subject FROM users ORDER BY id').fetchall()
                identities=owner.execute('SELECT issuer,subject,user_id,proof_ref,status,version FROM user_identities ORDER BY issuer,subject').fetchall()
            command.downgrade(config,'0038_c61_workspace_directory')
            assert run(runtime_role_dsn(dsn),lambda s:resolve_user_id(s,principal))==new
            with psycopg.connect(dsn) as owner:
                assert owner.execute('SELECT version_num FROM alembic_version').fetchone()==('0038_c61_workspace_directory',)
                assert owner.execute('SELECT id,issuer,subject FROM users ORDER BY id').fetchall()==ids
                assert owner.execute('SELECT issuer,subject,user_id,proof_ref,status,version FROM user_identities ORDER BY issuer,subject').fetchall()==identities
            command.upgrade(config,'0039_c61_user_identities')
            assert snapshot(dsn,legacy)==after
            with psycopg.connect(dsn) as owner:
                assert owner.execute('SELECT version_num FROM alembic_version').fetchone()==('0039_c61_user_identities',)
                assert owner.execute('SELECT id,issuer,subject FROM users ORDER BY id').fetchall()==ids
                assert owner.execute('SELECT issuer,subject,user_id,proof_ref,status,version FROM user_identities ORDER BY issuer,subject').fetchall()==identities
        finally:get_settings.cache_clear()


def test_identity_revision_preserves_runtime_off_and_rejects_unknown_future_head(fresh_identity_db,monkeypatch):
    from buyeros_api.services.worker_recovery import set_execution_runtime
    dsn=fresh_identity_db;config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    with monkeypatch.context() as context:
        context.setenv('BUYEROS_DATABASE_URL',dsn);get_settings.cache_clear()
        try:
            command.upgrade(config,'head')
            with psycopg.connect(dsn) as owner:
                before=owner.execute('SELECT backend,enabled,epoch,active_until FROM worker_runtime_control').fetchall()
            result=set_execution_runtime(dsn,expected_epoch=1,backend='celery',enabled=False,reason='Identity schema dry-run')
            assert result
            with psycopg.connect(dsn) as owner:
                assert owner.execute('SELECT backend,enabled,epoch,active_until FROM worker_runtime_control').fetchall()==before
                owner.execute("UPDATE alembic_version SET version_num='0099_unreviewed_future'")
            with pytest.raises(ValueError,match='compatible'):
                set_execution_runtime(dsn,expected_epoch=1,backend='celery',enabled=False,reason='Reject unknown future')
            with psycopg.connect(dsn) as owner:
                assert owner.execute('SELECT backend,enabled,epoch,active_until FROM worker_runtime_control').fetchall()==before
        finally:get_settings.cache_clear()


def test_supported_0038_upgrade_to_current_head_preserves_history_and_restricted_runtime(fresh_identity_db, monkeypatch):
    from alembic.script import ScriptDirectory
    from buyeros_api.services.identity_linking import create_canonical_user
    from buyeros_api.services.identity_resolver import resolve_user_id

    dsn = fresh_identity_db
    config = Config(str(ALEMBIC_INI))
    config.set_main_option('script_location', str(SERVICE_ROOT / 'alembic'))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert heads == ['0050_c61_delivery_authorizations']
    legacy, workspace, membership, preference = (uuid.uuid4() for _ in range(4))
    principal = Principal('urn:c61:neon-only', 'supported-upgrade-' + uuid.uuid4().hex)
    with monkeypatch.context() as context:
        context.setenv('BUYEROS_DATABASE_URL', dsn)
        get_settings.cache_clear()
        try:
            command.upgrade(config, '0038_c61_workspace_directory')
            with psycopg.connect(dsn) as owner:
                owner.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
                owner.execute("INSERT INTO workspaces(id,name) VALUES (%s,'C61 supported migration')", (workspace,))
                owner.execute("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,'urn:c61:legacy','supported-original','fixture@example.test')", (legacy,))
                owner.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) VALUES (%s,%s,%s,'{viewer}',true,1)", (membership, workspace, legacy))
                owner.execute("INSERT INTO workspace_preferences(id,workspace_id,user_id,locale,default_markets,version) VALUES (%s,%s,%s,'zh-HK','{HK}',1)", (preference, workspace, legacy))
            before = snapshot(dsn, legacy)
            command.upgrade(config, '0039_c61_user_identities')
            new_user = run(dsn, lambda session: create_canonical_user(session, principal=principal, proof_ref='owned-supported-migration-proof'))
            with psycopg.connect(dsn) as owner:
                identities_before = owner.execute('SELECT issuer,subject,user_id,proof_ref,status,version FROM user_identities ORDER BY issuer,subject').fetchall()
                role_flags_before = owner.execute("SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname IN ('buyeros_api','buyeros_worker') ORDER BY rolname").fetchall()
            assert role_flags_before == [('buyeros_api', False, False), ('buyeros_worker', False, False)]
            command.upgrade(config, 'head')
            after = snapshot(dsn, legacy)
            assert after[:3] == before[:3]
            assert set(before[3]) <= set(after[3])
            assert run(runtime_role_dsn(dsn), lambda session: resolve_user_id(session, principal)) == new_user
            with psycopg.connect(dsn) as owner:
                assert owner.execute('SELECT version_num FROM alembic_version').fetchone() == (heads[0],)
                assert owner.execute('SELECT issuer,subject,user_id,proof_ref,status,version FROM user_identities ORDER BY issuer,subject').fetchall() == identities_before
                assert owner.execute("SELECT rolname,rolsuper,rolbypassrls FROM pg_roles WHERE rolname IN ('buyeros_api','buyeros_worker') ORDER BY rolname").fetchall() == role_flags_before
                assert owner.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.delivery_authorizations'::regclass").fetchone() == (True, True)
                assert owner.execute("SELECT rolname,has_table_privilege(rolname,'delivery_authorizations','SELECT'),has_table_privilege(rolname,'delivery_authorizations','INSERT'),has_table_privilege(rolname,'delivery_authorizations','UPDATE'),has_table_privilege(rolname,'delivery_authorizations','DELETE') FROM pg_roles WHERE rolname IN ('buyeros_api','buyeros_worker') ORDER BY rolname").fetchall() == [('buyeros_api', True, True, False, False), ('buyeros_worker', True, True, False, False)]
        finally:
            get_settings.cache_clear()
