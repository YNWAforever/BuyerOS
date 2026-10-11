"""Read-only contact planning with synthetic reviewed metadata; never provider IO."""
from dataclasses import replace
import hashlib,json
import pytest
from buyeros_api.providers import base,registry
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from tests.test_provider_contracts import capability

def configured(monkeypatch):
    scope_type=getattr(registry,'ContactLookupScope',None)
    assert scope_type is not None,'C61-15 immutable reviewed contact account/scope metadata is absent'
    assert 'contact_scope' in ProviderRegistration.__dataclass_fields__,'C61-15 contact registration scope is absent'
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'hunter'}))
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'hunter'}))
    calls=[]
    def factory():calls.append('factory');raise AssertionError('read-only contact planning called factory')
    scope=scope_type(account_reference='synthetic-contact-account-v1',
        market_languages=(('US',('en',)),('HK',('zh-HK',))),
        nonbillable_status=True,status_evidence=('synthetic:saved-status-nocharge-proof-v1',),max_contacts=10)
    cap=capability(provider='hunter',service='contact',markets=frozenset({'US','HK'}),
        languages=frozenset({'en','zh-HK'}),roles=frozenset({'Procurement Manager'}))
    return ProviderRegistration(cap,factory,('synthetic:contact-selection-only',),contact_scope=scope),calls

@pytest.mark.parametrize('gate',['verified-US','verified-HK','no-registration','allowlist-empty',
    'sandbox-missing','unscoped','unsupported-market','unsupported-language','unsupported-pair',
    'unsupported-role','unknown-status','unsupported-status','unverified-idempotency',
    'missing-liability','missing-price','missing-official-evidence','missing-retention',
    'billable-status','missing-nonbillable-evidence','invalid-environment'])
def test_contact_planning_requires_current_bounded_reviewed_account_and_status_without_factory(monkeypatch,gate):
    item,calls=configured(monkeypatch)
    if gate=='allowlist-empty':monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset())
    if gate=='sandbox-missing':item=replace(item,sandbox_evidence=())
    if gate=='unscoped':item=replace(item,contact_scope=None)
    cap_changes={'unknown-status':{'status':'unknown'},'unsupported-status':{'status':'unsupported'},
        'unverified-idempotency':{'idempotency':'unknown'},'missing-liability':{'max_liability':None},
        'missing-price':{'pricing_version':''},'missing-official-evidence':{'source_urls':()},
        'missing-retention':{'retention':''}}
    if gate in cap_changes:item=replace(item,capability=replace(item.capability,**cap_changes[gate]))
    if gate=='billable-status':item=replace(item,contact_scope=replace(item.contact_scope,nonbillable_status=False))
    if gate=='missing-nonbillable-evidence':item=replace(item,contact_scope=replace(item.contact_scope,status_evidence=()))
    owned=ProviderRegistry(() if gate=='no-registration' else (item,))
    selector=getattr(owned,'contact_lookup_configuration',None)
    assert callable(selector),'C61-15 pure reviewed contact configuration selector is absent'
    market='HK' if gate=='verified-HK' else 'DE' if gate=='unsupported-market' else 'US'
    language='zh-HK' if gate in {'verified-HK','unsupported-pair'} else 'zz' if gate=='unsupported-language' else 'en'
    value=selector(market=market,language=language,role='other' if gate=='unsupported-role' else 'Procurement Manager',
        environment='prod' if gate=='invalid-environment' else 'production')
    if gate.startswith('verified-'):
        assert value=={'capability':item.capability,'scope':item.contact_scope,
            'registry_contract_hash':item.contract_hash,
            'receipt_contract_hash':ProviderRegistration(item.capability,lambda:None).contract_hash}
    else:assert value is None
    assert calls==[]

@pytest.mark.parametrize('bad',['empty-account','oversize-account','email-account','url-account','space-account',
    'control-account','mutable-pairs','mutable-languages','empty-pairs','duplicate-market','duplicate-language',
    'invalid-market','empty-language','oversize-language','nonboolean-status','mutable-status-evidence',
    'empty-status-reference','control-status-reference','oversize-status-reference','boolean-limit',
    'zero-limit','oversize-limit','unsupported-contact-type'])
