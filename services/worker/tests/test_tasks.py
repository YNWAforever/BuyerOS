import asyncio
from contextlib import asynccontextmanager

import pytest

import buyeros_worker.engine as engine_mod
import buyeros_worker.tasks as tasks
from buyeros_worker.registry import HandlerResult, UnknownHandler


class FakeEngine:
    def __init__(self):
        self.disposed = False

    async def dispose(self):
        self.disposed = True


def _patch_engine(monkeypatch):
    created = []

    def fake_create_engine():
        engine = FakeEngine()
        created.append(engine)
        return engine

    @asynccontextmanager
    async def fake_tenant_session(engine, workspace_id):
        yield object()

    monkeypatch.setattr(tasks, "create_engine", fake_create_engine)
    monkeypatch.setattr(tasks, "tenant_session", fake_tenant_session)
    return created


def _row(state="dispatched", generation=1, event_type="fetch.evidence", payload=None):
    return {"state": state, "event_type": event_type, "payload": payload or {}, "fencing_generation": generation}


def test_each_invocation_creates_and_disposes_its_own_engine(monkeypatch):
    created = _patch_engine(monkeypatch)

    async def fake_run_intent(session, context, intent_key, generation):
        return "done"

    monkeypatch.setattr(tasks, "run_intent", fake_run_intent)
    assert tasks.execute_intent_sync("job:1", "ws", 1) == "done"
    assert tasks.execute_intent_sync("job:2", "ws", 1) == "done"
    assert len(created) == 2
    assert all(engine.disposed for engine in created)


def test_stale_fencing_returns_stale_and_disposes(monkeypatch):
    created = _patch_engine(monkeypatch)

    async def fake_run_intent(session, context, intent_key, generation):
        raise tasks.StaleFenced()

    monkeypatch.setattr(tasks, "run_intent", fake_run_intent)
    assert tasks.execute_intent_sync("job:1", "ws", 1) == "stale"
    assert created[0].disposed is True


def test_run_intent_is_a_noop_for_a_terminal_row(monkeypatch):
    async def fake_load(session, intent_key):
        return _row(state="done")

    called = []
    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda *args: called.append(event_type))
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "duplicate"
    assert called == []


def test_run_intent_rejects_a_stale_generation_without_running_the_handler(monkeypatch):
    async def fake_load(session, intent_key):
        return _row(generation=9)

    called = []
    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda *args: called.append(event_type))
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "stale"
    assert called == []


def test_run_intent_marks_the_row_done(monkeypatch):
    async def fake_load(session, intent_key):
        return _row()

    terminal = []

    async def fake_mark(session, intent_key, generation, state):
        terminal.append((intent_key, generation, state))
        return 1

    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda s, c, p: HandlerResult(state="done"))
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "done"
    assert terminal == [("job:1", 1, "done")]


def test_run_intent_marks_blocked_as_terminal_failed(monkeypatch):
    async def fake_load(session, intent_key):
        return _row(event_type="run.discover")

    terminal = []

    async def fake_mark(session, intent_key, generation, state):
        terminal.append(state)
        return 1

    async def handler(session, context, payload):
        return HandlerResult(state="blocked")

    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
    monkeypatch.setattr(tasks, "get_handler", lambda event_type: handler)
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "blocked"
    assert terminal == ["failed"]


def test_run_intent_requests_a_retry_without_a_terminal_write(monkeypatch):
    async def fake_load(session, intent_key):
        return _row()

    called = []

    async def fake_mark(*args):
        called.append(args)
        return 1

    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda s, c, p: HandlerResult(state="retry"))
    with pytest.raises(tasks.RetryRequested):
        asyncio.run(tasks.run_intent(object(), {}, "job:1", 1))
    assert called == []


def test_run_intent_marks_unknown_handlers_terminal(monkeypatch):
    async def fake_load(session, intent_key):
        return _row(event_type="nope.nope")

    terminal = []

    async def fake_mark(session, intent_key, generation, state):
        terminal.append(state)
        return 1

    def fake_get_handler(event_type):
        raise UnknownHandler(event_type)

    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
    monkeypatch.setattr(tasks, "get_handler", fake_get_handler)
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "unknown_handler"
    assert terminal == ["failed"]


def test_run_intent_reports_unknown_intent(monkeypatch):
    async def fake_load(session, intent_key):
        return None

    monkeypatch.setattr(tasks, "load_intent", fake_load)
    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "unknown_intent"


def test_run_intent_passes_the_db_event_type_into_context(monkeypatch):
    async def fake_load(session, intent_key):
        return _row(event_type="fetch.evidence")

    seen = {}

    def fake_get_handler(event_type):
        def handler(session, context, payload):
            seen["context"] = context
            return HandlerResult(state="done")

        return handler

    async def fake_mark(session, intent_key, generation, state):
        return 1

    monkeypatch.setattr(tasks, "load_intent", fake_load)
    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
    monkeypatch.setattr(tasks, "get_handler", fake_get_handler)
    asyncio.run(tasks.run_intent(object(), {"workspace_id": "ws"}, "job:1", 1))
    assert seen["context"] == {"workspace_id": "ws", "event_type": "fetch.evidence"}


def test_worker_shutdown_disposes_the_in_flight_engine():
    from celery import signals

    engine = FakeEngine()
    engine_mod.set_active_engine(engine)
    signals.worker_shutdown.send(sender=None)
    assert engine.disposed is True
    assert engine_mod._active_engine is None
