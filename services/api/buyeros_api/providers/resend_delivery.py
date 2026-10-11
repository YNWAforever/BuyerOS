"""Unselected bounded Resend candidate; no account, price or sender activated.

Reviewed server-owned authorization/pricing and immutable prepared content are
required. The native runner owns the durable one-time permit; this adapter adds
one in-process attempt and never retries or follows redirects. Status uses only
an existing original canonical provider UUID, never an intent-key lookup.
"""
import asyncio,json,math,re,uuid
from dataclasses import dataclass
from types import MappingProxyType
import httpx
from .base import Money,SubmissionResult
from .delivery import DeliveryIntent,DeliveryStatusResult
from ..services.delivery_service import PreparedDelivery,delivery_payload_digest
from ..services.delivery_status import _require_status_authority
from ..services.delivery_submission import _require_submit_authority

ENDPOINT='https://api.resend.com/emails'
MAX_RESPONSE_BYTES=262144
MAX_REQUEST_BYTES=65536
_EVENTS={'sent':'accepted','delivered':'delivered','bounced':'bounced','complained':'complained','failed':'failed'}


@dataclass(frozen=True)
class DeliveryWirePricing:
    """Explicit reviewed upper estimate, never infer this from vendor JSON.

    This object alone does not prove real account pricing, cost, nonbillable
    status or verified billing receipts. No default pricing is supplied.
    """
    pricing_version:str
    reviewed_contract_hash:str
    estimate:Money

    def __post_init__(self):
        if (not isinstance(self.pricing_version,str) or re.fullmatch(r'[A-Za-z0-9:_/-]{1,64}',self.pricing_version) is None
                or self.pricing_version.startswith('legacy-') or not isinstance(self.reviewed_contract_hash,str)
                or re.fullmatch(r'[0-9a-f]{64}',self.reviewed_contract_hash) is None or type(self.estimate) is not Money):
            raise ValueError('explicit reviewed delivery wire pricing required')
        self.estimate.__post_init__()
        if self.estimate.amount<=0:raise ValueError('positive delivery wire estimate required')


def _ref(value):
    try:
        if not isinstance(value,str) or len(value)!=36:raise ValueError()
        parsed=uuid.UUID(value)
        if not parsed.int or str(parsed)!=value:raise ValueError()
        return value
    except (ValueError,AttributeError,TypeError):raise ValueError('original canonical delivery reference required') from None


def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('ambiguous delivery response')
        result[key]=value
    return result


def _constant(value):raise ValueError('nonfinite delivery response')


async def _read_http(http,api_key,method,url,*,headers,content=None):
    async with asyncio.timeout(10):
        async with http.stream(method,url,headers=headers,content=content,follow_redirects=False,timeout=10) as response:
            if response.status_code!=200 or response.headers.get('Content-Encoding','identity').lower()!='identity':
                raise ValueError('delivery response unresolved')
            raw=bytearray()
            async for chunk in response.aiter_bytes():
                if len(raw)+len(chunk)>MAX_RESPONSE_BYTES:raise ValueError('delivery response unresolved')
                raw.extend(chunk)
            if api_key.encode() in raw:raise ValueError('delivery response unresolved')
            result=json.loads(raw,object_pairs_hook=_pairs,parse_constant=_constant)
            if type(result) is not dict:raise ValueError('delivery response unresolved')
            return result


def _credential(api_key,http):
    if (not isinstance(api_key,str) or not 1<=len(api_key)<=4096 or any(ord(c)<33 or ord(c)>126 for c in api_key)
            or type(http) is not httpx.AsyncClient):raise ValueError('explicit private delivery HTTP client required')


