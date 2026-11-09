"""Real migration and integer ledger acceptance, never ORM-created substitutes."""
import psycopg
import pytest
from decimal import Decimal
from tests.xverum_fixtures import credit_case, connection_case, provisional_pg, execution_api, pg


@pytest.mark.parametrize('limit',['account','workspace','project'])
def test_competing_credit_reservations_are_atomic(credit_case,limit):
    import asyncio
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from buyeros_api.api.errors import ApiError
    c=credit_case
    with psycopg.connect(c.dsn) as db:
        if limit=='account':db.execute('UPDATE xverum_credit_accounts SET credit_limit=5')
        elif limit=='workspace':db.execute('UPDATE xverum_credit_limits SET credit_limit=5 WHERE project_id IS NULL')
        else:db.execute('UPDATE xverum_credit_limits SET credit_limit=5 WHERE project_id IS NOT NULL')
    async def run(factory):
        quotes=[]
        for i in range(2):
            async with factory() as s:quotes.append(await quote_search(s,c.scope,c.id,'Synthetic '+str(i),'company',c.buyer))
        async def admit(i):
            try:
                async with factory() as s:await confirm_quote(s,c.scope,quotes[i].id,quotes[i].fingerprint,'race-'+str(i))
                return 1
            except ApiError as e:
                assert e.code=='XVERUM_CREDIT_LIMIT'
                return 0
        assert sum(await asyncio.gather(admit(0),admit(1)))==1
    pg(c,run)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT sum(held_credits) FROM xverum_credit_reservations').fetchone()[0]==5
        assert db.execute('SELECT count(*) FROM budget_reservations').fetchone()[0]==1


@pytest.mark.parametrize('usage',[0,3,6,-1,True,None])
def test_settlement_is_idempotent_or_retains_unknown_hold(credit_case,usage):
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from buyeros_api.services.xverum_credits import settle_credits
    c=credit_case
    async def run(factory):
        async with factory() as s:
            q=await quote_search(s,c.scope,c.id,'Synthetic','company',c.buyer)
        async with factory() as s:r=await confirm_quote(s,c.scope,q.id,q.fingerprint,'settlement')
        with psycopg.connect(c.dsn) as db:db.execute("UPDATE xverum_receipts SET dispatch_state='dispatched' WHERE id=%s",(r.id,))
        for _ in range(2):
            async with factory() as s:await settle_credits(s,r.id,usage)
        return r
    r=pg(c,run)
    valid=type(usage) is int and 0<=usage<=5
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT dispatch_state FROM xverum_receipts WHERE id=%s',(r.id,)).fetchone()[0]==('settled' if valid else 'outcome_unknown')
        assert db.execute('SELECT version FROM xverum_receipts WHERE id=%s',(r.id,)).fetchone()[0]==2
        assert db.execute('SELECT held_credits FROM xverum_credit_reservations').fetchone()[0]==(0 if valid else 5)
        assert db.execute('SELECT count(*) FROM xverum_credit_settlements').fetchone()[0]==(1 if valid else 0)
        hold=db.execute('SELECT remaining_hold,currency,price_version,operation_id FROM budget_reservations WHERE id=%s',(r.reservation_ids[0],)).fetchone()
        assert hold[:3]==(Decimal('0') if valid else Decimal('.05'),'USD','fixture-v1')
        events=db.execute('SELECT amount,pricing_version,kind FROM cost_events WHERE operation_id=%s',(hold[3],)).fetchall()
        assert events==([(Decimal(usage)*Decimal('.01'),'fixture-v1','commit')] if valid else [])


def test_credit_ledger_installed(isolated_seeded):
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute("SELECT to_regclass('public.xverum_credit_accounts')").fetchone()[0] is not None


def test_empty_upgrade_rollback_reupgrade(isolated_migrated):
    from alembic import command
    from tests.test_conversation_threads_db import config
    from tests.conftest import runtime_role_dsn
    command.downgrade(config(),'0061_sales_outputs')
    with psycopg.connect(runtime_role_dsn(isolated_migrated)) as db:
        assert db.execute("SELECT to_regclass('public.xverum_connections')").fetchone()[0] is None
        assert db.execute('SELECT public.buyeros_model_receipts_writable()').fetchone()[0] is True
    command.upgrade(config(),'head')
    with psycopg.connect(runtime_role_dsn(isolated_migrated)) as db:
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0] is True
        assert db.execute('SELECT public.buyeros_search_receipts_writable(),public.buyeros_model_receipts_writable(),public.buyeros_contact_receipts_writable()').fetchone()==(True,True,True)
        assert not db.execute("SELECT has_table_privilege(current_user,'alembic_version','SELECT')").fetchone()[0]


