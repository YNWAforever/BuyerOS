"""Opt-in CF07 operating proof; owned PG, actual local Queue/Workflow, no providers."""
import asyncio
import json
import os
import platform
import socket
import statistics
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
import psycopg
import uvicorn

from tests.cloudflare_fixtures import cloudflare_database as migrated
from tests.test_cloudflare_runtime_control_db import seed_envelope, worker_runtime
from tests.test_cloudflare_local_steps_db import seed_project

ROOT = Path(__file__).resolve().parents[3]


def percentile(values, fraction):
    rows = sorted(values)
    at = (len(rows)-1)*fraction
    lo = int(at)
    return rows[lo] + (rows[min(lo+1,len(rows)-1)]-rows[lo])*(at-lo)


@pytest.mark.parametrize("repeat", [1, 2])
def test_ten_actual_queue_jobs_one_permit_and_hundred_workspace_cold_claims(migrated, worker_runtime, monkeypatch, tmp_path, repeat):
    from buyeros_api.api.app import create_app
    from buyeros_api.settings import get_settings
    from buyeros_api.services.worker_execution import create_execution_engine
    from buyeros_api.execution.dispatcher import claim_cycle
    from buyeros_api.execution import step_runner
    original_execute = step_runner.execute_claimed
    execution_intervals = []
    active = 0
    peak_active = 0
    async def observed_execute(*args, **kwargs):
        nonlocal active, peak_active
        started = time.perf_counter()
        active += 1
        peak_active = max(peak_active, active)
        try:
            return await original_execute(*args, **kwargs)
        finally:
            execution_intervals.append((started, time.perf_counter()))
            active -= 1
    monkeypatch.setattr(step_runner, 'execute_claimed', observed_execute)
    envelopes = []
    jobs = []
    buyers = []
    for _ in range(10):
        envelope = seed_envelope(migrated, worker_runtime[1])
        project, actor, member = seed_project(migrated, envelope.workspace_id)
        job, company, buyer = (uuid.uuid4() for _ in range(3))
        with psycopg.connect(migrated, autocommit=True) as db:
            db.execute("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES(%s,%s,'Fictional CF07','Fictional CF07')", (company,envelope.workspace_id))
            db.execute('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES(%s,%s,%s,%s)',(buyer,envelope.workspace_id,project,company))
            db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested) VALUES(%s,%s,%s,%s,'bulk_mutation','assignBuyerOwners',%s::jsonb,'queued',1)", (job,envelope.workspace_id,project,actor,json.dumps({'owner_membership_id':str(member),'reason':'Fictional ten-job operating fixture'})))
            db.execute("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status) VALUES(%s,%s,%s,%s,0,1,'pending')",(uuid.uuid4(),envelope.workspace_id,job,buyer))
            db.execute('UPDATE outbox_events SET payload=%s::jsonb WHERE id=%s',(json.dumps({'job_id':str(job)}),envelope.outbox_id))
        envelopes.append(envelope)
        jobs.append(job)
        buyers.append(str(buyer))
    monkeypatch.setenv('BUYEROS_WORKER_CURRENT_KEY_ID','fictional-key')
    monkeypatch.setenv('BUYEROS_WORKER_CURRENT_SECRET','fictional-cf05-secret-32-bytes-only')
    get_settings.cache_clear()
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(),log_level='error',access_log=False))
    def serve():
        asyncio.run(server.serve(sockets=[sock]),loop_factory=asyncio.SelectorEventLoop if sys.platform=='win32' else None)
    thread=threading.Thread(target=serve,daemon=True);thread.start()
    stop=threading.Event(); samples=[]
    def observe():
        with psycopg.connect(migrated,autocommit=True) as db:
            while not stop.is_set():
                active=db.execute("SELECT count(*) FROM worker_steps WHERE state='running'").fetchone()[0]
                connections=db.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()').fetchone()[0]
                samples.append((active,connections))
                stop.wait(.02)
    observer=threading.Thread(target=observe,daemon=True)
    cpu_started=time.process_time();wall_started=time.perf_counter()
    try:
        deadline=time.monotonic()+10
        while not server.started and thread.is_alive() and time.monotonic()<deadline: time.sleep(.05)
        assert server.started
        context=tmp_path/'opaque-operating-context.json'
        context.write_text(json.dumps({'origin':f'http://127.0.0.1:{port}','jobs':[e.model_dump(mode='json') for e in envelopes]}),encoding='utf8')
        env={k:v for k,v in os.environ.items() if not k.startswith(('BUYEROS_','AUTH0_','R2_','VERCEL_','CLOUDFLARE_'))}
        env['BUYEROS_CF_TEST_CONTEXT']=str(context)
        observer.start()
        result=subprocess.run(['node','node_modules/vitest/vitest.mjs','run','--config','services/cloudflare-jobs/vitest.operating.config.ts','--reporter=default','--reporter=junit',f'--outputFile.junit=artifacts/cloudflare/CF07-operating-platform-final-repeat{repeat}.xml'],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf8',timeout=180)
        (ROOT/f'artifacts/cloudflare/CF07-operating-platform-final-repeat{repeat}.txt').write_text(result.stdout+result.stderr,encoding='utf8')
        assert result.returncode==0,result.stdout+result.stderr
        with psycopg.connect(migrated) as db:
            assert db.execute("SELECT count(*) FROM async_jobs WHERE status='completed' AND id=ANY(%s)",(jobs,)).fetchone()[0]==10
            assert db.execute("SELECT count(*) FROM audit_events WHERE action='buyer.owner_assigned' AND subject_id=ANY(%s)",(buyers,)).fetchone()[0]==10
            intervals=db.execute('SELECT s.created_at,s.updated_at,o.created_at FROM worker_steps s JOIN outbox_events o ON o.id=s.outbox_id WHERE o.id=ANY(%s) ORDER BY s.created_at',([e.outbox_id for e in envelopes],)).fetchall()
            assert len(intervals)==10 and all(end is not None for _,end,_ in intervals)
            execution_intervals.sort()
            assert len(execution_intervals)==10 and peak_active==1
            assert all(execution_intervals[i][1]<=execution_intervals[i+1][0] for i in range(9)), 'actual native execution intervals must never overlap'
            first=[(start-created).total_seconds() for start,_,created in intervals]
            durations=[end-start for start,end in execution_intervals]
            assert max(durations)<=1, 'named non-provider fixture condition must actually hold'
            assert percentile(first,.95)<=120
        assert samples and max(active for active,_ in samples)<=1
        # New engines/process-local state on every tick; DB cursor alone owns fairness.
        cold=[]
        for _ in range(100):
            e=seed_envelope(migrated,worker_runtime[1])
            with psycopg.connect(migrated,autocommit=True) as db:
                db.execute("UPDATE outbox_events SET state='ready',fencing_generation=0 WHERE id=%s",(e.outbox_id,))
            cold.append(e)
        seen=set();tick_ms=[]
        async def cold_tick():
            engine=create_execution_engine()
            try:
                return await claim_cycle(engine,backend='cloudflare',epoch=worker_runtime[1],max_total=10)
            finally: await engine.dispose()
        for tick in range(12):
            started=time.perf_counter();batch=asyncio.run(cold_tick());tick_ms.append((time.perf_counter()-started)*1000)
            for row in batch.items:
                assert row.outbox_id not in seen
                seen.add(row.outbox_id)
            if len(seen)==100: break
        assert seen=={e.outbox_id for e in cold}, 'all 100 workspaces must survive cold-start cursor fairness'
        with psycopg.connect(migrated) as db:
            probe_age=db.execute('SELECT extract(epoch FROM (clock_timestamp()-last_probe_at)) FROM worker_runtime_probe').fetchone()[0]
            assert probe_age is not None and 0<=probe_age<=180
            oldest=db.execute("SELECT extract(epoch FROM(clock_timestamp()-min(created_at))) FROM outbox_events WHERE state IN ('ready','dispatched')").fetchone()[0]
        if sys.platform=='win32':
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage','PrivateUsage')]
            info=Counters();info.cb=ctypes.sizeof(info)
            get_memory=ctypes.windll.psapi.GetProcessMemoryInfo
            get_memory.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
            assert get_memory(wintypes.HANDLE(-1),ctypes.byref(info),info.cb)
            peak_rss=info.PeakWorkingSetSize
        else:
            import resource
            peak_rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        report={'repeat':repeat,'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'machine':platform.platform(),
            'conditions':{'transport':'actual local Cloudflare Queue and Workflow -> loopback native API -> owned PostgreSQL16','identity':'fictional machine key and staff membership','provider':'none','queued_jobs':10,'parallel_python_steps':1,'non_provider_step_ceiling_seconds':1,'fair_workspaces':100,'cold_engine_every_tick':True,'cron':'jobs injected together; claim ticks invoked immediately, no 60-second production wait'},
            'first_step_seconds':{'p50':statistics.median(first),'p95':percentile(first,.95),'max':max(first)},
            'step_seconds':{'p50':statistics.median(durations),'p95':percentile(durations,.95),'max':max(durations)},
            'max_observed_active_steps':max(x[0] for x in samples),'actual_native_intervals_no_overlap':True,'peak_active_native_bodies':peak_active,
            'peak_database_connections':max(x[1] for x in samples),'observer_samples':len(samples),'observer_interval_ms':20,
            'fairness':{'workspaces_served':len(seen),'cold_ticks':len(tick_ms),'tick_ms_p50':statistics.median(tick_ms),'tick_ms_p95':percentile(tick_ms,.95)},
            'api_process_cpu_seconds':time.process_time()-cpu_started,'wall_seconds':time.perf_counter()-wall_started,
            'queue_age_seconds_conservative':{'p50':statistics.median(first),'p95':percentile(first,.95)},'actual_probe_receipt_age_seconds':float(probe_age),'oldest_unexecuted_fairness_fixture_seconds':float(oldest),'api_fixture_peak_rss_bytes':peak_rss,'memory_conditions':'entire API fixture process peak; excludes Node/workerd/Docker child memory; no hosted memory inference'}
        (ROOT/f'artifacts/cloudflare/CF07-operating-benchmark-final-repeat{repeat}.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    finally:
        stop.set()
        if observer.is_alive(): observer.join(5)
        server.should_exit=True;thread.join(10);sock.close();get_settings.cache_clear()
        assert not thread.is_alive()
