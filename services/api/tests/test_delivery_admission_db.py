"""Actual owned PG50 admission/RLS/concurrency controls; production routes off."""
import asyncio,contextlib,importlib,json,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import psycopg,pytest
from alembic import command
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from tests.conftest import runtime_role_dsn
from tests.test_delivery_budget_db import limits,authority
from tests.test_delivery_preparation_db import approved
from tests.test_delivery_ledger_db import config,tenant
from tests.test_lookup_quotes_db import WORKSPACE_A,PROJECT,REVIEWER,_h
from tests.test_api_tenant_isolation import WORKSPACE_B

def module():
    path=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_admission.py'
    assert path.is_file(),'atomic delivery admission service is missing'
    return importlib.import_module('buyeros_api.services.delivery_admission')

class DenySession:
    def __getattr__(self,name):raise AssertionError('unselected admission must not access DB or provider: '+name)

def test_unselected_delivery_admission_refuses_before_any_database_or_provider_io():
    with pytest.raises(ApiError) as error:asyncio.run(module().admit_delivery(DenySession(),authorization=None))
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

def test_delivery_authority_schema_force_RLS_and_runtime_grants_are_real(isolated_quote_case):
    client,dsn,buyers=isolated_quote_case
    with psycopg.connect(dsn) as db:
        assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='delivery_authorizations'").fetchone()==(True,True),'durable delivery authority schema is missing'
    with tenant(dsn,WORKSPACE_A) as db:
        assert db.execute("SELECT has_table_privilege(current_user,'delivery_authorizations','SELECT'),has_table_privilege(current_user,'delivery_authorizations','INSERT'),has_table_privilege(current_user,'delivery_authorizations','UPDATE'),has_table_privilege(current_user,'delivery_authorizations','DELETE')").fetchone()==(True,True,False,False)
        assert db.execute('SELECT count(*) FROM delivery_authorizations').fetchone()==(0,)

