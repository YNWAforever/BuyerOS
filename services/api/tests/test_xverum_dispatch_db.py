"""Task9: owned PostgreSQL, native worker and synthetic transport only."""
import importlib.util
import psycopg
import pytest
from tests.xverum_fixtures import credit_case, connection_case, provisional_pg, execution_api, pg


@pytest.fixture(autouse=True)
def thread_entry(monkeypatch):
    # Route registration happens at app construction, before linked_task runs.
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')


def test_dispatch_owner_and_native_route_exist():
    assert importlib.util.find_spec('buyeros_api.services.xverum_dispatch'), 'durable dispatch owner missing'
    from buyeros_api.execution.step_runner import LOCAL_EVENTS
    assert 'xverum.step' in LOCAL_EVENTS


def test_durable_tool_receipts_installed(isolated_seeded):
    with psycopg.connect(isolated_seeded) as db:
        assert db.execute("SELECT to_regclass('public.xverum_tool_receipts')").fetchone()[0]
        assert db.execute("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='xverum_tool_receipts'::regclass").fetchone()[0]


@pytest.fixture
def dispatch_case(credit_case, monkeypatch):
    import uuid
    from urllib.parse import urlsplit, urlunsplit
    from buyeros_api.settings import get_settings
    from buyeros_api.execution.config import get_settings as worker_settings
    from buyeros_api.services import xverum_connections as connections
    from buyeros_api.services.xverum_dispatch import CONTRACT_HASH
    from buyeros_api.sales.contracts import SecretHandle, XverumResult
    from tests.policy_activation_fixtures import approve_provider_fixture
    c=credit_case
    for name in ('BUYEROS_PAID_ADMISSION_ENABLED','BUYEROS_PAID_DISPATCH_ENABLED','BUYEROS_CLOUDFLARE_EXECUTION_ENABLED'):
        monkeypatch.setenv(name,'true')
    get_settings.cache_clear();worker_settings.cache_clear()
    with psycopg.connect(c.dsn) as db:
        db.execute("UPDATE companies SET domain='synthetic.example' WHERE id=(SELECT company_id FROM project_buyers WHERE id=%s)",(c.buyer,))
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only'")
        c.epoch=db.execute("UPDATE worker_runtime_control SET backend='cloudflare',enabled=true,epoch=epoch+1,active_owner=NULL,active_until=NULL RETURNING epoch").fetchone()[0]
    parts=urlsplit(c.dsn)
    c.worker_dsn=urlunsplit(parts._replace(netloc=f'buyeros_worker:test-only@{parts.hostname}:{parts.port}'))
    approve_provider_fixture(c.dsn,c.ws,c.project,c.scope.actor_id,purpose='contact_research',
        scope={'provider_name':'xverum','account_reference':'synthetic-account','contract_sha256':CONTRACT_HASH},
        domains=['synthetic.example'],actions=['contact.enrich'])
    class Credentials:
        enabled=True
        durable_generation_singleflight=True
        async def resolve(self,binding):
            return SecretHandle(connection_id=binding.id,generation=binding.generation,token='synthetic-not-real')
    c.calls=0;c.mode='success';c.claims=[];c.usage=0
    class Transport:
        def __init__(self,*,before_dispatch):self.check=before_dispatch
        async def call(self,tool,arguments,handle):
            await self.check()
            with psycopg.connect(c.dsn) as db:
                proof=db.execute("SELECT state,claim_id FROM xverum_tool_receipts WHERE state='submitting'").fetchall()
                assert proof and all(claim for _,claim in proof), 'claim not committed before external await'
                c.claims.extend(str(claim) for _,claim in proof)
            c.calls+=1
            if c.mode=='lost' or c.mode=='lost_at_'+str(c.calls):
                from buyeros_api.providers.xverum_mcp import XverumTransportError
                raise XverumTransportError('tools/call')
            if tool.startswith('search_'):
                people=tool=='search_people_xverum'
                cards=[]
                if people:
                    from buyeros_api.sales.contracts import XverumPersonCard
                    for i in range(1,4):
                        cards.append({**{key:None for key in XverumPersonCard.model_fields},'id':str(i),'full_name':'Synthetic','evidence_summary':'Synthetic'})
                if not people and getattr(c,'company_cards',False):
                    from buyeros_api.sales.contracts import XverumCompanyCard
                    cards=[{**{key:None for key in XverumCompanyCard.model_fields},'id':'1','company_name':'Synthetic'}]
                projection={'result_type':'people' if people else 'company','results':cards,'total_count':len(cards),'page':1,'page_size':5}
            elif tool=='get_email_xverum':projection={'has_email':False,'emails':[]}
            else:
                from buyeros_api.sales.contracts import XverumPersonDetail
                projection={**{key:None for key in XverumPersonDetail.model_fields},'full_name':'Synthetic','evidence_summary':'Synthetic','experience':[]}
            projection=getattr(c,'projections',{}).get(tool,projection)
            if callable(projection):projection=projection(arguments)
            return XverumResult(tool=tool,request_id='synthetic-request-'+str(c.calls),credits_used=c.usage,credits_remaining=100,projection=projection)
    monkeypatch.setattr(connections,'CREDENTIAL_PROVIDER',Credentials())
    monkeypatch.setattr(connections,'XverumTransport',Transport)
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    async def admit(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic','company',c.buyer)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'dispatch')
    c.admitted=pg(c,admit)
    with psycopg.connect(c.dsn) as db:
        c.outbox=db.execute('SELECT outbox_id FROM xverum_receipts WHERE id=%s',(c.admitted.id,)).fetchone()[0]
    yield c
    get_settings.cache_clear();worker_settings.cache_clear()


def native_dispatch(c):
    from buyeros_api.api.worker_schemas import JobEnvelope
    from buyeros_api.services.worker_execution import execute_step
    from tests.test_sales_execution_db import pg_call
    with psycopg.connect(c.dsn) as db:
        db.execute("UPDATE outbox_events SET state='dispatched',runtime_backend='cloudflare',runtime_epoch=%s,fencing_generation=1 WHERE id=%s",(c.epoch,c.outbox))
    envelope=JobEnvelope(v=1,workspace_id=c.ws,outbox_id=c.outbox,generation=1,runtime_epoch=c.epoch)
    return pg_call(c,lambda engine:execute_step(engine,envelope,'start'))


def test_lost_response_keeps_hold_without_redispatch(dispatch_case):
    from decimal import Decimal
    c=dispatch_case;c.mode='lost'
    assert native_dispatch(c).state=='reconcile'
    native_dispatch(c)
    from buyeros_api.services.xverum_quotes import read_receipt
    async def read(factory):
        for _ in range(3):
            async with factory() as s:
                value=await read_receipt(s,c.scope,c.admitted.id)
                assert value.dispatch_state=='outcome_unknown' and value.held_credits==5
    pg(c,read)
    assert c.calls==1
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT remaining_hold FROM budget_reservations').fetchone()[0]==Decimal('.05')
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()[0]==0


def test_no_results_is_success_and_sanitized_evidence_survives(dispatch_case):
    c=dispatch_case
    assert native_dispatch(c).state=='done'
    assert c.calls==1
    from buyeros_api.services.xverum_dispatch import read_evidence
    async def read(factory):
        async with factory() as s:
            values=await read_evidence(s,c.scope,c.admitted.id)
            assert len(values)==1 and values[0]['projection']['results']==[]
    pg(c,read)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT held_credits FROM xverum_credit_reservations').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()[0]==1


def test_projection_save_failure_retains_claim_and_both_holds(dispatch_case,monkeypatch):
    from buyeros_api.services import xverum_dispatch as m
    c=dispatch_case
    async def fail(*args,**kwargs):raise RuntimeError('synthetic projection transaction failure')
    monkeypatch.setattr(m,'persist_result',fail)
    assert native_dispatch(c).state=='reconcile'
    native_dispatch(c)
    assert c.calls==1
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT held_credits FROM xverum_credit_reservations').fetchone()[0]==5
        assert db.execute('SELECT projection FROM xverum_tool_receipts').fetchone()[0] is None


def test_generation_revocation_prevents_dispatch(dispatch_case):
    c=dispatch_case
    with psycopg.connect(c.dsn) as db:db.execute('UPDATE xverum_connections SET generation=generation+1')
    assert native_dispatch(c).state in {'done','blocked'}
    assert c.calls==0


@pytest.mark.parametrize('boundary',['before_claim','after_claim','after_result'])
def test_crash_boundaries_never_blind_retry(dispatch_case,boundary):
    from types import SimpleNamespace
    from buyeros_api.services import xverum_dispatch as m
    from buyeros_api.db.outbox import OutboxEvent
    c=dispatch_case
    class Guard:
        envelope=SimpleNamespace(workspace_id=c.ws)
        async def guard(self,session):
            self.row=await session.get(OutboxEvent,c.outbox)
            return True
    async def crash(factory):
        prepared=None
        if boundary=='before_claim':
            with pytest.raises(RuntimeError):
                async with factory() as s:
                    await m.claim(s,c.admitted.id,Guard())
                    raise RuntimeError('before claim commit')
        else:
            async with factory() as s:prepared=await m.claim(s,c.admitted.id,Guard())
            if boundary=='after_result':
                from buyeros_api.services.xverum_connections import call_xverum
                scope,binding,tool,claim,name,args=prepared
                await call_xverum(factory,scope,binding,name,args)
        async with factory() as s:
            outbox=await s.get(OutboxEvent,c.outbox)
            terminal,_,_=await m.recover_outbox(s,outbox)
            assert terminal==(boundary!='before_claim')
    pg(c,crash)
    result=native_dispatch(c)
    assert c.calls==int(boundary in {'before_claim','after_result'})
    assert result.state==('done' if boundary=='before_claim' else 'reconcile')


def test_reconciliation_current_operator_cas_idempotency_and_disabled_entry(dispatch_case,monkeypatch):
    import uuid
    from buyeros_api.services.xverum_dispatch import ReconciliationEvidence,reconcile_xverum
    from buyeros_api.services.xverum_quotes import read_receipt
    from buyeros_api.api.errors import ApiError
    from tests.test_xverum_connections import headers
    from tests.test_buyer_review_db import OPERATOR
    c=dispatch_case;c.mode='lost'
    assert native_dispatch(c).state=='reconcile'
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    async def run(factory):
        async with factory() as s:value=await read_receipt(s,c.scope,c.admitted.id)
        evidence=ReconciliationEvidence(provider_request_id='authoritative-synthetic',authoritative_usage=3,
            evidence_ref=uuid.uuid4(),resolution='usage',expected_version=value.version)
        with pytest.raises(ApiError):
            async with factory() as s:
                await reconcile_xverum(s,c.scope.model_copy(update={'actor_id':uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)}),c.admitted.id,evidence)
        with pytest.raises(ApiError):
            async with factory() as s:await reconcile_xverum(s,c.scope,c.admitted.id,evidence.model_copy(update={'expected_version':1}))
        for _ in range(2):
            async with factory() as s:
                settled=await reconcile_xverum(s,c.scope,c.admitted.id,evidence)
                assert settled.credits_used==3 and settled.held_credits==0
        return evidence
    evidence=pg(c,run)
    path=c.path.rsplit('/connections',1)[0]+f'/receipts/{c.admitted.id}/reconcile'
    response=c.client.post(path,json=evidence.model_dump(mode='json'),headers=headers(version=evidence.expected_version,key='synthetic-repair'))
    assert response.status_code==200,response.text
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM xverum_reconciliations').fetchone()[0]==1
        db.execute('UPDATE memberships SET active=false WHERE user_id=%s',(c.scope.actor_id,))
    assert c.client.post(path,json=evidence.model_dump(mode='json'),headers=headers(version=evidence.expected_version,key='synthetic-repair')).status_code in {403,404}
    assert c.calls==1