class ResendDeliveryStatusReader:
    """Cold-start retained original GET only; no new admission or submit method.

    Its caller must resolve this original ref/account/scope from the retained
    tenant record, never accept authority or an arbitrary ref from HTTP JSON.
    """
    def __init__(self,*,authority,provider_ref,api_key,http):
        _require_status_authority(authority)
        if authority.provider_name!='resend':raise ValueError('original delivery provider required')
        self._provider_ref=_ref(provider_ref);_credential(api_key,http)
        self._authority=authority;self._key=api_key;self._http=http

    def __repr__(self):return 'ResendDeliveryStatusReader(bound=True)'

    async def status(self):
        _require_status_authority(self._authority)
        headers={'Authorization':'Bearer '+self._key,'Accept':'application/json','Accept-Encoding':'identity'}
        state='unknown'
        try:
            body=await _read_http(self._http,self._key,'GET',ENDPOINT+'/'+self._provider_ref,headers=headers)
            if _ref(body.get('id'))!=self._provider_ref or not isinstance(body.get('last_event'),str):
                raise ValueError('original delivery status unresolved')
            state=_EVENTS.get(body['last_event'],'unknown')
        except Exception:
            pass
        _require_status_authority(self._authority)
        # opened/clicked are not delivered. Suppressed needs its separate
        # reviewed reason/overlay; do not fabricate unsubscribe or no charge.
        return DeliveryStatusResult(state,self._provider_ref)


class ResendDeliveryAdapter:
    """An explicitly bound private adapter; no shared Service capability."""
    def __init__(self,*,prepared,authorization,reconciliation,pricing,api_key,http):
        _require_submit_authority(authorization);_require_status_authority(reconciliation)
        if (authorization.provider_name!='resend' or any(getattr(authorization,key)!=getattr(reconciliation,key) for key in
                ('workspace_id','provider_name','account_reference','scope_hash','reviewed_contract_hash'))
                or type(pricing) is not DeliveryWirePricing):
            raise ValueError('exact independent delivery wire authority required')
        pricing.__post_init__()
        if (pricing.pricing_version!=authorization.pricing_version or pricing.reviewed_contract_hash!=authorization.reviewed_contract_hash
                or pricing.estimate.currency!=authorization.currency or pricing.estimate.amount>authorization.upper_bound):
            raise ValueError('original reviewed delivery wire pricing required')
        if type(prepared) is not PreparedDelivery or type(prepared.intent) is not DeliveryIntent:
            raise ValueError('immutable server prepared delivery required')
        prepared.intent.__post_init__();intent=prepared.intent;payload=dict(prepared.payload)
        if (intent.workspace_id!=authorization.workspace_id or intent.sender_identity_id!=authorization.sender_identity_id
                or intent.recipient_ref not in authorization.recipient_refs or set(payload)!={'subject','body','recipient','sender'}
                or any(not isinstance(v,str) or not v or '\x00' in v for v in payload.values())
                or delivery_payload_digest(payload)!=intent.payload_digest):
            raise ValueError('original approved delivery payload required')
        for key in ('sender','recipient'):
            value=payload[key]
            if len(value)>254 or value.count('@')!=1 or any(ord(c)<=32 or ord(c)==127 for c in value):
                raise ValueError('single approved delivery address required')
        if any(ord(c)<32 or ord(c)==127 for c in payload['subject']):raise ValueError('bounded approved subject required')
        self._payload=json.dumps({'from':payload['sender'],'to':[payload['recipient']],'subject':payload['subject'],'text':payload['body']},ensure_ascii=False,separators=(',',':')).encode('utf-8')
        if len(self._payload)>MAX_REQUEST_BYTES:raise ValueError('bounded approved delivery payload required')
        _credential(api_key,http)
        self._prepared=PreparedDelivery(intent,MappingProxyType(payload));self._auth=authorization
        self._status=reconciliation;self._pricing=pricing;self._key=api_key;self._http=http
        self._attempted=False;self._result=SubmissionResult('unknown',None)

    def __repr__(self):return 'ResendDeliveryAdapter(bound=True)'

    def _original(self,intent):
        if type(intent) is not DeliveryIntent or intent!=self._prepared.intent:raise ValueError('original delivery intent required')
        intent.__post_init__()

    def estimate(self,intent):
        self._original(intent);_require_submit_authority(self._auth);self._pricing.__post_init__()
        return self._pricing.estimate

    def _headers(self):return {'Authorization':'Bearer '+self._key,'Accept':'application/json','Accept-Encoding':'identity'}

    async def submit(self,intent):
        self._original(intent)
        # A second in-process call never reaches HTTP, including cancellation
        # while the first request is unresolved. Durable fencing belongs to the
        # native runner/0050 permit and also prevents a new adapter from retrying.
        if self._attempted:return self._result
        self.estimate(intent)
        self._attempted=True
        headers=self._headers();headers.update({'Content-Type':'application/json','Idempotency-Key':intent.key})
        try:
            body=await _read_http(self._http,self._key,'POST',ENDPOINT,headers=headers,content=self._payload)
            if set(body)!={'id'}:raise ValueError('delivery response unresolved')
            self._result=SubmissionResult('accepted',_ref(body['id']))
        except Exception:
            # No status, response JSON or vendor exception proves no charge.
            # Return typed unknown without logging credential/message contents.
            pass
        return self._result

    async def status(self,provider_ref):
        # The separate reader also supports a new process with expired/revoked
        # original send authority, without creating a send-capable adapter.
        reader=ResendDeliveryStatusReader(authority=self._status,provider_ref=provider_ref,api_key=self._key,http=self._http)
        return await reader.status()


