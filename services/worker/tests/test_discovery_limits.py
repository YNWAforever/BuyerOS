"""T18 cumulative hard ceilings across rounds, retries and restart state."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json

import pytest

from buyeros_api.services.run_usage import UsageExceeded, advance_usage

START = datetime(2026, 9, 28, tzinfo=timezone.utc)
LIMITS = {
    "query_rounds": 3, "max_queries_per_run": 12, "max_results": 300,
    "max_pages": 200, "max_page_bytes": 2097152,
    "max_duration_seconds": 1800, "max_model_tokens": 100000,
    "provider_concurrency": 4,
}


def _run():
    return SimpleNamespace(limits=LIMITS, target_companies=100,
                           usage_counters={}, first_dispatch_at=None)


@pytest.mark.parametrize("name,limit", [
    ("rounds", 3), ("queries", 12), ("raw_results", 300),
    ("pages", 200), ("model_tokens", 100000),
    ("in_flight", 4), ("companies", 100),
])
def test_every_cumulative_ceiling_accepts_n_and_rejects_n_plus_one(name, limit):
    run = _run()
    advance_usage(run, {name: limit}, at=START, external=True)
    assert run.usage_counters[name] == limit
    before = dict(run.usage_counters)
    with pytest.raises(UsageExceeded):
        advance_usage(run, {name: 1}, at=START, external=True)
    assert run.usage_counters == before


def test_three_rounds_retry_and_restart_share_the_same_query_limit():
    run = _run()
    for count in (4, 5):
        advance_usage(run, {"queries": count, "rounds": 1}, at=START, external=True)
    # Rehydrate persisted JSON as a restarted worker would.
    resumed = SimpleNamespace(limits=json.loads(json.dumps(run.limits)),
        target_companies=run.target_companies,
        usage_counters=json.loads(json.dumps(run.usage_counters)),
        first_dispatch_at=run.first_dispatch_at)
    advance_usage(resumed, {"queries": 3, "rounds": 1}, at=START, external=True)
    assert resumed.usage_counters["queries"] == 12
    with pytest.raises(UsageExceeded):
        advance_usage(resumed, {"queries": 1}, at=START, external=True)


def test_duration_starts_at_first_external_dispatch_and_never_resets():
    run = _run()
    advance_usage(run, {"queries": 1}, at=START, external=True)
    assert run.first_dispatch_at == START
    advance_usage(run, {"queries": 1}, at=START + timedelta(seconds=1800), external=True)
    with pytest.raises(UsageExceeded):
        advance_usage(run, {"queries": 1}, at=START + timedelta(seconds=1801), external=True)
    assert run.first_dispatch_at == START


def test_page_bytes_and_concurrency_cannot_bypass_limits():
    run = _run()
    advance_usage(run, {"pages": 1, "in_flight": 4}, at=START,
                  external=True, page_bytes=2097152)
    with pytest.raises(UsageExceeded):
        advance_usage(run, {"pages": 1}, at=START, external=True, page_bytes=2097153)
    with pytest.raises(UsageExceeded):
        advance_usage(run, {"in_flight": 1}, at=START, external=True)
    advance_usage(run, {"in_flight": -4}, at=START)
    assert run.usage_counters["in_flight"] == 0


def test_release_after_deadline_does_not_reopen_external_budget():
    run = _run()
    advance_usage(run, {"queries": 1, "in_flight": 1}, at=START, external=True)
    advance_usage(run, {"in_flight": -1}, at=START + timedelta(seconds=1801))
    assert run.usage_counters["in_flight"] == 0
    with pytest.raises(UsageExceeded):
        advance_usage(run, {"queries": 1}, at=START + timedelta(seconds=1801), external=True)


def test_page_bytes_require_a_counted_page_attempt():
    run = _run()
    with pytest.raises(ValueError):
        advance_usage(run, {"queries": 1}, at=START, external=True, page_bytes=1024)


def test_late_authoritative_result_can_be_accounted_without_new_dispatch():
    run = _run()
    advance_usage(run, {"queries": 1, "pages": 1, "in_flight": 1}, at=START, external=True)
    advance_usage(run, {"raw_results": 1, "in_flight": -1},
                  at=START + timedelta(seconds=1801))
    assert run.usage_counters["raw_results"] == 1
    with pytest.raises(UsageExceeded):
        advance_usage(run, {"queries": 1}, at=START + timedelta(seconds=1801), external=True)
