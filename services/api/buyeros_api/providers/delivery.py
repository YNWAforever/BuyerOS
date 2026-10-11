"""Independent delivery protocol. No provider, sender or production route is activated."""
from __future__ import annotations

import base64
import hashlib
import hmac
import math
import re
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass,field
from typing import Literal,Protocol
from decimal import Decimal
from .base import Money,SubmissionResult

DeliveryState=Literal['prepared','submitting','unknown','accepted','delivered','bounced','complained','unsubscribed','failed','rejected']
_STATES=frozenset(DeliveryState.__args__)
_OBSERVED_STATES=_STATES-frozenset({'prepared','submitting'})
_NEXT={
    'prepared':frozenset({'submitting','rejected'}),
    'submitting':frozenset({'unknown','accepted','delivered','bounced','complained','failed','rejected'}),
    'unknown':frozenset({'accepted','delivered','bounced','complained','unsubscribed','failed'}),
    'accepted':frozenset({'delivered','bounced','complained','unsubscribed','failed'}),
    'delivered':frozenset({'bounced','complained','unsubscribed'}),
    'bounced':frozenset({'complained','unsubscribed'}),
    'complained':frozenset({'unsubscribed'}),
    'unsubscribed':frozenset(), 'failed':frozenset(), 'rejected':frozenset(),
}

@dataclass(frozen=True)
class DeliveryIntent:
    key:str
    workspace_id:uuid.UUID
    draft_revision_id:uuid.UUID
    recipient_ref:uuid.UUID
    sender_identity_id:uuid.UUID
    approval_id:uuid.UUID
    payload_digest:str

    def __post_init__(self):
        if not isinstance(self.key,str) or re.fullmatch(r'[A-Za-z0-9:_/-]{1,128}',self.key) is None:
            raise ValueError('bounded opaque delivery key required')
        for value in (self.workspace_id,self.draft_revision_id,self.recipient_ref,self.sender_identity_id,self.approval_id):
            if not isinstance(value,uuid.UUID) or value.int==0:raise ValueError('exact delivery UUID required')
        if not isinstance(self.payload_digest,str) or re.fullmatch(r'[0-9a-f]{64}',self.payload_digest) is None:
            raise ValueError('exact delivery payload digest required')

@dataclass(frozen=True)
class DeliveryStatusResult:
    state:DeliveryState
    provider_ref:str
    event_id:str|None=None

    def __post_init__(self):
        if not isinstance(self.state,str) or self.state not in _OBSERVED_STATES:
            raise ValueError('invalid observed delivery status')
        if not isinstance(self.provider_ref,str) or re.fullmatch(r'[A-Za-z0-9:_/-]{1,200}',self.provider_ref) is None:
            raise ValueError('invalid observed delivery status')
        if self.event_id is not None and (not isinstance(self.event_id,str) or re.fullmatch(r'[A-Za-z0-9_-]{1,200}',self.event_id) is None):
            raise ValueError('invalid observed delivery status')


def validate_delivery_status(result:DeliveryStatusResult,*,provider_ref:str)->DeliveryStatusResult:
    """Bind a typed observation to its original query reference before transition.

    The durable caller also checks the original provider/account authority and
    tenant context. This pure boundary retains the result without state updates.
    """
    if type(result) is not DeliveryStatusResult:
        raise ValueError('invalid observed delivery status')
    result.__post_init__()
    if not isinstance(provider_ref,str) or re.fullmatch(r'[A-Za-z0-9:_/-]{1,200}',provider_ref) is None or result.provider_ref!=provider_ref:
        raise ValueError('invalid observed delivery status')
    return result


