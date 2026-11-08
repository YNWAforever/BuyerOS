"""Owned adapters exercise stage refusals and approval validation without external writes."""
import copy
import os
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
                    'required_pull_request_reviews':{'required_approving_review_count':0,'dismiss_stale_reviews':True,'require_last_push_approval':False}},
        environment={'protection_rules':[{'type':'required_reviewers','prevent_self_review':True,'reviewers':[{'reviewer':{'id':202}}]}],
                     'deployment_branch_policy':{'protected_branches':True,'custom_branch_policies':False},'can_admins_bypass':False},
        project={'id':'prj_owned','accountId':'team_owned','autoAssignCustomDomains':False,
                 'link':{'type':'github','org':'YNWAforever','repo':'BuyerOS','repoId':1234,'productionBranch':'main'}},
        project_id='prj_owned',team_id='team_owned',
        run={'id':123,'head_sha':m['source_sha'],'head_branch':'main','status':'completed','conclusion':'success',
             'path':'.github/workflows/buyeros-ci.yml','repository':{'full_name':'YNWAforever/BuyerOS'}},
        jobs={'total_count':len(m['required_ci_jobs']),'jobs':[{'name':n,'status':'completed','conclusion':'success'} for n in m['required_ci_jobs']]})


def module():
    path=ROOT/'scripts/protected_release.py'
    assert path.is_file(),'protected release controls are absent'
    spec=importlib.util.spec_from_file_location('protected_controls',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('pr_approvals',[None,0,1])
def test_exact_current_main_complete_ci_and_controls_pass(pr_approvals):
    c=controls()
    if pr_approvals is None:
        c['protection'].pop('required_pull_request_reviews')
    else:
        c['protection']['required_pull_request_reviews']['required_approving_review_count']=pr_approvals
    assert module().verify_controls(**c) is None


@pytest.mark.parametrize('fault',['branch','checks','ci-head','ci-skipped','ci-duplicate','ci-incomplete','repo','team',
                                  'auto-alias','reviewers','self-review-policy','admin-bypass','environment-branch','admins'])
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
    if fault=='admins': c['protection']['enforce_admins']['enabled']=False
    with pytest.raises(ValueError): module().verify_controls(**c)


def approvals(comment=None):
    return [{'state':'approved','user':{'id':202,'login':'owned-reviewer'},
             'environments':[{'name':'buyeros-production-promote','id':88}],
             'comment':comment or 'workspace-canary-pass:'+('a'*40)+':dpl_owned:roles-project-reload-retry'}]


def test_runtime_bundle_requires_verified_nonself_approval_and_bound_canary_comment():
    result=module().verify_approval(approvals(), initiator_id=101, run_id=456, source='a'*40, deployment_id='dpl_owned')
    assert result['reviewer_id']==202 and result['initiator_id']==101 and result['approval_run_id']==456
    assert result['human_signoff'] is True


def test_explicit_solo_owner_policy_requires_real_bound_owner_approval(monkeypatch):
    monkeypatch.setenv('BUYEROS_RELEASE_REVIEW_POLICY','solo-owner-v1')
    c=controls()
    rule=c['environment']['protection_rules'][0]
    rule.update(prevent_self_review=False,reviewers=[{'type':'User','reviewer':{'id':201698560}}])
    assert module().verify_controls(**c) is None
    value=approvals();value[0]['user']['id']=201698560
    proof=module().verify_approval(value,initiator_id=201698560,run_id=456,source='a'*40,deployment_id='dpl_owned')
    assert proof['review_policy']=='solo-owner-v1'
    assert proof['reviewer_id']==proof['initiator_id']==201698560
    assert proof['release_owner_id']==201698560
    for fault in ('other-reviewer','wrong-comment','missing','rejected'):
        bad=copy.deepcopy(value)
        if fault=='other-reviewer':bad[0]['user']['id']=202
        if fault=='wrong-comment':bad[0]['comment']='approved'
        if fault=='missing':bad=[]
        if fault=='rejected':bad[0]['state']='rejected'
        with pytest.raises(ValueError):module().verify_approval(bad,initiator_id=201698560,run_id=456,source='a'*40,deployment_id='dpl_owned')


@pytest.mark.parametrize('fault',['wrong-owner','extra-reviewer','admin-bypass','missing-reviewer'])
def test_solo_owner_controls_remain_closed(monkeypatch,fault):
    monkeypatch.setenv('BUYEROS_RELEASE_REVIEW_POLICY','solo-owner-v1')
    c=controls();rule=c['environment']['protection_rules'][0]
    rule.update(prevent_self_review=False,reviewers=[{'type':'User','reviewer':{'id':201698560}}])
    if fault=='wrong-owner':rule['reviewers'][0]['reviewer']['id']=202
    if fault=='extra-reviewer':rule['reviewers'].append({'type':'User','reviewer':{'id':202}})
    if fault=='admin-bypass':c['environment']['can_admins_bypass']=True
    if fault=='missing-reviewer':rule['reviewers']=[]
    with pytest.raises(ValueError):module().verify_controls(**c)


def test_unknown_review_policy_is_not_an_escape_hatch(monkeypatch):
    monkeypatch.setenv('BUYEROS_RELEASE_REVIEW_POLICY','skip-review')
    with pytest.raises(ValueError):module().verify_controls(**controls())


def test_solo_owner_receipt_cannot_be_relabelled_as_independent(monkeypatch):
    from runtime_bundle import _human_canary
    monkeypatch.setenv('BUYEROS_RELEASE_REVIEW_POLICY','solo-owner-v1')
    value=approvals();value[0]['user']['id']=201698560
    proof=module().verify_approval(value,initiator_id=201698560,run_id=456,source='a'*40,deployment_id='dpl_owned')
    proof.update(api_observation_sha256='1'*64,schema_observation_sha256='2'*64)
    _human_canary(proof)
    for key in ('review_policy','release_owner_id'):
        bad=proof.copy();bad.pop(key)
        with pytest.raises(ValueError):_human_canary(bad)
    monkeypatch.delenv('BUYEROS_RELEASE_REVIEW_POLICY')
    with pytest.raises(ValueError):_human_canary(proof)


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
    ci=yaml.load((ROOT/'.github/workflows/buyeros-ci.yml').read_text(),Loader=yaml.BaseLoader)
    promotion=yaml.load((ROOT/'.github/workflows/buyeros-promote.yml').read_text(),Loader=yaml.BaseLoader)
    release_jobs=[*jobs.values(),*promotion['jobs'].values(),ci['jobs']['release-readiness']]
    installs=[step['run'] for job in release_jobs for step in job['steps']
              if 'npm install --global vercel@' in step.get('run','')]
    assert installs==['npm install --global vercel@54.17.2']*4
    for job in release_jobs:
        isolated=[step['run'] for step in job['steps'] if step.get('name')=='Install isolated protected curl CLI']
        assert len(isolated)==1
        assert 'npm install --prefix "$RUNNER_TEMP/buyeros-curl-cli" --no-audit --no-fund --package-lock=false vercel@50.28.0' in isolated[0]
        assert 'BUYEROS_VERCEL_CURL_PACKAGE=$RUNNER_TEMP/buyeros-curl-cli/node_modules/vercel' in isolated[0]
        assert '>> "$GITHUB_ENV"' in isolated[0]
        assert 'GITHUB_PATH' not in isolated[0]
    assert any('node scripts/check-vercel-curl-transport.mjs' in step.get('run','')
               for step in ci['jobs']['release-readiness']['steps'])
    assert any(step.get('run')=='node scripts/check-vercel-release-cli.mjs "$(npm root --global)/vercel"'
               for step in ci['jobs']['release-readiness']['steps'])
    assert jobs['stage-probe']['if']=="github.ref == 'refs/heads/main'"
    assert jobs['bundle-signoff']['if']=="github.ref == 'refs/heads/main'"
    assert jobs['stage-probe']['environment']=='buyeros-runtime-readonly'
    assert jobs['bundle-signoff']['environment']['name']=='buyeros-production-promote'
    secret='BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON'
    assert all(secret not in step.get('env',{}) for step in jobs['stage-probe']['steps'])
    signing=next(step for step in jobs['bundle-signoff']['steps'] if 'protected-runtime.py sign' in step.get('run',''))
    assert signing['env'][secret]=='${{ secrets.'+secret+' }}'
    uploads=[s for j in jobs.values() for s in j['steps'] if s.get('uses','').startswith('actions/upload-artifact@')]
    assert [u['with']['name'] for u in uploads]==['buyeros-private-stage-failure-encrypted','buyeros-private-observations-encrypted','buyeros-attested-runtime']
    assert [u['with']['path'] for u in uploads]==['${{ runner.temp }}/buyeros-stage-failure.encrypted.json','${{ runner.temp }}/buyeros-stage.encrypted.json','${{ runner.temp }}/runtime-bundle.json']
    assert uploads[0]['if']=="failure() && steps.stage.outcome == 'failure'"
    assert uploads[0]['with']['retention-days']=='1'
    assert uploads[0]['with']['if-no-files-found']=='ignore'
    attests=[s for s in jobs['bundle-signoff']['steps'] if s.get('uses','').startswith('actions/attest@')]
    assert attests[0]['with']['subject-path']=='${{ runner.temp }}/runtime-bundle.json'
    commands=[s for j in jobs.values() for s in j['steps'] if 'run' in s and 'scripts/' in s['run']]
    assert all('> "$RUNNER_TEMP/' in s['run'] and '2>&1' in s['run'] for s in commands)
    for operation,job in [('stage','stage-probe'),('sign','bundle-signoff')]:
        script=next(s['run'] for s in jobs[job]['steps'] if 'protected-runtime.py '+operation in s.get('run',''))
        lines=[line.strip() for line in script.splitlines()]
        safe='"$RUNNER_TEMP/buyeros-safe-'+operation+'.json"'
        assert lines[0]=='status=0'
        assert '--diagnostics-output '+safe in lines[1]
        if operation=='stage':
            assert '--private-diagnostics-output "$RUNNER_TEMP/buyeros-stage-failure.encrypted.json"' in lines[1]
        assert lines[1].endswith('> "$RUNNER_TEMP/buyeros-'+operation+'.log" 2>&1 || status=$?')
        assert lines[2:]==['if [ "$status" -ne 0 ]; then',
                          'if [ -f '+safe+' ]; then cat '+safe+'; fi',
                          'exit "$status"','fi']

def runtime_module():
    path=ROOT/'scripts/protected-runtime.py'
    assert path.is_file()
    spec=importlib.util.spec_from_file_location('protected_runtime_test',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('phase',['controls_branch','controls_protection','controls_environment',
                                 'controls_project','controls_run','controls_jobs','controls_verify'])
def test_control_failure_diagnostics_are_fixed_and_stop_stage(tmp_path,monkeypatch,capsys,phase):
    import json
    runtime=runtime_module();c=controls();seen=[]
    secret='PRIVATE_TOKEN_HOST_COMMAND_OUTPUT_NEVER_RENDER'
    class PrivateFailure(Exception):
        def __str__(self):raise AssertionError('Exception text must never be inspected')
    monkeypatch.setenv('VERCEL_PROJECT_ID','prj_owned');monkeypatch.setenv('VERCEL_ORG_ID','team_owned')
    monkeypatch.setenv('GITHUB_SHA','a'*40);monkeypatch.setenv('GITHUB_REF','refs/heads/main')
    monkeypatch.setenv('GITHUB_WORKFLOW','BuyerOS protected runtime bundle')
    monkeypatch.setenv('BUYEROS_ENABLE_PROTECTED_STAGE','true')
    summary=tmp_path/'summary';diagnostic=tmp_path/'safe.json';output=tmp_path/'encrypted.json'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    names={'branches/main':'branch','branches/main/protection':'protection',
           'environments/buyeros-production-promote':'environment',
           'actions/runs/123':'run','actions/runs/123/jobs?per_page=100':'jobs'}
    def read(name):
        seen.append(name)
        if 'controls_'+name==phase:raise PrivateFailure(secret)
        return c[name]
    monkeypatch.setattr(runtime,'github',lambda path:read(names[path]))
    monkeypatch.setattr(runtime,'vercel',lambda path:read('project'))
    def verify(**kwargs):
        seen.append('verify')
        if phase=='controls_verify':raise PrivateFailure(secret)
        raise AssertionError('Failed metadata must not reach verification')
    monkeypatch.setattr(runtime,'verify_controls',verify)
    def forbidden(*args,**kwargs):raise AssertionError('No deploy after failed controls')
    monkeypatch.setattr(runtime,'command',forbidden)
    assert runtime.main(['stage','--ci-run-id','123','--output',str(output),
                         '--diagnostics-output',str(diagnostic)])==2
    assert json.loads(diagnostic.read_text())=={'phase':phase,'category':'failed'}
    assert seen[-1]==phase.removeprefix('controls_') and not output.exists()
    captured=capsys.readouterr()
    assert secret not in captured.out+captured.err+summary.read_text()+diagnostic.read_text()
    assert phase+': failed' in summary.read_text()
    for line in summary.read_text().splitlines():
        label,status=line.removeprefix('- ').split(': ')
        assert label in runtime.DIAGNOSTIC_LABELS and status in runtime.DIAGNOSTIC_STATUSES


@pytest.mark.parametrize('kind,category',[('exit','command_nonzero'),('timeout','command_timeout'),('unknown','failed')])
def test_command_diagnostics_never_expose_arguments_or_process_output(tmp_path,monkeypatch,capsys,kind,category):
    import json
    import subprocess
    runtime=runtime_module();secret='SECRET_ARG_STDOUT_STDERR_EXCEPTION'
    errors={'exit':subprocess.CalledProcessError(42,[secret],output=secret,stderr=secret),
            'timeout':subprocess.TimeoutExpired([secret],45,output=secret,stderr=secret),
            'unknown':type(secret,(Exception,),{})(secret)}
    def fail(*args,**kwargs):raise errors[kind]
    monkeypatch.setattr(runtime.subprocess,'run',fail)
    monkeypatch.setattr(runtime,'stage',lambda *args:runtime.checked('stage_deploy',runtime.command,[secret]))
    summary=tmp_path/'summary';diagnostic=tmp_path/'safe.json'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    assert runtime.main(['stage','--output',str(tmp_path/'out'),'--diagnostics-output',str(diagnostic)])==2
    assert json.loads(diagnostic.read_text())=={'phase':'stage_deploy','category':category}
    captured=capsys.readouterr()
    assert secret not in captured.out+captured.err+summary.read_text()+diagnostic.read_text()


def test_unwritable_diagnostics_preserve_original_failure_and_exit(tmp_path,monkeypatch,capsys):
    runtime=runtime_module();error=ValueError('PRIVATE_FAILURE')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(tmp_path))
    def fail(*args):raise error
    with pytest.raises(ValueError) as raised:runtime.checked('stage_pull',fail)
    assert raised.value is error
    monkeypatch.setattr(runtime,'stage',fail)
    assert runtime.main(['stage','--output',str(tmp_path/'out'),'--diagnostics-output',str(tmp_path)])==2
    assert 'PRIVATE_FAILURE' not in capsys.readouterr().out


@pytest.mark.parametrize('code,category',[('401','http_unauthorized'),('403','http_forbidden'),('404','http_not_found')])
def test_metadata_http_categories_publish_only_fixed_labels(tmp_path,monkeypatch,capsys,code,category):
    import json
    import subprocess
    runtime=runtime_module();secret='HOSTILE_SECRET\n::error::DO_NOT_RENDER'
    summary=tmp_path/'summary';monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    for phase in sorted(runtime.GH_METADATA_LABELS):
        def fail(*args):
            raise subprocess.CalledProcessError(1,['gh','api',secret],output=secret,
                                                stderr=secret+' (HTTP '+code+')\n')
        monkeypatch.setattr(runtime,'stage',lambda *args:runtime.checked(phase,fail))
        diagnostic=tmp_path/(phase+'.json')
        assert runtime.main(['stage','--output',str(tmp_path/'out'),'--diagnostics-output',str(diagnostic)])==2
        assert json.loads(diagnostic.read_text())=={'phase':phase,'category':category}
        assert secret not in diagnostic.read_text()
    captured=capsys.readouterr()
    assert secret not in captured.out+captured.err+summary.read_text()
    assert 'DO_NOT_RENDER' not in summary.read_text()


def test_http_classifier_ignores_nonmetadata_commands_and_nonexact_suffixes(tmp_path,monkeypatch):
    import subprocess
    runtime=runtime_module();monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(tmp_path/'summary'))
    cases=[('controls_project',['gh','api'],'PRIVATE (HTTP 403)'),
           ('controls_project',['vercel','api'],'PRIVATE (403) trailing'),
           ('controls_project',['vercel','api'],'PRIVATE (HTTP 403)'),
           ('controls_project',['vercel','deploy'],'PRIVATE (403)'),
           ('stage_deploy',['vercel','api'],'PRIVATE (403)'),
           ('stage_deploy',['gh','api'],'PRIVATE (HTTP 403)'),
           ('controls_branch',['vercel','api'],'PRIVATE (HTTP 403)'),
           ('controls_branch',['gh','api'],'PRIVATE (HTTP 403) trailing'),
           ('controls_branch',['gh','api'],'PRIVATE (HTTP 403)\ntrailing'),
           ('controls_branch',['gh','api'],'PRIVATE (HTTP 500)'),
           ('controls_branch',['gh','api'],b'PRIVATE (HTTP 403)'),
           ('controls_branch',['gh','api'],None)]
    for phase,cmd,stderr in cases:
        error=subprocess.CalledProcessError(1,cmd,stderr=stderr,output='PRIVATE (HTTP 403)')
        def fail():raise error
        runtime._failure_diagnostic=None
        with pytest.raises(subprocess.CalledProcessError) as raised:runtime.checked(phase,fail)
        assert raised.value is error
        assert runtime._failure_diagnostic=={'phase':phase,'category':'command_nonzero'}
    assert 'PRIVATE' not in (tmp_path/'summary').read_text()


