"""C61-21 same project/actor summary and actual filtered-list contracts."""
import json,uuid
from datetime import datetime,timezone
import psycopg,pytest
from tests.test_buyer_review_db import api as buyer_api,WORKSPACE_A,WORKSPACE_B,PROJECT_A,PROJECT_A2,PROJECT_B,OPERATOR,REVIEWER,ADMIN,VIEWER,_h
from tests.contract_validation import assert_contract_response

def uid(subject):return uuid.uuid5(uuid.NAMESPACE_URL,subject)
def root(project):return f'/v1/workspaces/{WORKSPACE_A}/projects/{project}'

@pytest.fixture
def queue_case(buyer_api,seeded):
 with buyer_api as api:
  with psycopg.connect(seeded) as db:
   db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'Queue B','Fixture','Offer','{US}','{en}',1) ON CONFLICT DO NOTHING",(PROJECT_A2,WORKSPACE_A))
   for project,n,pending,failed,uncertain in [(PROJECT_A,5,2,2,1),(PROJECT_A2,7,3,3,2)]:
    buyers=[];icp=uuid.uuid4()
    db.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash) VALUES (%s,%s,%s,1,'{}','fixture-queue')",(icp,WORKSPACE_A,project))
    for i in range(n):
     company,buyer=uuid.uuid4(),uuid.uuid4();buyers.append(buyer)
     db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,'Fixture',%s)",(company,WORKSPACE_A,f'Queue {i}'))
     db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id,owner_user_id) VALUES (%s,%s,%s,%s,%s)",(buyer,WORKSPACE_A,project,company,uid(OPERATOR) if i<2 else None))
     if i<2:
      db.execute("INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,icp_version_id,evidence_set_hash,verdict,rationale,evidence_ids) VALUES (%s,%s,%s,%s,%s,'fixture','match','Fixture','[]')",(uuid.uuid4(),WORKSPACE_A,project,buyer,icp))
     if i==0:
      db.execute("INSERT INTO human_reviews(id,workspace_id,project_buyer_id,state,actor_user_id) VALUES (%s,%s,%s,'accepted',%s)",(uuid.uuid4(),WORKSPACE_A,buyer,uid(REVIEWER)))
     if i==1:
      db.execute("INSERT INTO human_reviews(id,workspace_id,project_buyer_id,state,actor_user_id,created_at) VALUES (%s,%s,%s,'rejected',%s,now()-interval '1 day'),(%s,%s,%s,'awaiting_review',%s,now())",(uuid.uuid4(),WORKSPACE_A,buyer,uid(REVIEWER),uuid.uuid4(),WORKSPACE_A,buyer,uid(REVIEWER)))
    for i in range(pending+1):
     draft,revision=uuid.uuid4(),uuid.uuid4()
     content={'subject':f'Queue draft {i}','body':'Fixture body','language':'en','kind':'initial','icp_version_id':str(icp),'evidence_set_hash':'a'*64,'value_proposition_fact_ids':[]}
     db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) VALUES (%s,%s,%s,%s,1,%s)",(draft,WORKSPACE_A,project,buyers[0],'review_requested' if i<pending else 'draft'))
     db.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,content,content_hash) VALUES (%s,%s,%s,1,%s::jsonb,%s)",(revision,WORKSPACE_A,draft,json.dumps(content),'b'*64))
    for subject,count in [(OPERATOR,failed),(REVIEWER,5 if project==PROJECT_A else 7)]:
     for _ in range(count):
      db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested,processed,blocked) VALUES (%s,%s,%s,%s,'bulk_mutation','reviewBuyers','{}','failed',1,1,1)",(uuid.uuid4(),WORKSPACE_A,project,uid(subject)))
    for subject,count in [(OPERATOR,uncertain),(REVIEWER,4 if project==PROJECT_A else 6)]:
     quote,job=uuid.uuid4(),uuid.uuid4()
     db.execute("INSERT INTO enrichment_quotes(id,workspace_id,project_id,actor_id,purpose,selection,request_hash,quote_hash,price_version,max_cost,status) VALUES (%s,%s,%s,%s,'contact_research','{}','fixture','fixture','fixture',1,'consumed')",(quote,WORKSPACE_A,project,uid(subject)))
     db.execute("INSERT INTO enrichment_jobs(id,workspace_id,quote_id,state) VALUES (%s,%s,%s,'unknown')",(job,WORKSPACE_A,quote))
     for i in range(count+1):
      db.execute("INSERT INTO provider_operations(id,workspace_id,job_id,intent_key,capability,input_hash,status,provider_ref,account_reference) VALUES (%s,%s,%s,%s,'contact_lookup','fixture',%s,'PRIVATE-RECEIPT','PRIVATE-ACCOUNT')",(uuid.uuid4(),WORKSPACE_A,job,str(uuid.uuid4()),'unknown' if i<count else 'accepted'))
    # A real durable research hold proves run/project/actor; no intent-key parsing.
    for subject in [OPERATOR,REVIEWER]:
     run,op,reservation,run_account,project_account=(uuid.uuid4() for _ in range(5))
     db.execute("INSERT INTO search_runs(id,workspace_id,project_id,icp_version_id,status,limits,execution_snapshot) VALUES (%s,%s,%s,%s,'running','{}',%s::jsonb)",(run,WORKSPACE_A,project,icp,json.dumps({'actor_id':str(uid(subject))})))
     for account,scope,scope_id in [(run_account,'run',run),(project_account,'project',project)]:
      db.execute("INSERT INTO budget_accounts(id,workspace_id,scope,scope_id,category,currency,period,period_start,period_end,approved_limit,settled_spend) VALUES (%s,%s,%s,%s,'all','USD','fixture',now(),now()+interval '1 day',10,0) ON CONFLICT (workspace_id,scope,scope_id,category,currency,period_start) DO NOTHING",(account,WORKSPACE_A,scope,scope_id))
      if scope=='project':project_account=db.execute("SELECT id FROM budget_accounts WHERE workspace_id=%s AND scope='project' AND scope_id=%s AND period_start=now()",(WORKSPACE_A,project)).fetchone()[0]
     db.execute("INSERT INTO budget_reservations(id,workspace_id,account_id,operation_id,intent_key,price_version,currency,origin_period_start,upper_bound,remaining_hold,state) VALUES (%s,%s,%s,%s,%s,'fixture','USD',now(),1,1,'unknown')",(reservation,WORKSPACE_A,project_account,op,str(op)))
     for account in [run_account,project_account]:db.execute("INSERT INTO budget_reservation_allocations(id,workspace_id,reservation_id,account_id) VALUES (%s,%s,%s,%s)",(uuid.uuid4(),WORKSPACE_A,reservation,account))
     db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) VALUES (%s,%s,%s,'account_search','fixture','submitting')",(op,WORKSPACE_A,str(uuid.uuid4())))
   # Missing provenance cannot acquire arbitrary project/actor scope.
   db.execute("INSERT INTO provider_operations(id,workspace_id,intent_key,capability,input_hash,status) VALUES (%s,%s,%s,'account_search','fixture','unknown')",(uuid.uuid4(),WORKSPACE_A,str(uuid.uuid4())))
  try:yield api,seeded
  finally:
   with psycopg.connect(seeded,autocommit=True) as db:
    for table in ['approvals','draft_revisions','outreach_drafts','provider_operations','enrichment_jobs','enrichment_quotes','budget_reservation_allocations','budget_reservations','budget_accounts','search_runs']:
     db.execute(f'DELETE FROM {table} WHERE workspace_id=%s',(WORKSPACE_A,))