def test_contact_scope_rejects_mutable_unbounded_or_nonopaque_account_and_lookup_basis(monkeypatch,bad):
    item,calls=configured(monkeypatch)
    changes={'empty-account':{'account_reference':''},'oversize-account':{'account_reference':'x'*129},
        'email-account':{'account_reference':'owner@example.test'},'url-account':{'account_reference':'https://example.test'},
        'space-account':{'account_reference':'account v1'},'control-account':{'account_reference':'account\nv1'},
        'mutable-pairs':{'market_languages':[('US',('en',))]},'mutable-languages':{'market_languages':(('US',['en']),)},
        'empty-pairs':{'market_languages':()},'duplicate-market':{'market_languages':(('US',('en',)),('US',('en',)))},
        'duplicate-language':{'market_languages':(('US',('en','en')), )},'invalid-market':{'market_languages':(('us',('en',)),)},
        'empty-language':{'market_languages':(('US',('',)),)},'oversize-language':{'market_languages':(('US',('x'*129,)),)},
        'nonboolean-status':{'nonbillable_status':1},'mutable-status-evidence':{'status_evidence':['synthetic:proof']},
        'empty-status-reference':{'status_evidence':('',)},'control-status-reference':{'status_evidence':('synthetic:\nproof',)},
        'oversize-status-reference':{'status_evidence':('x'*201,)},'boolean-limit':{'max_contacts':True},
        'zero-limit':{'max_contacts':0},'oversize-limit':{'max_contacts':11},'unsupported-contact-type':{'contact_type':'personal_email'}}
    with pytest.raises(ValueError,match='contact'):replace(item.contact_scope,**changes[bad])
    assert calls==[]

@pytest.mark.parametrize('bad',['wrong-service','wrong-provider','scope-market-outside-capability',
    'scope-language-outside-capability','mutable-capability-roles'])
def test_contact_registration_rejects_scope_not_owned_by_its_exact_hunter_capability(monkeypatch,bad):
    item,calls=configured(monkeypatch)
    changes={'wrong-service':{'service':'model'},'wrong-provider':{'provider':'fixture'},
        'scope-market-outside-capability':{'markets':frozenset({'US'})},
        'scope-language-outside-capability':{'languages':frozenset({'en'})},
        'mutable-capability-roles':{'roles':{'Procurement Manager'}}}
    with pytest.raises(ValueError,match='contact'):replace(item,capability=replace(item.capability,**changes[bad]))
    assert calls==[]

def test_contact_full_registry_hash_binds_account_pair_count_and_nonbillable_proof_preserving_old_receipt_hash(monkeypatch):
    item,calls=configured(monkeypatch);old=ProviderRegistration(item.capability,lambda:None)
    historical=hashlib.sha256(json.dumps(old.snapshot(),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert old.contract_hash==historical and 'contact_scope' not in old.snapshot()
    variants=[replace(item,contact_scope=replace(item.contact_scope,account_reference='synthetic-contact-account-v2')),
        replace(item,contact_scope=replace(item.contact_scope,market_languages=(('US',('en',)),))),
        replace(item,contact_scope=replace(item.contact_scope,max_contacts=9)),
        replace(item,contact_scope=replace(item.contact_scope,nonbillable_status=False)),
        replace(item,contact_scope=replace(item.contact_scope,status_evidence=('synthetic:proof-v2',))),
        replace(item,sandbox_evidence=('synthetic:review-v2',))]
    assert len({old.contract_hash,item.contract_hash,*[x.contract_hash for x in variants]})==8
    assert ProviderRegistration(item.capability,lambda:None).contract_hash==historical and calls==[]

def test_default_contact_planning_and_both_public_selectors_remain_closed():
    selector=getattr(registry.DEFAULT_REGISTRY,'contact_lookup_configuration',None)
    assert callable(selector),'C61-15 pure reviewed contact configuration selector is absent'
    assert selector(market='US',language='en',role='Procurement Manager',environment='production') is None
    assert registry.SELECTED_LIVE_PROVIDERS==base.SELECTED_LIVE_PROVIDERS==frozenset()
    from buyeros_api.api.routes.quotes import selected_contact_quote_capability
    from buyeros_api.api.routes.enrichment import selected_contact_status_capability
    assert selected_contact_quote_capability()==(None,'production')
    assert selected_contact_status_capability()==(None,'production',False)
