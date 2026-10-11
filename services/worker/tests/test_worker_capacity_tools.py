"""Owned worker benchmark wrapper controls; no real provider/DB claims."""
import importlib.util,json,os,sys
from types import SimpleNamespace
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
VARIABLES=('DATABASE_URL','BUYEROS_DATABASE_URL','BUYEROS_TEST_DATABASE_URL','BUYEROS_WORKER_DATABASE_URL')

def tool(monkeypatch,tmp_path):
    path=ROOT/'scripts/benchmark-worker-capacity.py'
    assert path.is_file(),"owned worker capacity wrapper missing"
    spec=importlib.util.spec_from_file_location('worker_capacity',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for variable in VARIABLES:monkeypatch.delenv(variable,raising=False)
    monkeypatch.setattr(sys,'argv',['worker-capacity','--output',str(tmp_path/'new.json'),'--junit',str(tmp_path/'new.xml')])
    return module

@pytest.mark.parametrize('variable',VARIABLES)
def test_worker_capacity_refuses_each_inherited_database_before_child(monkeypatch,tmp_path,variable):
    module=tool(monkeypatch,tmp_path);monkeypatch.setenv(variable,'postgresql://not-used.invalid/shared')
    monkeypatch.setattr(module.subprocess,'call',lambda *a,**k:pytest.fail('must refuse before child'))
    with pytest.raises(SystemExit) as denied:module.main()
    assert denied.value.code==2

@pytest.mark.parametrize('path',['new.json','new.xml'])
def test_worker_capacity_preserves_existing_report_and_junit(monkeypatch,tmp_path,path):
    module=tool(monkeypatch,tmp_path);existing=tmp_path/path;existing.write_bytes(b'original-evidence')
    monkeypatch.setattr(module.subprocess,'call',lambda *a,**k:pytest.fail('must refuse existing evidence'))
    with pytest.raises(SystemExit) as denied:module.main()
    assert denied.value.code==2 and existing.read_bytes()==b'original-evidence'

@pytest.mark.parametrize('xml,fresh',[
 ('<testsuite/>',True),
 ('<testsuite><testcase classname="tests.benchmark_worker_capacity_case" name="test_owned_backlog_rotation_and_worker_restart"><skipped/></testcase></testsuite>',True),
 ('<testsuite><testcase classname="tests.benchmark_worker_capacity_case" name="test_owned_backlog_rotation_and_worker_restart"><failure/></testcase></testsuite>',True),
 ('<testsuite><testcase classname="tests.other" name="unrelated_positive"/></testsuite>',True),
 ('<testsuite><testcase classname="tests.benchmark_worker_capacity_case" name="test_owned_backlog_rotation_and_worker_restart"/></testsuite>',True),
 ('<testsuite><testcase classname="tests.benchmark_worker_capacity_case" name="test_owned_backlog_rotation_and_worker_restart"/></testsuite>',False),
])
def test_worker_capacity_requires_named_positive_zero_skip_junit(monkeypatch,tmp_path,xml,fresh):
    module=tool(monkeypatch,tmp_path)
    # This mocked child has an explicit clock/mtime; actual benchmark freshness stays strict.
    monkeypatch.setattr(module,'time',SimpleNamespace(time=lambda:1_700_000_000.0))
    def child(command,*,cwd,env):
        assert env['BUYEROS_STRICT_INTEGRATION']=='1' and all(not env.get(k) for k in VARIABLES)
        Path(env['BUYEROS_WORKER_CAPACITY_OUTPUT']).write_text(json.dumps(valid_report()))
        junit=Path(env['BUYEROS_WORKER_CAPACITY_JUNIT']);junit.write_text(xml)
        stamp=(1_700_000_000 if fresh else 1_699_999_999)*1_000_000_000
        os.utime(junit,ns=(stamp,stamp))
        return 0
    monkeypatch.setattr(module.subprocess,'call',child)
    result=module.main();valid=fresh and 'unrelated' not in xml and '<testcase ' in xml and '<skipped' not in xml and '<failure' not in xml
    assert (result==0)==valid
    if valid:
        report=json.loads((tmp_path/'new.json').read_text());assert report['live_verified'] is False and report['release_accepted'] is False and report['provenance']['tool_hashes']

def valid_report():
    # This only exercises the wrapper gate, not worker execution.
    return dict(schema='buyeros.worker-capacity.v1',evidence_mode='owned_disposable_fixture',live_verified=False,release_accepted=False,complete=True,error=None,worker_pids=[1,2],observations=[dict(intent='synthetic:'+str(n),published={'generation':1},done_observed_seconds=1.0,timeout_or_incomplete=False) for n in range(29)])

@pytest.mark.parametrize('missing',['incomplete','empty','same-worker'])
def test_worker_capacity_named_pass_cannot_hide_missing_raw_denominator(monkeypatch,tmp_path,missing):
    module=tool(monkeypatch,tmp_path);report=valid_report()
    if missing=='incomplete':report['observations'][0]['timeout_or_incomplete']=True
    if missing=='empty':report['observations']=[]
    if missing=='same-worker':report['worker_pids']=[1,1]
    def child(command,*,cwd,env):
        Path(env['BUYEROS_WORKER_CAPACITY_OUTPUT']).write_text(json.dumps(report))
        Path(env['BUYEROS_WORKER_CAPACITY_JUNIT']).write_text('<testsuite><testcase classname="tests.benchmark_worker_capacity_case" name="test_owned_backlog_rotation_and_worker_restart"/></testsuite>')
        return 0
    monkeypatch.setattr(module.subprocess,'call',child)
    assert module.main()==1

def driver():
    path=Path(__file__).with_name('worker_capacity_driver.py')
    assert path.is_file(),'bounded backlog driver missing'
    spec=importlib.util.spec_from_file_location('capacity_driver',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_worker_capacity_continues_returned_cursor_after_empty_budget_cycle():
    import asyncio
    module=driver();seen=[];published={};cycles=[]
    async def dispatch(cursor):
        seen.append(cursor)
        result=[dict(published=[],next_cursor=2,visited=2),dict(published=['b'],next_cursor=0,visited=1)][len(seen)-1]
        for key in result['published']:published[key]={}
        return result
    asyncio.run(module.collect_bounded_backlog(dispatch,published,1,0,cycles,max_cycles=2))
    assert seen==[0,2] and len(cycles)==2 and cycles[0]['published']==[]
    assert all(row['wall_seconds']>=0 for row in cycles)

def test_worker_capacity_stalled_backlog_stops_with_all_empty_cycles_retained():
    import asyncio
    module=driver();seen=[];cycles=[]
    async def dispatch(cursor):
        seen.append(cursor);return dict(published=[],next_cursor=cursor+1,visited=1)
    with pytest.raises(AssertionError,match='bounded backlog incomplete'):
        asyncio.run(module.collect_bounded_backlog(dispatch,{},1,0,cycles,max_cycles=3))
    assert seen==[0,1,2] and len(cycles)==3 and all(row['published']==[] for row in cycles)
