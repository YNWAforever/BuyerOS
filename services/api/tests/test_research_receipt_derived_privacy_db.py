"""Future derived-copy regression, seeded only in owned DB; no evidence eligibility implied."""
import hashlib,json,uuid
from datetime import datetime,timezone
import psycopg,pytest
from tests.cutover_fixtures import role_dsn
from tests.test_research_page_retrieval_db import page_case,run_case,project_api,admission_case,migrated,Transport,execute

def digest(content):return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

@pytest.fixture
def derived_case(page_case):
    c=page_case;t=Transport(c);result=execute(c,t);assert result['status']=='retrieved'
    source=uuid.UUID(result['source_document_id']);names=['company','buyer','evidence','fit','draft','revision','approval','export']
    ids={name:uuid.uuid4() for name in names};w,p=c['workspace'],c['project']
    with psycopg.connect(c['dsn']) as db:
        icp=db.execute('SELECT icp_version_id FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]
        excerpt=db.execute('SELECT excerpt FROM source_documents WHERE id=%s',(source,)).fetchone()[0]
        content={'subject':'PRIVATE_C19_DERIVED_SUBJECT','body':'PRIVATE_C19_DERIVED_BODY','claims':[{'text':'PRIVATE_C19_DERIVED_CLAIM'}],'evidence_refs':[{'id':str(ids['evidence']),'version':1}],
            'objective':'PRIVATE_C19_DERIVED_OBJECTIVE','language':'zh-HK','kind':'initial','icp_version_id':str(icp),'evidence_set_hash':'a'*64,'value_proposition_fact_ids':[],'policy_decision_ids':[],'context_hash':'b'*64}
        db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Independent fictional target','Independent fictional target')",(ids['company'],w))
        db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(ids['buyer'],w,p,ids['company']))
        db.execute("INSERT INTO evidence(id,workspace_id,project_id,company_id,source_document_id,stance,excerpt,translation,is_inference) VALUES(%s,%s,%s,%s,%s,'supports',%s,'PRIVATE_C19_TRANSLATION',true)",(ids['evidence'],w,p,ids['company'],source,excerpt))
        db.execute("INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,icp_version_id,evidence_set_hash,verdict,rationale,evidence_ids,assessment_details) VALUES(%s,%s,%s,%s,%s,%s,'needs_review','PRIVATE_C19_FIT_RATIONALE',%s::jsonb,%s::jsonb)",(ids['fit'],w,p,ids['buyer'],icp,'a'*64,json.dumps([str(ids['evidence'])]),json.dumps({'copy':'PRIVATE_C19_FIT_DETAILS'})))
        db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state,review_context,review_context_hash) VALUES(%s,%s,%s,%s,1,'approved',%s::jsonb,%s)",(ids['draft'],w,p,ids['buyer'],json.dumps({'copy':'PRIVATE_C19_DRAFT_REVIEW'}),'a'*64))
        db.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,content,content_hash,evidence_ids,offer_fact_ids) VALUES(%s,%s,%s,1,%s::jsonb,%s,%s::jsonb,'[]'::jsonb)",(ids['revision'],w,ids['draft'],json.dumps(content,ensure_ascii=False),digest(content),json.dumps([str(ids['evidence'])])))
        db.execute("INSERT INTO approvals(id,workspace_id,draft_id,revision_number,content_hash,context_fingerprint,approver_id,draft_revision_id,context_snapshot,approved_at) VALUES(%s,%s,%s,1,%s,%s,%s,%s,%s::jsonb,now())",(ids['approval'],w,ids['draft'],digest(content),'a'*64,c['actor'],ids['revision'],json.dumps({'copy':'PRIVATE_C19_APPROVAL_SNAPSHOT'})))
        db.execute("INSERT INTO export_jobs(id,workspace_id,project_id,kind,scope_hash,state,actor_user_id,draft_id,draft_revision_id,approval_id,selection_manifest,expires_at) VALUES(%s,%s,%s,'draft',%s,'ready',%s,%s,%s,%s,%s::jsonb,now()+interval '1 hour')",(ids['export'],w,p,'a'*64,c['actor'],ids['draft'],ids['revision'],ids['approval'],json.dumps({'draft_revision_id':str(ids['revision']),'legacy_copy':'PRIVATE_C19_EXPORT_COPY'})))
        receipt=db.execute('SELECT request_hash,response_hash,intent_key,runtime_epoch FROM search_receipts WHERE id=%s',(c['receipt'],)).fetchone()
        hold=db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()
    try:yield {**c,'page_source':source,'derived':ids,'receipt_metadata':receipt,'hold':hold,'original_content':content}
    finally:
        with psycopg.connect(c['dsn']) as db:
            for table,name in [('export_jobs','export'),('approvals','approval'),('draft_revisions','revision'),('outreach_drafts','draft'),('fit_assessments','fit'),('evidence','evidence'),('project_buyers','buyer'),('companies','company')]:db.execute('DELETE FROM '+table+' WHERE id=%s',(ids[name],))

