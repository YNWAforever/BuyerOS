"""C18 owned HTTP/quote-candidate boundaries; no vendor or contact-accuracy claim."""
import asyncio,importlib,json,uuid
from dataclasses import replace
from datetime import date,datetime,timezone
from decimal import Decimal
from pathlib import Path
import httpx,pytest
from buyeros_api.providers.base import Money,ProviderCapability,ProviderIntent

def module():
    assert (Path(__file__).resolve().parents[1]/'buyeros_api/providers/live_contact.py').is_file(),'C61-18 live contact adapter missing'
    return importlib.import_module('buyeros_api.providers.live_contact')

def capability():
    return ProviderCapability(provider='hunter',adapter_version='c61-contact-v1',service='contact',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'Procurement manager'}),auth_model='server-key',pricing_version='offline-contact-price-v1',max_liability=Money(Decimal('0.100000'),'USD'),idempotency='unsupported',status='unsupported',callback='unsupported',cancel='unsupported',retention='offline-only',verified_at=datetime.now(timezone.utc),source_urls=('https://hunter.io/api-documentation/v2',))

def request():
    m=module()
    return m.ContactRequest(key='c18-offline-intent',workspace_id=uuid.uuid4(),project_id=uuid.uuid4(),actor_id=uuid.uuid4(),buyer_id=uuid.uuid4(),company_id=uuid.uuid4(),buyer_version=1,quote_id=uuid.uuid4(),quote_hash='a'*64,pricing_version='offline-contact-price-v1',adapter_version='c61-contact-v1',domain='fictional-sensors.com',market='US',language='en',role='Procurement manager',contact_type='business_email',limit=10)

def response():
    today=date.today().isoformat()
    return {'data':{'domain':'fictional-sensors.com','organization':'Fictional Sensors','emails':[{'value':'buyer@fictional-sensors.com','type':'personal','confidence':98,'first_name':'Fixture','last_name':'Buyer','position':'Procurement manager','sources':[{'uri':'https://fictional-sensors.com/team','extracted_on':today,'last_seen_on':today,'still_on_page':True}],'verification':{'status':'valid','date':today}}]},'meta':{'results':1,'limit':10,'offset':0,'params':{'domain':'fictional-sensors.com'}}}

def test_contact_credential_header_and_bounded_one_request():
    m=module();calls=[]
    def transport(req):
        calls.append(req);assert req.method=='GET' and req.url.scheme=='https' and req.url.host=='api.hunter.io' and req.url.path=='/v2/domain-search'
        assert req.headers['X-API-KEY']=='offline-not-a-real-key' and 'api_key' not in req.url.params
        assert req.url.params['domain']=='fictional-sensors.com' and req.url.params['limit']=='10' and req.url.params['offset']=='0'
        assert req.url.params['job_titles']=='Procurement manager' and req.url.params['type']=='personal'
        return httpx.Response(200,json=response())
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport),follow_redirects=True) as http:
            result=await m.HunterDomainClient(api_key='offline-not-a-real-key',http=http).lookup(request())
            assert len(result['candidates'])==1 and result['candidates'][0]['verification_status']=='needs_review'
            assert result['candidates'][0]['canonical_company_id'] is None and result['candidates'][0]['canonical_person_id'] is None
            assert 'offline-not-a-real-key' not in repr(result) and result.get('observed_cost') is None
    asyncio.run(exercise());assert len(calls)==1

@pytest.mark.parametrize('kind',['timeout','redirect','forbidden','rate-limit','server','oversize','malformed','credential-echo'])
def test_contact_error_unknown_never_retry_or_guess_no_charge(kind):
    m=module();calls=[]
    def transport(req):
        calls.append(req)
        if kind=='timeout':raise httpx.ReadTimeout('offline accepted result unknown')
        if kind=='redirect':return httpx.Response(302,headers={'Location':'https://private.invalid/'})
        if kind in {'forbidden','rate-limit','server'}:return httpx.Response({'forbidden':403,'rate-limit':429,'server':503}[kind])
        if kind=='oversize':return httpx.Response(200,content=b'x'*262145)
        if kind=='malformed':return httpx.Response(200,content=b'invalid JSON')
        body=response();body['data']['organization']='offline-not-a-real-key';return httpx.Response(200,json=body)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport),follow_redirects=True) as http:
            with pytest.raises(m.ContactResponseUnknown):await m.HunterDomainClient(api_key='offline-not-a-real-key',http=http).lookup(request())
    asyncio.run(exercise());assert len(calls)==1

