"""Unselected bounded Hunter candidate; deliverability is not company/person proof."""
from __future__ import annotations
import asyncio,hashlib,ipaddress,json,re,uuid
from dataclasses import dataclass,asdict
from datetime import date,datetime,timezone,timedelta
import httpx
from .base import ProviderIntent,ProviderCapability,Money,SubmissionResult,StatusResult
from .live_search import source_candidate

ENDPOINT='https://api.hunter.io/v2/domain-search'
MAX_RESPONSE_BYTES=262144

class ContactResponseUnknown(Exception):
    """Acceptance, response and charge remain unresolved; never retry/release."""

def canonical_json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()

def _domain(value):
    if not isinstance(value,str) or value!=value.strip() or value!=value.lower() or len(value)>253:raise ValueError('canonical public company DNS name required')
    try:ipaddress.ip_address(value)
    except ValueError:pass
    else:raise ValueError('IP domain forbidden')
    if (not re.fullmatch(r'(?=.{3,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',value) or
        value.endswith(('.local','.localhost','.internal','.invalid','.test','.example'))):raise ValueError('public company DNS name required')
    return value

@dataclass(frozen=True)
class ContactRequest:
    key:str
    workspace_id:uuid.UUID
    project_id:uuid.UUID
    actor_id:uuid.UUID
    buyer_id:uuid.UUID
    company_id:uuid.UUID
    buyer_version:int
    quote_id:uuid.UUID
    quote_hash:str
    pricing_version:str
    adapter_version:str
    domain:str
    market:str
    language:str
    role:str
    contact_type:str
    limit:int

    def __post_init__(self):
        for key in ['workspace_id','project_id','actor_id','buyer_id','company_id','quote_id']:
            if not isinstance(getattr(self,key),uuid.UUID):raise ValueError('canonical server-resolved contact references required')
        if not isinstance(self.key,str) or not 1<=len(self.key)<=128 or self.key.strip()!=self.key or not re.fullmatch(r'[0-9a-f]{64}',self.quote_hash):raise ValueError('stable confirmed quote digest required')
        if type(self.buyer_version) is not int or self.buyer_version<1 or type(self.limit) is not int or not 1<=self.limit<=10:raise ValueError('bounded frozen buyer/count required')
        for key in ['pricing_version','adapter_version','role','language']:
            value=getattr(self,key)
            if not isinstance(value,str) or not 1<=len(value)<=128 or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('bounded frozen quote scope required')
        if self.contact_type!='business_email' or not re.fullmatch('[A-Z]{2}',self.market):raise ValueError('supported frozen contact scope required')
        _domain(self.domain)

    @property
    def digest(self):return hashlib.sha256(canonical_json(asdict(self))).hexdigest()

def _text(value,limit,*,optional=False):
    if optional and value is None:return None
    if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('bounded contact metadata required')
    return value

