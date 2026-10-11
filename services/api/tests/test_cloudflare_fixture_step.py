"""Fixture contract only: actual worker route retains its bounded research engine.

No database, provider, authorization or production acceptance is claimed here.
"""
import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def native_fixture(monkeypatch):
    from tools import serve_cloudflare_e2e as fixture
    from buyeros_api.api import deps
    from buyeros_api.api.routes import worker_internal

    monkeypatch.setenv('BUYEROS_STRICT_INTEGRATION', '1')
    monkeypatch.delenv('BUYEROS_TEST_DATABASE_URL', raising=False)
    monkeypatch.setattr(fixture.fixture, 'main', lambda: None)
    # main installs these fixture-only hooks; restore every original after the unit.
    for target, name in [(fixture.fixture, 'seed'), (fixture.fixture, 'create_app'),
                         (fixture.worker_execution, 'execute_step')]:
        monkeypatch.setattr(target, name, getattr(target, name))
    delegated = AsyncMock(return_value={'opaque_fixture_result': True})
    monkeypatch.setattr(fixture, 'original_execute', delegated)
    fixture.main()
    execute = fixture.worker_execution.execute_step
    captured = inspect.getclosurevars(execute).nonlocals
    captured['connection'].update(owner='unit-fixture-no-database',
                                  worker='unit-fixture-no-checkpoint')
    research_engine, execution_engine = object(), object()
    monkeypatch.setattr(deps, 'get_engine', lambda: research_engine)
    selected = {'event': 'run.discover', 'processed': 0}

    class ReadOnlyFixture:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, statement, parameters):
            assert statement.startswith('SELECT '), 'this wrapper probe must never mutate a DB'
            if statement.startswith('SELECT event_type'):
                return SimpleNamespace(fetchone=lambda: (selected['event'], {'job_id': 'unit-job'}))
            assert statement.startswith('SELECT processed')
            return SimpleNamespace(fetchone=lambda: (selected['processed'],))

    def connect(dsn):
        assert dsn == 'unit-fixture-no-database'
        return ReadOnlyFixture()
    monkeypatch.setattr(fixture.psycopg, 'connect', connect)
    body = SimpleNamespace(envelope=SimpleNamespace(outbox_id='unit-outbox', workspace_id='unit-workspace'),
                           step_key='retained-step-key')
    request = SimpleNamespace(state=SimpleNamespace(execution_engine=execution_engine))
    return SimpleNamespace(route=worker_internal.step, body=body, request=request,
                           selected=selected, captured=captured, delegated=delegated,
                           research_engine=research_engine, execution_engine=execution_engine)


@pytest.mark.parametrize('event', ['run.discover', 'contact.enrich'])
def test_actual_worker_route_keeps_bounded_research_engine(native_fixture, event):
    f = native_fixture
    f.selected['event'] = event
    result = asyncio.run(f.route(f.body, f.request))
    assert result == {'opaque_fixture_result': True}
    f.delegated.assert_awaited_once()
    args, kwargs = f.delegated.await_args
    assert args == (f.execution_engine, f.body.envelope, f.body.step_key)
    assert kwargs['research_engine'] is f.research_engine
    assert kwargs['checkpoint_dsn'] == 'unit-fixture-no-checkpoint'
    assert kwargs['environment'] == 'test'
    assert kwargs['adapter'] is f.captured['contact' if event.startswith('contact.') else 'adapter']


def test_native_bulk_barrier_keeps_route_engine_until_release(native_fixture):
    f = native_fixture
    f.selected.update(event='bulk.mutate', processed=51)
    f.captured['barrier']['enabled'] = True
    async def run():
        pending = asyncio.create_task(f.route(f.body, f.request))
        await asyncio.sleep(0)
        if pending.done():
            await pending  # Retrieve any route binding failure before checking the barrier.
        assert f.captured['barrier']['hits'] == 1
        assert not pending.done()
        f.delegated.assert_not_awaited()
        f.captured['released'].set()
        assert await pending == {'opaque_fixture_result': True}
    asyncio.run(run())
    f.delegated.assert_awaited_once()
    assert f.delegated.await_args.kwargs['research_engine'] is f.research_engine
