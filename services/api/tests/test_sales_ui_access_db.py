"""Task13 endpoint composition on the strict owned allocator, synthetic providers only."""
import pytest
from tests.test_sales_tasks_api import sales_api, SALES_ROOT
from tests.test_sales_core_journey_db import new_task
from tests.test_conversation_threads_api import headers
from tests.test_xverum_enrichment_db import journey
from tests.test_research_candidate_review_db import review_case, page_case, run_case, project_api, admission_case, migrated
from tests.test_xverum_dispatch_db import dispatch_case,thread_entry
from tests.xverum_fixtures import credit_case,connection_case,provisional_pg,execution_api


def test_ui_saved_readback_and_disabled_recovery(sales_api,monkeypatch):
    client,dsn=sales_api
    task=new_task(client,'first-project',{'offer_description':'Synthetic Task13 offer'})
    response=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=task['revision']))
    assert response.status_code==200,response.text
    output=response.json()['data']
    output_url=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+output['id']
    assert client.get(output_url+'/permissions',headers=headers()).json()['data']=={'can_edit':True}
    from tests.test_conversation_threads_api import ROOT,member,VIEWER
    row=client.get(ROOT+'/'+task['thread_id'],headers=headers()).json()['data']
    assert client.put(ROOT+'/'+row['id']+'/shares/'+member(dsn,VIEWER),headers=headers(version=row['version']),json={'role':'viewer'}).status_code==200
    assert client.get(output_url+'/permissions',headers=headers(VIEWER)).json()['data']=={'can_edit':False}
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','false')
    from buyeros_api.settings import get_settings
    get_settings.cache_clear()
    try:
        url=SALES_ROOT.replace('sales-tasks','sales-outputs')+'/'+output['id']+'/versions/1'
        saved=client.get(url,headers=headers())
        assert saved.status_code==200,saved.text
        assert saved.json()['data']==output
        assert client.get(SALES_ROOT+'/'+task['id'],headers=headers()).status_code==200
    finally:get_settings.cache_clear()


def test_ui_candidates_are_authorized_projection_not_raw_response(journey):
    from tests.test_xverum_connections import headers
    c=journey
    url=c.path.rsplit('/connections',1)[0]+f'/receipts/{c.search.id}/candidates'
    response=c.client.get(url,headers=headers())
    assert response.status_code==200,response.text
    body=response.json()['data']
    assert body['result_type']=='company' and body['results'][0]['id']=='1'
    assert 'raw' not in body and 'request_id' not in body
    stages=c.client.get(c.path.rsplit('/connections',1)[0]+f'/tasks/{c.task}/stages',headers=headers())
    assert stages.status_code==200,stages.text
    assert any(item['receipt']['id']==str(c.detail.id) and item['search_receipt_id']==str(c.search.id) for item in stages.json()['data']['items'])
    import psycopg
    with psycopg.connect(c.dsn) as db:
        db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(c.buyer,))
    assert c.client.get(url,headers=headers()).status_code in {403,409}


