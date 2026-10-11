"""Explicit existing-company review of an actual permitted synthetic page.

No entity auto-merge, buyer-role inference, provider billing or human UAT claim.
"""
import asyncio,hashlib,importlib,json,uuid
import psycopg,pytest
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api.deps import async_database_url
from buyeros_api.db.session import tenant_session
from tests.cutover_fixtures import role_dsn
from tests.test_research_page_retrieval_db import page_case,run_case,project_api,admission_case,migrated,Transport,execute

NAME='Fictional Sensors Limited'
TEXT=NAME+' manufactures sensor parts. Buyer role remains unverified.'

def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def port():
    spec=importlib.util.find_spec('buyeros_api.services.research_candidate_review')
    assert spec is not None,'C61-19 explicit native candidate/page review port is missing'
    fn=getattr(importlib.import_module('buyeros_api.services.research_candidate_review'),'review_research_candidate',None)
    assert callable(fn),'C61-19 current reviewed canonical/evidence port is missing'
    return fn

@pytest.fixture
def review_case(page_case,request):
    c=page_case;company,sibling=uuid.uuid4(),uuid.uuid4()
    page_text=TEXT+(' Additional independent page content.'*240 if getattr(request,'param',None)=='long' else '')
    with psycopg.connect(c['dsn']) as db:
        roles=db.execute('SELECT roles FROM memberships WHERE workspace_id=%s AND user_id=%s',(c['workspace'],c['actor'])).fetchone()[0]
        db.execute("UPDATE memberships SET roles=%s WHERE workspace_id=%s AND user_id=%s",(list(set(roles+['reviewer'])),c['workspace'],c['actor']))
        for value,name in [(company,NAME),(sibling,'Fictional Sensors Subsidiary')]:
            db.execute('INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) VALUES(%s,%s,%s,%s,%s)',(value,c['workspace'],name,name,'sensors.example.test'))
    class NamedTransport(Transport):
        async def get(self,url,**kw):
            await super().get(url,**kw)
            return 200,{'content-type':'text/html','content-language':'en'},('<html><body>'+page_text+'</body></html>').encode()
    t=NamedTransport(c);result=execute(c,t);assert result['status']=='retrieved';source=uuid.UUID(result['source_document_id'])
    with psycopg.connect(c['dsn']) as db:
        page_digest,excerpt=db.execute('SELECT digest,excerpt FROM source_documents WHERE id=%s',(source,)).fetchone()
        company_hash=canonical({'id':str(company),'legal_name':NAME,'display_name':NAME,'domain':'sensors.example.test','registry_id':None})
        hold=db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()
    args={'workspace_id':c['workspace'],'run_id':c['run'],'raw_candidate_id':c['raw'],'page_source_id':source,
        'company_id':company,'actor_id':c['actor'],'expected_page_digest':page_digest,'expected_company_hash':company_hash,
        'excerpt':excerpt,'reason':'Explicit independently selected entity review','capability':c['cap']}
    try:yield {**c,'company':company,'sibling':sibling,'page_source':source,'args':args,'transport':t,'hold':hold}
    finally:
        with psycopg.connect(c['dsn']) as db:
            db.execute("DELETE FROM audit_events WHERE subject_type='raw_candidate' AND subject_id=%s",(str(c['raw']),))
            db.execute('DELETE FROM fit_assessments WHERE project_buyer_id IN(SELECT id FROM project_buyers WHERE company_id IN(%s,%s))',(company,sibling))
            db.execute('DELETE FROM evidence WHERE raw_candidate_id=%s',(c['raw'],))
            db.execute('DELETE FROM company_aliases WHERE raw_candidate_id=%s',(c['raw'],))
            db.execute('UPDATE raw_candidates SET canonical_company_id=NULL WHERE id=%s',(c['raw'],))
            db.execute('DELETE FROM project_buyers WHERE company_id IN(%s,%s)',(company,sibling))
            db.execute('DELETE FROM companies WHERE id IN(%s,%s)',(company,sibling))
            db.execute('UPDATE memberships SET roles=%s WHERE workspace_id=%s AND user_id=%s',(roles,c['workspace'],c['actor']))

def review(c,*,role='buyeros_api',changes=None):
    fn=port();args={**c['args'],**(changes or {})}
    async def run():
        engine=create_async_engine(async_database_url(role_dsn(c['dsn'],role)))
        try:
            async with tenant_session(engine,c['workspace']) as session:return await fn(session,**args)
        finally:await engine.dispose()
    return asyncio.run(run())

def test_explicit_page_review_maps_only_selected_existing_company_and_creates_cited_inference_once(review_case):
    c=review_case;value=review(c);assert review(c)==value and c['transport'].calls==1
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT canonical_company_id,merge_state FROM raw_candidates WHERE id=%s',(c['raw'],)).fetchone()==(c['company'],'reviewed_page')
        assert db.execute('SELECT count(*) FROM companies WHERE workspace_id=%s',(c['workspace'],)).fetchone()==(2,)
        assert db.execute('SELECT company_id FROM project_buyers WHERE id=%s',(uuid.UUID(value['buyer_id']),)).fetchone()==(c['company'],)
        assert db.execute('SELECT source_document_id,excerpt,is_inference,stance FROM evidence WHERE id=%s',(uuid.UUID(value['evidence_id']),)).fetchone()==(c['page_source'],c['args']['excerpt'],True,'qualifies')
        assert db.execute('SELECT count(*) FROM company_aliases WHERE raw_candidate_id=%s AND reviewed=true',(c['raw'],)).fetchone()==(1,)
        assert db.execute("SELECT count(*) FROM run_events WHERE run_id=%s AND event_type='candidate.page_reviewed'",(c['run'],)).fetchone()==(1,)
        assert db.execute('SELECT count(*) FROM fit_assessments').fetchone()==(0,)
        assert db.execute('SELECT state,remaining_hold FROM budget_reservations').fetchall()==c['hold']
        assert db.execute('SELECT count(*) FROM cost_events').fetchone()==(0,)

