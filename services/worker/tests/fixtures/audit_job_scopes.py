"""Q14 fictional job scope fixture; guarded owned loopback Docker only."""
import json,sys,uuid
import psycopg
from tests.fixtures.run_browser_research import owner_dsn,WORKSPACE
PROJECT_A='e1000000-0000-4000-8000-000000000001'
PROJECT_B='e1140000-0000-4000-8000-000000000002'
REVIEWER='e0000000-0000-4000-8000-000000000004'
OTHER='e0000000-0000-4000-8000-000000000002'
def main():
 count=int(sys.argv[1]);assert count in (5,21,101)
 with psycopg.connect(owner_dsn()) as db:
  if db.execute('SELECT name FROM workspaces WHERE id=%s',(WORKSPACE,)).fetchone()!=('E2E fixture workspace',):raise RuntimeError('unknown workbench')
  if db.execute('SELECT company_name FROM projects WHERE workspace_id=%s AND id=%s',(WORKSPACE,PROJECT_A)).fetchone()!=('Fictional Seller',):raise RuntimeError('unknown fixture project')
  db.execute("DELETE FROM async_job_items WHERE workspace_id=%s AND job_id IN (SELECT id FROM async_jobs WHERE workspace_id=%s AND command->>'q14_fixture'='owned')",(WORKSPACE,WORKSPACE))
  db.execute("DELETE FROM async_jobs WHERE workspace_id=%s AND command->>'q14_fixture'='owned'",(WORKSPACE,))
  db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'Q14 project B','Fictional Seller','Fixture offer','{HK}','{en}',1) ON CONFLICT DO NOTHING",(PROJECT_B,WORKSPACE))
  ids=[];other=[]
  for actor,n,target in [(REVIEWER,count,ids),(OTHER,3,other)]:
   for _ in range(n):
    job=uuid.uuid4();target.append(str(job));db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested,processed,blocked) VALUES (%s,%s,%s,%s,'bulk_mutation','reviewBuyers','{\"q14_fixture\":\"owned\"}','failed',1,1,1)",(job,WORKSPACE,PROJECT_B,actor))
  print(json.dumps({'fixture_only':True,'project_a':PROJECT_A,'project_b':PROJECT_B,'own_ids':ids,'other_ids':other,'own_failed':count,'other_failed':3}))
if __name__=='__main__':main()
