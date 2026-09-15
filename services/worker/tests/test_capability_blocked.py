import asyncio

from buyeros_worker.handlers.capability_blocked import BLOCKED_EVENTS, blocked
from buyeros_worker.registry import get_handler


def test_blocked_handlers_are_registered():
    for event in BLOCKED_EVENTS:
        assert get_handler(event) is blocked


def test_blocked_result_makes_no_external_call():
    result = asyncio.run(blocked(session=None, context=None, payload={}))
    assert result.state == "blocked"
    assert "no verified provider" in result.detail.lower()


def test_blocked_uses_context_event_type():
    result = asyncio.run(blocked(session=None, context={"event_type": "run.discover"}, payload={}))
    assert result.state == "blocked"
    assert "run.discover" in result.detail


def test_blocked_without_a_run_id_skips_emission():
    result = asyncio.run(blocked(session=object(), context={"event_type": "contact.submit"}, payload={}))
    assert result.state == "blocked"
