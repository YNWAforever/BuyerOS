"""Owned directory tools reject empty discovery and keep actual failed denominators."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from tools.quality_metrics import DATABASE_VARIABLES,summarize_requests

ROOT=Path(__file__).resolve().parents[3]


def load_tool():
    spec=importlib.util.spec_from_file_location('c61_directory_cli',ROOT/'scripts/benchmark-workspace-directory.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_directory_metrics_keep_failed_requests_and_unstable_small_sample():
    rows=[dict(latency_ms=float(i),sql_ms=1.0,queries=4,bytes=100,status=200,invalid_context=False) for i in range(30)]
    rows[0]['status']=500;rows[1]['status']=None;rows[2]['invalid_context']=True
    report=summarize_requests(rows)
    assert report['errors']['denominator']==30 and report['errors']['failed_requests']==3
    assert report['queries']['max']==4 and report['queries']['total']==120
    assert report['latency_ms']['p99_stable'] is False
    with pytest.raises(ValueError):summarize_requests([])
    rows[0]['latency_ms']=float('nan')
    with pytest.raises(ValueError):summarize_requests(rows)


def fake_capture(monkeypatch,tmp_path,xml):
    module=load_tool();output=tmp_path/'directory.json'
    for variable in DATABASE_VARIABLES:monkeypatch.delenv(variable,raising=False)
    monkeypatch.setattr(module.sys,'argv',['benchmark-workspace-directory.py','--output',str(output)])
    def run(command,**kwargs):
        assert command[1:3]==['-m','pytest'], 'this isolated unit must never launch Docker'
        junit=Path(next(value.split('=',1)[1] for value in command if value.startswith('--junitxml=')))
        junit.write_text(xml,encoding='utf-8')
        output.write_text(json.dumps({'run_id':kwargs['env']['BUYEROS_DIRECTORY_NONCE'],
            'schema':'buyeros.workspace-directory-benchmark.v1','matrix':[{}, {}, {}, {}],
            'directory_gate':{'passed':True}}),encoding='utf-8')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess,'run',run)
    return module


@pytest.mark.parametrize('xml',[
    '<testsuites tests="0"/>',
    '<testsuite><testcase><skipped/></testcase></testsuite>',
    '<testsuite><testcase><failure/></testcase></testsuite>',
    '<testsuite><testcase><error/></testcase></testsuite>',
])
def test_directory_capture_rejects_empty_or_nonpassing_required_junit(monkeypatch,tmp_path,xml):
    assert fake_capture(monkeypatch,tmp_path,xml).main()==1


def test_directory_capture_accepts_actual_positive_required_case(monkeypatch,tmp_path):
    assert fake_capture(monkeypatch,tmp_path,'<testsuite><testcase name="observed"/></testsuite>').main()==0


def test_directory_capture_rejects_inherited_database_before_subprocess(monkeypatch,tmp_path):
    module=load_tool()
    monkeypatch.setenv('DATABASE_URL','postgresql://unowned.invalid/unapproved')
    monkeypatch.setattr(module.sys,'argv',['benchmark-workspace-directory.py','--output',str(tmp_path/'new.json')])
    monkeypatch.setattr(module.subprocess,'run',lambda *args,**kwargs:pytest.fail('must not run outside owned fixture'))
    with pytest.raises(SystemExit) as denied:module.main()
    assert denied.value.code==2
