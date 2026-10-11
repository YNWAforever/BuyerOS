"""Read-only frozen owned directory matrix evaluation; never release acceptance.

Exit0: supplied numerical declarations pass; exit1: written blocked report;
exit2: malformed/changed input or existing/aliased output. No load is generated.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/api'))
from tools.quality_metrics import summarize_requests,write_new_report

TOOL_PATHS=('scripts/benchmark-workspace-directory.py','services/api/tests/benchmark_workspace_directory_case.py')

def integer(value,minimum=0,maximum=None):
    if type(value) is not int or value<minimum or (maximum is not None and value>maximum):
        raise ValueError('invalid integer declaration')
    return value

def bounded(value,maximum):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=maximum:
        raise ValueError('invalid or weakened numerical ceiling')
    return value

def validate_budget(budget):
    if set(budget)!=set(('owner','adopted','frozen_at','warm_api_p95_ms','warm_api_p99_ms','http_5xx_rate_max','sql_max','tenant_errors_max')):
        raise ValueError('unexpected budget fields')
    if type(budget['owner']) is not str or not budget['owner'].strip() or type(budget['adopted']) is not bool:
        raise ValueError('invalid owner or adoption declaration')
    if type(budget['frozen_at']) is not str:
        raise ValueError('missing freeze timestamp')
    frozen=datetime.fromisoformat(budget['frozen_at'].replace('Z','+00:00'))
    if frozen.tzinfo is None or frozen.utcoffset() is None:
        raise ValueError('freeze must have timezone')
    bounded(budget['warm_api_p95_ms'],800);bounded(budget['warm_api_p99_ms'],1500)
    bounded(budget['http_5xx_rate_max'],.01)
    integer(budget['sql_max'],1,6);integer(budget['tenant_errors_max'],0,0)

def evaluate(reports,budget):
    validate_budget(budget)
    blockers=[];directory=[];matrix=[];seen_actors=[];schemas=set();warm_n=0
    for report in reports:
        if report['schema']!='buyeros.workspace-directory-benchmark.v1' or report['evidence_mode']!='owned_disposable_fixture' or report['live_verified'] is not False or report['release_accepted'] is not False:
            raise ValueError('only explicit owned local evidence is supported')
        env=report['environment'];actors=integer(env['concurrency'],1,25)
        if actors not in (1,10,25):raise ValueError('unexpected actor stair')
        if actors in seen_actors:raise ValueError('duplicate actor report')
        seen_actors.append(actors);samples=integer(env['warm_samples_per_actor'],30,100)
        role=report['role'];schemas.add(role['schema_head'])
        if role['name']!='buyeros_api' or role['superuser'] is not False or role['bypass_rls'] is not False or role['membership_owner']==role['name'] or role['membership_rls'] is not True or not str(role['postgres_version']).startswith('16.'):
            directory.append(f'actor{actors}:runtime_role_or_rls')
        pool=report['pool_reuse'];retained=pool['retained_pool_connections']
        settings=pool['workspace_setting_after_return']+pool['actor_setting_after_return']+[row[key] for row in retained for key in ('workspace_setting','actor_setting')]
        if not retained or not settings or any(value not in (None,'') for value in settings) or pool['verified'] is not True or pool['all_inspected_connections_cleared'] is not True or (actors==1 and pool['same_connection_reused'] is not True):
            directory.append(f'actor{actors}:pool_context')
        if len(pool['probes'])!=5 or pool['revocation_seen'] is not True or summarize_requests(pool['probes'])['errors']['failed_requests']:
            directory.append(f'actor{actors}:scope_probe')
        cost=report['cost'];integer(cost['provider_calls'])
        if cost['provider_calls']!=0 or cost['paid_resources_created'] is not False:
            directory.append(f'actor{actors}:unexpected_external_cost')
        stages=report['matrix'];ws=[];query_maxima=[]
        for stage in stages:
            w=integer(stage['total_workspaces'],1);ws.append(w)
            if stage['actors']!=actors or stage['visible_memberships_per_actor']!=1 or stage['unrelated_workspaces']!=w-1:
                directory.append(f'actor{actors}:W{w}:dataset_context')
            raw=stage['observations'];identities=[]
            for row in raw:
                actor=integer(row['actor_index'],0,actors-1);repeat=integer(row['repetition'],0,samples-1)
                identities.append((actor,repeat))
            if len(set(identities))!=len(identities):raise ValueError('duplicate actor/repetition observation')
            if set(identities)!={(actor,repeat) for actor in range(actors) for repeat in range(samples)}:
                directory.append(f'actor{actors}:W{w}:incomplete_warm_coverage')
            warm_n+=len(raw)
            if not raw:
                directory.append(f'actor{actors}:W{w}:empty_observations');continue
            warm=summarize_requests(raw)
            all_rows=[stage['first_after_seed'],*stage['warmups'],*raw]
            total=summarize_requests(all_rows);query_maxima.append(warm['queries']['max'])
            prefix=f'actor{actors}:W{w}'
            if len(stage['warmups'])!=3:directory.append(prefix+':missing_primers')
            if total['errors']['failed_requests']:directory.append(prefix+':failed_request_or_context')
            if total['queries']['max']>budget['sql_max']:directory.append(prefix+':sql_budget')
            if warm['latency_ms']['p95']>budget['warm_api_p95_ms']:blockers.append(prefix+':warm_p95_exceeded')
            if warm['latency_ms']['p99']>budget['warm_api_p99_ms']:blockers.append(prefix+':warm_p99_exceeded')
            if warm['errors']['http_5xx']/warm['requests']>=budget['http_5xx_rate_max']:blockers.append(prefix+':5xx_budget')
            matrix.append(dict(actors=actors,total_workspaces=w,warm=warm,all_requests=total,raw_observations=len(raw),pool_wait_measured=total["pool_wait_ms"]["complete"],environment=env))
        if ws!=[1,10,100,1000]:directory.append(f'actor{actors}:incomplete_workspace_stairs')
        if len(set(query_maxima))!=1:directory.append(f'actor{actors}:sql_growth')
    if sorted(seen_actors)!=[1,10,25]:directory.append('incomplete_actor_stairs')
    if len(schemas)!=1 or not next(iter(schemas),''):directory.append('schema_mismatch_or_absence')
    if not budget['adopted']:blockers.append('budget_adoption_pending')
    blockers=directory+blockers
    pending_pool=[] if matrix and all(row['pool_wait_measured'] for row in matrix) else ['pool_wait_unmeasured']
    return dict(schema='buyeros.performance-report.v1',warm_requests=warm_n,matrix=matrix,budget=budget,directory_gate=dict(passed=not directory,blockers=directory),numerical_gate=dict(passed=not blockers,blockers=blockers),remaining_gates=pending_pool+['list_1k_and_10k','worker_backlog_restart','sustained_actor_stairs','true_cold_hk_preview','rum_cwv','human_uat','authenticated_budget_adoption'],measurement_authenticity_authenticated=False,threshold_adoption_authenticated=False,source_identity_authenticated=False,live_verified=False,release_accepted=False,c61_25_accepted=False,provider_calls=0,database_calls=0,note='Frozen declarations and existing owned raw observations only; no new traffic or external calls. Each stage has its own denominator; n>=1000 is only a p99 heuristic.')

def digest(raw):return hashlib.sha256(raw).hexdigest()

def object_json(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('duplicate JSON field')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('nonfinite JSON number')))

def bound_file(base,reference,path_key='path',hash_key='sha256'):
    expected=reference[hash_key]
    if type(expected) is not str or re.fullmatch('[0-9a-f]{64}',expected) is None:
        raise ValueError('invalid input hash')
    path=(base/reference[path_key]).resolve();raw=path.read_bytes()
    if digest(raw)!=expected:raise ValueError('changed frozen input')
    return path,raw

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    try:
        manifest_path=args.manifest.resolve();base=manifest_path.parent;raw=manifest_path.read_bytes();manifest=object_json(raw)
        if set(manifest)!=set(('schema','source_sha','source_bridge','budget','reports')) or manifest['schema']!='buyeros.performance-manifest.v1' or re.fullmatch('[0-9a-f]{40}',manifest['source_sha']) is None:
            raise ValueError('invalid frozen manifest')
        bridge_path,bridge_raw=bound_file(base,manifest['source_bridge']);bridge=object_json(bridge_raw)
        if bridge['source_sha']!=manifest['source_sha'] or bridge['live_verified'] is not False or bridge['release_accepted'] is not False or bridge['local_only'] is not True or re.fullmatch('[0-9a-f]{40}',bridge['parent']) is None:
            raise ValueError('invalid local source bridge')
        rows={row['path']:row for row in bridge['files']}
        if len(rows)!=len(bridge['files']) or any(path not in rows for path in TOOL_PATHS):raise ValueError('source bridge incomplete')
        protected=[manifest_path,bridge_path];reports=[];suites=[];input_rows=[]
        spec=importlib.util.spec_from_file_location('c61_required_suite',ROOT/'scripts/check-required-tests.py');validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
        for reference in manifest['reports']:
            if set(reference)!=set(('path','sha256','junit','junit_sha256')):raise ValueError('invalid report reference')
            path,report_raw=bound_file(base,reference);junit,junit_raw=bound_file(base,reference,'junit','junit_sha256')
            if path in protected or junit in protected or path==junit:raise ValueError('duplicate evidence input')
            protected.extend((path,junit));report=object_json(report_raw)
            if report['source_sha']!=bridge['parent'] or any(report['tool_hashes'].get(p)!=rows[p]['tested_sha256'] or rows[p]['LF_normalized_equal'] is not True for p in TOOL_PATHS):raise ValueError('mixed measurement source')
            if reports and report['tool_hashes']!=reports[0]['tool_hashes']:
                raise ValueError('mixed runtime file overlay')
            if any(type(h) is not str or re.fullmatch('[0-9a-f]{64}',h) is None for h in report['tool_hashes'].values()):
                raise ValueError('invalid runtime file hash')
            reports.append(report)
            try:
                passed,failed,errors,skipped=validator.summarize(junit)
                cases=list(ET.fromstring(junit_raw).iter('testcase'))
                required=len(cases)==1 and cases[0].get('name')=='test_workspace_directory_current_baseline' and cases[0].get('classname')=='tests.benchmark_workspace_directory_case'
                suite=dict(tests=passed+failed+errors+skipped,passed=passed,failed=failed,errors=errors,skipped=skipped,required_case_discovered=required,valid=required and passed>0 and failed==errors==skipped==0)
            except ValueError:
                suite=dict(tests=0,passed=0,failed=0,errors=0,skipped=0,valid=False)
            suites.append(suite);input_rows.append(dict(report=str(path),sha256=digest(report_raw),junit=str(junit),junit_sha256=digest(junit_raw),suite=suite))
        output=args.output.resolve()
        if output in protected or output.exists():raise ValueError('output must be new and distinct from every input')
        result=evaluate(reports,manifest['budget'])
        if any(not suite['valid'] for suite in suites):
            result['numerical_gate']['passed']=False;result['numerical_gate']['blockers'].append('required_junit_not_positive_zero_fail_error_skip')
        result.update(source_sha=manifest['source_sha'],measurement_source_sha=bridge['parent'],manifest_sha256=digest(raw),source_bridge_sha256=digest(bridge_raw),input_evidence=input_rows)
        write_new_report(output,result,tuple(protected))
        print(json.dumps({'numerical_passed':result['numerical_gate']['passed'],'directory_passed':result['directory_gate']['passed'],'warm_requests':result['warm_requests'],'blockers':result['numerical_gate']['blockers'],'live_verified':False,'release_accepted':False}))
        return 0 if result['numerical_gate']['passed'] else 1
    except (KeyError,TypeError,ValueError,OSError,ET.ParseError):
        print('Invalid, changed, unavailable or aliased frozen performance evidence; no report overwritten.',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
