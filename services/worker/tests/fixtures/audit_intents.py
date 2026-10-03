"""Read admission durability only after existing owned-Docker fixture proof."""
import json
import psycopg
from tests.fixtures.run_browser_research import owner_dsn,WORKSPACE
ACTOR='e0000000-0000-4000-8000-000000000002'
PROJECT='e9100000-0000-4000-8000-000000000001'
with psycopg.connect(owner_dsn()) as db:
    run_ids=[str(r[0]) for r in db.execute("SELECT id FROM search_runs WHERE workspace_id=%s AND project_id=%s AND execution_snapshot->>'actor_id'=%s",(WORKSPACE,PROJECT,ACTOR)).fetchall()]
    counts={'runs':len(run_ids),'run_ids':run_ids}
    counts['admission_outbox']=db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=%s AND event_type='run.discover' AND payload->>'run_id'=ANY(%s)",(WORKSPACE,run_ids)).fetchone()[0]
    counts['economic_intents']=db.execute("SELECT count(*) FROM budget_accounts WHERE workspace_id=%s AND scope='run' AND scope_id::text=ANY(%s)",(WORKSPACE,run_ids)).fetchone()[0]
    counts['provider_operations']=db.execute('SELECT count(*) FROM provider_operations WHERE workspace_id=%s',(WORKSPACE,)).fetchone()[0]
    counts['reservations']=db.execute('SELECT count(*) FROM budget_reservations WHERE workspace_id=%s',(WORKSPACE,)).fetchone()[0]
    print(json.dumps(counts))
