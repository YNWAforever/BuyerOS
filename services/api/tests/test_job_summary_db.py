"""Q06 actual actor-bound summary reads on guarded disposable PostgreSQL."""
import json
import uuid

import psycopg
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.contract_validation import assert_contract_response
from tests.test_buyer_review_db import ADMIN, OPERATOR, VIEWER, REVIEWER, WORKSPACE_A, WORKSPACE_B, PROJECT_A, _h, api


def seed_job(seeded, actor=OPERATOR, count=1000, status="running"):
    job=str(uuid.uuid4())
    with psycopg.connect(seeded) as db:
        db.execute("INSERT INTO async_jobs(id,workspace_id,project_id,actor_user_id,kind,operation,command,status,requested,processed,updated,unchanged,blocked,conflicts) VALUES (%s,%s,%s,%s,'bulk_mutation','owner_assign','{}',%s,%s,%s,%s,%s,%s,%s)",
                   (job,WORKSPACE_A,PROJECT_A,uuid.uuid5(uuid.NAMESPACE_URL,actor),status,count,count,count//4,count//4,count//4,count//4))
        companies=[(uuid.uuid4(),WORKSPACE_A,f"Q06 fixture {i}",f"Q06 fixture {i}") for i in range(count)]
        buyers=[(uuid.uuid4(),WORKSPACE_A,PROJECT_A,c[0]) for c in companies]
        with db.cursor() as cur:
            cur.executemany("INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,%s,%s)",companies)
            cur.executemany("INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)",buyers)
            cur.executemany("INSERT INTO async_job_items(id,workspace_id,job_id,buyer_id,ordinal,expected_version,status,resulting_version) VALUES (%s,%s,%s,%s,%s,1,%s,%s)",[(uuid.uuid4(),WORKSPACE_A,job,b[0],i,['updated','unchanged','blocked','conflict'][i%4],2 if i%4==0 else None) for i,b in enumerate(buyers)])
    return job


def test_q06_summary_has_exact_counters_and_no_item_queries(api,seeded):
    job=seed_job(seeded)
    statements=[]
    def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
    event.listen(Engine,'before_cursor_execute',capture)
    try:response=api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}/summary",headers=_h(subject=OPERATOR))
    finally:event.remove(Engine,'before_cursor_execute',capture)
    assert response.status_code==200,response.text
    assert_contract_response('AsyncJobSummaryResponse',response.json())
    data=response.json()['data']
    assert data['id']==job and data['status']=='running'
    assert [data[k] for k in ['requested','processed','updated','unchanged','blocked','conflicts','cancelled']]==[1000,1000,250,250,250,250,0]
    assert 'result_page' not in data and 'command' not in data and 'actor_user_id' not in data
    assert not any('async_job_items' in s.lower() for s in statements),statements
    assert len(response.content)<1500


def test_q06_summary_detail_guards_match_current_actor_admin_and_tenant(api,seeded):
    job=seed_job(seeded,count=4)
    for suffix in ['', '/summary']:
        path=f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}{suffix}"
        for actor,status in [(OPERATOR,200),(ADMIN,200),(REVIEWER,404),(VIEWER,404)]:
            result=api.get(path,headers=_h(subject=actor));assert result.status_code==status,result.text
        assert api.get(f"/v1/workspaces/{WORKSPACE_B}/jobs/{job}{suffix}",headers=_h(subject=OPERATOR)).status_code==404
        assert api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{uuid.uuid4()}{suffix}",headers=_h()).status_code==404
    with psycopg.connect(seeded) as db:
        db.execute("UPDATE memberships SET active=false WHERE workspace_id=%s AND user_id=%s",(WORKSPACE_A,uuid.uuid5(uuid.NAMESPACE_URL,OPERATOR)))
    for suffix in ['', '/summary']:
        assert api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}{suffix}",headers=_h(subject=OPERATOR)).status_code==404


def test_q06_summary_terminal_state_and_draft_result_id_survive_read_restart(api,seeded):
    job=seed_job(seeded,count=4,status='completed')
    with psycopg.connect(seeded) as db:
        db.execute("UPDATE async_jobs SET kind='draft_generation', command=%s WHERE id=%s",(json.dumps({'result_draft_id':str(uuid.uuid4())}),job))
        draft=db.execute("SELECT command->>'result_draft_id' FROM async_jobs WHERE id=%s",(job,)).fetchone()[0]
    response=api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}/summary",headers=_h())
    assert response.status_code==200,response.text
    first=response.json()
    assert_contract_response('AsyncJobSummaryResponse',first)
    second=api.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}/summary",headers=_h()).json()
    assert first['data']==second['data'] and first['data']['result_id']==draft


