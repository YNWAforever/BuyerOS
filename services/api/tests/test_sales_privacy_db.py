"""Task14 financial evidence stays separate from private content."""
import importlib
from decimal import Decimal
import uuid
import pytest
from tests.test_sales_execution_db import execution_api, execution_pg, pg_call, pg_dispatch


def owner():
    assert importlib.util.find_spec('buyeros_api.services.sales_accounting'), 'missing actual accounting owner'
    return importlib.import_module('buyeros_api.services.sales_accounting')


def test_accounting_requires_actual_money_not_tokens():
    m = owner()
    with pytest.raises(ValueError):
        m.FinancialObservation(step_id=uuid.uuid4(), claim_id=uuid.uuid4(),
            request_hash='a'*64, account_hash='b'*64, evidence_hash='c'*64,
            resolution='billed', amount=None, currency='USD', pricing_version='v1')


def test_partial_billing_releases_only_known_liability(execution_pg):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.sales.contracts import Scope
    from buyeros_api.sales.context import digest
    from tests.test_buyer_review_db import ADMIN
    m = owner()
    c = execution_pg
    pg_dispatch(c, 0)
    c.mode = 'lost'
    pg_dispatch(c, 1)
    with psycopg.connect(c.dsn) as db:
        parent, revision = db.execute('SELECT id,accounting_revision FROM sales_executions WHERE task_id=%s', (c.task['id'],)).fetchone()
        claim = db.execute('SELECT claim_id FROM sales_steps WHERE id=%s', (c.steps[0][0],)).fetchone()[0]
    scope = Scope(workspace_id=c.ws, project_id=c.project, actor_id=uuid.uuid5(uuid.NAMESPACE_URL, ADMIN))
    observation = m.FinancialObservation(step_id=c.steps[0][0], claim_id=claim,
        request_hash=digest('synthetic-ref'), account_hash=digest('synthetic-sales-account'),
        evidence_hash='c'*64, resolution='billed', amount=Decimal('.03'), currency='USD',
        pricing_version=c.item.capability.pricing_version)
    async def apply(engine):
        async with tenant_session(engine, c.ws) as session:
            evidence = await m.record_evidence(session, scope, parent, observation, key='bill-1')
        receipt = await m.ACCOUNTING_OWNER.reconcile_parent(engine, scope=scope, execution_id=parent,
            evidence_ids=(evidence,), expected_revision=revision, key='settle-1')
        replay = await m.ACCOUNTING_OWNER.reconcile_parent(engine, scope=scope, execution_id=parent,
            evidence_ids=(evidence,), expected_revision=revision, key='settle-1')
        assert receipt == replay
    pg_call(c, apply, worker=False)
    with psycopg.connect(c.dsn) as db:
        hold, bound = db.execute('SELECT remaining_hold,upper_bound FROM budget_reservations WHERE operation_id=%s', (parent,)).fetchone()
        assert hold == bound - Decimal('.1')
        assert db.execute('SELECT amount FROM cost_events WHERE operation_id=%s', (parent,)).fetchall() == [(Decimal('.03'),)]
        assert db.execute('SELECT count(*) FROM sales_accounting_receipts WHERE execution_id=%s', (parent,)).fetchone()[0] == 1
    from buyeros_api.api.errors import ApiError
    async def negatives(engine):
        with pytest.raises(ApiError, match='revision'):
            await m.ACCOUNTING_OWNER.reconcile_parent(engine,scope=scope,execution_id=parent,
                evidence_ids=(),expected_revision=0,key='stale-key')
        with pytest.raises(ApiError, match='already settled'):
            async with tenant_session(engine,c.ws) as session:
                evidence=await m.record_evidence(session,scope,parent,observation,key='bill-1')
            await m.ACCOUNTING_OWNER.reconcile_parent(engine,scope=scope,execution_id=parent,
                evidence_ids=(evidence,),expected_revision=1,key='duplicate-new-key')
        for change in ({'account_hash':'d'*64},{'claim_id':uuid.uuid4()},
                       {'request_hash':'e'*64},{'amount':Decimal('.04')}):
            with pytest.raises(ApiError):
                async with tenant_session(engine,c.ws) as session:
                    await m.record_evidence(session,scope,parent,observation.model_copy(update=change),key='bad')
        with pytest.raises(ApiError):
            await m.ACCOUNTING_OWNER.reconcile_parent(engine,scope=scope,execution_id=parent,
                evidence_ids=(uuid.uuid4(),),expected_revision=1,key='foreign')
    pg_call(c,negatives,worker=False)
    # Purge the owner's private task while the second supplier call is unknown.
    from buyeros_api.services.sales_retention import purge_sales_content
    from tests.test_buyer_review_db import OPERATOR
    async def purge(engine):
        async with tenant_session(engine,c.ws) as session:
            await purge_sales_content(session,scope.model_copy(update={'actor_id':uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)}),uuid.UUID(c.task['id']))
    pg_call(c,purge,worker=False)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_financial_evidence WHERE execution_id=%s',(parent,)).fetchone()[0]==1
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s',(parent,)).fetchone()[0]==Decimal('.1')
        db.execute('UPDATE memberships SET active=false WHERE user_id=%s AND workspace_id=%s',(scope.actor_id,c.ws))
    async def revoked(engine):
        with pytest.raises(ApiError,match='authority'):
            await m.ACCOUNTING_OWNER.reconcile_parent(engine,scope=scope,execution_id=parent,
                evidence_ids=(),expected_revision=1,key='revoked')
    pg_call(c,revoked,worker=False)