TABLES=('provider_operations','budget_reservations','budget_reservation_allocations','delivery_messages','delivery_liabilities','outbox_events','delivery_authorizations','cost_events')
def counts(dsn):
    with psycopg.connect(dsn) as db:return tuple(db.execute('SELECT count(*) FROM '+table+' WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0] for table in TABLES)

@pytest.fixture
def admission_case(isolated_quote_case):
    client,dsn,buyers,args=approved(isolated_quote_case)
    with psycopg.connect(dsn,autocommit=True) as db:
        assert db.execute("SELECT to_regclass('public.delivery_authorizations')").fetchone()[0] is not None,'durable delivery authority schema is missing'
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('0053_resumable_documents',)
        db.execute('UPDATE worker_runtime_control SET enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL WHERE singleton=1')
    limits(dsn);auth=authority(args)
    try:yield client,dsn,args,auth
    finally:
        with psycopg.connect(dsn,autocommit=True) as db:
            # Owner cleanup is confined to this owned child fixture. Runtime
            # roles never receive UPDATE/DELETE authority over these ledgers.
            db.execute('DELETE FROM worker_steps WHERE workspace_id=%s AND outbox_id IN (SELECT outbox_id FROM delivery_authorizations WHERE workspace_id=%s)',(WORKSPACE_A,WORKSPACE_A))
            for table in ('delivery_authorizations','delivery_events','delivery_liabilities','delivery_messages'):
                db.execute('DELETE FROM '+table+' WHERE workspace_id=%s',(WORKSPACE_A,))

def run(dsn,args,auth,*,abort=False,catch=False,environment='test'):
    async def apply():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine,args['workspace_id']) as session:
                try:result=await module().admit_delivery(session,authorization=auth,environment=environment,**args)
                except ApiError:
                    if not catch:raise
                    result=None
                if abort:raise RuntimeError('owned caller abort after atomic admission')
                return result
        finally:await engine.dispose()
    return asyncio.run(apply())

def snapshot(dsn,result):
    with psycopg.connect(dsn) as db:
        message=db.execute('SELECT id,operation_id,intent_key,draft_revision_id,recipient_ref,sender_identity_id,approval_id,actor_id,state,provider_ref,payload_digest FROM delivery_messages WHERE id=%s',(result.message_id,)).fetchone()
        hold=db.execute('SELECT id,operation_id,upper_bound,remaining_hold,currency,price_version,state FROM budget_reservations WHERE id=%s',(result.reservation_id,)).fetchone()
        scope=db.execute('SELECT message_id,outbox_id,scope_hash,scope_json,valid_until FROM delivery_authorizations WHERE message_id=%s',(result.message_id,)).fetchone()
        outbox=db.execute('SELECT id,intent_key,event_type,payload,state,runtime_backend,runtime_epoch FROM outbox_events WHERE id=%s',(result.outbox_id,)).fetchone()
        liability=db.execute('SELECT message_id,operation_id,reservation_id,max_liability,currency,pricing_version FROM delivery_liabilities WHERE message_id=%s',(result.message_id,)).fetchone()
        return message,hold,scope,outbox,liability

def test_atomic_delivery_reserves_persists_reviewed_scope_and_one_registered_paid_outbox(admission_case):
    client,dsn,args,auth=admission_case;before=counts(dsn);result=run(dsn,args,auth)
    assert result.state=='prepared' and result.replayed is False
    after=counts(dsn);assert tuple(a-b for a,b in zip(after,before))==(1,1,3,1,1,1,1,0)
    message,hold,scope,outbox,liability=snapshot(dsn,result)
    assert message[0:2]==(result.message_id,result.operation_id) and message[2:8]==(args['key'],args['draft_revision_id'],args['recipient_ref'],args['sender_identity_id'],args['approval_id'],args['actor_id']) and message[8:10]==('prepared',None)
    assert hold==(result.reservation_id,result.operation_id,auth.upper_bound,auth.upper_bound,'USD',auth.pricing_version,'active')
    assert scope==(result.message_id,result.outbox_id,auth.scope_hash,auth.scope_json,auth.valid_until)
    assert outbox[0:3]==(result.outbox_id,args['key'],'delivery.submit') and outbox[3]=={'workspace_id':str(args['workspace_id']),'message_id':str(result.message_id),'operation_id':str(result.operation_id),'scope_hash':auth.scope_hash} and outbox[4:] ==('ready','celery',2)
    assert liability==(result.message_id,result.operation_id,result.reservation_id,auth.upper_bound,'USD',auth.pricing_version)
    replay=run(dsn,args,auth);assert replay.replayed and replay.message_id==result.message_id and replay.outbox_id==result.outbox_id and counts(dsn)==after and snapshot(dsn,result)==(message,hold,scope,outbox,liability)
    disabled=client.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{args['draft_id']}/deliver",headers=_h(REVIEWER,key='atomic-private-route-remains-off'))
    assert (disabled.status_code,disabled.json()['code'])==(403,'DELIVERY_DISABLED') and counts(dsn)==after

@pytest.mark.parametrize('state',['unknown','accepted'])
def test_original_unknown_or_accepted_delivery_replays_without_new_key_hold_or_outbox(admission_case,state):
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth)
    with tenant(dsn,WORKSPACE_A) as db:
        db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(result.message_id,))
        db.execute('UPDATE delivery_messages SET state=%s,provider_ref=%s WHERE id=%s',(state,str(uuid.uuid4()) if state=='accepted' else None,result.message_id))
    with psycopg.connect(dsn,autocommit=True) as db:db.execute('UPDATE provider_operations SET status=%s WHERE id=%s',('unknown_acceptance' if state=='unknown' else 'accepted',result.operation_id))
    before=counts(dsn);original=snapshot(dsn,result);replay=run(dsn,args,auth)
    assert replay.replayed and replay.state==state and replay.message_id==result.message_id and counts(dsn)==before and snapshot(dsn,result)==original
    with pytest.raises(ApiError) as error:run(dsn,dict(args,key='delivery:new-key-must-not-resend'),auth)
    assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and counts(dsn)==before and snapshot(dsn,result)==original

