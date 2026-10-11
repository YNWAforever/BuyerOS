"""Protected, attested promotion entry point. No retry after an uncertain alias outcome."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='YNWAforever/BuyerOS'
SIGNER_WORKFLOW=REPOSITORY+'/.github/workflows/buyeros-runtime-acceptance.yml'
ENVIRONMENT='buyeros-production-promote'

def gate_module():
    spec=importlib.util.spec_from_file_location('release_gate',ROOT/'scripts/check-release-readiness.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def promote(manifest,receipts,gate,*,attestation_verified,metadata,execute,promote_alias):
    evaluation=gate_module().evaluate_release(manifest,receipts,gate)
    blockers=list(evaluation['blockers'])
    if attestation_verified is not True:blockers.append('trusted_runtime_attestation_missing')
    for key in ['auto_main_disabled','protected_main','protected_environment','ci_completed']:
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
    except (OSError,subprocess.SubprocessError):
        return result
    result.update(status='promotion_submitted_readback_required',promoted=True)
    return result

def command(argv):
    return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=45).stdout

def github(path):return json.loads(command(['gh','api',f'repos/{REPOSITORY}/{path}']))
def vercel(path):return json.loads(command(['vercel','api',path,'-X','GET','--raw']))

def remote_metadata(manifest):
    branch=github('branches/main')
    protection=github('branches/main/protection')
    environment=github('environments/'+ENVIRONMENT)
    run=github('actions/runs/'+str(manifest['ci_run_id']))
    jobs=github('actions/runs/'+str(manifest['ci_run_id'])+'/jobs?per_page=100')
    deployment=vercel('/v13/deployments/'+manifest['candidate_deployment_id'])
    project=vercel('/v9/projects/buyer-os')
    rules=environment.get('protection_rules',[])
    reviewed=any(rule.get('type')=='required_reviewers' and rule.get('reviewers') and rule.get('prevent_self_review') is True for rule in rules)
    status_checks=protection.get('required_status_checks',{})
    contexts=set(status_checks.get('contexts',[]))|{row.get('context') for row in status_checks.get('checks',[])}
    protected_main=branch.get('protected') is True and status_checks.get('strict') is True and gate_module().REQUIRED_CI_JOBS<=contexts
    # The project API must positively report the adopted no-auto-main control.
    # Missing/changed API shape fails closed; a local vercel.json is insufficient.
    main_disabled=project.get('autoAssignCustomDomains') is False
    job_rows=jobs.get('jobs',[])
    complete_inventory=jobs.get('total_count')==len(job_rows) and len({row['name'] for row in job_rows})==len(job_rows)
    return {'source_sha':deployment.get('meta',{}).get('githubCommitSha'),'deployment_id':deployment.get('id'),
        'target':deployment.get('target'),'ready_state':deployment.get('readyState'),
        'auto_main_disabled':main_disabled,'protected_main':protected_main,
        'protected_environment':reviewed and environment.get('deployment_branch_policy',{}).get('protected_branches') is True,
        'ci_completed':run.get('status')=='completed' and run.get('conclusion')=='success' and run.get('path')=='.github/workflows/buyeros-ci.yml' and complete_inventory,
        'ci_head':run.get('head_sha'),'ci_run_id':run.get('id'),
        'jobs':{row['name']:row.get('conclusion') if row.get('status')=='completed' else None for row in job_rows}}

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
        bundle=gate_module().read_json(args.bundle)
        if set(bundle)!={'schema','manifest','receipts'} or bundle['schema']!='buyeros.attested-runtime-bundle.v1':raise ValueError('invalid bundle')
        # Verify the exact bundle bytes against a designated protected runtime producer,
        # not arbitrary local assertions or a PR's CI attestation.
        command(['gh','attestation','verify',str(args.bundle),'--repo',REPOSITORY,'--signer-workflow',SIGNER_WORKFLOW,
            '--source-ref','refs/heads/main','--source-digest',bundle['manifest']['source_sha'],'--deny-self-hosted-runners'])
        if args.execute and (os.environ.get('GITHUB_WORKFLOW')!='BuyerOS guarded promotion' or os.environ.get('GITHUB_REF')!='refs/heads/main'):
            raise ValueError('execution requires reviewed protected workflow')
        metadata=remote_metadata(bundle['manifest'])
        result=promote(bundle['manifest'],bundle['receipts'],args.gate,attestation_verified=True,metadata=metadata,execute=args.execute,
            promote_alias=lambda deployment:command(['vercel','promote',deployment,'--yes']))
    except (ValueError,KeyError,TypeError,OSError,subprocess.SubprocessError,json.JSONDecodeError):pass
    if not args.output.exists():
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as output:output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['status'] in ('preflight_ready','promotion_submitted_readback_required') else 1

if __name__=='__main__':raise SystemExit(main())