@dataclass(frozen=True)
class DeliveryHttpPoolLimits:
    """Explicit finite server-owned pool configuration; no inferred defaults."""
    max_connections:int
    max_keepalive_connections:int
    keepalive_expiry:float

    def __post_init__(self):
        if (type(self.max_connections) is not int or self.max_connections<=0
                or type(self.max_keepalive_connections) is not int
                or not 0<=self.max_keepalive_connections<=self.max_connections
                or type(self.keepalive_expiry) not in (int,float)
                or not math.isfinite(self.keepalive_expiry) or self.keepalive_expiry<=0):
            raise ValueError('explicit finite delivery HTTP pool limits required')


def _new_delivery_http_client(**options):
    return httpx.AsyncClient(**options)


class ResendDeliveryHttpPool:
    """One async-runtime owner, one retained account/scope, one HTTP client.

    Construction, context entry and binding perform no I/O. Only an explicitly
    selected server factory may use this unselected candidate. Never share this
    owner between event loops or close another service's borrowed client.
    """
    def __init__(self,*,authority,api_key,limits):
        _require_status_authority(authority)
        if authority.provider_name!='resend':raise ValueError('reviewed original Resend account required')
        if (not isinstance(api_key,str) or not 1<=len(api_key)<=4096
                or any(ord(c)<33 or ord(c)>126 for c in api_key)):
            raise ValueError('private bounded server delivery credential required')
        if type(limits) is not DeliveryHttpPoolLimits:raise ValueError('explicit delivery HTTP pool limits required')
        limits.__post_init__()
        self._authority=authority;self._key=api_key;self._limits=limits
        self._state='new';self._http=None;self._closing=None

    def __repr__(self):return 'ResendDeliveryHttpPool(owned=True)'

    async def __aenter__(self):
        if self._state!='new':raise RuntimeError('delivery HTTP pool cannot be reopened')
        _require_status_authority(self._authority);self._limits.__post_init__()
        self._state='closed'
        self._http=_new_delivery_http_client(timeout=10.0,follow_redirects=False,trust_env=False,
            limits=httpx.Limits(max_connections=self._limits.max_connections,
                max_keepalive_connections=self._limits.max_keepalive_connections,
                keepalive_expiry=self._limits.keepalive_expiry))
        self._state='open';return self

    def _client(self):
        if self._state!='open' or self._http is None or self._http.is_closed:
            raise RuntimeError('active owned delivery HTTP pool required')
        return self._http

    def bind(self,*,prepared,authorization,pricing):
        # This remains a local bind. The native 0050 runner still owns the
        # committed durable permit before any adapter POST is allowed.
        return ResendDeliveryAdapter(prepared=prepared,authorization=authorization,
            reconciliation=self._authority,pricing=pricing,api_key=self._key,http=self._client())

    def retained_reader(self,provider_ref):
        # No PreparedDelivery, new-send authority, estimate or POST capability.
        return ResendDeliveryStatusReader(authority=self._authority,provider_ref=provider_ref,
            api_key=self._key,http=self._client())

    async def __aexit__(self,exc_type,exc_value,traceback):
        self._state='closed'  # Refuse new binds before the first cleanup await.
        if self._http is None:return False
        if self._closing is None:self._closing=asyncio.create_task(self._http.aclose())
        cancelled=False
        while not self._closing.done():
            try:await asyncio.shield(self._closing)
            except asyncio.CancelledError:cancelled=True
        self._closing.result()
        if cancelled:raise asyncio.CancelledError()
        return False
