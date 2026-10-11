"""Owned worker routing controls; actual provider submission remains absent."""
import asyncio,uuid
from decimal import Decimal
import psycopg,pytest
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.config import get_settings
from buyeros_api.services.budget_service import ensure_period_accounts,reserve_operation
from buyeros_worker import tasks
from buyeros_worker.engine import create_engine
from tests.conftest import seed_outbox


@pytest.mark.parametrize('paid,delivery',[(False,False),(True,False),(False,True),(True,True)])
def test_legacy_delivery_intent_never_resolves_contact_or_releases_original_hold(worker_database_url,pg_dsn,monkeypatch,paid,delivery):
    workspace,project,operation,message=(uuid.uuid4() for _ in range(4));key='delivery:owned-routing:'+str(message)
    with psycopg.connect(pg_dsn,autocommit=True) as db:
        db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'owned delivery routing','live')",(workspace,))
        db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'owned routing','owned routing','owned offer','{US}','{en}',1)",(project,workspace))
        db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,provider_name,account_reference,status) VALUES (%s,%s,%s,'delivery',%s,'resend','owned-routing-account','intent')",(operation,workspace,key,'b'*64))
    async def setup_hold():
        engine=create_engine()
        try:
            async with tenant_session(engine,workspace) as session:await ensure_period_accounts(session,workspace,project,None,'delivery')
            with psycopg.connect(pg_dsn,autocommit=True) as db:db.execute('UPDATE budget_accounts SET approved_limit=1 WHERE workspace_id=%s',(workspace,))
            async with tenant_session(engine,workspace) as session:return await reserve_operation(session,operation,{'workspace_id':workspace,'project_id':project,'category':'delivery'},Decimal('0.010000'),'USD','delivery-owned-routing-v1')
        finally:await engine.dispose()
    try:
        reservation=asyncio.run(setup_hold())
        with psycopg.connect(pg_dsn,autocommit=True) as db:
            seed_outbox(db,intent_key=key,event_type='delivery.submit',payload={'workspace_id':str(workspace),'message_id':str(message),'operation_id':str(operation),'scope_hash':'b'*64},workspace_id=str(workspace),state='dispatched',generation=1)
        def snapshot():
            with psycopg.connect(pg_dsn) as db:
                hold=db.execute('SELECT operation_id,upper_bound,remaining_hold,state,currency,price_version FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()
                op=db.execute('SELECT intent_key,capability,input_hash,status,provider_name,account_reference,provider_ref FROM provider_operations WHERE id=%s',(operation,)).fetchone()
                alloc=db.execute('SELECT a.scope,a.scope_id,a.category,x.id,x.account_id,x.reservation_id FROM budget_accounts a JOIN budget_reservation_allocations x ON x.workspace_id=a.workspace_id AND x.account_id=a.id WHERE x.reservation_id=%s ORDER BY a.scope',(reservation,)).fetchall()
                costs=db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s',(workspace,)).fetchone()
                return hold,op,alloc,costs
        before=snapshot();assert before[0][:4]==(operation,Decimal('0.010000'),Decimal('0.010000'),'active') and {x[:3] for x in before[2]}=={('workspace',workspace,'all'),('project',project,'all'),('category',project,'delivery')}
        monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED',str(paid).lower());monkeypatch.setenv('BUYEROS_DELIVERY_DISPATCH_ENABLED',str(delivery).lower());get_settings.cache_clear()
        def forbidden(*a,**kw):raise AssertionError('delivery cannot resolve contact/search/model or parse common Service command')
        monkeypatch.setattr(tasks,'resolve_provider_adapter',forbidden);monkeypatch.setattr(tasks,'_provider_command',forbidden)
        assert tasks.execute_intent_sync(key,str(workspace),1,adapter=object(),environment='test')==('blocked' if paid and delivery else 'dispatch_disabled')
        assert snapshot()==before
        with psycopg.connect(pg_dsn) as db:assert db.execute('SELECT state FROM outbox_events WHERE intent_key=%s',(key,)).fetchone()==('failed' if paid and delivery else 'dispatched',)
    finally:
        get_settings.cache_clear()
        with psycopg.connect(pg_dsn,autocommit=True) as db:
            for table in ('outbox_events','provider_operations','budget_reservation_allocations','budget_reservations','budget_accounts','projects'):
                db.execute('DELETE FROM '+table+' WHERE workspace_id=%s',(workspace,))
            db.execute('DELETE FROM workspaces WHERE id=%s',(workspace,))