@pytest.mark.parametrize('mutation',['role','epoch','source-expired','foreign-target','bad-digest','company-changed','unanchored-excerpt','missing-identity','license','foreign-raw','altered-page','missing-page-proof'])
def test_page_review_rechecks_member_scope_source_identity_and_original_fence(review_case,mutation):
    port();c=review_case;changes={}
    with psycopg.connect(c['dsn']) as db:
        if mutation=='role':db.execute("UPDATE memberships SET roles=ARRAY['operator'] WHERE workspace_id=%s AND user_id=%s",(c['workspace'],c['actor']))
        elif mutation=='epoch':db.execute('UPDATE worker_runtime_control SET epoch=epoch+1 WHERE singleton=1')
        elif mutation=='source-expired':db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
        elif mutation=='company-changed':db.execute("UPDATE companies SET display_name='Changed independently' WHERE id=%s",(c['company'],))
        elif mutation=='license':db.execute("UPDATE policy_decisions SET basis_reference='Source licence withdrawn',version=version+1 WHERE id=%s",(c['policy'],))
        elif mutation=='altered-page':
            changed=NAME+' UNOBSERVED_NEW_PAGE_CONTENT';db.execute('UPDATE source_documents SET excerpt=%s WHERE id=%s',(changed,c['page_source']));changes['excerpt']=changed
        elif mutation=='missing-page-proof':db.execute("UPDATE run_events SET payload=payload-'page_digest'-'excerpt_digest' WHERE run_id=%s AND event_type='page.fetch.finished'",(c['run'],))
        elif mutation=='foreign-target':changes['company_id']=uuid.uuid4()
        elif mutation=='foreign-raw':changes['raw_candidate_id']=uuid.uuid4()
        elif mutation=='bad-digest':changes['expected_page_digest']='0'*64
        elif mutation=='unanchored-excerpt':changes['excerpt']='Unobserved assertion about buyer role'
        elif mutation=='missing-identity':
            changes['company_id']=c['sibling'];changes['expected_company_hash']=canonical({'id':str(c['sibling']),'legal_name':'Fictional Sensors Subsidiary','display_name':'Fictional Sensors Subsidiary','domain':'sensors.example.test','registry_id':None})
    with pytest.raises(ValueError):review(c,changes=changes)
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT canonical_company_id FROM raw_candidates WHERE id=%s',(c['raw'],)).fetchone()==(None,)
        assert db.execute('SELECT count(*) FROM evidence').fetchone()==(0,)

def test_reviewed_page_evidence_expiry_clears_copy_but_keeps_independent_entity_uuid(review_case):
    c=review_case;value=review(c)
    with psycopg.connect(c['dsn']) as db:db.execute("UPDATE source_documents SET retention_until=now()-interval '1 second' WHERE id=%s",(c['page_source'],))
    with psycopg.connect(role_dsn(c['dsn'],'buyeros_api')) as db:
        db.execute("SELECT set_config('app.workspace_id',%s,true)",(str(c['workspace']),))
        assert db.execute("SELECT public.buyeros_erase_provider_receipt(%s,'search',%s,'c19_reviewed_page')",(c['workspace'],c['receipt'])).fetchone()==(True,)
    with psycopg.connect(c['dsn']) as db:
        assert db.execute('SELECT excerpt,translation FROM evidence WHERE id=%s',(uuid.UUID(value['evidence_id']),)).fetchone()==('Source expired',None)
        assert db.execute('SELECT canonical_company_id FROM raw_candidates WHERE id=%s',(c['raw'],)).fetchone()==(c['company'],)
        assert db.execute('SELECT legal_name FROM companies WHERE id=%s',(c['company'],)).fetchone()==(NAME,)
    with pytest.raises(ValueError):review(c)

def test_reviewed_raw_cannot_be_silently_relinked_by_a_different_replay(review_case):
    c=review_case;review(c)
    with pytest.raises(ValueError):review(c,changes={'company_id':c['sibling']})

def test_concurrent_same_review_keeps_one_alias_evidence_and_buyer(review_case):
    from concurrent.futures import ThreadPoolExecutor
    c=review_case;port()
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(lambda _:review(c),range(2)))
    assert values[0]==values[1]
    with psycopg.connect(c['dsn']) as db:
        for table in ['company_aliases','evidence','project_buyers']:assert db.execute('SELECT count(*) FROM '+table).fetchone()==(1,)

def test_worker_cannot_perform_human_page_review(review_case):
    from sqlalchemy.exc import DBAPIError
    port();c=review_case
    with pytest.raises((ValueError,DBAPIError)):review(c,role='buyeros_worker')


@pytest.mark.parametrize('material',['alias','evidence-hash','buyer-company'])
def test_review_replay_rejects_changed_stored_alias_citation_or_buyer_material(review_case,material):
    c=review_case;result=review(c)
    with psycopg.connect(c['dsn']) as db:
        if material=='alias':db.execute('UPDATE company_aliases SET normalized_value=%s WHERE id=%s',('0'*64,uuid.UUID(result['alias_id'])))
        elif material=='evidence-hash':db.execute('UPDATE evidence SET content_hash=%s WHERE id=%s',('0'*64,uuid.UUID(result['evidence_id'])))
        else:db.execute('UPDATE project_buyers SET company_id=%s WHERE id=%s',(c['sibling'],uuid.UUID(result['buyer_id'])))
    with pytest.raises(ValueError):review(c)
    assert c['transport'].calls==1
