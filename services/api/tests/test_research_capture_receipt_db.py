"""Capture of persisted native synthetic model receipt; not three live provider runs."""
import asyncio,json,uuid
from datetime import datetime,timedelta,timezone
import psycopg,pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from tools.capture_research_predictions import capture_from_db
from tests.cutover_fixtures import role_dsn
from tests.test_run_model_dispatch_db import model_case,native_basis_case,review_case,page_case,run_case,project_api,admission_case,migrated,clean_model_native_steps
from tests.test_run_model_dispatch_db import test_native_received_model_status_recovers_current_fit_without_a_second_submit as saved_native_model

@pytest.mark.parametrize('run_case',['native'],indirect=True)
def test_readonly_capture_reads_original_native_receipt_metadata_without_submit_or_settlement(model_case,monkeypatch):
    c=model_case
    saved_native_model(c,'none',monkeypatch)
    extras=[uuid.uuid4(),uuid.uuid4()]
    with psycopg.connect(c['dsn']) as db:
        row=db.execute('SELECT project_buyer_id FROM fit_assessments WHERE run_id=%s',(c['run'],)).fetchone();buyer=row[0]
        company=db.execute('SELECT company_id FROM project_buyers WHERE id=%s',(buyer,)).fetchone()[0]
        icp,snapshot,created=db.execute('SELECT icp_version_id,execution_snapshot,created_at FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        # Capture fixtures terminate metadata explicitly; extra two abstention
        # runs have no supplier call and are never presented as real repeats.
        db.execute("UPDATE search_runs SET status='completed' WHERE id=%s",(c['run'],))
        for run in extras:db.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,execution_snapshot) VALUES(%s,%s,%s,%s,'failed',%s::jsonb)",(run,c['workspace'],c['project'],icp,json.dumps(snapshot)))
        before=db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id IN(SELECT operation_id FROM model_receipts WHERE workspace_id=%s)",(c['workspace'],)).fetchall()
        cost=db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s',(c['workspace'],)).fetchone()
    manifest={'schema':'buyeros.research-capture-manifest.v1','dataset_marker':'synthetic-native-capture','environment':'owned-fixture','database':make_url(async_database_url(role_dsn(c['dsn'],'buyeros_api'))).database,'workspace_id':str(c['workspace']),'project_id':str(c['project']),'actor_id':str(c['actor']),'frozen_at':(created-timedelta(minutes=1)).isoformat(),'goldset_sha256':'a'*64,'thresholds_sha256':'b'*64,'goldset_file':'gold.json','thresholds_file':'thresholds.json','run_ids':list(map(str,[c['run'],*extras])),'holdout':[{'company_id':str(company),'buyer_id':str(buyer)}]}
    async def read():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')),isolation_level='REPEATABLE READ')
        try:return await capture_from_db(engine,manifest)
        finally:await engine.dispose()
    try:
        predictions,proof=asyncio.run(read());first=proof['observations'][0]
        assert first['assessment_id'] and first['fit_version']=='live-model-v1'
        assert first['receipt_metadata']['state']=='received' and len(first['receipt_metadata']['request_hash'])==64 and len(first['receipt_metadata']['response_hash'])==64
        assert first['receipt_metadata']['model_id']=='local-owned-model-v1' and first['receipt_metadata']['pricing_version']=='local-model-price-v1'
        assert all(run['rows'][0]['verdict']=='needs_review' for run in predictions['runs'])
        assert proof['provider_calls']==0 and proof['live_verified'] is proof['release_accepted'] is False
        with psycopg.connect(c['dsn']) as db:
            assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id IN(SELECT operation_id FROM model_receipts WHERE workspace_id=%s)",(c['workspace'],)).fetchall()==before
            assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s',(c['workspace'],)).fetchone()==cost
            assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(1,)
    finally:
        with psycopg.connect(c['dsn']) as db:db.execute('DELETE FROM search_runs WHERE id=ANY(%s)',(extras,))
