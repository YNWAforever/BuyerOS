"""Browser bridge forwards every product request to the actual owned FastAPI app."""
import json,os,shutil,subprocess,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

def run_browser(client,config,auth):
    root=Path(__file__).resolve().parents[3]
    evidence=Path(os.environ['SALES_TEST_EVIDENCE_DIR'])/('final-'+config['phase']+'-'+str(config.get('count',0)))
    evidence.mkdir(parents=True,exist_ok=True)
    responses=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):self.forward()
        def do_POST(self):self.forward()
        def do_PUT(self):self.forward()
        def forward(self):
            body=self.rfile.read(int(self.headers.get('Content-Length','0')))
            headers={'Authorization':auth['Authorization'],**{k:v for k,v in self.headers.items() if k.lower() in {'if-match','x-buyeros-if-match','idempotency-key','content-type'}}}
            response=client.request(self.command,self.path,headers=headers,content=body or None)
            if self.command=='POST':responses.append({'path':self.path,'status':response.status_code,'request':json.loads(body) if body else None,'response':response.json()})
            self.send_response(response.status_code);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(response.content)
    class Bridge(ThreadingHTTPServer):request_queue_size=128
    server=Bridge(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    path=evidence/'config.json';path.write_text(json.dumps({**config,'url':f'http://127.0.0.1:{server.server_port}'}),encoding='utf-8')
    env={k:v for k,v in os.environ.items() if not k.startswith('BUYEROS_') and k!='NEXT_PUBLIC_CONVERSATION_HOME'}
    env['FINAL_OWNED_CONFIG']=str(path)
    pnpm=['node',os.environ['SALES_PNPM_CJS']] if os.environ.get('SALES_PNPM_CJS') else [shutil.which('pnpm') or 'pnpm']
    try:
        with (evidence/'browser.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([*pnpm,'exec','playwright','test','--config','playwright.sales-skills.config.ts','--grep','final owned '+config['phase']],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        assert result.returncode==0,(evidence/'browser.log').read_text(encoding='utf-8')
    finally:
        (evidence/'requests.json').write_text(json.dumps(responses,indent=2),encoding='utf-8')
        server.shutdown();server.server_close();worker.join(timeout=5)
    return responses
