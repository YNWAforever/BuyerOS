"""Current contact quote/new-call contract; owned PG and synthetic IO, public selectors held."""
import asyncio,uuid,json,hashlib
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.routes.quotes import selected_contact_quote_capability
from buyeros_api.execution.handlers.contact_submit import execute_contact_lookup
from buyeros_api.providers import base,registry
from buyeros_api.providers.base import ProviderIntent
from buyeros_api.providers.registry import ContactLookupScope,ProviderRegistration,ProviderRegistry
from buyeros_api.providers.contact_receipts import PostgresContactReceipts
from buyeros_api.providers.live_contact import ContactRequest,ContactReceiptCipher,LiveContactAdapter,ContactResponseUnknown,normalize_contact_response
from tests.test_live_contact_adapter import capability,response
from tests.test_lookup_quotes_db import quote_case,_post,_body
from tests.test_contact_confirm_atomicity_db import _limits,_confirm
from tests.test_buyer_review_db import api,WORKSPACE_A,OPERATOR
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn

@pytest.fixture
def scoped_quote_case(quote_case,monkeypatch):
    client,dsn,buyers=quote_case;calls=[]
    cap=replace(capability(),idempotency='verified',status='verified')
    scope=ContactLookupScope('synthetic-contact-account-v1',(('US',('en',)),),True,('synthetic:saved-status-nocharge',))
    def factory():calls.append('factory');raise AssertionError('contact planning or confirmation must never construct adapter')
    item=ProviderRegistration(cap,factory,('synthetic:reviewed-contact-scope',),contact_scope=scope)
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'hunter'}));monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'hunter'}))
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((item,)))
    # Consumer guard test only; default public selector remains closed until native prepare is delivered.
    client.app.dependency_overrides[selected_contact_quote_capability]=lambda:(cap,'production')
    _limits(client,dsn)
    with psycopg.connect(dsn) as db:
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        db.execute("UPDATE companies SET domain='fictional-sensors.com' WHERE id=%s",(buyers[0][1],))
        db.execute("INSERT INTO company_aliases(id,workspace_id,company_id,alias_type,normalized_value,provenance,reviewed) VALUES(%s,%s,%s,'domain','fictional-sensors.com','owned explicit human domain review',true)",(uuid.uuid4(),WORKSPACE_A,buyers[0][1]))
    yield {'client':client,'dsn':dsn,'buyers':buyers,'cap':cap,'item':item,'calls':calls,'workspace':uuid.UUID(WORKSPACE_A)}
    with psycopg.connect(dsn) as db:
        db.execute('DELETE FROM contact_receipts WHERE workspace_id=%s',(WORKSPACE_A,))
        db.execute('DELETE FROM company_aliases WHERE company_id=%s',(buyers[0][1],))

def expected_configuration(c):
    return {'registry_contract_hash':c['item'].contract_hash,
        'receipt_contract_hash':ProviderRegistration(c['cap'],lambda:None).contract_hash,
        'account_reference':c['item'].contact_scope.account_reference,'market':'US','language':'en',
        'contact_type':'business_email','limit':10}

def quote(c):
    reply=_post(c['client'],_body(c['buyers'][:1]),key='scoped-contact-quote')
    assert reply.status_code==201,reply.text
    return reply.json()['data']

def no_admission(c):
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM enrichment_jobs WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0]==0
    assert c['calls']==[]

def drift(c,monkeypatch,kind):
    item=c['item']
    if kind=='account':item=replace(item,contact_scope=replace(item.contact_scope,account_reference='synthetic-contact-account-v2'))
    elif kind=='count':item=replace(item,contact_scope=replace(item.contact_scope,max_contacts=9))
    elif kind=='status-proof':item=replace(item,contact_scope=replace(item.contact_scope,status_evidence=('synthetic:status-review-v2',)))
    elif kind=='sandbox':item=replace(item,sandbox_evidence=('synthetic:changed-contact-review',))
    elif kind=='unscoped':item=replace(item,contact_scope=None)
    elif kind=='billable-status':item=replace(item,contact_scope=replace(item.contact_scope,nonbillable_status=False))
    elif kind=='allowlist-empty':monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset())
    elif kind=='unselected':monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry());return
    elif kind=='capability-swapped':item=replace(item,capability=replace(item.capability,adapter_version='synthetic-new-adapter'))
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry((item,)))