@pytest.mark.parametrize('domain',['https://fictional-sensors.com','127.0.0.1','169.254.169.254','localhost','internal.local','fictional-sensors.com/path','x@fictional-sensors.com','example.test'])
def test_contact_domain_is_scoped_public_dns_name_before_network(domain):
    m=module()
    with pytest.raises(ValueError):replace(request(),domain=domain)

@pytest.mark.parametrize('kind',['wrong-domain','wrong-email-domain','guessed','accept-all','no-sources','stale-source','private-source','wrong-role'])
def test_contact_wrong_company_quarantined(kind):
    m=module();value=request();body=response()
    if kind=='wrong-domain':body['data']['domain']='different-company.com'
    elif kind=='wrong-email-domain':body['data']['emails'][0]['value']='buyer@different-company.com'
    elif kind=='guessed':body['data']['emails'][0]['sources']=[];body['data']['pattern']='{first}.{last}'
    elif kind=='accept-all':body['data']['emails'][0]['verification']['status']='accept_all'
    elif kind=='no-sources':body['data']['emails'][0]['sources']=[]
    elif kind=='stale-source':body['data']['emails'][0]['sources'][0]['still_on_page']=False
    elif kind=='private-source':body['data']['emails'][0]['sources'][0]['uri']='https://169.254.169.254/credentials'
    else:body['data']['emails'][0]['position']='Different role'
    result=m.normalize_contact_response(body,value)
    assert result['verified_contacts']==[] and all(item['verification_status']!='verified' for item in result['candidates'])
    assert result['quarantined'] and all(item.get('canonical_company_id') is None and item.get('canonical_person_id') is None for item in result['candidates'])

def test_contact_quote_stale_price_blocks():
    m=module();value=request();cap=replace(capability(),pricing_version='new-unconfirmed-price')
    class Receipts:
        async def claim(self,intent):return {'ref':str(uuid.uuid4()),'request':value,'state':'prepared'},True
        async def finish(self,*args,**kwargs):pass
    class Client:
        async def lookup(self,*args):raise AssertionError('stale quote must never call provider')
    async def exercise():
        adapter=m.LiveContactAdapter(capability=cap,account_reference='offline-account',client=Client(),receipts=Receipts())
        result=await adapter.submit(ProviderIntent(value.key,'contact',value.market,value.language,value.role))
        assert result.state=='unknown'
    asyncio.run(exercise())


class SavedReceipt:
    def __init__(self,value,*,lose_ack=False):self.row={'ref':str(uuid.uuid4()),'request':value,'state':'prepared','digest':None,'response':None};self.lose_ack=lose_ack
    async def claim(self,intent):
        claimed=self.row['state']=='prepared'
        if claimed:self.row['state']='submitting'
        return dict(self.row),claimed
    async def finish(self,ref,*,state,response=None,digest=None):
        if self.row['state']=='submitting':self.row.update(state=state,response=response,digest=digest)
        if self.lose_ack and state=='received':raise TimeoutError('owned commit acknowledgement lost')
    async def get(self,ref):return dict(self.row) if ref==self.row['ref'] else None

