"""Focused receipt/fence/contract guards: owned PG and HTTP only."""
import asyncio,uuid
from dataclasses import replace
import httpx,psycopg,pytest
from tests.test_live_search_adapter import module,capability,Receipts,request
from tests.test_live_search_db import search_case,stores,hold
from tests.test_buyer_review_db import api
from buyeros_api.providers.base import ProviderIntent
from buyeros_api.execution.external_runner import execute_external

def test_response_without_durable_receipt_cannot_claim_accepted():
    m=module();key='c61:'+uuid.uuid4().hex;intent=ProviderIntent(key,'search','HK','en','company');calls=[]
    class NoCommit(Receipts):
        async def finish(self,*args,**kwargs):pass # fixture fence prevents a stale write
    class Client:
        async def search(self,*args):calls.append(args);return []
    adapter=m.LiveSearchAdapter(capability=capability(),client=Client(),receipts=NoCommit(request(m,key)))
    async def exercise():
        first=await adapter.submit(intent)
        assert first.state=='unknown'
        assert (await adapter.status(first.provider_ref)).state=='unknown'
        assert (await adapter.submit(intent)).state=='unknown'
    asyncio.run(exercise());assert len(calls)==1

def test_runtime_epoch_change_during_response_cannot_claim_accepted(search_case):
    case=search_case;calls=[]
    def response(req):
        calls.append(req)
        with psycopg.connect(case['dsn']) as db:db.execute('UPDATE worker_runtime_control SET epoch=epoch+1')
        return httpx.Response(200,json={'web':{'results':[]}})
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                client=m.BraveSearchClient(api_key='offline-token-not-real',http=http,language_codes={'en':'en'},api_version='2026-10-01')
                adapter=m.LiveSearchAdapter(capability=case['cap'],client=client,receipts=store)
                assert await execute_external(engine,case['workspace'],case['operation'],1,adapter,case['intent'],environment='test')=='unknown'
                assert (await store.get(ref))['state']=='submitting'
                assert (await adapter.status(ref)).state=='unknown'
                assert (await adapter.submit(case['intent'])).state=='unknown'
                assert hold(case)[0][0]=='active' and hold(case)[1]==0
    try:asyncio.run(exercise());assert len(calls)==1
    finally:
        with psycopg.connect(case['dsn']) as db:
            epoch=db.execute('SELECT epoch FROM worker_runtime_control').fetchone()[0]
            # Epoch monotonic: align this owned fixture's remaining outbox rows,
            # not the production runtime; no decrement/replay of old intents.
            db.execute("UPDATE outbox_events SET runtime_epoch=%s WHERE state IN ('ready','dispatched')",(epoch,))

@pytest.mark.parametrize('statement',[
    "UPDATE memberships SET roles='{viewer}',version=version+1 WHERE user_id=%s",
    "UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s",
    "UPDATE budget_reservations SET remaining_hold=0 WHERE operation_id=%s",
    "UPDATE provider_operations SET cancel_requested=true WHERE id=%s",
    "UPDATE outbox_events SET fencing_generation=2 WHERE id=%s",
])
def test_current_scope_hold_policy_or_fence_change_blocks_search(search_case,statement):
    case=search_case;calls=[]
    async def exercise():
        async with stores(case) as (m,engine,_,store,ref):
            key=case['actor'] if 'memberships' in statement else case['workspace'] if 'policy_decisions' in statement else case['outbox'] if 'outbox_events' in statement else case['operation']
            with psycopg.connect(case['dsn']) as db:db.execute(statement,(key,))
            class Client:
                async def search(self,*args):calls.append(args);raise AssertionError('network must remain closed')
            result=await execute_external(engine,case['workspace'],case['operation'],1,m.LiveSearchAdapter(capability=case['cap'],client=Client(),receipts=store),case['intent'],environment='test')
            assert result in {'unknown','blocked','stale'}
            assert (await store.get(ref))['state']=='prepared'
            assert hold(case)[1]==0
    asyncio.run(exercise());assert calls==[]

def test_existing_intent_cannot_be_rebound_to_changed_query_or_tariff(search_case):
    case=search_case
    async def exercise():
        async with stores(case) as (m,engine,api_store,store,ref):
            saved=await store.get(ref)
            with pytest.raises(ValueError,match='already frozen'):
                await api_store.prepare(replace(saved['request'],query='changed query'),operation_id=case['operation'],outbox_id=case['outbox'])
            changed=m.PostgresSearchReceipts(engine,case['workspace'],replace(case['cap'],pricing_version='changed-tariff'))
            with pytest.raises(ValueError,match='receipt changed'):await changed.claim(case['intent'])
            assert (await store.get(ref))['state']=='prepared' and hold(case)[1]==0
    asyncio.run(exercise())

