"""C19 native recovery plumbing; test-only provider, NOT real live journey/UAT."""
import uuid,json
from decimal import Decimal
import psycopg,pytest
from buyeros_api.providers.base import ProviderIntent,FixtureProviderAdapter
from buyeros_worker.tasks import execute_intent_sync
from buyeros_worker.external_runner import reconcile_intent_key
from tests import conftest as base
from tests.conftest import WS_A
from tests.test_external_runner_db import _setup,_capability
from tests.test_discovery_runner_db import discovery_case,SearchFixture,INTENT,RUN_ID,WS_A as DISCOVERY_WS

@pytest.fixture
def pg_dsn():
    # Each case owns an entire native cluster: no shared epoch/schema/reset.
    yield from base.pg_dsn.__wrapped__()

@pytest.fixture
def migrated(pg_dsn):
    return base.migrated.__wrapped__(pg_dsn)

@pytest.fixture
def runtime_dsn(migrated):
    return base.runtime_role_dsn(migrated)

def prepared(pg_dsn):
    intent=ProviderIntent('c19-native:'+str(uuid.uuid4()),'contact','HK','en','company');operation=uuid.uuid4()
    _setup(pg_dsn,intent,operation)
    with psycopg.connect(pg_dsn) as db:
        epoch=db.execute("UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1 RETURNING epoch").fetchone()[0]
        db.execute('UPDATE outbox_events SET runtime_epoch=%s WHERE intent_key=%s',(epoch,intent.key))
    return intent,operation,epoch

def held(pg_dsn,operation):
    with psycopg.connect(pg_dsn) as db:
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()==('active',Decimal('1.000000'))
        assert db.execute('SELECT count(*) FROM cost_events WHERE operation_id=%s',(operation,)).fetchone()==(0,)

def assert_reconciliation(pg_dsn,intent,operation,epoch):
    with psycopg.connect(pg_dsn) as db:
        assert db.execute('SELECT runtime_backend,runtime_epoch,state FROM outbox_events WHERE intent_key=%s',(reconcile_intent_key(operation),)).fetchone()==('celery',epoch,'ready')
        assert db.execute('SELECT count(*) FROM provider_operations WHERE intent_key=%s',(intent.key,)).fetchone()==(1,)
        assert db.execute('SELECT count(*) FROM outbox_events WHERE intent_key=%s',(intent.key,)).fetchone()==(1,)

def test_crash_after_provider_acceptance_reconciles(worker_database_url,pg_dsn):
    intent,operation,epoch=prepared(pg_dsn)
    class Killed(BaseException):pass
    class Adapter(FixtureProviderAdapter):
        async def submit(self,intent):
            await super().submit(intent);raise Killed('after synthetic acceptance, before local acknowledgement')
    adapter=Adapter(_capability(),environment='test')
    with pytest.raises(Killed):execute_intent_sync(intent.key,WS_A,1,adapter=adapter,environment='test')
    assert execute_intent_sync(intent.key,WS_A,1,adapter=adapter,environment='test')=='unknown'
    assert adapter.submit_count==1
    assert_reconciliation(pg_dsn,intent,operation,epoch);held(pg_dsn,operation)

def test_unknown_intent_uses_status_only_at_original_epoch(worker_database_url,pg_dsn):
    intent,operation,epoch=prepared(pg_dsn)
    class Adapter(FixtureProviderAdapter):
        status_calls=0
        async def status(self,ref):
            self.status_calls+=1;return await super().status(ref)
    adapter=Adapter(_capability(),environment='test',outcome='timeout_after_acceptance')
    assert execute_intent_sync(intent.key,WS_A,1,adapter=adapter,environment='test')=='unknown'
    assert_reconciliation(pg_dsn,intent,operation,epoch)
    key=reconcile_intent_key(operation)
    with psycopg.connect(pg_dsn) as db:db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1 WHERE intent_key=%s",(key,))
    assert execute_intent_sync(key,WS_A,1,adapter=adapter,environment='test')=='unknown'
    assert adapter.submit_count==1 and adapter.status_calls==1
    held(pg_dsn,operation)

def test_old_epoch_cannot_commit(worker_database_url,pg_dsn):
    intent,operation,epoch=prepared(pg_dsn)
    class Adapter(FixtureProviderAdapter):
        async def submit(self,intent):
            result=await super().submit(intent)
            with psycopg.connect(pg_dsn) as db:db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
            return result
    adapter=Adapter(_capability(),environment='test')
    assert execute_intent_sync(intent.key,WS_A,1,adapter=adapter,environment='test')=='stale'
    assert execute_intent_sync(intent.key,WS_A,1,adapter=adapter,environment='test')=='stale'
    assert adapter.submit_count==1
    with psycopg.connect(pg_dsn) as db:
        assert db.execute('SELECT status,provider_ref FROM provider_operations WHERE id=%s',(operation,)).fetchone()==('submitting',None)
        assert db.execute('SELECT count(*) FROM outbox_events WHERE intent_key=%s',(reconcile_intent_key(operation),)).fetchone()==(0,)
    held(pg_dsn,operation)

@pytest.mark.parametrize('next_event',['run.fit','run.discover','research.reconcile'])
def test_research_continuations_keep_original_selector_epoch(discovery_case,next_event):
    owner,dsn=discovery_case
    with psycopg.connect(owner) as db:
        epoch=db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1 RETURNING epoch').fetchone()[0]
        db.execute('UPDATE outbox_events SET runtime_epoch=%s WHERE intent_key=%s',(epoch,INTENT))
        if next_event=='run.discover':
            snapshot=db.execute('SELECT execution_snapshot FROM search_runs WHERE id=%s',(RUN_ID,)).fetchone()[0]
            snapshot['query_plan']['queries'].append({**snapshot['query_plan']['queries'][0],'id':'b'*24})
            db.execute('UPDATE search_runs SET execution_snapshot=%s::jsonb WHERE id=%s',(json.dumps(snapshot),RUN_ID))
    adapter=SearchFixture(owner,timeout=next_event=='research.reconcile')
    assert execute_intent_sync(INTENT,DISCOVERY_WS,1,search_adapter=adapter,environment='test')==('unknown' if next_event=='research.reconcile' else 'done')
    assert adapter.calls==1
    with psycopg.connect(owner) as db:
        continuation=db.execute('SELECT runtime_backend,runtime_epoch,state FROM outbox_events WHERE workspace_id=%s AND event_type=%s AND intent_key<>%s',(DISCOVERY_WS,next_event,INTENT)).fetchall()
        assert continuation==[('celery',epoch,'ready')]
        assert db.execute('SELECT count(*) FROM search_runs WHERE id=%s',(RUN_ID,)).fetchone()==(1,)