@pytest.mark.parametrize('field,value',[('reviewed_contract_hash','c'*64),('upper_bound',Decimal('0.020000')),('pricing_version','delivery-other-v2'),('account_reference','other-original-account'),('valid_until',datetime.now(timezone.utc)+timedelta(hours=1))])
def test_original_delivery_authority_cannot_be_rebound_under_same_intent(admission_case,field,value):
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);before=counts(dsn);original=snapshot(dsn,result)
    with pytest.raises(ApiError) as error:run(dsn,args,replace(auth,**{field:value}))
    assert (error.value.status_code,error.value.code)==(409,'IDEMPOTENCY_CONFLICT') and counts(dsn)==before and snapshot(dsn,result)==original

@pytest.mark.parametrize('field,value',[('selected',False),('reviewed',False),('sender_verified',False),('valid_until',datetime.now(timezone.utc)-timedelta(seconds=1))])
def test_disabled_or_expired_delivery_authority_never_creates_atomic_admission(admission_case,field,value):
    client,dsn,args,auth=admission_case;before=counts(dsn)
    with pytest.raises(ApiError) as error:run(dsn,args,replace(auth,**{field:value}))
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE') and counts(dsn)==before

def test_atomic_delivery_caller_abort_leaves_no_operation_hold_message_liability_or_outbox(admission_case):
    client,dsn,args,auth=admission_case;before=counts(dsn)
    with pytest.raises(RuntimeError,match='owned caller abort'):run(dsn,args,auth,abort=True)
    assert counts(dsn)==before

def test_postwrite_authority_expiry_refusal_rolls_back_even_if_outer_caller_commits(admission_case,monkeypatch):
    client,dsn,args,auth=admission_case;before=counts(dsn);real_datetime=datetime
    class ExpiringClock(real_datetime):
        calls=0
        @classmethod
        def now(cls,tz=None):
            cls.calls+=1
            return real_datetime.now(tz) if cls.calls==1 else auth.valid_until+timedelta(seconds=1)
    monkeypatch.setattr(module(),'datetime',ExpiringClock)
    assert run(dsn,args,auth,catch=True) is None and ExpiringClock.calls==2 and counts(dsn)==before

def test_twelve_parallel_same_intent_admissions_commit_one_original_liability(admission_case):
    client,dsn,args,auth=admission_case;before=counts(dsn)
    async def parallel():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)),pool_size=12,max_overflow=0)
        try:
            async def one():
                async with tenant_session(engine,args['workspace_id']) as session:return await module().admit_delivery(session,authorization=auth,environment='test',**args)
            return await asyncio.gather(*(one() for _ in range(12)))
        finally:await engine.dispose()
    results=asyncio.run(parallel());assert len({x.message_id for x in results})==len({x.operation_id for x in results})==len({x.reservation_id for x in results})==len({x.outbox_id for x in results})==1 and sum(not x.replayed for x in results)==1
    assert tuple(a-b for a,b in zip(counts(dsn),before))==(1,1,3,1,1,1,1,0)

def test_delivery_authority_force_RLS_owned_positive_foreign_denial_and_immutable_runtime_grants(admission_case):
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);original=snapshot(dsn,result)
    with tenant(dsn,WORKSPACE_A) as db:
        assert db.execute('SELECT scope_hash,scope_json FROM delivery_authorizations WHERE message_id=%s',(result.message_id,)).fetchone()==(auth.scope_hash,auth.scope_json)
        assert db.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()==(False,False)
        assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='delivery_authorizations'").fetchone()==(True,True)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():db.execute('UPDATE delivery_authorizations SET scope_hash=%s WHERE message_id=%s',('c'*64,result.message_id))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.transaction():db.execute('DELETE FROM delivery_authorizations WHERE message_id=%s',(result.message_id,))
    with tenant(dsn,WORKSPACE_B) as db:assert db.execute('SELECT scope_hash FROM delivery_authorizations WHERE message_id=%s',(result.message_id,)).fetchall()==[]
    with psycopg.connect(dsn) as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            with db.transaction():db.execute('UPDATE delivery_authorizations SET valid_until=valid_until+interval \'1 second\' WHERE message_id=%s',(result.message_id,))
    assert snapshot(dsn,result)==original

