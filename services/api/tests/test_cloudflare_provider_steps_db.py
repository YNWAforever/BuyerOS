"""Real owned PostgreSQL provider receipts; fictional adapters, never live verification."""
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest
from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.test_cloudflare_runtime_control_db import worker_runtime, seed_envelope
from tests.test_cloudflare_local_steps_db import seed_project

LIMITS = {'query_rounds': 3, 'max_queries_per_run': 12, 'max_results': 300,
          'max_pages': 200, 'max_page_bytes': 2097152, 'max_duration_seconds': 1800,
          'max_model_tokens': 100000, 'provider_concurrency': 4}


def provider_module():
    from buyeros_api.execution import step_runner
    assert callable(getattr(step_runner, 'execute_provider_step', None)), 'CF04 bounded provider entrypoint missing'
    return step_runner


def seed_research(dsn, epoch, *, query_count=1):
    from buyeros_api.db.icp import canonical_hash
    from buyeros_api.services.budget_service import _period
    envelope = seed_envelope(dsn, epoch, event_type='run.discover')
    project, actor, member = seed_project(dsn, envelope.workspace_id)
    icp, run, requirement = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    content = {'markets': ['HK'], 'languages': ['en'], 'buyer_types': ['distributor'],
               'requirements': [{'id': str(requirement), 'category': 'must', 'hard_exclusion': False, 'text': 'industrial sensors'}]}
    queries = [{'id': f'{i+1:024x}', 'query': 'industrial sensors distributor', 'market': 'HK', 'language': 'en',
                'role': 'distributor', 'requirement_id': str(requirement), 'round': 1,
                'filters': {'market': 'HK', 'language': 'en'}} for i in range(query_count)]
    snapshot = {'actor_id': str(actor), 'offer_revision': 1, 'icp_content_hash': canonical_hash(content),
                'capability': {'provider': 'fixture', 'price_version': 'fixture-price-v1', 'verified_filters': ['market', 'language'], 'markets': ['HK'], 'languages': ['en']},
                'query_plan': {'schema': 'query-plan.v1', 'queries': queries, 'rationale_summary': 'Fictional test only'}}
    start, end, period = _period(None)
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,basis_offer_revision,approved_at,approved_by) VALUES(%s,%s,%s,1,%s::jsonb,%s,1,now(),%s)",
                   (icp, envelope.workspace_id, project, json.dumps(content), canonical_hash(content), actor))
        db.execute("UPDATE projects SET active_icp_version_id=%s WHERE id=%s", (icp, project))
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) "
                   "VALUES(%s,%s,'project',%s,%s,'account_research','permitted','fictional-only','fixture','fixture','{HK}',now()+interval '1 day',1,%s)",
                   (uuid.uuid4(), envelope.workspace_id, project, envelope.workspace_id, actor))
        db.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,target_companies,max_cost,execution_snapshot,usage_counters) VALUES(%s,%s,%s,%s,'queued',%s::jsonb,100,2,%s::jsonb,'{}'::jsonb)",
                   (run, envelope.workspace_id, project, icp, json.dumps(LIMITS), json.dumps(snapshot)))
        db.execute("INSERT INTO run_events(id,workspace_id,run_id,sequence,event_type,payload) VALUES(%s,%s,%s,1,'run.queued','{}'::jsonb)", (uuid.uuid4(), envelope.workspace_id, run))
        for scope, scope_id, category in (('workspace', envelope.workspace_id, 'all'), ('project', project, 'all'), ('run', run, 'all'), ('category', project, 'discovery')):
            db.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,approved_limit,settled_spend) VALUES(%s,%s,%s,%s,%s,'USD',%s,%s,%s,2,0)",
                       (uuid.uuid4(), envelope.workspace_id, scope, scope_id, category, period, start, end))
        db.execute("UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s", (json.dumps({'run_id': str(run)}), envelope.outbox_id))
    return {'envelope': envelope, 'run': run, 'actor': actor, 'project': project, 'icp': icp, 'dsn': dsn}


