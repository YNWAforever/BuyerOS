"""Independent delivery intent and authentication; offline only, no sender activation."""
import dataclasses,importlib,uuid
from pathlib import Path
import pytest
from buyeros_api.providers.base import ProviderCapability

def core():
    assert Path(__file__).resolve().parents[1].joinpath('buyeros_api/providers/delivery.py').is_file(),'independent delivery protocol missing'
    return importlib.import_module('buyeros_api.providers.delivery')

def intent_args():
    return dict(key='delivery:opaque-001',workspace_id=uuid.uuid4(),draft_revision_id=uuid.uuid4(),recipient_ref=uuid.uuid4(),sender_identity_id=uuid.uuid4(),approval_id=uuid.uuid4(),payload_digest='a'*64)

def test_delivery_intent_is_immutable_and_independent_of_contact_service():
    module=core();intent=module.DeliveryIntent(**intent_args())
    assert not hasattr(intent,'service') and module.DeliveryAdapter is not ProviderCapability
    with pytest.raises(dataclasses.FrozenInstanceError):intent.key='new'

@pytest.mark.parametrize('field,value',[('key',''),('key','x'*129),('key','contains\nheader'),('payload_digest','z'*64),('payload_digest','A'*64),('payload_digest','a'*63),*[(field,'string-not-UUID') for field in ('workspace_id','draft_revision_id','recipient_ref','sender_identity_id','approval_id')],('approval_id',uuid.UUID(int=0))])
def test_delivery_intent_rejects_unbounded_or_ambiguous_binding(field,value):
    module=core();args=intent_args();args[field]=value
    with pytest.raises(ValueError):module.DeliveryIntent(**args)

@pytest.mark.parametrize('state',['submitting','unknown','accepted','delivered','bounced','failed'])
def test_delivery_accepted_unknown_or_submitting_never_authorizes_resubmit(state):
    module=core();assert module.may_submit_delivery(state,approval_current=True,policy_current=True,suppressed=False) is False

@pytest.mark.parametrize('approval,policy,suppressed',[(False,True,False),(True,False,False),(True,True,True),(1,True,False)])
def test_delivery_prepared_requires_exact_current_approval_policy_and_no_suppression(approval,policy,suppressed):
    module=core();assert module.may_submit_delivery('prepared',approval_current=approval,policy_current=policy,suppressed=suppressed) is False

def test_delivery_prepared_current_binding_is_only_submittable_state():
    module=core();assert module.may_submit_delivery('prepared',approval_current=True,policy_current=True,suppressed=False) is True

@pytest.mark.parametrize('current,event,expected',[('delivered','accepted','delivered'),('unknown','accepted','accepted'),('accepted','delivered','delivered'),('bounced','delivered','bounced'),('failed','accepted','failed'),('delivered','bounced','bounced'),('complained','accepted','complained')])
def test_delivery_status_never_regresses_or_confuses_acceptance_and_delivery(current,event,expected):
    assert core().delivery_transition(current,event)==expected

SECRET='whsec_plJ3nmyCDGBKInavdOK15jsl'
BODY=b'{"event_type":"ping","data":{"success":true}}'
HEADERS={'svix-id':'msg_loFOjxBNrRLzqYUf','svix-timestamp':'1731705121','svix-signature':'v1,rAvfW3dJ/X/qxhsaXPOyyCGmRKsaKWcsNccKXlIktD0='}

def test_delivery_webhook_verifies_official_svix_example_raw_bytes():
    module=core();verified=module.verify_delivery_webhook(BODY,HEADERS,secret=SECRET,now=1731705121)
    assert verified.event_id==HEADERS['svix-id'] and verified.raw_body==BODY and len(verified.body_digest)==64
    assert 'success' not in repr(verified)

