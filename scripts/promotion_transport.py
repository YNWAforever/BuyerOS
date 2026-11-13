"""No-retry release mutations and a project-scoped durable intent hold."""
import json
import os
import re
import urllib.error
import urllib.request

from runtime_bundle import canonical_json,unique_keys

API='https://api.github.com/repos/YNWAforever/BuyerOS/'
TASK='buyeros-protected-promotion'
LEDGER_ENVIRONMENT='buyeros-production-intents'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def request_json(url,token,*,method='GET',body=None):
    # urllib's opener makes one attempt; no CLI/client retry layer surrounds it.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    request=urllib.request.Request(url,method=method,data=canonical_json(body) if body is not None else None,
        headers={'Authorization':'Bearer '+token,'Accept':'application/json','Content-Type':'application/json',
                 'User-Agent':'BuyerOS-protected-release/1','X-GitHub-Api-Version':'2022-11-28'})
    with opener.open(request,timeout=30) as response:
        if response.code not in (200,201,202,204): raise ValueError('release mutation acknowledgement unverified')
        raw=response.read(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError('release response too large')
        return json.loads(raw.decode(),object_pairs_hook=unique_keys) if raw else None


CANONICAL_ALIAS='buyer-os-nu.vercel.app'


def single_assign_alias(project_id,team_id,deployment_id,rollback_id,token):
    """Move only the reviewed canonical alias; never call project promotion.

    The caller must first verify the attested workspace bundle and persist its
    durable intent. Any failure here leaves that intent unresolved, including a
    lost acknowledgement or a failed readback; no mutation is retried.
    """
    if (re.fullmatch(r'prj_[A-Za-z0-9]+',project_id) is None
            or re.fullmatch(r'team_[A-Za-z0-9]+',team_id) is None
            or re.fullmatch(r'dpl_[A-Za-z0-9_-]+',deployment_id) is None
            or re.fullmatch(r'dpl_[A-Za-z0-9_-]+',rollback_id) is None
            or deployment_id==rollback_id or not token):
        raise ValueError('exact alias and rollback targets required')
    base='https://api.vercel.com'
    scope='?teamId='+team_id

    def project_control():
        project=request_json(base+'/v9/projects/'+project_id+scope,token)
        if (not isinstance(project,dict) or project.get('id')!=project_id
                or project.get('accountId')!=team_id
                or project.get('autoAssignCustomDomains') is not False):
            raise ValueError('exact project and disabled automatic assignment required')

    def alias_target(expected):
        alias=request_json(base+'/v4/aliases/'+CANONICAL_ALIAS+scope,token)
        if (not isinstance(alias,dict) or alias.get('alias')!=CANONICAL_ALIAS
                or alias.get('projectId')!=project_id or alias.get('deploymentId')!=expected
                or alias.get('redirect') is not None):
            raise ValueError('canonical alias target unverified; reconcile read-only')

    project_control()
    alias_target(rollback_id)
    deployment=request_json(base+'/v13/deployments/'+deployment_id+scope,token)
    if (not isinstance(deployment,dict) or deployment.get('id')!=deployment_id
            or deployment.get('projectId')!=project_id or deployment.get('ownerId')!=team_id
            or deployment.get('target')!='production' or deployment.get('readyState')!='READY'
            or ('autoAssignCustomDomains' in deployment and deployment['autoAssignCustomDomains'] is not False)):
        raise ValueError('exact ready production alias target required')
    # This endpoint assigns one hostname. It does not promote the project or
    # enable automatic domain assignment. No redirect or caller-supplied alias.
    assigned=request_json(base+'/v2/deployments/'+deployment_id+'/aliases'+scope,
                          token,method='POST',body={'alias':CANONICAL_ALIAS})
    if (not isinstance(assigned,dict) or assigned.get('alias')!=CANONICAL_ALIAS
            or not isinstance(assigned.get('uid'),str) or not assigned['uid']
            or assigned.get('oldDeploymentId')!=rollback_id):
        raise ValueError('alias acknowledgement unverified; reconcile read-only')
    project_control()
    alias_target(deployment_id)
    return assigned


def claim_promotion_intent(context,*,get=None,post=None):
    token=os.environ.get('BUYEROS_RELEASE_LEDGER_TOKEN','')
    get=get or (lambda path:request_json(API+path,token))
    post=post or (lambda path,body:request_json(API+path,token,method='POST',body=body))
    keys={'schema','project_id','source_sha','deployment_id','bundle_sha256','promotion_run_id','runtime_run_id'}
    if (type(context) is not dict or set(context)!=keys or context.get('schema')!='buyeros.promotion-intent.v1'
            or re.fullmatch(r'prj_[A-Za-z0-9]+',context.get('project_id','')) is None
            or re.fullmatch(r'dpl_[A-Za-z0-9_-]+',context.get('deployment_id','')) is None
            or re.fullmatch(r'[0-9a-f]{40}',context.get('source_sha','')) is None
            or re.fullmatch(r'[0-9a-f]{64}',context.get('bundle_sha256','')) is None
            or any(type(context.get(k)) is not int or context[k]<=0 for k in ('promotion_run_id','runtime_run_id'))):
        raise ValueError('immutable promotion intent identity required')
    records=get('deployments?task='+TASK+'&environment='+LEDGER_ENVIRONMENT+'&per_page=100')
    if type(records) is not list or len(records)>=100: raise ValueError('complete durable intent history required')
    for record in records:
        payload=record.get('payload')
        if type(payload) is not dict: raise ValueError('unknown durable intent payload')
        if payload.get('project_id')!=context['project_id']: continue
        if payload.get('bundle_sha256')==context['bundle_sha256'] or payload.get('deployment_id')==context['deployment_id']:
            raise ValueError('candidate intent already exists; reconcile original identity')
        states=get('deployments/'+str(record['id'])+'/statuses?per_page=1')
        expected='read-only-reconciled:'+payload.get('source_sha','')+':'+payload.get('deployment_id','')
        if (type(states) is not list or not states or states[0].get('state') not in ('success','failure','inactive')
                or states[0].get('description')!=expected):
            raise ValueError('unresolved project promotion intent; read-only reconciliation required')
    record=post('deployments',{'ref':context['source_sha'],'task':TASK,'environment':LEDGER_ENVIRONMENT,
        'auto_merge':False,'required_contexts':[],'production_environment':True,'transient_environment':False,
        'description':'BuyerOS guarded promotion intent; unresolved until read-only reconciliation', 'payload':context})
    if type(record) is not dict or type(record.get('id')) is not int or record.get('payload')!=context:
        raise ValueError('durable intent acknowledgement unknown; do not submit promotion')
    return record['id']
