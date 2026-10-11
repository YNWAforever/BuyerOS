"""C61-32 named-branch shape rehearsal; never a production migration claim."""
import uuid
import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import ProgrammingError
from buyeros_api.api.auth import Principal
from buyeros_api.settings import get_settings
from buyeros_api.services.identity_resolver import resolve_user_id
from buyeros_api.services.workspace_directory import list_authorized_workspaces
from tests.conftest import ALEMBIC_INI, SERVICE_ROOT, runtime_role_dsn
from tests.test_identity_migration_db import fresh_identity_db, snapshot
from tests.test_identity_linking_db import run


def test_0033_missing_relation_rehearsal_preserves_canonical_history(fresh_identity_db,monkeypatch):
    dsn=fresh_identity_db
    config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    monkeypatch.setenv('BUYEROS_DATABASE_URL',dsn);monkeypatch.setenv('BUYEROS_DATABASE_MIGRATION_URL',dsn)
    get_settings.cache_clear()
    try:
        command.upgrade(config,'0033_api_rate_windows')
        user,workspace,membership,preference=(uuid.uuid4() for _ in range(4))
        principal=Principal('urn:c61:legacy-recovery','owned-0033-'+str(user))
        with psycopg.connect(dsn) as owner:
            owner.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
            owner.execute("INSERT INTO workspaces(id,name) VALUES (%s,'Owned recovery A')",(workspace,))
            owner.execute('INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)',(user,principal.issuer,principal.subject))
            owner.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active,version) VALUES (%s,%s,%s,'{viewer}',true,1)",(membership,workspace,user))
            owner.execute("INSERT INTO workspace_preferences(id,workspace_id,user_id,locale,default_markets,version) VALUES (%s,%s,%s,'zh-HK','{HK}',1)",(preference,workspace,user))
        before=snapshot(dsn,user)
        with pytest.raises(ProgrammingError) as missing:
            run(runtime_role_dsn(dsn),lambda session:resolve_user_id(session,principal))
        assert missing.value.orig.sqlstate=='42P01'
        # Explicit reviewed additive target. No stamp, email match or request hook.
        command.upgrade(config,'0050_c61_delivery_authorizations')
        after=snapshot(dsn,user)
        assert after[:3]==before[:3] and set(before[3])<=set(after[3])
        # Expansion adds policies for new tables; every pre-existing policy and
        # runtime role flag stays exact. Do not reject additive policies.
        assert set(before[4])<=set(after[4]) and before[5]==after[5]
        assert run(runtime_role_dsn(dsn),lambda session:resolve_user_id(session,principal))==user
        with psycopg.connect(dsn) as owner:
            assert owner.execute('SELECT user_id,status,proof_ref FROM public.user_identities WHERE issuer=%s AND subject=%s',(principal.issuer,principal.subject)).fetchone()==(user,'active','legacy-backfill:'+str(user))
            owner.execute("UPDATE public.user_identities SET status='revoked',version=version+1 WHERE issuer=%s AND subject=%s",(principal.issuer,principal.subject))
        assert run(runtime_role_dsn(dsn),lambda session:resolve_user_id(session,principal)) is None
        command.upgrade(config,'0050_c61_delivery_authorizations')
        assert run(runtime_role_dsn(dsn),lambda session:resolve_user_id(session,principal)) is None
        with psycopg.connect(dsn) as owner:
            assert owner.execute('SELECT count(*) FROM public.user_identities WHERE user_id=%s',(user,)).fetchone()==(1,)
            assert owner.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname='buyeros_api'").fetchone()==(False,False)
    finally:get_settings.cache_clear()