def test_vercel_project_forbidden_diagnostic_keeps_private_auth_transport_hidden(tmp_path,monkeypatch,capsys):
    import json
    import subprocess
    runtime=runtime_module();secret='PRIVATE_AUTH_PATH_TOKEN_AND_PROVIDER_TEXT'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(tmp_path/'summary'))
    def fail(*args):
        raise subprocess.CalledProcessError(1,['vercel','api','/v9/projects/private','--global-config',secret],
                                            output=secret,stderr=secret+' (403)\n')
    monkeypatch.setattr(runtime,'stage',lambda *args:runtime.checked('controls_project',fail))
    diagnostic=tmp_path/'safe.json'
    assert runtime.main(['stage','--output',str(tmp_path/'out'),'--diagnostics-output',str(diagnostic)])==2
    assert json.loads(diagnostic.read_text())=={'phase':'controls_project','category':'http_forbidden'}
    captured=capsys.readouterr()
    assert secret not in captured.out+captured.err+diagnostic.read_text()+(tmp_path/'summary').read_text()


def test_success_writes_no_failure_report_and_resets_previous_failure(tmp_path,monkeypatch):
    runtime=runtime_module();diagnostic=tmp_path/'safe.json'
    runtime._failure_diagnostic={'phase':'stage_deploy','category':'command_nonzero'}
    monkeypatch.setattr(runtime,'stage',lambda *args:None)
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(tmp_path/'summary'))
    private=tmp_path/'private.json'
    assert runtime.main(['stage','--output',str(tmp_path/'out'),'--diagnostics-output',str(diagnostic),
                         '--private-diagnostics-output',str(private)])==0
    assert not private.exists() and not diagnostic.exists() and runtime._failure_diagnostic is None