def normalize_contact_response(body,request:ContactRequest):
    if not isinstance(body,dict) or body.get('errors') or not isinstance(body.get('data'),dict) or len(canonical_json(body))>MAX_RESPONSE_BYTES:raise ValueError('bounded typed vendor contact response required')
    data=body['data'];items=data.get('emails')
    if not isinstance(items,list) or len(items)>request.limit:raise ValueError('bounded contact count required')
    result={'candidates':[],'quarantined':[],'verified_contacts':[],'domain':request.domain}
    if data.get('domain') is None and not items:return result # supplier200 empty is not proof of no charge
    returned_domain=_domain(data.get('domain'))
    for ordinal,item in enumerate(items):
        if not isinstance(item,dict):raise ValueError('typed contact metadata required')
        email=_text(item.get('value'),254);reasons=[]
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9.-]{3,253}",email):reasons.append('invalid_email')
        email_domain=email.rsplit('@',1)[-1].lower()
        if returned_domain!=request.domain or email_domain!=request.domain:reasons.append('wrong_company_domain')
        if item.get('type') not in {'personal','generic'} or type(item.get('confidence')) is not int or not 0<=item['confidence']<=100:raise ValueError('typed contact probability/type required')
        names={key:_text(item.get(key),160,optional=True) for key in ['first_name','last_name','position']}
        if item.get('type')!='personal' or not names['first_name'] or not names['last_name']:reasons.append('person_identity_unproven')
        if (names['position'] or '').casefold()!=request.role.casefold():reasons.append('requested_role_unproven')
        verification=item.get('verification') or {};status=verification.get('status') if isinstance(verification,dict) else None
        if status!='valid':reasons.append('deliverability_unverified')
        try:
            verified_on=date.fromisoformat(verification['date'])
            if not date.today()-timedelta(days=30)<=verified_on<=date.today():reasons.append('verification_stale')
        except (ValueError,KeyError,TypeError):reasons.append('verification_undated')
        sources=item.get('sources');normalized=[]
        if not isinstance(sources,list) or not 1<=len(sources)<=20:reasons.append('no_current_source')
        else:
            for source in sources:
                try:
                    if not isinstance(source,dict) or source.get('still_on_page') is not True:raise ValueError('source no longer current')
                    first=date.fromisoformat(source['extracted_on']);last=date.fromisoformat(source['last_seen_on'])
                    if not first<=last<=date.today() or last<date.today()-timedelta(days=30):raise ValueError('source stale')
                    safe=source_candidate({'url':source['uri'],'title':'Contact association metadata, unverified','snippet':''})
                    normalized.append({'url':safe['source_url'],'extracted_on':first.isoformat(),'last_seen_on':last.isoformat()})
                except (ValueError,KeyError,TypeError):reasons.append('source_unverified')
        candidate={'email':email,'type':item['type'],'confidence':item['confidence'],**names,'sources':normalized,
            'deliverability_status':status if status in {'valid','accept_all','unknown'} else 'unknown',
            'verification_status':'quarantined' if reasons else 'needs_review','canonical_company_id':None,'canonical_person_id':None,
            'reason_codes':sorted(set(reasons)) if reasons else ['company_person_evidence_required']}
        result['candidates'].append(candidate)
        if reasons:result['quarantined'].append({'index':ordinal,'reason_codes':candidate['reason_codes']})
    return result

def validate_contact_response(body,request):
    """Supplier/client metadata never supplies canonical identity or verified truth."""
    if not isinstance(body,dict) or set(body)!={'candidates','quarantined','verified_contacts','domain'} or body['verified_contacts']!=[] or body['domain']!=request.domain or len(canonical_json(body))>MAX_RESPONSE_BYTES:raise ValueError('bounded quarantinable contact result required')
    candidates=body['candidates'];quarantined=body['quarantined']
    if not isinstance(candidates,list) or len(candidates)>request.limit or not isinstance(quarantined,list) or len(quarantined)>len(candidates):raise ValueError('bounded contact candidates required')
    allowed={'invalid_email','wrong_company_domain','person_identity_unproven','requested_role_unproven','deliverability_unverified','verification_stale','verification_undated','no_current_source','source_unverified','company_person_evidence_required'}
    for item in candidates:
        if not isinstance(item,dict) or item.get('verification_status') not in {'needs_review','quarantined'} or item.get('canonical_company_id') is not None or item.get('canonical_person_id') is not None:raise ValueError('server company/person proof is separate from vendor contact metadata')
        _text(item.get('email'),254)
        if item.get('type') not in {'personal','generic'} or type(item.get('confidence')) is not int or not 0<=item['confidence']<=100 or item.get('deliverability_status') not in {'valid','accept_all','unknown'}:raise ValueError('typed vendor contact metadata required')
        for key in ['first_name','last_name','position']:_text(item.get(key),160,optional=True)
        reasons=item.get('reason_codes');sources=item.get('sources')
        if not isinstance(reasons,list) or not 1<=len(reasons)<=len(allowed) or any(not isinstance(x,str) or x not in allowed for x in reasons) or not isinstance(sources,list) or len(sources)>20:raise ValueError('bounded contact provenance reasons required')
        if item['verification_status']=='needs_review' and reasons!=['company_person_evidence_required']:raise ValueError('unverified contact requires explicit review')
        for source in sources:
            if not isinstance(source,dict):raise ValueError('typed contact source metadata required')
            source_candidate({'url':source['url'],'title':'Unverified contact association metadata','snippet':''})
            first=date.fromisoformat(source['extracted_on']);last=date.fromisoformat(source['last_seen_on'])
            if not first<=last<=date.today() or last<date.today()-timedelta(days=30):raise ValueError('current contact source metadata required')
    for item in quarantined:
        if not isinstance(item,dict) or type(item.get('index')) is not int or not 0<=item['index']<len(candidates) or candidates[item['index']]['verification_status']!='quarantined' or item.get('reason_codes')!=candidates[item['index']]['reason_codes']:raise ValueError('per-candidate quarantine reason required')
    return body

