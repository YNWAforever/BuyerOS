"""Resolve a precise current approval for delivery; preparation never sends or admits."""
import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass,field
from types import MappingProxyType
from ..api.errors import ApiError
from ..providers.delivery import DeliveryIntent
from .approval_service import _locked_draft
from .export_service import _approved_draft_content

_DELIVERY_ROLES=frozenset({'reviewer','workspace_admin'})

@dataclass(frozen=True)
class PreparedDelivery:
    intent:DeliveryIntent
    payload:Mapping[str,str]=field(repr=False)

def delivery_payload_digest(payload:Mapping[str,str])->str:
    return hashlib.sha256(json.dumps(dict(payload),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()

async def prepare_delivery_intent(session,*,workspace_id:uuid.UUID,actor_id:uuid.UUID,draft_id:uuid.UUID,draft_revision_id:uuid.UUID,recipient_ref:uuid.UUID,sender_identity_id:uuid.UUID,approval_id:uuid.UUID,key:str)->PreparedDelivery:
    # Keep current membership/policy locks and reviewer authorization before
    # resolving the same canonical approval checks used by approved export.
    await _locked_draft(session,workspace_id=workspace_id,draft_id=draft_id,actor_id=actor_id,roles=_DELIVERY_ROLES)
    project,draft,revision,approval,_=await _approved_draft_content(session,workspace_id=workspace_id,draft_id=draft_id,actor_id=actor_id,revision_id=draft_revision_id,approval_id=approval_id)
    context=approval.context_snapshot
    if (recipient_ref!=approval.recipient_contact_id or sender_identity_id!=uuid.UUID(context['sender']['id'])):
        raise ApiError(412,'STALE_REVISION','exact delivery recipient and sender are required')
    payload=MappingProxyType(dict(subject=revision.content['subject'],body=revision.content['body'],recipient=context['recipient']['value'],sender=context['sender']['business_email']))
    intent=DeliveryIntent(key=key,workspace_id=workspace_id,draft_revision_id=revision.id,recipient_ref=recipient_ref,sender_identity_id=sender_identity_id,approval_id=approval.id,payload_digest=delivery_payload_digest(payload))
    return PreparedDelivery(intent,payload)
