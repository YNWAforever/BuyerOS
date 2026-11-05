"""Task12 real canonical save/readback and native export boundary."""
from datetime import datetime, timezone
import uuid
import psycopg
from tests.test_sales_drafting_db import core_case, seeded, api, quote_case, ref
from tests.test_sales_core_journey_db import new_task
from tests.test_sales_tasks_api import SALES_ROOT
from tests.test_conversation_threads_api import headers
from tests.test_lookup_quotes_db import ICP, WORKSPACE_A
from tests.icp_fixtures import FACT_ID
from tests.test_lookup_quotes_db import PROJECT, _h
from tests.test_postgres_private_storage_db import private_postgres
import pytest


@pytest.mark.parametrize('recursive',[False,True])
def test_fix1_export_account_policy(core_case,recursive):
    from tests.test_exports_authorization_db import _permit
    from tests.test_lookup_quotes_db import REVIEWER
    client,dsn,buyer,_=core_case
    _,saved=prepare(client,'sales-report',{'as_of':datetime.now(timezone.utc).isoformat(),'buyer_ids':[buyer]})
    with psycopg.connect(dsn) as db:
        company,version=db.execute('SELECT company_id,version FROM project_buyers WHERE id=%s',(buyer,)).fetchone()
        if recursive:
            other=str(db.execute('SELECT id FROM project_buyers WHERE id<>%s LIMIT 1',(buyer,)).fetchone()[0])
    if recursive:
        _,saved=prepare(client,'sales-report',{'as_of':datetime.now(timezone.utc).isoformat(),'buyer_ids':[other]},[ref('output',saved['id'])])
        assert all(str(r['id'])!=buyer for r in saved['native_refs'])
    base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+saved['id']
    assert client.get(base,headers=headers()).json()['data']==saved
    for fmt in ('markdown','pdf'):
        denied=client.post(base+'/exports',headers=headers(version=1),json={'revision':1,'format':fmt,'approved':True})
        assert denied.status_code==403,denied.text
    with psycopg.connect(dsn) as db: _permit(db,'export_accounts')
    exports=[]
    for fmt in ('markdown','pdf'):
        response=client.post(base+'/exports',headers=headers(version=1),json={'revision':1,'format':fmt,'approved':True})
        assert response.status_code==200,response.text
        job=response.json()['data']
        url=f'/v1/workspaces/{WORKSPACE_A}/exports/{job["id"]}/content'
        assert client.get(url,headers=headers()).status_code==200
        reference=None
        if fmt=='pdf':
            _,reference=prepare(client,'sales-report-pdf',{'output_id':saved['id'],'output_revision':1,'export_id':job['id']},[ref('output',saved['id'])])
        exports.append((url,reference))
    with psycopg.connect(dsn) as db:
        db.execute("INSERT INTO policy_decisions(id,workspace_id,subject_type,subject_id,controller_scope_id,purpose,status,policy_version,basis_reference,provenance,countries,expires_at,retention_days,decision_author_id) VALUES (%s,%s,'company',%s,%s,'export_accounts','blocked','fixture-v1','fixture','fixture',ARRAY['US'],now()+interval '1 day',1,%s)",
            (uuid.uuid4(),WORKSPACE_A,company,WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,REVIEWER)))
        assert db.execute('SELECT version FROM project_buyers WHERE id=%s',(buyer,)).fetchone()[0]==version
    assert client.get(base,headers=headers()).json()['data']==saved
    for url,reference in exports:
        if reference:
            # Check reference authority before download can mark the native job revoked.
            reference_url=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+reference['id']
            assert client.get(reference_url,headers=headers()).json()['data']['availability']=='unavailable'
        assert client.get(url,headers=headers()).status_code==403
    assert client.post(base+'/exports',headers=headers(version=1),json={'revision':1,'format':'markdown','approved':True}).status_code==403


