"""Q05 fictional owned workbench only; no provider or live account verification."""
import json
import sys
import psycopg
from tests.fixtures.run_browser_research import owner_dsn, WORKSPACE
PROJECT='e1000000-0000-4000-8000-000000000001'
OTHER='e0000000-0000-4000-8000-000000000101'
OTHER_PROJECT='e1050000-0000-4000-8000-000000000001'
OPERATOR='e0000000-0000-4000-8000-000000000002'

def main():
    # Prove container ownership once per bounded helper invocation; never cache DSNs across cases.
    with psycopg.connect(owner_dsn()) as db:
        if db.execute('SELECT name FROM workspaces WHERE id=%s',(WORKSPACE,)).fetchone()!=('E2E fixture workspace',):
            raise RuntimeError('unknown fictional workbench')
        db.execute("SET LOCAL lock_timeout='5s'")
        command=sys.argv[1] if len(sys.argv)>1 else 'seed'
        if command=='seed':
            rows=[]
            for i in range(10):
                user=f'7100000{i+1}-0000-4000-8000-000000c011de' if i<2 else f'f2000000-0000-4000-8000-{i:012x}'
                rows.append((f'f1000000-0000-4000-8000-{i:012x}',user))
            db.cursor().executemany("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,'urn:buyeros:e2e',%s,%s) ON CONFLICT(id) DO UPDATE SET display_name=EXCLUDED.display_name",[(user,f'directory-{i}',f'Q05 colleague {i+1:02d}') for i,(_,user) in enumerate(rows)])
            db.cursor().executemany("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{viewer}',true) ON CONFLICT(id) DO UPDATE SET active=true,version=1",[(member,WORKSPACE,user) for member,user in rows])
            db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Other audit fixture','live') ON CONFLICT DO NOTHING",(OTHER,))
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES ('e0000000-0000-4000-8000-000000000109',%s,'e0000000-0000-4000-8000-000000000008','{workspace_admin}',true) ON CONFLICT DO NOTHING",(OTHER,))
            db.execute("DELETE FROM api_rate_windows WHERE workspace_id IN (%s,%s) AND actor_id IN ('e0000000-0000-4000-8000-000000000002','e0000000-0000-4000-8000-000000000004','e0000000-0000-4000-8000-000000000006')",(WORKSPACE,OTHER))
            db.execute('UPDATE project_buyers SET owner_user_id=NULL,version=1 WHERE workspace_id=%s AND project_id=%s',(WORKSPACE,PROJECT))
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES ('e0050000-0000-4000-8000-000000000002',%s,%s,'{operator}',true) ON CONFLICT DO NOTHING",(OTHER,OPERATOR))
            db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES (%s,%s,'Q05 other project','Fictional Seller','Fixture offer','{US}','{en}',1) ON CONFLICT DO NOTHING",(OTHER_PROJECT,OTHER))
            if db.execute('SELECT count(*) FROM project_buyers WHERE workspace_id=%s AND project_id=%s',(OTHER,OTHER_PROJECT)).fetchone()[0]==0:
                values=[(f'e2050000-0000-4000-8000-{i:012x}',f'e3050000-0000-4000-8000-{i:012x}',f'Scope B Fixture {i:03d}') for i in range(101)]
                db.cursor().executemany('INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,%s,%s)',[(company,OTHER,name,name) for _,company,name in values])
                db.cursor().executemany('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)',[(buyer,OTHER,OTHER_PROJECT,company) for buyer,company,_ in values])
            print(json.dumps({'fixture_only':True,'colleagues':[{'membership_id':str(m),'user_id':str(u)} for m,u in rows],'other':OTHER,'other_project':OTHER_PROJECT}))
        elif command=='targets':
            rows=db.execute('SELECT id,user_id FROM memberships WHERE workspace_id=%s AND id::text LIKE %s ORDER BY id LIMIT 10',(WORKSPACE,'f100%')).fetchall()
            print(json.dumps({'fixture_only':True,'colleagues':[{'membership_id':str(m),'user_id':str(u)} for m,u in rows],'other':OTHER,'other_project':OTHER_PROJECT}))
        elif command=='cleanup':
            db.execute('DELETE FROM memberships WHERE workspace_id=%s AND user_id=%s',(OTHER,OPERATOR));print(json.dumps({'fixture_only':True,'other_operator_removed':True}))
        elif command=='deactivate':
            db.execute('UPDATE memberships SET active=false,version=version+1 WHERE workspace_id=%s AND id=%s',(WORKSPACE,sys.argv[2]));print(json.dumps({'fixture_only':True,'deactivated':sys.argv[2]}))
        elif command=='stale':
            db.execute('UPDATE project_buyers SET version=version+1 WHERE workspace_id=%s AND project_id=%s AND id=%s',(WORKSPACE,PROJECT,sys.argv[2]));print(json.dumps({'fixture_only':True,'stale':sys.argv[2]}))
        elif command=='inspect':
            buyers=db.execute('SELECT id,owner_user_id,version FROM project_buyers WHERE workspace_id=%s AND project_id=%s ORDER BY id',(WORKSPACE,PROJECT)).fetchall()
            print(json.dumps({'fixture_only':True,'buyers':[{'id':str(b),'owner':str(o) if o else None,'version':v} for b,o,v in buyers]}))
        else:raise RuntimeError('unknown fixture command')
if __name__=='__main__':main()
