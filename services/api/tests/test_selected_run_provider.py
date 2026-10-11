"""Pure code-owned selector contract; all vendor/tariff/proof values synthetic."""
from dataclasses import replace
from decimal import Decimal
import pytest
from buyeros_api.api.routes.runs import selected_run_capability
from buyeros_api.providers import base,registry
from buyeros_api.providers.registry import ProviderRegistration,ProviderRegistry
from tests.test_provider_contracts import capability

@pytest.mark.parametrize('mode',['valid','changed-scope','default','unselected','sandbox-missing','price-missing','status-unknown','fixture','filter-missing','pair-unsupported','duplicate-pair','wrong-shape','unsupported-provider','transport-role-missing'])
def test_selected_run_capability_uses_only_verified_code_owned_search_scope(monkeypatch,mode):
    factory_calls=[]
    cap=capability(provider='brave-search',service='search',markets=frozenset({'HK'}),languages=frozenset({'en','zh-HK'}),roles=frozenset({'company'}))
    if mode=='fixture':cap=replace(cap,provider='fixture')
    if mode=='unsupported-provider':cap=replace(cap,provider='openai-responses')
    if mode=='transport-role-missing':cap=replace(cap,roles=frozenset({'distributor'}))
    if mode=='price-missing':cap=replace(cap,pricing_version='')
    if mode=='status-unknown':cap=replace(cap,status='unknown')
    item=ProviderRegistration(cap,lambda:factory_calls.append('must-not-build-tenant-adapter'),() if mode=='sandbox-missing' else ('synthetic:local-proof-only',))
    # Stage the new frozen registration scope on the existing real object before wiring exists.
    filters=frozenset({'market','language'}) if mode!='filter-missing' else frozenset({'market'})
    pairs=(('HK',('en',)),)
    if mode=='changed-scope':pairs=(('HK',('zh-HK',)),)
    if mode=='pair-unsupported':pairs=(('US',('en',)),)
    if mode=='duplicate-pair':pairs=(('HK',('en',)),('HK',('zh-HK',)))
    if mode=='wrong-shape':pairs={'HK':['en']}
    object.__setattr__(item,'verified_filters',filters)
    object.__setattr__(item,'market_languages',pairs)
    selected=frozenset() if mode=='unselected' else frozenset({'brave-search','openai-responses'})
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',selected)
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',selected)
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(()) if mode=='default' else ProviderRegistry((item,)))
    actual,environment=selected_run_capability()
    assert environment=='production' and factory_calls==[]
    if mode not in {'valid','changed-scope'}:
        assert actual is None
        return
    assert actual is not None,'Verified registry currently never reaches run admission'
    assert actual['provider']==cap.provider and actual['service']=='search' and actual['verified'] is True
    assert actual['price_version']==cap.pricing_version
    assert actual['verified_filters']==['language','market']
    assert actual['market_languages']=={k:list(v) for k,v in pairs}
    assert actual['receipt_contract_hash']==ProviderRegistration(cap,lambda:None).contract_hash
    assert actual['markets']==['HK'] and actual['languages']==['en','zh-HK'] and actual['roles']==['company']
    # Returned request planning values cannot mutate the frozen code-owned scope.
    actual['market_languages']['HK'].append('bad')
    again,_=selected_run_capability();assert again['market_languages']=={k:list(v) for k,v in pairs}


@pytest.mark.parametrize('mode',['valid','filters','duplicate','mutable','unsupported'])
def test_registration_search_scope_constructor_is_frozen_bounded_and_hash_bound(mode):
    cap=capability(provider='brave-search',service='search',markets=frozenset({'HK'}),languages=frozenset({'en','zh-HK'}))
    filters=frozenset({'market','language'});pairs=(('HK',('en',)),)
    if mode=='filters':filters=frozenset({'market'})
    if mode=='duplicate':pairs=(('HK',('en',)),('HK',('zh-HK',)))
    if mode=='mutable':pairs={'HK':['en']}
    if mode=='unsupported':pairs=(('US',('en',)),)
    if mode!='valid':
        with pytest.raises(ValueError):ProviderRegistration(cap,lambda:None,('synthetic:proof',),filters,pairs)
        return
    item=ProviderRegistration(cap,lambda:None,('synthetic:proof',),filters,pairs)
    changed=replace(item,market_languages=(('HK',('zh-HK',)),))
    assert item.contract_hash!=changed.contract_hash
    assert item.snapshot()['market_languages']=={'HK':['en']}
    old=ProviderRegistration(cap,lambda:None)
    assert 'verified_filters' not in old.snapshot() and 'market_languages' not in old.snapshot()