def test_populated_authority_downgrade_refuses_and_retains_original_refs_and_full_hold(admission_case,monkeypatch):
    from buyeros_api.settings import get_settings
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);original=snapshot(dsn,result)
    monkeypatch.setenv('BUYEROS_DATABASE_URL',dsn);get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError,match='retain original delivery authority'):command.downgrade(config(),'0049_c61_delivery_money')
        assert snapshot(dsn,result)==original
        with psycopg.connect(dsn) as db:assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('0053_resumable_documents',)
    finally:get_settings.cache_clear()


def test_registered_delivery_handler_refuses_without_db_or_common_contact_adapter():
    from buyeros_api.execution import handlers
    from buyeros_api.execution.registry import get_handler
    from buyeros_api.providers.base import Service
    from typing import get_args
    assert set(get_args(Service))=={'search','model','contact'}
    result=asyncio.run(get_handler('delivery.submit')(DenySession(),{},{}))
    assert result.state=='blocked' and 'not selected' in result.detail


@pytest.mark.parametrize('environment',['production','unrecognized'])
def test_new_delivery_paid_gate_remains_closed_before_db_io(admission_case,monkeypatch,environment):
    client,dsn,args,auth=admission_case
    from buyeros_api.settings import get_settings
    monkeypatch.setenv('BUYEROS_PAID_ADMISSION_ENABLED','false');get_settings.cache_clear()
    try:
        with pytest.raises(ApiError) as error:asyncio.run(module().admit_delivery(DenySession(),authorization=auth,environment=environment,**args))
        assert (error.value.status_code,error.value.code)==(503,'CAPABILITY_DISABLED')
    finally:get_settings.cache_clear()


@pytest.mark.parametrize('scope',['workspace_id','project_id','sender_identity_id','recipient_refs'])
def test_atomic_admission_requires_exact_current_selected_authority_scope(admission_case,scope):
    client,dsn,args,auth=admission_case;before=counts(dsn)
    changed=replace(auth,**{scope:(uuid.uuid4(),) if scope=='recipient_refs' else uuid.uuid4()})
    with pytest.raises(ApiError) as error:run(dsn,args,changed)
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE') and counts(dsn)==before


@pytest.mark.parametrize('budget',['missing','frozen','zero'])
def test_atomic_admission_budget_refusal_rolls_back_original_operation_and_all_bindings(admission_case,budget):
    client,dsn,args,auth=admission_case;before=counts(dsn)
    with psycopg.connect(dsn,autocommit=True) as db:
        predicate=" WHERE workspace_id=%s AND scope='category' AND scope_id=%s AND category='delivery'"
        if budget=='missing':db.execute('DELETE FROM budget_accounts'+predicate,(WORKSPACE_A,PROJECT))
        else:db.execute('UPDATE budget_accounts SET '+('frozen=true' if budget=='frozen' else 'approved_limit=0')+predicate,(WORKSPACE_A,PROJECT))
    with pytest.raises(ApiError) as error:run(dsn,args,auth)
    assert (error.value.status_code,error.value.code)==(409,'BUDGET_LIMIT') and counts(dsn)==before


def test_atomic_admission_disabled_selector_creates_no_operation_hold_or_paid_outbox(admission_case):
    client,dsn,args,auth=admission_case;before=counts(dsn)
    with psycopg.connect(dsn,autocommit=True) as db:db.execute('UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1 WHERE singleton=1')
    with pytest.raises(ApiError) as error:run(dsn,args,auth)
    assert (error.value.status_code,error.value.code)==(503,'CAPABILITY_DISABLED') and counts(dsn)==before


