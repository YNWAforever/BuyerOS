"""Independent delivery cost gate under actual current approval and tenant RLS.

No delivery message/outbox/submit is installed by this budget boundary.
"""
import asyncio,importlib,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.api.errors import ApiError
from buyeros_api.db.session import tenant_session
from tests.conftest import runtime_role_dsn
from tests.test_api_projects_db import api
from tests.test_delivery_preparation_db import approved
from tests.test_lookup_quotes_db import quote_case,WORKSPACE_A,PROJECT,REVIEWER,OPERATOR,_h

def module():
    path=Path(__file__).resolve().parents[1]/'buyeros_api/services/delivery_budget.py'
    assert path.is_file(),'independent delivery budget boundary is missing'
    return importlib.import_module('buyeros_api.services.delivery_budget')

def limits(dsn,amount='1.000000'):
    # Owned schemafixture funding only; production never obtains synthetic authority.
    with psycopg.connect(dsn,autocommit=True) as db:
        for scope,scope_id,category in [('workspace',WORKSPACE_A,'all'),('project',PROJECT,'all'),('category',PROJECT,'delivery')]:
            db.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,approved_limit,settled_spend) VALUES (%s,%s,%s,%s,%s,'USD',to_char(now(),'YYYY-MM'),date_trunc('month',now()),date_trunc('month',now())+interval '1 month',%s,0) ON CONFLICT(workspace_id,scope,scope_id,category,currency,period_start) DO UPDATE SET approved_limit=EXCLUDED.approved_limit,frozen=false",(uuid.uuid4(),WORKSPACE_A,scope,scope_id,category,amount))

def authority(args):
    return module().DeliveryBudgetAuthorization(workspace_id=args['workspace_id'],project_id=uuid.UUID(PROJECT),sender_identity_id=args['sender_identity_id'],recipient_refs=(args['recipient_ref'],),provider_name='resend',account_reference='owned-delivery-budget-fixture',pricing_version='delivery-reviewed-owned-v1',upper_bound=Decimal('0.010000'),currency='USD',reviewed_contract_hash='b'*64,selected=True,reviewed=True,sender_verified=True,valid_until=datetime.now(timezone.utc)+timedelta(minutes=10))

def counts(dsn):
    with psycopg.connect(dsn) as db:
        return tuple(db.execute('SELECT count(*) FROM '+table+' WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0] for table in ('budget_reservations','budget_reservation_allocations','cost_events','outbox_events','delivery_messages','delivery_liabilities'))

def run(dsn,args,authorization,operation=None,*,create=True,rollback=False,operation_changes=None):
    async def apply():
        from buyeros_api.services.delivery_service import prepare_delivery_intent
        from buyeros_api.db.contact import ProviderOperation
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine,args['workspace_id']) as session:
                op=operation or uuid.uuid4()
                if create:
                    original=await prepare_delivery_intent(session,**args)
                    values=dict(id=op,workspace_id=args['workspace_id'],intent_key=args['key'],capability='delivery',input_hash=original.intent.payload_digest,provider_name='resend',account_reference='owned-delivery-budget-fixture',status='intent')
                    values.update(operation_changes or {});session.add(ProviderOperation(**values))
                    await session.flush()
                result=await module().reserve_delivery_operation(session,operation_id=op,authorization=authorization,**args)
                if rollback:raise RuntimeError('owned caller abort after reserve')
                return op,result
        finally:await engine.dispose()
    return asyncio.run(apply())

def test_delivery_budget_reserves_original_operation_in_three_exact_scopes_and_keeps_public403(quote_case):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);before=counts(dsn)
    operation,reservation=run(dsn,args,authority(args))
    with psycopg.connect(dsn) as db:
        row=db.execute('SELECT operation_id,upper_bound,remaining_hold,currency,price_version,state FROM budget_reservations WHERE id=%s',(reservation,)).fetchone()
        assert row==(operation,Decimal('0.010000'),Decimal('0.010000'),'USD','delivery-reviewed-owned-v1','active')
        allocations=db.execute('SELECT a.scope,a.scope_id,a.category FROM budget_accounts a JOIN budget_reservation_allocations x ON x.workspace_id=a.workspace_id AND x.account_id=a.id WHERE x.reservation_id=%s',(reservation,)).fetchall()
        assert set(allocations)=={('workspace',uuid.UUID(WORKSPACE_A),'all'),('project',uuid.UUID(PROJECT),'all'),('category',uuid.UUID(PROJECT),'delivery')}
    after=counts(dsn);assert after[0]==before[0]+1 and after[1]==before[1]+3 and after[2:]==before[2:]
    disabled=api.post(f"/v1/workspaces/{WORKSPACE_A}/drafts/{args['draft_id']}/deliver",headers=_h(REVIEWER,key='delivery-budget-route-stays-disabled'))
    assert disabled.status_code==403 and disabled.json()['code']=='DELIVERY_DISABLED' and counts(dsn)==after

