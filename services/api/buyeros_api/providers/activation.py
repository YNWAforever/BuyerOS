"""Code-owned Exa search + Claude model registrations, enabled by deployed credentials.

Nothing registers unless the server-only key for that vendor is present, so test
and CI environments keep an empty registry. Every call still passes the existing
gates: approved profile, account research policy, approved budget, a durable
receipt claim before the vendor await, and BUYEROS_PAID_DISPATCH_ENABLED.

Prices are bounded upper liabilities from the vendors' published rates on the
verification date; re-verify and bump pricing_version when a tariff changes.
"""
from __future__ import annotations
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from .base import Money, ProviderCapability

VERIFIED_AT = datetime(2026, 10, 13, tzinfo=timezone.utc)
CONTRACT_TESTS = ('services/api/tests/test_exa_anthropic_providers.py',)
DEFAULT_MARKETS = 'HK,SG,TW,JP,KR,AU,NZ,US,CA,GB,IE,DE,FR,NL,BE,CH,AT,SE,DK,NO,FI,ES,IT,PL,AE'
# Exa has a market filter (userLocation) but no language filter. Only English is
# admitted, so the frozen language filter is never claimed for other languages.
SEARCH_LANGUAGES = ('en',)
# auto search with 20 results ($0.017) + 20 text pages ($0.020) = $0.037 per call.
EXA_MAX_LIABILITY = Money(Decimal('0.040000'))
# 20k input tokens at $4/M + 4k output tokens at $20/M = $0.16 per fit proposal.
CLAUDE_MAX_LIABILITY = Money(Decimal('0.160000'))


def _markets() -> frozenset[str]:
    raw = os.environ.get('BUYEROS_RESEARCH_MARKETS', DEFAULT_MARKETS)
    markets = frozenset(code.strip().upper() for code in raw.split(',') if code.strip())
    if not 1 <= len(markets) <= 64 or any(re.fullmatch(r'[A-Z]{2}', code) is None for code in markets):
        raise ValueError('BUYEROS_RESEARCH_MARKETS must list 1-64 two-letter country codes')
    return markets


class _UnscopedEngine:
    """Factory-time placeholder; the worker rescopes receipts to its tenant engine before use."""
    def __getattr__(self, name):
        raise RuntimeError('provider receipts must be rescoped to a tenant engine before use')


def _exa_registration(api_key: str, markets: frozenset[str]):
    from .registry import ProviderRegistration

    capability = ProviderCapability(
        provider='exa-search', adapter_version='exa-search.v1', service='search',
        markets=markets, languages=frozenset(SEARCH_LANGUAGES), roles=frozenset({'company'}),
        auth_model='server-only x-api-key', pricing_version='exa-2026-10-13:auto-20-text',
        max_liability=EXA_MAX_LIABILITY,
        # The durable receipt claim precedes the vendor await and is never reset, so
        # a call is submitted at most once; status reads the local receipt only.
        idempotency='verified', status='verified', callback='unsupported', cancel='unsupported',
        retention='search metadata retained per BuyerOS receipt retention policy',
        verified_at=VERIFIED_AT,
        source_urls=('https://exa.ai/docs/reference/search', 'https://exa.ai/pricing'))

    def factory():
        import httpx
        from .exa_search import ExaSearchClient
        from .live_search import LiveSearchAdapter
        client = ExaSearchClient(api_key=api_key, http=httpx.AsyncClient())
        # Receipts are bound per tenant by execute_live_run_search before any call.
        return LiveSearchAdapter(capability=capability, client=client, receipts=None)

    return ProviderRegistration(
        capability, factory, sandbox_evidence=CONTRACT_TESTS,
        verified_filters=frozenset({'market', 'language'}),
        market_languages=tuple((market, SEARCH_LANGUAGES) for market in sorted(markets)))


def _claude_registration(api_key: str, markets: frozenset[str]):
    from .model import ModelRoute
    from .registry import ProviderRegistration
    from .anthropic_model import DEFAULT_MODEL_ID

    model_id = os.environ.get('BUYEROS_ANTHROPIC_MODEL', DEFAULT_MODEL_ID)
    route = ModelRoute(prompt_version='fit-proposal.v1', permitted_tools=frozenset(),
                       max_input_tokens=20000, max_output_tokens=4000, deadline_seconds=60,
                       repair_limit=0, route_id='anthropic-fit.v1')
    capability = ProviderCapability(
        provider='anthropic-messages', adapter_version='anthropic-messages.v1', service='model',
        markets=markets, languages=frozenset(SEARCH_LANGUAGES), roles=frozenset({'company'}),
        auth_model='server-only x-api-key', pricing_version=f'anthropic-2026-10-13:{model_id}',
        max_liability=CLAUDE_MAX_LIABILITY,
        idempotency='verified', status='verified', callback='unsupported', cancel='unsupported',
        retention='no prompt or response storage beyond BuyerOS model receipts',
        verified_at=VERIFIED_AT,
        source_urls=('https://platform.claude.com/docs/en/build-with-claude/structured-outputs',
                     'https://www.anthropic.com/pricing#api'))

    def factory():
        from .anthropic_model import AnthropicModelClient
        from .live_model import LiveModelAdapter
        from .model_receipts import PostgresModelReceipts
        client = AnthropicModelClient(api_key=api_key, model_id=model_id)
        receipts = PostgresModelReceipts(_UnscopedEngine(), uuid.UUID(int=0), capability,
                                         model_id=model_id, route=route)
        return LiveModelAdapter(capability=capability, client=client, receipts=receipts)

    return ProviderRegistration(capability, factory, sandbox_evidence=CONTRACT_TESTS,
                                model_route=route, model_id=model_id)


def environment_registrations() -> tuple:
    exa_key = os.environ.get('BUYEROS_EXA_API_KEY')
    anthropic_key = os.environ.get('BUYEROS_ANTHROPIC_API_KEY')
    if not exa_key and not anthropic_key:
        return ()
    markets = _markets()
    registrations = []
    if exa_key:
        registrations.append(_exa_registration(exa_key, markets))
    if anthropic_key:
        registrations.append(_claude_registration(anthropic_key, markets))
    return tuple(registrations)