def get(api,path,subject=OPERATOR,params=None):
 r=api.get(path,headers=_h(subject=subject),params=params);assert r.status_code==200,r.text;return r.json()['data']

@pytest.mark.parametrize('project,expected',[(PROJECT_A,[4,2,3,2,3,2]),(PROJECT_A2,[6,3,5,3,5,3])])
def test_work_queue_count_equals_filtered_list(queue_case,project,expected):
 api,dsn=queue_case;summary=get(api,root(project)+'/work-queue')
 assert_contract_response('WorkQueueResponse',{'data':summary,'request_id':str(uuid.uuid4()),'data_mode':'live'})
 assert [x['count'] for x in summary['items']]==expected
 by_kind={x['kind']:x for x in summary['items']}
 for kind,filters in [('awaiting_review',{'review':['awaiting_review']}),('unassigned',{'owner_unassigned':True}),('unknown_fit',{'unknown_fit':True})]:
  snapshot=api.post(root(project)+'/buyer-snapshots',json={'filters':filters,'sort':'best_fit','requested_limit':100},headers=_h(subject=OPERATOR,key='queue-'+kind+'-'+project))
  assert snapshot.status_code==201,snapshot.text
  page=get(api,root(project)+'/buyers',params={'snapshot_id':snapshot.json()['data']['id'],'offset':0,'limit':100})
  assert page['total']==by_kind[kind]['count']
 assert get(api,root(project)+'/drafts',params={'approval':'pending','limit':100})['total']==by_kind['pending_approval']['count']
 assert get(api,f'/v1/workspaces/{WORKSPACE_A}/jobs',params={'project_id':project,'status':'failed','limit':100})['total']==by_kind['failed_job']['count']
 receipt=get(api,root(project)+'/provider-operations',params={'acceptance':'unknown','limit':100})
 assert receipt['total']==by_kind['unknown_acceptance']['count']
 assert len({x['id'] for x in receipt['items']})==receipt['total']
 assert {x['status'] for x in receipt['items']}=={'unknown','submitting'}
 assert 'PRIVATE-' not in json.dumps(receipt) and 'input_hash' not in json.dumps(receipt)
 assert by_kind['pending_approval']['filters']=={'approval':'pending'}
 assert by_kind['unknown_acceptance']['filters']=={'acceptance':'unknown'}
 assert datetime.fromisoformat(summary['as_of']).tzinfo is not None