@pytest.mark.parametrize('role',['buyeros_api','buyeros_worker'])
def test_search_receipt_erasure_clears_future_evidence_fit_draft_approval_export_copies_atomically(derived_case,role):
    c=derived_case;i=c['derived']
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
    with psycopg.connect(role_dsn(c['dsn'],role)) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
        assert db.execute("SELECT public.buyeros_erase_provider_receipt(%s,'search',%s,'c19_derived_receipt_fixture')",(c['workspace'],c['receipt'])).fetchone()==(True,)
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT excerpt,translation FROM evidence WHERE id=%s',(i['evidence'],)).fetchone()==('Source expired',None),'receipt erasure retained a derived evidence copy'
        assert db.execute('SELECT verdict,rationale,assessment_details FROM fit_assessments WHERE id=%s',(i['fit'],)).fetchone()==('needs_review','Source expired',{})
        content,hash_value=db.execute('SELECT content,content_hash FROM draft_revisions WHERE id=%s',(i['revision'],)).fetchone()
        assert 'PRIVATE_C19' not in json.dumps(content) and content['grounding_status']=='source_expired' and hash_value==digest(content)
        assert db.execute('SELECT state,review_context,review_context_hash FROM outreach_drafts WHERE id=%s',(i['draft'],)).fetchone()==('stale',None,None)
        assert db.execute('SELECT invalidated_reason,context_snapshot FROM approvals WHERE id=%s',(i['approval'],)).fetchone()==('SOURCE_EXPIRED',None)
        state,manifest=db.execute('SELECT state,selection_manifest FROM export_jobs WHERE id=%s',(i['export'],)).fetchone()
        assert state=='revoked' and 'PRIVATE_C19' not in json.dumps(manifest)
        assert db.execute('SELECT request_hash,response_hash,intent_key,runtime_epoch FROM search_receipts WHERE id=%s',(c['receipt'],)).fetchone()==c['receipt_metadata']
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()==c['hold']
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)
        assert db.execute('SELECT canonical_company_id FROM raw_candidates WHERE id=%s',(c['raw'],)).fetchone()==(None,)
    with psycopg.connect(role_dsn(c['dsn'],role)) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
        assert db.execute("SELECT public.buyeros_erase_provider_receipt(%s,'search',%s,'c19_derived_receipt_fixture')",(c['workspace'],c['receipt'])).fetchone()==(False,)


def erase(c,role='buyeros_api',workspace=None):
    with psycopg.connect(role_dsn(c['dsn'],role)) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(workspace or c['workspace']),))
        return db.execute("SELECT public.buyeros_erase_provider_receipt(%s,'search',%s,'c19_derived_receipt_fixture')",(workspace or c['workspace'],c['receipt'])).fetchone()[0]

def expire(c):
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))

def test_derived_erasure_rejects_not_due_foreign_workspace_and_direct_helper(derived_case):
    c=derived_case;i=c['derived'];assert erase(c) is False
    assert erase(c,workspace=uuid.uuid4()) is False
    with psycopg.connect(role_dsn(c['dsn'],'buyeros_api')) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute('SELECT public.buyeros_erase_search_derived(%s,%s,%s)',(c['workspace'],c['receipt'],'forbidden'))
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT redacted_at FROM search_receipts WHERE id=%s',(c['receipt'],)).fetchone()==(None,)
        assert db.execute('SELECT content FROM draft_revisions WHERE id=%s',(i['revision'],)).fetchone()==(c['original_content'],)

def test_derived_row_lock_failure_rolls_back_receipt_source_and_all_copies(derived_case):
    c=derived_case;i=c['derived'];expire(c)
    with psycopg.connect(c['dsn']) as locker:
        locker.execute('SELECT id FROM evidence WHERE id=%s FOR UPDATE',(i['evidence'],))
        with pytest.raises(psycopg.errors.LockNotAvailable):erase(c)
        assert locker.execute('SELECT redacted_at FROM search_receipts WHERE id=%s',(c['receipt'],)).fetchone()==(None,)
        assert locker.execute('SELECT excerpt FROM source_documents WHERE id=%s',(c['page_source'],)).fetchone()[0] is not None
        assert locker.execute('SELECT content FROM draft_revisions WHERE id=%s',(i['revision'],)).fetchone()==(c['original_content'],)
    assert erase(c) is True

