"""Newly admitted native work completes through worker/reconciliation owners."""
import pytest
import psycopg
from tests.test_native_model_completion_db import (
    model_case,native_basis_case,review_case,page_case,run_case,project_api,
    admission_case,migrated,clean_completion_steps,clean_model_native_steps,
    test_native_fit_completion_waits_for_original_model_work_and_current_basis as complete_native)


@pytest.fixture(autouse=True)
def sales_routes(monkeypatch):
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')


@pytest.mark.parametrize('run_case',['native'],indirect=True)
def test_completed_reconciled_native_run_becomes_sales_source_then_expires(model_case,monkeypatch):
    # This helper admits a real run, uses synthetic search/page/model transports,
    # reconciles original requests, recovers the worker generation, then executes
    # native fit completion. It does not set terminal run metadata in SQL.
    complete_native(model_case,'resume',monkeypatch)
    c=model_case
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',str(c['workspace']))
    from fastapi.testclient import TestClient
    from buyeros_api.api.app import create_app
    client=TestClient(create_app(),raise_server_exceptions=True)
    from tests.test_sales_core_journey_db import new_task
    from tests.test_sales_tasks_api import SALES_ROOT
    from tests.test_conversation_threads_api import headers
    from tests.test_sales_drafting_db import ref
    with psycopg.connect(c['dsn']) as db:
        version,status=db.execute('SELECT version,status FROM search_runs WHERE id=%s',(c['run'],)).fetchone()
        assert status=='completed'
    task=new_task(client,'sales-research',{'buyer_id':str(c['buyer'])},[
        ref('buyer',str(c['buyer'])),ref('run',str(c['run']),version)])
    prepared=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
    assert prepared.status_code==200,prepared.text
    output=prepared.json()['data']
    url=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+output['id']
    assert client.get(url,headers=headers()).json()['data']['availability']=='available'
    sources=client.get(SALES_ROOT+'/native-sources',headers=headers()).json()['data']['items']
    assert any(i['ref']['id']==str(c['run']) for i in sources)
    with psycopg.connect(c['dsn']) as db:
        db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
    assert client.get(url,headers=headers()).json()['data']['content'] is None
    from datetime import datetime,timezone
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution.engine import run_async,async_database_url
    from buyeros_api.services.retention import expire_subject_data
    from tests.test_native_model_completion_db import role_dsn
    async def expire():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_worker')))
        try:
            async with tenant_session(engine,c['workspace']) as s:
                await expire_subject_data(s,c['page_source'],'task14-native',datetime.now(timezone.utc),subject_type='source_document')
        finally:await engine.dispose()
    run_async(expire())
    sources=client.get(SALES_ROOT+'/native-sources',headers=headers()).json()['data']['items']
    assert not any(i['ref']['id']==str(c['run']) for i in sources)
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT excerpt FROM source_documents WHERE id=%s',(c['page_source'],)).fetchone()[0] is None
        assert db.execute('SELECT candidate FROM sales_output_versions WHERE output_id=%s',(output['id'],)).fetchone()[0]=={'kind':'research_report','purged':True}
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type LIKE 'delivery.%%'").fetchone()[0]==0
        # Exact test-owned discussions only; no financial execution is attached.
        db.execute("UPDATE sales_tasks SET state='cancelled' WHERE id=%s",(task['id'],))
        db.execute('DELETE FROM conversation_threads WHERE id=%s',(task['thread_id'],))
        db.execute('DELETE FROM sales_content_tombstones WHERE workspace_id=%s AND project_id=%s',(c['workspace'],c['project']))
