"""Code-owned model route planning; no factory, receipt, spend or network."""
from dataclasses import replace
import hashlib,json
import pytest
from buyeros_api.providers import base,registry
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from buyeros_api.providers.model import ModelRoute
from tests.test_provider_contracts import capability

def configured(monkeypatch,**changes):
    fields=ProviderRegistration.__dataclass_fields__
    assert {'model_route','model_id'}<=set(fields),'C61-19 reviewed model route and model identity metadata are absent'
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'openai-responses'}));monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'openai-responses'}))
    calls=[];route=ModelRoute('synthetic-prompt-v1',frozenset(),1000,500,30,0,'synthetic-route-v1')
    def factory():calls.append('factory');raise AssertionError('read-only model planning called factory')
    values=dict(capability=capability(provider='openai-responses',service='model',markets=frozenset({'US'}),languages=frozenset({'en'})),factory=factory,sandbox_evidence=('synthetic:model-selection-only',),model_route=route,model_id='synthetic-model-v1');values.update(changes)
    return ProviderRegistration(**values),calls

@pytest.mark.parametrize('gate',['verified','no-registration','allowlist-empty','sandbox-missing','unscoped','unsupported-market','unsupported-language','unknown-status','missing-liability'])
def test_selected_model_configuration_requires_complete_current_reviewed_route_without_factory(monkeypatch,gate):
    item,calls=configured(monkeypatch)
    if gate=='allowlist-empty':monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset())
    if gate=='sandbox-missing':item=replace(item,sandbox_evidence=())
    if gate=='unscoped':item=replace(item,model_route=None,model_id=None)
    if gate=='unknown-status':item=replace(item,capability=replace(item.capability,status='unknown'))
    if gate=='missing-liability':item=replace(item,capability=replace(item.capability,max_liability=None))
    owned=ProviderRegistry(() if gate=='no-registration' else (item,))
    selector=getattr(owned,'model_run_configuration',None);assert callable(selector),'C61-19 pure model registry selector is absent'
    value=selector(market='HK' if gate=='unsupported-market' else 'US',language='zz' if gate=='unsupported-language' else 'en',environment='production')
    if gate=='verified':
        assert value=={'capability':item.capability,'route':item.model_route,'model_id':item.model_id,'registry_contract_hash':item.contract_hash,'receipt_contract_hash':ProviderRegistration(item.capability,lambda:None).contract_hash}
    else:assert value is None
    assert calls==[]

@pytest.mark.parametrize('bad',['missing-id','missing-route','wrong-service','mutable-tools','empty-route-id','boolean-token-bound','oversize-model-id'])
def test_model_registration_rejects_partial_mutable_or_unbounded_native_configuration(monkeypatch,bad):
    item,_=configured(monkeypatch);route=item.model_route
    if bad=='missing-id':changes={'model_id':None}
    elif bad=='missing-route':changes={'model_route':None}
    elif bad=='wrong-service':changes={'capability':capability()}
    elif bad=='mutable-tools':changes={'model_route':replace(route,permitted_tools=set())}
    elif bad=='empty-route-id':changes={'model_route':replace(route,route_id='')}
    elif bad=='boolean-token-bound':changes={'model_route':replace(route,max_input_tokens=True)}
    else:changes={'model_id':'x'*201}
    with pytest.raises(ValueError,match='model'):replace(item,**changes)

def test_model_full_registry_hash_binds_route_model_and_review_without_changing_historical_receipt_hash(monkeypatch):
    item,calls=configured(monkeypatch);old=ProviderRegistration(item.capability,lambda:None)
    historical=hashlib.sha256(json.dumps(old.snapshot(),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert historical==old.contract_hash and 'model_route' not in old.snapshot() and 'model_id' not in old.snapshot()
    assert item.contract_hash!=old.contract_hash
    variants=[replace(item,model_id='synthetic-model-v2'),replace(item,model_route=replace(item.model_route,prompt_version='synthetic-prompt-v2')),replace(item,model_route=replace(item.model_route,max_output_tokens=501)),replace(item,sandbox_evidence=('synthetic:changed-review',))]
    assert len({item.contract_hash,*[x.contract_hash for x in variants]})==5 and ProviderRegistration(item.capability,lambda:None).contract_hash==historical and calls==[]

def test_default_production_model_configuration_stays_unselected():
    selector=getattr(registry.DEFAULT_REGISTRY,'model_run_configuration',None);assert callable(selector),'C61-19 pure model registry selector is absent'
    assert selector(market='US',language='en',environment='production') is None
    assert registry.SELECTED_LIVE_PROVIDERS==base.SELECTED_LIVE_PROVIDERS==frozenset()
