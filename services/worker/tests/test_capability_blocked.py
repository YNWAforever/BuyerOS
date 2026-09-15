# services/worker/tests/test_capability_blocked.py
from buyeros_worker.handlers.capability_blocked import BLOCKED_EVENTS, blocked
from buyeros_worker.registry import get_handler


def test_blocked_handlers_are_registered():
    for event in BLOCKED_EVENTS:
        assert get_handler(event) is blocked


def test_blocked_result_makes_no_external_call():
    result = blocked(session=None, context=None, payload={})
    assert result.state == "blocked"
    assert "no verified provider" in result.detail.lower()
