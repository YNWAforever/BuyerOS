from dataclasses import replace
from decimal import Decimal
import pytest
from buyeros_api.providers.base import FixtureProviderAdapter,Money,ProviderIntent
from buyeros_api.providers.registry import (ProviderRegistry,ProviderRegistration,ProviderUnavailable,resolve_provider)
from tests.test_provider_contracts import capability


def fixture_registry(**changes):
    cap=capability(**changes)
    item=ProviderRegistration(cap,lambda:FixtureProviderAdapter(cap,environment='test'),('fixture:test-contract',))
    return ProviderRegistry((item,)),item


@pytest.mark.parametrize('service',['search','model','contact'])
def test_unselected_provider_stays_503(service):
    with pytest.raises(ProviderUnavailable) as failure:
        resolve_provider(service,environment='production')
    assert failure.value.status_code==503
    assert failure.value.reasons==('PROVIDER_UNSELECTED',)


def test_unverified_provider_stays_blocked():
    registry,_=fixture_registry(verified_at=None,pricing_version='',status='unknown',max_liability=None)
    with pytest.raises(ProviderUnavailable) as failure:
        registry.resolve('search',environment='test')
    assert {'EVIDENCE_MISSING','PRICE_UNVERIFIED','UNKNOWN_STATUS_SEMANTICS','UNBOUNDED_TARIFF'} <= set(failure.value.reasons)


@pytest.mark.parametrize('environment',['production','staging','prod','TEST',''])
def test_fixture_cannot_activate_in_production_or_unknown_environment(environment):
    registry,_=fixture_registry()
    with pytest.raises(ProviderUnavailable) as failure:
        registry.resolve('search',environment=environment)
    assert {'FIXTURE_IN_PRODUCTION','UNKNOWN_ENVIRONMENT'} & set(failure.value.reasons)


def test_verified_test_registration_resolves_exact_adapter():
    registry,item=fixture_registry()
    adapter=registry.resolve('search',environment='test')
    assert isinstance(adapter,FixtureProviderAdapter)
    assert adapter.capability==item.capability


def test_contract_snapshot_is_versioned_and_exact_decimal():
    _,item=fixture_registry()
    assert item.snapshot()['max_liability_usd']=='1.000000'
    assert item.snapshot()['source_urls']==['https://example.test/fixture-contract']
    assert len(item.contract_hash)==64
    changed=replace(item,capability=replace(item.capability,max_liability=Money(Decimal('1.100000'))))
    assert changed.contract_hash!=item.contract_hash


def test_price_change_requires_reconfirm_even_if_vendor_reuses_price_version():
    _,previous=fixture_registry()
    updated=replace(previous,capability=replace(previous.capability,max_liability=Money(Decimal('1.100000'))))
    registry=ProviderRegistry((updated,))
    with pytest.raises(ProviderUnavailable) as failure:
        registry.estimate(ProviderIntent('stable','search','HK','en','company'),environment='test',budget=Money(Decimal('2.000000')),quoted_pricing_version=previous.capability.pricing_version,quoted_contract_hash=previous.contract_hash)
    assert failure.value.reasons==('PRICE_RECONFIRM_REQUIRED',)


@pytest.mark.parametrize(('budget','reason'),[(None,'BUDGET_UNVERIFIED'),(Money(Decimal('0.999999')),'BUDGET_EXCEEDED')])
def test_admission_requires_bounded_budget_before_factory(budget,reason):
    _,item=fixture_registry()
    calls=[]
    registry=ProviderRegistry((replace(item,factory=lambda:calls.append('must not construct')),))
    with pytest.raises(ProviderUnavailable) as failure:
        registry.estimate(ProviderIntent('stable','search','HK','en','company'),environment='test',budget=budget,quoted_pricing_version=item.capability.pricing_version,quoted_contract_hash=item.contract_hash)
    assert failure.value.reasons==(reason,)
    assert calls==[]


def test_verified_fixture_estimate_preserves_decimal():
    registry,item=fixture_registry()
    result=registry.estimate(ProviderIntent('stable','search','HK','en','company'),environment='test',budget=Money(Decimal('1.000000')),quoted_pricing_version=item.capability.pricing_version,quoted_contract_hash=item.contract_hash)
    assert result==Money(Decimal('1.000000'))


def test_factory_cannot_swap_verified_adapter_capability():
    _,item=fixture_registry()
    other=capability(service='contact')
    registry=ProviderRegistry((replace(item,factory=lambda:FixtureProviderAdapter(other,environment='test')),))
    with pytest.raises(ProviderUnavailable) as failure:
        registry.resolve('search',environment='test')
    assert failure.value.reasons==('ADAPTER_CONTRACT_MISMATCH',)


def test_code_owned_names_and_service_uniqueness():
    with pytest.raises(ValueError):fixture_registry(provider='arbitrary-env-provider')
    _,item=fixture_registry()
    with pytest.raises(ValueError):ProviderRegistry((item,item))
    with pytest.raises(ValueError):resolve_provider('delivery',environment='test')


@pytest.mark.parametrize('environment',['test','staging','production'])
def test_unselected_real_vendor_cannot_use_test_environment_as_activation(environment):
    _,item=fixture_registry(provider='brave-search')
    calls=[]
    registry=ProviderRegistry((replace(item,factory=lambda:calls.append('external call forbidden')),))
    with pytest.raises(ProviderUnavailable) as failure:
        registry.resolve('search',environment=environment)
    assert 'PROVIDER_UNSELECTED' in failure.value.reasons
    assert calls==[]


def test_readiness_exposes_safe_reason_and_next_action():
    from buyeros_api.providers.registry import provider_readiness
    from buyeros_api.api.routes.health import capabilities_payload
    value=provider_readiness('search',environment='production')
    assert value['status']=='blocked'
    assert value['reason_codes']==['PROVIDER_UNSELECTED']
    assert value['actions'] and 'Choose a vendor' in value['actions'][0]
    research=next(row for row in capabilities_payload()['items'] if row['name']=='research')
    assert research['status']=='unconfigured'
    assert 'PROVIDER_UNSELECTED' in research['reason_codes']
    assert research['billable'] is False