def test_accounted_child_does_not_block_queued_child_dispatch(execution_pg):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.sales.contracts import Scope
    from buyeros_api.sales.context import digest
    from tests.test_buyer_review_db import ADMIN
    m=owner();c=execution_pg
    pg_dispatch(c,0)
    with psycopg.connect(c.dsn) as db:
        parent=db.execute('SELECT id FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchone()[0]
        claim=db.execute('SELECT claim_id FROM sales_steps WHERE id=%s',(c.steps[0][0],)).fetchone()[0]
    scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN))
    async def account(engine):
        async with tenant_session(engine,c.ws) as session:
            eid=await m.record_evidence(session,scope,parent,m.FinancialObservation(step_id=c.steps[0][0],
                claim_id=claim,request_hash=digest('synthetic-ref'),account_hash=digest('synthetic-sales-account'),
                evidence_hash='a'*64,resolution='billed',amount=Decimal('.02'),currency='USD',
                pricing_version=c.item.capability.pricing_version),key='first')
        await m.ACCOUNTING_OWNER.reconcile_parent(engine,scope=scope,execution_id=parent,
            evidence_ids=(eid,),expected_revision=0,key='first')
    pg_call(c,account,worker=False)
    pg_dispatch(c,1)
    assert c.calls==2
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT state FROM sales_steps WHERE id=%s',(c.steps[1][0],)).fetchone()[0]=='received'


