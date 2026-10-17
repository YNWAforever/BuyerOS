"""C19 real native status path with owned PG and synthetic search/page responses."""
import asyncio,uuid
from decimal import Decimal
import httpx,psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from buyeros_api.providers.live_search import LiveSearchAdapter,PostgresSearchReceipts,BraveSearchClient
from tests.conftest import runtime_role_dsn
from tests.cutover_fixtures import role_dsn
from tests.test_run_search_preparation_db import run_case,prepare,dispatch,project_api,admission_case,migrated
from tests.test_research_page_retrieval_db import Transport,execute,URL

@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('page_state',['unattempted','pending','retrieved','missing-transport','policy-changed','policy-tampered','epoch-during-page'])
def test_native_received_status_recovery_continues_only_unattempted_permitted_pages(run_case,page_state,monkeypatch):
    c=run_case
    from tests.policy_activation_fixtures import approve_page_license_fixture
    c['policy'],_=approve_page_license_fixture(c['dsn'],c['workspace'],c['project'],URL)
    prepared=prepare(c);c['receipt']=prepared.receipt_id
    original=LiveSearchAdapter.submit
    class ProcessLost(BaseException):pass
    async def crash(self,intent):
        assert (await original(self,intent)).state=='accepted'
        raise ProcessLost('synthetic loss after durable received search, before metadata intake')
    if page_state in {'pending','retrieved'}:
        # These already-attempted pages were admitted after accepted search.
        # An unknown operation cannot be consumed before status recovery.
        assert asyncio.run(dispatch(c,prepared))=='accepted'
    else:
        monkeypatch.setattr(LiveSearchAdapter,'submit',crash)
        with pytest.raises(ProcessLost):asyncio.run(dispatch(c,prepared))
        monkeypatch.setattr(LiveSearchAdapter,'submit',original)
        assert asyncio.run(dispatch(c,prepared))=='unknown'
    assert len(c['calls'])==1
    transport=Transport(c,'epoch' if page_state=='epoch-during-page' else 'received')
    if page_state in {'pending','retrieved'}:
        async def intake():
            from buyeros_api.services.search_intake import ingest_received_search
            engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
            try:
                async with tenant_session(engine,c['workspace']) as session:
                    await ingest_received_search(session,workspace_id=c['workspace'],run_id=c['run'],receipt_id=c['receipt'],capability=c['cap'])
            finally:await engine.dispose()
        asyncio.run(intake())
        with psycopg.connect(c['dsn']) as db:c['raw']=db.execute('SELECT id FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchone()[0]
        if page_state=='pending':
            transport.mode='crash'
            with pytest.raises(KeyboardInterrupt):execute(c,transport)
            transport.mode='received'
        else:assert execute(c,transport)['status']=='retrieved'
    if page_state=='policy-changed':
        from tests.policy_activation_fixtures import approve_selected_research_fixture
        # A genuine, append-only withdrawal of page fetch permission retains
        # authorization to read the already-received search metadata.
        approve_selected_research_fixture(c['dsn'],c['workspace'],c['project'],domains=('sensors.example.test',),
            terms_overrides={'basis_reference':URL,'retention_days':1,
                'allowed_actions':['research.search','research.read','research.persist']})
    if page_state=='policy-tampered':
        # Keep the original tampering case too: it invalidates the entire proof,
        # so no private metadata may be copied and status remains unconfirmed.
        with psycopg.connect(c['dsn']) as db:db.execute("UPDATE policy_decisions SET basis_reference='no exact URL permission',version=version+1 WHERE id=%s",(c['policy'],))
    async def recover():
        from buyeros_api.api.worker_schemas import JobEnvelope
        from buyeros_api.services.worker_execution import execute_step
        from buyeros_api.execution.external_runner import reconcile_intent_key
        key=reconcile_intent_key(prepared.operation_id)
        with psycopg.connect(c['dsn']) as db:
            db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE intent_key=%s",(key,))
            oid,epoch=db.execute('SELECT id,runtime_epoch FROM outbox_events WHERE intent_key=%s',(key,)).fetchone()
            payload=db.execute('SELECT payload FROM outbox_events WHERE id=%s',(oid,)).fetchone()[0]
        worker=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        api=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        def unexpected(req):raise AssertionError('status recovery resubmitted/search HTTP after durable receipt')
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as http:
                adapter=LiveSearchAdapter(capability=c['cap'],receipts=PostgresSearchReceipts(worker,c['workspace'],c['cap']),
                    client=BraveSearchClient(api_key='synthetic-offline-only',http=http,language_codes={'en':'en'},api_version='2026-10-01'),
                    source_transport=None if page_state=='missing-transport' else transport)
                env=JobEnvelope(v=1,workspace_id=c['workspace'],outbox_id=oid,generation=1,runtime_epoch=epoch)
                first=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
                replay=await execute_step(worker,env,'start',adapter=adapter,research_engine=api,environment='test')
                expected='stale' if page_state=='epoch-during-page' else 'reconcile' if page_state=='policy-tampered' else 'done'
                assert first.state==replay.state==expected
        finally:await worker.dispose();await api.dispose()
        with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT payload FROM outbox_events WHERE id=%s',(oid,)).fetchone()==(payload,)
    asyncio.run(recover())
    if page_state=='epoch-during-page':
        with psycopg.connect(c['dsn']) as db:
            # Status proof was committed before GET/epoch change; never rewrite it.
            assert db.execute("SELECT state FROM worker_steps WHERE outbox_id IN(SELECT id FROM outbox_events WHERE event_type='provider.reconcile')").fetchone()==('done',)
    assert len(c['calls'])==1
    if page_state=='policy-tampered':
        assert transport.calls==0
        with psycopg.connect(c['dsn']) as db:
            assert db.execute('SELECT count(*) FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
            assert db.execute('SELECT count(*) FROM source_documents WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
            assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',
                (prepared.operation_id,)).fetchone()==('active',Decimal('0.005000'))
            assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        return
    assert transport.calls==(0 if page_state in {'missing-transport','policy-changed'} else 1),'status recovery did not continue only the original unattempted page'
    with psycopg.connect(c['dsn']) as db:
        count=1 if page_state in {'unattempted','retrieved'} else 0
        assert db.execute("SELECT count(*) FROM source_documents WHERE run_id=%s AND storage_mode='research_page_excerpt'",(c['run'],)).fetchone()==(count,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(prepared.operation_id,)).fetchone()==('active',Decimal('0.005000'))
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        assert db.execute('SELECT canonical_company_id,merge_state FROM raw_candidates WHERE run_id=%s',(c['run'],)).fetchone()==(None,'needs_review')
        assert db.execute('SELECT status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()==('running',)
        assert db.execute("SELECT usage_counters->>'pages',usage_counters->>'in_flight' FROM search_runs WHERE id=%s",(c['run'],)).fetchone()==(('0','0') if page_state in {'missing-transport','policy-changed'} else ('1','1') if page_state in {'pending','epoch-during-page'} else ('1','0'))
