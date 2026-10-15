"""Protected, attested promotion entry point. No retry after an uncertain alias outcome."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from promotion_transport import claim_promotion_intent,single_promote
from runtime_bundle import decrypt_workspace_bundle, is_encrypted_workspace_bundle
from runtime_bundle import build_workspace_bundle
from runtime_bundle import encrypt_workspace_bundle
from runtime_bundle import compose_workspace_receipts

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='YNWAforever/BuyerOS'
SIGNER_WORKFLOW=REPOSITORY+'/.github/workflows/buyeros-runtime-bundle.yml'
ENVIRONMENT='buyeros-production-promote'

def gate_module():
    spec=importlib.util.spec_from_file_location('release_gate',ROOT/'scripts/check-release-readiness.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def promote(manifest,receipts,gate,*,attestation_verified,metadata,execute,promote_alias):
    evaluation=gate_module().evaluate_release(manifest,receipts,gate)
    blockers=list(evaluation['blockers'])
    if gate!='workspace':blockers.append('workspace_gate_only')
    if attestation_verified is not True:blockers.append('trusted_runtime_attestation_missing')
    for key in ['auto_main_disabled','protected_main','protected_environment','ci_completed','project_match','team_match','repository_match','nonself_approval_verified','runtime_run_verified']:
        if metadata.get(key) is not True:blockers.append('remote_control_unverified:'+key)
    if metadata.get('source_sha')!=manifest.get('source_sha'):blockers.append('remote_source_mismatch')
    if metadata.get('deployment_id')!=manifest.get('candidate_deployment_id'):blockers.append('remote_deployment_mismatch')
    if metadata.get('target')!='production' or metadata.get('ready_state')!='READY':blockers.append('staged_production_artifact_required')
    if metadata.get('ci_head')!=manifest.get('source_sha') or metadata.get('ci_run_id')!=manifest.get('ci_run_id'):blockers.append('fresh_ci_identity_mismatch')
    jobs=metadata.get('jobs',{})
    if not isinstance(jobs,dict) or not all(jobs.get(job)=='success' for job in gate_module().REQUIRED_CI_JOBS):blockers.append('fresh_required_ci_not_green')
    result={'schema':'buyeros.promotion-receipt.v1','promoted':False,'status':'blocked' if blockers else 'preflight_ready','blockers':sorted(set(blockers))}
    if blockers or not execute:return result
    # A thrown/timeout result is unknown: never retry here or release any hold.
    result['status']='promotion_unknown'
    try:
        promote_alias(manifest['candidate_deployment_id'])
    except (OSError,subprocess.SubprocessError,ValueError):
        return result
    result.update(status='promotion_submitted_readback_required',promoted=True)
    return result

def command(argv):
    return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=45).stdout

def github(path):return json.loads(command(['gh','api',f'repos/{REPOSITORY}/{path}']))
def vercel(path):return json.loads(command(['vercel','api',path,'-X','GET','--raw']))

def runtime_module():
    spec=importlib.util.spec_from_file_location('promotion_runtime',ROOT/'scripts/protected-runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def remote_metadata(manifest,receipts):
    from protected_release import verify_approval
    runtime=runtime_module()
    controls=runtime.current_controls(manifest['source_sha'],manifest['ci_run_id'])
    deployment,origin=runtime.deployment(manifest['source_sha'],manifest['candidate_deployment_id'],controls)
    runtime.load_script('collect-runtime-binding.py').collect_configuration(manifest,origin,os.environ['BUYEROS_RELEASE_PROBE_TOKEN'])
    run_id=int(os.environ['GITHUB_RUN_ID'])
    run=github('actions/runs/'+str(run_id))
    if (run.get('head_sha')!=manifest['source_sha'] or run.get('head_branch')!='main'
            or run.get('run_attempt')!=1 or run.get('path')!='.github/workflows/buyeros-promote.yml'):
        raise ValueError('fresh exact-source promotion run required')
    verify_approval(github('actions/runs/'+str(run_id)+'/approvals'),initiator_id=run['triggering_actor']['id'],
                    run_id=run_id,source=manifest['source_sha'],deployment_id=manifest['candidate_deployment_id'],require_canary=False)
    runtime_run_id=int(os.environ['RUNTIME_RUN_ID'])
    runtime_run=github('actions/runs/'+str(runtime_run_id))
    if (runtime_run.get('head_sha')!=manifest['source_sha'] or runtime_run.get('head_branch')!='main'
            or runtime_run.get('run_attempt')!=1 or runtime_run.get('path')!='.github/workflows/buyeros-runtime-bundle.yml'
            or runtime_run.get('status')!='completed' or runtime_run.get('conclusion')!='success'
            or receipts['items']['workspace_canary']['data']['approval_run_id']!=runtime_run_id):
        raise ValueError('exact successful protected runtime run required')
    runtime_proof=verify_approval(github('actions/runs/'+str(runtime_run_id)+'/approvals'),
        initiator_id=runtime_run['triggering_actor']['id'],run_id=runtime_run_id,source=manifest['source_sha'],
        deployment_id=manifest['candidate_deployment_id'])
    if any(receipts['items']['workspace_canary']['data'].get(key)!=value for key,value in runtime_proof.items()):
        raise ValueError('runtime browser signoff proof mismatch')
    alias=vercel('/v4/aliases/buyer-os-nu.vercel.app?teamId='+controls['team_id'])
    if (alias.get('projectId')!=controls['project_id'] or alias.get('redirect')
            or not alias.get('deploymentId') or alias.get('deploymentId')==manifest['candidate_deployment_id']
            or receipts['items']['rollback']['data'].get('deployment_id')!=alias['deploymentId']):
        raise ValueError('current production rollback identity changed; reconcile read-only')
    return {'source_sha':deployment['meta']['githubCommitSha'],'deployment_id':deployment['id'],
        'project_match':True,'team_match':True,'repository_match':True,
        'target':deployment['target'],'ready_state':deployment['readyState'],
        'auto_main_disabled':True,'protected_main':True,'protected_environment':True,
        'ci_completed':True,'nonself_approval_verified':True,'runtime_run_verified':True,
        'ci_head':controls['run']['head_sha'],'ci_run_id':controls['run']['id'],
        'jobs':{row['name']:row['conclusion'] for row in controls['jobs']['jobs']}}


def write_receipt(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as handle:
        handle.write(json.dumps(value,indent=2)+'\n')
        handle.flush();os.fsync(handle.fileno())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',required=True,type=Path)
    parser.add_argument('--gate',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args(argv)
    result={'schema':'buyeros.promotion-receipt.v1','status':'blocked','promoted':False,'blockers':['invalid_or_untrusted_input']}
    try:
        if args.output.exists():raise ValueError('immutable output exists')
        if args.gate!='workspace':raise ValueError('workspace gate only')
        envelope=gate_module().read_json(args.bundle)
        if not is_encrypted_workspace_bundle(envelope):raise ValueError('encrypted workspace bundle required')
        # Attest the exact ciphertext before decrypting the customer/runtime receipt payload.
        command(['gh','attestation','verify',str(args.bundle),'--repo',REPOSITORY,'--signer-workflow',SIGNER_WORKFLOW,
            '--source-ref','refs/heads/main','--source-digest',envelope['source_sha'],'--deny-self-hosted-runners'])
        bundle=decrypt_workspace_bundle(envelope,os.environ.get('BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY',''))
        if args.execute and (os.environ.get('GITHUB_WORKFLOW')!='BuyerOS guarded promotion' or os.environ.get('GITHUB_REF')!='refs/heads/main'):
            raise ValueError('execution requires reviewed protected workflow')
        if args.execute and (os.environ.get('GITHUB_SHA')!=envelope['source_sha'] or os.environ.get('GITHUB_RUN_ATTEMPT')!='1'):
            raise ValueError('exact main source and first run attempt required')
        build_workspace_bundle(bundle['manifest'],bundle['receipts'],source_sha=envelope['source_sha'])
        metadata=remote_metadata(bundle['manifest'],bundle['receipts'])
        def submit_once(deployment):
            context={'schema':'buyeros.promotion-intent.v1','project_id':os.environ['VERCEL_PROJECT_ID'],
                     'source_sha':envelope['source_sha'],'deployment_id':deployment,
                     'bundle_sha256':hashlib.sha256(args.bundle.read_bytes()).hexdigest(),
                     'promotion_run_id':int(os.environ['GITHUB_RUN_ID']),'runtime_run_id':int(os.environ['RUNTIME_RUN_ID'])}
            ledger_id=claim_promotion_intent(context)
            intent={'schema':'buyeros.promotion-receipt.v1','status':'promotion_unknown','promoted':False,
                    'blockers':[],**{key:value for key,value in context.items() if key!='schema'},'ledger_id':ledger_id}
            write_receipt(args.output,intent)
            single_promote(os.environ['VERCEL_PROJECT_ID'],os.environ['VERCEL_ORG_ID'],deployment,os.environ['VERCEL_TOKEN'])
        result=promote(bundle['manifest'],bundle['receipts'],args.gate,attestation_verified=True,metadata=metadata,execute=args.execute,
            promote_alias=submit_once)
        result.update(source_sha=envelope['source_sha'],deployment_id=bundle['manifest']['candidate_deployment_id'],
                      project_id=os.environ.get('VERCEL_PROJECT_ID'),promotion_run_id=os.environ.get('GITHUB_RUN_ID'),
                      runtime_run_id=os.environ.get('RUNTIME_RUN_ID'),bundle_sha256=hashlib.sha256(args.bundle.read_bytes()).hexdigest())
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError,json.JSONDecodeError):pass
    if args.output.exists() and result['status'] in ('promotion_unknown','promotion_submitted_readback_required'):
        intent=gate_module().read_json(args.output)
        result.update({key:value for key,value in intent.items() if key not in ('schema','status','promoted','blockers')})
        replacement=args.output.with_suffix('.final.tmp')
        write_receipt(replacement,result)
        os.replace(replacement,args.output)
    elif not args.output.exists():
        write_receipt(args.output,result)
    print(json.dumps(result))
    return 0 if result['status'] in ('preflight_ready','promotion_submitted_readback_required') else 1

if __name__=='__main__':raise SystemExit(main())