@pytest.mark.parametrize('state',['cancelled','completed','queued','running','cancel_requested','outcome_unknown','failed'])
def test_fix1_preparation_preserves_state(core_case,monkeypatch,state):
    client,dsn,buyer,_=core_case
    refs=[ref('buyer',buyer),ref('profile',ICP),{**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
    args={'buyer_id':buyer,'profile_id':ICP,'pain_points':['Sensors'],'terms':[{'price':{'amount':'500','currency':'HKD'},'scope':'Sensors','exclusions':'Installation','timeline':'To agree','evidence':[refs[-1]]}]}
    if state=='completed': args['case_study_refs']=[refs[0]]
    task=new_task(client,'sales-proposal',args,refs)
    url=SALES_ROOT+'/'+task['id']
    if state=='cancelled':
        response=client.post(url+'/cancel',headers=headers(version=1))
        assert response.status_code==200,response.text
    elif state=='completed':
        response=client.post(url+'/core-preparation',headers=headers(version=1))
        assert response.status_code==200,response.text
        from buyeros_api.services import sales_outputs
        async def missing(*args,**kwargs): raise ValueError('Needs input: selected case-study proof')
        monkeypatch.setattr(sales_outputs,'assemble_or_core',missing)
    else:
        with psycopg.connect(dsn) as db: db.execute('UPDATE sales_tasks SET state=%s WHERE id=%s',(state,task['id']))
    before=client.get(url,headers=headers()).json()['data']
    with psycopg.connect(dsn) as db:
        events=db.execute('SELECT sequence,kind,payload FROM sales_task_events WHERE task_id=%s ORDER BY sequence',(task['id'],)).fetchall()
    response=client.post(url+'/core-preparation',headers=headers(version=before['revision']))
    assert response.status_code==409,response.text
    assert client.get(url,headers=headers()).json()['data']==before
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT sequence,kind,payload FROM sales_task_events WHERE task_id=%s ORDER BY sequence',(task['id'],)).fetchall()==events
    follow=client.post(url+'/followups',headers=headers(version=before['revision']),json={'user_message':'Add proof','arguments':{'case_study_refs':[refs[0]]}})
    assert follow.status_code==409,follow.text
    assert follow.json()['code']=='TASK_ACTIVE'


@pytest.fixture
def upload_cleanup(core_case,private_postgres):
    yield
    with psycopg.connect(core_case[1]) as db:
        db.execute('DELETE FROM document_uploads WHERE workspace_id=%s',(WORKSPACE_A,))
        db.execute('DELETE FROM document_slides WHERE workspace_id=%s',(WORKSPACE_A,))
        db.execute('DELETE FROM offer_documents WHERE workspace_id=%s',(WORKSPACE_A,))


def prepare(client,skill,args,refs=()):
    task=new_task(client,skill,args,refs)
    response=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
    assert response.status_code==200,response.text
    return task,response.json()['data']


def history(client,task,saved):
    base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+saved['id']
    assert client.get(base,headers=headers()).json()['data']==saved
    again=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=2))
    assert again.status_code==200,again.text
    assert again.json()['data']['revision']==2
    assert client.get(base+'/versions/1',headers=headers()).json()['data']==saved