def test_concurrent_derived_receipt_erasure_has_one_audit_and_no_replay(derived_case):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    c=derived_case;expire(c);barrier=Barrier(2)
    def run(role):barrier.wait(timeout=5);return erase(c,role)
    with ThreadPoolExecutor(max_workers=2) as pool:assert sorted(pool.map(run,['buyeros_api','buyeros_worker']))==[False,True]
    with psycopg.connect(c['dsn']) as db:
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='provider_receipt.expired' AND subject_id=%s",(str(c['receipt']),)).fetchone()==(1,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()==c['hold']

@pytest.mark.parametrize('dependent',[True,False])
def test_model_basis_payload_is_erased_only_when_dependent_on_search_source(derived_case,dependent):
    c=derived_case;ref=uuid.uuid4();source=c['page_source'] if dependent else uuid.uuid4()
    request={'basis':{'evidence':[{'source_id':str(source),'excerpt':'PRIVATE_C19_MODEL_BASIS'}]}}
    with psycopg.connect(c['dsn']) as db:
        # Owner-only historical/future copy fixture; no model/provider invocation.
        db.execute("INSERT INTO model_receipts(id,workspace_id,project_id,actor_id,operation_id,outbox_id,intent_key,request,request_hash,contract_hash,pricing_version,generation,runtime_epoch,runtime_backend,state,response,response_hash,retention_until) SELECT %s,workspace_id,project_id,actor_id,operation_id,outbox_id,%s,%s::jsonb,%s,contract_hash,pricing_version,generation,runtime_epoch,runtime_backend,'received',%s::jsonb,%s,now()+interval '1 hour' FROM search_receipts WHERE id=%s",(ref,'model-copy:'+str(ref),json.dumps(request),'d'*64,json.dumps({'copy':'PRIVATE_C19_MODEL_RESPONSE'}),'e'*64,c['receipt']))
    try:
        expire(c);assert erase(c) is True
        with psycopg.connect(c['dsn']) as db:
            value=db.execute('SELECT request,response,request_hash,response_hash,state,redacted_at FROM model_receipts WHERE id=%s',(ref,)).fetchone()
            assert value[2:5]==('d'*64,'e'*64,'received')
            assert (value[0]=={'redacted':True} and value[1] is None and value[5] is not None) if dependent else (value[0]==request and value[1] is not None and value[5] is None)
            assert db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()==c['hold']
    finally:
        with psycopg.connect(c['dsn']) as db:db.execute('DELETE FROM model_receipts WHERE id=%s',(ref,))

def test_populated_derived_privacy_rollback_retains_eraser_and_closes_all_receipt_writes(derived_case,monkeypatch):
    from tests.migration_guards import invoke_revision
    from alembic import command
    from alembic.config import Config
    from tests.conftest import ALEMBIC_INI,SERVICE_ROOT,runtime_role_dsn
    from buyeros_api.settings import get_settings
    c=derived_case;cfg=Config(str(ALEMBIC_INI));cfg.set_main_option('script_location',str(SERVICE_ROOT/'alembic'))
    monkeypatch.setenv('BUYEROS_DATABASE_URL',c['dsn']);get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError,match='preserve controller policy history'):
            command.downgrade(cfg,'0045_c61_research_page_privacy')
        invoke_revision(c['dsn'],cfg,'0046_c61_derived_privacy')
        with psycopg.connect(c['dsn']) as db:
            assert db.execute('SELECT public.buyeros_search_receipts_writable(),public.buyeros_model_receipts_writable(),public.buyeros_contact_receipts_writable()').fetchone()==(False,False,False)
            assert db.execute('SELECT request_hash,response_hash,intent_key,runtime_epoch FROM search_receipts WHERE id=%s',(c['receipt'],)).fetchone()==c['receipt_metadata']
        expire(c);assert erase(c,'buyeros_worker') is True
        with psycopg.connect(c['dsn']) as db:
            assert db.execute('SELECT excerpt,translation FROM evidence WHERE id=%s',(c['derived']['evidence'],)).fetchone()==('Source expired',None)
            assert db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()==c['hold']
    finally:
        invoke_revision(c['dsn'],cfg,'0056_policy_activation','_fences',('0056_policy_activation',))
        monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(c['dsn']));get_settings.cache_clear()
    assert erase(c) is False
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT count(*) FROM draft_revisions WHERE id=%s',(c['derived']['revision'],)).fetchone()==(1,)
        assert db.execute('SELECT content FROM draft_revisions WHERE id=%s',(c['derived']['revision'],)).fetchone()[0]['grounding_status']=='source_expired'