def decrypt_failure_fixture(envelope,key='3'*64,source='a'*40,run='456'):
    import base64
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    binding={'schema':'buyeros.runtime-failure.encrypted.v1','source_sha':source,'run_id':run}
    aad=json.dumps(binding,sort_keys=True,separators=(',',':')).encode('ascii')
    return json.loads(AESGCM(bytes.fromhex(key)).decrypt(base64.b64decode(envelope['nonce']),
        base64.b64decode(envelope['ciphertext']),aad))


def test_private_pull_failure_is_bounded_encrypted_and_never_deploys(tmp_path,monkeypatch,capsys):
    import base64
    import json
    import subprocess
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    marker='PRIVATE_STDERR_DATABASE_SECRET'
    stderr=marker+'é'*70000
    original=runtime.command
    def command(argv,**kwargs):
        if argv[:2]==['vercel','pull']:
            raise subprocess.CalledProcessError(9,['PRIVATE_ARG'],output='PRIVATE_STDOUT',stderr=stderr)
        return original(argv,**kwargs)
    monkeypatch.setattr(runtime,'command',command)
    monkeypatch.setenv('BUYEROS_RUNTIME_DIAGNOSTIC_ENCRYPTION_KEY','3'*64)
    summary=tmp_path/'summary';safe=tmp_path/'safe.json';private=tmp_path/'private.json'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    assert runtime.main(['stage','--ci-run-id','123','--output',str(output),
        '--diagnostics-output',str(safe),'--private-diagnostics-output',str(private)])==2
    envelope=json.loads(private.read_text())
    assert set(envelope)=={'schema','source_sha','run_id','nonce','ciphertext'}
    assert envelope['source_sha']=='a'*40 and envelope['run_id']=='456'
    payload=decrypt_failure_fixture(envelope)
    assert set(payload)=={'phase','category','exit_code','stderr_base64'}
    assert payload['phase']=='stage_pull' and payload['category']=='command_nonzero' and payload['exit_code']==9
    assert base64.b64decode(payload['stderr_base64'])==stderr.encode()[:65536]
    captured=capsys.readouterr()
    public=captured.out+captured.err+summary.read_text()+safe.read_text()+private.read_text()
    for value in (marker,'PRIVATE_ARG','PRIVATE_STDOUT'):assert value not in public
    assert not output.exists() and not any(call[:2]==['vercel','deploy'] for call in calls)
    assert not list(tmp_path.glob('.runtime-failure-*'))
    assert runtime._private_failure is None
    from runtime_bundle import decrypt_observation_packet,decrypt_workspace_bundle
    for decrypt in (decrypt_observation_packet,decrypt_workspace_bundle):
        with pytest.raises(ValueError):decrypt(envelope,'3'*64)


