"""Real owned PG/native runner + bounded HTTP MockTransport, not vendor proof."""
import asyncio,json
from decimal import Decimal
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.providers.base import Money
from buyeros_api.providers import resend_delivery
from buyeros_api.providers.resend_delivery import ResendDeliveryHttpPool,DeliveryHttpPoolLimits,DeliveryWirePricing
from buyeros_api.execution import delivery_runner
from buyeros_api.execution.step_runner import execute_claimed
from tests.test_delivery_admission_db import admission_case
from tests.test_delivery_submission_db import submission_case,worker_dsn,counts
from tests.test_delivery_status_db import authority,snapshot

REF='49a3999c-0ce1-4ea6-ab68-afcd6dc2e794'

@pytest.mark.parametrize('response',['accepted','server-error','timeout'])
def test_actual_native_delivery_http_candidate_uses_committed_permit_once_and_keeps_full_hold(submission_case,monkeypatch,response):
    client,dsn,args,auth,original,execution=submission_case;before=snapshot(dsn,original);money=counts(dsn)
    requests=[];built=[];clients=[]
    pool=ResendDeliveryHttpPool(authority=authority(args,auth),api_key="owned-delivery-wire-test-only",limits=DeliveryHttpPoolLimits(4,2,5.0))
    async def handler(request):
        current=snapshot(dsn,original)
        assert current['original'][0][8:10]==('unknown',None) and current['operation']==('unknown_acceptance',None)
        assert current['original'][1][2]==current['original'][1][3]==auth.upper_bound
        with psycopg.connect(dsn) as db:
            db.execute("SET LOCAL lock_timeout='200ms'")
            assert db.execute('SELECT id FROM delivery_messages WHERE id=%s FOR UPDATE NOWAIT',(original.message_id,)).fetchone()
            assert db.execute('SELECT singleton FROM worker_runtime_control WHERE singleton=1 FOR UPDATE NOWAIT').fetchone()
            assert db.execute('SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT',(original.outbox_id,)).fetchone()
        requests.append(request)
        assert request.method=='POST' and str(request.url)=='https://api.resend.com/emails' and request.headers['Idempotency-Key']==args['key']
        prepared=built[0]._prepared
        assert json.loads(request.content)==dict(to=[prepared.payload['recipient']],subject=prepared.payload['subject'],text=prepared.payload['body'],**{'from':prepared.payload['sender']})
        if response=='timeout':raise httpx.ReadTimeout('owned mock timeout')
        return httpx.Response(200,json={'id':REF}) if response=='accepted' else httpx.Response(500)
    def client(**options):
        assert options['trust_env'] is False and options['follow_redirects'] is False and options['timeout']==10.0
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler),**options);clients.append(http);return http
    monkeypatch.setattr(resend_delivery,'_new_delivery_http_client',client)
    def factory(prepared):
        adapter=pool.bind(prepared=prepared,authorization=auth,pricing=DeliveryWirePricing(auth.pricing_version,auth.reviewed_contract_hash,Money(Decimal('0.010000'))))
        built.append(adapter);return adapter
    selection=delivery_runner.DeliverySelection(auth,authority(args,auth),factory)
    monkeypatch.setattr(delivery_runner,'selected_delivery_runtime',lambda current:selection)
    async def run():
        engine=create_async_engine(async_database_url(worker_dsn(dsn)))
        try:
            assert clients==[] and requests==[]
            async with pool:
                assert len(clients)==1 and requests==[]
                result=await execute_claimed(engine,execution.envelope,'start',execution.owner)
                repeated=await execute_claimed(engine,execution.envelope,'start',execution.owner)
            assert len(clients)==1 and clients[0].is_closed
            return result,repeated
        finally:
            await engine.dispose()
    reply,repeated=asyncio.run(run());after=snapshot(dsn,original)
    assert (reply.state,reply.code)==('reconcile','PROVIDER_UNKNOWN') and (repeated.state,repeated.code)==('stale','STALE_FENCE')
    assert len(requests)==len(built)==1 and counts(dsn)==money and after['cost']==0
    assert after['original'][0][8:10]==(('accepted',REF) if response=='accepted' else ('unknown',None))
    assert len(after['events'])==(1 if response=='accepted' else 0) and before['original'][1:]==after['original'][1:]
    assert before['original'][0][:8]==after['original'][0][:8] and before['original'][0][10:]==after['original'][0][10:]
