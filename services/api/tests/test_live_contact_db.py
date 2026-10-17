"""C18 actual quote/confirm/worker/runtime-role/encrypted result; owned fake HTTP."""
import asyncio,uuid,hashlib,json
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.handlers.contact_submit import execute_contact_lookup
from buyeros_api.providers.base import ProviderIntent
from tests.test_live_contact_adapter import capability,module,response
from tests.test_lookup_quotes_db import quote_case,_post,_body
from tests.test_contact_confirm_atomicity_db import _limits,_confirm
from tests.test_buyer_review_db import api,WORKSPACE_A,WORKSPACE_B,OPERATOR
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn
from buyeros_api.api.routes.quotes import selected_contact_quote_capability

@pytest.fixture
def contact_case(quote_case,monkeypatch):
    client,dsn,buyers=quote_case;m=module()
    from buyeros_api.providers import base
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'hunter'}))
    cap=replace(capability(),idempotency='verified',status='verified') # fictional local status contract, no supplier claim
    client.app.dependency_overrides[selected_contact_quote_capability]=lambda:(cap,'test')
    from tests.policy_activation_fixtures import approve_provider_fixture
    from tests.test_api_projects_db import ADMIN
    from buyeros_api.providers.registry import ProviderRegistration
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE companies SET domain='fictional-sensors.com' WHERE id=%s",(buyers[0][1],))
    approve_provider_fixture(dsn,WORKSPACE_A,'a0000000-0000-4000-8000-000000000001',
        uuid.uuid5(uuid.NAMESPACE_URL,ADMIN),purpose='contact_research',domains=('fictional-sensors.com','fixture2.example'),
        scope={'provider_name':cap.provider,'account_reference':'fixture-test',
               'contract_sha256':ProviderRegistration(cap,lambda:None).contract_hash})
    _limits(client,dsn);quote=_post(client,_body(buyers[:1]),key='c18-owned-quote').json()['data']
    confirmed=_confirm(client,quote,key='c18-owned-confirm');assert confirmed.status_code==202,confirmed.text
    job=confirmed.json()['data'];workspace=uuid.UUID(WORKSPACE_A)
    with psycopg.connect(dsn) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("UPDATE companies SET domain='fictional-sensors.com' WHERE id=%s",(buyers[0][1],))
        db.execute("INSERT INTO company_aliases(id,workspace_id,company_id,alias_type,normalized_value,provenance,reviewed) VALUES(%s,%s,%s,'domain','fictional-sensors.com','owned human-reviewed fixture',true)",(uuid.uuid4(),workspace,buyers[0][1]))
        backend,epoch=db.execute('SELECT backend,epoch FROM worker_runtime_control').fetchone()
        outbox=db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend=%s,runtime_epoch=%s WHERE workspace_id=%s AND intent_key=%s RETURNING id",(backend,epoch,workspace,'contact.lookup:'+job['id'])).fetchone()[0]
        operation,key=db.execute('SELECT id,intent_key FROM provider_operations WHERE job_id=%s',(job['id'],)).fetchone()
    req=m.ContactRequest(key=key,workspace_id=workspace,project_id=uuid.UUID('a0000000-0000-4000-8000-000000000001'),actor_id=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR),buyer_id=uuid.UUID(buyers[0][0]),company_id=uuid.UUID(buyers[0][1]),buyer_version=1,quote_id=uuid.UUID(quote['id']),quote_hash=quote['quote_hash'],pricing_version=cap.pricing_version,adapter_version=cap.adapter_version,domain='fictional-sensors.com',market='US',language='en',role='Procurement manager',contact_type='business_email',limit=10)
    yield {'dsn':dsn,'cap':cap,'request':req,'operation':operation,'outbox':outbox,'job':uuid.UUID(job['id']),'workspace':workspace}
    with psycopg.connect(dsn) as db:
        if db.execute("SELECT to_regclass('public.contact_receipts')").fetchone()[0]:db.execute('DELETE FROM contact_receipts WHERE workspace_id=%s',(workspace,))
        db.execute('DELETE FROM company_aliases WHERE company_id=%s',(req.company_id,))