@pytest.mark.parametrize('fault',['key','source','run','ciphertext','nonce'])
def test_private_failure_authentication_rejects_wrong_binding_and_tampering(fault):
    import base64
    from cryptography.exceptions import InvalidTag
    from runtime_failure_diagnostic import encrypt_failure
    envelope=encrypt_failure({'phase':'stage_pull','category':'command_nonzero','exit_code':1,'stderr':b'PRIVATE'},'3'*64,'a'*40,'456')
    options={}
    if fault=='key':options['key']='4'*64
    if fault=='source':options['source']='b'*40
    if fault=='run':options['run']='457'
    if fault in ('ciphertext','nonce'):
        raw=bytearray(base64.b64decode(envelope[fault]));raw[0]^=1
        envelope[fault]=base64.b64encode(raw).decode()
    with pytest.raises(InvalidTag):decrypt_failure_fixture(envelope,**options)


@pytest.mark.parametrize('fault',['missing-key','bad-key','bad-source','bad-run','existing-file','missing-directory'])
def test_private_diagnostic_failure_never_masks_original_exit(tmp_path,monkeypatch,capsys,fault):
    import subprocess
    runtime=runtime_module()
    monkeypatch.setenv('GITHUB_SHA','a'*40);monkeypatch.setenv('GITHUB_RUN_ID','456')
    monkeypatch.setenv('BUYEROS_RUNTIME_DIAGNOSTIC_ENCRYPTION_KEY','3'*64)
    if fault=='missing-key':monkeypatch.delenv('BUYEROS_RUNTIME_DIAGNOSTIC_ENCRYPTION_KEY')
    if fault=='bad-key':monkeypatch.setenv('BUYEROS_RUNTIME_DIAGNOSTIC_ENCRYPTION_KEY','PRIVATE_INVALID_KEY')
    if fault=='bad-source':monkeypatch.setenv('GITHUB_SHA','PRIVATE_INVALID_SOURCE')
    if fault=='bad-run':monkeypatch.setenv('GITHUB_RUN_ID','PRIVATE_INVALID_RUN')
    private=tmp_path/'private.json'
    if fault=='existing-file':private.write_text('original evidence')
    if fault=='missing-directory':private=tmp_path/'absent'/'private.json'
    def fail(*args):raise subprocess.CalledProcessError(7,['PRIVATE_ARG'],stderr=b'PRIVATE_STDERR')
    monkeypatch.setattr(runtime,'stage',lambda *args:runtime.checked('stage_pull',fail))
    assert runtime.main(['stage','--output',str(tmp_path/'out'),'--private-diagnostics-output',str(private)])==2
    if fault=='existing-file':assert private.read_text()=='original evidence'
    else:assert not private.exists()
    assert not list(tmp_path.glob('.runtime-failure-*'))
    captured=capsys.readouterr();assert 'PRIVATE' not in captured.out+captured.err


@pytest.mark.parametrize('kind',['empty','unknown','timeout'])
def test_only_captured_subprocess_stderr_creates_private_evidence(tmp_path,monkeypatch,kind):
    import json
    import subprocess
    runtime=runtime_module()
    monkeypatch.setenv('GITHUB_SHA','a'*40);monkeypatch.setenv('GITHUB_RUN_ID','456')
    monkeypatch.setenv('BUYEROS_RUNTIME_DIAGNOSTIC_ENCRYPTION_KEY','3'*64)
    class PrivateError(Exception):
        def __str__(self):raise AssertionError('must never stringify')
    errors={'empty':subprocess.CalledProcessError(1,['PRIVATE'],stderr=None,output='PRIVATE'),
            'unknown':PrivateError('PRIVATE'),'timeout':subprocess.TimeoutExpired(['PRIVATE'],45,stderr=b'captured timeout')}
    def fail(*args):raise errors[kind]
    monkeypatch.setattr(runtime,'stage',lambda *args:runtime.checked('stage_pull',fail))
    private=tmp_path/'private.json'
    assert runtime.main(['stage','--output',str(tmp_path/'out'),'--private-diagnostics-output',str(private)])==2
    if kind=='timeout':
        payload=decrypt_failure_fixture(json.loads(private.read_text()))
        assert payload['exit_code'] is None and payload['phase']=='stage_pull' and payload['category']=='command_timeout'
    else:assert not private.exists()


def test_diagnostic_vocabulary_rejects_untrusted_labels_without_running_operation(tmp_path,monkeypatch):
    runtime=runtime_module();summary=tmp_path/'summary'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    runtime.safe_summary('PRIVATE_LABEL','failed');runtime.safe_summary('stage','PRIVATE_STATUS')
    with pytest.raises(ValueError):runtime.checked('PRIVATE_LABEL',lambda:pytest.fail('must not run'))
    assert not summary.exists()


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


