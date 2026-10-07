"""Q02 fictional directory; existing owner_dsn proves owned Docker + fixture DB."""
import json
import uuid
import psycopg
from tests.fixtures.run_browser_research import owner_dsn, WORKSPACE
ADMIN='e0000000-0000-4000-8000-000000000008'
def main():
    with psycopg.connect(owner_dsn()) as db:
        if db.execute("SELECT name FROM workspaces WHERE id=%s",(WORKSPACE,)).fetchone()!=('E2E fixture workspace',):
            raise RuntimeError('unknown fictional workspace')
        for i in range(246):
            user=f'7100000{i+1}-0000-4000-8000-000000c011de' if i<2 else f'f2000000-0000-4000-8000-{i:012x}'
            member=f'f1000000-0000-4000-8000-{i:012x}'
            name='Alex Chen' if i<2 else None if i==2 else f'Fixture member {i:03d}'
            db.execute("INSERT INTO users(id,issuer,subject,display_name) VALUES (%s,'urn:buyeros:e2e',%s,%s) ON CONFLICT(id) DO UPDATE SET display_name=EXCLUDED.display_name",(user,f'directory-{i}',name))
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{viewer}',true) ON CONFLICT(id) DO UPDATE SET roles='{viewer}',active=true,version=1",(member,WORKSPACE,user))
        rows=db.execute('SELECT id,user_id FROM memberships WHERE workspace_id=%s ORDER BY id',(WORKSPACE,)).fetchall()
        if len(rows)!=250:raise RuntimeError('unexpected directory size')
        db.execute("UPDATE users SET display_name='Search target 101' WHERE id=%s",(rows[100][1],))
        other='e0000000-0000-4000-8000-000000000101'
        db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Other audit fixture','live') ON CONFLICT DO NOTHING",(other,))
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES ('e0000000-0000-4000-8000-000000000109',%s,%s,'{workspace_admin}',true) ON CONFLICT DO NOTHING",(other,ADMIN))
        # Establish this case's other-workspace directory explicitly. Previous
        # job cases also need the fictional reviewer; do not assume only one row.
        reviewer='e0000000-0000-4000-8000-000000000004'
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES "
            "('e0000000-0000-4000-8000-000000000105',%s,%s,'{reviewer}',true) "
            "ON CONFLICT(id) DO UPDATE SET roles='{reviewer}',active=true",(other,reviewer))
        operator='e0000000-0000-4000-8000-000000000002'
        db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES "
            "('e0050000-0000-4000-8000-000000000002',%s,%s,'{operator}',true) "
            "ON CONFLICT(id) DO UPDATE SET roles='{operator}',active=true",(other,operator))
        print(json.dumps({'fixture_only':True,'ids':[str(r[1]) for r in rows],
            'target':str(rows[100][1]),'member':str(rows[100][0]),'other_ids':[reviewer,ADMIN,operator]}))
if __name__=='__main__':main()
