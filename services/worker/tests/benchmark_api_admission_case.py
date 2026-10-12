"""Opt-in actual owned RS256/ASGI/RLS admission and two-worker mixed burst."""
import asyncio,hashlib,importlib.util,json,os,subprocess,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
import psycopg
import redis
from celery import Celery
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine
from buyeros_api.api import auth
from buyeros_api.api.app import create_app
from buyeros_api.api.jwks import JwksKeyCache
from buyeros_api.api.verifier import TokenVerifier
from buyeros_api.settings import get_settings
from buyeros_api.execution.dispatcher import dispatch_cycle
from buyeros_api.execution.handlers.retention import expire_due_sources

ROOT=Path(__file__).resolve().parents[3];WORKER=ROOT/'services/worker'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

fx=module('admission_auth_fixtures',ROOT/'services/api/tests/auth_fixtures.py')

def runtime_role_dsn(dsn):return dsn.replace('buyeros:buyeros@','buyeros_api:test-only@',1)


def test_owned_api_admission_tenant_pairs_and_mixed_distribution(migrated,pg_dsn,monkeypatch):
    seeded=pg_dsn
    folder=Path(os.environ['BUYEROS_ADMISSION_OUTPUT']);(folder/'events').mkdir();(folder/'samples').mkdir()
    assert os.environ.get('BUYEROS_OWNED_API_ADMISSION')=='1'
    reader=module('rss',WORKER/'tests/worker_capacity_driver.py')
    guard=module('admission',WORKER/'tests/api_admission_driver.py')
    cleanup=module('cleanup',WORKER/'tests/mixed_workload_cleanup.py')
    worker_python=WORKER/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    with psycopg.connect(seeded) as db:
        db.execute("ALTER ROLE buyeros_api LOGIN PASSWORD 'test-only'")
        db.execute("ALTER ROLE buyeros_worker LOGIN PASSWORD 'test-only-worker'")
        db.execute("INSERT INTO worker_runtime_control(singleton,backend,enabled,epoch) VALUES(1,'celery',true,1) ON CONFLICT(singleton) DO UPDATE SET backend='celery',enabled=true,epoch=1")
    worker_dsn=seeded.replace('buyeros:buyeros@','buyeros_worker:test-only-worker@',1)
    env=dict(os.environ,BUYEROS_TEST_DATABASE_URL=seeded,BUYEROS_DATABASE_URL=worker_dsn,BUYEROS_OWNED_API_ADMISSION='1',BUYEROS_PAID_DISPATCH_ENABLED='false',BUYEROS_DELIVERY_DISPATCH_ENABLED='false',PYTHONUTF8='1')
    seeded_holds=subprocess.run([str(worker_python),'-m','tests.api_admission_seed'],cwd=WORKER,env=env,capture_output=True,timeout=60)
    assert seeded_holds.returncode==0,seeded_holds.stderr.decode('utf-8',errors='replace')
    held_job=json.loads(seeded_holds.stdout)['job_id']
    members=[dict(workspace=str(uuid.uuid4()),project=str(uuid.uuid4()),actor=str(uuid.uuid4()),membership=str(uuid.uuid4()),subject='admission|'+str(uuid.uuid4())) for _ in range(10)]
    with psycopg.connect(seeded) as db:
        for m in members:
            db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES(%s,'Owned admission','live')",(m['workspace'],))
            db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES(%s,%s,'Admission','Fictional','Nonpaid fixture','{US}','{en}',1)",(m['project'],m['workspace']))
            db.execute('INSERT INTO users(id,issuer,subject) VALUES(%s,%s,%s)',(m['actor'],fx.ISSUER,m['subject']))
            db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES(%s,%s,%s,'{workspace_admin}',true)",(m['membership'],m['workspace'],m['actor']))
    monkeypatch.setenv('BUYEROS_DATABASE_URL',runtime_role_dsn(seeded));monkeypatch.setenv('BUYEROS_AUTH0_ISSUER',fx.ISSUER);monkeypatch.setenv('BUYEROS_AUTH0_AUDIENCE',fx.AUDIENCE)
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','false');monkeypatch.setenv('BUYEROS_DELIVERY_DISPATCH_ENABLED','false');get_settings.cache_clear()
    cache=JwksKeyCache(lambda:asyncio.sleep(0,result=fx.jwks_document()),cache_seconds=300)
    monkeypatch.setattr(auth,'_verifier_from_settings',lambda:TokenVerifier(cache,issuer=fx.ISSUER,audience=fx.AUDIENCE))
    def role(dsn):
        with psycopg.connect(dsn) as db:
            x=db.execute("SELECT r.rolsuper,r.rolbypassrls,c.relrowsecurity,current_user=pg_get_userbyid(c.relowner) FROM pg_roles r CROSS JOIN pg_class c WHERE r.rolname=current_user AND c.oid='outbox_events'::regclass").fetchone()
        return dict(superuser=x[0],bypass=x[1],rls=x[2],owner=x[3])
    def holds():
        with psycopg.connect(seeded) as db:
            ops=db.execute('SELECT id,intent_key,status,provider_ref,input_hash FROM provider_operations WHERE job_id=%s ORDER BY id',(held_job,)).fetchall()
            h=db.execute('SELECT id,state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(held_job,)).fetchone()
            costs=db.execute('SELECT id,amount FROM cost_events WHERE operation_id=%s',(held_job,)).fetchall()
        return dict(operations=[dict(id=str(i),intent=k,status=s,ref=ref,input_hash=d) for i,k,s,ref,d in ops],reservation=dict(id=str(h[0]),state=h[1],remaining=str(h[2])),costs=[dict(id=str(i),amount=str(a)) for i,a in costs])
    baseline=holds();processes=[];ownership=[];requests=[];pairs=[];bulk=[];sources=[];pubs=[];samples=[];terminal=[];buyers=[]
    publisher=Celery('owned-admission',broker=os.environ['BUYEROS_ADMISSION_BROKER_URL']);broker=redis.Redis.from_url(os.environ['BUYEROS_ADMISSION_BROKER_URL'],socket_timeout=3)
    complete=False;error=None;api_role=role(runtime_role_dsn(seeded));worker_role=role(worker_dsn)
    def events():return sorted([json.loads(p.read_text(encoding='utf-8')) for p in (folder/'events').glob('*.json')],key=lambda x:x['at_ns'])
    def sample():
        resources=[];reader.sample_worker_resources(processes,0,resources)
        with psycopg.connect(seeded) as db:
            rows=db.execute('SELECT workspace_id,state,count(*) FROM outbox_events WHERE workspace_id=ANY(%s::uuid[]) GROUP BY workspace_id,state',([m['workspace'] for m in members],)).fetchall()
        spaces=[dict(workspace=m['workspace'],ready=0,dispatched=0,done=0) for m in members]
        for w,state,count in rows:next(x for x in spaces if x['workspace']==str(w))[state]=count
        with broker.pipeline(transaction=True) as pipe:q,u=pipe.lrange('celery',0,-1).hvals('unacked').execute()
        qids=[json.loads(x)['headers']['id'] for x in q];uids=[json.loads(x)[0]['headers']['id'] for x in u]
        snap=dict(at_ns=time.monotonic_ns(),spaces=spaces,resources=resources,holds=holds(),broker=dict(queued=len(qids),unacked=len(uids),queued_task_ids=qids,unacked_task_ids=uids));samples.append(snap)
        assert snap['holds']==baseline
        (folder/'samples'/f'{len(samples):04d}.json').write_text(json.dumps(snap)+'\n',encoding='utf-8')
    def state(m):
        with psycopg.connect(seeded) as db:
            manifest=db.execute('SELECT id,status,version FROM bulk_manifests WHERE project_id=%s ORDER BY id',(m['project'],)).fetchall()
            jobs=db.execute('SELECT id,status,processed FROM async_jobs WHERE project_id=%s ORDER BY id',(m['project'],)).fetchall()
            outbox=db.execute('SELECT id,state FROM outbox_events WHERE workspace_id=%s ORDER BY id',(m['workspace'],)).fetchall()
            keys=db.execute('SELECT id FROM idempotency_records WHERE workspace_id=%s ORDER BY id',(m['workspace'],)).fetchall()
        return json.loads(json.dumps(dict(manifests=manifest,jobs=jobs,outbox=outbox,idempotency=keys),default=str))
    def request(client,wave,m,stage,path,body,actor=None,version=None):
        actor=actor or m;key=str(uuid.uuid4());headers={'Authorization':'Bearer '+fx.make_token(sub=actor['subject']),'Idempotency-Key':key}
        if version is not None:headers['If-Match']=f'"{version}"'
        started=time.monotonic_ns();response=client.post(path,json=body,headers=headers);returned=time.monotonic_ns();data=response.json()
        row=dict(id=str(uuid.uuid4()),request_id=data.get('request_id'),header_request_id=response.headers.get('x-request-id'),wave=wave,workspace=m['workspace'],project=m['project'],actor=actor['actor'],method='POST',path=path,stage=stage,status=response.status_code,code=data.get('code'),body_hash=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest(),key=key,if_match=headers.get('If-Match'),started_ns=started,returned_ns=returned,body=body,response=data,etag=response.headers.get('etag'))
        requests.append(row);(folder/'requests').mkdir(exist_ok=True);(folder/'requests'/(row['id']+'.json')).write_text(json.dumps(row)+'\n',encoding='utf-8');return row
    try:
        for ordinal in [1,2]:
            child_env=dict(env,BUYEROS_BROKER_URL=os.environ['BUYEROS_ADMISSION_BROKER_URL'],BUYEROS_EAGER='false',BUYEROS_OWNED_MIXED_FIXTURE='1',BUYEROS_MIXED_OUTPUT=str(folder),BUYEROS_MIXED_WORKER=str(ordinal))
            with (folder/f'worker-{ordinal}.log').open('xb') as log:p=subprocess.Popen([str(worker_python),'-m','tests.mixed_workload_fixture'],cwd=WORKER,env=child_env,stdout=log,stderr=subprocess.STDOUT)
            processes.append(p);deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                ready=next((e for e in events() if e['stage']=='ready' and e['ordinal']==ordinal),None)
                if ready:
                    tree=[pid for pid,_,_ in reader._owned_process_tree(p.pid)];assert ready['pid'] in tree;ownership.append(dict(popen_pid=p.pid,tree_pids=tree));break
                assert p.poll() is None;time.sleep(.1)
            else:raise AssertionError('owned worker startup deadline')
        sample()
        with TestClient(create_app(),raise_server_exceptions=False) as client:
            for wave in range(3):
                for ordinal,m in enumerate(members):
                    count=303 if ordinal==0 else 101;prefix=f"Admission-{wave}-{ordinal}-"
                    with psycopg.connect(seeded) as db:
                        companies=db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) SELECT gen_random_uuid(),%s,%s||i,%s||i FROM generate_series(1,%s) i RETURNING id",(m['workspace'],prefix,prefix,count)).fetchall()
                        ids=[str(uuid.uuid4()) for _ in companies]
                        db.cursor().executemany('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',[(b,m['workspace'],m['project'],str(c[0])) for b,c in zip(ids,companies)])
                    path=f"/v1/workspaces/{m['workspace']}/projects/{m['project']}/bulk-manifests";body=dict(filters={'q':prefix},excluded_ids=[],operation='assignBuyerOwners',target={'owner_membership_id':m['membership']},reason='Owned API mixed admission')
                    denials=[]
                    if wave==0:
                        before=state(m);d=request(client,wave,m,'preview',path,body,actor=members[(ordinal+1)%10]);denials.append(dict(kind='foreign_preview',denied_id=d['id'],before=before,after=state(m)));assert d['status']==404,d['response']
                    preview=request(client,wave,m,'preview',path,body);assert preview['status']==201,preview['response'];manifest=preview['response']['data'];assert manifest['count']==count
                    for pair in denials:pair['owned_id']=preview['id'];pairs.append(pair)
                    body=dict(digest=manifest['digest'],confirmation=True);execute_path=path+'/'+manifest['id']+'/execute';denials=[]
                    def deny(kind,actor=None,version=None):
                        before=state(m);d=request(client,wave,m,'execute',execute_path,body,actor=actor,version=manifest['version'] if version is None else version);denials.append(dict(kind=kind,denied_id=d['id'],before=before,after=state(m)))
                        expected={'foreign_execute':404,'inactive':404,'viewer':403,'stale':412}[kind];assert d['status']==expected,d['response']
                    if wave==0:deny('foreign_execute',actor=members[(ordinal+1)%10])
                    if wave==1:
                        with psycopg.connect(seeded) as db:db.execute('UPDATE memberships SET active=false WHERE id=%s',(m['membership'],))
                        try:deny('inactive')
                        finally:
                            with psycopg.connect(seeded) as db:db.execute('UPDATE memberships SET active=true WHERE id=%s',(m['membership'],))
                    if wave==2:
                        with psycopg.connect(seeded) as db:db.execute("UPDATE memberships SET roles='{viewer}' WHERE id=%s",(m['membership'],))
                        try:deny('viewer')
                        finally:
                            with psycopg.connect(seeded) as db:db.execute("UPDATE memberships SET roles='{workspace_admin}' WHERE id=%s",(m['membership'],))
                        deny('stale',version=999)
                    accepted=request(client,wave,m,'execute',execute_path,body,version=manifest['version']);assert accepted['status']==202,accepted['response']
                    for pair in denials:pair['owned_id']=accepted['id'];pairs.append(pair)
                    bulk.append(dict(wave=wave,workspace=m['workspace'],project=m['project'],actor=m['actor'],preview_id=preview['id'],execute_id=accepted['id'],manifest_id=manifest['id'],digest=manifest['digest'],job_id=accepted['response']['data']['id'],count=count,buyer_ids=ids))
                    with psycopg.connect(seeded) as db:
                        for _ in range(3 if ordinal==0 else 1):
                            sid=str(uuid.uuid4());db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,object_key,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,%s,%s,'private_object',%s,'owned expired',now()-interval '1 second','account_research')",(sid,m['workspace'],m['project'],'https://owned.invalid/'+sid,'a'*64,'owned/'+sid));sources.append(dict(id=sid,workspace=m['workspace'],wave=wave))
                async def drive():
                    engine=create_async_engine(worker_dsn.replace('postgresql://','postgresql+psycopg://',1));cursor=0
                    try:
                        await expire_due_sources(engine,datetime.now(timezone.utc),policy_version='owned-admission-v1',limit=100)
                        def publish(message):
                            with psycopg.connect(seeded) as db:row=db.execute('SELECT id,event_type,payload FROM outbox_events WHERE intent_key=%s',(message['intent_key'],)).fetchone()
                            task=str(uuid.uuid4());at=time.monotonic_ns();publisher.send_task('buyeros.execute_intent',args=[message['intent_key'],message['workspace_id'],message['generation']],task_id=task)
                            pubs.append(dict(intent=message['intent_key'],workspace=message['workspace_id'],wave=wave,kind=row[1],payload=row[2],outbox_id=str(row[0]),task_id=task,generation=message['generation'],at_ns=at))
                        deadline=time.monotonic()+90
                        while time.monotonic()<deadline:
                            result=await dispatch_cycle(engine,publish,'owned-admission',datetime.now(timezone.utc),max_total=50,time_budget_seconds=5,cursor=cursor);cursor=result['next_cursor'];sample()
                            with psycopg.connect(seeded) as db:pending=db.execute("SELECT count(*) FROM outbox_events WHERE workspace_id=ANY(%s::uuid[]) AND state!='done'",([m['workspace'] for m in members],)).fetchone()[0]
                            if pending==0 and broker.llen('celery')==broker.hlen('unacked')==0:break
                            await asyncio.sleep(.1)
                        else:raise AssertionError('owned admitted burst incomplete')
                    finally:await engine.dispose()
                asyncio.run(drive())
        with psycopg.connect(seeded) as db:
            rows=db.execute('SELECT id,intent_key,workspace_id,event_type,state,fencing_generation,runtime_epoch,payload FROM outbox_events WHERE workspace_id=ANY(%s::uuid[])',([m['workspace'] for m in members],)).fetchall()
            terminal=[dict(id=str(i),intent=k,workspace=str(w),kind=t,state=s,generation=g,epoch=e,payload=p) for i,k,w,t,s,g,e,p in rows]
            for b in bulk:
                x=db.execute('SELECT status,processed,updated,conflicts,blocked FROM async_jobs WHERE id=%s',(b['job_id'],)).fetchone();b.update(zip(['status','processed','updated','conflicts','blocked'],x))
                b['outbox_ids']=[str(x[0]) for x in db.execute("SELECT id FROM outbox_events WHERE payload->>'job_id'=%s ORDER BY created_at,id",(b['job_id'],)).fetchall()]
                items=db.execute('SELECT b.id,b.workspace_id,i.status,b.version,b.owner_user_id FROM async_job_items i JOIN project_buyers b ON b.id=i.buyer_id WHERE i.job_id=%s',(b['job_id'],)).fetchall();buyers.extend(dict(id=str(i),workspace=str(w),job_id=b['job_id'],status=s,version=v,owner=str(o)) for i,w,s,v,o in items)
            for s in sources:
                key,excerpt,url=db.execute('SELECT object_key,excerpt,canonical_url FROM source_documents WHERE id=%s',(s['id'],)).fetchone();oid=db.execute("SELECT id FROM outbox_events WHERE payload->>'source_document_id'=%s",(s['id'],)).fetchone()[0];s.update(outbox_id=str(oid),object_key=key,excerpt=excerpt,tombstoned=url.startswith('https://redacted.invalid/'))
        sample();complete=True
    except Exception as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        raw=events();capture=dict(schema='buyeros.owned-api-admission.v1',complete=complete,error=error,live_verified=False,release_accepted=False,paid_enabled=False,delivery_enabled=False,provider_calls=sum(e['stage']=='forbidden_provider_call' for e in raw),send_calls=0,auth_method='real_RS256_local_JWKS',members=members,workers=ownership,api_role=api_role,worker_role=worker_role,requests=requests,denial_pairs=pairs,bulk=bulk,sources=sources,publications=pubs,events=raw,terminal=terminal,buyers=buyers,baseline_holds=baseline,samples=samples)
        def stop(p):
            if p.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10)
                else:p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=10)
        cleanup.capture_then_cleanup(folder,capture,[*[lambda p=p:stop(p) for p in processes],publisher.close,broker.close,get_settings.cache_clear])
    assert guard.capture_complete(capture),'API admission denominator refused; all raw attempts retained'