class SearchFixture:
    test_only = True
    provider = 'fixture'
    price_version = 'fixture-price-v1'
    quoted_upper_bound = Decimal('0.100000')
    retention_seconds = 86400
    status_nonbillable = True

    def __init__(self, case, *, timeout=False, hits=1):
        self.case, self.timeout, self.hits = case, timeout, hits
        self.calls, self.status_calls = 0, 0
        self.accepted = {}

    async def search(self, query, *, market, language, limit, intent_key):
        from buyeros_api.execution.discovery_runner import DiscoveryBatch
        self.calls += 1
        assert 0 < limit <= 50, 'canonicalization must be a bounded unit'
        with psycopg.connect(self.case['dsn'], autocommit=True) as db:
            db.execute("SELECT id FROM search_runs WHERE id=%s FOR UPDATE NOWAIT", (self.case['run'],))
            db.execute("SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT", (self.case['envelope'].outbox_id,))
        batch = DiscoveryBatch(hits=[{'url': f'https://fixture.invalid/{index}', 'legal_name': f'Fictional sensor distributor {index}',
                                     'registry_id': f'FIXTURE-{index}', 'excerpt': 'Distributes industrial sensors.', 'language': 'en', 'external_ref': f'fictional-{index}'}
                                    for index in range(min(limit, self.hits))],
                               charge=Decimal('0.050000'), billing_event_id='fictional-bill:'+intent_key)
        self.accepted[intent_key] = batch
        if self.timeout:
            raise TimeoutError('fictional response lost after acceptance')
        return batch

    async def status(self, intent_key):
        self.status_calls += 1
        return self.accepted.get(intent_key)


def run_provider(envelope, *, adapter=None, key='start', checkpoint_dsn=None, seconds=60):
    module = provider_module()
    from buyeros_api.services.worker_execution import create_execution_engine
    async def run():
        engine = create_execution_engine()
        try:
            return await module.execute_provider_step(engine, envelope, key, deadline=datetime.now(timezone.utc)+timedelta(seconds=seconds),
                adapter=adapter, checkpoint_dsn=checkpoint_dsn, environment='test')
        finally:
            await engine.dispose()
    return asyncio.run(run())


def seed_contact(dsn, epoch, count=3):
    from buyeros_api.services.budget_service import ensure_period_accounts, reserve_operation
    from buyeros_api.services.worker_execution import create_execution_engine
    from buyeros_api.services.quote_service import quote_hash
    from buyeros_api.db.session import tenant_session
    envelope = seed_envelope(dsn, epoch, event_type='contact.lookup')
    project, actor, member = seed_project(dsn, envelope.workspace_id)
    job, quote = uuid.uuid4(), uuid.uuid4()
    maximum = Decimal('0.300000') * count
    buyers = [(uuid.uuid4(), uuid.uuid4(), uuid.uuid4()) for _ in range(count)]
    resolved = [{'buyer_id': str(b), 'company_id': str(c), 'buyer_version': 1, 'eligible': True} for b, c, _ in buyers]
    with psycopg.connect(dsn, autocommit=True) as db:
        for b, c, _ in buyers:
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fictional','Fictional')", (c, envelope.workspace_id))
            db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)", (b, envelope.workspace_id, project, c))
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) VALUES(%s,%s,'project',%s,%s,'contact_research','permitted','fictional','fixture','fixture','{HK}',now()+interval '1 day',1,%s)", (uuid.uuid4(), envelope.workspace_id, project, envelope.workspace_id, actor))
    async def reserve():
        engine = create_execution_engine()
        try:
            async with tenant_session(engine, envelope.workspace_id) as session:
                await ensure_period_accounts(session, envelope.workspace_id, project, None, 'contact_lookup')
            with psycopg.connect(dsn, autocommit=True) as db:
                db.execute("UPDATE budget_accounts SET approved_limit=2 WHERE workspace_id=%s", (envelope.workspace_id,))
            async with tenant_session(engine, envelope.workspace_id) as session:
                return await reserve_operation(session, job, {'workspace_id': envelope.workspace_id, 'project_id': project, 'category': 'contact_lookup'}, maximum, 'USD', 'fixture-price-v1')
        finally:
            await engine.dispose()
    reservation = asyncio.run(reserve())
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute("INSERT INTO enrichment_quotes(id,workspace_id,project_id,actor_id,purpose,selection,request_hash,quote_hash,price_version,max_cost,status,adapter_version,roles,eligibility,contact_type) VALUES(%s,%s,%s,%s,'contact_research',%s::jsonb,%s,%s,'fixture-price-v1',%s,'consumed','contact-fixture-v1','[\"Procurement manager\"]'::jsonb,%s::jsonb,'business_email')", (quote, envelope.workspace_id, project, actor, json.dumps({'resolved': resolved}), 'a'*64, 'b'*64, maximum, json.dumps(resolved)))
        db.execute("INSERT INTO enrichment_jobs(id,workspace_id,quote_id,reservation_id,state) VALUES(%s,%s,%s,%s,'reserved')", (job, envelope.workspace_id, quote, reservation))
        for b, _, op in buyers:
            db.execute("INSERT INTO provider_operations(id,workspace_id,job_id,buyer_id,intent_key,capability,input_hash,status) VALUES(%s,%s,%s,%s,%s,'contact',%s,'intent')", (op, envelope.workspace_id, job, b, f'contact:{job}:{b}', quote_hash({'quote_hash': 'b'*64, 'buyer_id': str(b), 'roles': ['Procurement manager'], 'contact_type': 'business_email'})))
        db.execute("UPDATE outbox_events SET intent_key=%s,payload=%s::jsonb WHERE id=%s", (f'contact.lookup:{job}', json.dumps({'workspace_id': str(envelope.workspace_id), 'job_id': str(job)}), envelope.outbox_id))
    return {'envelope': envelope, 'project': project, 'actor': actor, 'job': job, 'quote': quote, 'dsn': dsn}


