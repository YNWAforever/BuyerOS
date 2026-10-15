"""Pure release-control checks shared by staging, signing, and promotion."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPOSITORY='YNWAforever/BuyerOS'
ENVIRONMENT='buyeros-production-promote'


def release_gate():
    spec=importlib.util.spec_from_file_location('protected_release_gate',ROOT/'scripts/check-release-readiness.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def verify_controls(*,source,ci_run_id,branch,protection,environment,project,project_id,team_id,run,jobs):
    required=release_gate().REQUIRED_CI_JOBS
    checks=protection.get('required_status_checks',{})
    contexts=set(checks.get('contexts',[]))|{x.get('context') for x in checks.get('checks',[])}
    if (branch.get('protected') is not True or branch.get('commit',{}).get('sha')!=source
            or checks.get('strict') is not True or not required<=contexts
            or protection.get('enforce_admins',{}).get('enabled') is not True):
        raise ValueError('strict current main protection required')
    policy=environment.get('deployment_branch_policy',{})
    if (policy.get('protected_branches') is not True or policy.get('custom_branch_policies') is not False
            or environment.get('can_admins_bypass') is not False
            or not any(rule.get('type')=='required_reviewers' and rule.get('prevent_self_review') is True
                       and rule.get('reviewers') for rule in environment.get('protection_rules',[]))):
        raise ValueError('non-self protected environment required')
    link=project.get('link',{})
    if (project.get('id')!=project_id or project.get('accountId')!=team_id
            or project.get('autoAssignCustomDomains') is not False
            or link.get('type')!='github' or link.get('org')!='YNWAforever' or link.get('repo')!='BuyerOS'
            or not link.get('repoId') or link.get('productionBranch')!='main'):
        raise ValueError('exact project team repository and no-auto-alias required')
    rows=jobs.get('jobs',[])
    if (run.get('id')!=ci_run_id or run.get('head_sha')!=source or run.get('head_branch')!='main'
            or run.get('status')!='completed' or run.get('conclusion')!='success'
            or run.get('path')!='.github/workflows/buyeros-ci.yml'
            or run.get('repository',{}).get('full_name')!=REPOSITORY
            or type(rows) is not list or jobs.get('total_count')!=len(rows)
            or len({row['name'] for row in rows})!=len(rows)
            or not all(any(row['name']==name and row.get('status')=='completed'
                           and row.get('conclusion')=='success' for row in rows) for name in required)):
        raise ValueError('complete exact-main successful CI inventory required')


def verify_approval(history,*,initiator_id,run_id,source,deployment_id,require_canary=True):
    if (type(history) is not list or type(initiator_id) is not int or initiator_id<=0
            or type(run_id) is not int or run_id<=0):
        raise ValueError('verified run identity required')
    relevant=[item for item in history if type(item) is dict
              and any(e.get('name')==ENVIRONMENT for e in item.get('environments',[]))]
    if len(relevant)!=1:
        raise ValueError('unambiguous recorded environment approval required')
    review=relevant[0];reviewer=review.get('user',{}).get('id')
    comment=review.get('comment','')
    expected='workspace-canary-pass:'+source+':'+deployment_id+':roles-project-reload-retry'
    if (review.get('state')!='approved' or type(reviewer) is not int or reviewer<=0 or reviewer==initiator_id
            or type(comment) is not str or (require_canary and comment!=expected)):
        raise ValueError('verified non-self approval and bound canary comment required')
    comment_digest=hashlib.sha256(comment.encode()).hexdigest()
    proof={'reviewer_id':reviewer,'initiator_id':initiator_id,'approval_run_id':run_id,
           'approval_comment_sha256':comment_digest,'human_signoff':True}
    proof['browser_canary_sha256']=hashlib.sha256(json.dumps({**proof,'source_sha':source,
        'deployment_id':deployment_id},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return proof