def test_proposal_competitive_child_and_report_export(core_case):
    client,dsn,buyer,contact=core_case
    from tests.test_exports_authorization_db import _permit
    with psycopg.connect(dsn) as db: _permit(db,'export_accounts')
    from tests.test_run_admission_db import LIMITS
    native=client.post(f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}/runs',headers=_h(key='task12-native-run'),json={
        'icp_version_id':ICP,'target_companies':1,'max_cost':{'amount':'1.000000','currency':'USD'},
        'limits':{**LIMITS,'max_queries_per_run':1,'max_results':1,'max_pages':1,'provider_concurrency':1}})
    assert native.status_code==202,native.text
    run=native.json()['data']['id']
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE search_runs SET status='completed' WHERE id=%s",(run,))
        db.execute('UPDATE evidence SET run_id=%s WHERE company_id=(SELECT company_id FROM project_buyers WHERE id=%s)',(run,buyer))
        db.execute('UPDATE source_documents SET run_id=%s WHERE id IN (SELECT source_document_id FROM evidence WHERE run_id=%s)',(run,run))
        excerpt=db.execute('SELECT excerpt FROM evidence WHERE run_id=%s LIMIT 1',(run,)).fetchone()[0]
    refs=[ref('buyer',buyer),ref('profile',ICP),ref('run',run),{**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
    for language in ('en','zh-HK'):
        args={'language':language,'buyer_id':buyer,'profile_id':ICP}
        child_task,child=prepare(client,'sales-competitors',{**args,'competitor_names':[excerpt.split()[0]]},refs)
        history(client,child_task,child)
        task,parent=prepare(client,'sales-prospect',{'buyer_id':buyer,'objective':'Review'},refs+[ref('output',child['id'])])
        assert not any('competitive_document' in s for s in parent['content']['unknowns'])
        assert parent['dependencies']==[{'id':child['id'],'revision':1}]
        terms=[{'price':{'amount':'500','currency':'HKD'},'scope':'Sensors','exclusions':'Installation','timeline':'To agree','evidence':[refs[-1]]}]
        proposal=new_task(client,'sales-proposal',{**args,'pain_points':['Sensors'],'terms':terms},refs)
        missing=client.post(SALES_ROOT+'/'+proposal['id']+'/core-preparation',headers=headers(version=1))
        assert missing.status_code==409 and 'case' in missing.json()['message']
        assert client.get(SALES_ROOT+'/'+proposal['id'],headers=headers()).json()['data']['state']=='needs_input'
        proposal_task,saved=prepare(client,'sales-proposal',{**args,'pain_points':['Sensors'],'terms':terms,'case_study_refs':[refs[0]]},refs)
        history(client,proposal_task,saved)
        assert saved['content']['terms'][0]['price']['amount']=='500'
        _,report=prepare(client,'sales-report',{'language':language,'as_of':datetime.now(timezone.utc).isoformat(),'buyer_ids':[buyer]},refs)
        base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+report['id']
        for fmt in ('markdown','pdf'):
            h=headers(version=1)
            response=client.post(base+'/exports',headers=h,json={'revision':1,'format':fmt,'approved':True})
            assert response.status_code==200,response.text
            exported=response.json()['data']
            assert client.post(base+'/exports',headers=h,json={'revision':1,'format':fmt,'approved':True}).json()['data']==exported
            if fmt=='pdf':
                export_task,saved_export=prepare(client,'sales-report-pdf',{'language':language,'output_id':report['id'],'output_revision':1,'export_id':exported['id']},[ref('output',report['id'])])
                assert saved_export['content']['export_ref']==exported
                assert saved_export['dependencies']==[{'id':report['id'],'revision':1}]
                history(client,export_task,saved_export)
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT count(*) FROM model_receipts').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM search_runs').fetchone()[0]==1


def test_native_upload_understanding_and_image_unknown(core_case,upload_cleanup):
    import hashlib
    from tests.test_document_upload_routes_db import staged,complete
    from tests.pptx_fixtures import pptx_bytes
    client,dsn,buyer,contact=core_case
    docs=[]
    for index,texts in enumerate((('Product: 香港感應器',),('',),('香港感應器 meeting notes',''))):
        text=texts[0]
        body=pptx_bytes(texts)
        upload=staged(client,body,key=f'task12-upload-{index}',name=f'doc{index}.pptx')
        response=complete(client,upload,key=f'task12-complete-{index}')
        assert response.status_code==202,response.text
        doc=response.json()['data'];docs.append(doc)
        for language in ('en','zh-HK'):
            task,saved=prepare(client,'understand-documents',{'language':language,'document_ids':[doc['id']],'question':'What product?'})
            content=saved['content']
            assert content['document_basis'][0]['sha256']==hashlib.sha256(body).hexdigest()
            if text:
                assert any('香港感應器' in s for s in content['extracted_passages'])
                if len(texts)==1: history(client,task,saved)
                else:
                    assert content['extraction_status']=='partial'
                    assert client.get(SALES_ROOT+'/'+task['id'],headers=headers()).json()['data']['state']=='needs_input'
            else:
                assert content['extraction_status']=='unavailable'
                assert content['extracted_passages']==[]
                assert client.get(SALES_ROOT+'/'+task['id'],headers=headers()).json()['data']['state']=='needs_input'
            base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+saved['id']
            assert client.get(base+'/versions/1',headers=headers()).json()['data']==saved
            with psycopg.connect(dsn) as db:
                assert db.execute('SELECT count(*) FROM sales_output_dependencies WHERE output_id=%s AND kind=%s AND source_id=%s',
                    (saved['id'],'document',doc['id'])).fetchone()[0]>=1
    exported=client.post(base+'/exports',headers=headers(version=1),json={'revision':1,'format':'markdown','approved':True})
    assert exported.status_code==200,exported.text
    download=f'/v1/workspaces/{WORKSPACE_A}/exports/{exported.json()["data"]["id"]}/content'
    assert client.get(download,headers=headers()).status_code==200
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE offer_documents SET status='deleted',deleted_at=now() WHERE id=%s",(docs[-1]['id'],))
    assert client.get(base,headers=headers()).json()['data']['availability']=='unavailable'
    assert client.get(download,headers=headers()).status_code==403


def test_remaining_documents_and_pipeline_saved(core_case):
    client,dsn,buyer,contact=core_case
    refs=[ref('buyer',buyer),ref('profile',ICP),{**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
    for language in ('en','zh-HK'):
        entries=[('sales-prep',{'buyer_id':buyer,'meeting_at':datetime.now(timezone.utc).isoformat(),'objective':'Discuss sensors'}),
            ('sales-objections',{'profile_id':ICP,'buyer_id':buyer,'objections':['Price']}),
            ('sales-report',{'as_of':datetime.now(timezone.utc).isoformat(),'buyer_ids':[buyer]})]
        for skill,args in entries:
            task=new_task(client,skill,{**args,'language':language},refs)
            response=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
            assert response.status_code==200,response.text
            saved=response.json()['data']
            base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+saved['id']
            assert client.get(base,headers=headers()).json()['data']==saved
            if skill=='sales-report':
                row=saved['content']['rows'][0]
                assert row['stage'] is None and row['value'] is None
                assert row['advisory_score'] is None
            repeat=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=2))
            assert repeat.status_code==200,repeat.text
            assert repeat.json()['data']['revision']==2
            assert client.get(base+'/versions/1',headers=headers()).json()['data']==saved


def test_pdf_exports_the_selected_revision(core_case,tmp_path):
    client,dsn,buyer,contact=core_case
    from tests.test_exports_authorization_db import _permit
    with psycopg.connect(dsn) as db: _permit(db,'export_accounts')
    refs=[ref('buyer',buyer),ref('profile',ICP),{**ref('project_fact',FACT_ID),'locator':f'fact:profile:{ICP}:{FACT_ID}'}]
    task=new_task(client,'sales-prep',{'language':'zh-HK','buyer_id':buyer,'meeting_at':datetime.now(timezone.utc).isoformat(),'objective':'香港銷售會議'},refs)
    result=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=1))
    assert result.status_code==200,result.text
    saved=result.json()['data']
    base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+saved['id']
    exported=client.post(base+'/exports',headers=headers(version=1),json={'revision':1,'format':'pdf','approved':True})
    assert exported.status_code==200,exported.text
    native=exported.json()['data']
    assert native['surface']=='export' and native['revision']==1
    url=f'/v1/workspaces/{WORKSPACE_A}/exports/{native["id"]}/content'
    content=client.get(url,headers=headers())
    assert content.status_code==200 and content.content.startswith(b'%PDF')
    from pypdf import PdfReader
    from io import BytesIO
    evidence=tmp_path
    (evidence/'authorized-zhHK.pdf').write_bytes(content.content)
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(content.content)).pages)
    assert '香港銷售會議' in text
    (evidence/'authorized-zhHK.txt').write_text(text,encoding='utf-8')
    history(client,task,saved)
    # Historical exact revision remains approved even after output regeneration.
    assert client.get(url,headers=headers()).status_code==200
    assert client.post(base+'/exports',headers=headers(version=1),json={'revision':1,'format':'pdf','approved':False}).status_code==422
    with psycopg.connect(dsn) as db:
        db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(buyer,))
    assert client.get(url,headers=headers()).status_code in (403,412)