def dispatch_flags(monkeypatch,*,paid,delivery,cloudflare=False):
    from buyeros_api.execution.config import get_settings as worker_settings
    from buyeros_api.settings import get_settings as api_settings
    for name,value in [('BUYEROS_PAID_DISPATCH_ENABLED',paid),('BUYEROS_DELIVERY_DISPATCH_ENABLED',delivery),('BUYEROS_CELERY_EXECUTION_ENABLED',True),('BUYEROS_CLOUDFLARE_EXECUTION_ENABLED',cloudflare)]:monkeypatch.setenv(name,str(value).lower())
    worker_settings.cache_clear();api_settings.cache_clear()



def worker_dsn(dsn):
    from urllib.parse import urlsplit,urlunsplit
    with psycopg.connect(dsn,autocommit=True) as db:db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
    parts=urlsplit(dsn);host=f'[{parts.hostname}]' if ':' in parts.hostname else parts.hostname
    result=urlunsplit(parts._replace(netloc=f'buyeros_worker:test-only@{host}:{parts.port}'))
    with psycopg.connect(result) as db:
        assert db.execute('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()==(False,False)
        assert db.execute("SELECT has_column_privilege(current_user,'worker_runtime_control','cursor','UPDATE'),has_column_privilege(current_user,'worker_runtime_control','enabled','UPDATE')").fetchone()==(True,False)
    return result

def claim(dsn,args,*,backend='celery',epoch=2):
    from buyeros_api.execution.dispatcher import claim_outbox_rows
    async def apply():
        engine=create_async_engine(async_database_url(worker_dsn(dsn)))
        try:
            async with tenant_session(engine,args['workspace_id']) as session:return await claim_outbox_rows(session,str(uuid.uuid4()),10,datetime.now(timezone.utc),120,backend=backend,epoch=epoch)
        finally:await engine.dispose()
    return asyncio.run(apply())


@pytest.mark.parametrize('paid,delivery',[(True,False),(False,True),(True,True)])
def test_paid_dispatcher_requires_both_independent_flags_and_retains_original_hold(admission_case,monkeypatch,paid,delivery):
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);before=counts(dsn);original=snapshot(dsn,result)
    dispatch_flags(monkeypatch,paid=paid,delivery=delivery)
    try:
        rows=claim(dsn,args)
        assert len(rows)==int(paid and delivery)
        if rows:assert rows[0]['id']==result.outbox_id and rows[0]['event_type']=='delivery.submit' and rows[0]['fencing_generation']==1
        after=snapshot(dsn,result);assert after[:3]==original[:3] and after[4]==original[4] and counts(dsn)==before
        assert after[3][4]==('dispatched' if rows else 'ready')
        if not rows:assert after==original
    finally:
        from buyeros_api.execution.config import get_settings
        get_settings.cache_clear()


@pytest.mark.parametrize('enabled',[False,True])
def test_native_delivery_step_never_routes_to_common_contact_and_keeps_full_hold(admission_case,monkeypatch,enabled):
    from buyeros_api.api.worker_schemas import JobEnvelope
    from buyeros_api.services.worker_execution import execute_step
    from buyeros_api.execution import provider_dispatch
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);original=snapshot(dsn,result);before=counts(dsn)
    with psycopg.connect(dsn,autocommit=True) as db:db.execute("UPDATE worker_runtime_control SET backend='cloudflare',epoch=epoch+1 WHERE singleton=1")
    dispatch_flags(monkeypatch,paid=True,delivery=True,cloudflare=True);rows=claim(dsn,args,backend='cloudflare',epoch=3);assert len(rows)==1 and rows[0]['id']==result.outbox_id
    dispatch_flags(monkeypatch,paid=enabled,delivery=enabled,cloudflare=True)
    async def forbidden(*a,**kw):raise AssertionError('delivery must not invoke common contact/search/model provider')
    monkeypatch.setattr(provider_dispatch,'execute_provider_claimed',forbidden)
    envelope=JobEnvelope(v=1,workspace_id=args['workspace_id'],outbox_id=result.outbox_id,generation=1,runtime_epoch=3)
    async def exercise():
        engine=create_async_engine(async_database_url(worker_dsn(dsn)))
        try:return await execute_step(engine,envelope,'start',adapter=DenySession(),environment='test')
        finally:await engine.dispose()
    try:
        reply=asyncio.run(exercise());assert (reply.state,reply.code)==('blocked','CAPABILITY_UNAVAILABLE' if enabled else 'EXECUTION_DISABLED')
        after=snapshot(dsn,result);assert after[:3]==original[:3] and after[4]==original[4] and counts(dsn)==before
        with psycopg.connect(dsn) as db:assert db.execute('SELECT state FROM worker_steps WHERE outbox_id=%s',(result.outbox_id,)).fetchone()==('blocked',)
    finally:
        from buyeros_api.execution.config import get_settings as worker_settings
        from buyeros_api.settings import get_settings as api_settings
        worker_settings.cache_clear();api_settings.cache_clear()


