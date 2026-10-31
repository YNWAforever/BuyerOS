"""Paid conversation receipt protocol on forced RLS with synthetic provider IO only."""
import asyncio
import hashlib
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import Money, ProviderCapability
from buyeros_api.providers.registry import ProviderRegistration
from buyeros_api.providers.live_model import canonical_json
from buyeros_api.providers.model_receipts import PostgresModelReceipts
from buyeros_api.services import conversation_admission as service
from buyeros_api.services.conversation_reply import resolve_sources
from tests.conftest import runtime_role_dsn
from tests.test_conversation_reply_db import conversation_api, enabled, api, SOURCE, PATH, DOCUMENT, PROFILE
from tests.test_buyer_review_db import WORKSPACE_A, WORKSPACE_B, PROJECT_A, PROJECT_B, OPERATOR, VIEWER, _h

WS, PROJECT, ACTOR = uuid.UUID(WORKSPACE_A), uuid.UUID(PROJECT_A), uuid.uuid5(uuid.NAMESPACE_URL, OPERATOR)


@pytest.fixture
def paid_case(conversation_api, monkeypatch):
    client, dsn = conversation_api
    from buyeros_api.providers import base
    from buyeros_api.settings import get_settings
    from buyeros_api.execution.config import get_settings as dispatch_settings
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED', 'true')
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED', 'true')
    monkeypatch.setenv('BUYEROS_OPENCODE_API_KEY', 'synthetic-conversation-no-real-key')
    get_settings.cache_clear(); dispatch_settings.cache_clear()
    monkeypatch.setattr(base, 'SELECTED_LIVE_PROVIDERS', frozenset({'opencode-go'}))
    route = replace(service.ROUTE, route_id='conversation-grounded.v1')
    cap = ProviderCapability('opencode-go', 'conversation-test.v1', 'model', frozenset({'US'}),
        frozenset({'en','zh-HK'}), frozenset({'company'}), 'server-only', 'conversation-test-price-v1',
        Money(Decimal('0.100000')), 'verified', 'verified', 'unsupported', 'unsupported', 'one-day',
        datetime.now(timezone.utc), ('https://opencode.ai/go',))
    item = ProviderRegistration(cap, lambda: None, ('synthetic:conversation-only',), model_route=route,
        model_id='synthetic-model', policy_account_reference='synthetic-conversation-account')
    monkeypatch.setattr(service, 'ROUTE', route); monkeypatch.setattr(service, 'REGISTRATION', item)
    from tests.policy_activation_fixtures import approve_research_fixture
    approve_research_fixture(dsn, WORKSPACE_A, PROJECT_A, domains=(), model=item.policy_binding,
        terms_overrides={'allowed_sources': {'domains': [], 'document_ids': [DOCUMENT]}})
    def setup(session):
        from buyeros_api.services.budget_service import ensure_period_accounts
        return ensure_period_accounts(session, WS, PROJECT, None, 'conversation')
    run_db(dsn, setup)
    with psycopg.connect(dsn) as db:
        db.execute('UPDATE budget_accounts SET approved_limit=1 WHERE workspace_id=%s', (WS,))
        db.execute("UPDATE projects SET language_preferences=ARRAY['en','zh-HK'] WHERE id=%s", (PROJECT,))
    try:
        yield client, dsn, item
    finally:
        get_settings.cache_clear(); dispatch_settings.cache_clear()
        # Receipt FK/privacy history is cleaned only in this disposable fixture.
        with psycopg.connect(dsn) as db:
            db.execute('DELETE FROM model_receipts WHERE workspace_id=%s', (WS,))
            db.execute('DELETE FROM provider_operations WHERE workspace_id=%s', (WS,))


def run_db(dsn, work, *, workspace=WS):
    async def run():
        engine = create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine, workspace) as session:
                return await work(session)
        finally:
            await engine.dispose()
    return asyncio.run(run())


