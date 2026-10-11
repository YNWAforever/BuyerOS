"""C19 source permission comes from current server rows; every page is synthetic."""
import asyncio,importlib,uuid
from dataclasses import FrozenInstanceError
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from tests.conftest import runtime_role_dsn
from tests.test_run_search_preparation_db import run_case,prepare,dispatch,project_api,admission_case,migrated

URL='https://sensors.example.test/company'

def scope_port():
    spec=importlib.util.find_spec('buyeros_api.services.research_page_scope')
    assert spec is not None,'C61-19 current exact-source page permission port is missing'
    fn=getattr(importlib.import_module('buyeros_api.services.research_page_scope'),'research_page_scope',None)
    assert callable(fn),'C61-19 canonical metadata-to-page scope port is missing'
    return fn

@pytest.fixture
def page_case(run_case):
    c=run_case;a=prepare(c);assert asyncio.run(dispatch(c,a))=='accepted'
    async def intake():
        from buyeros_api.services.search_intake import ingest_received_search
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                return await ingest_received_search(session,workspace_id=c['workspace'],run_id=c['run'],receipt_id=a.receipt_id,capability=c['cap'])
        finally:await engine.dispose()
    asyncio.run(intake())
    with psycopg.connect(c['dsn']) as db:
        raw,source=db.execute("SELECT id,(raw_payload->>'source_document_id')::uuid FROM raw_candidates WHERE run_id=%s",(c['run'],)).fetchone()
        policy,version=db.execute("UPDATE policy_decisions SET basis_reference=%s,provenance='synthetic exact-source licensing review',expires_at=now()+interval '2 hours',retention_days=1 WHERE subject_id=%s AND purpose='account_research' RETURNING id,version",(URL,c['project'])).fetchone()
    c.update(raw=raw,source=source,receipt=a.receipt_id,policy=policy,policy_version=version)
    return c

def call_scope(c,*,raw=None):
    fn=scope_port()
    async def exercise():
        engine=create_async_engine(async_database_url(runtime_role_dsn(c['dsn'])))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                return await fn(session,workspace_id=c['workspace'],run_id=c['run'],raw_candidate_id=raw or c['raw'],capability=c['cap'])
        finally:await engine.dispose()
    return asyncio.run(exercise())

def test_exact_source_scope_is_immutable_current_and_does_not_retrieve_or_promote(page_case):
    c=page_case;s=call_scope(c)
    assert s.workspace_id==c['workspace'] and s.run_id==c['run'] and s.raw_candidate_id==c['raw']
    assert s.source_document_id==c['source'] and s.receipt_id==c['receipt']
    assert s.source_url==URL and s.policy_id==c['policy'] and s.policy_version==c['policy_version']
    assert s.retention_until.tzinfo is not None and 0<s.retention_seconds<=7200
    assert s.max_page_bytes>0 and len(c['calls'])==1
    with pytest.raises(FrozenInstanceError):s.source_url='https://forged.example.test'
    with psycopg.connect(c['dsn']) as db:
        assert db.execute("SELECT usage_counters->>'pages' FROM search_runs WHERE id=%s",(c['run'],)).fetchone()==('0',)
        assert db.execute('SELECT canonical_company_id FROM raw_candidates WHERE id=%s',(c['raw'],)).fetchone()==(None,)
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)

@pytest.mark.parametrize('change',['generic-policy','wrong-url','wrong-purpose','expired-license','retention','actor','receipt','epoch','source-expired','source-altered','raw-altered','page-limit','foreign-raw','future-metadata'])
def test_page_scope_rejects_current_permission_provenance_and_fence_changes(page_case,change):
    scope_port() # Missing implementation must be RED, not swallowed as an expected rejection.
    c=page_case
    with psycopg.connect(c['dsn']) as db:
        if change=='generic-policy':db.execute("UPDATE policy_decisions SET basis_reference='Generic research permission' WHERE id=%s",(c['policy'],))
        elif change=='wrong-url':db.execute("UPDATE policy_decisions SET basis_reference='https://other.example.test/company' WHERE id=%s",(c['policy'],))
        elif change=='wrong-purpose':db.execute("UPDATE policy_decisions SET purpose='offer_research' WHERE id=%s",(c['policy'],))
        elif change=='expired-license':db.execute("UPDATE policy_decisions SET expires_at=now()-interval '1 second' WHERE id=%s",(c['policy'],))
        elif change=='retention':db.execute('UPDATE policy_decisions SET retention_days=31 WHERE id=%s',(c['policy'],))
        elif change=='actor':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor']))
        elif change=='receipt':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['source'],))
        elif change=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
        elif change=='source-expired':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['source'],))
        elif change=='source-altered':db.execute("UPDATE source_documents SET canonical_url='https://other.example.test/company' WHERE id=%s",(c['source'],))
        elif change=='raw-altered':db.execute("UPDATE raw_candidates SET raw_payload=jsonb_set(raw_payload,'{receipt_id}',to_jsonb(%s::text)) WHERE id=%s",(str(uuid.uuid4()),c['raw']))
        elif change=='page-limit':db.execute("UPDATE search_runs SET usage_counters=jsonb_set(usage_counters,'{pages}',to_jsonb((limits->>'max_pages')::int)) WHERE id=%s",(c['run'],))
        elif change=='future-metadata':db.execute("UPDATE source_documents SET retrieved_at=now()+interval '1 day' WHERE id=%s",(c['source'],))
    if change=='receipt':
        with psycopg.connect(runtime_role_dsn(c['dsn'])) as db:
            db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
            assert db.execute("SELECT public.buyeros_erase_provider_receipt(%s,'search',%s,'c19_page_scope_fixture')",(c['workspace'],c['receipt'])).fetchone()==(True,)
    from buyeros_api.api.errors import ApiError
    with pytest.raises((ValueError,ApiError)):call_scope(c,raw=uuid.uuid4() if change=='foreign-raw' else None)
    assert len(c['calls'])==1
