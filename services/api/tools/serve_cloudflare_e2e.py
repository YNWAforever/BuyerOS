"""Strict disposable native API fixture for the actual Cloudflare staff journey.

Uses fictional OIDC, bounded search and existing-contact input. No production
app fixture routes, credentials, provider acceptance or R2 verification.
"""
import asyncio
import json
import os
import uuid
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit

import psycopg
from fastapi import HTTPException

from tools import serve_e2e_fixture as fixture
from buyeros_api.api.app import create_app
from buyeros_api.services import worker_execution

original_seed = fixture.seed
original_execute = worker_execution.execute_step


class BrowserSearchFixture:
    test_only = True
    provider = 'fixture'
    price_version = 'fixture-price-v1'
    quoted_upper_bound = Decimal('0.100000')
    retention_seconds = 86400

    def __init__(self):
        self.accepted = {}

    async def search(self, query, *, market, language, limit, intent_key):
        from buyeros_api.execution.discovery_runner import DiscoveryBatch
        assert market == 'US' and language == 'en' and 1 <= limit <= 50
        batch = DiscoveryBatch(hits=[{
            'url': 'https://fixture.example.test/t30-industrial-buyer',
            'legal_name': 'T30 Fictional Industrial Buyer', 'registry_id': 'US-T30-FIXTURE-001',
            'excerpt': 'Fictional distributor lists industrial sensors in a public catalog.',
            'language': 'en', 'external_ref': 't30-fixture-buyer',
        }], charge=Decimal('0.050000'), billing_event_id=f'fixture-bill:{intent_key}')
        self.accepted[intent_key] = batch
        return batch

    async def status(self, intent_key):
        return self.accepted.get(intent_key)


