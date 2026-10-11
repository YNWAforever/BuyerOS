"""Actual code-owned contact selector/factory/native receipt prepare; owned PG, synthetic client."""
import asyncio,uuid
from dataclasses import replace
from decimal import Decimal
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.worker_schemas import JobEnvelope
from buyeros_api.api.routes.quotes import selected_contact_quote_capability
from buyeros_api.api.routes.enrichment import selected_contact_status_capability
from buyeros_api.providers import registry
from buyeros_api.providers.registry import ProviderRegistry,ProviderUnavailable
from buyeros_api.providers.contact_receipts import PostgresContactReceipts
from buyeros_api.providers.live_contact import LiveContactAdapter,ContactReceiptCipher,ContactResponseUnknown,normalize_contact_response
from buyeros_api.services.worker_execution import execute_step
from buyeros_api.execution.config import get_settings as worker_settings
from buyeros_api.settings import get_settings
from tests.test_contact_registry_scope_db import scoped_quote_case,quote_case,api,quote,held
from tests.test_contact_confirm_atomicity_db import _confirm
from tests.test_buyer_review_db import OPERATOR
from tests.test_live_contact_adapter import response
from tests.cutover_fixtures import role_dsn

@pytest.fixture
def native_case(scoped_quote_case,monkeypatch):
    c=scoped_quote_case;holder={};factories=[]
    c['client'].app.dependency_overrides.pop(selected_contact_quote_capability,None)
    def factory():factories.append('contact');return holder['adapter']
    item=replace(c['item'],factory=factory)
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((item,)))
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','true');worker_settings.cache_clear()
    monkeypatch.setenv('BUYEROS_CLOUDFLARE_EXECUTION_ENABLED','true');get_settings.cache_clear()
    assert get_settings().cloudflare_execution_enabled and worker_settings().paid_dispatch_enabled
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1 WHERE singleton=1")
    try:yield {**c,'item':item,'holder':holder,'factories':factories}
    finally:
        with psycopg.connect(c['dsn']) as db:db.execute('DELETE FROM worker_steps WHERE workspace_id=%s',(c['workspace'],))
        worker_settings.cache_clear();get_settings.cache_clear()

def admitted(c):
    q=quote(c);assert c['factories']==[]
    confirmed=_confirm(c['client'],q,key='native-contact-confirm');assert confirmed.status_code==202,confirmed.text
    replay=_confirm(c['client'],q,key='native-contact-confirm');assert replay.json()['data']==confirmed.json()['data']
    job=uuid.UUID(confirmed.json()['data']['id'])
    with psycopg.connect(c['dsn']) as db:
        backend,epoch=db.execute('SELECT backend,epoch FROM worker_runtime_control').fetchone()
        assert backend=='cloudflare'
        event=db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend=%s,runtime_epoch=%s WHERE intent_key=%s RETURNING id",(backend,epoch,'contact.lookup:'+str(job))).fetchone()[0]
        operation=db.execute('SELECT id FROM provider_operations WHERE job_id=%s',(job,)).fetchone()[0]
        assert db.execute('SELECT count(*) FROM contact_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,),'fixture manually prepared contact receipt before native path'
        assert db.execute('SELECT count(*) FROM provider_operations WHERE job_id=%s',(job,)).fetchone()==(1,)
    return {**c,'quote':q,'job':job,'outbox':event,'operation':operation,'epoch':epoch}

def test_current_contact_factory_can_resolve_exact_reviewed_account_without_company_role_fallback(native_case):
    c=native_case
    adapter=LiveContactAdapter(capability=c['cap'],account_reference=c['item'].contact_scope.account_reference,client=object(),receipts=object())
    c['holder']['adapter']=adapter
    assert registry.DEFAULT_REGISTRY.resolve('contact',environment='production') is adapter
    assert c['factories']==['contact']

@pytest.mark.parametrize('mismatch',['account','status'])
def test_contact_factory_cannot_swap_reviewed_account_or_nonbillable_status(native_case,mismatch):
    c=native_case
    adapter=LiveContactAdapter(capability=c['cap'],account_reference='synthetic-other-account' if mismatch=='account' else c['item'].contact_scope.account_reference,client=object(),receipts=object())
    if mismatch=='status':adapter.status_nonbillable=False
    c['holder']['adapter']=adapter
    with pytest.raises(ProviderUnavailable) as failure:registry.DEFAULT_REGISTRY.resolve('contact',environment='production')
    assert failure.value.reasons==('ADAPTER_CONTRACT_MISMATCH',)
    assert c['factories']==['contact']

@pytest.mark.parametrize('state',['received','unknown'])
def test_actual_public_contact_confirm_native_registry_factory_prepares_once_and_preserves_unknown_money(native_case,state):
    c=admitted(native_case);calls=[]
    class Client:
        async def lookup(self,request):
            calls.append(request)
            with psycopg.connect(c['dsn']) as db:
                assert db.execute('SELECT id FROM enrichment_jobs WHERE id=%s FOR UPDATE NOWAIT',(c['job'],)).fetchone()
                assert db.execute('SELECT id FROM contact_receipts WHERE operation_id=%s FOR UPDATE NOWAIT',(c['operation'],)).fetchone()
                assert db.execute('SELECT id FROM budget_reservations WHERE operation_id=%s FOR UPDATE NOWAIT',(c['job'],)).fetchone()
                assert db.execute('SELECT account_reference FROM provider_operations WHERE id=%s',(c['operation'],)).fetchone()==(c['item'].contact_scope.account_reference,)
            if state=='unknown':raise ContactResponseUnknown('synthetic accepted response lost')
            return normalize_contact_response(response(),request)
    async def run():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));api_engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            cipher=ContactReceiptCipher(keys={'synthetic-native-k1':b'a'*32},active_key_id='synthetic-native-k1')
            c['holder']['adapter']=LiveContactAdapter(capability=c['cap'],account_reference=c['item'].contact_scope.account_reference,client=Client(),receipts=PostgresContactReceipts(worker,c['workspace'],c['cap'],cipher=cipher))
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=c['outbox'],generation=1,runtime_epoch=c['epoch'])
            first=await execute_step(worker,env,'start',research_engine=api_engine,environment='production')
            assert calls,'native selected contact path never prepared/submitted its confirmed request'
            assert first.state=='reconcile'
            assert await execute_step(worker,env,'start',research_engine=api_engine,environment='production')==first
            with psycopg.connect(c['dsn']) as db:
                ref=db.execute('SELECT id FROM contact_receipts WHERE operation_id=%s',(c['operation'],)).fetchone()[0]
            reopened=await c['holder']['adapter'].receipts.get(str(ref));assert reopened['state']==state
            assert held(c)==(('active',Decimal('0.100000')),0)
            assert selected_contact_status_capability()==(c['cap'],'production',True)
            # Actual automatic status outbox uses the same current registry
            # factory; saved private status cannot invent supplier billing proof.
            with psycopg.connect(c['dsn']) as db:
                status=db.execute("SELECT id FROM outbox_events WHERE event_type='contact.reconcile' AND payload->>'operation_id'=%s",(str(c['operation']),)).fetchone()[0]
                db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend='cloudflare',runtime_epoch=%s WHERE id=%s",(c['epoch'],status))
            status_env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=status,generation=1,runtime_epoch=c['epoch'])
            checked=await execute_step(worker,status_env,'start',research_engine=api_engine,environment='production')
            assert checked.state=='reconcile'
            assert await execute_step(worker,status_env,'start',research_engine=api_engine,environment='production')==checked
            assert len(calls)==1 and held(c)==(('active',Decimal('0.100000')),0)
            assert await c['holder']['adapter'].receipts.get(str(ref))==reopened
            if state=='received':
                assert reopened['response']['verified_contacts']==[]
                with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM contact_points WHERE company_id=%s',(calls[0].company_id,)).fetchone()==(0,)
        finally:await worker.dispose();await api_engine.dispose()
    asyncio.run(run());assert len(calls)==1 and c['factories']==['contact','contact'] and c['calls']==[]

