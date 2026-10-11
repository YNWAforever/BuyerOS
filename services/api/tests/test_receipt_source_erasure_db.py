"""Shape-level retained rows test native source-copy erasure, not live accuracy."""
import asyncio,hashlib,json,uuid
from datetime import datetime,timezone
import psycopg,pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from buyeros_api.db.session import tenant_session
from buyeros_api.services.retention import expire_subject_data
from buyeros_api.services.receipt_retention import bind_receipt_source
from tests.test_live_contact_db import contact_case,engines,held
from tests.test_lookup_quotes_db import quote_case
from tests.test_buyer_review_db import api,WORKSPACE_B

@pytest.mark.parametrize('service',['search','model','contact'])
@pytest.mark.parametrize('already_tombstoned',[False,True])
def test_source_tombstone_erases_scoped_receipt_copy_through_api_role(contact_case,service,already_tombstoned):
    case=contact_case;source=uuid.uuid4();receipt=uuid.uuid4()
    async def exercise(m,engine,first,store,ref,cipher):
        nonlocal receipt
        with psycopg.connect(case['dsn']) as db:
            db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,'https://fictional-sensors.com/source',%s,'excerpt_only','C19_PRIVATE_SOURCE',now()-interval '1 second',%s)",(source,case['workspace'],case['request'].project_id,'a'*64,'contact_research' if service=='contact' else 'account_research'))
        if service=='contact':receipt=uuid.UUID(ref)
        else:
            # Existing immutable schema permits this shape-level historical row.
            # No model proposal, canonical entity proof or HTTP acceptance is claimed.
            payload={'query':'C19_PRIVATE_SEARCH'} if service=='search' else {'basis':{'evidence':[{'source_id':str(source),'source_excerpt':'C19_PRIVATE_MODEL'}]}}
            digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
            async with tenant_session(first.engine,case['workspace']) as session:
                await session.execute(text(f"""INSERT INTO {service}_receipts(id,workspace_id,project_id,actor_id,operation_id,outbox_id,intent_key,request,request_hash,contract_hash,pricing_version,generation,runtime_epoch,runtime_backend)
                  SELECT :receipt,workspace_id,project_id,actor_id,operation_id,outbox_id,:key,CAST(:request AS jsonb),:hash,contract_hash,pricing_version,generation,runtime_epoch,runtime_backend FROM contact_receipts WHERE id=:original"""),
                  {'receipt':receipt,'key':'c19-source-'+service,'request':json.dumps(payload),'hash':digest,'original':uuid.UUID(ref)})
        if service!='model':
            async with tenant_session(first.engine,case['workspace']) as session:
                await bind_receipt_source(session,service=service,receipt_id=receipt,source_id=source)
                await bind_receipt_source(session,service=service,receipt_id=receipt,source_id=source)
        with psycopg.connect(case['dsn']) as db:
            if already_tombstoned:db.execute("UPDATE source_documents SET excerpt=NULL,canonical_url='https://redacted.invalid/'||id::text WHERE id=%s",(source,))
            before=db.execute(f'SELECT intent_key,request_hash,response_hash,state,operation_id,outbox_id,generation,runtime_epoch FROM {service}_receipts WHERE id=%s',(receipt,)).fetchone()
        async with tenant_session(first.engine,case['workspace']) as session:
            assert (await expire_subject_data(session,source,'owned-c19-v1',datetime.now(timezone.utc),subject_type='source_document'))['expired'] is (not already_tombstoned)
        async with tenant_session(first.engine,case['workspace']) as session:
            assert not (await expire_subject_data(session,source,'owned-c19-v1',datetime.now(timezone.utc),subject_type='source_document'))['expired']
        with psycopg.connect(case['dsn']) as db:
            assert db.execute(f'SELECT intent_key,request_hash,response_hash,state,operation_id,outbox_id,generation,runtime_epoch FROM {service}_receipts WHERE id=%s',(receipt,)).fetchone()==before
            assert db.execute(f'SELECT request,redacted_at FROM {service}_receipts WHERE id=%s',(receipt,)).fetchone()[0]=={'redacted':True}
            assert db.execute("SELECT count(*) FROM audit_events WHERE action='provider_receipt.expired' AND subject_id=%s",(str(receipt),)).fetchone()[0]==1
            assert db.execute('SELECT excerpt FROM source_documents WHERE id=%s',(source,)).fetchone()==(None,)
        assert held(case)[1]==0
    try:asyncio.run(engines(case,exercise))
    finally:
        with psycopg.connect(case['dsn']) as db:
            db.execute('DELETE FROM receipt_source_bindings WHERE source_id=%s',(source,))
            if service!='contact':db.execute(f'DELETE FROM {service}_receipts WHERE id=%s',(receipt,))
            db.execute('DELETE FROM source_documents WHERE id=%s',(source,))

def test_binding_rejects_foreign_receipt_and_source_under_native_api_rls(contact_case):
    case=contact_case;source=uuid.uuid4()
    async def exercise(m,engine,first,store,ref,cipher):
        with psycopg.connect(case['dsn']) as db:db.execute("INSERT INTO source_documents(id,workspace_id,canonical_url,digest,storage_mode,excerpt,retention_until,permission_purpose) VALUES(%s,%s,'https://fictional-sensors.com/source',%s,'excerpt_only','owned',now()+interval '1 day','account_research')",(source,case['workspace'],'a'*64))
        with pytest.raises(DBAPIError):
            async with tenant_session(first.engine,uuid.UUID(WORKSPACE_B)) as session:await bind_receipt_source(session,service='contact',receipt_id=uuid.UUID(ref),source_id=source)
    try:asyncio.run(engines(case,exercise))
    finally:
        with psycopg.connect(case['dsn']) as db:db.execute('DELETE FROM source_documents WHERE id=%s',(source,))

@pytest.mark.parametrize('change',['foreign-project','foreign-purpose'])
def test_source_binding_requires_current_receipt_project_and_purpose(contact_case,change):
    case=contact_case;source=uuid.uuid4();project=case['request'].project_id
    if change=='foreign-project':project=uuid.uuid4()
    async def exercise(m,engine,first,store,ref,cipher):
        with psycopg.connect(case['dsn']) as db:
            if change=='foreign-project':db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES(%s,%s,'Other','Other','Owned','{US}','{en}',1)",(project,case['workspace']))
            db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,'https://fictional-sensors.com/source',%s,'excerpt_only','owned',now()+interval '1 day',%s)",(source,case['workspace'],project,'a'*64,'account_research' if change=='foreign-purpose' else 'contact_research'))
        with pytest.raises(DBAPIError):
            async with tenant_session(first.engine,case['workspace']) as session:await bind_receipt_source(session,service='contact',receipt_id=uuid.UUID(ref),source_id=source)
    try:asyncio.run(engines(case,exercise))
    finally:
        with psycopg.connect(case['dsn']) as db:
            db.execute('DELETE FROM receipt_source_bindings WHERE source_id=%s',(source,))
            db.execute('DELETE FROM source_documents WHERE id=%s',(source,))
            if change=='foreign-project':db.execute('DELETE FROM projects WHERE id=%s',(project,))
