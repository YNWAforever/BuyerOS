"""Native page model basis uses current bounded server provenance, never client proof."""
import asyncio,hashlib,importlib,uuid
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from tests.cutover_fixtures import role_dsn
from tests.test_research_candidate_review_db import review_case,review,page_case,run_case,project_api,admission_case,migrated

@pytest.fixture
def native_basis_case(review_case):
    c=review_case;value=review(c)
    with psycopg.connect(c['dsn']) as db:
        old=db.execute('SELECT stage,status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        db.execute("UPDATE search_runs SET stage='fit',status='running' WHERE id=%s",(c['run'],))
    try:yield {**c,'review':value,'buyer':uuid.UUID(value['buyer_id']),'evidence':uuid.UUID(value['evidence_id'])}
    finally:
        with psycopg.connect(c['dsn']) as db:db.execute('UPDATE search_runs SET stage=%s,status=%s WHERE id=%s',(*old,c['run']))

def port():
    spec=importlib.util.find_spec('buyeros_api.services.research_native_basis')
    assert spec is not None,'C61-19 current native reviewed evidence basis is missing'
    fn=getattr(importlib.import_module('buyeros_api.services.research_native_basis'),'reviewed_research_evidence',None)
    assert callable(fn),'C61-19 server-only native evidence proof is missing'
    return fn

def proof(c,role='buyeros_worker'):
    fn=port()
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],role)))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                return await fn(session,workspace_id=c['workspace'],run_id=c['run'],buyer_id=c['buyer'],evidence_id=c['evidence'])
        finally:await engine.dispose()
    return asyncio.run(run())

def model_basis(c):
    from buyeros_api.execution.live_fit_runner import LiveFitDomainRunner
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        try:
            runner=LiveFitDomainRunner(engine,c['workspace'],c['run'],c['buyer'],receipts=None)
            state={'workspace_id':str(c['workspace']),'run_id':str(c['run']),'buyer_id':str(c['buyer']),'workflow_version':'fit-v1'}
            state.update(await runner.load_basis(state));return await runner.model_basis(state)
        finally:await engine.dispose()
    return asyncio.run(run())

@pytest.mark.parametrize('review_case',['long'],indirect=True)
@pytest.mark.parametrize('role',['buyeros_api','buyeros_worker'])
def test_native_page_current_proof_distinguishes_excerpt_and_full_digest_under_restricted_roles(native_basis_case,role):
    c=native_basis_case;value=proof(c,role)
    assert value['current'] is True and value['source_hash']==hashlib.sha256(c['args']['excerpt'].encode()).hexdigest()
    assert value['source_document_hash']==c['args']['expected_page_digest'] and value['source_hash']!=value['source_document_hash']
    assert c['transport'].calls==1

@pytest.mark.parametrize('mutation',['source','citation','alias','company','expiry','receipt','license','missing-review-proof'])
def test_native_current_proof_rejects_changed_or_expired_authoritative_basis(native_basis_case,mutation):
    c=native_basis_case;port()
    with psycopg.connect(c['dsn']) as db:
        if mutation=='source':db.execute("UPDATE source_documents SET excerpt='changed' WHERE id=%s",(c['page_source'],))
        elif mutation=='citation':db.execute("UPDATE evidence SET excerpt='sensor parts' WHERE id=%s",(c['evidence'],))
        elif mutation=='alias':db.execute('UPDATE company_aliases SET normalized_value=%s WHERE id=%s',('0'*64,c['review']['alias_id']))
        elif mutation=='company':db.execute("UPDATE companies SET display_name='Changed independent label' WHERE id=%s",(c['company'],))
        elif mutation=='expiry':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
        elif mutation=='receipt':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['source'],))
        elif mutation=='license':db.execute("UPDATE policy_decisions SET expires_at=now()-interval '1 second' WHERE id=%s",(c['policy'],))
        else:db.execute("UPDATE run_events SET payload=payload-'review_reason_hash' WHERE run_id=%s AND event_type='candidate.page_reviewed'",(c['run'],))
    if mutation=='receipt':
        async def erase():
            engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
            try:
                async with tenant_session(engine,c['workspace']) as session:
                    erased=(await session.execute(text("SELECT public.buyeros_erase_provider_receipt(:ws,'search',:receipt,'C61-native-basis-expiry')"),{'ws':c['workspace'],'receipt':c['receipt']})).scalar_one()
                    assert erased is True
            finally:await engine.dispose()
        asyncio.run(erase())
        with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT redacted_at IS NOT NULL FROM search_receipts WHERE id=%s',(c['receipt'],)).fetchone()==(True,)
    with pytest.raises(ValueError):proof(c)

@pytest.mark.parametrize('review_case',['long'],indirect=True)
def test_live_model_basis_accepts_current_native_excerpt_proof_without_promoting_inference(native_basis_case):
    c=native_basis_case;basis=model_basis(c);item=basis['evidence'][0]
    assert item['current'] is True and item['is_inference'] is True
    assert item['source_hash']==hashlib.sha256(item['source_excerpt'].encode()).hexdigest()
    assert item['source_document_hash']==c['args']['expected_page_digest'] and item['source_hash']!=item['source_document_hash']

def test_live_model_basis_never_transfers_expired_native_page_prose(native_basis_case):
    c=native_basis_case
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
    with pytest.raises(ValueError):model_basis(c)
