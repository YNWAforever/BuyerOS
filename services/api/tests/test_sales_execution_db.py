"""Task5 offline invariants; PostgreSQL cases below use only the owned allocator."""
import importlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
import pytest


def implementation():
    name = 'buyeros_api.execution.sales_tasks'
    assert importlib.util.find_spec(name), 'Task5 durable execution owner is missing'
    return importlib.import_module(name)


def test_parent_debit_enforces_actual_calls_concurrency_and_liability():
    m = implementation()
    parent = NS(max_calls=2, calls_started=0, max_concurrency=1, consumed_usd=Decimal('0'), upper_bound=Decimal('.2'))
    m.debit(parent, active=0, liability=Decimal('.1'))
    assert parent.calls_started == 1 and parent.consumed_usd == Decimal('.1')
    with pytest.raises(ValueError): m.debit(parent, active=1, liability=Decimal('.1'))
    assert parent.calls_started == 1
    m.debit(parent, active=0, liability=Decimal('.1'))
    with pytest.raises(ValueError): m.debit(parent, active=0, liability=Decimal('.1'))
    assert parent.calls_started == 2 and parent.consumed_usd == parent.upper_bound


@pytest.mark.parametrize('states,expected', [(['received','failed'],'partially_completed'),
    (['received','received'],'ready_for_review'), (['unknown','received'],'outcome_unknown'),
    (['queued','received'],'running'), (['failed','failed'],'failed')])
def test_no_output_completion_without_canonical_readback(states, expected):
    m = implementation()
    assert m.aggregate_state(states, cancelled=False) == expected
    assert m.aggregate_state(states, cancelled=False) != 'completed'


def test_arbitrary_approval_uuid_does_not_authorize():
    m = implementation()
    now = datetime.now(timezone.utc)
    scope = NS(workspace_id=uuid.uuid4(), project_id=uuid.uuid4(), actor_id=uuid.uuid4())
    task = NS(id=uuid.uuid4(), revision=3)
    approval = NS(workspace_id=scope.workspace_id, project_id=scope.project_id, actor_id=scope.actor_id,
        task_id=task.id, task_revision=3, fingerprint='a'*64, expires_at=now+timedelta(minutes=5), revoked=False)
    m.validate_review(approval, scope, task, 'a'*64, now)
    for field, bad in [('actor_id',uuid.uuid4()),('task_revision',2),('fingerprint','b'*64),('revoked',True),('expires_at',now)]:
        old = getattr(approval,field)
        setattr(approval,field,bad)
        with pytest.raises(ValueError): m.validate_review(approval,scope,task,'a'*64,now)
        setattr(approval,field,old)
    with pytest.raises(ValueError): m.validate_review(None,scope,task,'a'*64,now)


def test_default_registration_unselected_and_future_actions_unregistered():
    implementation()
    from buyeros_api.sales import actions
    assert actions.REGISTRATION is None
    for name in ['get_email_xverum','reports.export','documents.read','buyers.review']:
        with pytest.raises(ValueError): actions.action(name)


def test_mixed_drive_context_cannot_enter_sales_receipt():
    m = implementation()
    from tests.test_sales_model import sample
    from copy import deepcopy
    basis, _, _ = sample()
    value = deepcopy(basis)
    value['request']['context']['refs'].append(dict(value['request']['context']['refs'][0], kind='drive',retention_class='zero_content'))
    # Real sales receipt verifier, not a source spy: invalid basis must never be persistable.
    with pytest.raises(ValueError): m.validate_receipt_basis(value)


def test_recovery_never_resubmits_a_dispatched_child():
    m = implementation()
    for state in ['submitting','unknown']:
        assert m.recovery_state(state) == 'unknown'
    assert m.recovery_state('queued') == 'queued'
    assert m.recovery_state('received') == 'received'

@pytest.fixture
def runtime(monkeypatch):
    """Transaction/authority stubs only; this is NOT PostgreSQL acceptance."""
    import asyncio
    from contextlib import asynccontextmanager
    from dataclasses import replace
    from buyeros_api.sales.context import empty_context, digest
    from buyeros_api.sales.model import ROUTE
    from buyeros_api.sales.contracts import Scope, ActionProposal
    from buyeros_api.execution import sales_tasks as m
    # This fixture tests execution with transaction stubs, never canonical DB storage.
    monkeypatch.setattr(m.actions,'SECTION_OWNER',None)
    context=empty_context()
    scope=Scope(workspace_id=uuid.uuid4(),project_id=uuid.uuid4(),actor_id=uuid.uuid4())
    row=NS(id=uuid.uuid4(),thread_id=uuid.uuid4(),skill_id='sales-quick',skill_version='1',
        arguments={'research_question':'SYNTHETIC'},source_refs=[],context_digest=context.digest,
        intake_history=[{'revision':1}],revision=1,state='ready_for_review',output_ids=[],pending_review=None)
    item=NS(model_id='synthetic-model',model_route=replace(ROUTE,route_id='sales-grounded.v1'),
        contract_hash='b'*64,capability=NS(max_liability=NS(amount=Decimal('.1')),pricing_version='synthetic-v1'))
    proposal=ActionProposal(id=uuid.uuid4(),capability='research.read',arguments={'refs':[],'purpose':'SYNTHETIC'},source_versions=[])
    async def task(*args,**kwargs):
        if state.revoked: raise ValueError('revoked actor')
        return row
    async def context_read(*args,**kwargs): return context
    async def config(*args): return item,'US','en'
    async def append(*args,**kwargs): pass
    class Result:
        def scalar_one_or_none(self): return state.review
    class Session:
        def __init__(self): self.added=[]
        async def execute(self,*args,**kwargs): return Result()
        async def flush(self): pass
        def add(self,item): self.added.append(item)
    state=NS(scope=scope,row=row,item=item,proposal=proposal,revoked=False,review=None,session=Session(),calls=0)
    monkeypatch.setattr(m.tasks,'task_row',task)
    monkeypatch.setattr(m.tasks,'append_event',append)
    monkeypatch.setattr(m,'resolve_context',context_read)
    monkeypatch.setattr(m,'configuration',config)
    async def held(*args): pass  # real budget hold acceptance is in owned PostgreSQL cases
    monkeypatch.setattr(m,'require_parent_hold',held)
    async def no_provider(*args):return 0
    monkeypatch.setattr(m,'provider_active',no_provider)
    monkeypatch.setattr(m,'cancel_provider_stages',held)
    async def unchanged(session,task,state):return state
    monkeypatch.setattr(m,'provider_task_state',unchanged)
    async def setup():
        _,plan,_,_,_,fingerprint=await m.prepare(state.session,scope,row,proposal)
        parent=NS(id=uuid.uuid4(),task_id=row.id,thread_id=row.thread_id,workspace_id=scope.workspace_id,
            project_id=scope.project_id,actor_id=scope.actor_id,review_id=uuid.uuid4(),task_revision=1,intake_revision=1,
            fingerprint=fingerprint,intake_hash=m.intake_hash(row),registration_hash=item.contract_hash,
            proposal=proposal.model_dump(mode='json'),plan=plan.model_dump(mode='json'),market='US',language='en',max_calls=len(plan.steps),
            max_concurrency=2,calls_started=0,upper_bound=Decimal('.1')*len(plan.steps),consumed_usd=Decimal(0),
            cancelled=False,unused_released=False,reservation_id=uuid.uuid4())
        state.parent=parent
        state.review=NS(id=parent.review_id,workspace_id=scope.workspace_id,project_id=scope.project_id,
            actor_id=scope.actor_id,task_id=row.id,task_revision=1,fingerprint=fingerprint,
            revoked=False,expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))
        state.steps=[]
        state.bases={}
        for planned in plan.steps:
            step_id=uuid.uuid4()
            basis=m.make_basis(m.request_for(row,context,item,step_id,planned.section),scope,context)
            step=NS(id=step_id,outbox_id=uuid.uuid4(),section=planned.section,state='queued',basis_hash=basis['basis_hash'],
                projection_hash=digest(m.wire_basis(basis)),liability=Decimal('.1'),claim_id=None,claimed_at=None,
                usage=None,result_digest=None,native_operation_id=None,definitely_unsubmitted=False)
            state.steps.append(step);state.bases[step_id]=basis
        async def locked(*args):
            step=next(s for s in state.steps if s.id==args[-1])
            return row,parent,step,state.steps
        monkeypatch.setattr(m,'locked',locked)
    asyncio.run(setup())
    state.hold=NS(id=state.parent.reservation_id,workspace_id=scope.workspace_id,
        operation_id=state.parent.id,upper_bound=state.parent.upper_bound,
        remaining_hold=state.parent.upper_bound,currency='USD',state='active')
    state.releases=0
    async def reservation(*args): return state.hold
    async def release(*args):
        state.releases+=1
        state.hold.remaining_hold=Decimal(0);state.hold.state='released'
    from buyeros_api.services import settlement
    monkeypatch.setattr(m,'parent_reservation',reservation)
    monkeypatch.setattr(settlement,'release_unsubmitted_operation',release)
    @asynccontextmanager
    async def transaction(*args):
        async with state.lock: yield state.session
    monkeypatch.setattr(m,'tenant_session',transaction)
    class Guard:
        def __init__(self,step):
            self.row=NS(id=step.outbox_id,event_type='sales.step',payload={'step_id':str(step.id)})
            self.envelope=NS(workspace_id=scope.workspace_id,outbox_id=step.outbox_id)
        async def guard(self,session): return True
    state.guard=Guard
    yield m,state