def test_production_quote_freezes_full_current_contact_scope_without_factory_budget_or_operation(scoped_quote_case):
    c=scoped_quote_case;q=quote(c)
    with psycopg.connect(c['dsn']) as db:selection=db.execute('SELECT selection FROM enrichment_quotes WHERE id=%s',(q['id'],)).fetchone()[0]
    assert selection.get('contact_configuration')==expected_configuration(c),'production quote omitted reviewed account/pair/count/full-registry digest'
    no_admission(c)

@pytest.mark.parametrize('kind',['account','count','status-proof','sandbox','unscoped','billable-status','allowlist-empty','unselected'])
def test_changed_contact_registry_requires_fresh_explicit_quote_before_confirm_admission(scoped_quote_case,monkeypatch,kind):
    c=scoped_quote_case;q=quote(c);drift(c,monkeypatch,kind)
    reply=_confirm(c['client'],q,key='scoped-contact-confirm')
    assert reply.status_code==(409 if kind in {'account','count','status-proof','sandbox'} else 503),reply.text
    no_admission(c)

@pytest.mark.parametrize('kind',['unscoped','billable-status','allowlist-empty','unselected','capability-swapped'])
def test_production_quote_rejects_typed_capability_without_exact_current_reviewed_registry(scoped_quote_case,monkeypatch,kind):
    c=scoped_quote_case;drift(c,monkeypatch,kind)
    reply=_post(c['client'],_body(c['buyers'][:1]),key='scoped-contact-denied-quote')
    assert reply.status_code==503,reply.text
    no_admission(c)

@pytest.fixture
def confirmed_case(scoped_quote_case):
    c=scoped_quote_case;q=quote(c);reply=_confirm(c['client'],q,key='scoped-contact-confirm');assert reply.status_code==202,reply.text
    job=reply.json()['data'];c={**c,'quote':q,'job':uuid.UUID(job['id'])}
    with psycopg.connect(c['dsn']) as db:
        backend,epoch=db.execute('SELECT backend,epoch FROM worker_runtime_control').fetchone()
        c['outbox']=db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend=%s,runtime_epoch=%s WHERE workspace_id=%s AND intent_key=%s RETURNING id",(backend,epoch,WORKSPACE_A,'contact.lookup:'+job['id'])).fetchone()[0]
        c['operation'],key=db.execute('SELECT id,intent_key FROM provider_operations WHERE job_id=%s',(job['id'],)).fetchone()
    c['request']=ContactRequest(key,c['workspace'],uuid.UUID('a0000000-0000-4000-8000-000000000001'),uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR),uuid.UUID(c['buyers'][0][0]),uuid.UUID(c['buyers'][0][1]),1,uuid.UUID(q['id']),q['quote_hash'],c['cap'].pricing_version,c['cap'].adapter_version,'fictional-sensors.com','US','en','Procurement manager','business_email',10)
    return c

def held(c):
    with psycopg.connect(c['dsn']) as db:return db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(c['job'],)).fetchone(),db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(c['job'],)).fetchone()[0]

async def engines(c,exercise):
    api_engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])));worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
    try:
        cipher=ContactReceiptCipher(keys={'synthetic-k1':b'a'*32},active_key_id='synthetic-k1')
        first=PostgresContactReceipts(api_engine,c['workspace'],c['cap'],cipher=cipher)
        store=PostgresContactReceipts(worker,c['workspace'],c['cap'],cipher=cipher)
        await exercise(first,store,worker,cipher)
    finally:await api_engine.dispose();await worker.dispose()