def test_delivery_budget_missing_selected_authority_never_creates_a_hold(quote_case):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);before=counts(dsn)
    with pytest.raises(ApiError) as error:run(dsn,args,None)
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE') and counts(dsn)==before


def test_delivery_budget_expiry_after_reserve_rolls_back_even_when_caller_catches(quote_case,monkeypatch):
    target=module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);before=counts(dsn)
    original_reserve=target.reserve_operation
    class ExpiredClock(datetime):
        @classmethod
        def now(cls,tz=None):return auth.valid_until+timedelta(seconds=1)
    async def expired_after_actual_reservation(*values,**keywords):
        result=await original_reserve(*values,**keywords)
        monkeypatch.setattr(target,'datetime',ExpiredClock)
        return result
    monkeypatch.setattr(target,'reserve_operation',expired_after_actual_reservation)
    async def apply():
        from buyeros_api.services.delivery_service import prepare_delivery_intent
        from buyeros_api.db.contact import ProviderOperation
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)))
        try:
            async with tenant_session(engine,args['workspace_id']) as session:
                prepared=await prepare_delivery_intent(session,**args);operation=uuid.uuid4()
                session.add(ProviderOperation(id=operation,workspace_id=args['workspace_id'],intent_key=args['key'],capability='delivery',input_hash=prepared.intent.payload_digest,provider_name=auth.provider_name,account_reference=auth.account_reference,status='intent'))
                await session.flush()
                try:
                    await target.reserve_delivery_operation(session,operation_id=operation,authorization=auth,**args)
                    result='ACCEPTED'
                except ApiError as error:
                    assert error.status_code==503;result=error.code
                # Deliberately commit the outer caller after catching the refusal.
                return result,operation
        finally:await engine.dispose()
    result,operation=asyncio.run(apply())
    assert result=='PROVIDER_UNAVAILABLE','authority expired during real reservation but helper returned a live hold'
    assert counts(dsn)==before,'caught expiry must roll back every reservation/allocation within the helper'
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT status FROM provider_operations WHERE id=%s',(operation,)).fetchone()==('intent',)
        assert db.execute('SELECT count(*) FROM budget_reservations WHERE operation_id=%s',(operation,)).fetchone()[0]==0


@pytest.mark.parametrize('changed',['selected','reviewed','sender_verified','expired','workspace','project','sender','recipient'])
def test_delivery_budget_current_selected_scope_is_required_before_any_hold(quote_case,changed):
    target=module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);before=counts(dsn)
    if changed in ('selected','reviewed','sender_verified'):auth=replace(auth,**{changed:False})
    elif changed=='expired':auth=replace(auth,valid_until=datetime.now(timezone.utc)-timedelta(seconds=1))
    elif changed=='recipient':auth=replace(auth,recipient_refs=(uuid.uuid4(),))
    else:auth=replace(auth,**{dict(workspace='workspace_id',project='project_id',sender='sender_identity_id')[changed]:uuid.uuid4()})
    with pytest.raises(ApiError) as error:run(dsn,args,auth)
    assert (error.value.status_code,error.value.code)==(503,'PROVIDER_UNAVAILABLE') and counts(dsn)==before

@pytest.mark.parametrize('changed',['key','provider','account','upper_bound','pricing_version'])
def test_delivery_budget_original_unknown_hold_cannot_be_rebound_or_released(quote_case,changed):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);operation,reservation=run(dsn,args,auth);before=counts(dsn)
    with psycopg.connect(dsn,autocommit=True) as db:db.execute("UPDATE provider_operations SET status='unknown_acceptance' WHERE id=%s",(operation,))
    assert run(dsn,args,auth,operation,create=False)==(operation,reservation) and counts(dsn)==before
    if changed=='key':args={**args,'key':'delivery:changed-original-key'}
    elif changed=='provider':auth=replace(auth,provider_name='other-reviewed-provider')
    elif changed=='account':auth=replace(auth,account_reference='other-reviewed-account')
    elif changed=='upper_bound':auth=replace(auth,upper_bound=Decimal('0.020000'))
    else:auth=replace(auth,pricing_version='new-reviewed-delivery-v2')
    with pytest.raises(ApiError) as error:run(dsn,args,auth,operation,create=False)
    assert (error.value.status_code,error.value.code)==(409,'IDEMPOTENCY_CONFLICT') and counts(dsn)==before
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT remaining_hold,state FROM budget_reservations WHERE id=%s',(reservation,)).fetchone()==(Decimal('0.010000'),'active')
        assert db.execute('SELECT status FROM provider_operations WHERE id=%s',(operation,)).fetchone()==('unknown_acceptance',)