async def engines(case,exercise):
    m=module();cls=getattr(m,'PostgresContactReceipts',None);assert callable(cls),'C61-18 durable encrypted contact receipts missing'
    api_engine=create_async_engine(async_database_url(runtime_role_dsn(case['dsn'])));worker_engine=create_async_engine(async_database_url(role_dsn(case['dsn'],'buyeros_worker')))
    try:
        cipher=m.ContactReceiptCipher(keys={'offline-k1':b'a'*32},active_key_id='offline-k1')
        first=cls(api_engine,case['workspace'],case['cap'],cipher=cipher,environment='test');store=cls(worker_engine,case['workspace'],case['cap'],cipher=cipher,environment='test')
        ref=await first.prepare(case['request'],operation_id=case['operation'],outbox_id=case['outbox'],expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        await exercise(m,worker_engine,first,store,ref,cipher)
    finally:await api_engine.dispose();await worker_engine.dispose()

def held(case):
    with psycopg.connect(case['dsn']) as db:return db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(case['job'],)).fetchone(),db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(case['job'],)).fetchone()[0]

@pytest.mark.parametrize('failure',['none','timeout'])
def test_actual_confirm_single_contact_operation_and_encrypted_reopen_without_billing(contact_case,failure):
    case=contact_case;calls=[]
    def http_response(req):
        calls.append(req)
        with psycopg.connect(case['dsn']) as db:
            db.execute('SELECT id FROM enrichment_jobs WHERE id=%s FOR UPDATE NOWAIT',(case['job'],))
            db.execute('SELECT id FROM contact_receipts WHERE workspace_id=%s FOR UPDATE NOWAIT',(case['workspace'],))
        if failure=='timeout':raise httpx.ReadTimeout('owned accepted response lost')
        return httpx.Response(200,json=response())
    async def exercise(m,engine,first,store,ref,cipher):
        async with httpx.AsyncClient(transport=httpx.MockTransport(http_response)) as http:
            adapter=m.LiveContactAdapter(capability=case['cap'],account_reference='offline-account',client=m.HunterDomainClient(api_key='offline-not-real',http=http),receipts=store)
            assert await execute_contact_lookup(engine,case['workspace'],case['job'],1,adapter,environment='test') in {'accepted','unknown','done'}
            assert await execute_contact_lookup(engine,case['workspace'],case['job'],1,adapter,environment='test') in {'unknown','done','stale'}
            reopened=m.PostgresContactReceipts(engine,case['workspace'],case['cap'],cipher=cipher,environment='test');saved=await reopened.get(ref)
            assert saved['state']==('unknown' if failure=='timeout' else 'received')
            assert held(case)==(('active',Decimal('0.100000')),0)
            if failure=='none':
                assert saved['response']['verified_contacts']==[] and saved['response']['candidates'][0]['verification_status']=='needs_review'
                with psycopg.connect(case['dsn']) as db:
                    blob=db.execute('SELECT response_ciphertext FROM contact_receipts WHERE id=%s',(ref,)).fetchone()[0]
                    assert b'buyer@fictional-sensors.com' not in bytes(blob)
                    assert db.execute('SELECT count(*) FROM contact_points WHERE company_id=%s',(case['request'].company_id,)).fetchone()[0]==0
            assert (await adapter.submit(ProviderIntent(case['request'].key,'contact','US','en','Procurement manager'))).state==('unknown' if failure=='timeout' else 'accepted')
    asyncio.run(engines(case,exercise));assert len(calls)==1

@pytest.mark.parametrize('mutation',['actor','price','buyer','domain','review','policy','cancel','fence'])
def test_contact_current_quote_company_scope_before_network(contact_case,mutation):
    case=contact_case;calls=[]
    async def exercise(m,engine,first,store,ref,cipher):
        with psycopg.connect(case['dsn']) as db:
            if mutation=='actor':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE user_id=%s',(case['request'].actor_id,))
            elif mutation=='price':db.execute("UPDATE enrichment_quotes SET price_version='stale-price' WHERE id=%s",(case['request'].quote_id,))
            elif mutation=='buyer':db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(case['request'].buyer_id,))
            elif mutation=='domain':db.execute("UPDATE companies SET domain='different-company.com' WHERE id=%s",(case['request'].company_id,))
            elif mutation=='review':db.execute('UPDATE company_aliases SET reviewed=false WHERE company_id=%s',(case['request'].company_id,))
            elif mutation=='policy':db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s",(case['workspace'],))
            elif mutation=='cancel':db.execute('UPDATE enrichment_jobs SET cancel_requested=true WHERE id=%s',(case['job'],))
            else:db.execute('UPDATE outbox_events SET fencing_generation=2 WHERE id=%s',(case['outbox'],))
        class Client:
            async def lookup(self,*args):calls.append(args);raise AssertionError('current stale basis must deny network')
        adapter=m.LiveContactAdapter(capability=case['cap'],account_reference='offline-account',client=Client(),receipts=store)
        assert await execute_contact_lookup(engine,case['workspace'],case['job'],1,adapter,environment='test') in {'actor_changed','blocked','cancelled','policy_blocked','stale','unknown','done'}
        assert held(case)[1]==0
    asyncio.run(engines(case,exercise));assert calls==[]