@pytest.mark.parametrize('resolution',['unknown','non_dispatch'])
def test_operator_missing_evidence_retains_hold_and_non_dispatch_releases(dispatch_case,resolution):
    import uuid
    from buyeros_api.services.xverum_dispatch import ReconciliationEvidence,reconcile_xverum
    from buyeros_api.services.xverum_quotes import read_receipt
    c=dispatch_case;c.mode='lost'
    native_dispatch(c)
    async def run(factory):
        async with factory() as s:value=await read_receipt(s,c.scope,c.admitted.id)
        evidence=ReconciliationEvidence(evidence_ref=uuid.uuid4(),resolution=resolution,expected_version=value.version)
        async with factory() as s:return await reconcile_xverum(s,c.scope,c.admitted.id,evidence)
    value=pg(c,run)
    assert value.held_credits==(5 if resolution=='unknown' else 0)
    assert c.calls==1


def test_native_cancel_and_suppression_prevent_undispatched_work(dispatch_case):
    import uuid
    c=dispatch_case
    with psycopg.connect(c.dsn) as db:
        company=db.execute('SELECT company_id FROM project_buyers WHERE id=%s',(c.buyer,)).fetchone()[0]
        # Native suppression input; schema defaults supply its active state.
        db.execute("INSERT INTO suppressions(id,workspace_id,subject_type,subject_id,reason,subject_key_hash,controller_scope_id,purpose,purposes,actor_id,active) VALUES(%s,%s,'company',%s,'synthetic','synthetic-hash',%s,'contact_research',ARRAY['contact_research'],%s,true)",(uuid.uuid4(),c.ws,company,c.ws,c.scope.actor_id))
    native_dispatch(c)
    assert c.calls==0