def test_unreadable_vercel_secrets_use_protected_bindings(tmp_path,monkeypatch):
    runtime=runtime_module();path=tmp_path/'production.env'
    path.write_text('BUYEROS_DATABASE_URL=""\nBUYEROS_RELEASE_PROBE_TOKEN=""\n')
    monkeypatch.setenv('BUYEROS_SCHEMA_CHECK_DATABASE_URL','postgresql://buyeros_api:fixture@ep-owned.neon.tech/buyer')
    monkeypatch.setenv('BUYEROS_RELEASE_PROBE_TOKEN','owned-probe-token')
    values=runtime.runtime_env(path)
    assert values['BUYEROS_DATABASE_URL']==os.environ['BUYEROS_SCHEMA_CHECK_DATABASE_URL']
    assert values['BUYEROS_RELEASE_PROBE_TOKEN']=='owned-probe-token'
    monkeypatch.delenv('BUYEROS_SCHEMA_CHECK_DATABASE_URL')
    with pytest.raises(ValueError):runtime.runtime_env(path)


def test_pinned_vercel_export_values_match_build_reader_without_json_or_expansion(tmp_path,monkeypatch):
    from vercel_env import parse_pulled_environment
    # Exact CLI 50.28 escapeValue and line wrapper; synthetic inputs only.
    cases={
        'CORS':('["https://qa.example.test"]','["https://qa.example.test"]'),
        'QUOTES':('say "hello"','say "hello"'),
        'DOLLARS':('$HOME ${TOKEN} $(whoami)','$HOME ${TOKEN} $(whoami)'),
        'ESCAPED_DOLLAR':('\\$TOKEN','\\$TOKEN'),
        'BACKSLASH':('C:\\temp\\file','C:\\temp\\file'),
        'SLASH_QUOTE':('a\\"b','a\\"b'),
        'LF':('a\nb','a\nb'),'CR':('a\rb','a\\rb'),
        'CRLF':('a\r\nb','a\\r\nb'),
        'LITERAL_N':('a\\nb','a\nb'),'LITERAL_R':('a\\rb','a\\rb'),
        'DOUBLE_SLASH_N':('a\\\\nb','a\\\nb'),
        'TAB':('a\tb','a\tb'),'PADDED':('  padded  ','padded'),
        'HASH_EQUALS':('a#b=c','a#b=c'),'EMPTY':('',''),
        'UNICODE':('a香港b','a香港b'),
        'BOM':('\ufeffpadded\ufeff','padded'),
        'NEL':('\u0085preserved\u0085','\u0085preserved\u0085'),
        'CONTROLS':('\u001c\u001d\u001e\u001fpreserved\u001c\u001d\u001e\u001f',
                    '\u001c\u001d\u001e\u001fpreserved\u001c\u001d\u001e\u001f'),
        'JS_SPACES':('\u00a0\u1680\u2000\u200a\u202f\u205f\u3000padded\u3000','padded'),
        'MONGOLIAN':('\u180epreserved\u180e','\u180epreserved\u180e'),
    }
    monkeypatch.setenv('TOKEN','MUST_NOT_INTERPOLATE')
    content='# Created by Vercel CLI\n'+''.join(
        key+'="'+value.replace('\n','\\n').replace('\r','\\r')+'"\n'
        for key,(value,expected) in cases.items())
    path=tmp_path/'pulled.env';path.write_text(content,encoding='utf-8')
    assert parse_pulled_environment(path)=={key:expected for key,(_,expected) in cases.items()}


@pytest.mark.parametrize('content',[
    'LOWERcase="PRIVATE"\n','A.B="PRIVATE"\n','A-B="PRIVATE"\n','1A="PRIVATE"\n',
    'A="PRIVATE"\nA="other"\n','A=PRIVATE\n','A="PRIVATE\n',
    'A=PRIVATE"\n',"A='PRIVATE'\n",'A="PRIVATE" trailing\n',
    'A="PRIVATE\ncontinued"\n','A="PRIVATE\x00"\n',
    'A="PRIVATE\u2028continued"\n','A="PRIVATE\u2029continued"\n',
])
def test_pulled_environment_rejects_ambiguous_export_with_fixed_error(tmp_path,content):
    from vercel_env import parse_pulled_environment
    path=tmp_path/'pulled.env';path.write_text(content,encoding='utf-8')
    with pytest.raises(ValueError) as caught:parse_pulled_environment(path)
    assert str(caught.value)=='invalid production environment file'


def test_runtime_environment_accepts_raw_nested_cors_quotes_and_preserves_probe_dollar(tmp_path,monkeypatch):
    import json
    runtime=runtime_module();path=tmp_path/'pulled.env'
    probe='owned-\\$TOKEN-"quoted"'
    monkeypatch.setenv('BUYEROS_RELEASE_PROBE_TOKEN',probe)
    path.write_text('# Created by Vercel CLI\n'
        'BUYEROS_DATABASE_URL="postgresql://user:pw@ep-owned.neon.tech/buyer"\n'
        'BUYEROS_CORS_ORIGINS="["https://qa.example.test"]"\n'
        'BUYEROS_RELEASE_PROBE_TOKEN="'+probe+'"\n',encoding='utf-8')
    values=runtime.runtime_env(path)
    assert json.loads(values['BUYEROS_CORS_ORIGINS'])==['https://qa.example.test']
    assert values['BUYEROS_RELEASE_PROBE_TOKEN']==probe


def test_readable_production_binding_cannot_be_overridden(tmp_path,monkeypatch):
    runtime=runtime_module();path=tmp_path/'production.env'
    path.write_text('BUYEROS_DATABASE_URL="postgresql://user:fixture@ep-actual.neon.tech/buyer"\nBUYEROS_RELEASE_PROBE_TOKEN="actual-token"\n')
    monkeypatch.setenv('BUYEROS_SCHEMA_CHECK_DATABASE_URL','postgresql://user:fixture@ep-other.neon.tech/buyer')
    monkeypatch.setenv('BUYEROS_RELEASE_PROBE_TOKEN','wrong-token')
    with pytest.raises(ValueError):runtime.runtime_env(path)

