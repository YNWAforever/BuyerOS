"""Opt-in1800s nonpaid mixed load:10 tenants, real broker/task/DB, no external IO."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from celery import Celery
import psycopg
import redis

from buyeros_worker.dispatcher import dispatch_cycle
from buyeros_worker.engine import create_engine
from tests.conftest import WS_A, WS_B, PROJECT_A, seed_outbox
from tests.test_contact_uncertainty_db import _setup
from tests.test_valkey_integration import _valkey_container
from tests.worker_capacity_driver import sample_worker_resources, _owned_process_tree
from tests.mixed_workload_driver import DURATION_NS, INTERVAL_NS, WAVES, workload_complete
from tests.mixed_workload_cleanup import capture_then_cleanup


def test_owned_ten_workspaces_thirty_minute_mixed_nonpaid(worker_database_url, pg_dsn, monkeypatch):
    folder = Path(os.environ['BUYEROS_MIXED_OUTPUT'])
    (folder/'events').mkdir()
    (folder/'samples').mkdir()
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED', 'false')
    monkeypatch.setenv('BUYEROS_DELIVERY_DISPATCH_ENABLED', 'false')
    from buyeros_worker.config import get_settings
    get_settings.cache_clear()
    spaces = [WS_A, WS_B, *[str(uuid.uuid4()) for _ in range(8)]]
    projects = [PROJECT_A, *[str(uuid.uuid4()) for _ in range(9)]]
    members = [dict(workspace=w, id=str(uuid.uuid4()), user=str(uuid.uuid4()), active=True) for w in spaces]
    prefix = 'mixed:'+uuid.uuid4().hex+':'
    workers=[]; ownership=[]; observations=[]; publications=[]; samples=[]; cycles=[]
    container=publisher=client=None; start=end=None; error=None; complete=False
    terminal=[]; durable=[]; baseline=None; role=None; job=None

    def events():
        return sorted([json.loads(p.read_text(encoding='utf-8')) for p in (folder/'events').glob('*.json')], key=lambda e:e['at_ns'])

    def holds(db):
        ops=db.execute('SELECT id,intent_key,status,provider_ref,input_hash FROM provider_operations WHERE job_id=%s ORDER BY id', (job,)).fetchall()
        res=db.execute('SELECT id,state,remaining_hold FROM budget_reservations WHERE operation_id=%s', (job,)).fetchone()
        costs=db.execute('SELECT id,amount FROM cost_events WHERE operation_id=%s ORDER BY id', (job,)).fetchall()
        return dict(operations=[dict(id=str(i),intent=k,status=s,ref=ref,input_hash=h) for i,k,s,ref,h in ops],
                    reservation=dict(id=str(res[0]),state=res[1],remaining=str(res[2])), costs=[dict(id=str(i),amount=str(a)) for i,a in costs])

    def start_worker():
        ordinal=len(workers)+1
        env=dict(os.environ); env.pop('PYTEST_ADDOPTS',None)
        env.update(BUYEROS_BROKER_URL=broker, BUYEROS_EAGER='false', BUYEROS_OWNED_MIXED_FIXTURE='1',
                   BUYEROS_MIXED_WORKER=str(ordinal), BUYEROS_PAID_DISPATCH_ENABLED='false',
                   BUYEROS_DELIVERY_DISPATCH_ENABLED='false', PYTHONUTF8='1')
        with (folder/f'worker-{ordinal}.log').open('xb') as log:
            p=subprocess.Popen([sys.executable,'-X','utf8','-m','tests.mixed_workload_fixture'],
                               cwd=Path(__file__).resolve().parents[1],env=env,stdout=log,stderr=subprocess.STDOUT)
        workers.append(p)
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            ready=next((e for e in events() if e['stage']=='ready' and e['ordinal']==ordinal),None)
            if ready:
                tree=[pid for pid,_,_ in _owned_process_tree(p.pid)]
                assert ready['pid'] in tree
                ownership.append(dict(popen_pid=p.pid, tree_pids=tree)); return
            assert p.poll() is None, 'owned worker exited before ready; raw log retained'
            time.sleep(.1)
        raise AssertionError('owned worker startup deadline')

    def seed_wave(wave):
        batch=[]
        with psycopg.connect(pg_dsn) as db:
            for ordinal,(w,project,member) in enumerate(zip(spaces,projects,members)):
                for index in range(3 if ordinal==0 else 1):
                    source=str(uuid.uuid4()); key=prefix+f'{wave}:{ordinal}:source:{index}'
                    object_key=f'tenants/{w}/{source}' if (wave+index)%2 else None
                    db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,object_key,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,%s,%s,'private_object',%s,NULL,now()-interval '1 second','account_research')", (source,w,project,'https://redacted.invalid/'+source,'a'*64,object_key))
                    outbox=str(uuid.uuid4()); seed_outbox(db,intent_key=key,workspace_id=w,event_type='source.delete',payload={'source_document_id':source},outbox_id=outbox)
                    batch.append(dict(intent=key,workspace=w,wave=wave,kind='source.delete',outbox_id=outbox,source_id=source))
                company,buyer,bulk_job,outbox=(str(uuid.uuid4()) for _ in range(4)); key=prefix+f'{wave}:{ordinal}:bulk'
                db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fictional mixed','Fictional mixed')",(company,w))
                db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(buyer,w,project,company))
                db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,requested,status) VALUES(%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,1,'queued')",(bulk_job,w,project,member['user'],json.dumps(dict(owner_membership_id=member['id'],reason='Owned mixed fixture assignment'))))
                db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) VALUES(%s,%s,%s,%s,0,1,'pending')",(str(uuid.uuid4()),w,bulk_job,buyer))
                seed_outbox(db,intent_key=key,workspace_id=w,event_type='bulk.mutate',payload={'job_id':bulk_job},outbox_id=outbox)
                batch.append(dict(intent=key,workspace=w,wave=wave,kind='bulk.mutate',outbox_id=outbox,job_id=bulk_job,buyer_id=buyer))
        at=time.monotonic_ns()
        for row in batch: row['created_ns']=at
        observations.extend(batch)

    def sample():
        resources=[]; sample_worker_resources(workers,0,resources)
        with psycopg.connect(pg_dsn) as db:
            raw=db.execute('SELECT workspace_id,state,count(*),EXTRACT(EPOCH FROM(now()-min(created_at))) FROM outbox_events WHERE intent_key LIKE %s GROUP BY workspace_id,state',(prefix+'%',)).fetchall()
            retained=holds(db)
        queues=[dict(workspace=w,ready=0,dispatched=0,done=0,failed=0,blocked=0,oldest_ready_seconds=None,oldest_dispatched_seconds=None) for w in spaces]
        for w,state,count,age in raw:
            q=next(q for q in queues if q['workspace']==str(w)); q[state]=count
            if state in ('ready','dispatched'): q['oldest_'+state+'_seconds']=float(age)
        # One broker transaction binds counters to the same list/hash read.
        with client.pipeline(transaction=True) as pipe:
            queued,unacked=pipe.lrange('celery',0,-1).hvals('unacked').execute()
        queued_ids=[json.loads(value)['headers']['id'] for value in queued]
        unacked_ids=[json.loads(value)[0]['headers']['id'] for value in unacked]
        snap=dict(at_ns=time.monotonic_ns(),spaces=queues,broker=dict(queued=len(queued_ids),unacked=len(unacked_ids),queued_task_ids=queued_ids,unacked_task_ids=unacked_ids),holds=retained,resources=resources)
        samples.append(snap)
        path=folder/'samples'/f'{len(samples):04d}.json'
        with path.open('x',encoding='utf-8') as f: json.dump(snap,f,allow_nan=False);f.write('\n')
        assert retained==baseline, 'original unknown/accepted liability changed during nonpaid load'
        assert all(p.poll() is None for p in workers), 'owned worker exited during sustained capture'

    try:
        with psycopg.connect(worker_database_url) as db:
            r=db.execute("SELECT current_user,r.rolsuper,r.rolbypassrls,pg_get_userbyid(c.relowner),c.relrowsecurity FROM pg_roles r CROSS JOIN pg_class c WHERE r.rolname=current_user AND c.oid='outbox_events'::regclass").fetchone()
        role=dict(name=r[0],superuser=r[1],bypass=r[2],owner=r[3],rls=r[4])
        assert role['superuser'] is role['bypass'] is False and role['rls'] is True and role['name']!=role['owner']
        # Owned seed only; no submit is used to create these retained liabilities.
        job,_=_setup(pg_dsn,count=2)
        with psycopg.connect(pg_dsn) as db:
            ops=db.execute('SELECT id FROM provider_operations WHERE job_id=%s ORDER BY id',(job,)).fetchall()
            db.execute("UPDATE provider_operations SET status='unknown',provider_ref=NULL WHERE id=%s",(ops[0][0],))
            db.execute("UPDATE provider_operations SET status='accepted',provider_ref='fixture-retained-accepted' WHERE id=%s",(ops[1][0],))
            db.execute("UPDATE outbox_events SET state='done' WHERE intent_key=%s",('contact.lookup:'+str(job),))
            for w in spaces[2:]: db.execute("INSERT INTO workspaces(id,name,data_mode) VALUES(%s,'Owned mixed','live')",(w,))
            for w,p in zip(spaces[1:],projects[1:]):
                db.execute("INSERT INTO projects(id,workspace_id,name,company_name,offer,markets,language_preferences,version) VALUES(%s,%s,'Mixed','Fictional','Nonpaid fixture','{US}','{en}',1)",(p,w))
            for m in members:
                db.execute("INSERT INTO users(id,issuer,subject) VALUES(%s,'https://fixture.invalid/',%s)",(m['user'],'mixed|'+m['user']))
                db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES(%s,%s,%s,'{workspace_admin}',true)",(m['id'],m['workspace'],m['user']))
            baseline=holds(db)
        container=_valkey_container()
        mapping=subprocess.check_output(['docker','port',container,'6379'],text=True).strip().splitlines()[0]
        broker='redis://127.0.0.1:'+mapping.rsplit(':',1)[1]+'/0'
        publisher=Celery('owned-mixed-publisher',broker=broker);client=redis.Redis.from_url(broker,socket_timeout=3)
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            try: client.ping(); break
            except redis.ConnectionError: time.sleep(.1)
        else: raise AssertionError('owned broker startup deadline')
        start_worker();start_worker()

        def publish(message):
            row=next(x for x in observations if x['intent']==message['intent_key'])
            assert not any(p['intent']==row['intent'] for p in publications)
            task_id=str(uuid.uuid4()); at=time.monotonic_ns()
            publisher.send_task('buyeros.execute_intent',args=[row['intent'],row['workspace'],message['generation']],task_id=task_id)
            publications.append(dict(intent=row['intent'],workspace=row['workspace'],generation=message['generation'],task_id=task_id,at_ns=at))

        async def sustain():
            nonlocal start,end
            engine=create_engine();cursor=0;wave=0;next_sample=0
            start=time.monotonic_ns()
            try:
                sample()
                while time.monotonic_ns()-start < DURATION_NS:
                    elapsed=time.monotonic_ns()-start
                    if wave<WAVES and elapsed>=wave*INTERVAL_NS:
                        assert elapsed< wave*INTERVAL_NS+15_000_000_000, 'wave missed; do not compress workload'
                        seed_wave(wave);wave+=1
                    if len(publications)<len(observations):
                        result=await dispatch_cycle(engine,publish,'owned-mixed',datetime.now(timezone.utc),max_total=50,time_budget_seconds=5,cursor=cursor)
                        cursor=result['next_cursor']; cycles.append(result)
                    if elapsed>=next_sample:
                        sample();next_sample+=10_000_000_000
                    await asyncio.sleep(.2)
                assert wave==60 and len(publications)==1320
                deadline=time.monotonic()+60
                while time.monotonic()<deadline:
                    with psycopg.connect(pg_dsn) as db:
                        pending=db.execute("SELECT count(*) FROM outbox_events WHERE intent_key LIKE %s AND state!='done'",(prefix+'%',)).fetchone()[0]
                    if pending==0 and client.llen('celery')==client.hlen('unacked')==0: break
                    await asyncio.sleep(.2)
                else: raise AssertionError('sustained workload incomplete; denominator retained')
                sample(); end=time.monotonic_ns()
            finally: await engine.dispose()

        asyncio.run(sustain())
        raw_events=events();pubs={p['intent']:p for p in publications}
        with psycopg.connect(pg_dsn) as db:
            final=db.execute('SELECT id,intent_key,workspace_id,event_type,state,fencing_generation,runtime_epoch FROM outbox_events WHERE intent_key LIKE %s',(prefix+'%',)).fetchall()
            terminal=[dict(id=str(i),intent=k,workspace=str(w),kind=t,state=s,generation=g,epoch=e) for i,k,w,t,s,g,e in final]
            for row in observations:
                p=pubs[row['intent']]
                starts=[e for e in raw_events if e['stage']=='started' and e['task_id']==p['task_id']]
                returns=[e for e in raw_events if e['stage']=='return' and e['task_id']==p['task_id']]
                assert len(starts)==len(returns)==1
                a,b=starts[0],returns[0];out=next(x for x in terminal if x['intent']==row['intent'])
                if row['kind']=='source.delete':
                    stored=db.execute('SELECT object_key FROM source_documents WHERE id=%s',(row['source_id'],)).fetchone()
                    result=dict(intent=row['intent'],kind=row['kind'],object_key=stored[0])
                else:
                    stored=db.execute('SELECT j.status,j.processed,j.updated,j.blocked,b.owner_user_id,b.version FROM async_jobs j JOIN project_buyers b ON b.id=%s WHERE j.id=%s',(row['buyer_id'],row['job_id'])).fetchone()
                    result=dict(intent=row['intent'],kind=row['kind'],status=stored[0],processed=stored[1],updated=stored[2],blocked=stored[3],owner=str(stored[4]),version=stored[5])
                durable.append(result)
                row.update(task_id=p['task_id'],generation=p['generation'],publish_ns=p['at_ns'],start_ns=a['at_ns'],return_ns=b['at_ns'],worker_pid=a['pid'],outcome=b['outcome'],state=out['state'],queue_wait_ns=a['at_ns']-p['at_ns'],execution_ns=b['at_ns']-a['at_ns'],durable_ok=True)
        complete=True
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc); raise
    finally:
        end=end or time.monotonic_ns()
        raw_events=events()
        capture=dict(schema='buyeros.owned-mixed-workload.v1',complete=complete,error=error,
                     live_verified=False,release_accepted=False,paid_enabled=False,
                     start_ns=start,end_ns=end,workspaces=spaces,memberships=members,role=role,
                     owned_workers=ownership,baseline_holds=baseline,provider_calls=sum(e['stage']=='forbidden_provider_call' for e in raw_events),send_calls=0,
                     observations=observations,publications=publications,events=raw_events,terminal=terminal,durable=durable,samples=samples,dispatcher_cycles=cycles,
                     method='actual monotonic1800s/60waves;publisher send begin to worker task-entry wait includes producer enqueue overhead;execution includes committed task body;10s SQL created-at age/state and broker counts/RSS samples are separate, not queue latency or all-time peak/PSS/cgroup;bulk seed bypasses API admission;private delete IO synthetic;no adopted resource/queue/fleet SLO;no HK/field/provider/UAT acceptance')
        def stop_worker(p):
            if p.poll() is None:
                if os.name=='nt': subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10)
                else: p.terminate()
                try: p.wait(timeout=10)
                except subprocess.TimeoutExpired: p.kill();p.wait(timeout=10)
        actions=[lambda p=p:stop_worker(p) for p in workers]
        if publisher: actions.append(publisher.close)
        if client: actions.append(client.close)
        if container: actions.append(lambda:subprocess.run(['docker','rm','-f',container],capture_output=True,timeout=20,check=True))
        # PG fixture owns and drops its entire disposable database/container.
        # Never mutate or release the seeded liabilities during cleanup.
        actions.append(get_settings.cache_clear)
        capture_then_cleanup(folder,capture,actions)
    assert workload_complete(capture), 'strict sustained denominator refused; all raw evidence retained'
