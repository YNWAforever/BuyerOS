import pytest

from buyeros_worker.registry import HANDLERS, HandlerResult, UnknownHandler, get_handler, register


def test_unknown_handler_raises():
    with pytest.raises(UnknownHandler):
        get_handler("does.not.exist")


def test_registration_makes_handler_available():
    @register("test.event")
    def handler(session, context, payload):
        return HandlerResult(state="done", detail="ok")

    assert get_handler("test.event") is handler
    assert "test.event" in HANDLERS
