"""Fictional completed jobs in the owned audit workbench; never a live API fallback."""
import json
import sys
import uuid
import psycopg
from tests.fixtures.run_browser_research import owner_dsn, WORKSPACE

PROJECT = 'e1000000-0000-4000-8000-000000000001'
ACTOR = 'e0000000-0000-4000-8000-000000000004'

def main():
    count = int(sys.argv[1])
    if count not in (0,21,101):
        raise ValueError('bounded audit fixture only')
    with psycopg.connect(owner_dsn()) as db:
        if db.execute('SELECT company_name FROM projects WHERE workspace_id=%s AND id=%s',(WORKSPACE,PROJECT)).fetchone()!=('Fictional Seller',):
            raise RuntimeError('unknown fixture project')
        other='e0000000-0000-4000-8000-000000000101'
        db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Other audit fixture','live') ON CONFLICT DO NOTHING",(other,))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES ('e0000000-0000-4000-8000-000000000105',%s,%s,'{reviewer}',true) ON CONFLICT DO NOTHING",(other,ACTOR))
        job = str(uuid.uuid4())
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested,processed,updated,blocked,conflicts) VALUES (%s,%s,%s,%s,'bulk_mutation','bulkUpdateBuyers','{}','completed',%s,%s,%s,%s,%s)",
            (job,WORKSPACE,PROJECT,ACTOR,max(1,count),count,(count+2)//3,count//3,(count+1)//3))
        ids=[]
        for index in range(1,count+1):
            buyer=f'e2000000-0000-4000-8000-{index:012x}'
            company=f'e3000000-0000-4000-8000-{index:012x}'
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name,domain) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",(company,WORKSPACE,f'Buyer Fixture {index:02d}',f'Buyer Fixture {index:02d}',f'fixture-{index:02d}.example.test'))
            db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',(buyer,WORKSPACE,PROJECT,company))
            status=('updated','conflict','blocked')[(index-1)%3]
            reason=None if status=='updated' else 'VERSION_CONFLICT' if status=='conflict' else 'POLICY_BLOCKED'
            db.execute('INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status,reason_code,resulting_version) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s)',(uuid.uuid4(),WORKSPACE,job,buyer,index-1,status,reason,2 if status=='updated' else None))
            ids.append(buyer)
        print(json.dumps({'job_id':job,'ids':ids,'fixture_only':True}))
if __name__=='__main__':main()