def validate_delivery_submission(result:SubmissionResult)->SubmissionResult:
    """Delivery-only typed response boundary; metadata never proves a charge.

    Generic search/model/contact responses keep their existing contracts. Only
    accepted with a bounded opaque reference can bind delivery acceptance.
    Unknown may lack a reference; rejection cannot establish no-charge proof.
    """
    if type(result) is not SubmissionResult or not isinstance(result.state,str) or result.state not in {'accepted','unknown','rejected'}:
        raise ValueError('invalid delivery submission result')
    ref=result.provider_ref
    if (ref is not None and (not isinstance(ref,str) or re.fullmatch(r'[A-Za-z0-9:_/-]{1,200}',ref) is None)
        or result.state=='accepted' and ref is None or result.state=='rejected' and ref is not None):
        raise ValueError('invalid delivery submission result')
    usage=result.observed_usage
    if usage is not None and (not isinstance(usage,Decimal) or not usage.is_finite()
                             or usage<0 or usage>=Decimal('100000000000000') or usage.as_tuple().exponent < -6):
        raise ValueError('invalid delivery submission result')
    digest=result.redacted_digest
    if digest is not None and (not isinstance(digest,str) or re.fullmatch(r'[0-9a-f]{64}',digest) is None):
        raise ValueError('invalid delivery submission result')
    return result


class DeliveryAdapter(Protocol):
    def estimate(self,intent:DeliveryIntent)->Money:...
    async def submit(self,intent:DeliveryIntent)->SubmissionResult:...
    async def status(self,provider_ref:str)->DeliveryStatusResult:...

def may_submit_delivery(state:DeliveryState,*,approval_current:bool,policy_current:bool,suppressed:bool)->bool:
    if state not in _STATES:raise ValueError('invalid delivery state')
    return state=='prepared' and approval_current is True and policy_current is True and suppressed is False

def delivery_transition(current:DeliveryState,event:DeliveryState)->DeliveryState:
    if current not in _STATES or event not in _STATES:raise ValueError('invalid delivery state')
    return event if event in _NEXT[current] else current

@dataclass(frozen=True)
class VerifiedDeliveryWebhook:
    event_id:str
    body_digest:str
    raw_body:bytes=field(repr=False)

def verify_delivery_webhook(raw_body:bytes,headers:Mapping[str,str],*,secret:str,now:float|None=None)->VerifiedDeliveryWebhook:
    """Svix v1 exact-byte HMAC with a fixed five-minute attempt timestamp window.

    This authenticates bytes only. Account/ref routing, event deduplication and
    suppression persistence still require the independent durable service.
    """
    try:
        if not isinstance(raw_body,bytes) or len(raw_body)>65536:raise ValueError()
        event_id=headers.get('svix-id','');stamp=headers.get('svix-timestamp','');signatures=headers.get('svix-signature','')
        if (not isinstance(event_id,str) or re.fullmatch(r'[A-Za-z0-9_-]{1,200}',event_id) is None
            or not isinstance(stamp,str) or re.fullmatch(r'[0-9]{1,12}',stamp) is None or str(int(stamp))!=stamp
            or not isinstance(signatures,str) or not 1<=len(signatures)<=2048):raise ValueError()
        observed=time.time() if now is None else now
        if type(observed) not in (int,float) or not math.isfinite(observed) or abs(observed-int(stamp))>300:raise ValueError()
        if not isinstance(secret,str) or not secret.startswith('whsec_') or len(secret)>256:raise ValueError()
        key=base64.b64decode(secret[6:],validate=True)
        if not 16<=len(key)<=128:raise ValueError()
        expected=base64.b64encode(hmac.digest(key,event_id.encode('ascii')+b'.'+stamp.encode('ascii')+b'.'+raw_body,'sha256')).decode('ascii')
        pieces=signatures.split(' ')
        if len(pieces)>16:raise ValueError()
        if not any(piece.startswith('v1,') and len(piece)==47 and hmac.compare_digest(expected,piece[3:]) for piece in pieces):raise ValueError()
        return VerifiedDeliveryWebhook(event_id,hashlib.sha256(raw_body).hexdigest(),raw_body)
    except (ValueError,TypeError,AttributeError,UnicodeError):
        raise ValueError('invalid delivery webhook') from None
