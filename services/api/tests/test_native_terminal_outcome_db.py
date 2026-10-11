"""One settled wakeup stays done while the whole run still has queued work."""
import asyncio
from pathlib import Path
import psycopg
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.provider_context import pending_run_work
from tests.test_cloudflare_provider_steps_db import migrated,worker_runtime,seed_research,SearchFixture,run_provider

def test_settled_discovery_step_does_not_reconcile_only_because_next_query_is_queued(migrated,worker_runtime):
    import buyeros_api
    assert Path(buyeros_api.__file__).resolve().parent==Path(__file__).resolve().parents[1]/'buyeros_api'
    case=seed_research(migrated,worker_runtime[1],query_count=2);adapter=SearchFixture(case,hits=0)
    result=run_provider(case['envelope'],adapter=adapter)
    assert result.state=='done',result
    assert run_provider(case['envelope'],adapter=adapter)==result and adapter.calls==1
    with psycopg.connect(migrated) as db:
        assert db.execute('SELECT status FROM search_runs WHERE id=%s',(case['run'],)).fetchone()==('running',)
        assert db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='run.discover' AND state='ready' AND payload->>'run_id'=%s",(case['envelope'].workspace_id,str(case['run']))).fetchone()==(1,)
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s AND status='settled'",(case['envelope'].workspace_id,)).fetchone()==(1,)
        assert db.execute('SELECT sum(remaining_hold) FROM budget_reservations WHERE workspace_id=%s',(case['envelope'].workspace_id,)).fetchone()==(0,)
    async def read():
        engine=create_async_engine(async_database_url(worker_runtime[0]))
        try:
            async with tenant_session(engine,case['envelope'].workspace_id) as session:
                assert await pending_run_work(session,case['envelope'].workspace_id,case['run']) is True
                assert await pending_run_work(session,case['envelope'].workspace_id,case['run'],uncertain_only=True) is False
        finally:await engine.dispose()
    asyncio.run(read())