def test_delivery_budget_disabled_new_authority_retains_original_unknown_full_hold(quote_case):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);operation,reservation=run(dsn,args,auth);before=counts(dsn)
    with psycopg.connect(dsn,autocommit=True) as db:db.execute("UPDATE provider_operations SET status='unknown_acceptance' WHERE id=%s",(operation,))
    with pytest.raises(ApiError) as error:run(dsn,args,None,operation,create=False)
    assert error.value.code=='PROVIDER_UNAVAILABLE' and counts(dsn)==before
    with psycopg.connect(dsn) as db:assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(reservation,)).fetchone()==(Decimal('0.010000'),)

@pytest.mark.parametrize('changed',['contact-category','wrong-key','wrong-digest','wrong-provider','wrong-account'])
def test_delivery_budget_cannot_borrow_contact_or_foreign_original_operation(quote_case,changed):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);before=counts(dsn)
    changes={'contact-category':{'capability':'contact_lookup'},'wrong-key':{'intent_key':'delivery:wrong-key'},'wrong-digest':{'input_hash':'c'*64},'wrong-provider':{'provider_name':'other-provider'},'wrong-account':{'account_reference':'other-account'}}
    with pytest.raises(ApiError) as error:run(dsn,args,auth,operation_changes=changes[changed])
    assert (error.value.status_code,error.value.code)==(409,'IDEMPOTENCY_CONFLICT') and counts(dsn)==before

def test_delivery_budget_nonintent_without_original_hold_requires_reconciliation(quote_case):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);before=counts(dsn)
    with pytest.raises(ApiError) as error:run(dsn,args,authority(args),operation_changes={'status':'unknown_acceptance'})
    assert (error.value.status_code,error.value.code)==(409,'RETRY_UNSAFE') and counts(dsn)==before

@pytest.mark.parametrize('changed',['zero-delivery','frozen-delivery','existing-unknown'])
def test_delivery_budget_independent_limit_is_required_and_unknown_hold_blocks_new_intent(quote_case,changed):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args)
    if changed=='existing-unknown':
        operation,reservation=run(dsn,args,auth)
        with psycopg.connect(dsn,autocommit=True) as db:
            db.execute("UPDATE provider_operations SET status='unknown_acceptance' WHERE id=%s",(operation,))
            db.execute("UPDATE budget_accounts SET approved_limit=0.01 WHERE workspace_id=%s AND scope='category' AND scope_id=%s AND category='delivery'",(WORKSPACE_A,PROJECT))
        args={**args,'key':'delivery:new-intent-with-original-unknown-hold'}
    else:
        with psycopg.connect(dsn,autocommit=True) as db:
            sql="UPDATE budget_accounts SET "+('approved_limit=0' if changed=='zero-delivery' else 'frozen=true')+" WHERE workspace_id=%s AND scope='category' AND scope_id=%s AND category='delivery'"
            db.execute(sql,(WORKSPACE_A,PROJECT))
    before=counts(dsn)
    with pytest.raises(ApiError) as error:run(dsn,args,auth)
    assert (error.value.status_code,error.value.code)==(409,'BUDGET_LIMIT') and counts(dsn)==before
    if changed=='existing-unknown':
        with psycopg.connect(dsn) as db:assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(reservation,)).fetchone()==(Decimal('0.010000'),)

def test_delivery_budget_caller_abort_rolls_back_original_operation_and_all_allocations(quote_case):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);before=counts(dsn)
    with psycopg.connect(dsn) as db:operations=db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0]
    with pytest.raises(RuntimeError,match='owned caller abort'):run(dsn,args,authority(args),rollback=True)
    assert counts(dsn)==before
    with psycopg.connect(dsn) as db:assert db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0]==operations

@pytest.mark.parametrize('changed',['operator','policy','suppression','revision'])
def test_delivery_budget_replay_rechecks_current_reviewer_and_exact_approval(quote_case,changed):
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);operation,reservation=run(dsn,args,auth);before=counts(dsn)
    if changed=='operator':args={**args,'actor_id':uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)}
    else:
        with psycopg.connect(dsn,autocommit=True) as db:
            if changed=='policy':db.execute("UPDATE policy_decisions SET status='blocked',version=version+1 WHERE workspace_id=%s AND purpose='outreach'",(WORKSPACE_A,))
            elif changed=='revision':db.execute("UPDATE outreach_drafts SET state='draft',state_version=state_version+1 WHERE id=%s",(args['draft_id'],))
            else:db.execute("INSERT INTO suppressions(id,workspace_id,subject_key_hash,subject_type,subject_id,controller_scope_id,purpose,purposes,reason,active,actor_id) VALUES (%s,%s,%s,'contact_point',%s,%s,'outreach',ARRAY['outreach'],'owned delivery budget opt out',true,%s)",(uuid.uuid4(),WORKSPACE_A,'d'*64,args['recipient_ref'],WORKSPACE_A,args['actor_id']))
    with pytest.raises(ApiError) as error:run(dsn,args,auth,operation,create=False)
    assert error.value.status_code in (403,412) and error.value.code in ('PERMISSION_DENIED','POLICY_BLOCKED','STALE_REVISION') and counts(dsn)==before
    with psycopg.connect(dsn) as db:assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(reservation,)).fetchone()==(Decimal('0.010000'),)

