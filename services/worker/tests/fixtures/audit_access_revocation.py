"""U05 fictional setup/readback; only existing owner_dsn owned Docker guard."""
import json
import sys
import psycopg
from tests.fixtures.run_browser_research import owner_dsn, WORKSPACE
USER = 'e0000000-0000-4000-8000-000000000002'
MEMBER = 'e0000000-0000-4000-8000-000000000003'
OTHER = 'e0000000-0000-4000-8000-000000000101'

def main():
    action = sys.argv[1]
    if action not in ('reset', 'inspect', 'cleanup'):
        raise ValueError('unsupported fixture action')
    with psycopg.connect(owner_dsn()) as db:
        if db.execute('SELECT name FROM workspaces WHERE id=%s', (WORKSPACE,)).fetchone() != ('E2E fixture workspace',):
            raise RuntimeError('unknown fictional workspace')
        if action in ('reset', 'cleanup'):
            db.execute("UPDATE memberships SET active=true,roles='{operator}',version=1 WHERE id=%s AND user_id=%s AND workspace_id=%s", (MEMBER, USER, WORKSPACE))
            db.execute("UPDATE workspace_preferences SET locale='en' WHERE workspace_id=%s AND user_id=%s", (WORKSPACE, USER))
            if action == 'reset':
                db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Other U05 fixture','live') ON CONFLICT DO NOTHING", (OTHER,))
                db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES ('e0000000-0000-4000-8000-000000000119',%s,%s,'{operator}',true) ON CONFLICT(id) DO UPDATE SET active=true,roles='{operator}'", (OTHER, USER))
        if action == 'cleanup':
            db.execute('DELETE FROM memberships WHERE id=%s AND workspace_id=%s AND user_id=%s', ('e0000000-0000-4000-8000-000000000119', OTHER, USER))
            db.execute("DELETE FROM workspaces WHERE id=%s AND name='Other U05 fixture' AND NOT EXISTS(SELECT 1 FROM memberships WHERE workspace_id=%s) AND NOT EXISTS(SELECT 1 FROM projects WHERE workspace_id=%s)", (OTHER, OTHER, OTHER))
        row = db.execute('SELECT active,roles,version FROM memberships WHERE id=%s', (MEMBER,)).fetchone()
        print(json.dumps({'fixture_only': True, 'active': row[0], 'roles': row[1], 'version': row[2],
            'users': db.execute('SELECT count(*) FROM users').fetchone()[0],
            'memberships': db.execute('SELECT count(*) FROM memberships').fetchone()[0],
            'audit_rows': db.execute('SELECT count(*) FROM audit_events').fetchone()[0]}))
if __name__ == '__main__':
    main()
