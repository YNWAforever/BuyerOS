"""Owned MockTransport protocol only; no provider/account/billing acceptance."""
import asyncio,importlib,json,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
import httpx,pytest
from buyeros_api.api.errors import ApiError
from buyeros_api.providers.base import Money,SubmissionResult
from buyeros_api.providers.delivery import DeliveryIntent
from buyeros_api.services.delivery_budget import DeliveryBudgetAuthorization
from buyeros_api.services.delivery_service import PreparedDelivery,delivery_payload_digest
from buyeros_api.services.delivery_status import DeliveryStatusAuthority

KEY='owned-delivery-wire-test-only'
REF='49a3999c-0ce1-4ea6-ab68-afcd6dc2e794'

def module():
    p=Path(__file__).resolve().parents[1]/'buyeros_api/providers/resend_delivery.py'
    assert p.is_file(),'bounded unselected Resend delivery adapter missing'
    return importlib.import_module('buyeros_api.providers.resend_delivery')

def inputs():
    ids=[uuid.uuid4() for _ in range(6)]
    payload=MappingProxyType(dict(subject='Owned subject',body='Owned body emoji 🧭',recipient='recipient@example.test',sender='sender@example.test'))
    intent=DeliveryIntent('owned:delivery:wire',ids[0],ids[1],ids[2],ids[3],ids[4],delivery_payload_digest(payload))
    prepared=PreparedDelivery(intent,payload)
    auth=DeliveryBudgetAuthorization(ids[0],ids[5],ids[3],(ids[2],),'resend','owned-wire-account','owned-pricing-v1',Decimal('0.010000'),'USD','b'*64,True,True,True,datetime.now(timezone.utc)+timedelta(minutes=10))
    status=DeliveryStatusAuthority(ids[0],'resend',auth.account_reference,auth.scope_hash,'b'*64,True,datetime.now(timezone.utc)+timedelta(hours=1))
    return prepared,auth,status

async def adapter_case(handler,*,change=None,pricing=None):
    prepared,auth,status=inputs()
    if change is not None:prepared,auth,status=change(prepared,auth,status)
    http=httpx.AsyncClient(transport=httpx.MockTransport(handler),trust_env=False,follow_redirects=True)
    try:
        pricing=pricing or module().DeliveryWirePricing('owned-pricing-v1','b'*64,Money(Decimal('0.010000')))
        adapter=module().ResendDeliveryAdapter(prepared=prepared,authorization=auth,reconciliation=status,pricing=pricing,api_key=KEY,http=http)
        yield adapter,prepared,auth,status
    finally:await http.aclose()

def test_resend_wire_fixed_POST_only_original_key_and_server_plaintext_payload():
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.method=='POST' and str(request.url)=='https://api.resend.com/emails'
        assert request.headers['Authorization']=='Bearer '+KEY and request.headers['Idempotency-Key']=='owned:delivery:wire'
        assert json.loads(request.content)=={'from':'sender@example.test','to':['recipient@example.test'],'subject':'Owned subject','text':'Owned body emoji 🧭'}
        return httpx.Response(200,json={'id':REF})
    async def one():
        async for adapter,prepared,auth,status in adapter_case(handler):
            assert adapter.estimate(prepared.intent)==Money(Decimal('0.010000'))
            first=await adapter.submit(prepared.intent);second=await adapter.submit(prepared.intent)
            assert first==second==SubmissionResult('accepted',REF) and len(requests)==1
            assert KEY not in repr(adapter) and prepared.payload['body'] not in repr(adapter)
    asyncio.run(one())

@pytest.mark.parametrize('state_code',[201,301,302,307,308,400,401,403,404,409,422,429,500,502,503])
def test_resend_wire_non200_no_redirect_retry_or_no_charge_claim(state_code):
    requests=[]
    def handler(request):
        requests.append(request);return httpx.Response(state_code,headers={'Location':'https://unrelated.example.test/steal'},json={'id':REF})
    async def one():
        async for adapter,prepared,auth,status in adapter_case(handler):
            assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None)
            assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None) and len(requests)==1
    asyncio.run(one())