def contact_adapter(case):
    from buyeros_api.providers.base import FixtureProviderAdapter, Money, ProviderCapability
    capability = ProviderCapability(provider='fixture', adapter_version='contact-fixture-v1', service='contact', markets=frozenset({'HK'}), languages=frozenset({'en'}), roles=frozenset({'Procurement manager'}), auth_model='fixture', pricing_version='fixture-price-v1', max_liability=Money(Decimal('0.300000')), idempotency='verified', status='verified', callback='unsupported', cancel='unsupported', retention='fixture-only', verified_at=datetime.now(timezone.utc), source_urls=('https://fixture.invalid/capability',))
    class ContactFixture(FixtureProviderAdapter):
        async def submit(self, intent):
            with psycopg.connect(case['dsn'], autocommit=True) as db:
                db.execute("SELECT id FROM enrichment_jobs WHERE id=%s FOR UPDATE NOWAIT", (case['job'],))
                db.execute("SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT", (case['envelope'].outbox_id,))
            return await super().submit(intent)
    return ContactFixture(capability, environment='test')


def test_checkpoint_saver_rejects_owner_login(migrated, worker_runtime):
    from buyeros_api.execution.checkpoints import open_checkpoint_saver
    async def run():
        with pytest.raises(RuntimeError, match='worker role catalog proof'):
            async with open_checkpoint_saver(migrated, uuid.uuid4()):
                pytest.fail('owner checkpoint login was accepted')
    asyncio.run(run())


@pytest.mark.parametrize('mutation', ['revoked', 'viewer', 'missing_actor'])
def test_contact_rechecks_admitting_actor_before_submission(migrated, worker_runtime, mutation):
    case = seed_contact(migrated, worker_runtime[1])
    adapter = contact_adapter(case)
    with psycopg.connect(migrated, autocommit=True) as db:
        if mutation == 'revoked':
            db.execute("UPDATE memberships SET active=false WHERE user_id=%s", (case['actor'],))
        elif mutation == 'viewer':
            db.execute("UPDATE memberships SET roles='{viewer}' WHERE user_id=%s", (case['actor'],))
        else:
            db.execute("UPDATE enrichment_quotes SET actor_id=NULL WHERE id=%s", (case['quote'],))
    result = run_provider(case['envelope'], adapter=adapter)
    assert (result.state, result.code) == ('blocked', 'ACTOR_CHANGED')
    assert adapter.submit_count == 0
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM provider_operations WHERE job_id=%s AND status='intent'", (case['job'],)).fetchone()[0] == 3