def prepare(dsn, key='synthetic-ask', **changes):
    async def work(session):
        grounding = await resolve_sources(session, workspace_id=WS, project_id=PROJECT, source_ids=[SOURCE], readonly=True)
        return await service.prepare_conversation(session, workspace_id=WS, project_id=PROJECT,
            actor_id=ACTOR, question='Which approved source should I review?', language='en', key=key,
            grounding=grounding, **changes)
    return run_db(dsn, work)


def ask(client, key='synthetic-ask', **changes):
    return client.post(PATH, headers={**_h(), 'Idempotency-Key': key}, json={
        'question': 'Which approved source should I review?', 'source_ids': [SOURCE], 'language': 'en', **changes})


def response(request):
    from buyeros_api.providers.conversation_model import validate_proposal
    proposal = {'text': 'Check this approved source before deciding.', 'status': 'needs_review', 'citations': [SOURCE]}
    return {'provider_ref': 'synthetic-receipt', 'model_id': request.model_id,
        'prompt_version': request.route.prompt_version, 'proposal': proposal,
        'assessment': validate_proposal(proposal, request.basis),
        'usage': {'input_tokens': 100, 'output_tokens': 40, 'total_tokens': 140}}


def store_for(engine, item):
    return PostgresModelReceipts(engine, WS, item.capability, model_id=item.model_id,
        route=item.model_route, policy_binding=item.policy_binding)


def test_atomic_prepare_claim_finish_replay_and_no_locks_during_provider_await(paid_case, monkeypatch):
    client, dsn, item = paid_case
    from buyeros_api.providers.opencode_model import OpenCodeGoModelClient
    calls = []
    async def complete(self, basis, route):
        calls.append(basis)
        # An independent connection observes COMMITTED claim + hold and can take
        # the operation/account locks. Network work never owns an open DB txn.
        with psycopg.connect(dsn) as db:
            db.execute("SET LOCAL lock_timeout='1s'")
            assert db.execute('SELECT state FROM model_receipts WHERE workspace_id=%s', (WS,)).fetchone() == ('submitting',)
            assert db.execute('SELECT status FROM provider_operations WHERE workspace_id=%s FOR UPDATE NOWAIT', (WS,)).fetchone() == ('submitting',)
            assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s FOR UPDATE NOWAIT', (WS,)).fetchone() == (Decimal('0.100000'),)
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", ('budget:'+str(WS),))
            lock=int.from_bytes(hashlib.sha256(('policy-gate:'+str(WS)).encode()).digest()[:8],'big',signed=True)
            db.execute('SELECT pg_advisory_xact_lock(%s)',(lock,))
            db.execute('SELECT id FROM offer_documents WHERE id=%s FOR UPDATE NOWAIT',(DOCUMENT,))
        from buyeros_api.providers.live_model import ModelRequest
        return response(ModelRequest('synthetic', basis, route, self.model_id, 'US', 'en', 'company'))
    monkeypatch.setattr(OpenCodeGoModelClient, 'complete', complete)
    first = ask(client)
    assert first.status_code == 200, first.text
    assert first.json()['data']['status'] == 'needs_review' and first.json()['data']['fixture'] is False
    assert first.json()['data']['citations'][0]['id'] == SOURCE
    assert first.headers['cache-control'] == 'no-store'
    assert ask(client).json()['data'] == first.json()['data']
    assert len(calls) == 1
    assert not {'run_id', 'buyer_id', 'company_id'} & calls[0].keys()
    assert ask(client, question='changed question').status_code == 409
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT state FROM model_receipts WHERE workspace_id=%s', (WS,)).fetchone() == ('received',)
        assert db.execute('SELECT remaining_hold,state FROM budget_reservations WHERE workspace_id=%s', (WS,)).fetchone() == (Decimal('0.100000'), 'active')
        assert db.execute('SELECT count(*) FROM cost_events WHERE workspace_id=%s', (WS,)).fetchone() == (0,)
        assert db.execute('SELECT event_type,state,lease_expires_at FROM outbox_events WHERE workspace_id=%s', (WS,)).fetchone() == ('conversation.model', 'done', None)