@pytest.mark.parametrize('kind',['account','count','status-proof','sandbox','unscoped','allowlist-empty','unselected','request-count'])
def test_new_private_contact_prepare_rechecks_full_confirmed_quote_before_receipt_write(confirmed_case,monkeypatch,kind):
    c=confirmed_case
    async def exercise(first,store,engine,cipher):
        req=c['request']
        if kind=='request-count':req=replace(req,limit=9)
        else:drift(c,monkeypatch,kind)
        with pytest.raises(ValueError,match='current contact'):
            await first.prepare(req,operation_id=c['operation'],outbox_id=c['outbox'],expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM contact_receipts WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0]==0
        assert held(c)==(('active',Decimal('0.100000')),0)
    asyncio.run(engines(c,exercise));assert c['calls']==[]

@pytest.mark.parametrize('kind',['account','count','status-proof','sandbox','unscoped','allowlist-empty','unselected','unbound-quote'])
def test_prepared_contact_claim_rechecks_full_current_registry_before_supplier_io(confirmed_case,monkeypatch,kind):
    c=confirmed_case
    async def exercise(first,store,engine,cipher):
        ref=await first.prepare(c['request'],operation_id=c['operation'],outbox_id=c['outbox'],expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        with psycopg.connect(c['dsn']) as db:
            db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(c['operation'],))
            if kind=='unbound-quote':db.execute("UPDATE enrichment_quotes SET selection=selection-'contact_configuration' WHERE id=%s",(c['request'].quote_id,))
        if kind!='unbound-quote':drift(c,monkeypatch,kind)
        with pytest.raises(ValueError,match='current contact'):
            await store.claim(ProviderIntent(c['request'].key,'contact','US','en','Procurement manager'))
        assert (await first.get(ref))['state']=='prepared'
        assert held(c)==(('active',Decimal('0.100000')),0)
    asyncio.run(engines(c,exercise));assert c['calls']==[]

@pytest.mark.parametrize('state',['received','unknown'])
def test_original_contact_received_or_unknown_reopens_after_current_scope_revocation_without_resubmit(confirmed_case,monkeypatch,state):
    c=confirmed_case;calls=[]
    class Client:
        async def lookup(self,request):
            calls.append(request)
            with psycopg.connect(c['dsn']) as db:
                db.execute('SELECT id FROM enrichment_jobs WHERE id=%s FOR UPDATE NOWAIT',(c['job'],))
                db.execute('SELECT id FROM contact_receipts WHERE intent_key=%s FOR UPDATE NOWAIT',(request.key,))
            if state=='unknown':raise ContactResponseUnknown('synthetic accepted response lost')
            return normalize_contact_response(response(),request)
    async def exercise(first,store,engine,cipher):
        ref=await first.prepare(c['request'],operation_id=c['operation'],outbox_id=c['outbox'],expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        adapter=LiveContactAdapter(capability=c['cap'],account_reference=c['item'].contact_scope.account_reference,client=Client(),receipts=store)
        assert await execute_contact_lookup(engine,c['workspace'],c['job'],1,adapter,environment='production',max_operations=1) in {'accepted','unknown'}
        original=await first.get(ref);assert original['state']==state
        drift(c,monkeypatch,'unselected')
        reopened=PostgresContactReceipts(engine,c['workspace'],c['cap'],cipher=cipher)
        assert await reopened.get(ref)==original
        repeated=await adapter.submit(ProviderIntent(c['request'].key,'contact','US','en','Procurement manager'))
        assert repeated.state==('accepted' if state=='received' else 'unknown') and len(calls)==1
        assert held(c)==(('active',Decimal('0.100000')),0)
        if state=='received':
            assert original['response']['verified_contacts']==[] and original['response']['candidates'][0]['verification_status']=='needs_review'
            with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM contact_points WHERE company_id=%s',(c['request'].company_id,)).fetchone()[0]==0
    asyncio.run(engines(c,exercise));assert c['calls']==[] and len(calls)==1