@pytest.mark.parametrize('subject,failed,uncertain',[(OPERATOR,2,2),(REVIEWER,5,5),(ADMIN,7,7),(VIEWER,0,0)])
def test_work_queue_actor_roles_project_and_no_side_effects(queue_case,subject,failed,uncertain):
 api,dsn=queue_case
 with psycopg.connect(dsn) as db:
  before={t:db.execute(f'SELECT count(*) FROM {t} WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0] for t in ['outbox_events','provider_operations','budget_reservations','idempotency_records','audit_events','buyer_snapshots']}
 first=get(api,root(PROJECT_A)+'/work-queue',subject);second=get(api,root(PROJECT_A)+'/work-queue',subject)
 counts={x['kind']:x['count'] for x in first['items']};assert counts['failed_job']==failed and counts['unknown_acceptance']==uncertain
 assert second['as_of']>=first['as_of']
 assert get(api,root(PROJECT_A)+'/provider-operations',subject,{'acceptance':'unknown','limit':1})['total']==uncertain
 assert api.get(f'/v1/workspaces/{WORKSPACE_B}/projects/{PROJECT_B}/work-queue',headers=_h(subject=subject)).status_code==404
 assert api.get(root(PROJECT_B)+'/work-queue',headers=_h(subject=subject)).status_code==404
 with psycopg.connect(dsn) as db:
  assert before=={t:db.execute(f'SELECT count(*) FROM {t} WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0] for t in before}

def test_work_queue_filters_are_typed_and_receipts_bounded(queue_case):
 api,_=queue_case
 for path,query in [(root(PROJECT_A)+'/drafts',{'approval':'anything'}),(root(PROJECT_A)+'/provider-operations',{'acceptance':'accepted'}),(root(PROJECT_A)+'/provider-operations',{'limit':101})]:
  assert api.get(path,params=query,headers=_h(subject=OPERATOR)).status_code==422
 rows=[]
 for offset in [0,1]:
  page=get(api,root(PROJECT_A)+'/provider-operations',params={'acceptance':'unknown','limit':1,'offset':offset});assert page['total']==2;rows.extend(page['items'])
 assert len({x['id'] for x in rows})==2

def test_provider_receipts_reject_cross_project_buyer_provenance(queue_case):
 api,dsn=queue_case
 with psycopg.connect(dsn) as db:
  job=db.execute("SELECT j.id FROM enrichment_jobs j JOIN enrichment_quotes q ON q.id=j.quote_id AND q.workspace_id=j.workspace_id WHERE q.project_id=%s AND q.actor_id=%s",(PROJECT_A,uid(OPERATOR))).fetchone()[0]
  foreign=db.execute("SELECT id FROM project_buyers WHERE project_id=%s LIMIT 1",(PROJECT_A2,)).fetchone()[0]
  operation=uuid.uuid4();db.execute("INSERT INTO provider_operations(id,workspace_id,job_id,buyer_id,intent_key,capability,input_hash,status) VALUES (%s,%s,%s,%s,%s,'contact','fixture','unknown')",(operation,WORKSPACE_A,job,foreign,str(operation)))
 assert get(api,root(PROJECT_A)+'/provider-operations',params={'acceptance':'unknown'})['total']==2
 assert get(api,root(PROJECT_A2)+'/provider-operations',params={'acceptance':'unknown'})['total']==3
 with psycopg.connect(dsn) as db:assert db.execute('SELECT status FROM provider_operations WHERE id=%s',(operation,)).fetchone()==('unknown',)

def test_receipt_list_holds_one_snapshot_during_concurrent_new_receipt(queue_case,monkeypatch):
 api,dsn=queue_case
 from buyeros_api.api.routes import work_queue
 original=work_queue.provider_operations_query;inserted=False
 def concurrent(**kwargs):
  nonlocal inserted
  if not inserted:
   inserted=True
   with psycopg.connect(dsn) as db:
    job=db.execute("SELECT j.id FROM enrichment_jobs j JOIN enrichment_quotes q ON q.id=j.quote_id AND q.workspace_id=j.workspace_id WHERE q.project_id=%s AND q.actor_id=%s",(PROJECT_A,uid(OPERATOR))).fetchone()[0]
    operation=uuid.uuid4();db.execute("INSERT INTO provider_operations(id,workspace_id,job_id,intent_key,capability,input_hash,status) VALUES (%s,%s,%s,%s,'contact','fixture','unknown')",(operation,WORKSPACE_A,job,str(operation)))
  return original(**kwargs)
 monkeypatch.setattr(work_queue,'provider_operations_query',concurrent)
 first=get(api,root(PROJECT_A)+'/provider-operations',params={'acceptance':'unknown','limit':100});assert inserted and first['total']==len(first['items'])==2
 second=get(api,root(PROJECT_A)+'/provider-operations',params={'acceptance':'unknown','limit':100});assert second['total']==len(second['items'])==3