@pytest.mark.parametrize('gate',['operator','inactive','policy','suppression','revision','authority-none','authority-disabled'])
def test_original_unknown_replay_refusal_keeps_exact_refs_authority_and_full_hold(admission_case,gate):
    from tests.test_lookup_quotes_db import OPERATOR
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth)
    with tenant(dsn,WORKSPACE_A) as db:
        db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(result.message_id,));db.execute("UPDATE delivery_messages SET state='unknown' WHERE id=%s",(result.message_id,))
    with psycopg.connect(dsn,autocommit=True) as db:
        db.execute("UPDATE provider_operations SET status='unknown_acceptance' WHERE id=%s",(result.operation_id,))
        if gate=='inactive':db.execute('UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,args['actor_id']))
        elif gate=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
        elif gate=='suppression':db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) VALUES (%s,%s,%s,'contact_point',%s,%s,'outreach',ARRAY['outreach'],'owned admission opt out',true,%s)",(uuid.uuid4(),WORKSPACE_A,'d'*64,args['recipient_ref'],WORKSPACE_A,args['actor_id']))
        elif gate=='revision':db.execute("UPDATE outreach_drafts SET state='draft',state_version=state_version+1 WHERE id=%s",(args['draft_id'],))
    before=counts(dsn);original=snapshot(dsn,result)
    if gate=='operator':args=dict(args,actor_id=uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR))
    elif gate=='authority-none':auth=None
    elif gate=='authority-disabled':auth=replace(auth,selected=False)
    expected={'operator':(403,'PERMISSION_DENIED'),'inactive':(403,'PERMISSION_DENIED'),'policy':(403,'POLICY_BLOCKED'),'suppression':(403,'POLICY_BLOCKED'),'revision':(412,'STALE_REVISION'),'authority-none':(503,'PROVIDER_UNAVAILABLE'),'authority-disabled':(503,'PROVIDER_UNAVAILABLE')}
    with pytest.raises(ApiError) as error:run(dsn,args,auth)
    assert (error.value.status_code,error.value.code)==expected[gate] and counts(dsn)==before and snapshot(dsn,result)==original


def test_twelve_parallel_different_keys_cannot_resend_same_original_revision(admission_case):
    client,dsn,args,auth=admission_case;before=counts(dsn)
    async def parallel():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)),pool_size=12,max_overflow=0)
        async def one(number):
            try:
                async with tenant_session(engine,args['workspace_id']) as session:return await module().admit_delivery(session,authorization=auth,environment='test',**dict(args,key='delivery:race-key-'+str(number)))
            except ApiError as error:return error
        try:return await asyncio.gather(*(one(x) for x in range(12)))
        finally:await engine.dispose()
    results=asyncio.run(parallel());ok=[x for x in results if not isinstance(x,ApiError)];denied=[x for x in results if isinstance(x,ApiError)]
    assert len(ok)==1 and len(denied)==11 and all((x.status_code,x.code)==(409,'RETRY_UNSAFE') for x in denied)
    assert tuple(a-b for a,b in zip(counts(dsn),before))==(1,1,3,1,1,1,1,0)