def test_populated_rollback_preserves_force_rls_and_roles(credit_case):
    from alembic import command
    from tests.test_conversation_threads_db import config
    from tests.conftest import runtime_role_dsn
    c=credit_case
    with pytest.raises(RuntimeError,match='preserve populated'):command.downgrade(config(),'0061_sales_outputs')
    tables=('connections','project_assignments','credit_accounts','credit_limits','tariffs','quotes','credit_reservations','receipts','credit_settlements')
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0068_conversation_turn_events'
        for table in tables:
            table='xverum_'+table
            assert db.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(table,)).fetchone()==(True,True)
        for role in ('buyeros_api','buyeros_worker'):
            assert not db.execute("SELECT has_column_privilege(%s,'xverum_connections','secret_ref','UPDATE')",(role,)).fetchone()[0]
            assert not db.execute("SELECT has_column_privilege(%s,'xverum_credit_accounts','credit_limit','UPDATE')",(role,)).fetchone()[0]
            assert not db.execute("SELECT has_table_privilege(%s,'xverum_tariffs','INSERT')",(role,)).fetchone()[0]
            assert not db.execute("SELECT has_table_privilege(%s,'xverum_credit_settlements','DELETE')",(role,)).fetchone()[0]
        assert not db.execute("SELECT has_table_privilege('buyeros_worker','xverum_project_assignments','INSERT')").fetchone()[0]
    with psycopg.connect(runtime_role_dsn(c.dsn)) as db:
        assert db.execute('SELECT count(*) FROM xverum_connections').fetchone()[0]==0
        db.execute("SELECT set_config('app.workspace_id','22222222-2222-4222-8222-222222222222',true)")
        assert db.execute('SELECT count(*) FROM xverum_credit_accounts').fetchone()[0]==0


def test_boolean_readiness_rejects_missing_ledger_relation(credit_case):
    from buyeros_api.services.xverum_connections import require_schema
    from buyeros_api.api.errors import ApiError
    c=credit_case
    with psycopg.connect(c.dsn) as db:db.execute('ALTER TABLE xverum_credit_settlements RENAME TO removed_settlements')
    async def run(factory):
        with pytest.raises(ApiError) as err:
            async with factory() as s:await require_schema(s)
        assert err.value.code=='XVERUM_SCHEMA_NOT_READY'
    pg(c,run)


def test_shared_account_across_projects_has_one_credit_pool(credit_case):
    import uuid,asyncio
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from buyeros_api.services.budget_service import ensure_period_accounts
    from buyeros_api.api.errors import ApiError
    c=credit_case
    project,buyer,connection,company=[uuid.uuid4() for _ in range(4)]
    scope=c.scope.model_copy(update={'project_id':project})
    with psycopg.connect(c.dsn) as db:
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES(%s,%s,'Second','Second','Synthetic','{US}','{en}',1)",(project,c.ws))
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Second','Second')",(company,c.ws))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(buyer,c.ws,project,company))
        db.execute("INSERT INTO xverum_connections(id,workspace_id,generation,version,account_ref,tariff_version,secret_ref,status,configured_by) VALUES(%s,%s,1,1,'synthetic-account','fixture-v1',%s,'connected',%s)",(connection,c.ws,uuid.uuid4(),c.scope.actor_id))
        db.execute('INSERT INTO xverum_project_assignments(id,workspace_id,connection_id,project_id) VALUES(%s,%s,%s,%s)',(uuid.uuid4(),c.ws,connection,project))
        db.execute('INSERT INTO xverum_credit_limits(id,workspace_id,project_id,credit_limit) VALUES(%s,%s,%s,100)',(uuid.uuid4(),c.ws,project))
        db.execute('UPDATE xverum_credit_accounts SET credit_limit=5')
    async def run(factory):
        async with factory() as s:
            await ensure_period_accounts(s,c.ws,project,None,'contact_lookup')
            q1=await quote_search(s,c.scope,c.id,'First','company',c.buyer)
            q2=await quote_search(s,scope,connection,'Second','company',buyer)
        with psycopg.connect(c.dsn) as db:db.execute('UPDATE budget_accounts SET approved_limit=100')
        async def admit(q,sc):
            try:
                async with factory() as s:await confirm_quote(s,sc,q.id,q.fingerprint,str(q.id))
                return 1
            except ApiError as e:
                assert e.code=='XVERUM_CREDIT_LIMIT'
                return 0
        assert sum(await asyncio.gather(admit(q1,c.scope),admit(q2,scope)))==1
    pg(c,run)


def test_usd_denial_leaves_no_credit_hold(credit_case):
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from buyeros_api.api.errors import ApiError
    c=credit_case
    with psycopg.connect(c.dsn) as db:db.execute('UPDATE budget_accounts SET approved_limit=0')
    async def run(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic','company',c.buyer)
        with pytest.raises(ApiError) as err:
            async with factory() as s:await confirm_quote(s,c.scope,q.id,q.fingerprint,'usd-denied')
        assert err.value.code=='BUDGET_LIMIT'
    pg(c,run)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM xverum_credit_reservations').fetchone()[0]==0


def test_connection_account_reference_is_tenant_bound(credit_case):
    c=credit_case
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with psycopg.connect(c.dsn) as db:
            db.execute("UPDATE xverum_connections SET account_ref='unprovisioned' WHERE id=%s",(c.id,))