@pytest.mark.parametrize('mutation',['expired','future','body','secret','missing-id','timestamp','version','huge-body'])
def test_delivery_webhook_rejects_forgery_expiry_and_ambiguous_headers(mutation):
    module=core();headers=dict(HEADERS);body=BODY;secret=SECRET;now=1731705121
    if mutation=='expired':now+=301
    if mutation=='future':now-=301
    if mutation=='body':body+=b' '
    if mutation=='secret':secret='whsec_'+('a'*24)
    if mutation=='missing-id':headers.pop('svix-id')
    if mutation=='timestamp':headers['svix-timestamp']='1731705121.0'
    if mutation=='version':headers['svix-signature']=headers['svix-signature'].replace('v1,','v2,')
    if mutation=='huge-body':body=b'x'*65537
    with pytest.raises(ValueError,match='invalid delivery webhook'):module.verify_delivery_webhook(body,headers,secret=secret,now=now)


@pytest.mark.parametrize('state',['unknown','accepted','delivered','bounced','complained','unsubscribed','failed','rejected'])
def test_delivery_status_result_keeps_observed_reference_and_cannot_authorize_resubmit(state):
    module=core();result=module.DeliveryStatusResult(state,'provider:ref/opaque_1')
    assert result.provider_ref=='provider:ref/opaque_1' and result.event_id is None
    assert module.may_submit_delivery(result.state,approval_current=True,policy_current=True,suppressed=False) is False
    with pytest.raises(dataclasses.FrozenInstanceError):result.provider_ref='other-reference'


@pytest.mark.parametrize('field,value',[
    ('state','prepared'),('state','submitting'),('state','unexpected'),('state',None),('state',1),('state',True),('state',[]),
    ('provider_ref',None),('provider_ref',1),('provider_ref',''),('provider_ref','email@example.invalid'),('provider_ref','x'*201),('provider_ref','hidden\nheader'),('provider_ref','ｒｅｆ'),
    ('event_id',''),('event_id','x'*201),('event_id','ambiguous.event'),('event_id',1),
])
def test_delivery_status_result_rejects_invalid_or_local_only_state_before_any_IO(field,value):
    module=core();args={'state':'accepted','provider_ref':'provider_ref','event_id':'msg_status'};args[field]=value
    with pytest.raises(ValueError,match='invalid observed delivery status'):module.DeliveryStatusResult(**args)


def status_validator():
    method=getattr(core(),'validate_delivery_status',None)
    assert callable(method),'independent original-reference delivery status validator missing'
    return method


def test_delivery_status_result_validator_preserves_exact_original_reference():
    module=core();result=module.DeliveryStatusResult('unknown','original-ref','msg_status')
    assert status_validator()(result,provider_ref='original-ref') is result


def test_delivery_status_result_validator_refuses_rebinding_to_another_reference():
    result=core().DeliveryStatusResult('accepted','foreign-ref')
    with pytest.raises(ValueError,match='invalid observed delivery status'):status_validator()(result,provider_ref='original-ref')
    assert result.provider_ref=='foreign-ref'


@pytest.mark.parametrize('value',[None,1,{'state':'accepted','provider_ref':'original-ref'}])
def test_delivery_status_result_validator_rejects_untyped_or_ambiguous_result(value):
    with pytest.raises(ValueError,match='invalid observed delivery status'):status_validator()(value,provider_ref='original-ref')


@pytest.mark.parametrize('ref',[None,'','x'*201])
def test_delivery_status_result_validator_rejects_missing_original_query_reference(ref):
    result=core().DeliveryStatusResult('unknown','original-ref')
    with pytest.raises(ValueError,match='invalid observed delivery status'):status_validator()(result,provider_ref=ref)


def test_delivery_status_result_validator_rechecks_even_frozen_result_data():
    result=core().DeliveryStatusResult('accepted','original-ref')
    object.__setattr__(result,'state','prepared')
    with pytest.raises(ValueError,match='invalid observed delivery status'):status_validator()(result,provider_ref='original-ref')