def test_review_uses_declared_parent_bounds(runtime):
    import asyncio
    m,s=runtime
    s.review=None
    review=asyncio.run(m.approve_step(s.session,s.scope,s.row.id,s.proposal,1,'synthetic-review'))
    assert review.max_concurrency==2 and review.max_calls<=8


def test_two_workers_claim_once_and_reconnect_starts_zero_work(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    async def complete(basis,item):
        s.calls+=1
        await asyncio.sleep(0)
        return synthetic_result(basis)
    monkeypatch.setattr(m.actions,'complete',complete)
    async def run():
        s.lock=asyncio.Lock()
        step=s.steps[0]
        results=await asyncio.gather(*(m.execute_step(None,step.id,workspace_id=s.scope.workspace_id,execution=s.guard(step)) for _ in range(2)))
        assert s.calls==1 and step.state=='received'
        assert s.parent.calls_started==1 and s.parent.consumed_usd==Decimal('.1')
        for _ in range(3): await m.execute_step(None,step.id,workspace_id=s.scope.workspace_id,execution=s.guard(step))
        assert s.calls==1
    asyncio.run(run())


def synthetic_result(basis):
    section=basis['request']['section']
    content={'summary':'SYNTHETIC','unknowns':[],'opportunities':[],'concerns':[]} if section=='summary' else {'findings':[]} if section=='findings' else {'opportunities':[],'concerns':[]}
    return {'proposal':{'kind':'research_report','section':section,'content':content,'citations':[],'complete':False},
        'usage':{'input_tokens':10,'output_tokens':10},'provider_ref':'synthetic-ref',
        'model_id':'synthetic-model','prompt_version':'sales-grounded.v1'}


def test_revoked_actor_before_dispatch_causes_no_external_call(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    s.revoked=True
    async def forbidden(*args): pytest.fail('revoked actor dispatched')
    monkeypatch.setattr(m.actions,'complete',forbidden)
    async def run():
        s.lock=asyncio.Lock()
        result=await m.execute_step(None,s.steps[0].id,workspace_id=s.scope.workspace_id,execution=s.guard(s.steps[0]))
        assert result.dispatch_state=='failed' and s.parent.calls_started==0
    asyncio.run(run())


def test_mixed_drive_rejected_by_actual_claim_and_receipt(runtime,monkeypatch):
    import asyncio
    from copy import deepcopy
    m,s=runtime
    drive={'id':str(uuid.uuid4()),'version':1,'kind':'drive','locator':'drive:synthetic','retention_class':'zero_content'}
    ident=uuid.uuid4()
    valid={'id':str(ident),'version':1,'kind':'document','locator':'document:'+str(ident),'retention_class':'durable'}
    s.row.source_refs=[valid,drive]
    s.parent.intake_hash=m.intake_hash(s.row)
    s.parent.proposal['source_versions']=[valid,drive]
    async def forbidden(*args): pytest.fail('Drive reached model transport')
    monkeypatch.setattr(m.actions,'complete',forbidden)
    async def run():
        s.lock=asyncio.Lock()
        step=s.steps[0]
        await m.execute_step(None,step.id,workspace_id=s.scope.workspace_id,execution=s.guard(step))
        assert step.state=='failed' and step.usage is None and s.calls==0
        step.state='submitting';step.claim_id=uuid.uuid4()
        bad=deepcopy(s.bases[step.id]);bad['request']['context']['refs'].extend([valid,drive])
        with pytest.raises(ValueError):
            await m.persist_result(s.session,step.id,step.claim_id,bad,synthetic_result(bad))
        assert step.usage is None and step.result_digest is None
    asyncio.run(run())


def test_claim_must_match_native_outbox(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    async def forbidden(*args): pytest.fail('foreign outbox dispatched')
    monkeypatch.setattr(m.actions,'complete',forbidden)
    async def run():
        s.lock=asyncio.Lock()
        with pytest.raises(ValueError,match='outbox'):
            await m.execute_step(None,s.steps[0].id,workspace_id=s.scope.workspace_id,execution=s.guard(s.steps[1]))
        assert s.parent.calls_started==0
    asyncio.run(run())


def test_native_identity_requires_registered_owner(runtime):
    import asyncio
    m,s=runtime
    s.row.arguments['buyer_id']=str(uuid.uuid4())
    with pytest.raises(ValueError,match='native'):
        asyncio.run(m.prepare(s.session,s.scope,s.row,s.proposal))


def test_production_bridge_uses_owned_http_and_content_free_receipt(runtime,monkeypatch):
    import asyncio,json,httpx
    m,s=runtime
    original=httpx.AsyncClient
    def transport(request):
        s.calls+=1
        body=json.loads(request.content)
        wire=json.loads(body['messages'][1]['content'])['untrusted_source_data']
        assert wire['step_id']==str(s.steps[0].id)
        assert body['parallel_tool_calls'] is False and body['tools']==[]
        result=synthetic_result(s.bases[s.steps[0].id])
        return httpx.Response(200,json={'id':'synthetic-ref','model':'synthetic-model',
            'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(result['proposal'])}}],
            'usage':{'prompt_tokens':10,'completion_tokens':10}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(transport)))
    monkeypatch.setenv('BUYEROS_OPENCODE_API_KEY','synthetic-not-a-real-key')
    async def run():
        s.lock=asyncio.Lock()
        step=s.steps[0]
        result=await m.execute_step(None,step.id,workspace_id=s.scope.workspace_id,execution=s.guard(step))
        assert result.dispatch_state=='received' and s.calls==1
        assert step.usage['usage']=={'input_tokens':10,'output_tokens':10,'cost':None}
        assert 'SYNTHETIC' not in json.dumps(step.usage) and step.result_digest
    asyncio.run(run())


def test_lost_response_keeps_hold_and_never_redispatches(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    async def lost(*args):
        s.calls+=1
        raise TimeoutError('synthetic accepted request with lost response')
    monkeypatch.setattr(m.actions,'complete',lost)
    async def run():
        s.lock=asyncio.Lock()
        step=s.steps[0]
        for _ in range(3): await m.execute_step(None,step.id,workspace_id=s.scope.workspace_id,execution=s.guard(step))
        assert s.calls==1 and step.state=='unknown' and s.parent.consumed_usd==Decimal('.1')
        assert s.row.state=='outcome_unknown'
    asyncio.run(run())


def test_actual_claims_respect_parent_concurrency(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    async def run():
        # Two claims consume the only slots, even across a worker restart.
        for step in s.steps[:2]:
            _,prepared=await m.claim(s.session,step.id,workspace_id=s.scope.workspace_id)
            assert prepared is not None
        # Replay consumes no call or additional money.
        _,prepared=await m.claim(s.session,s.steps[0].id,workspace_id=s.scope.workspace_id)
        assert prepared is None and s.parent.calls_started==2
        assert s.parent.consumed_usd==Decimal('.2')
        s.steps[0].state='unknown'
        assert s.parent.calls_started==2  # uncertainty does not return a slot/debit
    asyncio.run(run())


def test_cancellation_after_dispatch_preserves_liability(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    async def run():
        step=s.steps[0]
        await m.claim(s.session,step.id,workspace_id=s.scope.workspace_id)
        # Real cancellation service uses the parent query; supply the existing parent.
        class Result:
            def scalar_one_or_none(self): return s.parent
        async def execute(*args): return Result()
        async def children(*args): return s.steps
        monkeypatch.setattr(s.session,'execute',execute)
        monkeypatch.setattr(m,'children',children)
        result=await m.cancel_task(s.session,s.scope,s.row.id,s.row.revision)
        assert result.state=='cancel_requested'
        assert step.state=='submitting' and all(x.state=='cancelled' for x in s.steps[1:])
        assert s.parent.consumed_usd==Decimal('.1') and s.parent.cancelled
    asyncio.run(run())


def test_receipt_failure_and_recovery_readback_do_not_retry(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    async def run():
        step=s.steps[0]
        _,prepared=await m.claim(s.session,step.id,workspace_id=s.scope.workspace_id)
        basis,_,claim_id=prepared
        # Restart after committed claim but before/after external await is indistinguishable.
        assert await m.recover_outbox(s.session,NS(payload={'step_id':str(step.id)}))==(True,False,False)
        assert step.state=='unknown'
        # A late exact validated receipt resolves the same claim without another external call.
        await m.persist_result(s.session,step.id,claim_id,basis,synthetic_result(basis))
        assert step.state=='received' and s.parent.calls_started==1
        assert s.row.state!='completed'
        await m.recover_outbox(s.session,NS(payload={'step_id':str(step.id)}))
        assert step.state=='received'
    asyncio.run(run())


def test_one_failed_branch_produces_partial_completion(runtime):
    import asyncio
    m,s=runtime
    async def run():
        step=s.steps[0]
        s.steps[1].state='failed'
        _,prepared=await m.claim(s.session,step.id,workspace_id=s.scope.workspace_id)
        basis,_,claim_id=prepared
        await m.persist_result(s.session,step.id,claim_id,basis,synthetic_result(basis))
        assert s.row.state=='partially_completed' and not s.row.output_ids
    asyncio.run(run())


def test_human_review_rejects_changed_displayed_quote(runtime):
    import asyncio
    m,s=runtime
    s.review=None
    with pytest.raises(ValueError,match='quote'):
        asyncio.run(m.approve_step(s.session,s.scope,s.row.id,s.proposal,1,'synthetic-review',expected_fingerprint='c'*64))
    assert not s.session.added


def test_receipt_rejects_foreign_intake_section_and_scope(runtime):
    import asyncio
    from copy import deepcopy
    m,s=runtime
    async def run():
        step=s.steps[0]
        _,prepared=await m.claim(s.session,step.id,workspace_id=s.scope.workspace_id)
        basis,_,claim_id=prepared
        for key,value in [('step_id',str(uuid.uuid4())),('task_id',str(uuid.uuid4())),('section','findings')]:
            bad=deepcopy(basis);bad['request'][key]=value
            with pytest.raises(ValueError): await m.persist_result(s.session,step.id,claim_id,bad,synthetic_result(bad))
            assert step.usage is None
    asyncio.run(run())

# The cases below are authored for a fresh owned PostgreSQL allocator only.
# Do not run them against inherited DSNs, shared databases or SQLite.
@pytest.fixture
def execution_api(isolated_seeded,monkeypatch):
    """Retain all execution evidence until the owned clone is dropped, not row cleanup."""
    import asyncio,psycopg
    from fastapi.testclient import TestClient
    from tests import auth_fixtures as fx
    from tests.test_buyer_review_db import OPERATOR,REVIEWER,ADMIN,VIEWER,WORKSPACE_A
    from tests.conftest import runtime_role_dsn
    from buyeros_api.api import auth
    from buyeros_api.api.app import create_app
    from buyeros_api.api.jwks import JwksKeyCache
    from buyeros_api.api.verifier import TokenVerifier
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(isolated_seeded))
    monkeypatch.setenv('BUYEROS_AUTH_MODE','auth0')
    monkeypatch.setenv('BUYEROS_AUTH0_ISSUER',fx.ISSUER)
    monkeypatch.setenv('BUYEROS_AUTH0_AUDIENCE',fx.AUDIENCE)
    get_settings.cache_clear()
    cache=JwksKeyCache(lambda:asyncio.sleep(0,result=fx.jwks_document()),cache_seconds=300)
    monkeypatch.setattr(auth,'_verifier_from_settings',lambda:TokenVerifier(cache,issuer=fx.ISSUER,audience=fx.AUDIENCE))
    with psycopg.connect(isolated_seeded) as db:
        for subject,role in [(OPERATOR,'operator'),(REVIEWER,'reviewer'),(ADMIN,'workspace_admin'),(VIEWER,'viewer')]:
            user=uuid.uuid5(uuid.NAMESPACE_URL,subject)
            db.execute('INSERT INTO users(id,issuer,subject) VALUES(%s,%s,%s)',(user,fx.ISSUER,subject))
            db.execute('INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES(%s,%s,%s,%s,true)',
                (uuid.uuid4(),WORKSPACE_A,user,[role]))
    try:
        with TestClient(create_app()) as client:yield client
    finally:get_settings.cache_clear()


@pytest.fixture
def execution_pg(request,monkeypatch):
    import psycopg
    from dataclasses import replace
    from urllib.parse import urlsplit,urlunsplit
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.execution.engine import run_async,async_database_url
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.budget_service import ensure_period_accounts
    from buyeros_api.sales import actions
    from buyeros_api.sales.model import ROUTE
    from buyeros_api.providers import base
    from buyeros_api.providers.registry import ProviderRegistration
    from buyeros_api.providers.base import ProviderCapability,Money
    from buyeros_api.settings import get_settings
    from buyeros_api.execution.config import get_settings as dispatch_settings
    from tests.conftest import runtime_role_dsn
    from tests.test_buyer_review_db import WORKSPACE_A,PROJECT_A
    from tests.test_conversation_threads_api import create,headers
    from tests.test_sales_tasks_api import SALES_ROOT
    for name in ('NEXT_PUBLIC_CONVERSATION_HOME','BUYEROS_SALES_SKILLS_ENABLED','BUYEROS_PAID_ADMISSION_ENABLED',
                 'BUYEROS_PAID_DISPATCH_ENABLED','BUYEROS_CLOUDFLARE_EXECUTION_ENABLED'):
        monkeypatch.setenv(name,'true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',WORKSPACE_A)
    client=request.getfixturevalue('execution_api')
    dsn=request.getfixturevalue('isolated_seeded')
    get_settings.cache_clear();dispatch_settings.cache_clear()
    monkeypatch.setattr(base,'SELECTED_LIVE_PROVIDERS',frozenset({'opencode-go'}))
    item=ProviderRegistration(ProviderCapability('opencode-go','sales-test.v1','model',frozenset({'US'}),
        frozenset({'en'}),frozenset({'company'}),'server-only','sales-test-price.v1',Money(Decimal('.1')),
        'verified','verified','unsupported','unsupported','one-day',datetime.now(timezone.utc),('https://opencode.ai/go',)),
        lambda:None,('synthetic:owned-sales',),model_route=replace(ROUTE,route_id='sales-grounded.v1'),
        model_id='synthetic-model',policy_account_reference='synthetic-sales-account')
    monkeypatch.setattr(actions,'REGISTRATION',item)
    class SectionOwner:
        async def save_section(self,*args): pass  # deliberately no Task6 output acceptance
    monkeypatch.setattr(actions,'SECTION_OWNER',SectionOwner())
    monkeypatch.setenv('BUYEROS_OPENCODE_API_KEY','synthetic-not-a-credential')
    from tests.test_conversation_reply_db import conversation_api,DOCUMENT
    # Reuse authoritative approved synthetic offer/profile rows, not a policy bypass.
    sources_fixture=conversation_api.__wrapped__(None,client,dsn)
    next(sources_fixture)
    sources_fixture.close()
    source_refs=[{'id':DOCUMENT,'version':1,'kind':'document',
        'locator':'document:'+DOCUMENT,'retention_class':'durable'}]
    from tests.policy_activation_fixtures import approve_research_fixture
    approve_research_fixture(dsn,WORKSPACE_A,PROJECT_A,
        domains=(),countries=['US'],model=item.policy_binding,
        terms_overrides={'allowed_sources':{'domains':[],'document_ids':[DOCUMENT]}})
    ws,project=uuid.UUID(WORKSPACE_A),uuid.UUID(PROJECT_A)
    async def initialize():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine,ws) as session:
                await ensure_period_accounts(session,ws,project,None,'assessment')
        finally: await engine.dispose()
    run_async(initialize())
    with psycopg.connect(dsn) as db:
        db.execute('UPDATE budget_accounts SET approved_limit=10 WHERE workspace_id=%s',(ws,))
        db.execute("UPDATE projects SET markets=ARRAY['US'],language_preferences=ARRAY['en'] WHERE id=%s",(project,))
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        epoch=db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL RETURNING epoch").fetchone()[0]
    parts=urlsplit(dsn)
    worker_dsn=urlunsplit(parts._replace(netloc=f'buyeros_worker:test-only@{parts.hostname}:{parts.port}'))
    thread=create(client)
    response=client.post(SALES_ROOT,headers=headers(version=thread['version']),json={
        'thread_id':thread['id'],'skill_id':'sales-quick','skill_version':'1','user_message':'SYNTHETIC EXECUTION',
        'arguments':{'research_question':'SYNTHETIC'},'source_refs':source_refs})
    assert response.status_code==201,response.text
    task=response.json()['data'];path=SALES_ROOT+'/'+task['id']
    proposal={'id':str(uuid.uuid4()),'capability':'research.read','arguments':{'refs':[],'purpose':'SYNTHETIC'},'source_versions':source_refs}
    preview=client.post(path+'/execution-preview',headers=headers(),json=proposal)
    if preview.status_code!=200:
        async def diagnose():
            from buyeros_api.execution.sales_tasks import preview_step
            from buyeros_api.sales.contracts import Scope,ActionProposal
            from tests.test_buyer_review_db import OPERATOR
            engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
            try:
                async with tenant_session(engine,ws) as session:
                    await preview_step(session,Scope(workspace_id=ws,project_id=project,
                        actor_id=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)),uuid.UUID(task['id']),ActionProposal.model_validate(proposal))
            finally:await engine.dispose()
        run_async(diagnose())
    assert preview.status_code==200,preview.text
    review=client.post(path+'/reviews',headers=headers(version=1,key='synthetic-review'),
        json={'proposal':proposal,'fingerprint':preview.json()['data']['fingerprint']})
    assert review.status_code==200,review.text
    payload={'proposal':proposal,'review_id':review.json()['data']['id']}
    admitted=client.post(path+'/steps',headers=headers(version=1,key='synthetic-admit'),json=payload)
    assert admitted.status_code==200,admitted.text
    case=NS(client=client,dsn=dsn,worker_dsn=worker_dsn,ws=ws,project=project,task=task,path=path,payload=payload,
        epoch=epoch,calls=0,mode='received',item=item)
    async def transport(basis,item):
        case.calls+=1
        if case.mode=='lost': raise TimeoutError('synthetic lost response')
        return synthetic_result(basis)
    case.real_complete=actions.complete
    monkeypatch.setattr(actions,'complete',transport)
    with psycopg.connect(dsn) as db:
        case.steps=db.execute('SELECT s.id,s.outbox_id FROM sales_steps s JOIN sales_executions p ON p.id=s.execution_id WHERE p.task_id=%s ORDER BY s.section',(task['id'],)).fetchall()
    try: yield case
    finally:
        # The owned allocator drops this disposable DB. Preserve all rows until then.
        get_settings.cache_clear();dispatch_settings.cache_clear()


def pg_call(case, action, *, worker=True):
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.execution.engine import run_async,async_database_url
    from tests.conftest import runtime_role_dsn
    async def call():
        engine=create_async_engine(async_database_url(case.worker_dsn if worker else runtime_role_dsn(case.dsn)))
        try: return await action(engine)
        finally: await engine.dispose()
    return run_async(call())


def pg_dispatch(case,index=0):
    import psycopg
    from buyeros_api.api.worker_schemas import JobEnvelope
    from buyeros_api.services.worker_execution import execute_step
    with psycopg.connect(case.dsn) as db:
        db.execute("UPDATE outbox_events SET state='dispatched',runtime_backend='cloudflare',runtime_epoch=%s,fencing_generation=1 WHERE id=%s",(case.epoch,case.steps[index][1]))
    envelope=JobEnvelope(v=1,workspace_id=case.ws,outbox_id=case.steps[index][1],generation=1,runtime_epoch=case.epoch)
    return pg_call(case,lambda engine:execute_step(engine,envelope,'start'))


def test_postgres_two_workers_claim_once(execution_pg):
    import asyncio,psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution.sales_tasks import claim
    c=execution_pg
    async def run(engine):
        async def one():
            async with tenant_session(engine,c.ws) as session: return await claim(session,c.steps[0][0],workspace_id=c.ws)
        results=await asyncio.gather(one(),one())
        assert sum(prepared is not None for _,prepared in results)==1
    pg_call(c,run)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT calls_started,consumed_usd FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchone()==(1,Decimal('.1'))


def test_postgres_stream_reconnect_does_not_execute_again(execution_pg):
    from tests.test_buyer_review_db import _h
    c=execution_pg
    assert pg_dispatch(c).state=='done'
    for _ in range(3):
        assert c.client.get(c.path+'/events?after=0',headers=_h()).status_code==200
        assert c.client.get(c.path+'/steps',headers=_h()).status_code==200
    assert c.calls==1
    assert c.client.get(c.path,headers=_h()).json()['data']['state']!='completed'


def test_postgres_revoked_actor_before_dispatch_causes_no_external_call(execution_pg):
    import psycopg
    c=execution_pg
    with psycopg.connect(c.dsn) as db:
        db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=(SELECT actor_id FROM sales_executions WHERE task_id=%s)',(c.ws,c.task['id']))
    assert pg_dispatch(c).state=='blocked' and c.calls==0


def test_postgres_cancellation_after_dispatch_preserves_liability(execution_pg):
    import psycopg
    from tests.test_buyer_review_db import _h
    from tests.test_conversation_threads_api import headers
    c=execution_pg;c.mode='lost'
    assert pg_dispatch(c).state=='reconcile'
    task=c.client.get(c.path,headers=_h()).json()['data']
    result=c.client.post(c.path+'/cancel',headers=headers(version=task['revision'],key='synthetic-cancel'))
    assert result.status_code==200,result.text
    assert result.json()['data']['state']=='outcome_unknown'
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=(SELECT reservation_id FROM sales_executions WHERE task_id=%s)',(c.task['id'],)).fetchone()[0]==Decimal('.2')
        assert db.execute('SELECT consumed_usd FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchone()[0]==Decimal('.1')


@pytest.mark.parametrize('boundary',['before_claim','after_claim','after_external_await','after_receipt'])
def test_postgres_restart_each_commit_boundary(execution_pg,boundary):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution.sales_tasks import claim,persist_result,recover_outbox
    from buyeros_api.db.outbox import OutboxEvent
    c=execution_pg;step_id,event_id=c.steps[0]
    async def prepare(engine):
        async with tenant_session(engine,c.ws) as session: return await claim(session,step_id,workspace_id=c.ws)
    if boundary!='before_claim':
        _,prepared=pg_call(c,prepare)
        if boundary in {'after_external_await','after_receipt'}:
            from buyeros_api.sales import actions
            from buyeros_api.execution.engine import run_async
            basis,_,claim_id=prepared
            # Actually await the owned synthetic transport, then lose the result
            # before its receipt commit in the after_external_await case.
            response=run_async(actions.complete(basis,c.item))
            assert c.calls==1
        if boundary=='after_receipt':
            async def save(engine):
                async with tenant_session(engine,c.ws) as session:
                    return await persist_result(session,step_id,claim_id,basis,response)
            pg_call(c,save)
    async def recover(engine):
        async with tenant_session(engine,c.ws) as session:
            event=await session.get(OutboxEvent,event_id)
            return await recover_outbox(session,event)
    pg_call(c,recover)
    with psycopg.connect(c.dsn) as db:
        state=db.execute('SELECT state FROM sales_steps WHERE id=%s',(step_id,)).fetchone()[0]
        assert state==('queued' if boundary=='before_claim' else 'received' if boundary=='after_receipt' else 'unknown')
        assert db.execute('SELECT count(*) FROM budget_reservations WHERE operation_id=(SELECT id FROM sales_executions WHERE task_id=%s)',(c.task['id'],)).fetchone()[0]==1


def test_postgres_approval_forgery_and_cross_actor_replay_denied(execution_pg):
    from tests.test_conversation_threads_api import headers
    from tests.test_buyer_review_db import VIEWER
    c=execution_pg
    response=c.client.post(c.path+'/steps',headers=headers(version=2,key='synthetic-forged'),
        json={**c.payload,'review_id':str(uuid.uuid4())})
    assert response.status_code==409
    assert c.client.post(c.path+'/steps',headers=headers(VIEWER,1,'synthetic-admit'),json=c.payload).status_code==404


def test_postgres_parent_budget_and_outbox_rollback_atomic(execution_pg):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution.sales_tasks import claim
    c=execution_pg
    async def rollback(engine):
        with pytest.raises(RuntimeError):
            async with tenant_session(engine,c.ws) as session:
                await claim(session,c.steps[0][0],workspace_id=c.ws)
                raise RuntimeError('synthetic crash before claim commit')
    pg_call(c,rollback)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT calls_started,consumed_usd FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchone()==(0,Decimal('0'))
        assert db.execute('SELECT state FROM sales_steps WHERE id=%s',(c.steps[0][0],)).fetchone()[0]=='queued'


def test_postgres_worker_cannot_approve_admit_or_edit_frozen_child(execution_pg):
    import psycopg
    c=execution_pg
    with psycopg.connect(c.dsn) as db:
        for table in ('sales_reviews','sales_executions','sales_steps'):
            assert not db.execute('SELECT has_table_privilege(%s,%s,%s)',('buyeros_worker',table,'INSERT')).fetchone()[0]
        for table,column in [('sales_tasks','arguments'),('sales_executions','upper_bound'),('sales_steps','basis_hash'),('sales_reviews','fingerprint')]:
            assert not db.execute('SELECT has_column_privilege(%s,%s,%s,%s)',('buyeros_worker',table,column,'UPDATE')).fetchone()[0]
    with psycopg.connect(c.worker_dsn) as db:
        assert db.execute('SELECT count(*) FROM sales_steps').fetchone()[0]==0


def test_recovery_preserves_future_canonical_completion(runtime):
    import asyncio
    m,s=runtime
    for step in s.steps: step.state='received'
    s.row.state='completed';s.row.output_ids=[str(uuid.uuid4())]
    asyncio.run(m.recover_outbox(s.session,NS(payload={'step_id':str(s.steps[0].id)})))
    assert s.row.state=='completed'


def test_cancel_preserves_future_canonical_completion(runtime):
    import asyncio
    m,s=runtime
    s.row.state='completed';s.row.output_ids=[str(uuid.uuid4())]
    result=asyncio.run(m.cancel_task(s.session,s.scope,s.row.id,s.row.revision))
    assert result.state=='completed' and not s.parent.cancelled


def test_postgres_admission_replay_survives_idempotency_receipt_expiry(execution_pg):
    import psycopg
    from tests.test_conversation_threads_api import headers
    c=execution_pg
    with psycopg.connect(c.dsn) as db:
        before=db.execute('SELECT id,reservation_id FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchone()
        db.execute("DELETE FROM idempotency_records WHERE operation_id='admitSalesStep'")
    response=c.client.post(c.path+'/steps',headers=headers(version=1,key='synthetic-admit'),json=c.payload)
    assert response.status_code==200,response.text
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT id,reservation_id FROM sales_executions WHERE task_id=%s',(c.task['id'],)).fetchall()==[before]
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='sales.step'").fetchone()[0]==2


def test_execution_routes_bind_current_scope_revision_and_native_headers(monkeypatch):
    from contextlib import asynccontextmanager
    from fastapi.testclient import TestClient
    from buyeros_api.api.app import create_app
    from buyeros_api.api.auth import get_principal
    from buyeros_api.api.routes import sales_tasks as routes
    from buyeros_api.execution import sales_tasks as m
    from buyeros_api.sales.contracts import ExecutionPreview,ExecutionReview
    actor,ws,project,task=(uuid.uuid4() for _ in range(4))
    calls=[]
    @asynccontextmanager
    async def access(*args,**kwargs):
        calls.append(kwargs)
        yield object(),actor
    quote=ExecutionPreview(model_id='synthetic-model',route='sales-grounded.v1',task_id=task,revision=3,fingerprint='a'*64,max_calls=2,max_concurrency=2,max_liability_usd=Decimal('.2'))
    async def preview(session,scope,task_id,proposal):
        assert (scope.workspace_id,scope.project_id,scope.actor_id,task_id)==(ws,project,actor,task)
        return quote
    async def approve(session,scope,task_id,proposal,revision,key,*,expected_fingerprint):
        assert scope.actor_id==actor and revision==3 and key=='synthetic-approve' and expected_fingerprint==quote.fingerprint
        return ExecutionReview(**quote.model_dump(exclude={'model_id','route'}),id=uuid.uuid4(),expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))
    monkeypatch.setattr(routes,'access',access);monkeypatch.setattr(m,'preview_step',preview)
    monkeypatch.setattr(routes.service,'approve_step',approve)
    app=create_app();app.dependency_overrides[get_principal]=lambda:object()
    client=TestClient(app)
    path=f'/v1/workspaces/{ws}/projects/{project}/sales-tasks/{task}'
    proposal={'id':str(uuid.uuid4()),'capability':'research.read','arguments':{'refs':[],'purpose':'SYNTHETIC'},'source_versions':[]}
    result=client.post(path+'/execution-preview',json=proposal)
    assert result.status_code==200 and result.json()['data']['max_liability_usd']=='0.2'
    body={'proposal':proposal,'fingerprint':quote.fingerprint}
    assert client.post(path+'/reviews',json=body,headers={'Idempotency-Key':'synthetic-approve'}).status_code==400
    result=client.post(path+'/reviews',json=body,headers={'Idempotency-Key':'synthetic-approve','If-Match':'"3"'})
    assert result.status_code==200 and result.headers['cache-control']=='no-store'
    assert all(call=={'sales':True} for call in calls)


def test_worker_readiness_requires_consumption_but_not_approval_grants():
    from buyeros_api.services.schema_readiness import sales_requirements
    required=sales_requirements(worker=True)
    grants={(x['relation'],x['privilege']):set(x['columns']) for x in required['required_privileges']}
    assert ('public.sales_reviews','INSERT') not in grants
    assert ('public.sales_executions','INSERT') not in grants
    assert ('public.sales_steps','INSERT') not in grants
    assert grants['public.sales_executions','UPDATE']=={'calls_started','consumed_usd','unused_released','updated_at'}
    assert 'basis_hash' not in grants['public.sales_steps','UPDATE']
    assert 'arguments' not in grants['public.sales_tasks','UPDATE']


def test_released_or_foreign_parent_hold_cannot_authorize_child():
    m=implementation()
    assert hasattr(m,'validate_parent_hold'), 'claim must recheck the admitted native reservation'
    parent=NS(id=uuid.uuid4(),workspace_id=uuid.uuid4(),reservation_id=uuid.uuid4(),upper_bound=Decimal('.2'))
    hold=NS(id=parent.reservation_id,workspace_id=parent.workspace_id,operation_id=parent.id,
        upper_bound=Decimal('.2'),remaining_hold=Decimal('.2'),currency='USD',price_version='synthetic-v1',state='active')
    m.validate_parent_hold(parent,hold,'synthetic-v1')
    for field,value in [('remaining_hold',Decimal('0')),('operation_id',uuid.uuid4()),('currency','EUR'),('price_version','other')]:
        old=getattr(hold,field);setattr(hold,field,value)
        with pytest.raises(ValueError):m.validate_parent_hold(parent,hold,'synthetic-v1')
        setattr(hold,field,old)


def test_configuration_uses_transactional_policy_gate(monkeypatch):
    import asyncio
    from buyeros_api.execution import sales_tasks as m
    from buyeros_api.services import policy_service,conversation_access
    from buyeros_api.settings import get_settings
    scope=NS(workspace_id=uuid.uuid4(),project_id=uuid.uuid4())
    row=NS(arguments={},source_refs=[])
    item=NS(policy_binding=None)
    calls=[]
    class Result:
        def one(self):return NS(backend='cloudflare',enabled=True)
        def scalar_one(self):return NS(markets=['US'],language_preferences=['en'])
    class Session:
        async def execute(self,*args):return Result()
    async def forbidden(*args,**kwargs):pytest.fail('write transaction used read-only-only policy evaluator')
    async def evaluate(*args,**kwargs):calls.append('locked');return {'allowed':True}
    monkeypatch.setattr(policy_service,'evaluate_current_policy_readonly',forbidden)
    monkeypatch.setattr(policy_service,'evaluate_current_policy',evaluate)
    monkeypatch.setattr(conversation_access,'sales_enabled',lambda ws:True)
    monkeypatch.setattr(m.actions,'selected',lambda *args:item)
    monkeypatch.setenv('BUYEROS_CLOUDFLARE_EXECUTION_ENABLED','true');get_settings.cache_clear()
    try:
        assert asyncio.run(m.configuration(Session(),scope,row))==(item,'US','en')
        assert calls==['locked']
    finally:get_settings.cache_clear()


def test_worker_grants_cover_orm_timestamp_updates():
    from sqlalchemy import update
    from sqlalchemy.dialects import postgresql
    from buyeros_api.db.sales_execution import SalesExecution,SalesStep
    from buyeros_api.services.schema_readiness import sales_requirements
    grants={x['relation']:set(x['columns']) for x in sales_requirements(worker=True)['required_privileges'] if x['privilege']=='UPDATE'}
    for model,values in [(SalesExecution,{'calls_started':1}),(SalesStep,{'state':'unknown'})]:
        statement=str(update(model).values(**values).compile(dialect=postgresql.dialect()))
        assert 'updated_at=now()' in statement
        assert set(values)|{'updated_at'} <= grants['public.'+model.__tablename__]


def test_locked_children_refresh_identity_map():
    import asyncio
    m=implementation()
    class Session:
        async def execute(self,stmt):
            assert stmt.get_execution_options().get('populate_existing') is True
            return NS(scalars=lambda:NS(all=lambda:[]))
    asyncio.run(m.children(Session(),NS(id=uuid.uuid4(),workspace_id=uuid.uuid4())))


def test_missing_credential_never_opens_http(monkeypatch):
    import asyncio,httpx
    from buyeros_api.sales import actions
    monkeypatch.delenv('BUYEROS_OPENCODE_API_KEY',raising=False)
    monkeypatch.setattr(httpx,'AsyncClient',lambda:pytest.fail('local failure opened HTTP'))
    result=asyncio.run(actions.complete({},None))
    assert isinstance(result,actions.DefinitelyUnsubmitted)


def test_all_unused_release_is_idempotent(runtime):
    import asyncio
    m,s=runtime
    async def run():
        for step in s.steps: step.state='cancelled'
        assert await m.release_unused_parent(s.session,s.parent,s.steps)
        assert await m.release_unused_parent(s.session,s.parent,s.steps)
        assert s.parent.unused_released and s.hold.remaining_hold==0 and s.releases==1
    asyncio.run(run())


@pytest.mark.parametrize('state',['queued','submitting','unknown','received'])
def test_mixed_parent_cannot_release(runtime,state):
    import asyncio
    m,s=runtime
    for step in s.steps: step.state='cancelled'
    s.steps[0].state=state
    assert not asyncio.run(m.release_unused_parent(s.session,s.parent,s.steps))
    assert s.releases==0 and not s.parent.unused_released


def test_credential_disappears_after_claim_zero_http_and_unused_release(runtime,monkeypatch):
    import asyncio,httpx
    m,s=runtime
    monkeypatch.delenv('BUYEROS_OPENCODE_API_KEY',raising=False)
    monkeypatch.setattr(httpx,'AsyncClient',lambda:pytest.fail('credential loss opened HTTP'))
    async def run():
        s.lock=asyncio.Lock()
        step=s.steps[0]
        result=await m.execute_step(None,step.id,workspace_id=s.scope.workspace_id,execution=s.guard(step))
        assert result.dispatch_state=='failed' and step.definitely_unsubmitted
        assert s.parent.calls_started==0 and s.parent.consumed_usd==0
        assert s.releases==1 and s.parent.unused_released and s.row.state=='failed'
        await m.persist_unsubmitted(s.session,step.id,step.claim_id,workspace_id=s.scope.workspace_id)
        assert s.releases==1 and s.parent.calls_started==0
    asyncio.run(run())


def test_accounting_owner_and_credentials_are_independent_selection_gates(monkeypatch):
    from buyeros_api.sales import actions
    from buyeros_api.api.errors import ApiError
    from buyeros_api.settings import get_settings
    from buyeros_api.execution.config import get_settings as dispatch_settings
    from dataclasses import replace
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','true')
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','true')
    monkeypatch.setenv('BUYEROS_OPENCODE_API_KEY','synthetic')
    monkeypatch.setattr(actions,'SECTION_OWNER',object())
    monkeypatch.setattr(actions,'RECONCILER',object())
    item=NS(model_route=replace(actions.ROUTE,route_id=actions.PROMPT_VERSION),
        capability=NS(provider='opencode-go',service='model',max_liability=NS(currency='USD')),
        policy_binding=True,sandbox_evidence=True)
    monkeypatch.setattr(actions,'REGISTRATION',item)
    monkeypatch.setattr(actions,'activation_blockers',lambda *args,**kwargs:[])
    get_settings.cache_clear();dispatch_settings.cache_clear()
    try:
        real_accounting=actions.ACCOUNTING_OWNER
        monkeypatch.setattr(actions,'ACCOUNTING_OWNER',None)
        with pytest.raises(ApiError):actions.selected('US','en')
        monkeypatch.setattr(actions,'ACCOUNTING_OWNER',real_accounting)
        assert actions.selected('US','en') is item
        for key in ['', 'bad key', '\n']:
            monkeypatch.setenv('BUYEROS_OPENCODE_API_KEY',key)
            with pytest.raises(ApiError):actions.selected('US','en')
    finally:get_settings.cache_clear();dispatch_settings.cache_clear()


def test_pre_dispatch_configuration_failure_releases_all_unused(runtime,monkeypatch):
    import asyncio
    from buyeros_api.api.errors import ApiError
    m,s=runtime
    async def unavailable(*args):raise ApiError(503,'SALES_MODEL_UNAVAILABLE','configure credentials')
    monkeypatch.setattr(m,'configuration',unavailable)
    async def run():
        result,prepared=await m.claim(s.session,s.steps[0].id,workspace_id=s.scope.workspace_id)
        assert result.dispatch_state=='failed' and prepared is None
        assert s.releases==1 and s.parent.calls_started==0 and s.hold.remaining_hold==0
    asyncio.run(run())



def test_postgres_late_receipt_survives_recovery_cached_child(execution_pg):
    import asyncio,psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.db.sales_execution import SalesStep
    from buyeros_api.execution import sales_tasks as m
    c=execution_pg
    async def run(engine):
        prepared=[]
        for step_id,_ in c.steps:
            async with tenant_session(engine,c.ws) as session:
                _,value=await m.claim(session,step_id,workspace_id=c.ws)
                prepared.append(value)
        step_id,_=c.steps[0];basis,_,claim_id=prepared[0]
        other_basis,_,other_claim=prepared[1]
        async with tenant_session(engine,c.ws) as session:
            await m.persist_result(session,c.steps[1][0],other_claim,other_basis,synthetic_result(other_basis))
        late_saved=asyncio.Event();initial_read=asyncio.Event();committed=asyncio.Event()
        async def late():
            async with tenant_session(engine,c.ws) as session:
                await m.persist_result(session,step_id,claim_id,basis,synthetic_result(basis))
                late_saved.set()  # thread remains locked, valid receipt not committed
                await initial_read.wait()
            committed.set()
        async def recovery():
            await late_saved.wait()
            async with tenant_session(engine,c.ws) as session:
                original=session.execute
                intercepted=False
                async def execute(stmt,*args,**kwargs):
                    nonlocal intercepted
                    if (not intercepted and getattr(stmt,'column_descriptions',[])
                        and stmt.column_descriptions[0].get('entity') is SalesStep
                        and stmt._for_update_arg is None):
                        intercepted=True
                        result=await original(stmt,*args,**kwargs)
                        cached=result.scalar_one()  # force pre-lock ORM identity hydration
                        assert cached.state=='submitting'
                        initial_read.set()
                        await committed.wait()
                        return NS(scalar_one=lambda:cached)
                    return await original(stmt,*args,**kwargs)
                session.execute=execute
                await m.recover_outbox(session,NS(payload={'step_id':str(step_id)}))
                assert intercepted
                child=await session.get(SalesStep,step_id)
                assert child.state=='received' and child.usage and child.result_digest
        await asyncio.wait_for(asyncio.gather(late(),recovery()),10)
    pg_call(c,run)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT state FROM sales_tasks WHERE id=%s',(c.task['id'],)).fetchone()[0]=='ready_for_review'
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE operation_id=(SELECT id FROM sales_executions WHERE task_id=%s)',(c.task['id'],)).fetchone()[0]==Decimal('.2')


def test_postgres_all_unsubmitted_cancel_releases_once(execution_pg):
    import psycopg
    from tests.test_conversation_threads_api import headers
    from tests.test_buyer_review_db import _h
    c=execution_pg
    task=c.client.get(c.path,headers=_h()).json()['data']
    h=headers(version=task['revision'],key='synthetic-unused-cancel')
    for _ in range(2):
        response=c.client.post(c.path+'/cancel',headers=h)
        assert response.status_code==200,response.text
        assert response.json()['data']['state']=='cancelled'
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT p.unused_released,p.calls_started,p.consumed_usd,r.state,r.remaining_hold FROM sales_executions p JOIN budget_reservations r ON r.id=p.reservation_id WHERE p.task_id=%s',(c.task['id'],)).fetchone()==(True,0,Decimal(0),'released',Decimal(0))
    assert c.calls==0


def test_postgres_unused_release_rollback_is_atomic(execution_pg):
    import psycopg
    from buyeros_api.db.session import tenant_session
    from buyeros_api.execution import sales_tasks as m
    from buyeros_api.sales.contracts import Scope
    c=execution_pg
    async def run(engine):
        with pytest.raises(RuntimeError):
            async with tenant_session(engine,c.ws) as session:
                await m.lock_authority(session,c.ws,budget=True)
                row,parent,_,_=await m.locked(session,c.steps[0][0])
                scope=Scope(workspace_id=c.ws,project_id=c.project,actor_id=parent.actor_id)
                await m.cancel_task(session,scope,row.id,row.revision)
                raise RuntimeError('crash before cancellation/release commit')
    pg_call(c,run,worker=False)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT p.unused_released,p.cancelled,r.state,r.remaining_hold FROM sales_executions p JOIN budget_reservations r ON r.id=p.reservation_id WHERE p.task_id=%s',(c.task['id'],)).fetchone()==(False,False,'active',Decimal('.2'))
        assert db.execute('SELECT DISTINCT s.state FROM sales_steps s JOIN sales_executions p ON p.id=s.execution_id WHERE p.task_id=%s',(c.task['id'],)).fetchall()==[('queued',)]


@pytest.mark.parametrize('boundary',['before_claim','before_http'])
def test_postgres_credential_loss_releases_unused_without_transport(execution_pg,monkeypatch,boundary):
    import psycopg,httpx
    from buyeros_api.sales import actions
    from buyeros_api.execution import sales_tasks as m
    c=execution_pg
    # Fixture transport is synthetic; explicit typed result is the proven local no-HTTP branch.
    async def disappeared(*args):
        monkeypatch.delenv('BUYEROS_OPENCODE_API_KEY',raising=False)
        return await c.real_complete(*args)
    monkeypatch.setattr(httpx,'AsyncClient',lambda:pytest.fail('credential loss opened HTTP'))
    if boundary=='before_claim':monkeypatch.delenv('BUYEROS_OPENCODE_API_KEY',raising=False)
    else:monkeypatch.setattr(actions,'complete',disappeared)
    assert pg_dispatch(c).state=='blocked' and c.calls==0
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT p.unused_released,p.calls_started,p.consumed_usd,r.state,r.remaining_hold FROM sales_executions p JOIN budget_reservations r ON r.id=p.reservation_id WHERE p.task_id=%s',(c.task['id'],)).fetchone()==(True,0,Decimal(0),'released',Decimal(0))
        assert db.execute("SELECT count(*) FROM sales_task_events WHERE task_id=%s AND kind='error' AND payload->>'code'='configuration_required'",(c.task['id'],)).fetchone()[0]==1



def test_unsubmitted_proof_save_failure_stays_unknown(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    monkeypatch.delenv('BUYEROS_OPENCODE_API_KEY',raising=False)
    async def failed_save(*args,**kwargs):raise RuntimeError('synthetic save failure')
    monkeypatch.setattr(m,'persist_unsubmitted',failed_save)
    async def run():
        s.lock=asyncio.Lock()
        step=s.steps[0]
        result=await m.execute_step(None,step.id,workspace_id=s.scope.workspace_id,execution=s.guard(step))
        assert result.dispatch_state=='unknown' and s.parent.calls_started==1
        assert s.parent.consumed_usd==Decimal('.1') and s.releases==0
    asyncio.run(run())


def test_admission_configuration_failure_has_no_durable_side_effects(runtime,monkeypatch):
    import asyncio
    from buyeros_api.api.errors import ApiError
    m,s=runtime
    async def config(*args):raise ApiError(503,'SALES_MODEL_UNAVAILABLE','configuration required')
    monkeypatch.setattr(m,'configuration',config)
    with pytest.raises(ApiError):
        asyncio.run(m.admit_step(s.session,s.scope,s.row.id,s.proposal,s.review.id,expected_version=1))
    assert not s.session.added and s.row.state=='ready_for_review' and s.parent.calls_started==0


def test_cancel_service_takes_policy_and_budget_before_task_lock(runtime,monkeypatch):
    import asyncio
    m,s=runtime
    order=[]
    async def authority(session,ws,*,budget=False):
        assert budget;order.extend(['policy','budget'])
    async def task(*args,**kwargs):
        assert order==['policy','budget'];order.append('task');return s.row
    async def replay(*args,**kwargs):return NS(replay=True)
    monkeypatch.setattr(m,'lock_authority',authority)
    monkeypatch.setattr(m.tasks,'task_row',task)
    monkeypatch.setattr(m.tasks,'begin_idempotency',replay)
    monkeypatch.setattr(m.tasks,'record',lambda row:row)
    asyncio.run(m.tasks.cancel_task(s.session,s.scope,s.row.id,'synthetic-cancel',s.row.revision))
    assert order==['policy','budget','task']


@pytest.mark.parametrize('mutation',['missing_child','claimed_without_proof','receipt','debit'])
def test_release_requires_complete_unused_proof(runtime,mutation):
    import asyncio
    m,s=runtime
    for step in s.steps:step.state='failed'
    steps=list(s.steps)
    if mutation=='missing_child':steps.pop()
    if mutation=='claimed_without_proof':steps[0].claim_id=uuid.uuid4()
    if mutation=='receipt':steps[0].result_digest='a'*64
    if mutation=='debit':s.parent.consumed_usd=Decimal('.1')
    assert not asyncio.run(m.release_unused_parent(s.session,s.parent,steps))
    assert s.releases==0



def test_postgres_task_create_maps_native_fingerprint_and_replays(execution_pg):
    import psycopg
    from tests.test_conversation_threads_api import create,headers
    from tests.test_sales_tasks_api import SALES_ROOT
    c=execution_pg
    thread=create(c.client)
    body={'thread_id':thread['id'],'skill_id':'sales-quick','skill_version':'1',
        'user_message':'SYNTHETIC FINGERPRINT','arguments':{'research_question':'SYNTHETIC'},'source_refs':[]}
    h=headers(version=thread['version'],key='synthetic-fingerprint')
    first=c.client.post(SALES_ROOT,headers=h,json=body)
    assert first.status_code==201,first.text
    assert c.client.post(SALES_ROOT,headers=h,json=body).json()['data']==first.json()['data']
    ident=first.json()['data']['id']
    with psycopg.connect(c.dsn) as db:
        fingerprint=db.execute('SELECT intent_fingerprint FROM sales_tasks WHERE id=%s',(ident,)).fetchone()[0]
        native=db.execute("SELECT request_hash FROM idempotency_records WHERE operation_id='createSalesTask' AND key=%s",('synthetic-fingerprint',)).fetchone()[0]
        assert native=='sha256:'+fingerprint and len(fingerprint)==64
        db.execute("DELETE FROM idempotency_records WHERE operation_id='createSalesTask' AND key=%s",('synthetic-fingerprint',))
    assert c.client.post(SALES_ROOT,headers=h,json=body).json()['data']['id']==ident
    assert c.client.post(SALES_ROOT,headers=h,json={**body,'user_message':'CHANGED'}).status_code==409