from tests.test_api_projects_db import api as project_api,WORKSPACE_A,OPERATOR
from tests.test_run_admission_integration_db import admission_case,_post,_count

@pytest.fixture
def migrated(isolated_migrated):
    return isolated_migrated

@pytest.mark.parametrize('mode',['default','paid-off','verified','lost-replay','role-revoked','missing-scope'])
def test_registry_selected_scope_reaches_real_atomic_admission_without_route_override(admission_case,monkeypatch,mode):
    import uuid,psycopg
    from buyeros_api.settings import get_settings
    api,dsn=admission_case;calls=[]
    cap=capability(provider='brave-search',service='search',markets=frozenset({'US'}),languages=frozenset({'en'}),roles=frozenset({'company','distributor'}))
    item=ProviderRegistration(cap,lambda:calls.append('tenant-factory-must-not-run'),('synthetic:owned-HTTP-scope-proof',),
                              None if mode=='missing-scope' else frozenset({'market','language'}),
                              None if mode=='missing-scope' else (('US',('en',)),))
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    monkeypatch.setattr(registry,'DEFAULT_REGISTRY',ProviderRegistry(()) if mode=='default' else ProviderRegistry((item,)))
    # Test-owned process/DB only; paid gate is never changed in committed defaults.
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','false' if mode=='paid-off' else 'true');get_settings.cache_clear()
    api.app.dependency_overrides.pop(selected_run_capability)
    if mode=='role-revoked':
        with psycopg.connect(dsn) as db:
            db.execute("UPDATE memberships SET roles='{Reviewer}' WHERE workspace_id=%s AND user_id=%s",(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)))
    try:
        first=_post(api,key='c61-registry-'+mode)
        if mode not in {'verified','lost-replay'}:
            assert first.status_code==(403 if mode=='role-revoked' else 503),first.text
            assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==0
        else:
            assert first.status_code==202,first.text
            data=first.json()['data']
            again=_post(api,key='c61-registry-'+mode);assert again.status_code==202 and again.json()['data']==data
            assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==1
            with psycopg.connect(dsn) as db:
                snapshot=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(data['id'],)).fetchone()[0]
                assert snapshot['capability']['provider']=='brave-search'
                assert snapshot['capability']['receipt_contract_hash']==ProviderRegistration(cap,lambda:None).contract_hash
                assert snapshot['query_plan']['queries'][0]['filters']=={'market':'US','language':'en'}
        assert calls==[] and _count(dsn,'provider_operations')==_count(dsn,'cost_events')==0
    finally:get_settings.cache_clear()


@pytest.mark.parametrize('supported',[False,True])
def test_registry_quote_rejects_unverified_market_language_pair_before_factory(monkeypatch,supported):
    from buyeros_api.providers.base import Money,ProviderIntent
    from buyeros_api.providers.registry import ProviderUnavailable
    cap=capability(provider='brave-search',service='search',markets=frozenset({'HK','US'}),languages=frozenset({'en','zh-HK'}))
    calls=[]
    class Adapter:
        capability=cap
        def estimate(self,intent):return cap.max_liability
        async def submit(self,intent):raise AssertionError('quote must never submit')
        async def status(self,ref):raise AssertionError('quote must never query')
    def factory():calls.append(1);return Adapter()
    item=ProviderRegistration(cap,factory,('synthetic:pair-proof',),frozenset({'market','language'}),(('HK',('zh-HK',)),('US',('en',))))
    owner=ProviderRegistry((item,));monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}));monkeypatch.setattr(registry,'SELECTED_LIVE_PROVIDERS',frozenset({'brave-search'}))
    intent=ProviderIntent('synthetic-quote','search','US' if supported else 'HK','en','company')
    def quote():return owner.estimate(intent,environment='production',budget=Money(Decimal('2.000000')),quoted_pricing_version=cap.pricing_version,quoted_contract_hash=item.contract_hash)
    if supported:
        assert quote()==cap.max_liability and calls==[1]
    else:
        with pytest.raises(ProviderUnavailable) as failure:quote()
        assert 'UNSUPPORTED_MARKET_LANGUAGE_PAIR' in failure.value.reasons and calls==[]
