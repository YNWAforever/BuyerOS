"""Versioned code-owned provider registry. Live providers register only from deployed credentials."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable
from .base import (FixtureProviderAdapter, Money, ProviderAdapter, ProviderCapability,
                   ProviderIntent, Service, SELECTED_LIVE_PROVIDERS, LIVE_MODEL_PROVIDERS, LIVE_SEARCH_PROVIDERS,
                   activation_blockers, quote_requires_reconfirmation)
from ..api.errors import ApiError
from .model import ModelRoute


class ProviderName(StrEnum):
    FIXTURE = 'fixture'
    BRAVE_SEARCH = 'brave-search'
    OPENAI_RESPONSES = 'openai-responses'
    HUNTER = 'hunter'
    EXA_SEARCH = 'exa-search'
    ANTHROPIC_MESSAGES = 'anthropic-messages'


class ProviderUnavailable(ApiError):
    def __init__(self, reasons: tuple[str, ...]):
        super().__init__(503, 'CAPABILITY_BLOCKED', 'provider capability is not ready')
        self.reasons = reasons


def _verified_search_scope(item) -> bool:
    """Explicit immutable account-verified filter matrix; never infer a Cartesian product."""
    cap=item.capability
    filters,pairs=item.verified_filters,item.market_languages
    if (cap.service!='search' or type(filters) is not frozenset or filters!=frozenset({'market','language'})
            or type(pairs) is not tuple or not 1<=len(pairs)<=64
            or not 1<=len(cap.markets)<=64 or not 1<=len(cap.languages)<=64 or not 1<=len(cap.roles)<=64):
        return False
    seen=set()
    for pair in pairs:
        if type(pair) is not tuple or len(pair)!=2:
            return False
        market,languages=pair
        if (type(market) is not str or market not in cap.markets or market in seen
                or type(languages) is not tuple or not 1<=len(languages)<=64
                or any(type(language) is not str or language not in cap.languages for language in languages)
                or len(set(languages))!=len(languages)):
            return False
        seen.add(market)
    return True


def _verified_model_scope(item) -> bool:
    """Immutable code-owned model identity and route, never inferred from factory IO."""
    route, model_id = item.model_route, item.model_id
    if (item.capability.service != 'model' or item.capability.provider not in LIVE_MODEL_PROVIDERS
        or type(route) is not ModelRoute or type(model_id) is not str
        or not 1 <= len(model_id) <= 200 or any(c.isspace() or ord(c) < 32 for c in model_id)
        or type(route.permitted_tools) is not frozenset or route.permitted_tools
        or any(type(value) is not str or not 1 <= len(value) <= 200 for value in (route.route_id, route.prompt_version))
        or any(type(value) is not int for value in (route.max_input_tokens, route.max_output_tokens, route.deadline_seconds, route.repair_limit))):
        return False
    return (1 <= route.max_input_tokens <= 20000 and 1 <= route.max_output_tokens <= 4000
            and 1 <= route.deadline_seconds <= 120 and 0 <= route.repair_limit <= 2)



@dataclass(frozen=True)
class ContactLookupScope:
    """Reviewed nonsecret account ID and finite lookup/status evidence, never credentials."""
    account_reference: str
    market_languages: tuple[tuple[str, tuple[str, ...]], ...]
    nonbillable_status: bool
    status_evidence: tuple[str, ...] = ()
    contact_type: str = 'business_email'
    max_contacts: int = 10

    def __post_init__(self):
        import re
        if (type(self.account_reference) is not str
            or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',self.account_reference) is None
            or type(self.nonbillable_status) is not bool
            or self.contact_type!='business_email'
            or type(self.max_contacts) is not int or not 1<=self.max_contacts<=10
            or type(self.status_evidence) is not tuple or len(self.status_evidence)>16
            or any(type(ref) is not str or not 1<=len(ref)<=200 or any(ord(c)<32 or ord(c)==127 for c in ref) for ref in self.status_evidence)
            or type(self.market_languages) is not tuple or not 1<=len(self.market_languages)<=64):
            raise ValueError('immutable bounded contact account/status/lookup scope required')
        seen=set()
        for pair in self.market_languages:
            if type(pair) is not tuple or len(pair)!=2:
                raise ValueError('immutable bounded contact market/language pair required')
            market,languages=pair
            if (type(market) is not str or re.fullmatch(r'[A-Z]{2}',market) is None or market in seen
                or type(languages) is not tuple or not 1<=len(languages)<=64
                or any(type(lang) is not str or not 1<=len(lang)<=128 or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in lang) for lang in languages)
                or len(set(languages))!=len(languages)):
                raise ValueError('immutable bounded contact market/language pair required')
            seen.add(market)


def _verified_contact_scope(item) -> bool:
    cap,scope=item.capability,item.contact_scope
    if (cap.service!='contact' or cap.provider!=ProviderName.HUNTER or type(scope) is not ContactLookupScope
        or any(type(values) is not frozenset or not 1<=len(values)<=64 for values in (cap.markets,cap.languages,cap.roles))
        or any(type(role) is not str or not 1<=len(role)<=128 or any(ord(c)<32 or ord(c)==127 for c in role) for role in cap.roles)):
        return False
    return all(market in cap.markets and all(language in cap.languages for language in languages)
               for market,languages in scope.market_languages)


@dataclass(frozen=True)
class ProviderRegistration:
    capability: ProviderCapability
    factory: Callable[[], ProviderAdapter]
    sandbox_evidence: tuple[str, ...] = ()
    verified_filters: frozenset[str] | None = None
    market_languages: tuple[tuple[str, tuple[str, ...]], ...] | None = None
    model_route: ModelRoute | None = None
    model_id: str | None = None
    contact_scope: ContactLookupScope | None = None

    def __post_init__(self):
        ProviderName(self.capability.provider)
        if (self.verified_filters is not None or self.market_languages is not None) and not _verified_search_scope(self):
            raise ValueError('explicit bounded verified search filter/pair scope required')
        if (self.model_route is not None or self.model_id is not None) and not _verified_model_scope(self):
            raise ValueError('explicit immutable bounded model identity and route required')
        if self.contact_scope is not None and not _verified_contact_scope(self):
            raise ValueError('explicit immutable bounded contact capability/account scope required')

    def snapshot(self) -> dict:
        cap = self.capability
        value = {'provider': cap.provider, 'adapter_version': cap.adapter_version,
                'service': cap.service, 'auth_model': cap.auth_model,
                'markets': sorted(cap.markets), 'languages': sorted(cap.languages),
                'roles': sorted(cap.roles), 'pricing_version': cap.pricing_version,
                'max_liability_usd': format(cap.max_liability.amount, '.6f') if cap.max_liability else None,
                'idempotency': cap.idempotency, 'status': cap.status,
                'callback': cap.callback, 'cancel': cap.cancel, 'retention': cap.retention,
                'verified_at': cap.verified_at.isoformat() if cap.verified_at else None,
                'source_urls': list(cap.source_urls), 'sandbox_evidence': list(self.sandbox_evidence)}
        if self.verified_filters is not None:
            value['verified_filters']=sorted(self.verified_filters)
            value['market_languages']={market:list(languages) for market,languages in self.market_languages}
        if self.model_route is not None:
            route=self.model_route
            value['model_id']=self.model_id
            value['model_route']={'route_id':route.route_id,'prompt_version':route.prompt_version,
                'permitted_tools':sorted(route.permitted_tools),'max_input_tokens':route.max_input_tokens,
                'max_output_tokens':route.max_output_tokens,'deadline_seconds':route.deadline_seconds,
                'repair_limit':route.repair_limit}
        if self.contact_scope is not None:
            scope=self.contact_scope
            value['contact_scope']={'account_reference':scope.account_reference,
                'market_languages':{market:list(languages) for market,languages in scope.market_languages},
                'nonbillable_status':scope.nonbillable_status,'status_evidence':list(scope.status_evidence),
                'contact_type':scope.contact_type,'max_contacts':scope.max_contacts}
        return value

    @property
    def contract_hash(self) -> str:
        return hashlib.sha256(json.dumps(self.snapshot(),sort_keys=True,separators=(',',':')).encode()).hexdigest()


@dataclass(frozen=True)
class ProviderRegistry:
    registrations: tuple[ProviderRegistration, ...] = ()

    def __post_init__(self):
        services = [item.capability.service for item in self.registrations]
        if len(services) != len(set(services)):
            raise ValueError('exactly one versioned registration per service')

    def registration(self, service: Service) -> ProviderRegistration | None:
        if service not in {'search','model','contact'}:
            raise ValueError('unsupported service; delivery has a separate contract')
        return next((item for item in self.registrations if item.capability.service == service), None)

    def blockers(self, service: Service, *, environment: str, intent: ProviderIntent | None = None) -> tuple[str, ...]:
        item = self.registration(service)
        if environment not in {'test','staging','production'}:
            return ('UNKNOWN_ENVIRONMENT',)
        if item is None:
            return ('PROVIDER_UNSELECTED',)
        cap = item.capability
        reasons = list(activation_blockers(cap, market=intent.market if intent else next(iter(sorted(cap.markets)), ''),
                         language=intent.language if intent else next(iter(sorted(cap.languages)), ''),
                         role=intent.role if intent else next(iter(sorted(cap.roles)), '') if service=='contact' else 'company', environment=environment))
        if cap.provider != ProviderName.FIXTURE and cap.provider not in SELECTED_LIVE_PROVIDERS:
            reasons.append('PROVIDER_UNSELECTED')
        if not item.sandbox_evidence:
            reasons.append('SANDBOX_EVIDENCE_MISSING')
        if service=='search' and cap.provider!=ProviderName.FIXTURE and not _verified_search_scope(item):
            reasons.append('SEARCH_FILTERS_UNVERIFIED')
        elif service=='search' and cap.provider!=ProviderName.FIXTURE and intent is not None:
            pairs={market:languages for market,languages in item.market_languages}
            if intent.language not in pairs.get(intent.market,()):
                reasons.append('UNSUPPORTED_MARKET_LANGUAGE_PAIR')
        if service=='contact' and cap.provider!=ProviderName.FIXTURE:
            if not _verified_contact_scope(item):
                reasons.append('CONTACT_SCOPE_UNVERIFIED')
            else:
                scope=item.contact_scope
                if not scope.nonbillable_status or not scope.status_evidence:
                    reasons.append('NONBILLABLE_STATUS_UNVERIFIED')
                if intent is not None and intent.language not in dict(scope.market_languages).get(intent.market,()):
                    reasons.append('UNSUPPORTED_MARKET_LANGUAGE_PAIR')
            if cap.idempotency!='verified' or cap.status!='verified':
                reasons.append('CONTACT_RECONCILIATION_UNVERIFIED')
        return tuple(dict.fromkeys(reasons))

    def search_run_capability(self, *, environment: str) -> dict | None:
        """Read admission planning facts without constructing a tenant-bound adapter."""
        if self.blockers('search',environment=environment):
            return None
        item=self.registration('search')
        if item is None or item.capability.provider not in LIVE_SEARCH_PROVIDERS or not _verified_search_scope(item):
            return None
        cap=item.capability
        # PostgresSearchReceipts binds the capability-only receipt contract. The
        # full registry quote hash additionally binds sandbox/filter evidence.
        receipt_hash=ProviderRegistration(cap,lambda:None).contract_hash
        return {'service':'search','provider':cap.provider,'verified':True,
                'price_version':cap.pricing_version,'verified_filters':sorted(item.verified_filters),
                'markets':sorted(cap.markets),'languages':sorted(cap.languages),'roles':sorted(cap.roles),
                'market_languages':{market:list(languages) for market,languages in item.market_languages},
                'receipt_contract_hash':receipt_hash,'registry_contract_hash':item.contract_hash}

    def model_run_configuration(self, *, market: str, language: str, environment: str) -> dict | None:
        """Read the reviewed native model configuration without constructing an adapter."""
        intent=ProviderIntent('readiness:model', 'model', market, language, 'company')
        if self.blockers('model',environment=environment,intent=intent):
            return None
        item=self.registration('model')
        if item is None or not _verified_model_scope(item):
            return None
        cap=item.capability
        if cap.idempotency!='verified' or cap.status!='verified':
            return None
        return {'capability':cap,'route':item.model_route,'model_id':item.model_id,
                'registry_contract_hash':item.contract_hash,
                'receipt_contract_hash':ProviderRegistration(cap,lambda:None).contract_hash}

    def contact_lookup_configuration(self, *, market: str, language: str, role: str, environment: str) -> dict | None:
        """Read exact reviewed contact facts without constructing an adapter or charging status."""
        intent=ProviderIntent('readiness:contact','contact',market,language,role)
        if self.blockers('contact',environment=environment,intent=intent):
            return None
        item=self.registration('contact')
        if item is None or not _verified_contact_scope(item):
            return None
        cap,scope=item.capability,item.contact_scope
        if (cap.idempotency!='verified' or cap.status!='verified' or not scope.nonbillable_status
            or not scope.status_evidence or language not in dict(scope.market_languages).get(market,())):
            return None
        return {'capability':cap,'scope':scope,'registry_contract_hash':item.contract_hash,
                'receipt_contract_hash':ProviderRegistration(cap,lambda:None).contract_hash}

    def contact_quote_capability(self, *, environment: str) -> ProviderCapability | None:
        """Read a ready contact contract; the quote still validates the exact project scope."""
        item=self.registration('contact')
        if item is None or not _verified_contact_scope(item):
            return None
        market,languages=item.contact_scope.market_languages[0]
        config=self.contact_lookup_configuration(market=market,language=languages[0],
            role=sorted(item.capability.roles)[0],environment=environment)
        return config['capability'] if config is not None else None

    def resolve(self, service: Service, *, environment: str) -> ProviderAdapter:
        reasons = self.blockers(service, environment=environment)
        if reasons:
            raise ProviderUnavailable(reasons)
        item = self.registration(service)
        assert item is not None
        adapter = item.factory()
        if (getattr(adapter,'capability',None) != item.capability
            or not all(callable(getattr(adapter,name,None)) for name in ('estimate','submit','status'))
            or item.capability.provider == ProviderName.FIXTURE and not isinstance(adapter,FixtureProviderAdapter)):
            raise ProviderUnavailable(('ADAPTER_CONTRACT_MISMATCH',))
        if service=='contact' and item.capability.provider!=ProviderName.FIXTURE:
            from .live_contact import LiveContactAdapter
            if (type(adapter) is not LiveContactAdapter
                or adapter.account_reference!=item.contact_scope.account_reference
                or getattr(adapter,'status_nonbillable',None) is not True):
                raise ProviderUnavailable(('ADAPTER_CONTRACT_MISMATCH',))
        return adapter

    def estimate(self, intent: ProviderIntent, *, environment: str, budget: Money | None,
                 quoted_pricing_version: str, quoted_contract_hash: str) -> Money:
        item = self.registration(intent.service)
        reasons = self.blockers(intent.service, environment=environment, intent=intent)
        if reasons:
            raise ProviderUnavailable(reasons)
        assert item is not None
        if quote_requires_reconfirmation(quoted_pricing_version,item.capability) or quoted_contract_hash != item.contract_hash:
            raise ProviderUnavailable(('PRICE_RECONFIRM_REQUIRED',))
        if budget is None:
            raise ProviderUnavailable(('BUDGET_UNVERIFIED',))
        if item.capability.max_liability.amount > budget.amount:
            raise ProviderUnavailable(('BUDGET_EXCEEDED',))
        estimate = self.resolve(intent.service,environment=environment).estimate(intent)
        if not isinstance(estimate,Money) or estimate.amount > item.capability.max_liability.amount or estimate.amount > budget.amount:
            raise ProviderUnavailable(('UNBOUNDED_TARIFF',))
        return estimate


from .activation import environment_registrations  # noqa: E402 - needs the classes above
DEFAULT_REGISTRY = ProviderRegistry(environment_registrations())


def resolve_provider(service: Service, *, environment: str) -> ProviderAdapter:
    return DEFAULT_REGISTRY.resolve(service, environment=environment)


BLOCKER_ACTIONS = {
    'PROVIDER_UNSELECTED': 'Choose a vendor and record its approved versioned contract.',
    'SANDBOX_EVIDENCE_MISSING': 'Verify the approved isolated sandbox with a bounded test allowance.',
    'CONTACT_SCOPE_UNVERIFIED': 'Record the reviewed nonsecret account identifier, exact contact scope and count ceiling.',
    'NONBILLABLE_STATUS_UNVERIFIED': 'Record verified no-charge status evidence before status readiness.',
    'CONTACT_RECONCILIATION_UNVERIFIED': 'Verify original intent idempotency and status semantics before contact admission.',
    'SEARCH_FILTERS_UNVERIFIED': 'Record the account-verified market/language filters and explicit supported pairs.',
    'UNSUPPORTED_MARKET_LANGUAGE_PAIR': 'Use an explicitly verified market/language pair for this account contract.',
    'EVIDENCE_MISSING': 'Record dated official sources and verified contract evidence.',
    'PRICE_UNVERIFIED': 'Confirm the account tariff and exact six-decimal USD liability.',
    'UNKNOWN_STATUS_SEMANTICS': 'Verify status/reconciliation semantics before admitting work.',
    'UNBOUNDED_TARIFF': 'Verify a maximum charge before admitting work.',
    'FIXTURE_IN_PRODUCTION': 'Select a verified real adapter for this environment.',
}


def provider_readiness(service: Service, *, environment: str) -> dict:
    reasons = DEFAULT_REGISTRY.blockers(service,environment=environment)
    return {'status':'blocked' if reasons else 'ready','reason_codes':list(reasons),
            'actions':[BLOCKER_ACTIONS.get(reason,'Resolve the verified provider contract gate.') for reason in reasons]}
