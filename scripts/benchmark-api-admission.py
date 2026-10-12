"""Owned short API burst alongside, never replacing, the required30min capture."""
import argparse,importlib.util,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WORKER=ROOT/'services/worker';API=ROOT/'services/api'
sys.path.insert(0,str(API))
from tools.quality_metrics import DATABASE_VARIABLES,provenance
sys.path.insert(0,str(WORKER))
from tests.api_admission_driver import capture_complete
from tests.mixed_workload_cleanup import run_owned_child
spec=importlib.util.spec_from_file_location('mixed_runner',ROOT/'scripts/benchmark-mixed-workload.py')
mixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(mixed)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
    for key in DATABASE_VARIABLES:
        if os.environ.get(key):parser.error('unset inherited database '+key)
    folder=args.output_dir.resolve()
    if folder.exists():parser.error('new output directory required')
    if sys.platform!='linux':parser.error('owned admission runner requires native Linux')
    python=WORKER/'.venv/bin/python'
    if not python.is_file():parser.error('frozen worker/API environment required')
    paths=[Path(__file__),ROOT/'scripts/benchmark-mixed-workload.py',WORKER/'tests/api_admission_driver.py',WORKER/'tests/api_admission_seed.py',WORKER/'tests/mixed_workload_fixture.py',WORKER/'tests/mixed_workload_cleanup.py',WORKER/'tests/broker_recovery_fixture.py',WORKER/'tests/test_contact_uncertainty_db.py',WORKER/'tests/worker_capacity_driver.py',WORKER/'tests/conftest.py',WORKER/'buyeros_worker/tasks.py',WORKER/'tests/benchmark_api_admission_case.py',API/'tests/auth_fixtures.py',API/'tests/conftest.py',API/'buyeros_api/api/app.py',API/'buyeros_api/api/auth.py',API/'buyeros_api/api/deps.py',API/'buyeros_api/api/verifier.py',API/'buyeros_api/api/jwks.py',API/'buyeros_api/api/routes/bulk_manifests.py',API/'buyeros_api/services/bulk_manifest.py',API/'buyeros_api/services/bulk_service.py',API/'buyeros_api/services/identity_resolver.py',API/'buyeros_api/execution/dispatcher.py',API/'buyeros_api/execution/handlers/retention.py',API/'buyeros_api/execution/handlers/bulk_mutate.py']
    assert all(p.is_file() for p in paths)
    folder.mkdir();before=provenance(ROOT,paths);(folder/'provenance-start.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8')
    env=dict(os.environ);env.pop('PYTEST_ADDOPTS',None);env.update(PYTHONUTF8='1',BUYEROS_STRICT_INTEGRATION='1',BUYEROS_OWNED_API_ADMISSION='1',BUYEROS_ADMISSION_OUTPUT=str(folder),BUYEROS_PAID_DISPATCH_ENABLED='false',BUYEROS_DELIVERY_DISPATCH_ENABLED='false')
    command=[str(python),'-m','pytest','tests/benchmark_api_admission_case.py'];d=folder/'discovery.txt';j=folder/'tests.xml'
    collect=subprocess.run(command+['--collect-only','-q'],cwd=WORKER,env=env,capture_output=True,timeout=60);d.write_bytes(collect.stdout)
    if collect.returncode:sys.stderr.buffer.write(collect.stderr);return collect.returncode
    gate=[str(python),str(ROOT/'scripts/check-required-tests.py'),'--pytest-discovery',str(d),'--expected-count','1']
    checked=subprocess.run(gate+['--discovery-only'],cwd=ROOT,env=env,timeout=60)
    if checked.returncode:return checked.returncode
    if 'test_owned_api_admission_tenant_pairs_and_mixed_distribution' not in collect.stdout.decode():return 1
    with mixed.owned_runtime(env,folder) as owned:
        owned['BUYEROS_ADMISSION_BROKER_URL']=owned['BUYEROS_MIXED_BROKER_URL']
        with (folder/'native.log').open('xb') as log:tested=run_owned_child(command+['-q','--tb=short','--junitxml='+j.as_posix()],cwd=WORKER,env=owned,timeout=450,stdout=log,stderr=subprocess.STDOUT)
    if tested.returncode:return tested.returncode
    checked=subprocess.run(gate+['--junit',str(j)],cwd=ROOT,env=env,timeout=60)
    if checked.returncode:return checked.returncode
    capture=json.loads((folder/'capture.json').read_text(encoding='utf-8'))
    if not capture_complete(capture):return 1
    after=provenance(ROOT,paths);(folder/'provenance-end.json').write_text(json.dumps(after,indent=2)+'\n',encoding='utf-8')
    if not mixed.source_capture_unchanged(before,after):return 1
    targets=json.loads((folder/'owned-targets.json').read_text());cleanup=json.loads((folder/'owned-target-cleanup.json').read_text())
    if len(cleanup['receipts'])!=2 or any(x['returncode']!=0 for x in cleanup['receipts']) or {x['id'] for x in targets['targets']}!={x['id'] for x in cleanup['receipts']}:return 1
    report=dict(schema='buyeros.api-admission-report.v1',capture=capture,provenance=before,source_capture_stable=True,owned_targets=targets,owned_target_cleanup=cleanup,live_verified=False,release_accepted=False,limitations='short ASGI/localRS256 owned burst; no real Neon/provider/HK/UAT/adopted SLO; unchanged30min runner separately required')
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8');return 0


if __name__=='__main__':raise SystemExit(main())
