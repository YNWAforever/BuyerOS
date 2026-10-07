"""Fictional queue observations only in the guarded owned browser fixture."""
import json,uuid
import psycopg
from tests.fixtures.run_browser_research import owner_dsn,WORKSPACE

def main():
 actor=uuid.UUID('e0000000-0000-4000-8000-000000000004');other=uuid.UUID('e0000000-0000-4000-8000-000000000002');projects=[]
 with psycopg.connect(owner_dsn()) as db:
  if db.execute("SELECT issuer,subject FROM users WHERE id=%s",(actor,)).fetchone()!=("urn:buyeros:e2e","reviewer"):raise RuntimeError('owned fictional reviewer required')
  for suffix,n,owned,pending,failed,uncertain in [('A',5,2,2,2,1),('B',7,3,3,4,3)]:
   project=uuid.uuid4();buyers=[]
   db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,%s,'C61 fictional seller','Fixture offer','{US}','{en}',1)",(project,WORKSPACE,f'C61 Queue {suffix} {str(project)[:8]}'))
   for i in range(n):
    company,buyer=uuid.uuid4(),uuid.uuid4();buyers.append(buyer)
    db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,'Fixture',%s)",(company,WORKSPACE,f'C61 Queue {suffix} {i}'))
    db.execute("INSERT INTO project_buyers(id,workspace_id,project_id,company_id,owner_user_id) VALUES (%s,%s,%s,%s,%s)",(buyer,WORKSPACE,project,company,actor if i<owned else None))
    if i<owned:db.execute("INSERT INTO human_reviews(id,workspace_id,project_buyer_id,state,actor_user_id) VALUES (%s,%s,%s,'accepted',%s)",(uuid.uuid4(),WORKSPACE,buyer,actor))
   for i in range(pending+1):
    draft=uuid.uuid4();content={'subject':f'C61 pending {i}','body':'Fictional queue draft','language':'en','kind':'initial','icp_version_id':str(uuid.uuid4()),'evidence_set_hash':'a'*64,'value_proposition_fact_ids':[]}
    db.execute("INSERT INTO outreach_drafts(id,workspace_id,project_id,buyer_id,current_revision,state) VALUES (%s,%s,%s,%s,1,%s)",(draft,WORKSPACE,project,buyers[0],'review_requested' if i<pending else 'draft'))
    db.execute("INSERT INTO draft_revisions(id,workspace_id,draft_id,revision_number,content,content_hash) VALUES (%s,%s,%s,1,%s::jsonb,%s)",(uuid.uuid4(),WORKSPACE,draft,json.dumps(content),'b'*64))
   for subject,count in [(actor,failed),(other,5)]:
    for _ in range(count):db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested,processed,blocked) VALUES (%s,%s,%s,%s,'bulk_mutation','reviewBuyers','{}','failed',1,1,1)",(uuid.uuid4(),WORKSPACE,project,subject))
   for subject,count in [(actor,uncertain),(other,4)]:
    quote,job=uuid.uuid4(),uuid.uuid4()
    db.execute("INSERT INTO enrichment_quotes(id,workspace_id,project_id,actor_id,purpose,selection,request_hash,quote_hash,price_version,max_cost,status) VALUES (%s,%s,%s,%s,'contact_research','{}','fixture','fixture','fixture',1,'consumed')",(quote,WORKSPACE,project,subject))
    db.execute("INSERT INTO enrichment_jobs(id,workspace_id,quote_id,state) VALUES (%s,%s,%s,'unknown')",(job,WORKSPACE,quote))
    for i in range(count+1):db.execute("INSERT INTO provider_operations(id,workspace_id,job_id,intent_key,capability,input_hash,status) VALUES (%s,%s,%s,%s,'contact_lookup','fixture',%s)",(uuid.uuid4(),WORKSPACE,job,str(uuid.uuid4()),'unknown' if i<count else 'accepted'))
   projects.append({'id':str(project),'counts':{'awaiting_review':n-owned,'pending_approval':pending,'unassigned':n-owned,'failed_job':failed,'unknown_fit':n,'unknown_acceptance':uncertain}})
 print(json.dumps({'fixture_only':True,'projects':projects}))
if __name__=='__main__':main()
