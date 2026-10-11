"""Original-reference GET orchestration under owned PG; no production registry/POST."""
import asyncio,contextlib,importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from pathlib import Path
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.providers.delivery import DeliveryStatusResult
from tests.test_delivery_admission_db import admission_case,run as admit,worker_dsn,dispatch_flags
from tests.test_delivery_status_db import authority,submitted,snapshot,assert_originals_retained
from tests.test_lookup_quotes_db import WORKSPACE_A
from tests.test_api_tenant_isolation import WORKSPACE_B

def module():
    p=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_reconciliation.py'
    assert p.is_file(),'transaction-separated retained status orchestration missing'
    return importlib.import_module('buyeros_api.services.delivery_reconciliation')

class DenyEngine:
    def __getattr__(self,name):raise AssertionError('unselected retained reconciliation must refuse before IO: '+name)

@pytest.fixture
def reconciliation_case(admission_case):
    client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original,ref='original-ref')
    return client,dsn,args,auth,original,authority(args,auth)

class Reader:
    def __init__(self,case,*,result=None,error=None,before_result=None,lock_probe=True):
        self.case=case;self.lock_probe=lock_probe;self.result=result if result is not None else DeliveryStatusResult('accepted','original-ref');self.error=error;self.before_result=before_result;self.calls=[]
    async def status(self):
        ref='original-ref';client,dsn,args,auth,original,retained=self.case
        before=snapshot(dsn,original);assert before['original'][1][2:4]==(auth.upper_bound,auth.upper_bound) and before['cost']==0
        if self.lock_probe:
            with psycopg.connect(dsn) as db:
                db.execute("SET LOCAL lock_timeout='200ms'")
                for query,params in [('SELECT id FROM delivery_messages WHERE id=%s FOR UPDATE NOWAIT',(original.message_id,)),('SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT',(original.outbox_id,)),('SELECT singleton FROM worker_runtime_control WHERE singleton=1 FOR UPDATE NOWAIT',())]:assert db.execute(query,params).fetchone()
        self.calls.append(ref);await asyncio.sleep(0)
        if self.before_result:self.before_result()
        if self.error:raise self.error
        return self.result

def select(case,reader=None,*,factory=None):
    chosen=reader or Reader(case);calls=[]
    def build(ref):
        assert type(ref) is str and ref=='original-ref';calls.append(ref)
        return chosen if factory is None else factory(ref)
    return module().DeliveryReconciliationSelection(case[-1],build),chosen,calls

def apply(case,selection,*,workspace=None,message=None):
    async def run():
        engine=create_async_engine(async_database_url(worker_dsn(case[1])))
        try:return await module().reconcile_delivery_status(engine,workspace_id=workspace or case[2]['workspace_id'],message_id=message or case[4].message_id,selection=selection)
        finally:await engine.dispose()
    return asyncio.run(run())

def test_retained_reconciliation_default_selector_refuses_before_database_or_provider_IO():
    mod=module()
    with pytest.raises(ApiError) as error:asyncio.run(mod.reconcile_delivery_message(DenyEngine(),workspace_id=uuid.uuid4(),message_id=uuid.uuid4()))
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