@pytest.mark.parametrize('raw',[b'not-json',b'{"id":null}',b'{"id":"not-a-uuid"}',b'{"id":"00000000-0000-0000-0000-000000000000"}',b'{"id":"49a3999c-0ce1-4ea6-ab68-afcd6dc2e794","id":"49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"}',b'{"id":"49A3999C-0CE1-4EA6-AB68-AFCD6DC2E794"}',b'{"id":"49a3999c-0ce1-4ea6-ab68-afcd6dc2e794","usage":0}',b'{"id":NaN}',KEY.encode(),b'x'*262145],ids=['not-json','null-ref','opaque-ref','zero-ref','duplicate-ref','uppercase-ref','unexpected-usage','NaN','credential-echo','oversize'])
def test_resend_wire_malformed_ambiguous_credential_echo_or_unbounded_response_stays_unknown(raw):
    requests=[]
    def handler(request):requests.append(request);return httpx.Response(200,content=raw)
    async def one():
        async for adapter,prepared,auth,status in adapter_case(handler):
            assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None)
            assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None) and len(requests)==1
    asyncio.run(one())

@pytest.mark.parametrize('error',[httpx.ReadTimeout('owned timeout'),httpx.ConnectError('owned network failure'),asyncio.CancelledError()])
def test_resend_wire_network_error_or_cancellation_cannot_retry_original(error):
    calls=[]
    def handler(request):calls.append(request);raise error
    async def one():
        async for adapter,prepared,auth,status in adapter_case(handler):
            if isinstance(error,asyncio.CancelledError):
                with pytest.raises(asyncio.CancelledError):await adapter.submit(prepared.intent)
            else:assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None)
            assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None) and len(calls)==1
    asyncio.run(one())

def test_resend_wire_twelve_concurrent_calls_one_POST_remaining_unknown_until_original_finishes():
    calls=[]
    async def handler(request):calls.append(request);await asyncio.sleep(0.01);return httpx.Response(200,json={'id':REF})
    async def one():
        async for adapter,prepared,auth,status in adapter_case(handler):
            results=await asyncio.gather(*(adapter.submit(prepared.intent) for _ in range(12)))
            assert len(calls)==1 and sum(r.state=='accepted' for r in results)==1 and sum(r.state=='unknown' for r in results)==11
            assert await adapter.submit(prepared.intent)==SubmissionResult('accepted',REF) and len(calls)==1
    asyncio.run(one())

@pytest.mark.parametrize('fault',['workspace','account','contract','scope','provider','unreviewed','expired','sender','digest'])
def test_resend_wire_wrong_unreviewed_expired_or_rebound_input_refuses_before_HTTP(fault):
    calls=[]
    def handler(request):calls.append(request);pytest.fail('invalid delivery binding reached HTTP')
    def change(prepared,auth,status):
        if fault=='workspace':status=replace(status,workspace_id=uuid.uuid4())
        elif fault=='account':status=replace(status,account_reference='wrong-account')
        elif fault=='contract':status=replace(status,reviewed_contract_hash='c'*64)
        elif fault=='scope':status=replace(status,scope_hash='c'*64)
        elif fault=='provider':auth=replace(auth,provider_name='common-contact-provider')
        elif fault=='unreviewed':auth=replace(auth,reviewed=False)
        elif fault=='expired':auth=replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
        elif fault=='sender':auth=replace(auth,sender_identity_id=uuid.uuid4())
        else:prepared=PreparedDelivery(prepared.intent,MappingProxyType(dict(prepared.payload,body='client arbitrary body')))
        return prepared,auth,status
    async def one():
        module() # A missing implementation is an assertion, never a refusal.
        with pytest.raises((ValueError,ApiError)):
            async for adapter,*_ in adapter_case(handler,change=change):pytest.fail('invalid delivery binding constructed')
        assert calls==[]
    asyncio.run(one())

def test_resend_wire_rebound_intent_cannot_estimate_or_submit():
    requests=[]
    async def one():
        async for adapter,prepared,auth,status in adapter_case(lambda request:requests.append(request)):
            changed=replace(prepared.intent,key='owned:other:key')
            with pytest.raises(ValueError):adapter.estimate(changed)
            with pytest.raises(ValueError):await adapter.submit(changed)
            assert requests==[]
    asyncio.run(one())

