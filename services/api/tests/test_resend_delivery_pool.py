"""Owned HTTP lifecycle and MockTransport only; no provider activation."""
import asyncio,importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import httpx,pytest
from buyeros_api.api.errors import ApiError
from buyeros_api.providers.base import Money,SubmissionResult
from test_resend_delivery_transport import inputs,KEY,REF

def module():
    wire=importlib.import_module('buyeros_api.providers.resend_delivery')
    assert hasattr(wire,'ResendDeliveryHttpPool'),'reviewed candidate HTTP pool lifecycle missing'
    return wire

def setup(monkeypatch,handler):
    wire=module();made=[];kwargs=[]
    def client(**options):
        kwargs.append(options);http=httpx.AsyncClient(transport=httpx.MockTransport(handler),**options);made.append(http);return http
    monkeypatch.setattr(wire,'_new_delivery_http_client',client)
    prepared,auth,status=inputs()
    limits=wire.DeliveryHttpPoolLimits(max_connections=4,max_keepalive_connections=2,keepalive_expiry=5.0)
    pool=wire.ResendDeliveryHttpPool(authority=status,api_key=KEY,limits=limits)
    pricing=wire.DeliveryWirePricing('owned-pricing-v1','b'*64,Money(Decimal('0.010000')))
    return pool,prepared,auth,status,pricing,made,kwargs

def test_resend_pool_no_HTTP_during_constructor_entry_binding_and_estimate(monkeypatch):
    requests=[];pool,prepared,auth,status,pricing,made,options=setup(monkeypatch,lambda q:requests.append(q))
    assert made==[] and requests==[] and KEY not in repr(pool)
    async def one():
        async with pool:
            first=pool.bind(prepared=prepared,authorization=auth,pricing=pricing)
            second=pool.bind(prepared=prepared,authorization=auth,pricing=pricing)
            reader=pool.retained_reader(REF)
            assert first._http is second._http is reader._http is made[0]
            assert first.estimate(prepared.intent)==pricing.estimate and requests==[]
            assert not hasattr(reader,'submit') and not hasattr(reader,'estimate')
        assert made[0].is_closed and requests==[]
    asyncio.run(one())
    assert len(made)==len(options)==1
    assert options[0]['trust_env'] is False and options[0]['follow_redirects'] is False and options[0]['timeout']==10.0
    limits=options[0]['limits'];assert limits.max_connections==4 and limits.max_keepalive_connections==2 and limits.keepalive_expiry==5.0

def test_resend_pool_binding_before_enter_after_close_or_second_enter_refuses(monkeypatch):
    pool,prepared,auth,status,pricing,made,_=setup(monkeypatch,lambda q:pytest.fail('lifecycle refusal reached HTTP'))
    def bind():return pool.bind(prepared=prepared,authorization=auth,pricing=pricing)
    with pytest.raises(RuntimeError):bind()
    with pytest.raises(RuntimeError):pool.retained_reader(REF)
    async def one():
        async with pool:
            with pytest.raises(RuntimeError):await pool.__aenter__()
        with pytest.raises(RuntimeError):bind()
        with pytest.raises(RuntimeError):pool.retained_reader(REF)
        with pytest.raises(RuntimeError):await pool.__aenter__()
        await pool.__aexit__(None,None,None)
        assert len(made)==1 and made[0].is_closed
    asyncio.run(one())

def test_resend_pool_closes_after_owner_exception(monkeypatch):
    pool,*rest=setup(monkeypatch,lambda q:pytest.fail('unexpected HTTP'));made=rest[-2]
    async def one():
        with pytest.raises(ValueError,match='owned exception'):
            async with pool:raise ValueError('owned exception')
        assert len(made)==1 and made[0].is_closed
    asyncio.run(one())

def test_resend_pool_cancellation_during_cleanup_waits_for_owned_close(monkeypatch):
    pool,*rest=setup(monkeypatch,lambda q:pytest.fail('unexpected HTTP'));made=rest[-2]
    async def one():
        await pool.__aenter__();started=asyncio.Event();release=asyncio.Event();original=made[0].aclose
        async def close():started.set();await release.wait();await original()
        monkeypatch.setattr(made[0],'aclose',close)
        owner=asyncio.create_task(pool.__aexit__(None,None,None));await started.wait();owner.cancel();await asyncio.sleep(0)
        assert not owner.done() and not made[0].is_closed
        with pytest.raises(RuntimeError):pool.retained_reader(REF)
        release.set()
        with pytest.raises(asyncio.CancelledError):await owner
        assert made[0].is_closed
    asyncio.run(one())

