"""Independent delivery budget boundary; unused by public delivery/worker routes.

This reserves only the exact original operation in its caller's transaction.
The future producer must persist its reviewed scope with the message/liability
and registered paid outbox atomically before any dispatch. No provider I/O here.
"""
import hashlib,json,re,uuid
from dataclasses import dataclass
from datetime import datetime,timezone
from decimal import Decimal
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.budget import BudgetReservation
from ..db.contact import ProviderOperation
from ..db.drafts import OutreachDraft
from .budget_service import lock_budget_workspace,reserve_operation
from .delivery_service import prepare_delivery_intent

@dataclass(frozen=True)
class DeliveryBudgetAuthorization:
    """Server-owned selected/reviewed scope. Never accept this object from HTTP.

    Default selection is absent. Synthetic test scopes are supplied only by an
    owned fixture; no production provider/account/sender selection is installed.
    """
    workspace_id:uuid.UUID
    project_id:uuid.UUID
    sender_identity_id:uuid.UUID
    recipient_refs:tuple[uuid.UUID,...]
    provider_name:str
    account_reference:str
    pricing_version:str
    upper_bound:Decimal
    currency:str
    reviewed_contract_hash:str
    selected:bool
    reviewed:bool
    sender_verified:bool
    valid_until:datetime

    def __post_init__(self):
        for value in (self.workspace_id,self.project_id,self.sender_identity_id):
            if not isinstance(value,uuid.UUID) or value.int==0:raise ValueError('exact delivery scope UUID required')
        if (not isinstance(self.recipient_refs,tuple) or not 1<=len(self.recipient_refs)<=10000
            or any(not isinstance(value,uuid.UUID) or value.int==0 for value in self.recipient_refs)
            or len(set(self.recipient_refs))!=len(self.recipient_refs)):
            raise ValueError('immutable exact delivery recipient scope required')
        for value,pattern in [(self.provider_name,r'[A-Za-z0-9_-]{1,64}'),(self.account_reference,r'[A-Za-z0-9:_/-]{1,128}'),(self.pricing_version,r'[A-Za-z0-9:_/-]{1,64}')]:
            if not isinstance(value,str) or re.fullmatch(pattern,value) is None:raise ValueError('bounded original delivery provider/account/tariff required')
        if self.pricing_version.startswith('legacy-'):raise ValueError('verified delivery pricing required')
        if (not isinstance(self.upper_bound,Decimal) or not self.upper_bound.is_finite()
            or not Decimal('0')<self.upper_bound<Decimal('100000000000000')
            or self.upper_bound.as_tuple().exponent < -6 or self.currency!='USD'):
            raise ValueError('bounded exact positive USD delivery liability required')
        if not isinstance(self.reviewed_contract_hash,str) or re.fullmatch(r'[0-9a-f]{64}',self.reviewed_contract_hash) is None:
            raise ValueError('exact reviewed delivery contract hash required')
        if any(type(value) is not bool for value in (self.selected,self.reviewed,self.sender_verified)):
            raise ValueError('explicit delivery authority flags required')
        if not isinstance(self.valid_until,datetime) or self.valid_until.utcoffset() is None:
            raise ValueError('bounded aware delivery authority expiry required')

    @property
    def scope_json(self)->str:
        metadata={key:value for key,value in vars(self).items()}
        metadata['recipient_refs']=sorted(str(value) for value in self.recipient_refs)
        metadata['upper_bound']=format(self.upper_bound.quantize(Decimal('0.000001')),'.6f')
        metadata['valid_until']=self.valid_until.astimezone(timezone.utc).isoformat()
        return json.dumps(metadata,sort_keys=True,separators=(',',':'),default=str)

    @property
    def scope_hash(self)->str:
        return hashlib.sha256(self.scope_json.encode('utf-8')).hexdigest()

async def reserve_delivery_operation(session,*,operation_id:uuid.UUID,authorization:DeliveryBudgetAuthorization|None=None,**bindings)->uuid.UUID:
    # A typed, explicitly reviewed current scope is necessary before budget work.
    if (not isinstance(authorization,DeliveryBudgetAuthorization) or authorization.selected is not True
        or authorization.reviewed is not True or authorization.sender_verified is not True
        or authorization.valid_until<=datetime.now(timezone.utc)):
        raise ApiError(503,'PROVIDER_UNAVAILABLE','selected reviewed delivery budget authority is unavailable')
    # Refusal rolls back new holds even if the outer caller catches it and commits.
    async with session.begin_nested():
        prepared=await prepare_delivery_intent(session,**bindings)
        intent=prepared.intent
        project_id=(await session.execute(select(OutreachDraft.project_id).where(
            OutreachDraft.workspace_id==intent.workspace_id,OutreachDraft.id==bindings['draft_id']))).scalar_one()
        if (authorization.workspace_id!=intent.workspace_id or authorization.project_id!=project_id
            or authorization.sender_identity_id!=intent.sender_identity_id or intent.recipient_ref not in authorization.recipient_refs):
            raise ApiError(503,'PROVIDER_UNAVAILABLE','original delivery scope is not authorized')
        await lock_budget_workspace(session,intent.workspace_id)
        operation=(await session.execute(select(ProviderOperation).where(
            ProviderOperation.workspace_id==intent.workspace_id,ProviderOperation.id==operation_id).with_for_update())).scalar_one_or_none()
        if operation is None:raise ApiError(404,'NOT_FOUND','original delivery operation not found')
        if (operation.capability!='delivery' or operation.intent_key!=intent.key or operation.input_hash!=intent.payload_digest
            or operation.provider_name!=authorization.provider_name or operation.account_reference!=authorization.account_reference):
            raise ApiError(409,'IDEMPOTENCY_CONFLICT','original delivery operation binding differs')
        from .provider_policy_context import require_delivery_policy
        await require_delivery_policy(session, prepared=prepared, authorization=authorization,
                                      project_id=project_id, draft_id=bindings['draft_id'])
        existing=(await session.execute(select(BudgetReservation.id).where(
            BudgetReservation.workspace_id==intent.workspace_id,BudgetReservation.operation_id==operation.id))).scalar_one_or_none()
        if operation.status!='intent' and existing is None:
            raise ApiError(409,'RETRY_UNSAFE','non-intent delivery requires original liability reconciliation')
        if authorization.valid_until<=datetime.now(timezone.utc):
            raise ApiError(503,'PROVIDER_UNAVAILABLE','delivery budget authority expired before reservation')
        reservation=await reserve_operation(session,operation.id,{'workspace_id':intent.workspace_id,'project_id':project_id,'category':'delivery'},
            authorization.upper_bound,authorization.currency,authorization.pricing_version)
        if authorization.valid_until<=datetime.now(timezone.utc):
            raise ApiError(503,'PROVIDER_UNAVAILABLE','delivery budget authority expired during reservation')
        return reservation