def test_binding_collector_refuses_changed_effective_configuration():
    from test_release_readiness import candidate
    runtime=runtime_module();collector=runtime.load_script('collect-runtime-binding.py');manifest,_=candidate()
    observed={'schema':'buyeros.runtime-configuration.v1','source_sha':manifest['source_sha'],
              'deployment_id':manifest['candidate_deployment_id'],'configuration_sha256':manifest['configuration_sha256'],
              'activation':{'providers':'disabled','worker':'disabled','delivery':'disabled','contact_enrichment':'unconfigured'}}
    receipt=collector.collect_configuration(manifest,'https://owned.vercel.app','owned-token-'+'x'*32,get=lambda u,t:(200,observed))
    assert receipt['data']['activation']['worker']=='disabled'
    for key in ('providers','worker','delivery','contact_enrichment'):
        changed={**observed,'activation':{**observed['activation'],key:'active'}}
        with pytest.raises(ValueError): collector.collect_configuration(manifest,'https://owned.vercel.app','owned-token-'+'x'*32,get=lambda u,t:(200,changed))
    changed={**observed,'configuration_sha256':'0'*64}
    with pytest.raises(ValueError): collector.collect_configuration(manifest,'https://owned.vercel.app','owned-token-'+'x'*32,get=lambda u,t:(200,changed))


def owned_stage(tmp_path, monkeypatch, deployment_policy=False,auth_mode='auth0'):
    """Run real stage orchestration with only external CLI/HTTP/DB adapters replaced."""
    import json
    from types import SimpleNamespace
    from test_release_readiness import candidate
    from test_runtime_observation_packet import schema_contract
    from test_workspace_runtime_observations import packet, TOKENS
    from runtime_bundle_fixtures import api_observation
    runtime=runtime_module()
    _,receipts=candidate()
    account=packet();schema=schema_contract()
    dsn='postgresql://user:pw@ep-owned.neon.tech/owned'
    schema['target']['endpoint_sha256']=runtime.database_endpoint_sha256(dsn)
    schema['target_receipt']=copy.deepcopy(schema['target'])
    parsed_schema=runtime.SchemaContract.model_validate(schema)
    observed_schema=copy.deepcopy(receipts['items']['schema']['data'])
    observed_schema['contract_sha256']=runtime.digest(parsed_schema.model_dump(mode='json',by_alias=True))
    reads=runtime.load_script('collect-workspace-observations.py')
    observed_api=api_observation('a'*40,receipts['items']['schema']['checked_at'])
    monkeypatch.setattr(reads,'collect',lambda *args:copy.deepcopy(observed_api))
    collector=SimpleNamespace(collect_binding=lambda *args:copy.deepcopy(receipts['items']['deployment_binding']),
        collect_configuration=lambda *args:copy.deepcopy(receipts['items']['runtime_configuration']))
    monkeypatch.setattr(runtime,'load_script',lambda name:reads if name=='collect-workspace-observations.py' else collector)
    async def observe(*args): return copy.deepcopy(observed_schema)
    monkeypatch.setattr(runtime,'schema_observation',observe)
    monkeypatch.setattr(runtime,'current_controls',lambda *args:controls())
    monkeypatch.setattr(runtime,'ROOT',tmp_path)
    values={'GITHUB_SHA':'a'*40,'GITHUB_REF':'refs/heads/main','GITHUB_WORKFLOW':'BuyerOS protected runtime bundle',
        'BUYEROS_ENABLE_PROTECTED_STAGE':'true','GITHUB_RUN_ID':'456','GITHUB_OUTPUT':str(tmp_path/'github-output'),
        'BUYEROS_G0_TARGET_JSON':json.dumps(account),'BUYEROS_SCHEMA_CONTRACT_JSON':json.dumps(schema),
        'BUYEROS_G0_CONTRACT_SHA256':runtime.digest(account),
        'BUYEROS_SCHEMA_CONTRACT_SHA256':runtime.digest(parsed_schema.model_dump(mode='json',by_alias=True)),
        'BUYEROS_RUNTIME_READ_SCOPE_SHA256':account['authorization_reference_sha256'],
        'BUYEROS_RELEASE_PROBE_TOKEN':'owned-probe-token','BUYEROS_ROLLBACK_DEPLOYMENT_ID':'dpl_rollback',
        'BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY':'1'*64,
        **{'BUYEROS_G0_'+key.upper()+'_TOKEN':token for key,token in TOKENS.items()}}
    for key,value in values.items(): monkeypatch.setenv(key,value)
    candidate_deployment={'id':'dpl_candidate','projectId':'prj_owned','ownerId':'team_owned','target':'production',
        'readyState':'READY','url':'owned-candidate.vercel.app','aliasAssigned':True,'alias':[],
        'meta':{'githubCommitSha':'a'*40,'githubCommitOrg':'YNWAforever','githubCommitRepo':'BuyerOS','githubCommitRepoId':'1234'},
        'services':[{'name':'app'},{'name':'api'}],
        'lambdas':[{'readyState':'READY','output':[{'functionName':'app'},{'functionName':'api'}]}]}
    if deployment_policy!='absent': candidate_deployment['autoAssignCustomDomains']=deployment_policy
    rollback={**copy.deepcopy(candidate_deployment),'id':'dpl_rollback','url':'owned-rollback.vercel.app'}
    def read_vercel(path):
        if path=='/v4/aliases/buyer-os-nu.vercel.app?teamId=team_owned':
            return {'alias':'buyer-os-nu.vercel.app','deploymentId':'dpl_rollback'}
        if path=='/v2/deployments/dpl_candidate/aliases?teamId=team_owned': return {'aliases':[]}
        if '/dpl_rollback?' in path: return copy.deepcopy(rollback)
        assert '/dpl_candidate?' in path or '/owned-candidate.vercel.app?' in path
        return copy.deepcopy(candidate_deployment)
    monkeypatch.setattr(runtime,'vercel',read_vercel)
    calls=[]
    def command(argv,**kwargs):
        calls.append(argv)
        if argv[:2]==['vercel','pull']:
            path=tmp_path/'.vercel/.env.production.local';path.parent.mkdir()
            path.write_text('BUYEROS_DATABASE_URL='+json.dumps(dsn)+'\nBUYEROS_RELEASE_PROBE_TOKEN="owned-probe-token"\n'
                +('BUYEROS_AUTH_MODE='+json.dumps(auth_mode)+'\n' if auth_mode is not None else ''))
            return ''
        if argv[:2]==['vercel','build']: return ''
        if argv[:2]==['vercel','deploy']:
            assert '--skip-domain' in argv
            assert ['--env','BUYEROS_NEON_STAGED_ORIGIN_ENABLED=1']==argv[argv.index('BUYEROS_NEON_STAGED_ORIGIN_ENABLED=1')-1:argv.index('BUYEROS_NEON_STAGED_ORIGIN_ENABLED=1')+1]
            assert 'BUYEROS_RUNTIME_SOURCE_SHA='+('a'*40) in argv
            return 'https://owned-candidate.vercel.app\n'
        assert argv==['git','rev-parse',('a'*40)+'^{tree}']
        return ('b'*40)+'\n'
    monkeypatch.setattr(runtime,'command',command)
    return runtime,candidate_deployment,calls,tmp_path/'stage.encrypted.json'


