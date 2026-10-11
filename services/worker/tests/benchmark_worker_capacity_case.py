"""Opt-in nonpaid tombstone backlog; real broker and two separate workers."""
import asyncio,json,os,platform,subprocess,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
import psycopg
from buyeros_worker.app import celery_app
from buyeros_worker.dispatcher import dispatch_cycle
from buyeros_worker.engine import create_engine
from buyeros_worker.tasks import publish_message
from tests.conftest import WS_A,WS_B,PROJECT_A,API_ROLE,seed_outbox
from tests.test_valkey_integration import _valkey_container
from tests.worker_capacity_driver import collect_bounded_backlog

def test_owned_backlog_rotation_and_worker_restart(worker_database_url,pg_dsn,monkeypatch):
    output=Path(os.environ['BUYEROS_WORKER_CAPACITY_OUTPUT']);assert not output.exists()
    nonce=os.environ['BUYEROS_WORKER_CAPACITY_NONCE'];prefix='c61capacity:'+nonce+':'
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','false')
    from buyeros_worker.config import get_settings
    get_settings.cache_clear()
    third=str(uuid.uuid4());workspaces=[WS_A,WS_B,third];backlogs=[25,3,1]
    projects=[PROJECT_A,str(uuid.uuid4()),str(uuid.uuid4())]
    sources=[];intents={};published={};observed_done={};cycles=[];snapshots=[];workers=[];logs=[]
    original=celery_app.conf.broker_url;name=None;started=time.monotonic();ready=None;error=None
    def snapshot():
        with psycopg.connect(pg_dsn) as db:
            rows=db.execute('SELECT workspace_id,state,count(*),EXTRACT(EPOCH FROM (now()-min(created_at))) FROM outbox_events WHERE intent_key LIKE %s GROUP BY workspace_id,state',(prefix+'%',)).fetchall()
        return {'at_seconds':time.monotonic()-started,'rows':[dict(workspace=str(w),state=s,count=n,oldest_age_seconds=float(a)) for w,s,n,a in rows]}
    def start_worker(broker):
        env=os.environ.copy();env.update(BUYEROS_BROKER_URL=broker,BUYEROS_EAGER='false',BUYEROS_PAID_DISPATCH_ENABLED='false')
        path=output.with_name(output.stem+f'-worker-{len(workers)+1}.log');assert not path.exists()
        with path.open('xb') as log:
            process=subprocess.Popen([sys.executable,'-m','celery','-A','buyeros_worker.tasks','worker','--pool=solo','--concurrency=1','--loglevel=WARNING','--without-gossip','--without-mingle','--without-heartbeat'],cwd=Path(__file__).resolve().parents[1],env=env,stdout=log,stderr=subprocess.STDOUT)
        workers.append(process);logs.append(path);return process
    def stop_worker(process):
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
    def wait_done(keys,process):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            with psycopg.connect(pg_dsn) as db:
                rows=db.execute('SELECT intent_key,state FROM outbox_events WHERE intent_key LIKE %s',(prefix+'%',)).fetchall()
            now=time.monotonic()
            for key,state in rows:
                if state=='done':observed_done.setdefault(key,now)
            if set(keys)<=set(observed_done):return
            assert process.poll() is None,'owned worker exited; see own log'
            time.sleep(.2)
        raise AssertionError('owned worker backlog timeout; incomplete observations retained')
    try:
        with psycopg.connect(worker_database_url) as db:
            role=db.execute("SELECT current_user,r.rolsuper,r.rolbypassrls,pg_get_userbyid(c.relowner),c.relrowsecurity FROM pg_roles r CROSS JOIN pg_class c WHERE r.rolname=current_user AND c.oid='outbox_events'::regclass").fetchone()
        assert role[0]==API_ROLE and role[1] is role[2] is False and role[3]!=role[0] and role[4] is True
        with psycopg.connect(pg_dsn,autocommit=True) as db:
            schema_head=db.execute('SELECT version_num FROM alembic_version').fetchone()[0]
            db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES(%s,'Owned capacity C','live')",(third,))
            for w,project in zip(workspaces[1:],projects[1:]):
                db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES(%s,%s,'Capacity','Fictional','Tombstone only','{US}','{en}',1)",(project,w))
            for tenant,(workspace,project,count) in enumerate(zip(workspaces,projects,backlogs)):
                for index in range(count):
                    source=str(uuid.uuid4());sources.append(source);key=prefix+f'{tenant}:{index}';intents[key]=workspace
                    db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,object_key,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,%s,%s,'private_object',NULL,NULL,now()-interval '1 second','account_research')",(source,workspace,project,'https://redacted.invalid/'+source,'a'*64))
                    seed_outbox(db,intent_key=key,event_type='source.delete',payload={'source_document_id':source},workspace_id=workspace)
            ready=time.monotonic();db.execute('UPDATE outbox_events SET created_at=now() WHERE intent_key LIKE %s',(prefix+'%',))
        name=_valkey_container();mapping=subprocess.run(['docker','port',name,'6379'],check=True,capture_output=True,text=True).stdout.strip().splitlines()[0];broker='redis://127.0.0.1:'+mapping.rsplit(':',1)[1]+'/0';celery_app.conf.broker_url=broker
        for _ in range(15):
            try:
                with celery_app.connection() as connection:connection.ensure_connection(max_retries=1)
            except Exception:time.sleep(.2)
            else:break
        else:raise AssertionError('owned Valkey unavailable')
        def publish(message):
            assert message['intent_key'] in intents
            publish_message(message);assert message['intent_key'] not in published
            published[message['intent_key']]=dict(at_seconds=time.monotonic()-ready,workspace=message['workspace_id'],generation=message['generation'])
        async def dispatch(cursor):
            engine=create_engine()
            try:return await dispatch_cycle(engine,publish,'owned-'+nonce,datetime.now(timezone.utc),max_total=3,time_budget_seconds=5,cursor=cursor)
            finally:await engine.dispose()
        snapshots.append(snapshot());first=start_worker(broker)
        result=asyncio.run(dispatch(0));cycles.append(result)
        assert len(result['published'])==3 and {intents[k] for k in result['published']}==set(workspaces)
        wait_done(result['published'],first);stop_worker(first);snapshots.append(snapshot())
        cursor=result['next_cursor']
        asyncio.run(collect_bounded_backlog(dispatch,published,len(intents),cursor,cycles,max_cycles=2*len(intents)))
        snapshots.append(snapshot());second=start_worker(broker)
        assert second.pid!=first.pid
        wait_done(intents,second);snapshots.append(snapshot())
        with psycopg.connect(pg_dsn) as db:
            terminal=db.execute('SELECT state,fencing_generation,count(*) FROM outbox_events WHERE intent_key LIKE %s GROUP BY state,fencing_generation',(prefix+'%',)).fetchall()
        assert terminal==[('done',1,29)] and len(observed_done)==len(published)==29
        assert all(k in published for k in observed_done)
    except Exception as exc:
        error=type(exc).__name__;raise
    finally:
        for worker in workers:stop_worker(worker)
        if ready is not None:
            report=dict(schema='buyeros.worker-capacity.v1',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),evidence_mode='owned_disposable_fixture',live_verified=False,release_accepted=False,complete=error is None and len(observed_done)==29,error=error,
                environment=dict(os=platform.platform(),python=platform.python_version(),region='local loopback;notHK',database='owned PG16',broker='owned Valkey8',worker='actual separate Celery solo processes',restart='between committed first3 and remaining broker backlog;not inflight kill/redelivery',provider_calls=0,private_object_io=0,paid_dispatch_enabled=False,dispatch_time_budget_seconds=5,max_total_per_cycle=3,max_remaining_cycles=2*len(intents)),
                initial_backlogs=[dict(workspace=w,count=n) for w,n in zip(workspaces,backlogs)],schema_head=schema_head,role=dict(name=role[0],superuser=role[1],bypass_rls=role[2],outbox_owner=role[3],outbox_rls=role[4]),worker_pids=[p.pid for p in workers],dispatcher_cycles=cycles,backlog_snapshots=snapshots,
                observations=[dict(intent=key,workspace=w,published=published.get(key),done_observed_seconds=observed_done[key]-ready if key in observed_done else None,timeout_or_incomplete=key not in observed_done) for key,w in intents.items()],
                observation_method='ready-to-publish actual wall clock;ready-to-done sampled upper bound at200ms polling,includes startup/restart;no actual dequeue timestamp or oldest wait distribution inferred',seconds=time.monotonic()-started)
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open('x',encoding='utf-8') as artifact:json.dump(report,artifact,indent=2);artifact.write('\n')
        celery_app.conf.broker_url=original;get_settings.cache_clear()
        if name is not None:subprocess.run(['docker','rm','-f',name],capture_output=True,text=True,timeout=20)
        with psycopg.connect(pg_dsn,autocommit=True) as db:
            db.execute('DELETE FROM outbox_events WHERE intent_key LIKE %s',(prefix+'%',))
            db.execute('DELETE FROM source_documents WHERE id=ANY(%s)',(sources,))
            db.execute('DELETE FROM projects WHERE id=ANY(%s)',(projects[1:],))
            db.execute('DELETE FROM workspaces WHERE id=%s',(third,))
