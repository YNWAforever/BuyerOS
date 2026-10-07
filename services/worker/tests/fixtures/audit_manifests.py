"""Bounded fictional Q08 helper, owned Docker workbench only. No live/provider fallback."""
import asyncio,json,os,sys,uuid
from urllib.parse import urlsplit,urlunsplit
import psycopg
from tests.fixtures.run_browser_research import owner_dsn,WORKSPACE
PROJECT='e1000000-0000-4000-8000-000000000001'
PREFIX='Q08 Manifest Fixture'

def main():
 dsn=owner_dsn()
 with psycopg.connect(dsn) as db:
  if db.execute('SELECT name FROM workspaces WHERE id=%s',(WORKSPACE,)).fetchone()!=('E2E fixture workspace',):raise RuntimeError('unknown workbench')
  db.execute("SET LOCAL lock_timeout='5s'")
  command=sys.argv[1]
  if command=='seed':
   other='e0000000-0000-4000-8000-000000000101'
   db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES (%s,'Other audit fixture','live') ON CONFLICT DO NOTHING",(other,))
   db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES ('e0050000-0000-4000-8000-000000000002',%s,'e0000000-0000-4000-8000-000000000002','{operator}',true) ON CONFLICT DO NOTHING",(other,))
   db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES ('e1050000-0000-4000-8000-000000000001',%s,'Q08 other project','Fictional Seller','Fixture offer','{US}','{en}',1) ON CONFLICT DO NOTHING",(other,))
   count=int(sys.argv[2])
   if not 1<=count<=10001:raise ValueError('bounded fixture count')
   old=db.execute("SELECT id FROM bulk_manifests WHERE workspace_id=%s AND project_id=%s AND specification->'filters'->>'q'=%s",(WORKSPACE,PROJECT,PREFIX)).fetchall()
   # Only this helper's manifests/jobs/buyers; preserve normal workbench draft FKs.
   for (manifest,) in old:
    jobs=db.execute('SELECT id FROM async_jobs WHERE workspace_id=%s AND manifest_id=%s',(WORKSPACE,manifest)).fetchall()
    for (job,) in jobs:
     db.execute("DELETE FROM outbox_events WHERE workspace_id=%s AND payload->>'job_id'=%s",(WORKSPACE,str(job)))
     db.execute('DELETE FROM async_job_items WHERE workspace_id=%s AND job_id=%s',(WORKSPACE,job))
     db.execute('DELETE FROM async_jobs WHERE workspace_id=%s AND id=%s',(WORKSPACE,job))
    db.execute('DELETE FROM bulk_manifest_items WHERE workspace_id=%s AND manifest_id=%s',(WORKSPACE,manifest))
    db.execute('DELETE FROM bulk_manifests WHERE workspace_id=%s AND id=%s',(WORKSPACE,manifest))
   snapshots=db.execute("SELECT DISTINCT si.snapshot_id FROM buyer_snapshot_items si JOIN project_buyers b ON b.id=si.buyer_id AND b.workspace_id=si.workspace_id JOIN companies c ON c.id=b.company_id AND c.workspace_id=b.workspace_id WHERE si.workspace_id=%s AND si.project_id=%s AND c.display_name LIKE %s",(WORKSPACE,PROJECT,PREFIX+'%')).fetchall()
   for (snapshot,) in snapshots:
    db.execute('DELETE FROM buyer_snapshot_items WHERE workspace_id=%s AND snapshot_id=%s',(WORKSPACE,snapshot))
    db.execute('DELETE FROM buyer_snapshots WHERE workspace_id=%s AND id=%s',(WORKSPACE,snapshot))
   companies=db.execute('SELECT id FROM companies WHERE workspace_id=%s AND display_name LIKE %s',(WORKSPACE,PREFIX+'%')).fetchall()
   for (company,) in companies:
    db.execute('DELETE FROM human_reviews WHERE workspace_id=%s AND project_buyer_id IN (SELECT id FROM project_buyers WHERE workspace_id=%s AND company_id=%s)',(WORKSPACE,WORKSPACE,company))
    db.execute('DELETE FROM fit_assessments WHERE workspace_id=%s AND project_buyer_id IN (SELECT id FROM project_buyers WHERE workspace_id=%s AND company_id=%s)',(WORKSPACE,WORKSPACE,company))
    db.execute('DELETE FROM list_memberships WHERE workspace_id=%s AND buyer_id IN (SELECT id FROM project_buyers WHERE workspace_id=%s AND company_id=%s)',(WORKSPACE,WORKSPACE,company))
    db.execute('DELETE FROM project_buyers WHERE workspace_id=%s AND company_id=%s',(WORKSPACE,company))
    db.execute('DELETE FROM companies WHERE workspace_id=%s AND id=%s',(WORKSPACE,company))
   values=[(uuid.uuid5(uuid.NAMESPACE_URL,f'Q08-buyer-{i}'),uuid.uuid5(uuid.NAMESPACE_URL,f'Q08-company-{i}'),f'{PREFIX} {i:05d}') for i in range(count)]
   db.cursor().executemany('INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,%s,%s)',[(c,WORKSPACE,n,n) for b,c,n in values])
   db.cursor().executemany('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)',[(b,WORKSPACE,PROJECT,c) for b,c,n in values])
   print(json.dumps({'fixture_only':True,'count':count,'ids':[str(b) for b,c,n in values]}));return
  if command=='assess':
   icp=db.execute('SELECT active_icp_version_id FROM projects WHERE id=%s AND workspace_id=%s',(PROJECT,WORKSPACE)).fetchone()[0]
   if icp is None:
    icp=uuid.uuid4();number=db.execute('SELECT coalesce(max(number),0)+1 FROM icp_versions WHERE workspace_id=%s AND project_id=%s',(WORKSPACE,PROJECT)).fetchone()[0]
    db.execute("INSERT INTO icp_versions(id,workspace_id,project_id,number,content,content_hash,basis_offer_revision) VALUES (%s,%s,%s,%s,'{}',%s,1)",(icp,WORKSPACE,PROJECT,number,'sha256:'+'0'*64))
    db.execute('UPDATE projects SET active_icp_version_id=%s WHERE workspace_id=%s AND id=%s',(icp,WORKSPACE,PROJECT))
   buyers=db.execute('SELECT b.id FROM project_buyers b JOIN companies c ON c.id=b.company_id AND c.workspace_id=b.workspace_id WHERE b.workspace_id=%s AND b.project_id=%s AND c.display_name LIKE %s',(WORKSPACE,PROJECT,PREFIX+'%')).fetchall()
   db.cursor().executemany("INSERT INTO fit_assessments(id,workspace_id,project_id,project_buyer_id,icp_version_id,evidence_set_hash,verdict,rationale,evidence_ids) VALUES (%s,%s,%s,%s,%s,%s,'match','Fictional assessment, not live validation','[]')",[(uuid.uuid4(),WORKSPACE,PROJECT,b,icp,'a'*64) for b, in buyers])
   print(json.dumps({'fixture_only':True,'assessed':len(buyers)}));return
  if command=='stale':
   buyer=uuid.UUID(sys.argv[2]);proof=db.execute('SELECT c.display_name FROM project_buyers b JOIN companies c ON c.id=b.company_id AND c.workspace_id=b.workspace_id WHERE b.id=%s AND b.workspace_id=%s AND b.project_id=%s',(buyer,WORKSPACE,PROJECT)).fetchone()
   if not proof or not proof[0].startswith(PREFIX):raise RuntimeError('unknown Q08 buyer')
   db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s AND workspace_id=%s',(buyer,WORKSPACE));print(json.dumps({'fixture_only':True,'stale':str(buyer)}));return
  if command=='inspect':
   buyers=db.execute('SELECT b.id,b.version,b.owner_user_id FROM project_buyers b JOIN companies c ON c.id=b.company_id AND c.workspace_id=b.workspace_id WHERE b.workspace_id=%s AND b.project_id=%s AND c.display_name LIKE %s ORDER BY c.display_name',(WORKSPACE,PROJECT,PREFIX+'%')).fetchall()
   manifests=db.execute('SELECT id,count,status,job_id FROM bulk_manifests WHERE workspace_id=%s AND project_id=%s ORDER BY created_at',(WORKSPACE,PROJECT)).fetchall()
   print(json.dumps({'fixture_only':True,'buyers':[{'id':str(b),'version':v,'owner':str(o) if o else None} for b,v,o in buyers],'manifests':[{'id':str(m),'count':n,'status':s,'job_id':str(j) if j else None} for m,n,s,j in manifests]}));return
  if command not in {'drain','chunk'}:raise RuntimeError('unknown fixture command')
  job=uuid.UUID(sys.argv[2]);proof=db.execute('SELECT project_id,manifest_id,requested FROM async_jobs WHERE workspace_id=%s AND id=%s',(WORKSPACE,job)).fetchone()
  if not proof or str(proof[0])!=PROJECT or proof[1] is None or not 101<=proof[2]<=10000:raise RuntimeError('unknown Q08 job')
  db.execute("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='buyeros_manifest_fixture') THEN CREATE ROLE buyeros_manifest_fixture NOBYPASSRLS IN ROLE buyeros_worker; END IF; END $$")
  db.execute("ALTER ROLE buyeros_manifest_fixture LOGIN PASSWORD 'test-only'")
 parts=urlsplit(dsn);os.environ['BUYEROS_DATABASE_URL']=urlunsplit(parts._replace(netloc=f'buyeros_manifest_fixture:test-only@127.0.0.1:{parts.port}'))
 if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
 from buyeros_api.settings import get_settings
 from buyeros_api.api.deps import tenant_scoped,dispose_engines
 from buyeros_api.services.bulk_service import apply_bulk_chunk
 get_settings.cache_clear()
 async def drain():
  chunks=[]
  try:
   for _ in range(1 if command=='chunk' else 201):
    async with tenant_scoped(WORKSPACE) as session:result=await apply_bulk_chunk(session,job)
    assert result['processed']<=50;chunks.append(result['processed'])
    if command=='chunk' or result['processed']==0:break
   else:raise RuntimeError('bounded drain exhausted')
   print(json.dumps({'fixture_only':True,'job_id':str(job),'chunks':chunks,'total':sum(chunks),'role':'buyeros_worker'}))
  finally:await dispose_engines()
 asyncio.run(drain())
if __name__=='__main__':main()