def test_contact_resumes_one_operation_per_receipt_without_releasing_unknown_hold(migrated, worker_runtime):
    case = seed_contact(migrated, worker_runtime[1])
    adapter = contact_adapter(case)
    first = run_provider(case['envelope'], adapter=adapter)
    assert first.state == 'continue' and adapter.submit_count == 1
    assert run_provider(case['envelope'], adapter=adapter) == first and adapter.submit_count == 1
    second = run_provider(case['envelope'], key=first.next_step_key, adapter=adapter)
    assert second.state == 'continue' and adapter.submit_count == 2
    last = run_provider(case['envelope'], key=second.next_step_key, adapter=adapter)
    assert last.state == 'reconcile' and adapter.submit_count == 3
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE operation_id=%s", (case['job'],)).fetchone() == ('active', Decimal('0.900000'))
        assert db.execute("SELECT count(*) FROM cost_events WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (case['envelope'].outbox_id,)).fetchone()[0] == 3


def test_api_deadline_after_possible_acceptance_requires_reconciliation(migrated, worker_runtime, monkeypatch):
    case = seed_research(migrated, worker_runtime[1])
    accepted = None
    class SlowAcceptance(SearchFixture):
        async def search(self, *args, **kwargs):
            batch = await super().search(*args, **kwargs)
            accepted.set()
            await asyncio.sleep(60)
            return batch
    adapter = SlowAcceptance(case)
    # Inject expiry at the acceptance boundary, independently of DB startup speed.
    original_wait_for = asyncio.wait_for
    async def expire_after_acceptance(awaitable, timeout):
        nonlocal accepted
        if getattr(awaitable, '__qualname__', '') != 'execute_claimed':
            return await original_wait_for(awaitable, timeout)
        accepted = asyncio.Event()
        task = asyncio.create_task(awaitable)
        try:
            await original_wait_for(accepted.wait(), 10)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        raise TimeoutError('fixture native unit expired after acceptance')
    monkeypatch.setattr(asyncio, 'wait_for', expire_after_acceptance)
    result = run_provider(case['envelope'], adapter=adapter)
    assert (result.state, result.code) == ('reconcile', 'PROVIDER_UNKNOWN')
    assert run_provider(case['envelope'], adapter=adapter) == result and adapter.calls == 1
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone() == ('active', Decimal('0.100000'))


def test_legacy_finalize_is_fenced_after_runtime_switch(migrated, worker_runtime, monkeypatch):
    from buyeros_api.api.worker_schemas import JobEnvelope
    from buyeros_api.execution.config import get_settings
    from buyeros_api.execution.domain_executor import StaleFenced
    from buyeros_api.execution.provider_context import execution_scope, LegacyExecution
    from buyeros_api.execution.discovery_runner import execute_discovery
    from buyeros_api.services.worker_execution import create_execution_engine
    case = seed_research(migrated, worker_runtime[1])
    monkeypatch.setenv('BUYEROS_CELERY_EXECUTION_ENABLED', 'true')
    get_settings.cache_clear()
    with psycopg.connect(migrated, autocommit=True) as db:
        epoch = db.execute("UPDATE worker_runtime_control SET backend='celery',epoch=epoch+1 RETURNING epoch").fetchone()[0]
        db.execute("UPDATE outbox_events SET runtime_backend='celery',runtime_epoch=%s WHERE id=%s", (epoch, case['envelope'].outbox_id))
        intent = db.execute("SELECT intent_key FROM outbox_events WHERE id=%s", (case['envelope'].outbox_id,)).fetchone()[0]
    class SwitchDuringAcceptance(SearchFixture):
        async def search(self, *args, **kwargs):
            batch = await super().search(*args, **kwargs)
            with psycopg.connect(migrated, autocommit=True) as db:
                db.execute("UPDATE worker_runtime_control SET backend='cloudflare',epoch=epoch+1,active_owner=NULL,active_until=NULL")
            return batch
    adapter = SwitchDuringAcceptance(case)
    async def run():
        engine = create_execution_engine()
        try:
            legacy = LegacyExecution(JobEnvelope(**{**case['envelope'].model_dump(), 'runtime_epoch': epoch}))
            with execution_scope(legacy), pytest.raises(StaleFenced):
                await execute_discovery(engine, case['envelope'].workspace_id, intent, 1, adapter=adapter, environment='test')
        finally:
            await engine.dispose()
    try:
        asyncio.run(run())
    finally:
        get_settings.cache_clear()
    assert adapter.calls == 1
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM source_documents WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone()[0] == 0
        assert db.execute("SELECT status FROM provider_operations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone()[0] == 'submitting'
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone() == ('active', Decimal('0.100000'))


def test_arbitrary_continuation_cannot_skip_server_step(migrated, worker_runtime):
    case = seed_contact(migrated, worker_runtime[1])
    adapter = contact_adapter(case)
    first = run_provider(case['envelope'], adapter=adapter)
    assert first.state == 'continue'
    denied = run_provider(case['envelope'], key='step:999', adapter=adapter)
    assert (denied.state, denied.code) == ('blocked', 'INVALID_INTENT')
    assert adapter.submit_count == 1
    assert run_provider(case['envelope'], key=first.next_step_key, adapter=adapter).state == 'continue'


@pytest.mark.parametrize('mutation,code', [('actor', 'ACTOR_CHANGED'), ('profile', 'POLICY_CHANGED'), ('policy', 'POLICY_CHANGED')])
def test_fit_continuation_rechecks_current_authority(migrated, worker_runtime, mutation, code):
    case = seed_research(migrated, worker_runtime[1])
    assert run_provider(case['envelope'], adapter=SearchFixture(case)).state == 'done'
    fit = claim_ready(migrated, case['envelope'], 'run.fit')
    with psycopg.connect(migrated, autocommit=True) as db:
        if mutation == 'actor':
            db.execute("UPDATE memberships SET active=false WHERE user_id=%s", (case['actor'],))
        elif mutation == 'profile':
            db.execute("UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s", (case['project'],))
        else:
            db.execute("UPDATE policy_decisions SET expires_at=now()-interval '1 minute' WHERE workspace_id=%s", (fit.workspace_id,))
    result = run_provider(fit, checkpoint_dsn=worker_runtime[0])
    assert (result.state, result.code) == ('blocked', code)
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM fit_assessments WHERE run_id=%s", (case['run'],)).fetchone()[0] == 0
        assert db.execute("SELECT status,stage FROM search_runs WHERE id=%s", (case['run'],)).fetchone() == ('partial', 'fit_review_required')


def claim_ready(dsn, envelope, event_type):
    with psycopg.connect(dsn, autocommit=True) as db:
        row = db.execute("SELECT id FROM outbox_events WHERE workspace_id=%s AND event_type=%s AND state='ready' ORDER BY created_at LIMIT 1", (envelope.workspace_id, event_type)).fetchone()
        assert row is not None
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=1,runtime_backend='cloudflare',runtime_epoch=%s WHERE id=%s", (envelope.runtime_epoch, row[0]))
    return envelope.model_copy(update={'outbox_id': row[0]})


def test_accepted_then_lost_response_keeps_hold_and_uses_status_only(migrated, worker_runtime):
    provider_module()
    case = seed_research(migrated, worker_runtime[1])
    adapter = SearchFixture(case, timeout=True)
    result = run_provider(case['envelope'], adapter=adapter)
    assert result.state == 'reconcile' and result.code == 'PROVIDER_UNKNOWN'
    assert run_provider(case['envelope'], adapter=adapter) == result
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT state,upper_bound,remaining_hold FROM budget_reservations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone() == ('active', Decimal('0.100000'), Decimal('0.100000'))
        assert db.execute("SELECT count(*) FROM cost_events WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone()[0] == 0
    reconcile = claim_ready(migrated, case['envelope'], 'research.reconcile')
    assert run_provider(reconcile, adapter=adapter).state == 'done'
    assert (adapter.calls, adapter.status_calls) == (1, 1)
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT state,remaining_hold FROM budget_reservations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone() == ('settled', Decimal('0.000000'))
        assert db.execute("SELECT kind,amount FROM cost_events WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone() == ('commit', Decimal('0.050000'))
        assert db.execute("SELECT count(*) FROM cost_events WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone()[0] == 1


def test_new_generation_cannot_resubmit_unknown_operation(migrated, worker_runtime):
    provider_module()
    case = seed_research(migrated, worker_runtime[1])
    adapter = SearchFixture(case, timeout=True)
    assert run_provider(case['envelope'], adapter=adapter).state == 'reconcile'
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE outbox_events SET state='dispatched',fencing_generation=2 WHERE id=%s", (case['envelope'].outbox_id,))
    run_provider(case['envelope'].model_copy(update={'generation': 2}), adapter=adapter)
    assert adapter.calls == 1 and adapter.status_calls == 0
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*),min(state) FROM budget_reservations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone() == (1, 'active')


def test_restart_shares_twelve_query_two_hundred_page_and_original_deadline_limits(migrated, worker_runtime):
    provider_module()
    case = seed_research(migrated, worker_runtime[1], query_count=13)
    started = datetime.now(timezone.utc)-timedelta(seconds=100)
    with psycopg.connect(migrated, autocommit=True) as db:
        db.execute("UPDATE search_runs SET status='running',usage_counters=%s::jsonb,first_dispatch_at=%s WHERE id=%s", (json.dumps({'queries': 11, 'pages': 199, 'rounds': 1}), started, case['run']))
        db.execute("UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s", (json.dumps({'run_id': str(case['run']), 'query_index': 11}), case['envelope'].outbox_id))
    adapter = SearchFixture(case, hits=0)
    assert run_provider(case['envelope'], adapter=adapter).state == 'done'
    successor = claim_ready(migrated, case['envelope'], 'run.discover')
    result = run_provider(successor, adapter=adapter)
    assert result.code == 'LIMIT_EXCEEDED'
    assert adapter.calls == 1
    with psycopg.connect(migrated) as db:
        usage, first = db.execute("SELECT usage_counters,first_dispatch_at FROM search_runs WHERE id=%s", (case['run'],)).fetchone()
        assert usage['queries'] == 12 and usage['pages'] == 200 and first == started
        assert db.execute("SELECT count(*) FROM budget_reservations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone()[0] == 1


@pytest.mark.parametrize('change', ['icp', 'membership', 'policy'])
def test_changed_icp_membership_or_policy_blocks_next_provider_step(migrated, worker_runtime, change):
    provider_module()
    case = seed_research(migrated, worker_runtime[1])
    with psycopg.connect(migrated, autocommit=True) as db:
        if change == 'icp': db.execute("UPDATE projects SET offer_revision=offer_revision+1 WHERE id=%s", (case['project'],))
        elif change == 'membership': db.execute("UPDATE memberships SET active=false WHERE user_id=%s", (case['actor'],))
        else: db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s", (case['envelope'].workspace_id,))
    adapter = SearchFixture(case)
    run_provider(case['envelope'], adapter=adapter)
    assert adapter.calls == 0
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM budget_reservations WHERE workspace_id=%s", (case['envelope'].workspace_id,)).fetchone()[0] == 0
        assert db.execute("SELECT status FROM search_runs WHERE id=%s", (case['run'],)).fetchone()[0] == 'failed'


def test_fit_checkpoint_resumes_one_buyer_and_stops_for_review(migrated, worker_runtime):
    provider_module()
    case = seed_research(migrated, worker_runtime[1])
    adapter = SearchFixture(case, hits=3)
    assert run_provider(case['envelope'], adapter=adapter).state == 'done'
    fit = claim_ready(migrated, case['envelope'], 'run.fit')
    first = run_provider(fit, checkpoint_dsn=worker_runtime[0])
    assert first.state == 'continue' and first.next_step_key is not None
    assert run_provider(fit, checkpoint_dsn=worker_runtime[0]) == first
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM fit_assessments WHERE run_id=%s", (case['run'],)).fetchone()[0] == 1
    current = first
    units = 1
    while current.state == 'continue':
        current = run_provider(fit, key=current.next_step_key, checkpoint_dsn=worker_runtime[0])
        units += 1
        assert units <= 3
    assert current.state == 'done' and adapter.calls == 1
    with psycopg.connect(migrated) as db:
        assert db.execute("SELECT count(*) FROM fit_assessments WHERE run_id=%s", (case['run'],)).fetchone()[0] == 3
        assert db.execute("SELECT status,stage FROM search_runs WHERE id=%s", (case['run'],)).fetchone() == ('completed', 'review')
        assert db.execute("SELECT count(*) FROM human_reviews WHERE workspace_id=%s", (fit.workspace_id,)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM worker_steps WHERE outbox_id=%s", (fit.outbox_id,)).fetchone()[0] == 3