@pytest.mark.parametrize('fault',['untyped','unreviewed','expired','factory'])
def test_retained_reconciliation_invalid_selection_refuses_before_database_or_provider_IO(fault):
    from buyeros_api.services.delivery_status import DeliveryStatusAuthority
    retained=DeliveryStatusAuthority(uuid.uuid4(),'resend','original-account','a'*64,'b'*64,True,datetime.now(timezone.utc)+timedelta(hours=1))
    if fault=='unreviewed':retained=replace(retained,reviewed=False)
    elif fault=='expired':retained=replace(retained,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    selected=module().DeliveryReconciliationSelection(retained,None if fault=='factory' else lambda ref:None)
    if fault=='untyped':selected={}
    with pytest.raises(ApiError) as error:asyncio.run(module().reconcile_delivery_status(DenyEngine(),workspace_id=retained.workspace_id,message_id=uuid.uuid4(),selection=selected))
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE')

def test_retained_reconciliation_original_GET_closes_all_transactions_and_records_once_without_money(reconciliation_case):
    case=reconciliation_case;selected,reader,factories=select(case);before=snapshot(case[1],case[4]);first=apply(case,selected);second=apply(case,selected);after=snapshot(case[1],case[4])
    assert reader.calls==factories==['original-ref','original-ref']
    assert first.state==second.state=='accepted' and first.event_id==second.event_id and not first.replayed and second.replayed and len(after['events'])==1
    assert after['events'][0][1].startswith('status:');assert_originals_retained(before,after)

def test_retained_reconciliation_survives_revoked_role_policy_flags_and_disabled_runtime(reconciliation_case,monkeypatch):
    case=reconciliation_case;selected,reader,factories=select(case);dispatch_flags(monkeypatch,paid=False,delivery=False,cloudflare=False)
    with psycopg.connect(case[1]) as db:
        db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND user_id=%s',(WORKSPACE_A,case[2]['actor_id']))
        db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
        db.execute('UPDATE worker_runtime_control SET enabled=false,epoch=epoch+1 WHERE singleton=1')
    try:
        before=snapshot(case[1],case[4]);result=apply(case,selected);assert result.state=='accepted' and reader.calls==['original-ref'];assert_originals_retained(before,snapshot(case[1],case[4]))
    finally:
        from buyeros_api.execution.config import get_settings
        get_settings.cache_clear()

@pytest.mark.parametrize('fault',['provider','account','scope','contract'])
def test_retained_reconciliation_original_binding_refuses_before_factory_and_has_owned_control(reconciliation_case,fault):
    case=reconciliation_case;selected,reader,factories=select(case);field={'provider':'provider_name','account':'account_reference','scope':'scope_hash','contract':'reviewed_contract_hash'}[fault]
    selected=replace(selected,authority=replace(case[-1],**{field:'other-provider' if fault=='provider' else 'other-account' if fault=='account' else 'c'*64}));before=snapshot(case[1],case[4])
    with pytest.raises(ApiError) as error:apply(case,selected)
    assert (error.value.status_code,error.value.code)==((404,'NOT_FOUND') if fault in {'provider','account'} else (409,'RETRY_UNSAFE')) and reader.calls==factories==[] and snapshot(case[1],case[4])==before
    good,_,_=select(case);assert apply(case,good).state=='accepted'

def test_retained_reconciliation_foreign_tenant_is404_with_matching_owned_control(reconciliation_case):
    case=reconciliation_case;selected,reader,factories=select(case);selected=replace(selected,authority=replace(case[-1],workspace_id=uuid.UUID(WORKSPACE_B)));before=snapshot(case[1],case[4])
    with pytest.raises(ApiError) as error:apply(case,selected,workspace=uuid.UUID(WORKSPACE_B))
    assert (error.value.status_code,error.value.code)==(404,'NOT_FOUND') and reader.calls==factories==[] and snapshot(case[1],case[4])==before
    good,_,_=select(case);assert apply(case,good).state=='accepted'

def test_retained_reconciliation_lost_original_reference_never_looks_up_key_or_constructs_reader(admission_case):
    client,dsn,args,auth=admission_case;original=admit(dsn,args,auth);submitted(dsn,original,ref=None);case=client,dsn,args,auth,original,authority(args,auth);selected,reader,factories=select(case);before=snapshot(dsn,original)
    with pytest.raises(ApiError) as error:apply(case,selected)
    assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and reader.calls==factories==[] and snapshot(dsn,original)==before

@pytest.mark.parametrize('fault',['submit','estimate','capability','status'])
def test_retained_reconciliation_rejects_common_or_submit_capable_reader_without_GET(reconciliation_case,fault):
    case=reconciliation_case;reader=Reader(case)
    if fault=='capability':reader.capability='contact'
    elif fault=='status':reader.status=None
    else:setattr(reader,fault,lambda *args:None)
    selected,reader,factories=select(case,reader);before=snapshot(case[1],case[4])
    with pytest.raises(ApiError) as error:apply(case,selected)
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE') and reader.calls==[] and snapshot(case[1],case[4])==before

@pytest.mark.parametrize('result',[{'state':'accepted'},DeliveryStatusResult('accepted','foreign-ref')],ids=['untyped','foreign-ref'])
def test_retained_reconciliation_malformed_observation_never_changes_state_hold_or_cost(reconciliation_case,result):
    case=reconciliation_case;selected,reader,_=select(case,Reader(case,result=result));before=snapshot(case[1],case[4])
    with pytest.raises(ApiError) as error:apply(case,selected)
    assert (error.value.status_code,error.value.code)==(422,'INVALID_REQUEST') and reader.calls==['original-ref'] and snapshot(case[1],case[4])==before

def test_retained_reconciliation_network_exception_retains_original_unknown_and_no_new_event(reconciliation_case):
    case=reconciliation_case;selected,reader,_=select(case,Reader(case,error=RuntimeError('secret-bearing provider error must not be logged')));before=snapshot(case[1],case[4]);result=apply(case,selected)
    assert result.state=='unknown' and result.event_id is None and reader.calls==['original-ref'] and snapshot(case[1],case[4])==before

def test_retained_reconciliation_cancellation_retains_original_hold_without_observation(reconciliation_case):
    case=reconciliation_case;selected,reader,_=select(case,Reader(case,error=asyncio.CancelledError()));before=snapshot(case[1],case[4])
    with pytest.raises(asyncio.CancelledError):apply(case,selected)
    assert reader.calls==['original-ref'] and snapshot(case[1],case[4])==before

@pytest.mark.parametrize('phase',['factory','after-GET'])
def test_retained_reconciliation_expiry_at_actual_boundary_refuses_without_local_event(reconciliation_case,phase):
    case=reconciliation_case;expired=case[-1]
    def expire():object.__setattr__(expired,'valid_until',datetime.now(timezone.utc)-timedelta(seconds=1))
    reader=Reader(case,before_result=expire if phase=='after-GET' else None)
    def factory(ref):
        if phase=='factory':expire()
        return reader
    selected,reader,_=select(case,reader,factory=factory);before=snapshot(case[1],case[4])
    with pytest.raises(ApiError) as error:apply(case,selected)
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE') and len(reader.calls)==(1 if phase=='after-GET' else 0) and snapshot(case[1],case[4])==before

@pytest.mark.parametrize('phase',['before-GET','observation'])
def test_retained_reconciliation_failed_transaction_commit_never_creates_partial_event_or_money(reconciliation_case,monkeypatch,phase):
    case=reconciliation_case;mod=module();real=mod.tenant_session;calls=[];selected,reader,factories=select(case);before=snapshot(case[1],case[4])
    @contextlib.asynccontextmanager
    async def fail(*args,**kwargs):
        async with real(*args,**kwargs) as session:
            calls.append(1);yield session
            if len(calls)==(1 if phase=='before-GET' else 2):raise ApiError(500,'INTERNAL_ERROR','owned commit failure')
    monkeypatch.setattr(mod,'tenant_session',fail)
    with pytest.raises(ApiError) as error:apply(case,selected)
    assert error.value.status_code==500 and len(reader.calls)==(0 if phase=='before-GET' else 1) and snapshot(case[1],case[4])==before

def test_retained_reconciliation_parallel_GET_deduplicates_status_event_without_extra_operation_or_hold(reconciliation_case):
    case=reconciliation_case;selected,reader,factories=select(case,Reader(case,lock_probe=False));before=snapshot(case[1],case[4])
    async def race():
        engine=create_async_engine(async_database_url(worker_dsn(case[1])),pool_size=12,max_overflow=0)
        try:return await asyncio.gather(*(module().reconcile_delivery_status(engine,workspace_id=case[2]['workspace_id'],message_id=case[4].message_id,selection=selected) for _ in range(12)))
        finally:await engine.dispose()
    results=asyncio.run(race());after=snapshot(case[1],case[4]);assert len(reader.calls)==len(factories)==12 and len({x.event_id for x in results})==1 and sum(not x.replayed for x in results)==1 and len(after['events'])==1;assert_originals_retained(before,after)

@pytest.mark.parametrize('state',['delivered','bounced','complained','unsubscribed'])
def test_retained_reconciliation_terminal_and_adverse_status_does_not_regress_or_release_full_hold(reconciliation_case,state):
    case=reconciliation_case;before=snapshot(case[1],case[4]);selected,reader,_=select(case,Reader(case,result=DeliveryStatusResult(state,'original-ref')));first=apply(case,selected);duplicate=apply(case,selected);late,_,_=select(case);late_receipt=apply(case,late);after=snapshot(case[1],case[4])
    assert first.state==duplicate.state==late_receipt.state==state and first.event_id==duplicate.event_id and duplicate.replayed and len(after['events'])==2
    assert after['suppression']==before['suppression']+(0 if state=='delivered' else 1);assert_originals_retained(before,after)


@pytest.mark.parametrize('event,expected',[('sent','accepted'),('delivered','delivered'),('bounced','bounced'),('delivery_delayed','unknown')])
def test_actual_bound_cold_Resend_reader_records_original_GET_without_new_send_authority_or_lock(admission_case,event,expected):
    import httpx
    from buyeros_api.providers.resend_delivery import ResendDeliveryStatusReader
    client,dsn,args,auth=admission_case
    if event=='delivered':auth=replace(auth,valid_until=datetime.now(timezone.utc)+timedelta(seconds=2))
    original=admit(dsn,args,auth);ref='49a3999c-0ce1-4ea6-ab68-afcd6dc2e794';submitted(dsn,original,ref=ref);retained=authority(args,auth);before=snapshot(dsn,original);requests=[];clients=[];factories=[]
    async def handler(request):
        assert request.method=='GET' and str(request.url)=='https://api.resend.com/emails/'+ref and request.content==b'' and 'Idempotency-Key' not in request.headers
        current=snapshot(dsn,original);assert current['original'][1][2:4]==(auth.upper_bound,auth.upper_bound) and current['cost']==0
        with psycopg.connect(dsn) as db:
            db.execute("SET LOCAL lock_timeout='200ms'")
            assert db.execute('SELECT id FROM delivery_messages WHERE id=%s FOR UPDATE NOWAIT',(original.message_id,)).fetchone()
            assert db.execute('SELECT id FROM outbox_events WHERE id=%s FOR UPDATE NOWAIT',(original.outbox_id,)).fetchone()
            if event=='delivered':assert db.execute('SELECT valid_until<now() FROM delivery_authorizations WHERE message_id=%s',(original.message_id,)).fetchone()==(True,)
        requests.append(request);return httpx.Response(200,json={'id':ref,'last_event':event})
    def factory(original_ref):
        assert original_ref==ref;factories.append(original_ref);http=httpx.AsyncClient(transport=httpx.MockTransport(handler),trust_env=False);clients.append(http)
        return ResendDeliveryStatusReader(authority=retained,provider_ref=original_ref,api_key='owned-status-wire-test-only',http=http)
    selected=module().DeliveryReconciliationSelection(retained,factory)
    async def run():
        engine=create_async_engine(async_database_url(worker_dsn(dsn)))
        try:
            if event=='delivered':await asyncio.sleep(2.1)
            return await module().reconcile_delivery_status(engine,workspace_id=args['workspace_id'],message_id=original.message_id,selection=selected)
        finally:
            for http in clients:await http.aclose()
            await engine.dispose()
    result=asyncio.run(run());after=snapshot(dsn,original);assert len(requests)==len(factories)==1 and result.state==expected
    assert len(after['events'])==(0 if expected=='unknown' else 1) and after['suppression']==before['suppression']+(1 if expected=='bounced' else 0);assert_originals_retained(before,after)