@pytest.mark.parametrize('outcome', ['timeout', 'invalid-citation', 'tools', 'cancelled'])
def test_unknown_or_cancelled_keeps_the_original_hold_and_never_resubmits(paid_case, monkeypatch, outcome):
    client, dsn, item = paid_case
    from buyeros_api.providers.opencode_model import OpenCodeGoModelClient
    calls = []
    async def complete(self, basis, route):
        calls.append(1)
        if outcome == 'timeout': raise TimeoutError('synthetic loss after acceptance')
        if outcome == 'cancelled': raise asyncio.CancelledError()
        from buyeros_api.providers.live_model import ModelRequest
        result = response(ModelRequest('synthetic', basis, route, self.model_id, 'US', 'en', 'company'))
        if outcome == 'invalid-citation': result['proposal']['citations'] = ['document:'+str(uuid.uuid4())]
        else: result['proposal']['tool_calls'] = [{'name': 'start_research'}]
        return result
    monkeypatch.setattr(OpenCodeGoModelClient, 'complete', complete)
    result = ask(client)
    assert result.status_code == 503, result.text
    assert result.json()['code'] == 'CONVERSATION_MODEL_UNAVAILABLE'
    assert ask(client).status_code == 503 and len(calls) == 1
    with psycopg.connect(dsn) as db:
        state = db.execute('SELECT state FROM model_receipts WHERE workspace_id=%s', (WS,)).fetchone()[0]
        assert state == ('submitting' if outcome == 'cancelled' else 'unknown')
        assert db.execute('SELECT count(*),sum(remaining_hold) FROM budget_reservations WHERE workspace_id=%s', (WS,)).fetchone() == (1, Decimal('0.100000'))


@pytest.mark.parametrize('gate', ['admission', 'dispatch', 'route', 'registration', 'capability', 'price', 'policy', 'budget', 'permission', 'source', 'foreign-project', 'foreign-workspace', 'unlicensed-fact'])
def test_every_gate_fails_before_any_provider_call_or_reservation(paid_case, monkeypatch, gate):
    client, dsn, item = paid_case
    from buyeros_api.providers.opencode_model import OpenCodeGoModelClient
    from buyeros_api.settings import get_settings
    from buyeros_api.execution.config import get_settings as dispatch_settings
    async def forbidden(*args, **kwargs): pytest.fail('closed gate reached provider')
    monkeypatch.setattr(OpenCodeGoModelClient, 'complete', forbidden)
    path, headers = PATH, {**_h(), 'Idempotency-Key': 'gates'}
    sources=[SOURCE]
    with psycopg.connect(dsn) as db:
        if gate == 'admission': monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','false'); get_settings.cache_clear()
        elif gate == 'dispatch': monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','false'); dispatch_settings.cache_clear()
        elif gate == 'route': monkeypatch.setattr(service,'ROUTE',replace(service.ROUTE,route_id=None))
        elif gate == 'registration': monkeypatch.setattr(service,'REGISTRATION',None)
        elif gate == 'capability': monkeypatch.setattr(service,'REGISTRATION',replace(item,capability=replace(item.capability,verified_at=None)))
        elif gate == 'price': monkeypatch.setattr(service,'REGISTRATION',replace(item,capability=replace(item.capability,max_liability=Money(Decimal('0.01')))))
        elif gate == 'policy': db.execute('DELETE FROM policy_activation_resolutions WHERE workspace_id=%s',(WS,))
        elif gate == 'budget': db.execute('UPDATE budget_accounts SET approved_limit=0 WHERE workspace_id=%s',(WS,))
        elif gate == 'permission': headers={**_h(VIEWER),'Idempotency-Key':'gates'}
        elif gate == 'source': db.execute('UPDATE projects SET offer_revision=2 WHERE id=%s',(PROJECT,))
        elif gate == 'unlicensed-fact':
            from psycopg.types.json import Jsonb
            from buyeros_api.db.icp import canonical_hash
            content=db.execute('SELECT content FROM icp_versions WHERE id=%s',(PROFILE,)).fetchone()[0]
            fact_id=str(uuid.uuid4())
            content['offer_facts'].append({'id':fact_id,'field':'notes','value':'Unlicensed manual fact',
                'provenance':'user_entered','approved':True})
            db.execute('UPDATE icp_versions SET content=%s,content_hash=%s WHERE id=%s',(Jsonb(content),canonical_hash(content),PROFILE))
            sources.append(f'fact:profile:{PROFILE}:{fact_id}')
        elif gate == 'foreign-project': path=PATH.replace(PROJECT_A,PROJECT_B)
        else: path=PATH.replace(WORKSPACE_A,WORKSPACE_B).replace(PROJECT_A,PROJECT_B)
    result = client.post(path, headers=headers, json={'question':'Review?','source_ids':sources,'language':'en'})
    assert result.status_code in {403,404,409,422,503}, result.text
    assert 'data' not in result.json()
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',(WS,)).fetchone() == (0,)
        assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(WS,)).fetchone() == (0,)


