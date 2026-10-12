"""Exactly10 owned tenants/30minutes; no inherited DB, shorter run, or live acceptance."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/'services/worker'; API=ROOT/'services/api'
sys.path.insert(0,str(API))
from tools.quality_metrics import DATABASE_VARIABLES, provenance
sys.path.insert(0,str(WORKER))
from tests.mixed_workload_driver import workload_complete
from tests.mixed_workload_cleanup import cleanup_all, run_owned_child


def native_linux_supported():
    return sys.platform == 'linux'


@contextmanager
def owned_runtime(env,folder):
    from tests.conftest import _start_container
    from tests.test_valkey_integration import _valkey_container
    targets=[]; receipts=[]

    def own(kind,name):
        target=dict(kind=kind,name=name,id=name)
        targets.append(target)
        target['id']=subprocess.check_output(['docker','inspect','--format','{{.Id}}',name],text=True,timeout=20).strip()
        return target

    def remove(target):
        result=subprocess.run(['docker','rm','-f',target['id']],capture_output=True,text=True,timeout=20)
        receipts.append(dict(kind=target['kind'],id=target['id'],returncode=result.returncode))
        result.check_returncode()

    try:
        name,dsn=_start_container(); own('postgres',name)
        broker=own('valkey',_valkey_container())
        mapping=subprocess.check_output(['docker','port',broker['id'],'6379'],text=True,timeout=20).strip().splitlines()[0]
        child_env=dict(env,BUYEROS_TEST_DATABASE_URL=dsn,BUYEROS_MIXED_BROKER_URL='redis://127.0.0.1:'+mapping.rsplit(':',1)[1]+'/0')
        with (folder/'owned-targets.json').open('x',encoding='utf-8') as file:
            json.dump(dict(owner_pid=os.getpid(),targets=targets),file,indent=2)
        yield child_env
    finally:
        try: cleanup_all([lambda target=target:remove(target) for target in reversed(targets)])
        finally:
            with (folder/'owned-target-cleanup.json').open('x',encoding='utf-8') as file:
                json.dump(dict(owner_pid=os.getpid(),receipts=receipts),file,indent=2)


def source_capture_unchanged(before,after):
    return (isinstance(before,dict) and isinstance(after,dict)
            and bool(before.get('source_sha')) and before.get('source_sha')==after.get('source_sha')
            and isinstance(before.get('tool_hashes'),dict) and bool(before['tool_hashes'])
            and before['tool_hashes']==after.get('tool_hashes'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    for key in DATABASE_VARIABLES:
        if os.environ.get(key): parser.error('unset inherited database '+key+'; owned fixture only')
    folder=args.output_dir.resolve()
    if folder.exists(): parser.error('new output directory required; retain previous evidence')
    if not native_linux_supported(): parser.error('owned sustained runner requires native Linux; no targets created')
    python=WORKER/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file(): parser.error('frozen worker virtual environment required')
    folder.mkdir(parents=True)
    paths=[Path(__file__),WORKER/'tests/benchmark_mixed_workload_case.py',WORKER/'tests/mixed_workload_fixture.py',WORKER/'tests/mixed_workload_driver.py',WORKER/'tests/mixed_workload_cleanup.py',WORKER/'tests/mixed_timeout_probe.py',WORKER/'tests/broker_recovery_fixture.py',WORKER/'tests/conftest.py',WORKER/'tests/test_contact_uncertainty_db.py',WORKER/'tests/test_valkey_integration.py',WORKER/'tests/worker_capacity_driver.py',WORKER/'buyeros_worker/tasks.py',WORKER/'buyeros_worker/app.py',API/'buyeros_api/execution/dispatcher.py',API/'buyeros_api/execution/handlers/retention.py',API/'buyeros_api/execution/handlers/bulk_mutate.py',API/'buyeros_api/services/bulk_service.py']
    frozen=provenance(ROOT,paths)
    with (folder/'provenance-start.json').open('x',encoding='utf-8') as f:json.dump(frozen,f,indent=2);f.write('\n')
    env=dict(os.environ);env.pop('PYTEST_ADDOPTS',None)
    env.update(PYTHONUTF8='1',BUYEROS_STRICT_INTEGRATION='1',BUYEROS_MIXED_OUTPUT=str(folder),BUYEROS_PAID_DISPATCH_ENABLED='false',BUYEROS_DELIVERY_DISPATCH_ENABLED='false')
    command=[str(python),'-X','utf8','-m','pytest','tests/benchmark_mixed_workload_case.py']
    collected=subprocess.run(command+['--collect-only','-q'],cwd=WORKER,env=env,capture_output=True,timeout=60)
    discovery=folder/'discovery.txt';discovery.write_bytes(collected.stdout)
    if collected.returncode:sys.stderr.buffer.write(collected.stderr);return collected.returncode
    gate=[str(python),str(ROOT/'scripts/check-required-tests.py'),'--pytest-discovery',str(discovery),'--expected-count','2']
    checked=subprocess.run(gate+['--discovery-only'],cwd=ROOT,env=env,timeout=60)
    if checked.returncode:return checked.returncode
    if 'tests/benchmark_mixed_workload_case.py::test_owned_ten_workspaces_thirty_minute_mixed_nonpaid' not in collected.stdout.decode('utf-8'):return 1
    if 'tests/benchmark_mixed_workload_case.py::test_owned_timeout_cleans_cooperative_and_stubborn_processes' not in collected.stdout.decode('utf-8'):return 1
    junit=folder/'tests.xml'
    with owned_runtime(env,folder) as owned_env:
        tested=run_owned_child(command+['-q','--tb=short','--junitxml='+junit.as_posix()],cwd=WORKER,env=owned_env,timeout=2100)
    if tested.returncode:return tested.returncode
    checked=subprocess.run(gate+['--junit',str(junit)],cwd=ROOT,env=env,timeout=60)
    if checked.returncode:return checked.returncode
    capture=json.loads((folder/'capture.json').read_text(encoding='utf-8'))
    if not workload_complete(capture):print('Incomplete sustained denominator; raw evidence retained',file=sys.stderr);return 1
    after=provenance(ROOT,paths)
    with (folder/'provenance-end.json').open('x',encoding='utf-8') as f:json.dump(after,f,indent=2);f.write('\n')
    if not source_capture_unchanged(frozen,after):
        print('Source/runtime changed during capture; raw evidence retained, no candidate acceptance',file=sys.stderr);return 1
    targets=json.loads((folder/'owned-targets.json').read_text(encoding='utf-8'))
    cleanup=json.loads((folder/'owned-target-cleanup.json').read_text(encoding='utf-8'))
    if (len(targets['targets'])!=2 or len(cleanup['receipts'])!=2
        or {x['id'] for x in targets['targets']}!={x['id'] for x in cleanup['receipts']}
        or any(x['returncode']!=0 for x in cleanup['receipts'])):
        print('Owned target cleanup incomplete; raw evidence retained',file=sys.stderr);return 1
    report=dict(schema='buyeros.mixed-workload-report.v1',live_verified=False,release_accepted=False,capture=capture,provenance=frozen,source_capture_stable=True,owned_targets=targets,owned_target_cleanup=cleanup)
    with (folder/'report.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
