"""Opt-in actual Celery/Valkey crash windows with synthetic, nonbillable IO."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

import psycopg
import pytest
import redis
from celery import Celery

from buyeros_worker.dispatcher import dispatch_once, sweep_once
from buyeros_worker.engine import create_engine
from tests.conftest import WS_A, PROJECT_A, seed_outbox, reset_tenant
from tests.test_contact_uncertainty_db import _setup
from tests.test_valkey_integration import _valkey_container
from tests.worker_capacity_driver import _owned_process_tree, sample_worker_resources
from tests.broker_recovery_driver import CASES


@pytest.mark.parametrize('name', CASES)
def test_owned_broker_recovery(name, worker_database_url, pg_dsn, monkeypatch):
    folder=Path(os.environ['BUYEROS_BROKER_RECOVERY_OUTPUT'])/name
    folder.mkdir(); (folder/'events').mkdir()
    monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','true' if name in ('unknown','accepted') else 'false')
    from buyeros_worker.config import get_settings
    get_settings.cache_clear()
    workers=[]; ownership=[]; resources=[]; snapshots=[]
    started=time.monotonic(); container=None; client=None; killed=None
    broker_before=None; broker_final=None; complete=False; error=None
    job=operation=source=publisher=None
    broker_expired=None

    def events():
        return sorted([json.loads(p.read_text(encoding='utf-8')) for p in (folder/'events').glob('*.json')],key=lambda e:e['at_ns'])

    def wait(predicate, timeout=45):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            sample_worker_resources(workers,time.monotonic()-started,resources)
            result=predicate()
            if result:return result
            time.sleep(.1)
        raise AssertionError('owned recovery deadline; raw evidence retained')

    def event(stage, **fields):
        return next((e for e in events() if e['stage']==stage and all(e.get(k)==v for k,v in fields.items())),None)

    def broker_state():
        values=client.hgetall('unacked')
        ids=[json.loads(value)[0]['headers']['id'] for value in values.values()]
        return dict(unacked=sorted(ids),queued=client.llen('celery'))

    def snapshot(label):
        with psycopg.connect(pg_dsn) as db:
            row=db.execute('SELECT id,intent_key,workspace_id,state,fencing_generation,runtime_epoch,lease_expires_at,now(),attempts FROM outbox_events WHERE intent_key=%s',(key,)).fetchone()
            snap=dict(label=label,outbox=dict(id=str(row[0]),key=row[1],workspace=str(row[2]),state=row[3],generation=row[4],epoch=row[5]),lease_expires=row[6].isoformat() if row[6] else None,db_now=row[7].isoformat(),attempts=row[8])
            if job:
                op=db.execute('SELECT id,intent_key,status,provider_ref FROM provider_operations WHERE id=%s',(operation,)).fetchone()
                reservation=db.execute('SELECT id,state,remaining_hold FROM budget_reservations WHERE operation_id=%s',(job,)).fetchone()
                costs=db.execute('SELECT amount FROM cost_events WHERE operation_id=%s ORDER BY id',(job,)).fetchall()
                snap.update(provider=dict(id=str(op[0]),intent=op[1],status=op[2],ref=op[3]),reservation=dict(id=str(reservation[0]),state=reservation[1],remaining=str(reservation[2])),costs=[str(v[0]) for v in costs])
            snap['selector_epoch']=db.execute('SELECT epoch FROM worker_runtime_control WHERE singleton=1').fetchone()[0]
        snapshots.append(snap);return snap

    def start_worker():
        ordinal=len(workers)+1
        env=dict(os.environ)
        env.pop('PYTEST_ADDOPTS',None)
        env.update(BUYEROS_BROKER_URL=broker, BUYEROS_EAGER='false',
                   BUYEROS_OWNED_BROKER_FIXTURE='1', BUYEROS_BROKER_RECOVERY_CASE=name,
                   BUYEROS_BROKER_RECOVERY_CASE_DIR=str(folder),BUYEROS_BROKER_RECOVERY_WORKER=str(ordinal),
                   BUYEROS_CELERY_EXECUTION_ENABLED='true',PYTHONUTF8='1')
        with (folder/f'worker-{ordinal}.log').open('xb') as log:
            p=subprocess.Popen([sys.executable,'-X','utf8','-m','tests.broker_recovery_fixture'],
                               cwd=Path(__file__).resolve().parents[1],env=env,stdout=log,stderr=subprocess.STDOUT)
        workers.append(p)
        ready=wait(lambda:event('ready',ordinal=ordinal))
        tree=[pid for pid,_,_ in _owned_process_tree(p.pid)]
        assert ready['pid'] in tree
        ownership.append(dict(popen_pid=p.pid,tree_pids=tree))
        return p,ready['pid']

    def hard_stop(p,pid):
        assert pid in ownership[0]['tree_pids'] and p is workers[0]
        if os.name=='nt':
            subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,check=True,timeout=10)
        else:p.kill()
        code=p.wait(timeout=10)
        return dict(pid=pid,popen_pid=p.pid,exit_code=code,mode='owned process tree hard loss')

    def send(intent,generation,task_id=None):
        return publisher.send_task('buyeros.execute_intent',args=[intent,WS_A,generation],task_id=task_id).id

    async def claim(sweep=False,publish=True,lease=120):
        engine=create_engine()
        messages=[]
        def emit(message):
            messages.append(message)
            if publish:send(message['intent_key'],message['generation'])
        try:
            selected=await (sweep_once if sweep else dispatch_once)(engine,emit,'owned-recovery',datetime.now(timezone.utc),1,lease)
            return selected,messages
        finally:await engine.dispose()

    try:
        with psycopg.connect(worker_database_url) as db:
            r=db.execute("SELECT current_user,r.rolsuper,r.rolbypassrls,pg_get_userbyid(c.relowner),c.relrowsecurity FROM pg_roles r CROSS JOIN pg_class c WHERE r.rolname=current_user AND c.oid='outbox_events'::regclass").fetchone()
        role=dict(name=r[0],superuser=r[1],bypass=r[2],owner=r[3],rls=r[4])
        assert role['superuser'] is role['bypass'] is False and role['rls'] is True and role['name']!=role['owner']
        if name in ('unknown','accepted'):
            job,operation=_setup(pg_dsn)
            key=f'contact.lookup:{job}'
            with psycopg.connect(pg_dsn,autocommit=True) as db:
                db.execute("UPDATE outbox_events SET state='ready',fencing_generation=0 WHERE intent_key=%s",(key,))
        else:
            source=uuid.uuid4(); key=f'source.delete:{source}'
            with psycopg.connect(pg_dsn,autocommit=True) as db:
                reset_tenant(db)
                db.execute("INSERT INTO source_documents(id,workspace_id,project_id,canonical_url,digest,storage_mode,object_key,excerpt,retention_until,permission_purpose) VALUES(%s,%s,%s,%s,'fixture','private_object',%s,NULL,now()-interval '1 second','account_research')",(source,WS_A,PROJECT_A,f'https://redacted.invalid/{source}',f'tenants/{WS_A}/{source}'))
                seed_outbox(db,intent_key=key,event_type='source.delete',payload={'source_document_id':str(source)})
        container=_valkey_container()
        mapping=subprocess.check_output(['docker','port',container,'6379'],text=True).strip().splitlines()[0]
        broker='redis://127.0.0.1:'+mapping.rsplit(':',1)[1]+'/0'
        # A fresh app owns each disposable broker's producer pool. Mutating the
        # production singleton URL retains the prior case's cached producer.
        publisher=Celery('owned-recovery-publisher',broker=broker)
        client=redis.Redis.from_url(broker,socket_timeout=3)
        wait(client.ping,timeout=10)
        first,first_pid=start_worker()
        assert asyncio.run(claim(lease=5 if name=='lease' else 120))[0]==[key]
        wait(lambda:event('submit') if job else event('delete'))
        inflight=snapshot('inflight')
        if name=='accepted':
            assert inflight['outbox']['state']=='dispatched' and inflight['provider']['status']=='submitting'
            (folder/'allow-provider-return').touch(exist_ok=False)
            wait(lambda:event('committed'))
            committed=snapshot('committed')
            assert committed['outbox']['state']=='done' and committed['provider']['status']=='accepted'
        broker_before=wait(lambda:broker_state() if broker_state()['unacked'] else None)
        assert event('started')['task_id'] in broker_before['unacked']
        if name=='lease':
            def expired():
                with psycopg.connect(pg_dsn) as db:
                    return db.execute('SELECT now()>=lease_expires_at FROM outbox_events WHERE intent_key=%s',(key,)).fetchone()[0]
            wait(expired,timeout=10); snapshot('expired')
            second,second_pid=start_worker()
            assert asyncio.run(claim(sweep=True))[0]==[key]
            wait(lambda:event('return',intent=key,generation=2,outcome='done'))
            (folder/'release-first').touch(exist_ok=False)
            wait(lambda:event('return',intent=key,generation=1,outcome='stale'))
        else:
            killed=hard_stop(first,first_pid)
            def visible():
                server=client.time(); now=server[0]+server[1]/1000000
                scores=client.zrange('unacked_index',0,-1,withscores=True)
                if scores and all(now-score>=2 for _,score in scores):
                    return dict(server_time=now,unacked_scores=[score for _,score in scores],visibility_timeout_seconds=2)
            # Observe actual broker expiry. The consumer's periodic restore
            # scan is unchanged; startup need not scan an expired message.
            broker_expired=wait(visible,timeout=10)
            second,second_pid=start_worker()
            wait(lambda:event('return',intent=key,pid=second_pid,outcome={'redelivery':'done','unknown':'unknown','accepted':'duplicate'}[name]),timeout=180)
        final=snapshot('final')
        assert final['outbox']['state']=='done' and final['outbox']['generation']==(2 if name=='lease' else 1)
        if name=='unknown':
            assert final['provider']['status']=='unknown' and final['provider']['ref'] is None
        if name=='accepted':
            # Claim the persisted status intent without publishing, then prove
            # the original epoch is fenced. Owner writes only seed this fixture.
            rec=f'contact.reconcile:{operation}'
            monkeypatch.setenv('BUYEROS_PAID_DISPATCH_ENABLED','false');get_settings.cache_clear()
            assert asyncio.run(claim(publish=False))[0]==[rec]
            with psycopg.connect(pg_dsn,autocommit=True) as db:db.execute('UPDATE worker_runtime_control SET epoch=2 WHERE singleton=1')
            send(rec,1,task_id='old-epoch')
            wait(lambda:event('return',task_id='old-epoch',outcome='stale'))
            snapshot('epoch_denied')
            assert len([e for e in events() if e['stage']=='status'])==0
            with psycopg.connect(pg_dsn,autocommit=True) as db:db.execute('UPDATE worker_runtime_control SET epoch=1 WHERE singleton=1')
            pending_id=send(rec,1)
            wait(lambda:event('return',task_id=pending_id,outcome='pending'))
            snapshot('pending')
            (folder/'authoritative-status').touch(exist_ok=False)
            with psycopg.connect(pg_dsn,autocommit=True) as db:db.execute("UPDATE outbox_events SET state='ready' WHERE intent_key=%s",(rec,))
            assert asyncio.run(claim())[0]==[rec]
            wait(lambda:event('return',intent=rec,generation=2,outcome='reconciled'))
            settled=snapshot('settled')
            assert settled['reservation']['state']=='settled' and settled['costs']==['0.100000']
            duplicate_id=send(rec,2)
            wait(lambda:event('return',task_id=duplicate_id,outcome='duplicate'))
            assert snapshot('settled_duplicate')['costs']==['0.100000']
        if job:
            assert len([e for e in events() if e['stage']=='submit'])==1
            assert final['reservation']['state']=='active' and final['reservation']['remaining']=='0.300000' and not final['costs']
        broker_final=wait(lambda:broker_state() if broker_state()==dict(unacked=[],queued=0) else None)
        complete=True
    except Exception as exc:
        error=type(exc).__name__+': '+str(exc);raise
    finally:
        for p in workers:
            if p.poll() is None:
                if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=10)
                else:p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=10)
        capture=dict(name=name,complete=complete,error=error,live_verified=False,release_accepted=False,
                     role=locals().get('role'),owned_workers=ownership,events=events(),snapshots=snapshots,
                     broker_before=broker_before,broker_expired=broker_expired,broker_final=broker_final,killed=killed,resource_samples=resources,
                     seconds=time.monotonic()-started,owned_environment=dict(database='owned PG16',broker='owned Valkey8',worker='actual Celery solo',visibility_timeout_seconds=120 if name=='lease' else 2,initial_fixture_dispatch_paid_flag=name in ('unknown','accepted'),provider='test-only fixture; no HTTP/credentials/charge',external_provider_calls=0,send_calls=0),
                     status_fixture_note='owner seeds ready status intent and selector epoch in disposable DB; does not prove API admission or real promotion/rollback')
        with (folder/'capture.json').open('x',encoding='utf-8') as file:json.dump(capture,file,indent=2,allow_nan=False);file.write('\n')
        if publisher:publisher.close()
        get_settings.cache_clear()
        if container:subprocess.run(['docker','rm','-f',container],capture_output=True,timeout=20)
        with psycopg.connect(pg_dsn,autocommit=True) as db:
            db.execute('UPDATE worker_runtime_control SET epoch=1 WHERE singleton=1')
            if source:
                db.execute('DELETE FROM outbox_events WHERE intent_key=%s',(key,));db.execute('DELETE FROM source_documents WHERE id=%s',(source,))
