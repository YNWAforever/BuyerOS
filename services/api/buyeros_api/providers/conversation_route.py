"""Reviewed code-owned conversation model route and disabled-by-default opt-in.

The default discussion binding is ``deepseek-v4.1-flash`` called through the
documented OpenCode Go endpoint using the BuyerOS service-account credential. A
conversation call is possible only when all of these hold:

* an operator explicitly enables this exact workspace/project pair through
  ``BUYEROS_CONVERSATION_MODEL_ENABLED=true`` plus the two id variables, and
  deploys the dedicated ``BUYEROS_CONVERSATION_MODEL_API_KEY`` (never the global
  research provider selector or key);
* one ``ReviewedConversationRoute`` below is pinned to that exact pair and was
  independently reviewed with the code-owned default model/version, tariff upper
  bound, markets/languages, dated Go source URLs, service-account identity,
  retained/expiry terms and expected provider-contract hash;
* the account/model verification is marked complete and any reviewed evidence
  expiry has not passed;
* the rebuilt registration's ``contract_hash`` equals the reviewed hash exactly;
* every pre-existing paid-admission, dispatch, policy, source, budget and receipt
  guard still passes.

``REVIEWED_ROUTES`` binds approval to the exact workspace and project. Model,
pricing and liability come from the reviewed provider contract.
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
DEFAULT_MODEL_ID = 'deepseek-v4.1-flash'
DEFAULT_MODEL_VERSION = 'deepseek-v4.1-flash-1017'
DEFAULT_PRICING_VERSION = 'opencode-go-2026-11-21:deepseek-v4.1-flash-1017'
DEFAULT_AUTH_MODEL = 'service-account bearer key'
DEFAULT_POLICY_ACCOUNT_REFERENCE = 'buyeros-conversation-service-account'
DEFAULT_MARKETS = frozenset({'US'})
REVIEWED_MARKETS = frozenset({'US', 'SG'})
DEFAULT_LANGUAGES = frozenset({'en'})
DEFAULT_VERIFIED_AT = datetime(2026, 11, 21, tzinfo=timezone.utc)
DEFAULT_SOURCE_URLS = (
    'https://opencode.ai/inference/go/v1/models',
    'https://opencode.ai/docs/console/go/#where-can-i-use-it',
    'https://opencode.ai/docs/console/go/#endpoints',
    'https://opencode.ai/docs/console/go/#privacy',
)
DEFAULT_RETENTION = ('0 days; DeepSeek ZDR agreement valid through 2026-11-30; '
    'no training per Go privacy terms')
ACCOUNT_KIND = 'service-account'
# The receipt transition in migration 0057 claims an exact US$0.10 hold.
# Published token cost at the request caps is US$0.0030.
DEFAULT_MAX_LIABILITY = Money(Decimal('0.100000'))
CONVERSATION_ROUTE = ModelRoute(prompt_version=PROMPT_VERSION,
    permitted_tools=frozenset(), max_input_tokens=6000, max_output_tokens=1000,
    deadline_seconds=30, repair_limit=0, route_id=ROUTE_ID)
ROUTE = CONVERSATION_ROUTE
# Actual conversation-schema tests, not the fit-policy sandbox evidence.
CONVERSATION_TEST_EVIDENCE = (
    'services/api/tests/test_conversation_admission_db.py',
    'services/api/tests/test_discussion_context_recall.py',
    'services/api/tests/test_conversation_route_registration.py',
    'services/api/tests/test_conversation_model.py',
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
    contract_sha256: str
    account_verified: bool = False
    model_id: str = DEFAULT_MODEL_ID
    pricing_version: str = DEFAULT_PRICING_VERSION
    policy_account_reference: str = DEFAULT_POLICY_ACCOUNT_REFERENCE
    max_liability: Money = DEFAULT_MAX_LIABILITY
    markets: frozenset[str] = DEFAULT_MARKETS
    languages: frozenset[str] = DEFAULT_LANGUAGES
    verified_at: datetime = DEFAULT_VERIFIED_AT
    source_urls: tuple[str, ...] = DEFAULT_SOURCE_URLS
    retention: str = DEFAULT_RETENTION
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
                or self.model_id != DEFAULT_MODEL_ID
                or not isinstance(self.pricing_version, str)
                or _PRICING_VERSION.fullmatch(self.pricing_version) is None
                or self.pricing_version != DEFAULT_PRICING_VERSION
                or not isinstance(self.policy_account_reference, str)
                or _ACCOUNT.fullmatch(self.policy_account_reference) is None
                or self.policy_account_reference != DEFAULT_POLICY_ACCOUNT_REFERENCE):
            raise ValueError('code-owned default conversation model/pricing/account facts required')
        if (not isinstance(self.max_liability, Money)
                or self.max_liability != DEFAULT_MAX_LIABILITY):
            raise ValueError('reviewed bounded conversation liability required')
        if (not isinstance(self.markets, frozenset) or not self.markets
                or not self.markets <= REVIEWED_MARKETS
                or not isinstance(self.languages, frozenset) or self.languages != DEFAULT_LANGUAGES):
            raise ValueError('reviewed exact market/language subset required')
        if (not isinstance(self.verified_at, datetime) or self.verified_at.tzinfo is None
                or self.verified_at != DEFAULT_VERIFIED_AT
                or not isinstance(self.source_urls, tuple)
                or self.source_urls != DEFAULT_SOURCE_URLS):
            raise ValueError('dated vendor source URLs required')
        if not isinstance(self.contract_sha256, str) or _SHA256.fullmatch(self.contract_sha256) is None:
            raise ValueError('independently reviewed contract hash required')
        if not isinstance(self.retention, str) or self.retention != DEFAULT_RETENTION:
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


# Isolated synthetic QA workspace and project for the owner-authorized recall test.
# Vendor pricing and privacy evidence are reviewed through the QA window.
REVIEWED_ROUTES: tuple[ReviewedConversationRoute, ...] = (
    ReviewedConversationRoute(
        workspace_id='064d5168-709b-57e7-a7c3-871c2f16c814',
        project_id='bd632836-3298-58de-aa85-59213cb28ab2',
        contract_sha256='db688dbde21a126e376952397c74a3305052486e40db27f61fdb3ef02569ead1',
        account_verified=True,
        markets=frozenset({'SG'}),
        evidence_expires_at=datetime(2026, 11, 25, tzinfo=timezone.utc),
    ),
)


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
    from .opencode_model import CONVERSATION_ENDPOINT
    capability = ProviderCapability(
        provider=PROVIDER, adapter_version=ADAPTER_VERSION, service='model',
        markets=facts.markets, languages=facts.languages, roles=frozenset({'company'}),
        auth_model=DEFAULT_AUTH_MODEL, pricing_version=facts.pricing_version,
        max_liability=facts.max_liability, idempotency='verified', status='verified',
        callback='unsupported', cancel='unsupported',
        retention=facts.retention,
        verified_at=facts.verified_at, source_urls=facts.source_urls,
        endpoint=CONVERSATION_ENDPOINT)

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
