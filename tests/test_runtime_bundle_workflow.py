"""Owned adapters exercise stage refusals and approval validation without external writes."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))


def controls():
    from test_release_readiness import candidate
    m,_=candidate()
    return dict(source=m['source_sha'], ci_run_id=123, branch={'protected':True,'commit':{'sha':m['source_sha']}},
        protection={'enforce_admins':{'enabled':True},'required_status_checks':{'strict':True,'contexts':m['required_ci_jobs']},
                    'required_pull_request_reviews':{'required_approving_review_count':1,'dismiss_stale_reviews':True}},
        environment={'protection_rules':[{'type':'required_reviewers','prevent_self_review':True,'reviewers':[{'reviewer':{'id':202}}]}],
                     'deployment_branch_policy':{'protected_branches':True,'custom_branch_policies':False},'can_admins_bypass':False},
        project={'id':'prj_owned','accountId':'team_owned','autoAssignCustomDomains':False,
                 'link':{'type':'github','org':'YNWAforever','repo':'BuyerOS','repoId':1234,'productionBranch':'main'}},
        project_id='prj_owned',team_id='team_owned',
        run={'id':123,'head_sha':m['source_sha'],'head_branch':'main','status':'completed','conclusion':'success',
             'path':'.github/workflows/buyeros-ci.yml','repository':{'full_name':'YNWAforever/BuyerOS'}},
        jobs={'total_count':12,'jobs':[{'name':n,'status':'completed','conclusion':'success'} for n in m['required_ci_jobs']]})


def module():
    path=ROOT/'scripts/protected_release.py'
    assert path.is_file(),'protected release controls are absent'
    spec=importlib.util.spec_from_file_location('protected_controls',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_exact_current_main_complete_ci_and_controls_pass():
    assert module().verify_controls(**controls()) is None


@pytest.mark.parametrize('fault',['branch','checks','ci-head','ci-skipped','ci-duplicate','ci-incomplete','repo','team',
                                  'auto-alias','reviewers','self-review-policy','admin-bypass','environment-branch','unreviewed-main'])
def test_stage_refuses_missing_controls_before_deploy(fault):
    c=controls()
    if fault=='branch': c['branch']['protected']=False
    if fault=='checks': c['protection']['required_status_checks']['strict']=False
    if fault=='ci-head': c['run']['head_sha']='0'*40
    if fault=='ci-skipped': c['jobs']['jobs'][0]['conclusion']='skipped'
    if fault=='ci-duplicate': c['jobs']['jobs'][0]['name']=c['jobs']['jobs'][1]['name']
    if fault=='ci-incomplete': c['jobs']['total_count']=13
    if fault=='repo': c['project']['link']['repo']='other'
    if fault=='team': c['project']['accountId']='team_other'
    if fault=='auto-alias': c['project']['autoAssignCustomDomains']=True
    if fault=='reviewers': c['environment']['protection_rules']=[]
    if fault=='self-review-policy': c['environment']['protection_rules'][0]['prevent_self_review']=False
    if fault=='admin-bypass': c['environment']['can_admins_bypass']=True
    if fault=='environment-branch': c['environment']['deployment_branch_policy']['protected_branches']=False
    if fault=='unreviewed-main': c['protection']['required_pull_request_reviews']['required_approving_review_count']=0
    with pytest.raises(ValueError): module().verify_controls(**c)


def approvals(comment=None):
    return [{'state':'approved','user':{'id':202,'login':'owned-reviewer'},
             'environments':[{'name':'buyeros-production-promote','id':88}],
             'comment':comment or 'workspace-canary-pass:'+('a'*40)+':dpl_owned:roles-project-reload-retry'}]


def test_runtime_bundle_requires_verified_nonself_approval_and_bound_canary_comment():
    result=module().verify_approval(approvals(), initiator_id=101, run_id=456, source='a'*40, deployment_id='dpl_owned')
    assert result['reviewer_id']==202 and result['initiator_id']==101 and result['approval_run_id']==456
    assert result['human_signoff'] is True


@pytest.mark.parametrize('fault',['missing','self','comment','environment','rejected','forged-id','multiple'])
def test_runtime_bundle_refuses_unverified_approval(fault):
    value=approvals()
    if fault=='missing': value=[]
    if fault=='self': value[0]['user']['id']=101
    if fault=='comment': value[0]['comment']='workspace-canary-pass:wrong:dpl_wrong:roles-project-reload-retry'
    if fault=='environment': value[0]['environments'][0]['name']='unprotected'
    if fault=='rejected': value[0]['state']='rejected'
    if fault=='forged-id': value[0]['user']['id']='202'
    if fault=='multiple': value.append(copy.deepcopy(value[0]))
    with pytest.raises(ValueError): module().verify_approval(value,initiator_id=101,run_id=456,source='a'*40,deployment_id='dpl_owned')


def test_runtime_bundle_workflow_keeps_private_payload_out_of_logs_and_artifacts():
    path=ROOT/'.github/workflows/buyeros-runtime-bundle.yml'
    assert path.is_file(),'protected bundle workflow absent'
    workflow=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
    jobs=workflow['jobs']
    assert set(jobs)=={'stage-probe','bundle-signoff'}
    assert jobs['stage-probe']['if']=="github.ref == 'refs/heads/main'"
    assert jobs['bundle-signoff']['if']=="github.ref == 'refs/heads/main'"
    assert jobs['stage-probe']['environment']=='buyeros-runtime-readonly'
    assert jobs['bundle-signoff']['environment']['name']=='buyeros-production-promote'
    uploads=[s for j in jobs.values() for s in j['steps'] if s.get('uses','').startswith('actions/upload-artifact@')]
    assert [u['with']['name'] for u in uploads]==['buyeros-private-observations-encrypted','buyeros-attested-runtime']
    assert [u['with']['path'] for u in uploads]==['${{ runner.temp }}/buyeros-stage.encrypted.json','${{ runner.temp }}/runtime-bundle.json']
    attests=[s for s in jobs['bundle-signoff']['steps'] if s.get('uses','').startswith('actions/attest@')]
    assert attests[0]['with']['subject-path']=='${{ runner.temp }}/runtime-bundle.json'
    commands=[s for j in jobs.values() for s in j['steps'] if 'run' in s and 'scripts/' in s['run']]
    assert all('> "$RUNNER_TEMP/' in s['run'] and '2>&1' in s['run'] for s in commands)

def runtime_module():
    path=ROOT/'scripts/protected-runtime.py'
    assert path.is_file()
    spec=importlib.util.spec_from_file_location('protected_runtime_test',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_stage_does_not_deploy_when_remote_controls_fail(tmp_path,monkeypatch):
    runtime=runtime_module();effects=[]
    monkeypatch.setenv('GITHUB_SHA','a'*40)
    monkeypatch.setenv('GITHUB_REF','refs/heads/main')
    monkeypatch.setenv('GITHUB_WORKFLOW','BuyerOS protected runtime bundle')
    monkeypatch.setenv('BUYEROS_ENABLE_PROTECTED_STAGE','true')
    def reject(*args): raise ValueError('PRIVATE_REMOTE_DETAIL')
    monkeypatch.setattr(runtime,'current_controls',reject)
    monkeypatch.setattr(runtime,'command',lambda argv,**kwargs:effects.append(argv))
    output=tmp_path/'bundle.json'
    assert runtime.main(['stage','--ci-run-id','123','--output',str(output)])==2
    assert not output.exists() and effects==[]


def test_stage_is_default_off_before_remote_reads(tmp_path,monkeypatch):
    runtime=runtime_module()
    monkeypatch.setenv('GITHUB_SHA','a'*40)
    monkeypatch.setenv('GITHUB_REF','refs/heads/main')
    monkeypatch.setenv('GITHUB_WORKFLOW','BuyerOS protected runtime bundle')
    monkeypatch.delenv('BUYEROS_ENABLE_PROTECTED_STAGE',raising=False)
    def reject(*args): raise AssertionError('No external reads without explicit staging selection')
    monkeypatch.setattr(runtime,'current_controls',reject)
    with pytest.raises(ValueError): runtime.stage(123,tmp_path/'out.json')


def test_runtime_binding_collector_refuses_a_response_from_other_database():
    from test_release_readiness import candidate
    runtime=runtime_module();binding=runtime.load_script('collect-runtime-binding.py')
    m,_=candidate()
    dsn='postgresql://test:owned@ep-owned.neon.tech/buyer'
    m['db_target_sha256']=runtime.database_target_sha256(dsn)
    good={'schema':'buyeros.runtime-db-binding.v1','source_sha':m['source_sha'],
          'deployment_id':m['candidate_deployment_id'],'schema_head':m['required_heads'][0],
          'db_target_sha256':m['db_target_sha256']}
    for key,value in [('source_sha','0'*40),('deployment_id','dpl_other'),('db_target_sha256','0'*64),('schema_head','wrong')]:
        response={**good,key:value}
        with pytest.raises(ValueError):
            binding.collect_binding(m,'https://owned.vercel.app',dsn,'owned-token-'+'x'*32,get=lambda u,t:(200,response))
    result=binding.collect_binding(m,'https://owned.vercel.app',dsn,'owned-token-'+'x'*32,get=lambda u,t:(200,good))
    assert result['data']['verified'] is True
    assert result['data']['db_target_sha256']==m['db_target_sha256']


def test_runtime_environment_rejects_libpq_target_overrides_and_paid_activation(tmp_path,monkeypatch):
    runtime=runtime_module();path=tmp_path/'production.env'
    monkeypatch.setenv('BUYEROS_RELEASE_PROBE_TOKEN','test-token')
    base='BUYEROS_DATABASE_URL="postgresql://user:pw@ep-owned.neon.tech/buyer"\nBUYEROS_RELEASE_PROBE_TOKEN="test-token"\n'
    path.write_text(base,encoding='utf-8')
    assert runtime.runtime_env(path)['BUYEROS_DATABASE_URL'].endswith('/buyer')
    for key in ('BUYEROS_PAID_ADMISSION_ENABLED','BUYEROS_DELIVERY_ADMISSION_ENABLED','BUYEROS_CLOUDFLARE_EXECUTION_ENABLED'):
        path.write_text(base+key+'="true"\n')
        with pytest.raises(ValueError): runtime.runtime_env(path)
