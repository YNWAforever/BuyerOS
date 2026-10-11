"""Owned fictional provider journal; never installed in production packages."""
import json,os,uuid
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import psycopg
from celery import Celery
from tests.fixtures.run_browser_research import ROOT,WORKSPACE,owner_dsn
from buyeros_worker.discovery_runner import DiscoveryBatch

celery_app=Celery('c61_joined_unknown_fixture',broker=os.environ['BUYEROS_BROKER_URL'])
celery_app.conf.update(task_ignore_result=True,task_acks_late=True,worker_prefetch_multiplier=1,broker_connection_timeout=5)

class BrowserSearchFixture:
    """Clearly fictional, bounded search result for a disposable browser run."""
    test_only = True
    provider = "fixture"
    price_version = "fixture-price-v1"
    quoted_upper_bound = Decimal("0.100000")
    retention_seconds = 86400

    def __init__(self):
        self.accepted = {}

    async def search(self, query, *, market, language, limit, intent_key):
        assert market == "US" and language == "en" and 1 <= limit <= 300
        batch = DiscoveryBatch(
            hits=[{"url": "https://fixture.example.test/t30-industrial-buyer",
                   "legal_name": "T30 Fictional Industrial Buyer",
                   "registry_id": "US-T30-FIXTURE-001",
                   "excerpt": "Fictional distributor lists industrial sensors in a public catalog.",
                   "language": "en", "external_ref": "t30-fixture-buyer"}],
            charge=Decimal("0.050000"), billing_event_id=f"fixture-bill:{intent_key}",
        )
        self.accepted[intent_key] = batch
        return batch

    async def status(self, intent_key):
        return self.accepted.get(intent_key)



class JournalSearchFixture(BrowserSearchFixture):
    def __init__(self):
        super().__init__();self.run=uuid.UUID(os.environ['BUYEROS_T30_ACCEPTED_UNKNOWN_RUN_ID']);self.project=uuid.UUID(os.environ['BUYEROS_T30_ACCEPTED_UNKNOWN_PROJECT_ID']);self.phase=os.environ['BUYEROS_T30_ACCEPTED_UNKNOWN_PHASE']
        self.path=Path(os.environ['BUYEROS_T30_ACCEPTED_UNKNOWN_JOURNAL'])
        assert self.phase in {'unknown','accepted'}
        assert self.path.resolve()==(ROOT/'test-results/c61-joined-search'/str(self.run)/'accepted.json').resolve()
        assert owner_dsn()==os.environ['BUYEROS_TEST_OWNER_DSN']
        with psycopg.connect(owner_dsn()) as db:
            assert db.execute('SELECT p.company_name FROM search_runs r JOIN projects p ON p.id=r.project_id AND p.workspace_id=r.workspace_id WHERE r.id=%s AND r.workspace_id=%s AND r.project_id=%s',(self.run,WORKSPACE,self.project)).fetchone()==('T30 Fictional Seller',)
    async def search(self,query,*,market,language,limit,intent_key):
        assert self.phase=='unknown' and intent_key.startswith(f'research:{self.run}:')
        assert not self.path.exists(),'never resubmit the original possibly accepted fixture intent'
        batch=await super().search(query,market=market,language=language,limit=limit,intent_key=intent_key)
        row=dict(fixture_only=True,workspace_id=str(WORKSPACE),project_id=str(self.project),run_id=str(self.run),intent_key=intent_key,hits=batch.hits,charge=str(batch.charge),billing_event_id=batch.billing_event_id,native_submit_worker_pid=os.getpid(),submitted_at=datetime.now(timezone.utc).isoformat())
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.path.open('x',encoding='utf-8') as f:json.dump(row,f);f.flush();os.fsync(f.fileno())
        raise TimeoutError('owned fictional provider accepted batch before lost acknowledgment')
    async def status(self,intent_key):
        assert self.phase=='accepted' and self.path.exists()
        row=json.loads(self.path.read_bytes());assert row['fixture_only'] and row['intent_key']==intent_key and row['run_id']==str(self.run) and row['project_id']==str(self.project)
        observation=self.path.with_name('status.json');assert not observation.exists(),'one original status observation only'
        with observation.open('x',encoding='utf-8') as f:json.dump(dict(original_intent_key=intent_key,native_status_worker_pid=os.getpid(),submit_worker_pid=row['native_submit_worker_pid'],fixture_only=True),f)
        return DiscoveryBatch(hits=row['hits'],charge=Decimal(row['charge']),billing_event_id=row['billing_event_id'])

@celery_app.task(name='buyeros.execute_intent',acks_late=True)
def execute_fixture_intent(intent_key,workspace_id,generation):
    from buyeros_worker.tasks import execute_intent_sync
    return execute_intent_sync(intent_key,workspace_id,generation,search_adapter=JournalSearchFixture(),environment='test',checkpoint_dsn=os.environ['BUYEROS_CHECKPOINT_DATABASE_URL'])