def test_native_pipeline_asof_filter_and_expired_export(core_case):
    client,dsn,buyer,contact=core_case
    from tests.test_exports_authorization_db import _permit
    with psycopg.connect(dsn) as db: _permit(db,'export_accounts')
    root=f'/v1/workspaces/{WORKSPACE_A}/projects/{PROJECT}'
    before=datetime.now(timezone.utc).isoformat()
    result=client.post(root+'/outcomes',headers=_h(key='task12-native-outcome'),json={'buyer_id':buyer,'stage':'opportunity',
        'occurred_at':datetime.now(timezone.utc).isoformat(),'source':'manual','notes':'Synthetic verified conversation'})
    assert result.status_code==201,result.text
    _,old=prepare(client,'sales-report',{'as_of':before,'buyer_ids':[buyer]})
    assert old['content']['rows'][0]['stage'] is None
    _,current=prepare(client,'sales-report',{'as_of':datetime.now(timezone.utc).isoformat(),'buyer_ids':[buyer]})
    assert current['content']['rows'][0]['stage']=='opportunity'
    assert current['content']['record_basis'][0]['id']==result.json()['data']['id']
    lists=client.post(root+'/lists',headers=_h(key='task12-filter-list'),json={'name':'Filter'})
    assert lists.status_code==201,lists.text
    _,filtered=prepare(client,'sales-report',{'as_of':datetime.now(timezone.utc).isoformat(),'buyer_ids':[buyer],'list_id':lists.json()['data']['id']})
    assert filtered['content']['rows']==[] and filtered['content']['unavailable_buyer_ids']==[buyer]
    base=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+current['id']
    response=client.post(base+'/exports',headers=headers(version=1),json={'revision':1,'format':'markdown','approved':True})
    assert response.status_code==200,response.text
    job=response.json()['data']['id']
    with psycopg.connect(dsn) as db:
        db.execute("UPDATE export_jobs SET expires_at=now()-interval '1 second' WHERE id=%s",(job,))
    assert client.get(f'/v1/workspaces/{WORKSPACE_A}/exports/{job}/content',headers=headers()).status_code==403
    with psycopg.connect(dsn) as db:
        db.execute('DELETE FROM buyer_lists WHERE id=%s',(lists.json()['data']['id'],))


def test_client_candidate_cannot_forge_native_pipeline(core_case):
    client,dsn,buyer,contact=core_case
    task,saved=prepare(client,'sales-report',{'as_of':datetime.now(timezone.utc).isoformat(),'buyer_ids':[buyer]})
    candidate={key:saved[key] for key in ('kind','content','citations','dependencies','native_refs')}
    candidate['content']['rows'][0]['advisory_score']=100
    response=client.post(SALES_ROOT.replace('sales-tasks','sales-outputs'),headers=headers(version=2),json={
        'task_id':task['id'],'expected_task_revision':2,'candidate':candidate,'visibility':'thread'})
    assert response.status_code==409,response.text
