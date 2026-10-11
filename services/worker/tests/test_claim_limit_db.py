"""Real restricted-role claim limits; no publisher or worker is involved."""
import asyncio,json,os,uuid
from datetime import datetime,timezone
from pathlib import Path
import psycopg,pytest
from sqlalchemy import event
from buyeros_api.db.session import tenant_session
from buyeros_api.execution.dispatcher import claim_outbox_rows
from buyeros_worker.engine import create_engine
from tests.conftest import WS_A,WS_B,seed_outbox

@pytest.mark.parametrize('limit',[1,3])
def test_actual_single_tenant_claim_respects_locked_limit(worker_database_url,pg_dsn,limit):
    prefix='c61limit:'+uuid.uuid4().hex+':';plan=[]
    with psycopg.connect(pg_dsn,autocommit=True) as db:
        for workspace in (WS_A,WS_B):
            for number in range(25):seed_outbox(db,intent_key=prefix+workspace+':'+str(number),event_type='source.delete',payload={'source_document_id':str(uuid.uuid4())},workspace_id=workspace)
        db.execute('UPDATE outbox_events SET created_at=now() WHERE intent_key LIKE %s',(prefix+'%',))
    async def claim():
        engine=create_engine()
        def explain(conn,cursor,statement,parameters,context,many):
            if 'UPDATE outbox_events' in statement and 'RETURNING' in statement and not statement.startswith('EXPLAIN'):
                savepoint=conn.begin_nested()
                try:plan.append(conn.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+statement,parameters).scalar_one())
                finally:savepoint.rollback()
        event.listen(engine.sync_engine,'before_cursor_execute',explain)
        try:
            async with tenant_session(engine,uuid.UUID(WS_A)) as session:
                return await claim_outbox_rows(session,'owned-limit',limit,datetime.now(timezone.utc),60)
        finally:event.remove(engine.sync_engine,'before_cursor_execute',explain);await engine.dispose()
    try:
        rows=asyncio.run(claim())
        with psycopg.connect(pg_dsn) as db:
            counts=db.execute('SELECT workspace_id,state,count(*) FROM outbox_events WHERE intent_key LIKE %s GROUP BY workspace_id,state',(prefix+'%',)).fetchall()
        counts=[(str(w),state,n) for w,state,n in counts]
        proof={'limit':limit,'claimed':len(rows),'workspaces':[str(row['workspace_id']) for row in rows],'counts':[(str(w),s,n) for w,s,n in counts],'explain_analyze_savepoint_rolled_back':plan,'role':'owned leastprivilege worker fixture;tenant WS_A','no_broker_or_worker':True}
        destination=os.environ.get('BUYEROS_CLAIM_PROFILE_PREFIX')
        if destination:
            path=Path(destination+'-'+str(limit)+'.json');assert not path.exists()
            with path.open('x',encoding='utf-8') as f:json.dump(proof,f,indent=2);f.write('\n')
        print(json.dumps({'limit':limit,'actual_claimed':len(rows),'foreign_unchanged':(WS_B,'ready',25) in counts}),flush=True)
        assert len(rows)==limit,'real PG claim exceeds locked candidate limit'
        assert all(str(row['workspace_id'])==WS_A for row in rows)
        assert (WS_A,'ready',25-limit) in counts and (WS_A,'dispatched',limit) in counts and (WS_B,'ready',25) in counts
    finally:
        with psycopg.connect(pg_dsn,autocommit=True) as db:db.execute('DELETE FROM outbox_events WHERE intent_key LIKE %s',(prefix+'%',))