def main():
    if os.environ.get('BUYEROS_STRICT_INTEGRATION') != '1' or os.environ.get('BUYEROS_TEST_DATABASE_URL'):
        raise RuntimeError('Cloudflare browser fixture requires a fresh owned cluster, no inherited DSN')
    adapter = BrowserSearchFixture()
    connection = {}
    barrier = {'enabled': False, 'hits': 0}
    released = asyncio.Event()
    from datetime import datetime, timezone
    from buyeros_api.providers.base import FixtureProviderAdapter, Money, ProviderCapability
    contact = FixtureProviderAdapter(ProviderCapability(provider='fixture', adapter_version='contact-fixture-v1', service='contact', markets=frozenset({'US'}), languages=frozenset({'en'}), roles=frozenset({'Procurement manager'}), auth_model='fixture', pricing_version='fixture-price-v1', max_liability=Money(Decimal('0.300000')), idempotency='verified', status='verified', callback='unsupported', cancel='unsupported', retention='fixture-only', verified_at=datetime.now(timezone.utc), source_urls=('https://fixture.invalid/capability',)), environment='test', outcome='timeout_after_acceptance')

    def seed(owner_dsn):
        # Combined browser fixture seeds research before contact's upserted budget.
        confirm = os.environ.get('BUYEROS_E2E_SEED_CONFIRM', '0')
        os.environ['BUYEROS_E2E_SEED_CONFIRM'] = '0'
        try:
            original_seed(owner_dsn)
        finally:
            os.environ['BUYEROS_E2E_SEED_CONFIRM'] = confirm
        with psycopg.connect(owner_dsn, autocommit=True) as db:
            if confirm == '1': fixture._seed_contact_budget(db)
            db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
            epoch = db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1 RETURNING epoch").fetchone()[0]
        parts = urlsplit(owner_dsn)
        worker_dsn = urlunsplit(parts._replace(netloc=f'buyeros_worker:test-only@127.0.0.1:{parts.port}'))
        connection.update(owner=owner_dsn, worker=worker_dsn, epoch=epoch)
        os.environ.update({'BUYEROS_EXECUTION_DATABASE_URL': worker_dsn,
            'BUYEROS_CLOUDFLARE_EXECUTION_ENABLED': 'true', 'BUYEROS_PAID_DISPATCH_ENABLED': 'true',
            'BUYEROS_WORKER_CURRENT_KEY_ID': 'fictional-key',
            'BUYEROS_WORKER_CURRENT_SECRET': 'fictional-cf05-secret-32-bytes-only'})
        from buyeros_api.execution.config import get_settings
        get_settings.cache_clear()

    async def execute(engine, envelope, step_key):
        with psycopg.connect(connection['owner']) as db:
            event = db.execute('SELECT event_type,payload FROM outbox_events WHERE id=%s AND workspace_id=%s', (envelope.outbox_id, envelope.workspace_id)).fetchone()
            progress = db.execute('SELECT processed FROM async_jobs WHERE id=%s', (event[1].get('job_id'),)).fetchone() if event and event[0]=='bulk.mutate' else None
        if barrier['enabled'] and progress and progress[0]>=50:
            barrier['hits']+=1
            await released.wait()
        selected = contact if event and event[0].startswith('contact.') else adapter
        return await original_execute(engine, envelope, step_key, adapter=selected,
            checkpoint_dsn=connection['worker'], environment='test')

    def app_factory():
        app = create_app()

        @app.post('/fixture/cloudflare/barrier/{enabled}', include_in_schema=False)
        async def set_barrier(enabled: bool):
            barrier['enabled'] = enabled
            if enabled: released.clear()
            else: released.set()
            return {'fixture_only': True, **barrier}

        @app.get('/fixture/cloudflare/bulk/{job_id}', include_in_schema=False)
        def bulk(job_id: uuid.UUID):
            with psycopg.connect(connection['owner']) as db:
                row=db.execute('SELECT status,processed,updated,conflicts FROM async_jobs WHERE id=%s AND workspace_id=%s', (job_id, fixture.WORKSPACE_ID)).fetchone()
                if row is None: raise HTTPException(404, 'fictional bulk job absent')
                receipts=db.execute("SELECT count(*) FROM worker_steps s JOIN outbox_events o ON o.id=s.outbox_id WHERE o.payload->>'job_id'=%s AND o.runtime_backend='cloudflare' AND s.outcome IS NOT NULL", (str(job_id),)).fetchone()[0]
            return {'status':row[0], 'processed':row[1], 'updated':row[2], 'conflicts':row[3], 'platform_receipts':receipts, 'barrier_hits':barrier['hits']}

        @app.get('/fixture/cloudflare/contact/{job_id}', include_in_schema=False)
        def contact_state(job_id: uuid.UUID):
            with psycopg.connect(connection['owner']) as db:
                job=db.execute('SELECT state FROM enrichment_jobs WHERE id=%s AND workspace_id=%s',(job_id, fixture.WORKSPACE_ID)).fetchone()
                if job is None: raise HTTPException(404, 'fictional contact job absent')
                hold=db.execute('SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(job_id,)).fetchone()
                ops=db.execute('SELECT status FROM provider_operations WHERE job_id=%s',(job_id,)).fetchall()
            return {'status':job[0], 'hold':str(hold[1]), 'hold_state':hold[0], 'operations':[r[0] for r in ops], 'fixture_submit_count':contact.submit_count}

        @app.get('/fixture/cloudflare/context', include_in_schema=False)
        def context():
            return {'fixture_only': True, 'origin': 'http://127.0.0.1:8000', 'epoch': connection['epoch']}

        @app.get('/fixture/cloudflare/state/{project_id}/{run_id}', include_in_schema=False)
        def state(project_id: uuid.UUID, run_id: uuid.UUID, draft_job_id: uuid.UUID | None = None):
            with psycopg.connect(connection['owner']) as db:
                run = db.execute('SELECT status FROM search_runs WHERE id=%s AND project_id=%s AND workspace_id=%s',
                    (run_id, project_id, fixture.WORKSPACE_ID)).fetchone()
                if run is None:
                    raise HTTPException(404, 'UI-created run not found')
                receipts = db.execute("SELECT count(*) FROM worker_steps s JOIN outbox_events o ON o.id=s.outbox_id AND o.workspace_id=s.workspace_id WHERE s.workspace_id=%s AND o.runtime_backend='cloudflare' AND o.runtime_epoch=%s AND s.outcome IS NOT NULL AND (o.payload->>'run_id'=%s OR o.payload->>'job_id'=%s)", (fixture.WORKSPACE_ID, connection['epoch'], str(run_id) if not draft_job_id else None, str(draft_job_id) if draft_job_id else None)).fetchone()[0]
                if draft_job_id:
                    job = db.execute("SELECT status,command FROM async_jobs WHERE id=%s AND project_id=%s AND operation='generateDraft'", (draft_job_id, project_id)).fetchone()
                    if job is None:
                        raise HTTPException(404, 'UI-created draft job not found')
                    draft = db.execute("SELECT d.id,r.content->>'grounding_status' FROM outreach_drafts d JOIN draft_revisions r ON r.draft_id=d.id AND r.workspace_id=d.workspace_id AND r.revision_number=1 WHERE d.id=%s AND d.project_id=%s",
                        (job[1].get('result_draft_id'), project_id)).fetchone() if job[1].get('result_draft_id') else None
                    return {'transport': 'actual-local-cloudflare', 'platform_receipts': receipts,
                            'job_id': str(draft_job_id), 'status': job[0],
                            'draft_id': str(draft[0]) if draft else None, 'grounding_status': draft[1] if draft else None}
                return {'transport': 'actual-local-cloudflare', 'platform_receipts': receipts,
                    'run_id': str(run_id), 'status': run[0],
                    'evidence': db.execute('SELECT count(*) FROM evidence WHERE run_id=%s', (run_id,)).fetchone()[0],
                    'buyers': db.execute('SELECT count(*) FROM project_buyers WHERE project_id=%s', (project_id,)).fetchone()[0],
                    'fit_verdicts': [r[0] for r in db.execute('SELECT verdict FROM fit_assessments WHERE run_id=%s', (run_id,)).fetchall()],
                    'published': [str(r[0]) for r in db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND fencing_generation>0 AND event_type='run.discover' AND payload->>'run_id'=%s", (fixture.WORKSPACE_ID, str(run_id))).fetchall()]}
        return app

    fixture.seed = seed
    fixture.create_app = app_factory
    worker_execution.execute_step = execute
    fixture.main()


if __name__ == '__main__':
    main()