@pytest.mark.parametrize('failure',['none','timeout','lost-ack','crash-after-claim'])
def test_contact_durable_response_restart_and_lost_ack_single_lookup(failure):
    m=module();value=request();receipts=SavedReceipt(value,lose_ack=failure=='lost-ack');calls=[]
    class Client:
        async def lookup(self,request):
            calls.append(request)
            if failure=='timeout':raise TimeoutError('vendor may have accepted')
            return m.normalize_contact_response(response(),request)
    async def exercise():
        intent=ProviderIntent(value.key,'contact',value.market,value.language,value.role)
        if failure=='crash-after-claim':assert (await receipts.claim(intent))[1]
        adapter=m.LiveContactAdapter(capability=capability(),account_reference='offline-account',client=Client(),receipts=receipts)
        expected='unknown' if failure in {'timeout','crash-after-claim'} else 'accepted'
        assert (await adapter.submit(intent)).state==expected
        assert (await adapter.submit(intent)).state==expected
        reopened=m.LiveContactAdapter(capability=capability(),account_reference='offline-account',client=None,receipts=receipts)
        assert (await reopened.status(receipts.row['ref'])).state==('unknown' if expected=='unknown' else 'succeeded')
        assert receipts.row['response'] is None or receipts.row['response']['verified_contacts']==[]
    asyncio.run(exercise());assert len(calls)==(0 if failure=='crash-after-claim' else 1)

def codec():
    m=importlib.import_module('buyeros_api.providers.live_contact')
    cls=getattr(m,'ContactReceiptCipher',None);assert callable(cls),'C61-18 private contact encryption owner missing'
    return cls(keys={'offline-k1':b'a'*32},active_key_id='offline-k1')

def test_contact_private_receipt_encrypts_bounded_payload_without_plaintext():
    from datetime import timedelta
    value=request();ref=uuid.uuid4();expires=datetime.now(timezone.utc)+timedelta(days=1);cipher=codec()
    payload=module().normalize_contact_response(response(),value)
    kwargs={'workspace_id':value.workspace_id,'ref':ref,'request_digest':value.digest,'expires_at':expires}
    first=cipher.seal(payload,**kwargs);second=cipher.seal(payload,**kwargs)
    assert isinstance(first,bytes) and first!=second and b'buyer@fictional-sensors.com' not in first and b'Fixture' not in first
    assert cipher.open(first,**kwargs)==payload

@pytest.mark.parametrize('mutation',['tenant','receipt','digest','expiry','ciphertext','key'])
def test_contact_private_receipt_denies_scope_tamper_expiry_or_missing_key(mutation):
    from datetime import timedelta
    value=request();ref=uuid.uuid4();expires=datetime.now(timezone.utc)+timedelta(days=1);cipher=codec()
    kwargs={'workspace_id':value.workspace_id,'ref':ref,'request_digest':value.digest,'expires_at':expires}
    blob=cipher.seal(module().normalize_contact_response(response(),value),**kwargs)
    if mutation=='tenant':kwargs['workspace_id']=uuid.uuid4()
    elif mutation=='receipt':kwargs['ref']=uuid.uuid4()
    elif mutation=='digest':kwargs['request_digest']='f'*64
    elif mutation=='expiry':kwargs['expires_at']=datetime.now(timezone.utc)-timedelta(seconds=1)
    elif mutation=='ciphertext':blob=blob[:-1]+bytes([blob[-1]^1])
    else:cipher=type(cipher)(keys={'offline-k2':b'b'*32},active_key_id='offline-k2')
    with pytest.raises(ValueError):cipher.open(blob,**kwargs)


@pytest.mark.parametrize('mutation',['verified-flag','company-ref','person-ref','private-source'])
def test_contact_client_port_cannot_promote_supplier_hints_to_verified(mutation):
    m=module();value=request();receipts=SavedReceipt(value);calls=[]
    body=m.normalize_contact_response(response(),value)
    if mutation=='verified-flag':body['candidates'][0]['verification_status']='verified'
    elif mutation=='company-ref':body['candidates'][0]['canonical_company_id']=str(value.company_id)
    elif mutation=='person-ref':body['candidates'][0]['canonical_person_id']=str(uuid.uuid4())
    else:body['candidates'][0]['sources'][0]['url']='https://169.254.169.254/private'
    class Client:
        async def lookup(self,*args):calls.append(args);return body
    async def exercise():
        adapter=m.LiveContactAdapter(capability=capability(),account_reference='offline-account',client=Client(),receipts=receipts)
        intent=ProviderIntent(value.key,'contact',value.market,value.language,value.role)
        assert (await adapter.submit(intent)).state=='unknown'
        assert (await adapter.submit(intent)).state=='unknown'
        assert receipts.row['state']=='unknown' and receipts.row['response'] is None
    asyncio.run(exercise());assert len(calls)==1