@pytest.mark.parametrize('fault',['workspace','account','scope','contract','revoked','expired'])
def test_resend_pool_foreign_or_inactive_send_binding_refuses_without_HTTP(monkeypatch,fault):
    pool,prepared,auth,status,pricing,made,_=setup(monkeypatch,lambda q:pytest.fail('wrong scope reached HTTP'))
    if fault=='workspace':auth=replace(auth,workspace_id=uuid.uuid4())
    elif fault=='account':auth=replace(auth,account_reference='foreign-account')
    elif fault=='scope':auth=replace(auth,sender_identity_id=uuid.uuid4())
    elif fault=='contract':auth=replace(auth,reviewed_contract_hash='c'*64)
    elif fault=='revoked':auth=replace(auth,selected=False)
    else:auth=replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    async def one():
        async with pool:
            with pytest.raises((ValueError,ApiError)):pool.bind(prepared=prepared,authorization=auth,pricing=pricing)
        assert made[0].is_closed
    asyncio.run(one())

def test_resend_pool_cold_GET_only_factory_needs_no_new_send_authority(monkeypatch):
    requests=[]
    def handler(request):requests.append(request);return httpx.Response(200,json=dict(id=REF,last_event='delivered'))
    pool,prepared,auth,status,pricing,made,_=setup(monkeypatch,handler)
    auth=replace(auth,selected=False,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    async def one():
        async with pool:
            with pytest.raises((ValueError,ApiError)):pool.bind(prepared=prepared,authorization=auth,pricing=pricing)
            reader=pool.retained_reader(REF);result=await reader.status()
            assert result.state=='delivered' and len(requests)==1 and requests[0].method=='GET' and str(requests[0].url)=='https://api.resend.com/emails/'+REF
            assert not hasattr(reader,'submit') and not hasattr(reader,'estimate')
        assert made[0].is_closed
    asyncio.run(one())

@pytest.mark.parametrize('values',[(0,0,1.0),(True,0,1.0),(2,3,1.0),(2,-1,1.0),(2,1,float('inf')),(2,1,float('nan')),(2,1,0.0),(2,1,True)])
def test_resend_pool_invalid_or_unbounded_limits_refuse_before_client_creation(values):
    wire=module()
    with pytest.raises(ValueError):wire.DeliveryHttpPoolLimits(max_connections=values[0],max_keepalive_connections=values[1],keepalive_expiry=values[2])

@pytest.mark.parametrize('fault',['expired','unreviewed','provider','empty-key','newline-key'])
def test_resend_pool_invalid_retained_scope_or_key_refuses_before_client_creation(monkeypatch,fault):
    wire=module();prepared,auth,status=inputs()
    if fault=='expired':status=replace(status,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    elif fault=='unreviewed':status=replace(status,reviewed=False)
    elif fault=='provider':status=replace(status,provider_name='unreviewed-vendor')
    key='' if fault=='empty-key' else 'private\nkey' if fault=='newline-key' else KEY
    monkeypatch.setattr(wire,'_new_delivery_http_client',lambda **options:pytest.fail('invalid binding created HTTP client'))
    with pytest.raises((ValueError,ApiError)):wire.ResendDeliveryHttpPool(authority=status,api_key=key,limits=wire.DeliveryHttpPoolLimits(4,2,5.0))

def test_resend_pool_one_original_POST_and_unknown_not_retried(monkeypatch):
    requests=[]
    def handler(q):requests.append(q);return httpx.Response(503,json={'id':REF})
    pool,prepared,auth,status,pricing,made,_=setup(monkeypatch,handler)
    async def one():
        async with pool:
            adapter=pool.bind(prepared=prepared,authorization=auth,pricing=pricing)
            assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None)
            assert await adapter.submit(prepared.intent)==SubmissionResult('unknown',None)
            assert len(requests)==1 and requests[0].method=='POST' and requests[0].headers['Idempotency-Key']==prepared.intent.key
        assert made[0].is_closed
    asyncio.run(one())
