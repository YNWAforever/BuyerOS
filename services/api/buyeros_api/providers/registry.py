"""Versioned code-owned provider registry. No live provider is selected."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable
from .base import (FixtureProviderAdapter, Money, ProviderAdapter, ProviderCapability,
                   ProviderIntent, Service, SELECTED_LIVE_PROVIDERS, activation_blockers, quote_requires_reconfirmation)
from ..api.errors import ApiError


class ProviderName(StrEnum):
    FIXTURE = 'fixture'
    BRAVE_SEARCH = 'brave-search'
    OPENAI_RESPONSES = 'openai-responses'
    HUNTER = 'hunter'


class ProviderUnavailable(ApiError):
    def __init__(self, reasons: tuple[str, ...]):
        super().__init__(503, 'CAPABILITY_BLOCKED', 'provider capability is not ready')
        self.reasons = reasons


@dataclass(frozen=True)
class ProviderRegistration:
    capability: ProviderCapability
    factory: Callable[[], ProviderAdapter]
    sandbox_evidence: tuple[str, ...] = ()

    def __post_init__(self):
        ProviderName(self.capability.provider)

    def snapshot(self) -> dict:
        cap = self.capability
        return {'provider': cap.provider, 'adapter_version': cap.adapter_version,
                'service': cap.service, 'auth_model': cap.auth_model,
                'markets': sorted(cap.markets), 'languages': sorted(cap.languages),
                'roles': sorted(cap.roles), 'pricing_version': cap.pricing_version,
                'max_liability_usd': format(cap.max_liability.amount, '.6f') if cap.max_liability else None,
                'idempotency': cap.idempotency, 'status': cap.status,
                'callback': cap.callback, 'cancel': cap.cancel, 'retention': cap.retention,
                'verified_at': cap.verified_at.isoformat() if cap.verified_at else None,
                'source_urls': list(cap.source_urls), 'sandbox_evidence': list(self.sandbox_evidence)}

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
                         role=intent.role if intent else 'company', environment=environment))
        if cap.provider != ProviderName.FIXTURE and cap.provider not in SELECTED_LIVE_PROVIDERS:
            reasons.append('PROVIDER_UNSELECTED')
        if not item.sandbox_evidence:
            reasons.append('SANDBOX_EVIDENCE_MISSING')
        return tuple(dict.fromkeys(reasons))

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


DEFAULT_REGISTRY = ProviderRegistry()


def resolve_provider(service: Service, *, environment: str) -> ProviderAdapter:
    return DEFAULT_REGISTRY.resolve(service, environment=environment)


BLOCKER_ACTIONS = {
    'PROVIDER_UNSELECTED': 'Choose a vendor and record its approved versioned contract.',
    'SANDBOX_EVIDENCE_MISSING': 'Verify the approved isolated sandbox with a bounded test allowance.',
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