class HunterDomainClient:
    def __init__(self,*,api_key,http):
        if not isinstance(api_key,str) or not 1<=len(api_key)<=4096 or any(ord(c)<33 or ord(c)>126 for c in api_key):raise ValueError('server-only contact credential required')
        self._api_key,self.http=api_key,http

    async def lookup(self,request:ContactRequest):
        if not isinstance(request,ContactRequest):raise ValueError('frozen scoped contact quote required')
        try:
            async with asyncio.timeout(10):
                async with self.http.stream('GET',ENDPOINT,params={'domain':request.domain,'limit':request.limit,'offset':0,'type':'personal','job_titles':request.role},headers={'X-API-KEY':self._api_key,'Accept':'application/json','Accept-Encoding':'identity'},follow_redirects=False,timeout=10) as response:
                    if response.status_code!=200 or response.headers.get('Content-Encoding','identity').lower()!='identity':raise ContactResponseUnknown('bounded vendor response unavailable')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw)+len(chunk)>MAX_RESPONSE_BYTES:raise ContactResponseUnknown('vendor response too large')
                        raw.extend(chunk)
            if self._api_key.encode() in raw:raise ContactResponseUnknown('credential echo blocked')
            return normalize_contact_response(json.loads(raw),request)
        except (httpx.HTTPError,TimeoutError,ValueError,UnicodeError,KeyError,TypeError) as error:
            raise ContactResponseUnknown('vendor contact acceptance/result/charge unknown') from error

class LiveContactAdapter:
    """Local saved response only; official billing/current encrypted proof is separate."""
    # status reads only the saved private DB receipt; no supplier or billing IO.
    status_nonbillable = True
    def __init__(self,*,capability,account_reference,client,receipts):
        if capability.provider!='hunter' or capability.service!='contact' or not isinstance(account_reference,str) or not 1<=len(account_reference)<=128:raise ValueError('code-owned contact contract/account required')
        self.capability,self.account_reference,self.client,self.receipts=capability,account_reference,client,receipts

    def estimate(self,intent):
        if intent.service!='contact' or intent.market not in self.capability.markets or intent.language not in self.capability.languages or intent.role not in self.capability.roles or self.capability.max_liability is None:raise ValueError('bounded contact contract required')
        return self.capability.max_liability

    async def submit(self,intent):
        self.estimate(intent);saved,claimed=await self.receipts.claim(intent);request=saved['request'];ref=saved['ref']
        if (not isinstance(request,ContactRequest) or request.pricing_version!=self.capability.pricing_version or request.adapter_version!=self.capability.adapter_version or
            (request.key,request.market,request.language,request.role)!=(intent.key,intent.market,intent.language,intent.role)):
            if claimed:await self.receipts.finish(ref,state='unknown')
            return SubmissionResult('unknown',ref)
        if not claimed:return SubmissionResult('accepted' if saved['state']=='received' else 'unknown',ref)
        try:
            response=await self.client.lookup(request)
            validate_contact_response(response,request)
            digest=hashlib.sha256(canonical_json(response)).hexdigest();await self.receipts.finish(ref,state='received',response=response,digest=digest)
            final=await self.receipts.get(ref)
            if final is None or final['state']!='received' or final['digest']!=digest:raise ContactResponseUnknown('durable contact receipt unavailable')
            return SubmissionResult('accepted',ref,redacted_digest='sha256:'+digest)
        except Exception:
            try:
                final=await self.receipts.get(ref)
                if final is not None and final['state']=='received':return SubmissionResult('accepted',ref,redacted_digest='sha256:'+final['digest'])
                await self.receipts.finish(ref,state='unknown')
            except Exception:pass
            return SubmissionResult('unknown',ref)

    async def status(self,provider_ref):
        saved=await self.receipts.get(provider_ref)
        if saved is None or saved['state']!='received':return StatusResult('unknown',provider_ref)
        return StatusResult('succeeded',provider_ref,redacted_digest='sha256:'+saved['digest'])


