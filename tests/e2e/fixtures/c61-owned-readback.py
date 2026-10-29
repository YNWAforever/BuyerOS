"""Read metadata only from the proven owned browser fixture. No writes or cleanup."""
import hashlib,json,os,subprocess,sys,uuid
from pathlib import Path
from psycopg.rows import dict_row
import psycopg
sys.path.insert(0,str(Path.cwd()))
from tests.fixtures.run_browser_research import owner_dsn,WORKSPACE,ROOT
project,run,buyer,draft,export=(uuid.UUID(v) for v in sys.argv[1:])
dsn=owner_dsn()
with psycopg.connect(dsn,row_factory=dict_row) as db:
    db.execute('SET TRANSACTION READ ONLY')
    assert db.execute('SELECT id FROM projects WHERE workspace_id=%s AND id=%s',(WORKSPACE,project)).fetchone()['id']==project
    run_row=db.execute('SELECT id,project_id,icp_version_id,status,usage_counters FROM search_runs WHERE workspace_id=%s AND id=%s',(WORKSPACE,run)).fetchone();assert run_row['project_id']==project
    buyer_row=db.execute('SELECT id,project_id,owner_user_id,version FROM project_buyers WHERE workspace_id=%s AND id=%s',(WORKSPACE,buyer)).fetchone();assert buyer_row['project_id']==project
    draft_row=db.execute('SELECT id,project_id,buyer_id,current_revision,state FROM outreach_drafts WHERE workspace_id=%s AND id=%s',(WORKSPACE,draft)).fetchone();assert (draft_row['project_id'],draft_row['buyer_id'])==(project,buyer)
    export_row=db.execute('SELECT id,project_id,draft_id,draft_revision_id,approval_id,state,actor_user_id,record_count FROM export_jobs WHERE workspace_id=%s AND id=%s',(WORKSPACE,export)).fetchone();assert (export_row['project_id'],export_row['draft_id'],export_row['record_count'])==(project,draft,1)
    approval=db.execute('SELECT id,draft_id,draft_revision_id,revision_number,approver_id,recipient_contact_id,invalidated_reason,content_hash,context_fingerprint FROM approvals WHERE workspace_id=%s AND id=%s',(WORKSPACE,export_row['approval_id'])).fetchone()
    assert (approval['draft_id'],approval['draft_revision_id'],approval['revision_number'],approval['invalidated_reason'])==(draft,export_row['draft_revision_id'],draft_row['current_revision'],None)
    outcomes=db.execute('SELECT id,buyer_id,project_id,source,actor_user_id,supersedes_id FROM outcome_events WHERE workspace_id=%s AND project_id=%s AND buyer_id=%s ORDER BY id',(WORKSPACE,project,buyer)).fetchall();assert len(outcomes)==1 and outcomes[0]['source']=='manual'
    runtime=db.execute('SELECT backend,enabled,epoch FROM worker_runtime_control').fetchone();assert runtime['backend']=='celery' and runtime['enabled'] is True
    schema=db.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'];assert schema=='0058_conversation_threads'
    actors=db.execute("SELECT user_id,roles,active FROM memberships WHERE workspace_id=%s AND user_id IN ('e0000000-0000-4000-8000-000000000002','e0000000-0000-4000-8000-000000000004','e0000000-0000-4000-8000-000000000008') ORDER BY user_id",(WORKSPACE,)).fetchall()
    original_ops=db.execute("SELECT DISTINCT p.id,p.capability,p.status,p.provider_name,p.account_reference,p.provider_ref FROM provider_operations p JOIN budget_reservations b ON b.workspace_id=p.workspace_id AND b.operation_id=p.id JOIN budget_reservation_allocations a ON a.workspace_id=b.workspace_id AND a.reservation_id=b.id JOIN budget_accounts c ON c.workspace_id=a.workspace_id AND c.id=a.account_id WHERE p.workspace_id=%s AND c.scope='run' AND c.scope_id=%s ORDER BY p.id",(WORKSPACE,run)).fetchall()
marker=(ROOT/'test-results/e2e-db-container.txt').read_text().strip()
if sys.platform=='linux':
    from c61_built_owner import read_owned_linux_built_artifact
    built=read_owned_linux_built_artifact(ROOT,os.environ.get('C61_SOURCE_SHA',''))
else:
    metadata=json.loads((ROOT/'test-results/audit-ui-container.json').read_text());assert metadata['runtime']=='built' and metadata['mode']=='http'
    inspect=json.loads(subprocess.check_output(['docker','inspect',metadata['name']],text=True))[0]
    assert inspect['Name']=='/'+metadata['name'] and inspect['Config']['Labels']['buyeros.audit.owner']==metadata['owner'] and inspect['Config']['Image']==metadata['image']
    script="const fs=require('fs'),path=require('path'),crypto=require('crypto'),root='/src/.output',rows=[];function walk(d){for(const n of fs.readdirSync(d).sort()){const p=path.join(d,n),s=fs.lstatSync(p);if(s.isDirectory())walk(p);else if(s.isSymbolicLink())rows.push([path.relative(root,p),'symlink',fs.readlinkSync(p)]);else if(s.isFile())rows.push([path.relative(root,p),s.size,crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')]);}}walk(root);if(!rows.length||!rows.some(x=>x[0]==='server/index.mjs'))throw Error('missing built entrypoint');process.stdout.write(JSON.stringify({files:rows.length,manifest_sha256:crypto.createHash('sha256').update(JSON.stringify(rows)).digest('hex'),entrypoint_sha256:rows.find(x=>x[0]==='server/index.mjs')[2]}));"
    built=json.loads(subprocess.check_output(['docker','exec',metadata['name'],'node','-e',script],text=True))
print(json.dumps(dict(environment='built-owned-legacy-Celery-fixture',fixture_only=True,cleanup_marker=marker,workspace_id=str(WORKSPACE),schema_head=schema,worker=runtime,actors=actors,run=run_row,buyer=buyer_row,draft=draft_row,approval=approval,export=export_row,outcomes=outcomes,original_operations=original_ops,built_artifact=built,real_provider_accepted=False,real_Neon_accepted=False,human_UAT=False),default=str))
