"""Current receipt read policy/deadline and atomic erase audit; real runtime roles."""
import asyncio,hashlib,uuid
from datetime import datetime,timezone
import psycopg,pytest
from sqlalchemy import text
from buyeros_api.db.session import tenant_session
from buyeros_api.services.receipt_retention import bind_receipt_source
from tests.test_live_search_db import search_case,stores,hold
from tests.test_buyer_review_db import api

@pytest.mark.parametrize('change',['source','actor','policy'])
def test_received_search_read_requires_current_source_and_actor_purpose(search_case,change):
    case=search_case;source=uuid.uuid4()
    async def exercise():
        async with stores(case) as (m,engine,first,store,ref):
            with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
            assert (await store.claim(case['intent']))[1]
            item=m.source_candidate({'url':'https://sensors.example.test/company','title':'Owned','snippet':'C19_PRIVATE_SNIPPET'})
            await store.finish(ref,state='received',sources=[item],digest=hashlib.sha256(m.canonical_json([item])).hexdigest())
            with psycopg.connect(case['dsn']) as db:
                if change=='source':db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,'https://sensors.example.test/company',%s,'excerpt_only','owned expired',now()-interval '1 second','account_research')",(source,case['workspace'],case['project'],'a'*64))
                elif change=='actor':db.execute('UPDATE memberships SET active=false,version=version+1 WHERE user_id=%s',(case['actor'],))
                else:db.execute("UPDATE policy_decisions SET status='blocked' WHERE workspace_id=%s",(case['workspace'],))
            if change=='source':
                async with tenant_session(first.engine,case['workspace']) as session:await bind_receipt_source(session,service='search',receipt_id=uuid.UUID(ref),source_id=source)
                saved=await store.get(ref);assert saved['state']=='expired' and saved['request'] is None and saved['sources']==[]
                assert (await m.LiveSearchAdapter(capability=case['cap'],client=None,receipts=store).status(ref)).state=='unknown'
                assert not (await store.claim(case['intent']))[1]
            else:
                with pytest.raises(ValueError,match='current|permission|policy'):await store.get(ref)
            assert hold(case)[1]==0
    try:asyncio.run(exercise())
    finally:
        with psycopg.connect(case['dsn']) as db:
            db.execute('DELETE FROM receipt_source_bindings WHERE source_id=%s',(source,))
            db.execute('DELETE FROM source_documents WHERE id=%s',(source,))

def test_narrow_erase_function_atomically_audits_once_without_app_callback(search_case):
    case=search_case;source=uuid.uuid4()
    async def exercise():
        async with stores(case) as (m,engine,first,store,ref):
            with psycopg.connect(case['dsn']) as db:db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,'https://sensors.example.test/company',%s,'excerpt_only','owned expired',now()-interval '1 second','account_research')",(source,case['workspace'],case['project'],'a'*64))
            async with tenant_session(first.engine,case['workspace']) as session:await bind_receipt_source(session,service='search',receipt_id=uuid.UUID(ref),source_id=source)
            async def erase():
                async with tenant_session(first.engine,case['workspace']) as session:return (await session.execute(text("SELECT public.buyeros_erase_provider_receipt(:ws,'search',:ref,'owned-c19-v1')"),{'ws':case['workspace'],'ref':uuid.UUID(ref)})).scalar_one()
            # The function owns the audit with the erasure transaction. Racing
            # callers must never produce two success receipts or two audits.
            assert sorted(await asyncio.gather(erase(),erase()))==[False,True]
            with psycopg.connect(case['dsn']) as db:
                assert db.execute("SELECT count(*) FROM audit_events WHERE action='provider_receipt.expired' AND subject_id=%s",(ref,)).fetchone()[0]==1
                assert db.execute("SELECT request FROM search_receipts WHERE id=%s",(ref,)).fetchone()==({'redacted':True},)
            assert hold(case)[1]==0
    try:asyncio.run(exercise())
    finally:
        with psycopg.connect(case['dsn']) as db:
            db.execute('DELETE FROM receipt_source_bindings WHERE source_id=%s',(source,))
            db.execute('DELETE FROM source_documents WHERE id=%s',(source,))

def test_receipt_read_does_not_wait_on_its_own_parent_policy_transaction(search_case):
    case=search_case
    async def exercise():
        from buyeros_api.services.policy_service import policy_workspace_lock
        async with stores(case) as (m,engine,first,store,ref):
            with psycopg.connect(case['dsn']) as db:db.execute("UPDATE provider_operations SET status='submitting' WHERE id=%s",(case['operation'],))
            assert (await store.claim(case['intent']))[1]
            item=m.source_candidate({'url':'https://sensors.example.test/company','title':'Owned','snippet':'Current source'})
            await store.finish(ref,state='received',sources=[item],digest=hashlib.sha256(m.canonical_json([item])).hexdigest())
            async with tenant_session(first.engine,case['workspace']) as parent:
                await policy_workspace_lock(parent,case['workspace'])
                saved=await asyncio.wait_for(store.get(ref),timeout=1.5)
                assert saved['state']=='received'
    asyncio.run(exercise())

def test_readonly_policy_snapshot_cannot_authorize_a_mutating_transaction(search_case):
    case=search_case
    async def exercise():
        from buyeros_api.services.policy_service import evaluate_current_policy_readonly
        async with stores(case) as (m,engine,first,store,ref):
            async with tenant_session(first.engine,case['workspace']) as session:
                with pytest.raises(ValueError,match='read-only'):await evaluate_current_policy_readonly(session,{'workspace_id':case['workspace'],'project_id':case['project']},'account_research',datetime.now(timezone.utc))
    asyncio.run(exercise())