def sql_authority_probe(dsn,args,result,auth,*,metadata=None,message_id=None,outbox_id=None,raw=None,digest=None,keep_original=False):
    import hashlib
    text=raw if raw is not None else json.dumps(metadata if metadata is not None else json.loads(auth.scope_json),sort_keys=True,separators=(',',':'))
    hashed=digest or hashlib.sha256(text.encode()).hexdigest()
    with psycopg.connect(dsn) as db:
        # Modifications are deliberately rolled back inside this owned child.
        if not keep_original:db.execute('DELETE FROM delivery_authorizations WHERE message_id=%s',(result.message_id,))
        db.execute("UPDATE outbox_events SET payload=jsonb_set(payload,'{scope_hash}',to_jsonb(%s::text)) WHERE id=%s",(hashed,result.outbox_id))
        db.execute('SET LOCAL ROLE buyeros_api');db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(args['workspace_id']),))
        try:
            with db.transaction():db.execute('INSERT INTO delivery_authorizations(id,workspace_id,message_id,outbox_id,scope_hash,scope_json,valid_until) VALUES (%s,%s,%s,%s,%s,%s,%s)',(uuid.uuid4(),args['workspace_id'],message_id or result.message_id,outbox_id or result.outbox_id,hashed,text,auth.valid_until))
        finally:db.rollback()


@pytest.mark.parametrize('field',['workspace_id','project_id','sender_identity_id','recipient_refs','provider_name','account_reference','upper_bound','pricing_version','message_id','outbox_id'])
def test_SQL_authority_requires_exact_original_message_liability_scope_and_paid_outbox(admission_case,field):
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);original=snapshot(dsn,result);before=counts(dsn)
    metadata=json.loads(auth.scope_json);bindings={}
    if field in ('message_id','outbox_id'):bindings[field]=uuid.uuid4()
    elif field=='recipient_refs':metadata[field]=[str(uuid.uuid4())]
    elif field in ('workspace_id','project_id','sender_identity_id'):metadata[field]=str(uuid.uuid4())
    elif field=='upper_bound':metadata[field]='0.020000'
    else:metadata[field]='other-reviewed-original'
    with pytest.raises(psycopg.errors.ForeignKeyViolation):sql_authority_probe(dsn,args,result,auth,metadata=metadata,**bindings)
    assert snapshot(dsn,result)==original and counts(dsn)==before


@pytest.mark.parametrize('field',['missing','extra','duplicate-json','selected-string','selected-false','expiry','currency','legacy-tariff','recipient-empty','recipient-duplicate','hash'])
def test_SQL_authority_refuses_incomplete_ambiguous_expired_or_unhashed_metadata(admission_case,field):
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);metadata=json.loads(auth.scope_json);bindings={};original=snapshot(dsn,result)
    if field=='missing':metadata.pop('selected')
    elif field=='extra':metadata['client_selected']=True
    elif field=='duplicate-json':bindings['raw']=auth.scope_json[:-1]+',"selected":true}'
    elif field=='selected-string':metadata['selected']='true'
    elif field=='selected-false':metadata['selected']=False
    elif field=='expiry':metadata['valid_until']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    elif field=='currency':metadata['currency']='HKD'
    elif field=='legacy-tariff':metadata['pricing_version']='legacy-guessed'
    elif field=='recipient-empty':metadata['recipient_refs']=[]
    elif field=='recipient-duplicate':metadata['recipient_refs']*=2
    elif field=='hash':bindings['digest']='f'*64
    with pytest.raises(psycopg.errors.CheckViolation):sql_authority_probe(dsn,args,result,auth,metadata=metadata,**bindings)
    assert snapshot(dsn,result)==original


def test_SQL_original_message_and_outbox_cannot_acquire_a_second_authority(admission_case):
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth);original=snapshot(dsn,result)
    with pytest.raises(psycopg.errors.UniqueViolation):sql_authority_probe(dsn,args,result,auth,keep_original=True)
    assert snapshot(dsn,result)==original