# Full browser -> actual HTTP owner -> strict owned PostgreSQL. Provider transport
# stays synthetic; this bridge never accepts a DSN or credential from the browser.
@pytest.mark.parametrize("phase", ["sources", "retry", "capability"])
def test_fix1_browser_native_owner(review_case,monkeypatch,phase):
    import json,os,subprocess,threading
    from pathlib import Path
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    import psycopg
    from tests.test_research_candidate_review_db import review
    from tests.test_api_projects_db import _h,OPERATOR
    from tests.test_run_admission_integration_db import CAPABILITY
    from buyeros_api.api.routes.runs import selected_run_capability
    c=review_case
    native=review(c)
    monkeypatch.setenv('NEXT_PUBLIC_CONVERSATION_HOME','true')
    monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true')
    monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',str(c['workspace']))
    client=c['api']
    client.__enter__()  # One lifespan/event loop for the whole browser journey.
    with psycopg.connect(c['dsn']) as db:
        db.execute("UPDATE search_runs SET status='completed' WHERE id=%s",(c['run'],))
        profile=db.execute('SELECT active_icp_version_id FROM projects WHERE id=%s',(c['project'],)).fetchone()[0]
    from buyeros_api.providers import registry
    capability=registry.DEFAULT_REGISTRY.search_run_capability(environment='production')
    assert capability is not None
    # Provider-independent admission overlay for the fixture's approved distributor profile.
    # No worker/provider is dispatched by this browser admission test.
    capability={**capability,'roles':['distributor']}
    client.app.dependency_overrides[selected_run_capability]=lambda:(capability,'test')
    root=f"/v1/workspaces/{c['workspace']}/projects/{c['project']}"
    from tests.test_conversation_threads_api import create
    thread=create(client)
    state={'deny':False,'starts':[]}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.forward()
        def do_POST(self):self.forward()
        def do_PUT(self):self.forward()
        def forward(self):
            length=int(self.headers.get('Content-Length','0'));body=self.rfile.read(length)
            if self.path=='/fixture-control':
                command=json.loads(body)
                if command.get('stale'):
                    with psycopg.connect(c['dsn']) as db:db.execute('UPDATE project_buyers SET version=version+1 WHERE id=%s',(native['buyer_id'],))
                if 'deny' in command:state['deny']=command['deny']
                if 'opted' in command:monkeypatch.setenv('BUYEROS_SALES_WORKSPACE_IDS',str(c['workspace']) if command['opted'] else '')
                if 'enabled' in command:monkeypatch.setenv('BUYEROS_SALES_SKILLS_ENABLED','true' if command['enabled'] else 'false')
                self.send_response(200);self.end_headers();self.wfile.write(b'{}');return
            headers={'Authorization':_h(OPERATOR)['Authorization'],**{k:v for k,v in self.headers.items() if k.lower() in {'if-match','x-buyeros-if-match','idempotency-key','content-type'}}}
            if state['deny']:
                headers['Authorization']=_h('task13-unrelated-actor')['Authorization']
            response=client.request(self.command,self.path,headers=headers,content=body or None)
            if response.status_code>=400:print('UI API ERROR',self.command,self.path,response.status_code,response.text,flush=True)
            if self.command=='POST' and self.path==root+'/runs' and response.status_code==202:
                state['starts'].append({'key':headers.get('Idempotency-Key') or headers.get('idempotency-key'),'body':json.loads(body),'id':response.json()['data']['id']})
            self.send_response(response.status_code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(response.content)
    class Bridge(ThreadingHTTPServer):request_queue_size=128
    server=Bridge(('127.0.0.1',0),Handler);worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    repo=Path(__file__).resolve().parents[3];e=Path(os.environ.get('SALES_TEST_EVIDENCE_DIR',str(repo/'.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-13-fix1-evidence')))/phase
    e.mkdir(parents=True,exist_ok=True)
    pnpm=['node',os.environ['SALES_PNPM_CJS']] if os.environ.get('SALES_PNPM_CJS') else ['corepack','pnpm']
    config={'url':f'http://127.0.0.1:{server.server_port}','workspace':str(c['workspace']),'project':str(c['project']),'thread':thread['id'],'buyer':native['buyer_id'],'profile':str(profile),'run':str(c['run'])}
    path=e/'owned-browser.json';path.write_text(json.dumps(config),encoding='utf-8')
    env={k:v for k,v in os.environ.items() if not k.startswith('BUYEROS_') and k!='NEXT_PUBLIC_CONVERSATION_HOME'};env['TASK13_OWNED_CONFIG']=str(path);env['TASK13_OWNED_PHASE']=phase
    try:
        if phase in {'sources','retry'}:
            with (e/'owned-browser.log').open('w',encoding='utf-8') as log:
                result=subprocess.run([*pnpm,'exec','playwright','test','--config','playwright.sales-skills.config.ts','--grep','fix1 owned qualification'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
            assert result.returncode==0,(e/'owned-browser.log').read_text(encoding='utf-8')
            if phase=='sources':return
            assert len(state['starts'])==2 and state['starts'][0]==state['starts'][1]
            with psycopg.connect(c['dsn']) as db:
                assert db.execute('SELECT count(*) FROM search_runs WHERE id=%s',(state['starts'][0]['id'],)).fetchone()[0]==1
            (e/'native-start-replay.json').write_text(json.dumps(state['starts'],indent=2),encoding='utf-8')
            return
        state['deny']=False
        with psycopg.connect(c['dsn']) as db:
            version=db.execute('SELECT version FROM search_runs WHERE id=%s',(c['run'],)).fetchone()[0]
        refs=[{'id':str(c['run']),'kind':'run','version':version,'locator':f'run:{c["run"]}','retention_class':'durable'}]
        task=new_task(client,'sales-research',{'research_question':'Owned capability recovery'},refs)
        prepared=client.post(SALES_ROOT+'/'+task['id']+'/core-preparation',headers=headers(version=task['revision']))
        assert prepared.status_code==200,prepared.text
        config['output']=prepared.json()['data']['id'];config['outputKind']=prepared.json()['data']['kind']
        path.write_text(json.dumps(config),encoding='utf-8');env['TASK13_FULL_SHELL']='1'
        with (e/'owned-capability-browser.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([*pnpm,'exec','playwright','test','--config','playwright.sales-skills.config.ts','--grep','fix1 owned capability'],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        assert result.returncode==0,(e/'owned-capability-browser.log').read_text(encoding='utf-8')

    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
        client.__exit__(None,None,None)
        with psycopg.connect(c['dsn']) as db:
            db.execute("UPDATE sales_tasks SET state='cancelled'")
            db.execute('DELETE FROM conversation_threads')