def test_concurrent_asks_and_replays_never_exceed_the_approved_budget(paid_case):
    _, dsn, item = paid_case
    with psycopg.connect(dsn) as db:
        db.execute('UPDATE budget_accounts SET approved_limit=0.30 WHERE workspace_id=%s',(WS,))
    async def race():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)),pool_size=12)
        async def one(key):
            try:
                async with tenant_session(engine,WS) as session:
                    grounding=await resolve_sources(session,workspace_id=WS,project_id=PROJECT,source_ids=[SOURCE], readonly=True)
                    return await service.prepare_conversation(session,workspace_id=WS,project_id=PROJECT,actor_id=ACTOR,
                        question='Review?',language='en',key=key,grounding=grounding)
            except ApiError as error:
                assert error.code=='BUDGET_LIMIT';return None
        try:
            return await asyncio.gather(*(one('race-'+str(i//2)) for i in range(20)))
        finally:await engine.dispose()
    results=asyncio.run(race())
    assert sum(result is not None for result in results)==6
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*),sum(remaining_hold) FROM budget_reservations WHERE workspace_id=%s',(WS,)).fetchone()==(3,Decimal('0.300000'))
        assert db.execute('SELECT count(*) FROM model_receipts WHERE workspace_id=%s',(WS,)).fetchone()==(3,)


@pytest.mark.parametrize('change',['revoked','stale','expired','policy','fence','hold','deadline','budget-frozen'])
def test_prepare_to_claim_rechecks_current_authority_and_retains_hold(paid_case, change):
    _, dsn, item=paid_case
    request,intent,ref,_=prepare(dsn)
    with psycopg.connect(dsn) as db:
        if change=='revoked':db.execute('UPDATE memberships SET active=false WHERE user_id=%s',(ACTOR,))
        elif change=='stale':db.execute('UPDATE projects SET offer_revision=2 WHERE id=%s',(PROJECT,))
        elif change=='expired':db.execute("UPDATE offer_documents SET retention_until=now()-interval '1s' WHERE id=%s",(DOCUMENT,))
        elif change=='policy':db.execute('DELETE FROM policy_activation_resolutions WHERE workspace_id=%s',(WS,))
        elif change=='fence':db.execute('UPDATE outbox_events SET fencing_generation=2 WHERE workspace_id=%s',(WS,))
        elif change=='budget-frozen':db.execute('UPDATE budget_accounts SET frozen=true WHERE workspace_id=%s',(WS,))
        elif change=='hold':db.execute('UPDATE budget_reservations SET remaining_hold=0.09 WHERE workspace_id=%s',(WS,))
        else:db.execute("UPDATE provider_operations SET deadline=now()-interval '1s' WHERE workspace_id=%s",(WS,))
    async def claim():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            store=store_for(engine,item)
            try:
                saved,claimed=await store.claim(intent)
                assert not claimed and saved['state'] in {'expired','redacted'}
            except (ValueError,ApiError):pass
        finally:await engine.dispose()
    asyncio.run(claim())
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT state FROM model_receipts WHERE id=%s',(ref,)).fetchone()==('prepared',)
        assert db.execute('SELECT remaining_hold>0 FROM budget_reservations WHERE workspace_id=%s',(WS,)).fetchone()==(True,)


def test_two_claims_submit_at_most_once_and_db_function_is_tenant_scoped(paid_case):
    _,dsn,item=paid_case
    request,intent,ref,_=prepare(dsn)
    async def race():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            store=store_for(engine,item)
            results=await asyncio.gather(store.claim(intent),store.claim(intent))
            assert sum(claimed for _,claimed in results)==1
            async with tenant_session(engine,uuid.UUID(WORKSPACE_B)) as session:
                assert await session.scalar(text("SELECT public.buyeros_transition_conversation_receipt(:id,'unknown',NULL,NULL)"),{'id':uuid.UUID(ref)}) is False
            await store.finish(ref,state='unknown')
            await store.finish(ref,state='received',response=response(request),digest=hashlib.sha256(canonical_json(response(request))).hexdigest())
            assert (await store.get(ref))['state']=='unknown'
        finally:await engine.dispose()
    asyncio.run(race())
    with psycopg.connect(dsn) as db:
        assert not db.execute("SELECT has_table_privilege('buyeros_api','model_receipts','UPDATE')").fetchone()[0]
        assert not db.execute("SELECT has_function_privilege('buyeros_worker','public.buyeros_transition_conversation_receipt(uuid,text,jsonb,text)','EXECUTE')").fetchone()[0]


def test_populated_migration_rollback_refuses_to_erase_receipt_or_hold(paid_case, monkeypatch):
    _,dsn,item=paid_case
    request,intent,ref,_=prepare(dsn)
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI,SERVICE_ROOT
    monkeypatch.setenv('BUYEROS_DATABASE_URL',dsn)
    from buyeros_api.settings import get_settings
    get_settings.cache_clear()
    cfg=Config(str(ALEMBIC_INI));cfg.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    with pytest.raises(RuntimeError,match='preserve conversation'):
        command.downgrade(cfg,'0056_policy_activation')
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('0059_conversation_connections',)
        assert db.execute('SELECT state FROM model_receipts WHERE id=%s',(ref,)).fetchone()==('prepared',)
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s',(WS,)).fetchone()==(Decimal('0.100000'),)
        assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='model_receipts'").fetchone()==(True,True)


def test_expired_conversation_document_erases_payload_but_preserves_hashes_and_hold(paid_case):
    _,dsn,item=paid_case
    request,intent,ref,_=prepare(dsn)
    with psycopg.connect(dsn) as db:
        before=db.execute('SELECT request_hash,contract_hash FROM model_receipts WHERE id=%s',(ref,)).fetchone()
        db.execute("UPDATE offer_documents SET retention_until=now()-interval '1s' WHERE id=%s",(DOCUMENT,))
    async def erase(session):
        from buyeros_api.services.receipt_retention import expire_provider_receipts
        return await expire_provider_receipts(session,now=datetime.now(timezone.utc),policy_version='synthetic-conversation.v1')
    assert run_db(dsn,erase)==[{'service':'model','id':ref}]
    with psycopg.connect(dsn) as db:
        row=db.execute('SELECT request_hash,contract_hash,request,redacted_at FROM model_receipts WHERE id=%s',(ref,)).fetchone()
        assert row[:2]==before and row[2]=={'redacted':True} and row[3] is not None
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE workspace_id=%s',(WS,)).fetchone()==(Decimal('0.100000'),)
