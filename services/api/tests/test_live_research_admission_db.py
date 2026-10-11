"""C19 admission uses current actor and selector; fixture remains test-only."""
import asyncio,uuid
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.errors import ApiError
from buyeros_api.api.schemas import RunCreate
from buyeros_api.db.session import tenant_session
from buyeros_api.services.run_admission import admit_run
from tests.conftest import runtime_role_dsn
from tests.test_api_projects_db import api as project_api,WORKSPACE_A,OPERATOR
from tests.test_run_admission_integration_db import admission_case,CAPABILITY,PROJECT_A,_post,_request,_count

@pytest.fixture
def migrated(isolated_migrated):
    # Selector epoch changes belong only to this fresh child DB.
    return isolated_migrated

@pytest.mark.parametrize('backend',['celery','cloudflare'])
def test_lost202_single_run_outbox_uses_current_selector_epoch(admission_case,backend):
    api,dsn=admission_case
    with psycopg.connect(dsn) as db:
        current=db.execute('UPDATE worker_runtime_control SET backend=%s,enabled=false,epoch=epoch+1 WHERE singleton=1 RETURNING epoch',(backend,)).fetchone()[0]
    first=_post(api,key='c19-selector-lost202');assert first.status_code==202,first.text
    run_id=first.json()['data']['id']
    with psycopg.connect(dsn) as db:
        original=db.execute("SELECT id,runtime_backend,runtime_epoch FROM outbox_events WHERE workspace_id=%s AND event_type='run.discover'",(WORKSPACE_A,)).fetchone()
        assert original[1:]==(backend,current)
        db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
    replay=_post(api,key='c19-selector-lost202');assert replay.status_code==202 and replay.json()['data']['id']==run_id
    assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==1
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT id,runtime_backend,runtime_epoch FROM outbox_events WHERE id=%s',(original[0],)).fetchone()==original
        assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()==(0,)

@pytest.mark.parametrize('changed',['inactive','role'])
def test_role_revoked_before_admission_blocks(admission_case,changed):
    api,dsn=admission_case;actor=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)
    with psycopg.connect(dsn) as db:
        if changed=='inactive':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,actor))
        else:db.execute("UPDATE memberships SET roles='{Reviewer}' WHERE workspace_id=%s AND user_id=%s",(WORKSPACE_A,actor))
    async def exercise():
        engine=create_async_engine(runtime_role_dsn(dsn).replace('postgresql://','postgresql+psycopg://',1))
        try:
            async with tenant_session(engine,uuid.UUID(WORKSPACE_A)) as session:
                with pytest.raises(ApiError) as denied:
                    await admit_run(session,actor,uuid.UUID(PROJECT_A),RunCreate.model_validate(_request()),workspace_id=uuid.UUID(WORKSPACE_A),capabilities=CAPABILITY,environment='test')
                assert denied.value.status_code==403 and denied.value.code=='PERMISSION_DENIED'
        finally:await engine.dispose()
    asyncio.run(exercise())
    assert _count(dsn,'search_runs')==_count(dsn,'outbox_events')==0

@pytest.mark.parametrize('backend',['celery','cloudflare'])
def test_safe_fit_retry_reads_current_runtime_without_replaying_prior_intent(admission_case,backend):
    api,dsn=admission_case;first=_post(api,key='c19-fit-partial');assert first.status_code==202,first.text
    run_id=uuid.UUID(first.json()['data']['id'])
    with psycopg.connect(dsn) as db:
        original=db.execute("UPDATE outbox_events SET state='done' WHERE workspace_id=%s AND event_type='run.discover' RETURNING id,runtime_backend,runtime_epoch",(WORKSPACE_A,)).fetchone()
        db.execute("UPDATE search_runs SET status='partial',stage='fit_review_required' WHERE id=%s",(run_id,))
        current=db.execute('UPDATE worker_runtime_control SET backend=%s,enabled=false,epoch=epoch+1 WHERE singleton=1 RETURNING epoch',(backend,)).fetchone()[0]
    async def retry():
        from buyeros_api.services.run_control import retry_run
        engine=create_async_engine(runtime_role_dsn(dsn).replace('postgresql://','postgresql+psycopg://',1))
        try:
            async with tenant_session(engine,uuid.UUID(WORKSPACE_A)) as session:
                run=await retry_run(session,uuid.UUID(WORKSPACE_A),run_id,'owned fit checkpoint retry',expected_version=1)
                assert run.id==run_id and run.attempt==2
        finally:await engine.dispose()
    asyncio.run(retry())
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT runtime_backend,runtime_epoch,state FROM outbox_events WHERE workspace_id=%s AND event_type='run.fit'",(WORKSPACE_A,)).fetchall()==[(backend,current,'ready')]
        assert db.execute('SELECT id,runtime_backend,runtime_epoch,state FROM outbox_events WHERE id=%s',(original[0],)).fetchone()==(*original,'done')
        assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()==(0,)