def test_q06_60s_ten_view_traffic_replays_real_http_bytes_and_db_executes(api,seeded,monkeypatch):
    """Fake-clock scheduling; every counted request/byte/SQL execute is replayed, not extrapolated."""
    import subprocess
    from collections import Counter
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from buyeros_api.services import api_rate_limit
    from tests import auth_fixtures as fx
    root=Path(__file__).resolve().parents[3];out=root/'test-results';out.mkdir(exist_ok=True)
    job=seed_job(seeded)
    with api as client:
        samples={'pages':{}}
        for offset in range(0,1000,100):
            response=client.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}?offset={offset}&limit=100",headers=_h())
            assert response.status_code==200,response.text;samples['pages'][str(offset)]=response.json()
        response=client.get(f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}/summary",headers=_h());assert response.status_code==200,response.text;samples['summary']=response.json()
        sample_path=out/'q06-traffic-samples.json';sample_path.write_text(json.dumps(samples),encoding='utf-8')
        trace_path=out/'q06-traffic-schedule.json'
        scheduled=subprocess.run(['node','tests/job-poller-traffic.mjs',str(sample_path),str(trace_path)],cwd=root,capture_output=True,text=True,encoding='utf-8',check=True)
        (out/'q06-traffic-node.log').write_text(scheduled.stdout+scheduled.stderr,encoding='utf-8')
        trace=json.loads(trace_path.read_text(encoding='utf-8'));subjects=[f'auth0|q06-view-{i}' for i in range(10)]
        with psycopg.connect(seeded) as db:
            for subject in subjects:
                user=uuid.uuid5(uuid.NAMESPACE_URL,subject)
                db.execute('INSERT INTO users(id,issuer,subject) VALUES (%s,%s,%s)',(user,fx.ISSUER,subject))
                db.execute("INSERT INTO memberships(id,workspace_id,user_id,roles,active) VALUES (%s,%s,%s,'{workspace_admin}',true)",(uuid.uuid4(),WORKSPACE_A,user))
        class LogicalRateClock(datetime):
            current=datetime(2026,10,3,0,0,30,tzinfo=timezone.utc)
            @classmethod
            def now(cls,tz=None):return cls.current if tz else cls.current.replace(tzinfo=None)
        monkeypatch.setattr(api_rate_limit,'datetime',LogicalRateClock)
        metrics=[]
        try:
            for run in trace['runs']:
                with psycopg.connect(seeded) as db:
                    db.execute('DELETE FROM api_rate_windows WHERE workspace_id=%s AND actor_id=ANY(%s)',(WORKSPACE_A,[uuid.uuid5(uuid.NAMESPACE_URL,v) for v in subjects]))
                statements=[]
                def capture(conn,cursor,statement,parameters,context,executemany):statements.append(statement)
                event.listen(Engine,'before_cursor_execute',capture);bytes_total=0;statuses=Counter()
                try:
                    for call in run['requests']:
                        LogicalRateClock.current=datetime(2026,10,3,0,0,30,tzinfo=timezone.utc)+timedelta(milliseconds=call['at_ms'])
                        path=f"/v1/workspaces/{WORKSPACE_A}/jobs/{job}"
                        path+='/summary' if call['kind']=='summary' else f"?offset={call['offset']}&limit={call['limit']}"
                        response=client.get(path,headers=_h(subject=subjects[call['view']]))
                        statuses[response.status_code]+=1;assert response.status_code==200,response.text;bytes_total+=len(response.content)
                finally:event.remove(Engine,'before_cursor_execute',capture)
                metrics.append({'mode':run['mode'],'requests':len(run['requests']),'response_body_bytes':bytes_total,'db_execute_count':len(statements),'result_table_execute_count':sum('async_job_items' in q.lower() for q in statements),'http_status_counts':dict(statuses),'max_per_view_in_flight':max(v['maxInFlight'] for v in run['per_view'])})
            before,after=metrics;assert after['requests']<before['requests'];assert after['response_body_bytes']<before['response_body_bytes'];assert after['db_execute_count']<before['db_execute_count'];assert after['result_table_execute_count']==0;assert after['max_per_view_in_flight']==1
            result={'fixture_only':True,'baseline_source_sha':trace['baseline_sha'],'conditions':{'logical_seconds':60,'views':10,'persisted_results':1000,'simulated_rtt_ms':2500,'wall_clock_performance':False,'database':'owned disposable PostgreSQL16; real runtime-role HTTP and executes','rate_limit':'unchanged120/minute per actor; ten fictional current admins; logical experiment starts30s before minute boundary; fresh fixture windows between independent runs','identity':'fictional signed principals; no live account/provider verification'},'measurements':metrics}
            (out/'q06-traffic-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        finally:
            with psycopg.connect(seeded) as db:
                for subject in subjects:
                    user=uuid.uuid5(uuid.NAMESPACE_URL,subject)
                    db.execute('DELETE FROM api_rate_windows WHERE actor_id=%s',(user,));db.execute('DELETE FROM memberships WHERE user_id=%s',(user,));db.execute('DELETE FROM users WHERE id=%s',(user,))