def test_populated_xverum_enrichments_tenant_read_insert_update(isolated_api,isolated_seeded):
    import psycopg
    from psycopg.types.json import Jsonb
    from tests.conftest import runtime_role_dsn
    from tests.test_buyer_review_db import WORKSPACE_A,WORKSPACE_B,PROJECT_A,PROJECT_B,ADMIN
    actor=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN)
    rows=[]
    with psycopg.connect(isolated_seeded) as db:
        for ws,project in ((WORKSPACE_A,PROJECT_A),(WORKSPACE_B,PROJECT_B)):
            company,buyer,row=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fixture','Fixture')",(company,ws))
            db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(buyer,ws,project,company))
            db.execute('INSERT INTO xverum_enrichments(id,workspace_id,project_id,actor_id,buyer_id,proposal,proof) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                (row,ws,project,actor,buyer,Jsonb({'fixture':ws}),Jsonb({})))
            rows.append((row,buyer))
    with psycopg.connect(runtime_role_dsn(isolated_seeded)) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(WORKSPACE_A,))
        assert db.execute('SELECT id FROM xverum_enrichments').fetchall()==[(rows[0][0],)]
        assert db.execute('UPDATE xverum_enrichments SET applied=%s WHERE id=%s RETURNING id',(Jsonb({}),rows[1][0])).fetchall()==[]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():
                db.execute('INSERT INTO xverum_enrichments(id,workspace_id,project_id,actor_id,buyer_id,proposal,proof) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                    (uuid.uuid4(),WORKSPACE_B,PROJECT_B,actor,rows[1][1],Jsonb({}),Jsonb({})))
        assert db.execute('SELECT applied FROM xverum_enrichments WHERE id=%s',(rows[0][0],)).fetchone()[0] is None
    with psycopg.connect(isolated_seeded) as db:
        db.execute('DELETE FROM xverum_enrichments WHERE id=ANY(%s)',([row[0] for row in rows],))


def test_lifecycle_migration_empty_roundtrip_and_grants(isolated_migrated):
    import psycopg
    from alembic import command
    from tests.test_conversation_threads_db import config
    command.downgrade(config(),'0064_xverum_enrichment')
    command.upgrade(config(),'head')
    with psycopg.connect(isolated_migrated) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0067_conversation_buyer'
        for service in ('search','model','contact'):
            assert db.execute(f'SELECT public.buyeros_{service}_receipts_writable()').fetchone()[0]
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0]
        assert not db.execute("SELECT has_table_privilege('buyeros_worker','sales_financial_evidence','INSERT')").fetchone()[0]
        assert not db.execute("SELECT has_table_privilege('buyeros_api','sales_accounting_receipts','UPDATE')").fetchone()[0]
        assert not db.execute("SELECT has_column_privilege('buyeros_worker','sales_executions','accounted_bound','UPDATE')").fetchone()[0]
        assert not db.execute("SELECT has_column_privilege('buyeros_api','sales_output_versions','candidate','UPDATE')").fetchone()[0]
        assert db.execute("SELECT count(*) FROM pg_class WHERE relname IN ('sales_financial_evidence','sales_accounting_receipts','sales_content_tombstones') AND relrowsecurity AND relforcerowsecurity").fetchone()[0]==3


def test_all_unsubmitted_accounting_and_populated_downgrade_refusal(execution_pg):
    import psycopg
    from tests.test_conversation_threads_api import headers
    from tests.test_buyer_review_db import ADMIN
    from buyeros_api.sales.contracts import Scope
    from alembic import command
    from tests.test_conversation_threads_db import config
    c=execution_pg;m=owner()
    current=c.client.get(c.path,headers=headers()).json()['data']
    response=c.client.post(c.path+'/cancel',headers=headers(version=current['revision']))
    assert response.status_code==200,response.text
    with psycopg.connect(c.dsn) as db:
        parent=db.execute('SELECT id FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchone()[0]
    scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN))
    async def apply(engine):
        import asyncio
        kwargs=dict(scope=scope,execution_id=parent,evidence_ids=(),expected_revision=0,key='unused')
        ids=await asyncio.gather(m.ACCOUNTING_OWNER.reconcile_parent(engine,**kwargs),m.ACCOUNTING_OWNER.reconcile_parent(engine,**kwargs))
        assert ids[0]==ids[1]
    pg_call(c,apply,worker=False)
    with pytest.raises(RuntimeError,match='preserve financial'):
        command.downgrade(config(),'0064_xverum_enrichment')
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT remaining_hold,state FROM budget_reservations WHERE operation_id=%s',(parent,)).fetchone()==(Decimal(0),'released')
        assert db.execute('SELECT count(*) FROM sales_accounting_receipts WHERE execution_id=%s',(parent,)).fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(parent,)).fetchone()[0]==0
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0067_conversation_buyer'