def test_worker_rls_and_immutable_tool_identity(dispatch_case):
    c=dispatch_case
    with psycopg.connect(c.worker_dsn) as db:
        assert db.execute('SELECT current_user').fetchone()[0]=='buyeros_worker'
        assert db.execute('SELECT count(*) FROM xverum_tool_receipts').fetchone()[0]==0
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c.ws),))
        assert db.execute('SELECT count(*) FROM xverum_tool_receipts').fetchone()[0]==1
        for table in ['xverum_stages','xverum_tool_receipts','xverum_reconciliations']:
            assert not db.execute("SELECT has_table_privilege(current_user,%s,'INSERT')",(table,)).fetchone()[0]
        assert not db.execute("SELECT has_column_privilege(current_user,'xverum_tool_receipts','arguments','UPDATE')").fetchone()[0]
        assert not db.execute("SELECT has_column_privilege(current_user,'xverum_stages','task_id','UPDATE')").fetchone()[0]



def linked_task(c,monkeypatch,language='en'):
    import uuid
    from tests.test_conversation_threads_api import ROOT,BODY,headers
    from tests.test_sales_tasks_api import SALES_ROOT
    from tests.test_buyer_review_db import ADMIN
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    response=c.client.post(ROOT,headers=headers(ADMIN),json=BODY)
    assert response.status_code==201,response.text
    thread=response.json()['data']
    response=c.client.post(SALES_ROOT,headers=headers(ADMIN,thread['version']),json={
        'thread_id':thread['id'],'skill_id':'sales-contacts','skill_version':'1',
        'user_message':'Synthetic professional research','arguments':{'language':language,'buyer_id':str(c.buyer),'purpose':'Synthetic procurement','roles':['Buyer']},'source_refs':getattr(c,'selected_refs',[])})
    assert response.status_code==201,response.text
    return uuid.UUID(response.json()['data']['id'])