def test_empty0050_downgrade_and_reupgrade_restore_exact_head_receipt_guards(isolated_quote_case,monkeypatch):
    from buyeros_api.settings import get_settings
    client,dsn,buyers=isolated_quote_case
    monkeypatch.setenv('BUYEROS_DATABASE_URL',dsn);get_settings.cache_clear()
    def guards():
        with psycopg.connect(dsn) as db:return db.execute('SELECT buyeros_search_receipts_writable(),buyeros_model_receipts_writable(),buyeros_contact_receipts_writable()').fetchone()
    try:
        assert guards()==(True,True,True)
        with psycopg.connect(dsn) as db:
            db.execute("UPDATE alembic_version SET version_num='unreviewed_future_head'")
            assert db.execute('SELECT buyeros_search_receipts_writable(),buyeros_model_receipts_writable(),buyeros_contact_receipts_writable()').fetchone()==(False,False,False)
            db.rollback()
        command.downgrade(config(),'0049_c61_delivery_money')
        with psycopg.connect(dsn) as db:assert db.execute("SELECT version_num,to_regclass('public.delivery_authorizations') FROM alembic_version").fetchone()==('0049_c61_delivery_money',None)
        assert guards()==(True,True,True)
        command.upgrade(config(),'head');assert guards()==(True,True,True)
        with psycopg.connect(dsn) as db:assert db.execute("SELECT version_num,to_regclass('public.delivery_authorizations') FROM alembic_version").fetchone()==('0053_resumable_documents','delivery_authorizations')
    finally:
        try:command.upgrade(config(),'head')
        finally:get_settings.cache_clear()


def test_new_approved_revision_and_new_key_cannot_hide_original_unknown_delivery(admission_case):
    from tests.test_draft_approval_context_db import _review,_approval_payload
    client,dsn,args,auth=admission_case;result=run(dsn,args,auth)
    with tenant(dsn,WORKSPACE_A) as db:
        db.execute("UPDATE delivery_messages SET state='submitting' WHERE id=%s",(result.message_id,));db.execute("UPDATE delivery_messages SET state='unknown' WHERE id=%s",(result.message_id,))
    revision=uuid.uuid4()
    with psycopg.connect(dsn,autocommit=True) as db:
        db.execute("UPDATE provider_operations SET status='unknown_acceptance' WHERE id=%s",(result.operation_id,))
        # A distinct immutable successor exists; the original revision/approval
        # are retained, and the successor receives a real current API approval.
        db.execute('INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,content,content_hash,evidence_ids,offer_fact_ids) SELECT %s,workspace_id,draft_id,2,content,content_hash,evidence_ids,offer_fact_ids FROM draft_revisions WHERE id=%s',(revision,args['draft_revision_id']))
        db.execute("UPDATE approvals SET invalidated_reason='owned successor',invalidated_at=now() WHERE id=%s",(args['approval_id'],))
        db.execute("UPDATE outreach_drafts SET current_revision=2,state='draft',state_version=state_version+1,review_context_hash=NULL,review_revision_id=NULL,review_context=NULL WHERE id=%s",(args['draft_id'],))
    review=_review(client,str(args['draft_id']),key='admission-successor-review');assert review.status_code==200,review.text
    approved=client.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{args['draft_id']}/approvals",json=_approval_payload(review),headers=_h(REVIEWER,key='admission-successor-approve',**{'If-Match':f'"{review.json()["data"]["version"]}"'}));assert approved.status_code==201,approved.text
    fresh=dict(args,draft_revision_id=revision,approval_id=uuid.UUID(approved.json()['data']['id']),key='delivery:new-approved-successor-key')
    before=counts(dsn);original=snapshot(dsn,result)
    with pytest.raises(ApiError) as error:run(dsn,fresh,auth)
    assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and counts(dsn)==before and snapshot(dsn,result)==original