@pytest.mark.parametrize('alias_assigned',[False,True])
@pytest.mark.parametrize('deployment_policy',['absent',False],ids=['optional-field-absent','explicitly-disabled'])
def test_stage_accepts_native_deployment_with_reviewed_project_policy(tmp_path,monkeypatch,deployment_policy,alias_assigned):
    import json
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch,deployment_policy)
    deployed['aliasAssigned']=alias_assigned
    runtime.stage(123,output)
    packet=runtime.decrypt_observation_packet(json.loads(output.read_text()),'1'*64)
    assert packet['files']['manifest.json']['candidate_deployment_id']=='dpl_candidate'
    assert packet['files']['manifest.json']['activation']=={'auth':'auth0','providers':'disabled','worker':'disabled','delivery':'disabled'}
    assert len([call for call in calls if call[:2]==['vercel','deploy']])==1
    assert not (tmp_path/'.vercel/.env.production.local').exists()
    assert 'postgresql://' not in output.read_text()


@pytest.mark.parametrize('phase',['stage_rollback_probe','stage_api_probe'])
def test_failed_api_observation_never_reports_probe_passed(tmp_path,monkeypatch,phase):
    import json
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    reads=runtime.load_script('collect-workspace-observations.py');original=reads.collect
    def collect(packet,tokens,origin):
        result=original(packet,tokens,origin)
        if ('owned-rollback' in origin)==(phase=='stage_rollback_probe'):
            result['all_checks_passed']=False
        return result
    monkeypatch.setattr(reads,'collect',collect)
    summary=tmp_path/'summary';diagnostic=tmp_path/'safe.json'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(summary))
    assert runtime.main(['stage','--ci-run-id','123','--output',str(output),
                         '--diagnostics-output',str(diagnostic)])==2
    assert json.loads(diagnostic.read_text())=={'phase':phase,'category':'failed'}
    assert phase+': failed' in summary.read_text()
    assert phase+': passed' not in summary.read_text()
    assert not output.exists()
    assert len([call for call in calls if call[:2]==['vercel','deploy']])==(phase=='stage_api_probe')


@pytest.mark.parametrize('auth_mode,expected',[(None,'neon'),('auth0','auth0'),('neon','neon'),('dual','dual')])
def test_stage_records_effective_auth_mode_without_consuming_neon_receipt(auth_mode,expected,tmp_path,monkeypatch):
    import json
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch,auth_mode=auth_mode)
    monkeypatch.setenv('BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON','invalid JSON must not be consumed by stage')
    runtime.stage(123,output)
    packet=runtime.decrypt_observation_packet(json.loads(output.read_text()),'1'*64)
    assert packet['files']['manifest.json']['activation']['auth']==expected
    assert 'neon-receipt.json' not in packet['files']


def test_stage_omitted_auth_mode_can_publish_before_neon_acceptance(tmp_path,monkeypatch):
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch,auth_mode=None)
    monkeypatch.delenv('BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON',raising=False)
    runtime.stage(123,output)
    assert output.exists()
    assert not (tmp_path/'.vercel/.env.production.local').exists()


@pytest.mark.parametrize('fault',['assigned','assignment-unproven','malformed-alias','alias-error','auto-assigned','malformed-auto-assignment'])
def test_stage_refuses_assigned_or_unproven_candidate_aliases(tmp_path,monkeypatch,fault):
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    if fault=='assigned': deployed['alias']=['unexpected.example.com']
    if fault=='assignment-unproven': deployed.pop('alias')
    if fault=='malformed-alias': deployed['alias']=None
    if fault=='alias-error': deployed['aliasError']={'code':'failed'}
    if fault=='auto-assigned': deployed['autoAssignCustomDomains']=True
    if fault=='malformed-auto-assignment': deployed['autoAssignCustomDomains']=None
    with pytest.raises(ValueError,match='unexpectedly assigned aliases'): runtime.stage(123,output)
    assert not output.exists()
    assert not (tmp_path/'.vercel/.env.production.local').exists()


@pytest.mark.parametrize('auth_mode',['neon','dual'])
@pytest.mark.parametrize('fault',['valid','missing','deployment_id','source_sha','tree_sha',
                                  'configuration_sha256','db_target_sha256','stale','unaccepted',
                                  'approval-missing','late-alias','late-canonical'])
def test_sign_requires_separate_exact_fresh_neon_acceptance(tmp_path,monkeypatch,auth_mode,fault):
    """Exercise signing and the real compose/evaluate gates with synthetic evidence."""
    import json
    from types import SimpleNamespace
    from test_runtime_bundle import private_inputs
    from runtime_bundle import decrypt_workspace_bundle
    runtime=runtime_module()
    manifest=private_inputs(tmp_path)
    manifest['activation']['auth']=auth_mode
    files={path.name:json.loads(path.read_text()) for path in tmp_path.glob('*.json')}
    files['manifest.json']=manifest
    files['rollback-receipt.json']=files.pop('protected-receipts.json')['items']['rollback']
    files['rollback-receipt.json']['data']['deployment_id']='dpl_rollback'
    receipt={**runtime.common(manifest),'data':{'accepted':True,'neon_only_rollback_verified':True}}
    # A legacy packet receipt must never substitute for the protected signing input.
    files['neon-receipt.json']=copy.deepcopy(receipt)
    packet={'schema':'buyeros.private-runtime-observations.v1','source_sha':manifest['source_sha'],
            'origin':'https://owned.vercel.app','files':files,'stage_run_id':456}
    stage_file=tmp_path/'stage.encrypted.json'
    runtime.write_encrypted(stage_file,runtime.encrypt_observation_packet(packet,'1'*64))
    env={'GITHUB_SHA':manifest['source_sha'],'GITHUB_REF':'refs/heads/main',
         'GITHUB_WORKFLOW':'BuyerOS protected runtime bundle','GITHUB_RUN_ID':'456',
         'BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY':'1'*64,
         'BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY':'2'*64,'BUYEROS_RELEASE_PROBE_TOKEN':'owned-test-probe'}
    for key,value in env.items():monkeypatch.setenv(key,value)
    monkeypatch.delenv('BUYEROS_RELEASE_REVIEW_POLICY',raising=False)
    monkeypatch.setattr(runtime,'current_controls',lambda *args:controls())
    events=[]
    candidate={'id':manifest['candidate_deployment_id'],'alias':[],'aliasAssigned':True}
    monkeypatch.setattr(runtime,'deployment',lambda *args:(copy.deepcopy(candidate),packet['origin']))
    def vercel(path):
        assert 'approved' in events
        events.append(path)
        if '/v2/deployments/' in path:
            return {'aliases':['unexpected.example.com'] if fault=='late-alias' else []}
        assert path=='/v4/aliases/buyer-os-nu.vercel.app?teamId=team_owned'
        return {'alias':'buyer-os-nu.vercel.app','deploymentId':'dpl_other' if fault=='late-canonical' else 'dpl_rollback'}
    monkeypatch.setattr(runtime,'vercel',vercel)
    verify=runtime.verify_approval
    def approve(*args,**kwargs):
        result=verify(*args,**kwargs)
        events.append('approved')
        return result
    monkeypatch.setattr(runtime,'verify_approval',approve)
    monkeypatch.setattr(runtime,'load_script',lambda name:SimpleNamespace(collect_configuration=lambda *args:None))
    comment='workspace-canary-pass:'+manifest['source_sha']+':'+manifest['candidate_deployment_id']+':roles-project-reload-retry'
    monkeypatch.setattr(runtime,'github',lambda path:([] if fault=='approval-missing' else approvals(comment)) if path.endswith('/approvals')
        else {'run_attempt':1,'triggering_actor':{'id':101},'id':456})
    if fault=='deployment_id':receipt[fault]='dpl_other'
    if fault in ('source_sha','tree_sha'):receipt[fault]='0'*40
    if fault in ('configuration_sha256','db_target_sha256'):receipt[fault]='0'*64
    if fault=='stale':receipt['checked_at']='2020-01-01T00:00:00Z'
    if fault=='unaccepted':receipt['data']['accepted']=False
    if fault=='missing':monkeypatch.delenv('BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON',raising=False)
    else:monkeypatch.setenv('BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON',json.dumps(receipt))
    output=tmp_path/'signed.encrypted.json'
    if fault=='valid':
        runtime.sign(stage_file,output)
        bundle=decrypt_workspace_bundle(json.loads(output.read_text()),'2'*64)
        assert bundle['receipts']['items']['neon']==receipt
        assert len(events)==3 and events[0]=='approved'
    elif fault in ('approval-missing','late-alias','late-canonical'):
        diagnostic=tmp_path/'safe.json'
        assert runtime.main(['sign','--input',str(stage_file),'--output',str(output),'--diagnostics-output',str(diagnostic)])==2
        expected={'approval-missing':'sign','late-alias':'sign_aliases_before_publish',
                  'late-canonical':'sign_canonical_before_publish'}[fault]
        assert json.loads(diagnostic.read_text())=={'phase':expected,'category':'failed'}
        assert not output.exists()
        if fault=='approval-missing':assert events==[]
    else:
        with pytest.raises(ValueError,match='protected input unavailable' if fault=='missing' else 'complete live gate'):
            runtime.sign(stage_file,output)
        assert not output.exists()