@pytest.mark.parametrize('gate',['actor','domain','domain-review','policy','full-contract','key-owner','paid-dispatch','epoch'])
def test_actual_native_contact_denies_unready_current_basis_before_private_prepare_or_network(native_case,monkeypatch,gate):
    c=admitted(native_case);calls=[]
    with psycopg.connect(c['dsn']) as db:
        if gate=='actor':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE user_id=%s',(uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR),))
        elif gate=='domain':db.execute("UPDATE companies SET domain=NULL WHERE id=%s",(c['buyers'][0][1],))
        elif gate=='domain-review':db.execute('UPDATE company_aliases SET reviewed=false WHERE company_id=%s',(c['buyers'][0][1],))
        elif gate=='policy':db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s",(c['workspace'],))
        elif gate=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
    if gate=='full-contract':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((replace(c['item'],sandbox_evidence=('synthetic:changed-review',)),)))
    if gate=='paid-dispatch':monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','false');worker_settings.cache_clear()
    class Client:
        async def lookup(self,request):calls.append(request);raise AssertionError('unready contact must never reach supplier')
    async def run():
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')));api_engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            cipher=ContactReceiptCipher(keys={'synthetic-native-k1':b'a'*32},active_key_id='synthetic-native-k1')
            receipts=object() if gate=='key-owner' else PostgresContactReceipts(worker,c['workspace'],c['cap'],cipher=cipher)
            c['holder']['adapter']=LiveContactAdapter(capability=c['cap'],account_reference=c['item'].contact_scope.account_reference,client=Client(),receipts=receipts)
            env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=c['outbox'],generation=1,runtime_epoch=c['epoch'])
            first=await execute_step(worker,env,'start',research_engine=api_engine,environment='production')
            assert first.state==('done' if gate=='policy' else 'stale' if gate=='epoch' else 'blocked')
            assert await execute_step(worker,env,'start',research_engine=api_engine,environment='production')==first
            assert calls==[]
            assert held(c)==(('released',Decimal('0.000000')) if gate=='policy' else ('active',Decimal('0.100000')),0)
            with psycopg.connect(c['dsn']) as db:
                assert db.execute('SELECT count(*) FROM contact_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(0,)
                assert db.execute('SELECT status FROM provider_operations WHERE id=%s',(c['operation'],)).fetchone()==('cancelled' if gate=='policy' else 'intent',),'native failed closed only after falsely entering supplier submission'
        finally:await worker.dispose();await api_engine.dispose()
    asyncio.run(run())
