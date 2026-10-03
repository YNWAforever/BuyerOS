"""Q14 existing project/actor job query contract on strict owned PostgreSQL."""
import uuid
import psycopg,pytest
from tests.test_buyer_review_db import api as buyer_api,ADMIN,REVIEWER,VIEWER,OPERATOR,WORKSPACE_A,WORKSPACE_B,PROJECT_A,PROJECT_A2,_h
from tests.contract_validation import assert_contract_response
@pytest.fixture
def api(buyer_api):
 with buyer_api as client:yield client

def seed_jobs(dsn,count):
 own=[];other=[]
 with psycopg.connect(dsn) as db:
  db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'Q14 B','Fictional Seller','Fixture offer','{HK}','{en}',1) ON CONFLICT DO NOTHING",(PROJECT_A2,WORKSPACE_A))
  for subject,n,ids in [(REVIEWER,count,own),(OPERATOR,3,other)]:
   for _ in range(n):
    job=str(uuid.uuid4());ids.append(job);db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested,processed,blocked) VALUES (%s,%s,%s,%s,'bulk_mutation','reviewBuyers','{}','failed',1,1,1)",(job,WORKSPACE_A,PROJECT_A2,uuid.uuid5(uuid.NAMESPACE_URL,subject)))
 return own,other

def page(api,subject,project=None,offset=0,limit=20):
 r=api.get(f'/v1/workspaces/{WORKSPACE_A}/jobs',params={'status':'failed','offset':offset,'limit':limit,**({'project_id':project} if project else {})},headers=_h(subject=subject));assert r.status_code==200,r.text;assert_contract_response('AsyncJobPageResponse',r.json());return r.json()['data']

def test_job_scope_project_zero_five_workspace_keeps_current_actor(api,seeded):
 own,other=seed_jobs(seeded,5)
 assert page(api,REVIEWER,PROJECT_A)['total']==0
 assert page(api,REVIEWER,PROJECT_A2)['total']==5
 assert page(api,REVIEWER)['total']==5
 assert page(api,OPERATOR)['total']==3
 assert page(api,ADMIN)['total']==8
 assert page(api,ADMIN,PROJECT_A)['total']==0
 assert page(api,VIEWER)['total']==0
 assert api.get(f'/v1/workspaces/{WORKSPACE_A}/jobs/{other[0]}',headers=_h(subject=REVIEWER)).status_code==404
 assert api.get(f'/v1/workspaces/{WORKSPACE_B}/jobs',headers=_h(subject=REVIEWER)).status_code==404
 assert {x['id'] for x in page(api,REVIEWER)['items']}==set(own)
 with psycopg.connect(seeded) as db:
  assert db.execute('SELECT count(*) FROM outbox_events WHERE workspace_id=%s',(WORKSPACE_A,)).fetchone()[0]==0

@pytest.mark.parametrize('count',[21,101])
def test_job_scope_all_real_schema_rows_paged_without_other_actor(api,seeded,count):
 own,other=seed_jobs(seeded,count);seen=[]
 for offset in range(0,count,20):
  p=page(api,REVIEWER,PROJECT_A2,offset);assert p['total']==count and p['offset']==offset and p['limit']==20;assert len(p['items'])==min(20,count-offset);seen.extend(x['id'] for x in p['items'])
 assert len(seen)==len(set(seen))==count and set(seen)==set(own) and not set(seen)&set(other)
 assert page(api,REVIEWER,PROJECT_A)['items']==[]
