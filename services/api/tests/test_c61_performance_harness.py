"""Frozen owned-matrix gates; all data here is explicitly synthetic."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[3]
SCRIPT=ROOT/'scripts/c61-performance-harness.py'

def tool():
    assert SCRIPT.exists(), 'C61 frozen performance harness is missing'
    spec=importlib.util.spec_from_file_location('c61_performance_harness',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def synthetic():
    reports=[]
    for actors in (1,10,25):
        matrix=[]
        for w in (1,10,100,1000):
            observed=[dict(latency_ms=100.0,sql_ms=10.0,queries=4,bytes=200,status=200,invalid_context=False,actor_index=i,repetition=j,pool_wait_ms=None) for j in range(30) for i in range(actors)]
            matrix.append(dict(total_workspaces=w,actors=actors,visible_memberships_per_actor=1,unrelated_workspaces=w-1,first_after_seed=copy.deepcopy(observed[0]),warmups=copy.deepcopy(observed[:3]),observations=observed,warm={'errors':{'failed_requests':0}}))
        reports.append(dict(schema='buyeros.workspace-directory-benchmark.v1',source_sha='a'*40,tool_hashes={'scripts/benchmark-workspace-directory.py':'1'*64,'services/api/tests/benchmark_workspace_directory_case.py':'2'*64},evidence_mode='owned_disposable_fixture',live_verified=False,release_accepted=False,environment=dict(concurrency=actors,warm_samples_per_actor=30,region='synthetic local loopback',transport='synthetic ASGI',cold_warm='synthetic warm',duration_model='fixed synthetic batches',device='synthetic host',network='synthetic loopback',pool_wait='unmeasured'),role=dict(name='buyeros_api',superuser=False,bypass_rls=False,membership_owner='buyeros',membership_rls=True,schema_head='0047_c61_legacy_source_privacy',postgres_version='16.4'),pool_reuse=dict(verified=True,all_inspected_connections_cleared=True,same_connection_reused=actors==1,workspace_setting_after_return=[''],actor_setting_after_return=[''],retained_pool_connections=[dict(pid=1,workspace_setting='',actor_setting='')],revocation_seen=True,probes=copy.deepcopy(matrix[0]['observations'][:5])),cost=dict(provider_calls=0,paid_resources_created=False),matrix=matrix,directory_gate={'passed':True}))
    budget=dict(owner='synthetic owner declaration',adopted=True,frozen_at='2026-10-06T00:00:00Z',warm_api_p95_ms=800.0,warm_api_p99_ms=1500.0,http_5xx_rate_max=0.01,sql_max=6,tenant_errors_max=0)
    return reports,budget

def test_frozen_matrix_recomputes_raw_denominators_and_never_claims_release():
    reports,budget=synthetic();result=tool().evaluate(reports,budget)
    assert result['directory_gate']['passed'] and result['numerical_gate']['passed']
    assert result['warm_requests']==4320 and len(result['matrix'])==12
    assert all(x['warm']['errors']['denominator']==x['actors']*30 for x in result['matrix'])
    assert all(x['warm']['latency_ms']['p99_stable'] is False for x in result['matrix'])
    assert not result['live_verified'] and not result['release_accepted'] and not result['threshold_adoption_authenticated']
    assert 'pool_wait_unmeasured' in result['remaining_gates'] and not result['c61_25_accepted']
    assert result['provider_calls']==result['database_calls']==0

@pytest.mark.parametrize('change',['500','429','timeout','scope','sql','latency','unadopted','pool','role','missing-actor','missing-stage','missing-report','schema-drift'])
def test_frozen_matrix_never_hides_actual_failures_or_incomplete_coverage(change):
    reports,budget=synthetic();row=reports[0]['matrix'][0]['observations'][0]
    if change=='500': row['status']=500
    if change=='429': row['status']=429
    if change=='timeout': row['status']=None;row['transport_error']='ReadTimeout';row['latency_ms']=10000.0
    if change=='scope': row['invalid_context']=True
    if change=='sql': row['queries']=7
    if change=='latency':
        for x in reports[2]['matrix'][0]['observations']:x['latency_ms']=1600.0
    if change=='unadopted':budget['adopted']=False
    if change=='pool': reports[2]['pool_reuse']['retained_pool_connections'][0]['actor_setting']='other-actor'
    if change=='role':reports[1]['role']['bypass_rls']=True
    if change=='missing-actor':reports[2]['matrix'][0]['observations'].pop()
    if change=='missing-stage':reports[2]['matrix'].pop()
    if change=='missing-report':reports.pop()
    if change=='schema-drift':reports[1]['role']['schema_head']='older'
    result=tool().evaluate(reports,budget)
    assert not result['numerical_gate']['passed'] and result['numerical_gate']['blockers']
    assert result['warm_requests']==sum(len(s['observations']) for r in reports for s in r['matrix'])
    if change in ('500','429','timeout','scope'):
        assert result['matrix'][0]['warm']['errors']['failed_requests']==1
        assert result['matrix'][0]['warm']['errors']['denominator']==30

@pytest.mark.parametrize('change',['duplicate-actor-row','bool-sql','nan-latency','negative-cost','blank-owner','bool-ceiling','loose-sql','loose-p95','bool-tenant','missing-freeze'])
def test_frozen_matrix_rejects_invalid_or_weakened_declarations(change):
    reports,budget=synthetic();row=reports[0]['matrix'][0]['observations'][0]
    if change=='duplicate-actor-row':reports[0]['matrix'][0]['observations'][1]=copy.deepcopy(row)
    if change=='bool-sql':row['queries']=True
    if change=='nan-latency':row['latency_ms']=float('nan')
    if change=='negative-cost':reports[0]['cost']['provider_calls']=-1
    if change=='blank-owner':budget['owner']='  '
    if change=='bool-ceiling':budget['sql_max']=True
    if change=='loose-sql':budget['sql_max']=7
    if change=='loose-p95':budget['warm_api_p95_ms']=900.0
    if change=='bool-tenant':budget['tenant_errors_max']=False
    if change=='missing-freeze':budget['frozen_at']=None
    with pytest.raises(ValueError):tool().evaluate(reports,budget)

def files(tmp_path):
    reports,budget=synthetic();digest=lambda b:hashlib.sha256(b).hexdigest()
    refs=[]
    for i,report in enumerate(reports):
        raw=(json.dumps(report)+'\n').encode();p=tmp_path/f'report-{i}.json';p.write_bytes(raw)
        q=tmp_path/f'suite-{i}.xml';q.write_text('<testsuite><testcase classname="tests.benchmark_workspace_directory_case" name="test_workspace_directory_current_baseline"/></testsuite>')
        refs.append(dict(path=p.name,sha256=digest(raw),junit=q.name,junit_sha256=digest(q.read_bytes())))
    bridge=dict(source_sha='b'*40,parent='a'*40,live_verified=False,release_accepted=False,local_only=True,files=[dict(path=p,tested_sha256=h,LF_normalized_equal=True) for p,h in reports[0]['tool_hashes'].items()])
    p=tmp_path/'bridge.json';p.write_text(json.dumps(bridge));manifest=dict(schema='buyeros.performance-manifest.v1',source_sha='b'*40,source_bridge=dict(path=p.name,sha256=digest(p.read_bytes())),budget=budget,reports=refs)
    p=tmp_path/'manifest.json';p.write_text(json.dumps(manifest));return p,manifest

@pytest.mark.parametrize('change',['current','changed-report','mixed-source','empty-junit','skipped-junit','failed-junit','missing-junit','alias','existing-output'])
def test_frozen_performance_actual_cli_binds_inputs_and_refuses_empty_required_evidence(tmp_path,change):
    tool();manifest,body=files(tmp_path);output=tmp_path/'new.json';expected=0
    if change=='changed-report':(tmp_path/body['reports'][0]['path']).write_text('{}');expected=2
    if change=='mixed-source':
        p=tmp_path/body['reports'][0]['path'];obj=json.loads(p.read_text());obj['source_sha']='c'*40;p.write_text(json.dumps(obj));body['reports'][0]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();expected=2
    if change in ('empty-junit','skipped-junit','failed-junit'):
        p=tmp_path/body['reports'][0]['junit'];p.write_text({'empty-junit':'<testsuite/>','skipped-junit':'<testsuite><testcase><skipped/></testcase></testsuite>','failed-junit':'<testsuite><testcase><failure/></testcase></testsuite>'}[change]);body['reports'][0]['junit_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();expected=1
    if change=='missing-junit':(tmp_path/body['reports'][0]['junit']).unlink();expected=2
    if change=='alias':output=manifest;expected=2
    if change=='existing-output':output.write_text('retain prior evidence');expected=2
    manifest.write_text(json.dumps(body));before={str(p):p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    result=subprocess.run([sys.executable,str(SCRIPT),'--manifest',str(manifest),'--output',str(output)],capture_output=True,text=True)
    assert result.returncode==expected,result.stderr
    assert all(Path(p).read_bytes()==b for p,b in before.items())
    if expected in (0,1):
        report=json.loads(output.read_text());assert not report['live_verified'] and not report['release_accepted'];assert report['provider_calls']==report['database_calls']==0
        assert report['numerical_gate']['passed']==(expected==0)


@pytest.mark.parametrize('change',['revocation','probes'])
def test_frozen_scope_controls_cannot_be_omitted_from_an_otherwise_valid_matrix(change):
    reports,budget=synthetic()
    if change=='revocation':reports[1]['pool_reuse']['revocation_seen']=False
    else:reports[1]['pool_reuse']['probes']=reports[1]['pool_reuse']['probes'][:3]
    assert not tool().evaluate(reports,budget)['numerical_gate']['passed']

@pytest.mark.parametrize('change',['wrong-required-case','mixed-runtime-file'])
def test_frozen_cli_rejects_unrelated_positive_suite_and_mixed_runtime_overlay(tmp_path,change):
    tool();manifest,body=files(tmp_path)
    if change=='wrong-required-case':
        p=tmp_path/body['reports'][0]['junit'];p.write_text('<testsuite><testcase classname="other.module" name="unrelated"/></testsuite>')
        body['reports'][0]['junit_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();expected=1
    else:
        for index in range(3):
            p=tmp_path/body['reports'][index]['path'];row=json.loads(p.read_text());row['tool_hashes']['services/api/buyeros_api/api/deps.py']=str(index+3)*64;p.write_text(json.dumps(row));body['reports'][index]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        expected=2
    manifest.write_text(json.dumps(body));result=subprocess.run([sys.executable,str(SCRIPT),'--manifest',str(manifest),'--output',str(tmp_path/'new.json')],capture_output=True,text=True)
    assert result.returncode==expected,result.stderr


@pytest.mark.parametrize('complete',[True,False])
def test_frozen_pool_wait_coverage_is_measured_without_filling_unknowns(complete):
    reports,budget=synthetic()
    for report in reports:
        for stage in report['matrix']:
            for row in [stage['first_after_seed'],*stage['warmups'],*stage['observations']]:row.update(pool_wait_ms=5.0,pool_queue_gets=2)
    if not complete:reports[0]['matrix'][0]['observations'][0]['pool_wait_ms']=None
    result=tool().evaluate(reports,budget)
    assert result['matrix'][0]['pool_wait_measured'] is complete
    assert ('pool_wait_unmeasured' not in result['remaining_gates']) is complete
    assert result['matrix'][0]['warm']['pool_wait_ms']['denominator']==30
