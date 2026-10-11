"""Native C19 payload erasure keeps acceptance metadata and economic holds."""
import asyncio,hashlib,importlib,json,time,uuid
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import psycopg,pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from tests.test_live_contact_db import contact_case,engines,held
from tests.test_live_contact_adapter import response
from tests.test_lookup_quotes_db import quote_case
from tests.test_buyer_review_db import api,WORKSPACE_B
from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import ProviderIntent

def service():return importlib.import_module('buyeros_api.services.receipt_retention')

async def expiring_engines(case,exercise):
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.api.deps import async_database_url
    from tests.conftest import runtime_role_dsn
    from tests.cutover_fixtures import role_dsn
    from tests.test_live_contact_adapter import module
    m=module();api_engine=create_async_engine(async_database_url(runtime_role_dsn(case['dsn'])))
    worker_engine=create_async_engine(async_database_url(role_dsn(case['dsn'],'buyeros_worker')))
    try:
        cipher=m.ContactReceiptCipher(keys={'offline-k1':b'a'*32},active_key_id='offline-k1')
        first=m.PostgresContactReceipts(api_engine,case['workspace'],case['cap'],cipher=cipher,environment='test')
        store=m.PostgresContactReceipts(worker_engine,case['workspace'],case['cap'],cipher=cipher,environment='test')
        ref=await first.prepare(case['request'],operation_id=case['operation'],outbox_id=case['outbox'],expires_at=datetime.now(timezone.utc)+timedelta(seconds=5))
        await exercise(m,worker_engine,first,store,ref,cipher)
    finally:await api_engine.dispose();await worker_engine.dispose()

def test_expired_contact_payload_is_erased_without_releasing_unknown_hold(contact_case):
    case=contact_case
    async def exercise(m,engine,first,store,ref,cipher):
        svc=service()
        with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
        intent=ProviderIntent(case['request'].key,'contact','US','en','Procurement manager')
        assert (await store.claim(intent))[1]
        payload=m.normalize_contact_response(response(),case['request']);digest=hashlib.sha256(m.canonical_json(payload)).hexdigest()
        await store.finish(ref,state='received',response=payload,digest=digest)
        with psycopg.connect(case['dsn']) as db:
            before=db.execute('SELECT intent_key,request_hash,response_hash,state,operation_id,outbox_id,generation,runtime_epoch FROM contact_receipts WHERE id=%s',(ref,)).fetchone()
            expiry=db.execute('SELECT retention_until FROM contact_receipts WHERE id=%s',(ref,)).fetchone()[0]
        await asyncio.sleep(max(0,(expiry-datetime.now(timezone.utc)).total_seconds())+0.05)
        async with tenant_session(engine,case['workspace']) as session:
            result=await svc.expire_provider_receipts(session,now=datetime.now(timezone.utc),policy_version='owned-c19-v1',limit=1)
        assert result==[{'service':'contact','id':ref}]
        async with tenant_session(engine,case['workspace']) as session:
            assert await svc.expire_provider_receipts(session,now=datetime.now(timezone.utc),policy_version='owned-c19-v1',limit=1)==[]
        with psycopg.connect(case['dsn']) as db:
            after=db.execute('SELECT intent_key,request_hash,response_hash,state,operation_id,outbox_id,generation,runtime_epoch FROM contact_receipts WHERE id=%s',(ref,)).fetchone()
            erased=db.execute('SELECT request,response_ciphertext,redacted_at,redaction_policy FROM contact_receipts WHERE id=%s',(ref,)).fetchone()
            assert after==before and erased[0]=={'redacted':True} and erased[1] is None and erased[2] and erased[3]=='owned-c19-v1'
            assert db.execute("SELECT count(*) FROM audit_events WHERE action='provider_receipt.expired' AND subject_id=%s",(ref,)).fetchone()[0]==1
        saved=await store.get(ref);assert saved['state']=='redacted' and saved['request'] is None and saved['response'] is None and saved['digest']==digest
        assert not (await store.claim(intent))[1]
        assert (await m.LiveContactAdapter(capability=case['cap'],account_reference='owned',client=None,receipts=store).status(ref)).state=='unknown'
        assert held(case)==(('active',Decimal('0.100000')),0)
    asyncio.run(expiring_engines(case,exercise))

@pytest.mark.parametrize('mutation',['early','restore','metadata','cross-tenant','api-role'])
def test_receipt_erasure_guard_does_not_grant_payload_mutation(contact_case,mutation):
    case=contact_case
    async def exercise(m,engine,first,store,ref,cipher):
        service()
        if mutation=='cross-tenant':
            async with tenant_session(engine,uuid.UUID(WORKSPACE_B)) as session:
                assert await service().expire_provider_receipts(session,now=datetime.now(timezone.utc)+timedelta(days=2),policy_version='owned',limit=50)==[]
            return
        target=first.engine if mutation=='api-role' else engine
        statement="UPDATE contact_receipts SET request='{}'::jsonb WHERE id=:id"
        if mutation=='early':statement="UPDATE contact_receipts SET request=jsonb_build_object('redacted',true),response_ciphertext=NULL,redacted_at=now(),redaction_policy='owned' WHERE id=:id"
        elif mutation=='restore':statement="UPDATE contact_receipts SET redacted_at=now(),redaction_policy='owned' WHERE id=:id"
        elif mutation=='metadata':statement="UPDATE contact_receipts SET request_hash=repeat('0',64),redacted_at=now(),redaction_policy='owned' WHERE id=:id"
        with pytest.raises(DBAPIError):
            async with tenant_session(target,case['workspace']) as session:await session.execute(text(statement),{'id':uuid.UUID(ref)})
        assert (await store.get(ref))['state']=='prepared' and held(case)[1]==0
    asyncio.run(engines(case,exercise))

@pytest.mark.parametrize('limit',[0,101,True])
def test_receipt_sweep_requires_bounded_explicit_policy(contact_case,limit):
    case=contact_case
    async def exercise(m,engine,first,store,ref,cipher):
        async with tenant_session(engine,case['workspace']) as session:
            with pytest.raises(ValueError):await service().expire_provider_receipts(session,now=datetime.now(timezone.utc),policy_version='owned',limit=limit)
    asyncio.run(engines(case,exercise))

def test_private_contact_read_does_not_wait_on_parent_policy_transaction(contact_case):
    case=contact_case
    async def exercise(m,engine,first,store,ref,cipher):
        from buyeros_api.services.policy_service import policy_workspace_lock
        with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
        intent=ProviderIntent(case['request'].key,'contact','US','en','Procurement manager')
        assert (await store.claim(intent))[1]
        payload=m.normalize_contact_response(response(),case['request'])
        await store.finish(ref,state='received',response=payload,digest=hashlib.sha256(m.canonical_json(payload)).hexdigest())
        async with tenant_session(first.engine,case['workspace']) as parent:
            await policy_workspace_lock(parent,case['workspace'])
            saved=await asyncio.wait_for(store.get(ref),timeout=1.5)
            assert saved['state']=='received' and saved['response']['verified_contacts']==[]
    asyncio.run(engines(case,exercise))