@pytest.mark.parametrize('event,state',[('sent','accepted'),('delivered','delivered'),('bounced','bounced'),('complained','complained'),('failed','failed'),('opened','unknown'),('clicked','unknown'),('suppressed','unknown'),('queued','unknown'),('scheduled','unknown'),('delivery_delayed','unknown'),('unsubscribed','unknown'),('invented','unknown')])
def test_resend_wire_status_GET_only_exact_original_id_and_conservative_event(event,state):
    requests=[]
    def handler(request):
        requests.append(request);assert request.method=='GET' and str(request.url)=='https://api.resend.com/emails/'+REF
        assert 'Idempotency-Key' not in request.headers and request.content==b''
        return httpx.Response(200,json={'id':REF,'last_event':event})
    async def one():
        async for adapter,prepared,auth,status in adapter_case(handler):
            result=await adapter.status(REF)
            assert result.state==state and result.provider_ref==REF and result.event_id is None and len(requests)==1
    asyncio.run(one())

@pytest.mark.parametrize('fault',['404','redirect','foreign-ref','missing-id','duplicate-id','invalid-json'])
def test_resend_wire_unknown_status_never_rebinds_ref_or_submits(fault):
    requests=[]
    def handler(request):
        requests.append(request)
        if fault=='404':return httpx.Response(404,json={'message':'not found'})
        if fault=='redirect':return httpx.Response(302,headers={'Location':'https://unrelated.example.test/steal'})
        if fault=='foreign-ref':return httpx.Response(200,json={'id':str(uuid.uuid4()),'last_event':'delivered'})
        if fault=='missing-id':return httpx.Response(200,json={'last_event':'delivered'})
        if fault=='duplicate-id':return httpx.Response(200,content=('{"id":"'+REF+'","id":"'+REF+'","last_event":"delivered"}').encode())
        return httpx.Response(200,content=b'not-json')
    async def one():
        async for adapter,prepared,auth,status in adapter_case(handler):
            result=await adapter.status(REF)
            assert result.state=='unknown' and result.provider_ref==REF and len(requests)==1 and requests[0].method=='GET'
    asyncio.run(one())

@pytest.mark.parametrize('ref',[None,'','not-uuid','../../other','49A3999C-0CE1-4EA6-AB68-AFCD6DC2E794','00000000-0000-0000-0000-000000000000'])
def test_resend_wire_status_requires_existing_canonical_ref_no_key_lookup(ref):
    calls=[]
    async def one():
        async for adapter,*_ in adapter_case(lambda request:calls.append(request)):
            with pytest.raises(ValueError):await adapter.status(ref)
            assert calls==[]
    asyncio.run(one())


def reader_type():
    cls=getattr(module(),'ResendDeliveryStatusReader',None)
    assert callable(cls),'cold retained GET-only delivery status reader missing'
    return cls

def test_cold_retained_delivery_status_reader_needs_no_new_send_authority_or_payload():
    async def one():
        cls=reader_type();prepared,auth,status=inputs();expired=replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(days=1),selected=False,sender_verified=False)
        assert expired.valid_until<datetime.now(timezone.utc)
        calls=[]
        def handler(request):
            calls.append(request);assert request.method=='GET' and str(request.url)=='https://api.resend.com/emails/'+REF
            return httpx.Response(200,json={'id':REF,'last_event':'delivered'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler),trust_env=False) as http:
            reader=cls(authority=status,provider_ref=REF,api_key=KEY,http=http)
            result=await reader.status()
            assert result.state=='delivered' and result.provider_ref==REF and len(calls)==1
            assert not hasattr(reader,'submit') and not hasattr(reader,'estimate') and KEY not in repr(reader)
    asyncio.run(one())

@pytest.mark.parametrize('fault',['unreviewed','expired','provider'])
def test_cold_retained_status_invalid_authority_refuses_before_HTTP(fault):
    async def one():
        cls=reader_type();prepared,auth,status=inputs()
        if fault=='unreviewed':status=replace(status,reviewed=False)
        elif fault=='expired':status=replace(status,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
        else:status=replace(status,provider_name='other-provider')
        calls=[]
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:calls.append(request)),trust_env=False) as http:
            with pytest.raises((ValueError,ApiError)):cls(authority=status,provider_ref=REF,api_key=KEY,http=http)
            assert calls==[]
    asyncio.run(one())

def test_cold_retained_status_expiry_after_construction_cannot_query_HTTP(monkeypatch):
    async def one():
        cls=reader_type();prepared,auth,status=inputs();calls=[]
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:calls.append(request)),trust_env=False) as http:
            reader=cls(authority=status,provider_ref=REF,api_key=KEY,http=http)
            monkeypatch.setattr(reader,'_authority',replace(status,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1)))
            with pytest.raises(ApiError) as error:await reader.status()
            assert error.value.code=='PROVIDER_UNAVAILABLE' and calls==[]
    asyncio.run(one())