def test_contact_runtime_rls_immutable_private_result_and_populated_rollback(contact_case,monkeypatch):
    case=contact_case
    async def exercise(m,engine,first,store,ref,cipher):
        from sqlalchemy import text
        from sqlalchemy.exc import IntegrityError
        from alembic import command
        from alembic.config import Config
        from tests.conftest import ALEMBIC_INI,SERVICE_ROOT
        from buyeros_api.settings import get_settings
        assert await m.PostgresContactReceipts(engine,uuid.UUID(WORKSPACE_B),case['cap'],cipher=cipher,environment='test').get(ref) is None
        async with tenant_session(engine,case['workspace']) as session:
            assert (await session.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='contact_receipts'"))).one()==(True,True)
            assert (await session.execute(text("SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user"))).scalar_one() is False
        with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
        intent=ProviderIntent(case['request'].key,'contact','US','en','Procurement manager');assert (await store.claim(intent))[1];assert not (await store.claim(intent))[1]
        payload=m.normalize_contact_response(response(),case['request']);digest=hashlib.sha256(m.canonical_json(payload)).hexdigest();await store.finish(ref,state='received',response=payload,digest=digest)
        saved=await store.get(ref);assert saved['state']=='received'
        for sql in ["UPDATE contact_receipts SET state='prepared'","UPDATE contact_receipts SET request=jsonb_set(request,'{domain}','\"different-company.com\"')","UPDATE contact_receipts SET response_ciphertext=decode('00','hex')"]:
            with pytest.raises(IntegrityError):
                async with tenant_session(engine,case['workspace']) as session:await session.execute(text(sql))
        monkeypatch.setenv('BUYEROS_DATABASE_URL',case['dsn']);get_settings.cache_clear();config=Config(str(ALEMBIC_INI));config.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
        try:
            with pytest.raises(RuntimeError,match='preserve controller policy history'):
                command.downgrade(config,'0041_c61_model_receipts')
            from tests.migration_guards import invoke_revision
            invoke_revision(case['dsn'],config,'0042_c61_contact_receipts')
            invoke_revision(case['dsn'],config,'0043_c61_receipt_retention')
            assert await store.get(ref)==saved
            with pytest.raises(ValueError,match='0042'):await store.claim(intent)
        finally:
            invoke_revision(case['dsn'],config,'0056_policy_activation','_fences',('0056_policy_activation',))
            monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(case['dsn']));get_settings.cache_clear()
        assert await store.get(ref)==saved
    asyncio.run(engines(case,exercise))


def test_contact_epoch_change_during_vendor_response_never_claims_accepted(contact_case):
    case=contact_case;calls=[]
    def vendor(req):
        calls.append(req)
        with psycopg.connect(case['dsn']) as db:db.execute('UPDATE worker_runtime_control SET epoch=epoch+1,enabled=false WHERE singleton=1')
        return httpx.Response(200,json=response())
    async def exercise(m,engine,first,store,ref,cipher):
        async with httpx.AsyncClient(transport=httpx.MockTransport(vendor)) as http:
            adapter=m.LiveContactAdapter(capability=case['cap'],account_reference='offline-account',client=m.HunterDomainClient(api_key='offline-not-real',http=http),receipts=store)
            result=await execute_contact_lookup(engine,case['workspace'],case['job'],1,adapter,environment='test')
            assert result in {'unknown','stale','done'}
            assert (await store.get(ref))['state']=='submitting'
            assert (await adapter.status(ref)).state=='unknown'
            assert (await adapter.submit(ProviderIntent(case['request'].key,'contact','US','en','Procurement manager'))).state=='unknown'
            assert held(case)==(('active',Decimal('0.100000')),0)
    asyncio.run(engines(case,exercise));assert len(calls)==1