@pytest.mark.parametrize('second',['queued','unknown'])
def test_cancelled_mixed_parent_settles_actual_once_and_releases_only_known_unused(execution_pg,second):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.sales.contracts import Scope
    from buyeros_api.sales.context import digest
    from tests.test_buyer_review_db import ADMIN
    from tests.test_conversation_threads_api import headers
    c=execution_pg;m=owner();pg_dispatch(c,0)
    if second=='unknown':c.mode='lost';pg_dispatch(c,1)
    current=c.client.get(c.path,headers=headers()).json()['data']
    assert c.client.post(c.path+'/cancel',headers=headers(version=current['revision'])).status_code==200
    with psycopg.connect(c.dsn) as db:
        parent=db.execute('SELECT id FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchone()[0]
        claims=dict(db.execute('SELECT id,claim_id FROM sales_steps WHERE execution_id=%s',(parent,)).fetchall())
    scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,ADMIN))
    async def settle(engine):
        async def evidence(index,resolution,amount):
            async with tenant_session(engine,c.ws) as session:
                return await m.record_evidence(session,scope,parent,m.FinancialObservation(
                    step_id=c.steps[index][0],claim_id=claims[c.steps[index][0]],
                    request_hash=digest('synthetic-ref' if index==0 else 'authoritative-unknown-request'),
                    account_hash=digest('synthetic-sales-account'),evidence_hash=digest(f'bill-{index}'),
                    resolution=resolution,amount=amount,currency='USD',pricing_version=c.item.capability.pricing_version),key=f'bill-{index}')
        first=await evidence(0,'billed',Decimal('.03'))
        kwargs=dict(scope=scope,execution_id=parent,evidence_ids=(first,),expected_revision=0,key='settle-first')
        receipt=await m.ACCOUNTING_OWNER.reconcile_parent(engine,**kwargs)
        assert await m.ACCOUNTING_OWNER.reconcile_parent(engine,**kwargs)==receipt
        if second=='unknown':
            with psycopg.connect(c.dsn) as db:
                assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE operation_id=%s',(parent,)).fetchone()[0]==Decimal('.1')
            last=await evidence(1,'not_billed',Decimal(0))
            await m.ACCOUNTING_OWNER.reconcile_parent(engine,scope=scope,execution_id=parent,
                evidence_ids=(last,),expected_revision=1,key='settle-last')
    pg_call(c,settle,worker=False)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT remaining_hold,state FROM budget_reservations WHERE operation_id=%s',(parent,)).fetchone()==(Decimal(0),'settled')
        assert db.execute('SELECT sum(amount) FROM cost_events WHERE operation_id=%s',(parent,)).fetchone()[0]==Decimal('.03')
        assert db.execute('SELECT accounted_bound,settled_usd FROM sales_executions WHERE id=%s',(parent,)).fetchone()==(Decimal('.2'),Decimal('.03'))


@pytest.mark.parametrize('role',['buyeros_api','buyeros_worker'])
def test_lifecycle_readiness_exact_runtime_role_and_purge_execute_fence(isolated_seeded,role):
    import asyncio,psycopg
    from sqlalchemy.ext.asyncio import create_async_engine
    from tests.test_schema_readiness_db import contract
    from tests.test_native_model_completion_db import role_dsn
    from buyeros_api.services.schema_readiness import SchemaContract,inspect_schema,sales_requirements
    from buyeros_api.execution.engine import async_database_url
    with psycopg.connect(isolated_seeded) as db:
        db.execute(f"ALTER ROLE {role} LOGIN PASSWORD 'test-only'")
        db.execute(f'GRANT SELECT(version_num) ON alembic_version TO {role}')
    data=contract(isolated_seeded,**sales_requirements(worker=role=='buyeros_worker'),
        runtime_role_policy={'role':role,'superuser':False,'bypass_rls':False})
    async def probe():
        engine=create_async_engine(async_database_url(role_dsn(isolated_seeded,role)))
        try:
            async with engine.connect() as connection:return await inspect_schema(connection,SchemaContract.model_validate(data))
        finally:await engine.dispose()
    result=asyncio.run(probe())
    assert result.compatible,result.blockers
    for function in ('buyeros_purge_sales_task','buyeros_purge_xverum_stage'):
        with psycopg.connect(isolated_seeded) as db:
            db.execute(f'ALTER FUNCTION public.{function}(uuid) SET search_path=pg_catalog,public')
        unsafe=asyncio.run(probe())
        assert not unsafe.compatible and any(function in b for b in unsafe.blockers),unsafe.blockers
        with psycopg.connect(isolated_seeded) as db:
            db.execute(f'ALTER FUNCTION public.{function}(uuid) SET search_path=pg_catalog,public,pg_temp')
    with psycopg.connect(isolated_seeded) as db:
        db.execute(f'REVOKE EXECUTE ON FUNCTION public.buyeros_purge_xverum_stage(uuid) FROM {role}')
    result=asyncio.run(probe())
    assert not result.compatible and any('purge_xverum' in b for b in result.blockers),result.blockers