class ContactReceiptCipher:
    """Explicit server-owned AES-GCM keys; immutable tenant/intent/purpose/TTL AAD.

    Encryption protects supplier PII at rest. It establishes neither authenticity
    nor company/person accuracy, and is never a reason to release an unknown hold.
    Keys are supplied by an approved runtime owner; no environment/key guessing.
    """
    def __init__(self,*,keys,active_key_id):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        if (not isinstance(keys,dict) or not 1<=len(keys)<=8 or active_key_id not in keys or
            any(not isinstance(k,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',k) or not isinstance(v,bytes) or len(v)!=32 for k,v in keys.items())):raise ValueError('explicit bounded server encryption keyring required')
        self._keys={k:AESGCM(v) for k,v in keys.items()};self.active_key_id=active_key_id

    def _aad(self,workspace_id,ref,request_digest,expires_at):
        if (not isinstance(workspace_id,uuid.UUID) or not isinstance(ref,uuid.UUID) or
            not isinstance(request_digest,str) or not re.fullmatch(r'[0-9a-f]{64}',request_digest) or
            not isinstance(expires_at,datetime) or expires_at.tzinfo is None):raise ValueError('immutable private receipt scope required')
        return canonical_json({'schema':'c61-contact-private.v1','purpose':'contact_research','workspace_id':workspace_id,'ref':ref,'request_digest':request_digest,'expires_at':expires_at.astimezone(timezone.utc).isoformat()})

    def seal(self,payload,*,workspace_id,ref,request_digest,expires_at):
        import secrets
        raw=canonical_json(payload);now=datetime.now(timezone.utc)
        aad=self._aad(workspace_id,ref,request_digest,expires_at)
        if not isinstance(payload,dict) or len(raw)>MAX_RESPONSE_BYTES or not now<expires_at<=now+timedelta(days=30):raise ValueError('bounded current private contact retention required')
        nonce=secrets.token_bytes(12)
        return b'C61C1:'+self.active_key_id.encode()+b':'+nonce+self._keys[self.active_key_id].encrypt(nonce,raw,aad)

    def open(self,blob,*,workspace_id,ref,request_digest,expires_at):
        from cryptography.exceptions import InvalidTag
        aad=self._aad(workspace_id,ref,request_digest,expires_at)
        try:
            if not isinstance(blob,bytes) or not 47<=len(blob)<=MAX_RESPONSE_BYTES+128 or expires_at<=datetime.now(timezone.utc):raise ValueError('private receipt unavailable or expired')
            prefix,key_id,raw=blob.split(b':',2)
            if prefix!=b'C61C1' or len(raw)<28:raise ValueError('private receipt unavailable')
            cipher=self._keys[key_id.decode('ascii')];plain=cipher.decrypt(raw[:12],raw[12:],aad)
            result=json.loads(plain)
            if len(plain)>MAX_RESPONSE_BYTES or not isinstance(result,dict):raise ValueError('bounded private receipt required')
            return result
        except (ValueError,KeyError,UnicodeError,InvalidTag) as error:raise ValueError('private contact receipt unavailable') from error


def __getattr__(name):
    if name=='PostgresContactReceipts':
        from .contact_receipts import PostgresContactReceipts
        return PostgresContactReceipts
    raise AttributeError(name)
