import pytest

from buyeros_worker.registry import HandlerResult, UnknownHandler
from buyeros_worker.tasks import run_intent


class FakeSession:
    def __init__(self):
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        self.committed = True


def test_run_intent_returns_handler_state():
    session = FakeSession()

    async def handler(s, context, payload):
        return HandlerResult(state="done", detail="ok")

    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
    assert state == "done"
    assert session.committed is True


def test_run_intent_reports_blocked_without_raising():
    session = FakeSession()

    async def handler(s, context, payload):
        return HandlerResult(state="blocked", detail="no provider")

    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
    assert state == "blocked"