def retained_old_tombstone(c):
    # Owner-only reproduction of the pre-0046 receipt/source erasure shape;
    # immutable receipt trigger remains enabled throughout.
    expire(c)
    with psycopg.connect(c['dsn']) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
        db.execute("UPDATE search_receipts SET request=jsonb_build_object('redacted',true),response=NULL,redacted_at=now(),redaction_policy='legacy_c19',updated_at=now() WHERE id=%s",(c['receipt'],))
        db.execute("UPDATE source_documents s SET excerpt=NULL,canonical_url='https://redacted.invalid/'||id::text,retention_until=LEAST(retention_until,now()) WHERE s.workspace_id=%s AND EXISTS(SELECT 1 FROM receipt_source_bindings b WHERE b.workspace_id=s.workspace_id AND b.source_id=s.id AND b.service='search' AND b.receipt_id=%s)",(c['workspace'],c['receipt']))

@pytest.mark.parametrize('role',['buyeros_api','buyeros_worker'])
def test_retained_pre0046_tombstone_repairs_derived_copies_without_new_receipt_audit(derived_case,role):
    c=derived_case;retained_old_tombstone(c)
    assert erase(c,role) is False # no second receipt redaction or acceptance change
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT excerpt,translation FROM evidence WHERE id=%s',(c['derived']['evidence'],)).fetchone()==('Source expired',None)
        version=db.execute('SELECT state_version FROM outreach_drafts WHERE id=%s',(c['derived']['draft'],)).fetchone()
    assert erase(c,role) is False
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT state_version FROM outreach_drafts WHERE id=%s',(c['derived']['draft'],)).fetchone()==version
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='provider_receipt.expired' AND subject_id=%s",(str(c['receipt']),)).fetchone()==(0,)
        assert db.execute('SELECT redaction_policy FROM search_receipts WHERE id=%s',(c['receipt'],)).fetchone()==('legacy_c19',)

def test_source_specific_compatible_sweep_repairs_retained_derived_copies(derived_case):
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from buyeros_api.api.deps import async_database_url
    from buyeros_api.db.session import tenant_session
    from buyeros_api.services.receipt_retention import expire_provider_receipts
    c=derived_case;retained_old_tombstone(c)
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],'buyeros_api')))
        try:
            async with tenant_session(engine,c['workspace']) as session:
                assert await expire_provider_receipts(session,now=datetime.now(timezone.utc),policy_version='c19_compatible',source_id=c['page_source'])==[]
        finally:await engine.dispose()
    asyncio.run(run())
    with psycopg.connect(c['dsn']) as db:assert db.execute('SELECT excerpt,translation FROM evidence WHERE id=%s',(c['derived']['evidence'],)).fetchone()==('Source expired',None)

def test_atomic_eraser_does_not_relax_draft_or_approval_immutability(derived_case):
    c=derived_case;i=c['derived']
    with psycopg.connect(role_dsn(c['dsn'],'buyeros_api')) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
        with pytest.raises(psycopg.errors.RaiseException,match='immutable'):
            db.execute("UPDATE draft_revisions SET content=jsonb_set(content,'{body}','\"Unauthorized replacement\"') WHERE id=%s",(i['revision'],))
    expire(c);assert erase(c)
    with psycopg.connect(role_dsn(c['dsn'],'buyeros_api')) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
        with pytest.raises(psycopg.errors.RaiseException,match='cannot reactivate'):
            db.execute('UPDATE approvals SET invalidated_reason=NULL,invalidated_at=NULL WHERE id=%s',(i['approval'],))


@pytest.mark.parametrize('old_source_state',['tombstoned','still_live'])
def test_retained_old_receipt_must_clear_metadata_raw_and_older_live_source(derived_case,old_source_state):
    c=derived_case
    if old_source_state=='tombstoned':retained_old_tombstone(c)
    else:
        expire(c)
        with psycopg.connect(c['dsn']) as db:
            db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
            db.execute("UPDATE search_receipts SET request=jsonb_build_object('redacted',true),response=NULL,redacted_at=now(),redaction_policy='legacy_c19',updated_at=now() WHERE id=%s",(c['receipt'],))
    assert erase(c) is False
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT raw_payload FROM raw_candidates WHERE id=%s',(c['raw'],)).fetchone()[0].get('redacted') is True,'retained old receipt left raw metadata readable'
        assert db.execute('SELECT excerpt,canonical_url FROM source_documents WHERE id=%s',(c['page_source'],)).fetchone()==(None,'https://redacted.invalid/'+str(c['page_source'])),'older receipt tombstone left source content readable'