def linked_admit(c,task,i):
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from buyeros_api.db.sales_tasks import SalesTask
    async def run(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic linked '+str(i),'company',c.buyer)
        async with factory() as s:
            row=await s.get(SalesTask,task)
            return await confirm_quote(s,c.scope,q.id,q.fingerprint,'linked-stage-'+str(i),task_id=task,expected_task_version=row.revision)
    return pg(c,run)


def test_linked_stage_task_state_authority_and_cancel(dispatch_case,monkeypatch):
    from buyeros_api.services.xverum_quotes import read_receipt
    from buyeros_api.services.sales_tasks import task_row
    from buyeros_api.execution.sales_tasks import cancel_task
    c=dispatch_case;task=linked_task(c,monkeypatch)
    admitted=linked_admit(c,task,0)
    assert admitted.task_id==task
    c.admitted=admitted
    with psycopg.connect(c.dsn) as db:
        c.outbox=db.execute('SELECT outbox_id FROM xverum_receipts WHERE id=%s',(admitted.id,)).fetchone()[0]
        assert db.execute('SELECT state FROM sales_tasks WHERE id=%s',(task,)).fetchone()[0]=='queued'
    c.mode='lost'
    assert native_dispatch(c).state=='reconcile'
    async def run(factory):
        async with factory() as s:
            row=await task_row(s,c.scope,task,edit=True)
            assert row.state=='outcome_unknown'
            result=await cancel_task(s,c.scope,task,row.revision)
            assert result.state=='outcome_unknown'
        async with factory() as s:
            assert (await read_receipt(s,c.scope,admitted.id)).held_credits==5
    pg(c,run)
    assert c.calls==1


def test_linked_limits_atomic_two_concurrent_sixteen_total(dispatch_case,monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from buyeros_api.services import xverum_dispatch as m
    from buyeros_api.db.outbox import OutboxEvent
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;task=linked_task(c,monkeypatch)
    receipts=[linked_admit(c,task,i) for i in range(16)]
    with pytest.raises(ApiError):linked_admit(c,task,16)
    async def run(factory):
        class Guard:
            envelope=SimpleNamespace(workspace_id=c.ws)
            def __init__(self,outbox):self.outbox=outbox
            async def guard(self,session):
                self.row=await session.get(OutboxEvent,self.outbox)
                return True
        async def one(receipt):
            async with factory() as s:
                from buyeros_api.db.xverum import XverumReceiptRow
                row=await s.get(XverumReceiptRow,receipt.id)
                return await m.claim(s,row.id,Guard(row.outbox_id))
        values=await asyncio.gather(*(one(r) for r in receipts[:3]))
        assert sum(value is not None for value in values)==2
        async with factory() as s:
            total,models,active=await m.invocation_counts(s,task)
            assert (total,models,active)==(16,0,2)
            with pytest.raises(ApiError):await m.require_bounds(s,task,model_additional=1)
    pg(c,run)
    assert c.calls==0


def test_standalone_cannot_be_relinked_to_private_task(dispatch_case,monkeypatch):
    from buyeros_api.services.xverum_quotes import confirm_quote
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;task=linked_task(c,monkeypatch)
    with psycopg.connect(c.dsn) as db:
        quote,fingerprint=db.execute('SELECT q.id,q.fingerprint FROM xverum_quotes q JOIN xverum_credit_reservations r ON r.quote_id=q.id JOIN xverum_receipts x ON x.reservation_id=r.id WHERE x.id=%s',(c.admitted.id,)).fetchone()
    async def run(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await confirm_quote(s,c.scope,quote,fingerprint,'dispatch',task_id=task,expected_task_version=1)
    pg(c,run)



def test_staged_six_tools_stop_on_uncertainty_and_reconcile_exact_member(dispatch_case):
    import uuid
    from buyeros_api.services.xverum_quotes import quote_search,quote_details,confirm_quote,read_receipt
    from buyeros_api.services.xverum_dispatch import ReconciliationEvidence,reconcile_xverum,read_evidence
    c=dispatch_case
    async def search(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic','people',c.buyer)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'people-stage')
    search_receipt=pg(c,search)
    def select_stage(receipt):
        c.admitted=receipt
        with psycopg.connect(c.dsn) as db:c.outbox=db.execute('SELECT outbox_id FROM xverum_receipts WHERE id=%s',(receipt.id,)).fetchone()[0]
    select_stage(search_receipt)
    assert native_dispatch(c).state=='done'
    async def detail(factory):
        async with factory() as s:q=await quote_details(s,c.scope,search_receipt.id,['1','2','3'],True)
        assert len(q.tool_plan)==6 and q.max_credits==18
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'details-stage')
    receipt=pg(c,detail);select_stage(receipt)
    c.usage=3
    c.mode='lost_at_3'  # search succeeded, person1 succeeded, person1 email uncertain
    assert native_dispatch(c).state=='reconcile'
    assert c.calls==3
    native_dispatch(c)
    assert c.calls==3
    with psycopg.connect(c.dsn) as db:
        states=db.execute('SELECT id,state FROM xverum_tool_receipts WHERE stage_id=%s ORDER BY ordinal',(receipt.id,)).fetchall()
        assert [state for _,state in states]==['received','unknown','queued','queued','queued','queued']
    async def repair(factory):
        async with factory() as s:current=await read_receipt(s,c.scope,receipt.id)
        assert current.held_credits==18
        evidence=ReconciliationEvidence(tool_receipt_id=states[1][0],provider_request_id='email-synthetic',
            authoritative_usage=2,evidence_ref=uuid.uuid4(),resolution='usage',expected_version=current.version)
        for _ in range(2):
            async with factory() as s:value=await reconcile_xverum(s,c.scope,receipt.id,evidence)
        assert value.credits_used==5 and value.held_credits==0
        async with factory() as s:assert len(await read_evidence(s,c.scope,receipt.id))==1
    pg(c,repair)
    from decimal import Decimal
    with psycopg.connect(c.dsn) as db:
        operation,hold=db.execute('SELECT operation_id,usd_reservation_id FROM xverum_credit_reservations WHERE id=(SELECT reservation_id FROM xverum_receipts WHERE id=%s)',(receipt.id,)).fetchone()
        assert db.execute('SELECT amount,pricing_version FROM cost_events WHERE operation_id=%s',(operation,)).fetchall()==[(Decimal('.05'),'fixture-v1')]
        assert db.execute('SELECT remaining_hold,currency FROM budget_reservations WHERE id=%s',(hold,)).fetchone()==(Decimal(0),'USD')
    assert c.calls==3


def test_known_nonacceptance_is_bounded_and_unknown_is_never_retried(dispatch_case,monkeypatch):
    from buyeros_api.services import xverum_connections
    from buyeros_api.providers.xverum_mcp import XverumTransportError
    c=dispatch_case;c.initializations=0
    class NotAccepted:
        def __init__(self,**kwargs):pass
        async def call(self,*args):
            c.initializations+=1
            raise XverumTransportError('initialize')
    monkeypatch.setattr(xverum_connections,'XverumTransport',NotAccepted)
    assert native_dispatch(c).state=='done'
    assert c.initializations==2 and c.calls==0
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT attempts,state FROM xverum_tool_receipts').fetchone()==(2,'cancelled')
        assert db.execute('SELECT held_credits FROM xverum_credit_reservations').fetchone()[0]==0


def test_late_duplicate_result_and_current_evidence_revocation(dispatch_case):
    from buyeros_api.services import xverum_dispatch as m
    from buyeros_api.sales.contracts import XverumResult
    from buyeros_api.api.errors import ApiError
    c=dispatch_case
    native_dispatch(c)
    with psycopg.connect(c.dsn) as db:
        ident,claim=db.execute('SELECT id,claim_id FROM xverum_tool_receipts').fetchone()
    result=XverumResult(tool='search_company_xverum',request_id='synthetic-request-1',credits_used=0,credits_remaining=100,
        projection={'result_type':'company','results':[],'total_count':0,'page':1,'page_size':5})
    async def repeat(factory):
        for _ in range(2):
            async with factory() as s:await m.persist_result(s,c.admitted.id,ident,claim,result)
    pg(c,repeat)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()[0]==1
        db.execute('UPDATE xverum_connections SET generation=generation+1')
    async def denied(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await m.read_evidence(s,c.scope,c.admitted.id)
    pg(c,denied)
    assert c.calls==1



def test_operator_liability_readback_has_no_private_projection(dispatch_case):
    from tests.test_xverum_connections import headers
    from tests.test_buyer_review_db import OPERATOR
    c=dispatch_case;c.mode='lost';native_dispatch(c)
    path=c.path.rsplit('/connections',1)[0]+f'/receipts/{c.admitted.id}/liability'
    response=c.client.get(path,headers=headers())
    assert response.status_code==200,response.text
    value=response.json()['data']
    assert value['receipt']['held_credits']==5 and len(value['tools'])==1
    assert 'projection' not in value['tools'][0] and 'arguments' not in value['tools'][0]
    assert c.client.get(path,headers=headers(OPERATOR)).status_code==404


def test_native_terminal_readback_recognizes_durable_provider_uncertainty(dispatch_case):
    from buyeros_api.execution.provider_context import terminal_business_outcome
    from buyeros_api.db.outbox import OutboxEvent
    c=dispatch_case;c.mode='lost';native_dispatch(c)
    async def run(factory):
        async with factory() as s:
            value=await terminal_business_outcome(s,await s.get(OutboxEvent,c.outbox),include_running=True)
            assert value.state=='reconcile'
    pg(c,run)


def test_linked_private_share_revocation_blocks_receipt_and_next_dispatch(dispatch_case,monkeypatch):
    import uuid
    from tests.test_conversation_threads_api import create,grant,headers,member,ROOT
    from tests.test_sales_tasks_api import SALES_ROOT
    from tests.test_buyer_review_db import ADMIN,OPERATOR
    from buyeros_api.services.xverum_quotes import read_receipt
    from buyeros_api.api.errors import ApiError
    c=dispatch_case
    thread=grant(c.client,c.dsn,create(c.client),ADMIN,'editor')
    response=c.client.post(SALES_ROOT,headers=headers(ADMIN,thread['version']),json={
        'thread_id':thread['id'],'skill_id':'sales-contacts','skill_version':'1','user_message':'Synthetic',
        'arguments':{'buyer_id':str(c.buyer),'purpose':'Synthetic','roles':['Buyer']},'source_refs':getattr(c,'selected_refs',[])})
    assert response.status_code==201,response.text
    task=uuid.UUID(response.json()['data']['id']);c.admitted=linked_admit(c,task,0)
    current=c.client.get(ROOT+'/'+thread['id'],headers=headers()).json()['data']
    removed=c.client.delete(ROOT+'/'+thread['id']+'/shares/'+member(c.dsn,ADMIN),headers=headers(version=current['version']))
    assert removed.status_code==200,removed.text
    async def denied(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await read_receipt(s,c.scope,c.admitted.id)
    pg(c,denied)
    with psycopg.connect(c.dsn) as db:c.outbox=db.execute('SELECT outbox_id FROM xverum_receipts WHERE id=%s',(c.admitted.id,)).fetchone()[0]
    native_dispatch(c)
    assert c.calls==0



def test_worker_authoritative_usage_settles_exact_separate_usd(dispatch_case):
    from decimal import Decimal
    c=dispatch_case;c.usage=3
    assert native_dispatch(c).state=='done'
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT credits_used FROM xverum_credit_settlements').fetchone()[0]==3
        assert db.execute('SELECT amount,pricing_version FROM cost_events').fetchall()==[(Decimal('.03'),'fixture-v1')]
        assert db.execute('SELECT remaining_hold,currency FROM budget_reservations').fetchone()==(Decimal(0),'USD')
    assert c.calls==1


def test_credit_denial_creates_no_second_dispatch(dispatch_case):
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    from buyeros_api.api.errors import ApiError
    c=dispatch_case
    with psycopg.connect(c.dsn) as db:db.execute('UPDATE xverum_credit_accounts SET credit_limit=5')
    async def denied(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Another','company',c.buyer)
        with pytest.raises(ApiError) as caught:
            async with factory() as s:await confirm_quote(s,c.scope,q.id,q.fingerprint,'denied-credit')
        assert caught.value.code=='XVERUM_CREDIT_LIMIT'
    pg(c,denied)
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT count(*) FROM budget_reservations').fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM outbox_events WHERE event_type='xverum.step'").fetchone()[0]==1
    assert c.calls==0


def test_default_disabled_credentials_are_not_unknown_billing(dispatch_case,monkeypatch):
    from buyeros_api.services import xverum_connections as connections
    c=dispatch_case
    monkeypatch.setattr(connections,'CREDENTIAL_PROVIDER',connections.DisabledCredentialProvider())
    assert native_dispatch(c).state=='done'
    assert c.calls==0
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT claim_id FROM xverum_tool_receipts').fetchone()[0] is None
        assert db.execute('SELECT held_credits FROM xverum_credit_reservations').fetchone()[0]==0



def test_post_response_generation_change_keeps_billing_but_drops_projection(dispatch_case,monkeypatch):
    from buyeros_api.services import xverum_connections
    c=dispatch_case;original=xverum_connections.call_xverum
    async def late_revocation(*args,**kwargs):
        result=await original(*args,**kwargs)
        with psycopg.connect(c.dsn) as db:db.execute('UPDATE xverum_connections SET generation=generation+1')
        return result
    monkeypatch.setattr(xverum_connections,'call_xverum',late_revocation)
    assert native_dispatch(c).state=='done'
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT projection FROM xverum_tool_receipts').fetchone()[0] is None
        assert db.execute('SELECT credits_used FROM xverum_credit_settlements').fetchone()[0]==0
    assert c.calls==1



def test_linked_approval_replay_keeps_original_task_precondition(dispatch_case,monkeypatch):
    from buyeros_api.services.xverum_quotes import confirm_quote
    c=dispatch_case;task=linked_task(c,monkeypatch);first=linked_admit(c,task,0)
    with psycopg.connect(c.dsn) as db:
        quote,fingerprint=db.execute('SELECT q.id,q.fingerprint FROM xverum_quotes q JOIN xverum_credit_reservations r ON r.quote_id=q.id JOIN xverum_receipts x ON x.reservation_id=r.id WHERE x.id=%s',(first.id,)).fetchone()
    async def replay(factory):
        async with factory() as s:return await confirm_quote(s,c.scope,quote,fingerprint,'linked-stage-0',task_id=task,expected_task_version=1)
    assert pg(c,replay)==first
    assert c.calls==0



def test_populated_dispatch_downgrade_preserves_proof(dispatch_case):
    from alembic import command
    from tests.test_conversation_threads_db import config
    c=dispatch_case
    with pytest.raises(RuntimeError,match='preserve dispatch'):
        command.downgrade(config(),'0062_xverum_credits')
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='0069_conversation_turn_reconciliations'
        assert db.execute('SELECT count(*) FROM xverum_tool_receipts').fetchone()[0]==1
        for name in ('xverum_stages','xverum_tool_receipts','xverum_reconciliations'):
            assert db.execute('SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',(name,)).fetchone()[0]


def test_missing_dispatch_table_fails_boolean_readiness(dispatch_case):
    c=dispatch_case
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0]
        # Hide only the expected relation name; 0065 dependencies retain their
        # real FK to its OID. Rollback restores the complete schema and grants.
        db.execute('ALTER TABLE xverum_tool_receipts RENAME TO fixture_missing_tool_receipts')
        assert db.execute("SELECT to_regclass('public.xverum_tool_receipts')").fetchone()==(None,)
        assert not db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0]
        db.rollback()
        assert db.execute('SELECT public.buyeros_xverum_connections_ready()').fetchone()[0]


def select_receipt(c, receipt):
    c.admitted=receipt
    with psycopg.connect(c.dsn) as db:
        c.outbox=db.execute('SELECT outbox_id FROM xverum_receipts WHERE id=%s',(receipt.id,)).fetchone()[0]


def shared_search(c):
    """Actual linked worker result, owned by another user's private thread."""
    import uuid
    from tests.test_conversation_threads_api import create,grant,headers,ROOT,member
    from tests.test_sales_tasks_api import SALES_ROOT
    from tests.test_buyer_review_db import ADMIN
    from buyeros_api.services.xverum_quotes import quote_search,confirm_quote
    thread=grant(c.client,c.dsn,create(c.client),ADMIN,'editor')
    response=c.client.post(SALES_ROOT,headers=headers(ADMIN,thread['version']),json={
        'thread_id':thread['id'],'skill_id':'sales-contacts','skill_version':'1','user_message':'Synthetic',
        'arguments':{'buyer_id':str(c.buyer),'purpose':'Synthetic','roles':['Buyer']},'source_refs':getattr(c,'selected_refs',[])})
    assert response.status_code==201,response.text
    task=uuid.UUID(response.json()['data']['id'])
    async def admit(factory):
        async with factory() as s:q=await quote_search(s,c.scope,c.id,'Synthetic','people',c.buyer)
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'source-linked',task_id=task,expected_task_version=1)
    source=pg(c,admit);select_receipt(c,source)
    assert native_dispatch(c).state=='done' and c.calls==1
    def revoke():
        current=c.client.get(ROOT+'/'+thread['id'],headers=headers()).json()['data']
        response=c.client.delete(ROOT+'/'+thread['id']+'/shares/'+member(c.dsn,ADMIN),headers=headers(version=current['version']))
        assert response.status_code==200,response.text
    return source,revoke,task


def source_change(c, source, revoke, change):
    if change=='revoke':revoke()
    else:
        with psycopg.connect(c.dsn) as db:
            if change=='expiry':
                db.execute("UPDATE xverum_tool_receipts SET expires_at=now()-interval '1 second' WHERE stage_id=%s",(source.id,))
            else:
                db.execute("UPDATE sales_tasks SET arguments=jsonb_set(arguments,'{purpose}','\"Changed\"') WHERE id=(SELECT task_id FROM xverum_stages WHERE id=%s)",(source.id,))


def detail_quote(c, source):
    from buyeros_api.services.xverum_quotes import quote_details
    async def run(factory):
        async with factory() as s:return await quote_details(s,c.scope,source.id,['1','2'],True)
    return pg(c,run)


def detail_admit(c, q, task=None):
    from buyeros_api.services.xverum_quotes import confirm_quote
    async def run(factory):
        async with factory() as s:return await confirm_quote(s,c.scope,q.id,q.fingerprint,'source-detail',
            task_id=task,expected_task_version=1 if task else None)
    receipt=pg(c,run);select_receipt(c,receipt)
    return receipt


@pytest.mark.parametrize('when',['creation','approval'])
@pytest.mark.parametrize('change',['expiry','revoke','context'])
def test_source_dependency_admission(dispatch_case,when,change):
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;source,revoke,_=shared_search(c)
    q=detail_quote(c,source) if when=='approval' else None
    source_change(c,source,revoke,change)
    with pytest.raises(ApiError):
        detail_admit(c,q) if q else detail_quote(c,source)
    assert c.calls==1


@pytest.mark.parametrize('different_task',[False,True])
@pytest.mark.parametrize('change',['revoke','expiry','context'])
def test_source_dependency_before_call(dispatch_case,monkeypatch,different_task,change):
    c=dispatch_case;source,revoke,_=shared_search(c)
    task=linked_task(c,monkeypatch) if different_task else None
    receipt=detail_admit(c,detail_quote(c,source),task)
    source_change(c,source,revoke,change)
    assert native_dispatch(c).state=='done'
    assert c.calls==1
    with psycopg.connect(c.dsn) as db:
        assert db.execute('SELECT dispatch_state FROM xverum_receipts WHERE id=%s',(receipt.id,)).fetchone()[0]=='cancelled'


@pytest.mark.parametrize('when',['before_transport','before_retention','after_settlement'])
@pytest.mark.parametrize('change',['revoke','expiry','context'])
def test_source_dependency_retention_and_readback(dispatch_case,monkeypatch,when,change):
    from buyeros_api.services import xverum_connections as connections
    from buyeros_api.services.xverum_dispatch import read_evidence,read_liability,resolve_evidence
    from buyeros_api.services.xverum_quotes import read_quote
    from types import SimpleNamespace
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;source,revoke,_=shared_search(c)
    q=detail_quote(c,source);receipt=detail_admit(c,q)
    with psycopg.connect(c.dsn) as db:
        tool_id=db.execute('SELECT id FROM xverum_tool_receipts WHERE stage_id=%s ORDER BY ordinal LIMIT 1',(receipt.id,)).fetchone()[0]
    original=connections.call_xverum
    async def change_during_call(*args,**kwargs):
        if when=='before_transport':source_change(c,source,revoke,change)
        result=await original(*args,**kwargs)
        if when=='before_retention':source_change(c,source,revoke,change)
        return result
    if when!='after_settlement':monkeypatch.setattr(connections,'call_xverum',change_during_call)
    native_dispatch(c)
    if when=='after_settlement':
        assert c.calls==5  # valid four-tool detail path before source loss
        async def readable(factory):
            async with factory() as s:assert len(await read_evidence(s,c.scope,receipt.id))==4
        pg(c,readable)
        source_change(c,source,revoke,change)
    else:
        assert c.calls==(1 if when=='before_transport' else 2)
        with psycopg.connect(c.dsn) as db:
            assert db.execute('SELECT count(*) FROM xverum_tool_receipts WHERE stage_id=%s AND projection IS NOT NULL',(receipt.id,)).fetchone()[0]==0
    async def denied(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await read_evidence(s,c.scope,receipt.id)
        with pytest.raises(ApiError):
            async with factory() as s:await read_quote(s,c.scope,q.id)
        with pytest.raises(ApiError):
            async with factory() as s:await resolve_evidence(s,c.scope,SimpleNamespace(id=tool_id,version=1,locator='provider_evidence:'+str(tool_id)))
        async with factory() as s:
            value=await read_liability(s,c.scope,receipt.id)
            assert value.receipt.id==receipt.id  # financial authority survives source loss
    pg(c,denied)


def test_source_revocation_preserves_uncertain_financial_repair(dispatch_case):
    import uuid
    from buyeros_api.services.xverum_dispatch import read_liability,reconcile_xverum,ReconciliationEvidence,read_evidence
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;source,revoke,_=shared_search(c)
    receipt=detail_admit(c,detail_quote(c,source));c.mode='lost'
    assert native_dispatch(c).state=='reconcile'
    revoke()
    async def repair(factory):
        async with factory() as s:value=await read_liability(s,c.scope,receipt.id)
        proof=ReconciliationEvidence(expected_version=value.receipt.version,evidence_ref=uuid.uuid4(),
            tool_receipt_id=value.tools[0].id,resolution='usage',authoritative_usage=1,provider_request_id='synthetic-repair')
        for _ in range(2):
            async with factory() as s:result=await reconcile_xverum(s,c.scope,receipt.id,proof)
            assert result.credits_used==1 and result.held_credits==0
        with pytest.raises(ApiError):
            async with factory() as s:await read_evidence(s,c.scope,receipt.id)
    pg(c,repair)
    assert c.calls==2


def test_http_cancel_orders_gates_before_linked_ownership_and_replay(dispatch_case,monkeypatch):
    import asyncio,time
    from concurrent.futures import ThreadPoolExecutor
    from types import SimpleNamespace
    from sqlalchemy import text
    from buyeros_api.services import xverum_dispatch as m
    from buyeros_api.db.outbox import OutboxEvent
    from tests.xverum_fixtures import headers
    c=dispatch_case;receipt=linked_admit(c,linked_task(c,monkeypatch),0);select_receipt(c,receipt)
    path=c.path.removesuffix('/connections')+f'/receipts/{receipt.id}/cancel'
    with ThreadPoolExecutor(max_workers=1) as pool:
        async def competing(factory, *, replay=False):
            async with factory() as s:
                await s.execute(text("SET LOCAL lock_timeout='1500ms'"))
                await m.gates(s,c.ws)
                pid=await s.scalar(text('SELECT pg_backend_pid()'))
                future=pool.submit(c.client.post,path,headers=headers(version=2 if replay else 1,key='cancel-replay' if replay else 'cancel-race'))
                deadline=time.monotonic()+5
                blocked=False
                while time.monotonic()<deadline:
                    with psycopg.connect(c.dsn) as db:
                        blocked=db.execute('SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE %s=ANY(pg_blocking_pids(pid)))',(pid,)).fetchone()[0]
                    if blocked:break
                    await asyncio.sleep(.02)
                assert blocked,'HTTP cancellation never reached the competing gate'
                if replay:await m.sync_task(s,receipt.id)
                else:
                    class Guard:
                        envelope=SimpleNamespace(workspace_id=c.ws)
                        async def guard(self,session):
                            self.row=await session.get(OutboxEvent,c.outbox)
                            return True
                    assert await m.claim(s,receipt.id,Guard()) is not None
            response=await asyncio.to_thread(future.result,5)
            assert response.status_code==(200 if replay else 409),response.text
        pg(c,competing)
        # Claim advances receipt from1 to2; cancel has its own durable replay.
        response=c.client.post(path,headers=headers(version=2,key='cancel-replay'))
        assert response.status_code==200,response.text
        # Replay must use the original precondition, not the returned revision.
        async def replay(factory):
            # Same two-transaction schedule, with exact original key/precondition.
            await competing(factory,replay=True)
        pg(c,replay)
    assert c.calls==0


def test_source_dependency_rejects_nonterminal_search_closure(dispatch_case):
    from buyeros_api.services.xverum_dispatch import read_evidence
    from buyeros_api.api.errors import ApiError
    c=dispatch_case;source,_,_=shared_search(c)
    receipt=detail_admit(c,detail_quote(c,source))
    assert native_dispatch(c).state=='done'
    with psycopg.connect(c.dsn) as db:
        # Deliberate owner-role corruption: a source with its own dependency is
        # invalid, including cycles. No recursive graph traversal is permitted.
        db.execute('UPDATE xverum_quotes SET source_receipt_id=%s WHERE id=(SELECT quote_id FROM xverum_credit_reservations WHERE id=(SELECT reservation_id FROM xverum_receipts WHERE id=%s))',(receipt.id,source.id))
    async def denied(factory):
        with pytest.raises(ApiError):
            async with factory() as s:await read_evidence(s,c.scope,receipt.id)
    pg(c,denied)
    assert c.calls==5