def test_delivery_budget_twelve_parallel_replays_create_one_three_scope_hold(quote_case):
    from tests.test_delivery_preparation_db import prepare
    target=module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);prepared=prepare(api,args);operation=uuid.uuid4();before=counts(dsn)
    with psycopg.connect(dsn,autocommit=True) as db:db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,provider_name,account_reference,status) VALUES (%s,%s,%s,'delivery',%s,%s,%s,'intent')",(operation,WORKSPACE_A,args['key'],prepared.intent.payload_digest,auth.provider_name,auth.account_reference))
    async def race():
        engine=create_async_engine(async_database_url(runtime_role_dsn(dsn)),pool_size=12,max_overflow=0)
        async def one():
            async with tenant_session(engine,args['workspace_id']) as session:return await target.reserve_delivery_operation(session,operation_id=operation,authorization=auth,**args)
        try:return await asyncio.gather(*(one() for _ in range(12)))
        finally:await engine.dispose()
    results=asyncio.run(race());assert len(results)==12 and len(set(results))==1
    after=counts(dsn);assert after[0]==before[0]+1 and after[1]==before[1]+3 and after[2:]==before[2:]
    with psycopg.connect(dsn) as db:assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(results[0],)).fetchone()==(Decimal('0.010000'),)

@pytest.mark.parametrize('amount',[Decimal('NaN'),Decimal('Infinity'),Decimal('-0.01'),Decimal('0'),Decimal('0.0100001'),Decimal('100000000000000'),0.01])
def test_delivery_budget_rejects_nonfinite_unbounded_or_inexact_tariff_without_writes(quote_case,amount):
    module();api,dsn,buyers,args=approved(quote_case);before=counts(dsn)
    with pytest.raises(ValueError,match='bounded exact positive USD'):replace(authority(args),upper_bound=amount)
    assert counts(dsn)==before


def test_delivery_budget_foreign_workspace_is_denied_after_owned_positive_control(quote_case):
    from tests.test_api_tenant_isolation import WORKSPACE_B
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);operation,reservation=run(dsn,args,auth);before=counts(dsn)
    with psycopg.connect(dsn) as db:foreign_before=db.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',(WORKSPACE_B,)).fetchone()[0]
    foreign={**args,'workspace_id':uuid.UUID(WORKSPACE_B)}
    with pytest.raises(ApiError) as error:run(dsn,foreign,auth,operation,create=False)
    assert (error.value.status_code,error.value.code)==(403,'PERMISSION_DENIED') and counts(dsn)==before
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',(WORKSPACE_B,)).fetchone()[0]==foreign_before
        assert db.execute('SELECT remaining_hold FROM budget_reservations WHERE id=%s',(reservation,)).fetchone()==(Decimal('0.010000'),)

def test_delivery_budget_foreign_operation_is_not_found_with_matching_owned_control(quote_case):
    from tests.test_api_tenant_isolation import WORKSPACE_B
    from tests.test_delivery_preparation_db import prepare
    module();api,dsn,buyers,args=approved(quote_case);limits(dsn);auth=authority(args);operation,reservation=run(dsn,args,auth);before=counts(dsn);foreign=uuid.uuid4();prepared=prepare(api,args)
    try:
        with psycopg.connect(dsn,autocommit=True) as db:db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,provider_name,account_reference,status) VALUES (%s,%s,%s,'delivery',%s,%s,%s,'intent')",(foreign,WORKSPACE_B,args['key']+':foreign',prepared.intent.payload_digest,auth.provider_name,auth.account_reference))
        with pytest.raises(ApiError) as error:run(dsn,args,auth,foreign,create=False)
        assert (error.value.status_code,error.value.code,str(error.value.message))==(404,'NOT_FOUND','original delivery operation not found') and counts(dsn)==before
        assert run(dsn,args,auth,operation,create=False)==(operation,reservation) and counts(dsn)==before
    finally:
        with psycopg.connect(dsn,autocommit=True) as db:db.execute('DELETE FROM provider_operations WHERE workspace_id=%s AND id=%s',(WORKSPACE_B,foreign))
