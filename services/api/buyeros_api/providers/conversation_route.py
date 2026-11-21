"""Reviewed code-owned conversation model route and disabled-by-default opt-in.

A conversation call is possible only when all of these hold:

* an operator explicitly enables this exact workspace/project pair through
  ``BUYEROS_CONVERSATION_MODEL_ENABLED=true`` plus the two id variables, and
  deploys the dedicated ``BUYEROS_CONVERSATION_MODEL_API_KEY`` (never the global
  research provider selector or key);
* one ``ReviewedConversationRoute`` below is pinned to that exact pair and was
  independently reviewed with the vendor model, tariff upper bound, supported
  markets/languages, dated source URLs, conversation policy account reference,
  retained/expiry terms and expected provider-contract hash;
* the account/model verification is marked complete and any reviewed evidence
  expiry has not passed;
* the rebuilt registration's ``contract_hash`` equals the reviewed hash exactly;
* every pre-existing paid-admission, dispatch, policy, source, budget and receipt
  guard still passes.

``REVIEWED_ROUTES`` is empty in this repository. It is intentionally populated
only by a reviewed owner change with real vendor facts; an arbitrary environment
model id, pricing string or liability value is never trusted or marked verified.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .base import Money, ProviderCapability
from .model import ModelRoute
from .registry import ProviderRegistration

ENABLED_ENV = 'BUYEROS_CONVERSATION_MODEL_ENABLED'
WORKSPACE_ENV = 'BUYEROS_CONVERSATION_MODEL_WORKSPACE_ID'
PROJECT_ENV = 'BUYEROS_CONVERSATION_MODEL_PROJECT_ID'
# Deliberately distinct from BUYEROS_OPENCODE_API_KEY: applying the conversation
# credential must not select or run any unrelated research/model operation.
CREDENTIAL_ENV = 'BUYEROS_CONVERSATION_MODEL_API_KEY'

PROVIDER = 'opencode-go'
ADAPTER_VERSION = 'opencode-go-conversation.v1'
ROUTE_ID = 'opencode-go-conversation.v1'
PROMPT_VERSION = 'conversation-grounded.v1'
CONVERSATION_ROUTE = ModelRoute(prompt_version=PROMPT_VERSION,
    permitted_tools=frozenset(), max_input_tokens=6000, max_output_tokens=1000,
    deadline_seconds=30, repair_limit=0, route_id=ROUTE_ID)
ROUTE = CONVERSATION_ROUTE
# Actual conversation-schema tests, not the fit-policy sandbox evidence.
CONVERSATION_TEST_EVIDENCE = (
    'services/api/tests/test_conversation_admission_db.py',
    'services/api/tests/test_discussion_context_recall.py',
    'services/api/tests/test_conversation_route_registration.py',
)
MAX_QA_CALL_LIABILITY = Money(Decimal('1.000000'))
_ACCOUNT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z')
_MODEL_ID = re.compile(r'[A-Za-z0-9._:-]{1,128}\Z')
_PRICING_VERSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z')
_SHA256 = re.compile(r'[a-f0-9]{64}\Z')
_MARKET = re.compile(r'[A-Z]{2}\Z')
_LANGUAGE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,63}\Z')


@dataclass(frozen=True)
class ReviewedConversationRoute:
    """An independently reviewed, exact conversation/model/account scope.

    No field is derived from the request or from an arbitrary environment value.
    ``contract_sha256`` is the separately reviewed expected ``ProviderRegistration``
    contract hash, so a policy binding cannot be approved from a hash this code
    would simply compute and then trust.
    """
    workspace_id: str
    project_id: str
    model_id: str
    pricing_version: str
    policy_account_reference: str
    max_liability: Money
    markets: frozenset[str]
    languages: frozenset[str]
    verified_at: datetime
    source_urls: tuple[str, ...]
    contract_sha256: str
    retention: str
    account_verified: bool = False
    evidence_expires_at: datetime | None = None
    evidence: tuple[str, ...] = CONVERSATION_TEST_EVIDENCE

    def __post_init__(self):
        try:
            workspace = uuid.UUID(self.workspace_id)
            project = uuid.UUID(self.project_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError('reviewed conversation workspace/project required') from error
        if str(workspace) != self.workspace_id or str(project) != self.project_id:
            raise ValueError('canonical reviewed conversation scope required')
        if (not isinstance(self.model_id, str) or _MODEL_ID.fullmatch(self.model_id) is None
                or not isinstance(self.pricing_version, str)
                or _PRICING_VERSION.fullmatch(self.pricing_version) is None
                or not isinstance(self.policy_account_reference, str)
                or _ACCOUNT.fullmatch(self.policy_account_reference) is None):
            raise ValueError('reviewed conversation model/pricing/account facts required')
        if (not isinstance(self.max_liability, Money)
                or not Decimal(0) < self.max_liability.amount <= MAX_QA_CALL_LIABILITY.amount):
            raise ValueError('reviewed bounded conversation liability required')
        if (not isinstance(self.markets, frozenset) or not 1 <= len(self.markets) <= 64
                or any(not isinstance(item, str) or _MARKET.fullmatch(item) is None for item in self.markets)
                or not isinstance(self.languages, frozenset) or not 1 <= len(self.languages) <= 64
                or any(not isinstance(item, str) or _LANGUAGE.fullmatch(item) is None for item in self.languages)):
            raise ValueError('reviewed provider market/language facts required')
        if (not isinstance(self.verified_at, datetime) or self.verified_at.tzinfo is None
                or not isinstance(self.source_urls, tuple) or not 1 <= len(self.source_urls) <= 20
                or any(not isinstance(url, str) or not url.startswith('https://') or len(url) > 500
                       for url in self.source_urls)):
            raise ValueError('dated vendor source URLs required')
        if not isinstance(self.contract_sha256, str) or _SHA256.fullmatch(self.contract_sha256) is None:
            raise ValueError('independently reviewed contract hash required')
        if (not isinstance(self.retention, str) or not 1 <= len(self.retention) <= 500
                or any(ord(character) < 32 for character in self.retention)):
            raise ValueError('reviewed provider retention terms required')
        if self.evidence_expires_at is not None and (
                not isinstance(self.evidence_expires_at, datetime)
                or self.evidence_expires_at.tzinfo is None):
            raise ValueError('aware reviewed evidence expiry required')
        if type(self.account_verified) is not bool:
            raise ValueError('explicit account verification state required')
        if (not isinstance(self.evidence, tuple) or not self.evidence
                or any(not isinstance(path, str) or not path.startswith('services/api/tests/')
                       or not path.endswith('.py') for path in self.evidence)):
            raise ValueError('actual conversation contract tests required')


# Deliberately empty until an owner records real vendor facts and their exact
# independently reviewed contract hash. Do not infer an entry from deployment
# environment or credentials.
REVIEWED_ROUTES: tuple[ReviewedConversationRoute, ...] = ()


def _canonical_uuid(value) -> str | None:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError):
        return None
    return str(parsed) if str(parsed) == value else None


def credential_present(env=None) -> bool:
    """Whether a dedicated conversation credential is deployed; the value is never read.

    This is intentionally not ``BUYEROS_OPENCODE_API_KEY``. The caller may only
    learn that a nonempty credential is present; selection cannot turn on research.
    """
    env = os.environ if env is None else env
    value = env.get(CREDENTIAL_ENV)
    return isinstance(value, str) and bool(value)


def reviewed_scope(env=None) -> tuple[str, str] | None:
    """The single exact workspace/project opt-in pair, or None when disabled/malformed."""
    env = os.environ if env is None else env
    if env.get(ENABLED_ENV) != 'true':
        return None
    workspace = _canonical_uuid(env.get(WORKSPACE_ENV))
    project = _canonical_uuid(env.get(PROJECT_ENV))
    if workspace is None or project is None:
        return None
    return workspace, project


def opted_in(workspace_id, project_id, env=None) -> bool:
    """Whether this exact workspace/project pair is enabled, before fact/account checks."""
    scope = reviewed_scope(env)
    if scope is None:
        return False
    try:
        return scope == (str(uuid.UUID(str(workspace_id))), str(uuid.UUID(str(project_id))))
    except (AttributeError, TypeError, ValueError):
        return False


def registration_for_facts(facts: ReviewedConversationRoute) -> ProviderRegistration:
    """Build the registration whose hash must equal the reviewed hash.

    Used by preflight and tests; callers must compare ``contract_hash`` to
    ``facts.contract_sha256`` and never treat this object as verified by itself.
    """
    capability = ProviderCapability(
        provider=PROVIDER, adapter_version=ADAPTER_VERSION, service='model',
        markets=facts.markets, languages=facts.languages, roles=frozenset({'company'}),
        auth_model='server-only bearer key', pricing_version=facts.pricing_version,
        max_liability=facts.max_liability, idempotency='verified', status='verified',
        callback='unsupported', cancel='unsupported',
        retention=facts.retention,
        verified_at=facts.verified_at, source_urls=facts.source_urls)

    def factory():
        # Admission owns the receipt-bound OpenCode client; a registry-resolved
        # adapter would bypass the conversation operation/outbox contract.
        raise RuntimeError('conversation model calls require conversation admission')

    return ProviderRegistration(capability, factory, sandbox_evidence=facts.evidence,
        model_route=CONVERSATION_ROUTE, model_id=facts.model_id,
        policy_account_reference=facts.policy_account_reference)


def _facts_for(scope: tuple[str, str]) -> ReviewedConversationRoute | None:
    seen = set()
    found = None
    for facts in REVIEWED_ROUTES:
        key = (facts.workspace_id, facts.project_id)
        if key in seen:
            raise ValueError('duplicate reviewed conversation scope')
        seen.add(key)
        if key == scope:
            found = facts
    return found


def preflight(env=None) -> ProviderRegistration | None:
    """Read protected configuration and prove its hash before any provider path.

    Returns None for disabled, unverified, missing, malformed or mismatched
    configuration. It checks only whether the dedicated conversation credential
    is present; it never logs, returns or otherwise inspects its value, reserves
    budget or contacts a provider, and it cannot turn an arbitrary env model
    id/pricing into verified capability facts.
    """
    scope = reviewed_scope(env)
    if scope is None or not credential_present(env):
        return None
    try:
        facts = _facts_for(scope)
        if facts is None or facts.account_verified is not True:
            return None
        if (facts.evidence_expires_at is not None
                and facts.evidence_expires_at <= datetime.now(timezone.utc)):
            return None
        registration = registration_for_facts(facts)
        if registration.contract_hash != facts.contract_sha256:
            return None
    except (TypeError, ValueError):
        return None
    return registration


def conversation_registration(env=None) -> ProviderRegistration | None:
    """The exact reviewed conversation registration, or absent (fail closed)."""
    return preflight(env)
