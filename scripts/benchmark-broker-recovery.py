"""Owned PG16/Valkey8 inflight recovery; refuses all inherited database targets."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/'services/worker'
API=ROOT/'services/api'
sys.path.insert(0,str(API))
from tools.quality_metrics import DATABASE_VARIABLES, provenance
sys.path.insert(0,str(WORKER))
from tests.broker_recovery_driver import CASES, captures_complete


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    for key in DATABASE_VARIABLES:
        if os.environ.get(key):parser.error('unset inherited database '+key+'; owned fixture only')
    folder=args.output_dir.resolve()
    if folder.exists():parser.error('output directory must be new; retain previous evidence')
    python=WORKER/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not python.is_file():parser.error('frozen worker virtual environment required')
    folder.mkdir(parents=True)
    env=dict(os.environ);env.pop('PYTEST_ADDOPTS',None)
    env.update(PYTHONUTF8='1',BUYEROS_STRICT_INTEGRATION='1',BUYEROS_BROKER_RECOVERY_OUTPUT=str(folder))
    case='tests/benchmark_broker_recovery_case.py'
    command=[str(python),'-X','utf8','-m','pytest',case]
    discovery=folder/'discovery.txt'; junit=folder/'tests.xml'
    collected=subprocess.run(command+['--collect-only','-q'],cwd=WORKER,env=env,capture_output=True,timeout=60)
    discovery.write_bytes(collected.stdout)
    if collected.returncode:
        sys.stderr.buffer.write(collected.stderr);return collected.returncode
    gate=[str(python),str(ROOT/'scripts/check-required-tests.py'),'--pytest-discovery',str(discovery),'--expected-count','4']
    checked=subprocess.run(gate+['--discovery-only'],cwd=ROOT,env=env,timeout=60)
    if checked.returncode:return checked.returncode
    tested=subprocess.run(command+['-q','--tb=short','--junitxml='+junit.as_posix()],cwd=WORKER,env=env,timeout=600)
    if tested.returncode:return tested.returncode
    checked=subprocess.run(gate+['--junit',str(junit)],cwd=ROOT,env=env,timeout=60)
    if checked.returncode:return checked.returncode
    captures=[json.loads((folder/name/'capture.json').read_text(encoding='utf-8')) for name in CASES]
    if not captures_complete(captures):
        print('Incomplete broker recovery; all raw evidence retained',file=sys.stderr);return 1
    paths=[Path(__file__),WORKER/case,WORKER/'tests/broker_recovery_driver.py',WORKER/'tests/broker_recovery_fixture.py',
           WORKER/'tests/conftest.py',WORKER/'tests/test_contact_uncertainty_db.py',WORKER/'tests/test_valkey_integration.py',
           WORKER/'tests/worker_capacity_driver.py',WORKER/'buyeros_worker/tasks.py',WORKER/'buyeros_worker/app.py',
           API/'buyeros_api/execution/dispatcher.py',API/'buyeros_api/execution/handlers/contact_submit.py',
           API/'buyeros_api/execution/handlers/reconcile.py',API/'buyeros_api/execution/handlers/retention.py',
           API/'buyeros_api/services/worker_execution.py',API/'buyeros_api/services/contact_result_service.py']
    report=dict(schema='buyeros.owned-broker-recovery.v1',live_verified=False,release_accepted=False,
                evidence_mode='actual_owned_celery_solo_pg16_valkey8_fixture_IO',captures=captures,
                provenance=provenance(ROOT,paths))
    with (folder/'report.json').open('x',encoding='utf-8') as file:json.dump(report,file,indent=2,allow_nan=False);file.write('\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
