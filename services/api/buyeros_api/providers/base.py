"""Provider-neutral, fixture-first capability boundary. No live adapter is selected."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

Service = Literal["search", "model", "contact"]
Support = Literal["verified", "unsupported", "unknown"]
SubmissionState = Literal["accepted", "unknown", "rejected"]
StatusState = Literal["accepted", "pending", "unknown", "succeeded", "not_found", "failed"]
_QUANTUM = Decimal("0.000001")
# No real vendor has been selected and verified for this repository.
SELECTED_LIVE_PROVIDERS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Literal["USD"] = "USD"

    def __post_init__(self) -> None:
        if isinstance(self.amount, bool) or not isinstance(self.amount, Decimal):
            raise ValueError("money must be a Decimal")
        if self.currency != "USD" or not self.amount.is_finite() or self.amount < 0 or self.amount > Decimal("99999999999999.999999"):
            raise ValueError("money must be nonnegative USD within NUMERIC(20,6)")
        if self.amount != self.amount.quantize(_QUANTUM):
            raise ValueError("money must be exact to six places")


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    adapter_version: str
    service: Service
    markets: frozenset[str]
    languages: frozenset[str]
    roles: frozenset[str]
    auth_model: str
    pricing_version: str
    max_liability: Money | None
    idempotency: Support
    status: Support
    callback: Support
    cancel: Support
    retention: str
    verified_at: datetime | None
    source_urls: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.service not in {"search", "model", "contact"}:
            raise ValueError("unsupported service")
        if any(value not in {"verified", "unsupported", "unknown"} for value in
               (self.idempotency, self.status, self.callback, self.cancel)):
            raise ValueError("unsupported capability evidence state")


@dataclass(frozen=True)
class ProviderIntent:
    key: str
    service: Service
    market: str
    language: str
    role: str

    def __post_init__(self) -> None:
        if not self.key or len(self.key) > 200:
            raise ValueError("stable provider intent key required")


@dataclass(frozen=True)
class SubmissionResult:
    state: SubmissionState
    provider_ref: str | None
    observed_usage: Decimal | None = None
    redacted_digest: str | None = None


@dataclass(frozen=True)
class StatusResult:
    state: StatusState
    provider_ref: str
    observed_usage: Decimal | None = None
    redacted_digest: str | None = None
    event_id: str | None = None


class ProviderAdapter(Protocol):
    capability: ProviderCapability

    def estimate(self, request: ProviderIntent) -> Money: ...
    async def submit(self, intent: ProviderIntent) -> SubmissionResult: ...
    async def status(self, provider_ref: str) -> StatusResult: ...


def activation_blockers(capability: ProviderCapability, *, market: str, language: str,
                        role: str, environment: str = "production") -> tuple[str, ...]:
    """Fail closed for evidence or safety gaps; each service is evaluated separately."""
    blockers: list[str] = []
    if environment not in {"test", "staging", "production"}:
        blockers.append("UNKNOWN_ENVIRONMENT")
    if (capability.provider != "fixture" or environment != "test") and capability.provider not in SELECTED_LIVE_PROVIDERS:
        blockers.append("PROVIDER_UNSELECTED")
    if capability.provider == "fixture" and environment != "test":
        blockers.append("FIXTURE_IN_PRODUCTION")
    if market not in capability.markets:
        blockers.append("UNSUPPORTED_MARKET")
    if language not in capability.languages:
        blockers.append("UNSUPPORTED_LANGUAGE")
    if role not in capability.roles:
        blockers.append("UNSUPPORTED_ROLE")
    if capability.max_liability is None or capability.max_liability.amount <= 0:
        blockers.append("UNBOUNDED_TARIFF")
    if not capability.pricing_version:
        blockers.append("PRICE_UNVERIFIED")
    if capability.status == "unknown":
        blockers.append("UNKNOWN_STATUS_SEMANTICS")
    if capability.idempotency != "verified" and capability.status != "verified":
        blockers.append("NO_SAFE_RECONCILIATION")
    if capability.verified_at is None or capability.verified_at.tzinfo is None or not capability.source_urls:
        blockers.append("EVIDENCE_MISSING")
    if not capability.adapter_version or not capability.auth_model or not capability.retention:
        blockers.append("CONTRACT_INCOMPLETE")
    return tuple(blockers)


def quote_requires_reconfirmation(quoted_pricing_version: str, capability: ProviderCapability) -> bool:
    return not quoted_pricing_version or quoted_pricing_version != capability.pricing_version


class FixtureProviderAdapter:
    """Synthetic acceptance/timeout fixture only. It has no HTTP transport or credentials."""
    test_only = True
    status_nonbillable = True

    def __init__(self, capability: ProviderCapability, *, environment: str = "production",
                 outcome: str = "accepted"):
        if environment != "test":
            raise RuntimeError("fixture adapter is test-only")
        if capability.provider != "fixture":
            raise ValueError("fixture adapter requires fixture capability")
        if outcome not in {"accepted", "timeout_after_acceptance", "rejected"}:
            raise ValueError("unknown fixture outcome")
        self.capability = capability
        self.outcome = outcome
        self.submit_count = 0
        self._by_key: dict[str, SubmissionResult] = {}
        self._states: dict[str, StatusResult] = {}

    def estimate(self, request: ProviderIntent) -> Money:
        if request.service != self.capability.service:
            raise ValueError("intent service differs from capability")
        if activation_blockers(self.capability, market=request.market, language=request.language,
                               role=request.role, environment="test"):
            raise ValueError("fixture capability blocked")
        assert self.capability.max_liability is not None
        return self.capability.max_liability

    async def submit(self, intent: ProviderIntent) -> SubmissionResult:
        self.estimate(intent)
        if intent.key in self._by_key:
            return self._by_key[intent.key]
        self.submit_count += 1
        digest = hashlib.sha256(intent.key.encode("utf-8")).hexdigest()
        ref = f"fixture:{digest[:24]}"
        state: SubmissionState = ("unknown" if self.outcome == "timeout_after_acceptance"
                                  else "rejected" if self.outcome == "rejected" else "accepted")
        result = SubmissionResult(state, ref if state != "rejected" else None,
                                  redacted_digest=digest)
        self._by_key[intent.key] = result
        if result.provider_ref:
            self._states[result.provider_ref] = StatusResult(
                "unknown" if state == "unknown" else "accepted", result.provider_ref,
                redacted_digest=digest)
        return result

    async def status(self, provider_ref: str) -> StatusResult:
        return self._states[provider_ref]

    def resolve(self, provider_ref: str, state: StatusState, *,
                observed_usage: Decimal | None = None) -> None:
        if provider_ref not in self._states:
            raise KeyError(provider_ref)
        previous = self._states[provider_ref]
        self._states[provider_ref] = StatusResult(state, provider_ref, observed_usage,
                                                  previous.redacted_digest,
                                                  f"fixture-status:{provider_ref}:{state}")
