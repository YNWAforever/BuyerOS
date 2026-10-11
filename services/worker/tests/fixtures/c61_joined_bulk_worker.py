"""Same UI-created project; owned Docker fixture only; real restricted bulk worker.

The receipt proves abrupt owned standalone process death after a committed chunk.
It does not test a Celery broker acknowledgment window or a real provider.
"""
import contextlib,io,json,os,sys,uuid,subprocess,queue,threading,time
import psycopg
from tests.fixtures.run_browser_research import owner_dsn,WORKSPACE
from tests.fixtures import audit_manifests as existing

def abrupt_committed_chunk(project,args):
    assert len(args)==1
    env={**os.environ,'C61_OWNED_PAUSED_CHUNK_PARENT_PID':str(os.getpid())}
    executable=sys.executable
    if sys.platform=='win32':
        # Launch the actual interpreter directly, retaining this exact venv.
        # The Windows venv redirector introduces another PID and must never
        # be mistaken for the process that commits and pauses.
        executable=sys._base_executable;env['__PYVENV_LAUNCHER__']=sys.executable
    argv=[executable,str(__file__),str(project),'pause-after-chunk',*args]
    child=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    received=queue.Queue()
    threading.Thread(target=lambda:received.put(child.stdout.readline()),daemon=True).start()
    try:
        row=json.loads(received.get(timeout=30))
        assert row['fixture_only'] and row['project_id']==str(project)
        assert row['native_process_pid']==child.pid and row['phase']=='paused_after_committed_chunk'
        assert row['total']==50 and row['role']=='buyeros_worker' and child.poll() is None
        # Terminate only this child after observing its committed real chunk.
        # This is an abrupt standalone process death, not a Celery broker test.
        child.kill();code=child.wait(timeout=5);assert code!=0
        row.update(abrupt_worker_crash=True,owned_child_force_terminated=True,killed_native_exit=code,
                   controller_pid=os.getpid(),Celery_broker_ack_window_tested=False)
        print(json.dumps(row),flush=True)
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=5)
        child.stdout.close();child.stderr.close()

def main():
    if len(sys.argv)<3 or sys.argv[2] not in {'seed','stale-many','chunk','drain','inspect','expired-copy','crash-after-committed-chunk','pause-after-chunk'}:
        raise SystemExit('usage: c61_joined_bulk_worker.py UI_PROJECT COMMAND [BOUND_ARGS]')
    project=uuid.UUID(sys.argv[1]);command=sys.argv[2];args=sys.argv[3:]
    if command=='crash-after-committed-chunk':return abrupt_committed_chunk(project,args)
    pause=command=='pause-after-chunk'
    if pause:
        assert os.environ.get('C61_OWNED_PAUSED_CHUNK_PARENT_PID')==str(os.getppid()),'only this owned parent may create a paused child'
        command='chunk'
    prefix=f'C61 Joined Bulk Fixture {project.hex[:8]}'
    dsn=owner_dsn()
    with psycopg.connect(dsn) as db:
        assert db.execute('SELECT company_name FROM projects WHERE workspace_id=%s AND id=%s',(WORKSPACE,project)).fetchone()==('T30 Fictional Seller',),'not the UI-created owned fictional project'
        assert db.execute('SELECT count(*) FROM outreach_drafts WHERE workspace_id=%s AND project_id=%s AND state=\'approved\'',(WORKSPACE,project)).fetchone()==(1,),'existing exact approved draft required before appended bulk fault'
        if command=='seed':
            assert not args
            assert db.execute('SELECT count(*) FROM companies WHERE workspace_id=%s AND display_name LIKE %s',(WORKSPACE,prefix+'%')).fetchone()==(0,),'never delete/reseed an existing joined dataset'
            values=[(uuid.uuid5(uuid.NAMESPACE_URL,f'C61-joined-buyer:{WORKSPACE}:{project}:{i}'),uuid.uuid5(uuid.NAMESPACE_URL,f'C61-joined-company:{WORKSPACE}:{project}:{i}'),f'{prefix} {i:05d}') for i in range(120)]
            db.cursor().executemany('INSERT INTO companies(id,workspace_id,legal_name,display_name) VALUES (%s,%s,%s,%s)',[(c,WORKSPACE,n,n) for b,c,n in values])
            db.cursor().executemany('INSERT INTO project_buyers(id,workspace_id,project_id,company_id) VALUES (%s,%s,%s,%s)',[(b,WORKSPACE,project,c) for b,c,n in values])
            result=dict(fixture_only=True,count=120,ids=[str(b) for b,c,n in values])
        else:result=None
    if result is None:
        existing.PROJECT=str(project);existing.PREFIX=prefix
        sys.argv=['owned-original-bulk-helper',command,*args]
        captured=io.StringIO()
        with contextlib.redirect_stdout(captured):existing.main()
        result=json.loads(captured.getvalue())
    assert result['fixture_only'] is True
    result.update(project_id=str(project),workspace_id=str(WORKSPACE),prefix=prefix,native_process_pid=os.getpid(),abrupt_worker_crash=False,real_provider=False)
    if pause:result['phase']='paused_after_committed_chunk'
    print(json.dumps(result),flush=True)
    if pause:time.sleep(600)

if __name__=='__main__':main()