@pytest.mark.parametrize('body',[None, [], {}, {'aliases':None}, {'aliases':{}}, {'aliases':['unexpected.example.com']},
    {'aliases':[], 'pagination':None}, {'aliases':[], 'pagination':{}},
    {'aliases':[], 'pagination':{'next':123}}, {'aliases':[], 'pagination':{'next':''}}])
def test_stage_refuses_unproven_authoritative_alias_inventory(tmp_path,monkeypatch,body):
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    original=runtime.vercel
    monkeypatch.setattr(runtime,'vercel',lambda path:body if '/aliases?' in path else original(path))
    with pytest.raises(ValueError,match='alias'):runtime.stage(123,output)
    assert not output.exists()
    assert not (tmp_path/'.vercel/.env.production.local').exists()


def test_stage_accepts_exhausted_authoritative_alias_inventory(tmp_path,monkeypatch):
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    original=runtime.vercel
    monkeypatch.setattr(runtime,'vercel',lambda path:{'aliases':[],'pagination':{'next':None}} if '/aliases?' in path else original(path))
    runtime.stage(123,output)
    assert output.exists()


@pytest.mark.parametrize('boundary',['before','after'])
@pytest.mark.parametrize('fault',['changed','missing','wrong-host','redirect','unavailable'])
def test_stage_canonical_readback_is_exact_and_failure_has_fixed_phase(tmp_path,monkeypatch,boundary,fault):
    import json
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    original=runtime.vercel;read_count=0
    def read(path):
        nonlocal read_count
        result=original(path)
        if '/v4/aliases/' in path:
            read_count+=1
            if read_count==(1 if boundary=='before' else 2):
                if fault=='changed':result['deploymentId']='dpl_other'
                if fault=='missing':result.pop('deploymentId')
                if fault=='wrong-host':result['alias']='other.vercel.app'
                if fault=='redirect':result['redirect']='other.example.com'
                if fault=='unavailable':raise ValueError('private remote failure')
        return result
    monkeypatch.setattr(runtime,'vercel',read)
    diagnostic=tmp_path/'safe.json'
    assert runtime.main(['stage','--ci-run-id','123','--output',str(output),'--diagnostics-output',str(diagnostic)])==2
    assert json.loads(diagnostic.read_text())=={'phase':'stage_canonical_'+boundary,'category':'failed'}
    assert not output.exists()
    assert not (tmp_path/'.vercel/.env.production.local').exists()
    assert len([c for c in calls if c[:2]==['vercel','deploy']])==(boundary=='after')


def test_stage_alias_read_failure_reports_fixed_phase_and_publishes_nothing(tmp_path,monkeypatch):
    import json
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    original=runtime.vercel
    def read(path):
        if '/aliases?' in path:raise ValueError('private diagnostic')
        return original(path)
    monkeypatch.setattr(runtime,'vercel',read)
    diagnostic=tmp_path/'safe.json'
    assert runtime.main(['stage','--ci-run-id','123','--output',str(output),'--diagnostics-output',str(diagnostic)])==2
    assert json.loads(diagnostic.read_text())=={'phase':'stage_candidate_aliases','category':'failed'}
    assert not output.exists()
    assert not (tmp_path/'.vercel/.env.production.local').exists()


@pytest.mark.parametrize('fault',['inventory','metadata'])
def test_stage_rechecks_aliases_after_probes_before_publication(tmp_path,monkeypatch,fault):
    import json
    runtime,deployed,calls,output=owned_stage(tmp_path,monkeypatch)
    original=runtime.vercel;inventory_reads=0;metadata_reads=0
    def read(path):
        nonlocal inventory_reads,metadata_reads
        result=original(path)
        if '/v2/deployments/' in path:
            inventory_reads+=1
            if inventory_reads==2 and fault=='inventory':result={'aliases':['late.example.com']}
        if '/v13/deployments/dpl_candidate?' in path:
            metadata_reads+=1
            if metadata_reads==2 and fault=='metadata':result['alias']=['late.example.com']
        return result
    monkeypatch.setattr(runtime,'vercel',read)
    diagnostic=tmp_path/'safe.json'
    assert runtime.main(['stage','--ci-run-id','123','--output',str(output),'--diagnostics-output',str(diagnostic)])==2
    assert json.loads(diagnostic.read_text())=={'phase':'stage_aliases_before_publish','category':'failed'}
    assert not output.exists()
    assert not (tmp_path/'.vercel/.env.production.local').exists()
