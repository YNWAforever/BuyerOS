"""Finite owned backlog/worker restart capture; never uses a shared DSN."""
import argparse,json,math,os,subprocess,sys,time,uuid
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];API=ROOT/'services/api';WORKER=ROOT/'services/worker'
sys.path.insert(0,str(API))
from tools.quality_metrics import DATABASE_VARIABLES,provenance

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--junit',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();junit=args.junit.resolve()
    for key in DATABASE_VARIABLES:
        if os.environ.get(key):parser.error('unset inherited database '+key+'; owned fixture only')
    if output==junit or output.exists() or junit.exists():parser.error('output and junit must be distinct new evidence')
    python=WORKER/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():parser.error('frozen worker virtual environment required')
    env=dict(os.environ);env.update(BUYEROS_STRICT_INTEGRATION='1',PYTHONUTF8='1',BUYEROS_WORKER_CAPACITY_OUTPUT=str(output),BUYEROS_WORKER_CAPACITY_JUNIT=str(junit),BUYEROS_WORKER_CAPACITY_NONCE=uuid.uuid4().hex)
    case=WORKER/'tests/benchmark_worker_capacity_case.py';started=time.time()
    result=subprocess.call([str(python),'-X','utf8','-m','pytest','-q','-s',str(case),'--tb=short','--junitxml='+str(junit)],cwd=WORKER,env=env)
    if result:return result
    if not output.is_file():parser.error('benchmark produced no observations; collection is not verification')
    if not junit.is_file() or junit.stat().st_mtime<started:return 1
    cases=list(ET.parse(junit).getroot().iter('testcase'))
    if len(cases)!=1 or cases[0].get('name')!='test_owned_backlog_rotation_and_worker_restart' or cases[0].get('classname')!='tests.benchmark_worker_capacity_case' or any(c.find(k) is not None for c in cases for k in ('failure','error','skipped')):return 1
    report=json.loads(output.read_text(encoding='utf-8'))
    if report.get('schema')!='buyeros.worker-capacity.v1' or report.get('evidence_mode')!='owned_disposable_fixture' or report.get('live_verified') is not False or report.get('release_accepted') is not False:return 1
    rows=report.get('observations');pids=report.get('worker_pids')
    if (report.get('complete') is not True or report.get('error') is not None
        or not isinstance(rows,list) or len(rows)!=29
        or not isinstance(pids,list) or len(pids)!=2
        or any(type(pid) is not int or pid<=0 for pid in pids) or pids[0]==pids[1]
        or any(not isinstance(row,dict) or not isinstance(row.get('intent'),str)
               or row.get('timeout_or_incomplete') is not False
               or not isinstance(row.get('published'),dict)
               or row['published'].get('generation')!=1
               or type(row.get('done_observed_seconds')) not in (int,float)
               or not math.isfinite(row['done_observed_seconds']) or row['done_observed_seconds']<0
               for row in rows)
        or len({row['intent'] for row in rows})!=29):return 1
    report['provenance']=provenance(ROOT,[Path(__file__).resolve(),case,WORKER/'tests/worker_capacity_driver.py',WORKER/'tests/conftest.py',WORKER/'buyeros_worker/tasks.py',WORKER/'buyeros_worker/app.py',API/'buyeros_api/execution/dispatcher.py',API/'buyeros_api/execution/handlers/retention.py'])
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':raise SystemExit(main())
