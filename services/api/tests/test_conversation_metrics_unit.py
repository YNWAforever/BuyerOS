"""Unit: metrics window bounds, percentile, boundary parsing and budget split."""
from datetime import datetime, timezone

import pytest

from buyeros_api.services.conversation_metrics import (_budget, _observed_instant,
    percentile, validate_window_days)


@pytest.mark.parametrize('value', [0, 31, -1, 1.5, '7', None, True])
def test_validate_window_days_rejects_non_bounded_values(value):
    with pytest.raises(ValueError):
        validate_window_days(value)
    assert validate_window_days(1) == 1
    assert validate_window_days(30) == 30


def test_percentile_rounds_and_never_invents_a_sample():
    assert percentile([], 0.5) is None
    assert percentile([4], 0.95) == 4
    assert percentile([10, 20], 0.5) == 15
    assert percentile([1, 2, 3, 100], 0.95) == 85


def test_observed_instant_accepts_only_bounded_utc_instants():
    assert _observed_instant('2026-11-11T00:00:01Z') == datetime(
        2026, 11, 11, 0, 0, 1, tzinfo=timezone.utc)
    assert _observed_instant('2026-11-11T00:00:01.250Z') == datetime(
        2026, 11, 11, 0, 0, 1, 250000, tzinfo=timezone.utc)
    assert _observed_instant('2026-11-11T08:00:01+08:00') == datetime(
        2026, 11, 11, 0, 0, 1, tzinfo=timezone.utc)
    for value in (None, '', 'not-an-instant', 42, {'at': 'x'}):
        assert _observed_instant(value) is None


def test_budget_separates_priced_unknown_and_no_cost_proposals():
    rows = [
        ('documents.read', 'proposed', True, None),
        ('documents.read', 'proposed', True,
         {'kind': 'nonbillable', 'amount': 0, 'unit': 'USD', 'known': True}),
        ('xverum.enrich_company', 'proposed', True,
         {'kind': 'provider_credits', 'amount': 0, 'unit': 'credits', 'known': False,
          'may_incur_provider_charges': True}),
        ('xverum.enrich_company', 'proposed', True,
         {'kind': 'provider_credits', 'amount': 0, 'unit': 'credits', 'known': None}),
        ('xverum.enrich_company', 'approved', True,
         {'kind': 'provider_credits', 'amount': '120.5', 'unit': 'credits',
          'known': True, 'may_incur_provider_charges': True}),
        ('research.read', 'proposed', True,
         {'kind': 'provider_credits', 'amount': 2, 'unit': 'USD', 'known': True}),
    ]
    budget = _budget(rows)
    assert budget['priced_proposals'] == 2
    assert budget['unknown_price_proposals'] == 2
    assert budget['no_cost_proposals'] == 2
    assert budget['may_incur_provider_charges'] == 2
    assert budget['estimated'] == [
        {'unit': 'credits', 'amount': '120.5'},
        {'unit': 'USD', 'amount': '2'},
    ]


def test_budget_reports_no_price_rather_than_zero_for_nonbillable_work():
    budget = _budget([('research.read', 'proposed', True,
        {'kind': 'nonbillable', 'amount': 0, 'unit': 'USD', 'known': True})])
    assert budget['priced_proposals'] == 0
    assert budget['unknown_price_proposals'] == 0
    assert budget['no_cost_proposals'] == 1
    assert budget['estimated'] == []