@pytest.mark.parametrize('body',[
    b'x'*262145,
    b'{malformed-json',
    b'{"web":{"results":[{"url":"http://127.0.0.1/a","title":"Unsafe","description":"data"}]}}',
    b'{"web":{"results":[{"url":"https://sensors.example.test","title":"offline-token-not-real","description":"data"}]}}',
],ids=['oversize','malformed-json','private-url','secret-echo'])
def test_oversize_corrupt_private_or_secret_echo_response_is_unknown(body):
    m=module();calls=[]
    def response(req):calls.append(req);return httpx.Response(200,content=body)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response),follow_redirects=True) as http:
            client=m.BraveSearchClient(api_key='offline-token-not-real',http=http,language_codes={'en':'en'},api_version='2026-10-01')
            with pytest.raises(m.SearchResponseUnknown):await client.search('query','HK','en',20)
    asyncio.run(exercise());assert len(calls)==1


@pytest.mark.parametrize('boundary',['request','http'])
def test_padded_oversize_query_is_rejected_before_network(boundary):
    m=module();query=' '*601+'industrial sensors';calls=[]
    if boundary=='request':
        with pytest.raises(ValueError):m.SearchRequest(key='c61:query-bound',query=query,market='HK',language='en',role='company',limit=20,project_id=uuid.uuid4(),actor_id=uuid.uuid4())
    else:
        def response(req):calls.append(req);return httpx.Response(200,json={'web':{'results':[]}})
        async def exercise():
            async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
                client=m.BraveSearchClient(api_key='offline-token-not-real',http=http,language_codes={'en':'en'},api_version='2026-10-01')
                with pytest.raises(ValueError):await client.search(query,'HK','en',20)
        asyncio.run(exercise())
    assert calls==[]

@pytest.mark.parametrize('service',['search','model'])
def test_native_generic_dispatch_selects_payload_service_without_contact_fallback(monkeypatch,service):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from buyeros_api.execution import provider_dispatch,external_runner
    selected=object();calls=[]
    def resolve(actual,*,environment):calls.append((actual,environment));return selected
    @asynccontextmanager
    async def session(*args):yield object()
    async def execute(*args,**kwargs):assert args[4] is selected;return 'unknown'
    async def terminal(*args):return None
    class Execution:
        finished=False
        envelope=SimpleNamespace(workspace_id=uuid.uuid4(),generation=1)
        row=SimpleNamespace(event_type='provider.external',intent_key='c61:native-routing',payload={'operation_id':str(uuid.uuid4()),'service':service,'market':'US','language':'en','role':'company'})
        async def guard(self,*args):return True
        def finish(self,result):self.result=result;self.finished=True
    monkeypatch.setattr(provider_dispatch,'resolve_provider_adapter',resolve)
    monkeypatch.setattr(provider_dispatch,'tenant_session',session)
    monkeypatch.setattr(provider_dispatch,'terminal_business_outcome',terminal)
    monkeypatch.setattr(external_runner,'execute_external',execute)
    asyncio.run(provider_dispatch.execute_provider_claimed(object(),Execution(),environment='test'))
    assert calls==[(service,'test')]


@pytest.mark.parametrize('hop',['private-redirect','same-host-dns-rebind'])
def test_fetch_redirect_private_blocked(hop):
    from tests.test_ingestion_security import FixtureTransport,MemoryStore,INTENT
    m=module();store=MemoryStore()
    class Rebind(FixtureTransport):
        resolutions=0
        async def resolve(self,host):
            self.resolutions+=1
            return ['93.184.216.34'] if self.resolutions==1 else ['169.254.169.254']
    location='https://169.254.169.254/private' if hop=='private-redirect' else 'https://example.com/private'
    transport=Rebind(responses=[(302,{'location':location},b'')])
    adapter=m.LiveSearchAdapter(capability=capability(),client=None,receipts=None)
    result=asyncio.run(adapter.fetch_source(INTENT,transport,store))
    assert result['status']=='blocked' and store.saved==[] and len(transport.calls)==1
    assert transport.calls[0][1]=='93.184.216.34'
    if hop=='same-host-dns-rebind':assert transport.resolutions==2
