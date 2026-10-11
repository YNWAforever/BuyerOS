"""Current native reviewed entity context cannot grant factual fit coverage."""
import asyncio,uuid
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.execution.fit_runner import FitDomainRunner
from buyeros_api.services.fit import InventedEvidence
from tests.cutover_fixtures import role_dsn
from tests.test_run_model_admission_db import model_case,native_basis_case,review_case,page_case,run_case,project_api,admission_case,migrated

async def exercise(c,*,before_persist=None):
    engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
    try:
        runner=FitDomainRunner(engine,c['workspace'],c['run'],c['buyer'])
        state={'workspace_id':str(c['workspace']),'run_id':str(c['run']),'buyer_id':str(c['buyer']),'workflow_version':'fit-v1'}
        state.update(await runner.load_basis(state))
        state.update(await runner.hard_exclusions(state));assert state['hard_excluded'] is False
        state.update(await runner.fit(state));state.update(await runner.verify(state))
        if before_persist:before_persist()
        state.update(await runner.persist(state));again=await runner.persist(state)
        assert again['assessment_id']==state['assessment_id'];return state
    finally:await engine.dispose()

@pytest.mark.parametrize('run_case',['native'],indirect=True)
def test_native_fit_callbacks_keep_current_entity_context_as_needs_review_without_factual_coverage(model_case):
    c=model_case;result=asyncio.run(exercise(c))
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(1,)
        verdict,ids,details=db.execute('SELECT verdict,evidence_ids,assessment_details FROM fit_assessments WHERE id=%s',(uuid.UUID(result['assessment_id']),)).fetchone()
        assert verdict=='needs_review' and ids==[] and details['evidence_ids']==[] and details['supported_requirement_ids']==[]
        assert details['contradicted_requirement_ids']==[] and details['unknown_requirement_ids']
        assert db.execute('SELECT requirement_id,stance,is_inference FROM evidence WHERE id=%s',(c['evidence'],)).fetchone()==(None,'qualifies',True)
        assert db.execute("SELECT count(*) FROM provider_operations WHERE workspace_id=%s AND capability='model'",(c['workspace'],)).fetchone()==(0,)
    assert c['transport'].calls==1

@pytest.mark.parametrize('run_case',['native'],indirect=True)
@pytest.mark.parametrize('change',['source-expired','source-url','alias','claim-stance','claim-factual','foreign-requirement'])
def test_native_fit_context_exception_requires_current_original_server_proof(model_case,change):
    c=model_case
    with psycopg.connect(c['dsn']) as db:
        if change=='source-expired':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
        elif change=='source-url':db.execute("UPDATE source_documents SET canonical_url='https://foreign.example.test/page' WHERE id=%s",(c['page_source'],))
        elif change=='alias':db.execute('UPDATE company_aliases SET normalized_value=%s WHERE id=%s',('0'*64,uuid.UUID(c['review']['alias_id'])))
        elif change=='claim-stance':db.execute("UPDATE evidence SET stance='supports' WHERE id=%s",(c['evidence'],))
        elif change=='claim-factual':db.execute('UPDATE evidence SET is_inference=false WHERE id=%s',(c['evidence'],))
        elif change=='foreign-requirement':db.execute("UPDATE evidence SET requirement_id='foreign-unassigned' WHERE id=%s",(c['evidence'],))
    with pytest.raises((ValueError,InventedEvidence)):asyncio.run(exercise(c))
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
    assert c['transport'].calls==1

@pytest.mark.parametrize('run_case',['native'],indirect=True)
def test_native_entity_context_expired_after_verify_cannot_persist_a_fit(model_case):
    c=model_case
    def expire():
        with psycopg.connect(c['dsn']) as db:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
    with pytest.raises(ValueError,match='basis changed before persistence'):asyncio.run(exercise(c,before_persist=expire))
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT count(*) FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone()==(0,)
    assert c['transport'].calls==1
