"""T14: provider activation requires evidence, bounded liability and safe unknown semantics."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from buyeros_api.providers.base import (
    Money, ProviderCapability, ProviderIntent, FixtureProviderAdapter,
    activation_blockers, quote_requires_reconfirmation,
)
from buyeros_api.providers.model import ModelRoute
from buyeros_api.services.provider_op import transition, should_hold


def capability(service="search", **changes):
    values = dict(
        provider="fixture", adapter_version="fixture-v1", service=service,
        markets=frozenset({"HK"}), languages=frozenset({"en"}),
        roles=frozenset({"company"}), auth_model="test-only",
        pricing_version="fixture-price-v1", max_liability=Money(Decimal("1.000000")),
        idempotency="verified", status="verified", callback="unsupported",
        cancel="unsupported", retention="test-only",
        verified_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
        source_urls=("https://example.test/fixture-contract",),
    )
    values.update(changes)
    return ProviderCapability(**values)


def test_activation_rejects_unsupported_market_role_and_unbounded_tariff():
    cap = capability(provider="candidate")
    assert "UNSUPPORTED_MARKET" in activation_blockers(cap, market="DE", language="en", role="company")
    assert "UNSUPPORTED_ROLE" in activation_blockers(cap, market="HK", language="en", role="person")
    assert "UNBOUNDED_TARIFF" in activation_blockers(
        capability(provider="candidate", max_liability=None), market="HK", language="en", role="company")


def test_unknown_semantics_and_fixture_production_selection_are_blocked_independently():
    for service in ("search", "model", "contact"):
        cap = capability(service, provider="candidate", status="unknown")
        assert "UNKNOWN_STATUS_SEMANTICS" in activation_blockers(cap, market="HK", language="en", role="company")
        assert "FIXTURE_IN_PRODUCTION" in activation_blockers(
            capability(service), market="HK", language="en", role="company", environment="production")
    assert activation_blockers(capability(), market="HK", language="en", role="company", environment="test") == ()


def test_price_change_requires_exact_quote_reconfirmation():
    assert quote_requires_reconfirmation("fixture-price-v1", capability(pricing_version="fixture-price-v2"))
    assert not quote_requires_reconfirmation("fixture-price-v1", capability())


@pytest.mark.asyncio
async def test_timeout_after_acceptance_remains_unknown_and_duplicate_intent_does_not_submit_twice():
    adapter = FixtureProviderAdapter(capability("contact"), environment="test", outcome="timeout_after_acceptance")
    intent = ProviderIntent(key="contact:quote-1:buyer-1", service="contact",
                            market="HK", language="en", role="company")
    assert adapter.estimate(intent) == Money(Decimal("1.000000"))
    first = await adapter.submit(intent)
    again = await adapter.submit(intent)
    assert first == again
    assert first.state == "unknown"
    assert first.provider_ref
    assert adapter.submit_count == 1
    assert should_hold(transition("submitting", first.state))
    assert (await adapter.status(first.provider_ref)).state == "unknown"


def test_model_route_has_fixed_tools_tokens_deadline_and_repair_bound():
    route = ModelRoute(prompt_version="query-plan.v1", permitted_tools=frozenset(),
                       max_input_tokens=2000, max_output_tokens=500,
                       deadline_seconds=30, repair_limit=1)
    assert route.permitted_tools == frozenset()
    with pytest.raises(ValueError):
        ModelRoute(prompt_version="query-plan.v1", permitted_tools=frozenset({"send_email"}),
                   max_input_tokens=2000, max_output_tokens=500,
                   deadline_seconds=30, repair_limit=1)


def test_capabilities_are_independent_by_service_and_real_provider_selection():
    from buyeros_api.providers.model import model_activation_blockers
    from buyeros_api.providers.contact import contact_activation_blockers
    search = capability("search")
    model = capability("model")
    contact = capability("contact", status="unsupported", idempotency="unknown")
    route = ModelRoute(prompt_version="query-plan.v1", permitted_tools=frozenset(),
                       max_input_tokens=2000, max_output_tokens=500,
                       deadline_seconds=30, repair_limit=1)
    assert activation_blockers(search, market="HK", language="en", role="company",
                               environment="test") == ()
    assert "MODEL_ROUTE_UNSELECTED" in model_activation_blockers(
        model, route, market="HK", language="en")
    assert "NO_SAFE_RECONCILIATION" in contact_activation_blockers(
        contact, market="HK", language="en", role="company")
    assert "PROVIDER_UNSELECTED" in activation_blockers(
        capability(provider="candidate"), market="HK", language="en", role="company")


def test_duplicate_fixture_provider_reference_settles_one_economic_event(seeded):
    import asyncio
    import uuid

    import psycopg

    from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
    from buyeros_api.services.settlement import settle_operation
    from tests.test_budget_rollover_db import _run, SEPTEMBER
    from tests.test_buyer_review_db import PROJECT_A, WORKSPACE_A

    workspace_id, project_id, operation_id = map(uuid.UUID, (WORKSPACE_A, PROJECT_A, str(uuid.uuid4())))
    scope = {"workspace_id": workspace_id, "project_id": project_id, "category": "discovery"}
    _run(seeded, lambda session: ensure_period_accounts(
        session, workspace_id, project_id, None, "discovery", at=SEPTEMBER))
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("UPDATE budget_accounts SET approved_limit=2 WHERE workspace_id=%s",
                     (WORKSPACE_A,))
    _run(seeded, lambda session: reserve_operation(
        session, operation_id, scope, Decimal("1.000000"), "USD", "fixture-price-v1", at=SEPTEMBER))
    adapter = FixtureProviderAdapter(capability(), environment="test")
    intent = ProviderIntent(key=f"search:{operation_id}", service="search",
                            market="HK", language="en", role="company")
    first = asyncio.run(adapter.submit(intent))
    duplicate = asyncio.run(adapter.submit(intent))
    assert first.provider_ref == duplicate.provider_ref
    event_id = f"{first.provider_ref}:charge"
    settled = _run(seeded, lambda session: settle_operation(
        session, operation_id, Decimal("0.750000"), event_id))
    replay = _run(seeded, lambda session: settle_operation(
        session, operation_id, Decimal("0.750000"), event_id))
    assert not settled["replayed"] and replay["replayed"]
    with psycopg.connect(seeded) as conn:
        assert conn.execute("SELECT count(*) FROM cost_events WHERE operation_id=%s",
                            (operation_id,)).fetchone()[0] == 1


def test_fixture_adapter_cannot_be_constructed_in_default_production_configuration():
    with pytest.raises(RuntimeError, match="test-only"):
        FixtureProviderAdapter(capability())


def test_provider_money_rejects_float_excess_precision_and_unsupported_currency():
    for amount, currency in ((1.0, "USD"), (Decimal("1.0000001"), "USD"),
                             (Decimal("1.000000"), "EUR"),
                             (Decimal("100000000000000.000000"), "USD")):
        with pytest.raises(ValueError):
            Money(amount, currency)


def test_unselected_live_provider_is_blocked_even_in_test_mode():
    # The execution core also uses this gate directly, without a registry.
    reasons = activation_blockers(capability(provider="candidate"), market="HK",
                                  language="en", role="company", environment="test")
    assert "PROVIDER_UNSELECTED" in reasons


def test_unknown_environment_is_not_a_provider_activation_path():
    reasons = activation_blockers(capability(), market="HK", language="en",
                                  role="company", environment="typo")
    assert "UNKNOWN_ENVIRONMENT" in reasons
