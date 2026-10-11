"""Independent delivery-only submit-result validation; no provider calls."""
import importlib
from decimal import Decimal
import pytest
from buyeros_api.providers.base import SubmissionResult,StatusResult

def validator():
 method=getattr(importlib.import_module('buyeros_api.providers.delivery'),'validate_delivery_submission',None)
 assert callable(method),'independent bounded delivery submission result validator missing'
 return method

@pytest.mark.parametrize('state,ref',[('accepted','original-ref'),('unknown',None),('unknown','original-ref'),('rejected',None)])
def test_delivery_submission_result_preserves_exact_typed_acceptance_and_reference(state,ref):
 result=SubmissionResult(state,ref,Decimal('0.000001'),'a'*64)
 assert validator()(result) is result

@pytest.mark.parametrize('field,value',[
 ('state','prepared'),('state','delivered'),('state',''),('state',None),('state',1),('state',[]),
 ('provider_ref',None),('provider_ref',''),('provider_ref','x'*201),('provider_ref','hidden\nheader'),('provider_ref','email@example.invalid'),('provider_ref','ｒｅｆ'),('provider_ref',1),
 ('unknown_ref','hidden\nheader'),('rejected_ref','original-ref'),
 ('observed_usage',True),('observed_usage',0.1),('observed_usage',Decimal('NaN')),('observed_usage',Decimal('Infinity')),('observed_usage',Decimal('-1')),('observed_usage',Decimal('0.0000001')),('observed_usage',Decimal('100000000000000')),
 ('redacted_digest',''),('redacted_digest','A'*64),('redacted_digest','a'*63),('redacted_digest',1),
])
def test_delivery_submission_result_rejects_malformed_unbounded_or_ambiguous_response(field,value):
 values=dict(state='accepted',provider_ref='original-ref')
 if field in {'unknown_ref','rejected_ref'}:values.update(state='unknown' if field=='unknown_ref' else 'rejected',provider_ref=value)
 else:values[field]=value
 with pytest.raises(ValueError,match='invalid delivery submission result'):validator()(SubmissionResult(**values))

@pytest.mark.parametrize('result',[None,{},StatusResult('accepted','original-ref')])
def test_delivery_submission_result_refuses_untyped_and_status_response(result):
 with pytest.raises(ValueError,match='invalid delivery submission result'):validator()(result)

def test_delivery_submission_result_rechecks_frozen_values_before_durable_application():
 result=SubmissionResult('accepted','original-ref');object.__setattr__(result,'provider_ref',None)
 with pytest.raises(ValueError,match='invalid delivery submission result'):validator()(result)
