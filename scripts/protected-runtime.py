"""Protected main-only stage/probe/signoff orchestration. No automatic alias assignment."""
import argparse
import asyncio
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

from protected_release import ENVIRONMENT,REPOSITORY,release_gate,verify_controls,verify_approval
from vercel_cli_auth import authenticated_command
from runtime_bundle import (canonical_json,unique_keys,encrypt_observation_packet,decrypt_observation_packet,
                            build_workspace_bundle,compose_workspace_receipts,encrypt_workspace_bundle)

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/api'))
from buyeros_api.services.release_binding import database_target_sha256,database_endpoint_sha256
from buyeros_api.services.release_configuration import pulled_configuration_sha256
from buyeros_api.services.schema_readiness import SchemaContract,inspect_schema


DIAGNOSTIC_LABELS=frozenset({'stage','sign','controls_target','controls_branch','controls_protection',
    'controls_environment','controls_project','controls_run','controls_jobs','controls_verify',
    'stage_controls','stage_api_contract','stage_schema_contract','stage_account_scope','stage_rollback',
    'stage_rollback_artifacts','stage_pull','stage_environment','stage_schema_probe','stage_rollback_probe',
    'stage_recheck_controls','stage_build','stage_deploy','stage_candidate_lookup','stage_candidate_verify',
    'stage_candidate_artifacts','stage_tree','stage_binding_probe','stage_configuration_probe',
    'stage_api_probe','stage_encrypt','stage_write'})
DIAGNOSTIC_STATUSES=frozenset({'started','passed','failed','command_nonzero','command_timeout','file_unavailable',
                              'http_unauthorized','http_forbidden','http_not_found'})
GH_METADATA_LABELS=frozenset({'controls_branch','controls_protection','controls_environment','controls_run','controls_jobs'})
_failure_diagnostic=None


def safe_summary(label,status):
    """Best-effort fixed vocabulary only; never render exception or command data."""
    if label not in DIAGNOSTIC_LABELS or status not in DIAGNOSTIC_STATUSES:return
    try:
        path=os.environ.get('GITHUB_STEP_SUMMARY')
        if path:
            with open(path,'a',encoding='utf-8') as handle:
                handle.write('- '+label+': '+status+'\n')
    except Exception:
        # Observability must neither authorize work nor replace its failure.
        pass


def checked(label,operation,*args,**kwargs):
    global _failure_diagnostic
    if label not in DIAGNOSTIC_LABELS:raise ValueError('invalid diagnostic label')
    safe_summary(label,'started')
    try:
        result=operation(*args,**kwargs)
    except Exception as error:
        status='failed'
        if isinstance(error,subprocess.CalledProcessError):
            status='command_nonzero'
            # Inspect only the CLI's exact trailing HTTP marker. No command,
            # stderr text, captured digits, or exception names are published.
            if (label in GH_METADATA_LABELS and type(error.cmd) is list
                    and error.cmd[:2]==['gh','api'] and type(error.stderr) is str):
                match=re.search(r'\(HTTP (401|403|404)\)(?:\r?\n)?\Z',error.stderr)
                if match:status={'401':'http_unauthorized','403':'http_forbidden','404':'http_not_found'}[match.group(1)]
            elif (label=='controls_project' and type(error.cmd) is list
                    and error.cmd[:2]==['vercel','api'] and type(error.stderr) is str
                    and re.search(r'\(403\)(?:\r?\n)?\Z',error.stderr)):
                status='http_forbidden'
        elif isinstance(error,subprocess.TimeoutExpired):status='command_timeout'
        elif isinstance(error,FileNotFoundError):status='file_unavailable'
        if _failure_diagnostic is None:_failure_diagnostic={'phase':label,'category':status}
        safe_summary(label,status)
        raise
    safe_summary(label,'passed')
    return result


def write_failure_diagnostic(path):
    """Optional public-safe failure report; a failed write cannot alter exit 2."""
    if path is None:return
    report=_failure_diagnostic
    if (type(report) is not dict or set(report)!={'phase','category'}
            or report['phase'] not in DIAGNOSTIC_LABELS
            or report['category'] not in DIAGNOSTIC_STATUSES-{'started','passed'}):
        report={'phase':'stage','category':'failed'}
    try:
        with path.open('x',encoding='utf-8') as handle:
            handle.write(json.dumps(report)+'\n')
    except Exception:
        pass


def load_script(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'scripts'/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def command(argv,*,timeout=45):
    with authenticated_command(argv) as authenticated:
        return subprocess.run(authenticated,check=True,capture_output=True,text=True,timeout=timeout).stdout


def github(path):
    return json.loads(command(['gh','api','repos/'+REPOSITORY+'/'+path]),object_pairs_hook=unique_keys)


def vercel(path):
    return json.loads(command(['vercel','api',path,'-X','GET','--raw']),object_pairs_hook=unique_keys)


def digest(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def private_json(key):
    raw=os.environ.get(key,'')
    if not raw or len(raw.encode())>65536: raise ValueError('protected input unavailable')
    return json.loads(raw,object_pairs_hook=unique_keys)


def current_controls(source,ci_run_id):
    def target():
        project_id=os.environ['VERCEL_PROJECT_ID'];team_id=os.environ['VERCEL_ORG_ID']
        if not re.fullmatch(r'prj_[A-Za-z0-9]+',project_id) or not re.fullmatch(r'team_[A-Za-z0-9]+',team_id):
            raise ValueError('exact project and team required')
        return project_id,team_id
    project_id,team_id=checked('controls_target',target)
    inputs=dict(source=source,ci_run_id=ci_run_id,branch=checked('controls_branch',github,'branches/main'),
        protection=checked('controls_protection',github,'branches/main/protection'),
        environment=checked('controls_environment',github,'environments/'+ENVIRONMENT),
        project=checked('controls_project',vercel,'/v9/projects/'+project_id+'?teamId='+team_id),project_id=project_id,team_id=team_id,
        run=checked('controls_run',github,'actions/runs/'+str(ci_run_id)),
        jobs=checked('controls_jobs',github,'actions/runs/'+str(ci_run_id)+'/jobs?per_page=100'))
    checked('controls_verify',verify_controls,**inputs)
    return inputs


def deployment(source,deployment_id,controls):
    result=vercel('/v13/deployments/'+deployment_id+'?teamId='+controls['team_id'])
    meta=result.get('meta',{});link=controls['project']['link']
    if (result.get('id')!=deployment_id or result.get('projectId')!=controls['project_id']
            or result.get('ownerId')!=controls['team_id'] or result.get('target')!='production'
            or result.get('readyState')!='READY' or meta.get('githubCommitSha')!=source
            or meta.get('githubCommitOrg')!=link['org'] or meta.get('githubCommitRepo')!=link['repo']
            or str(meta.get('githubCommitRepoId'))!=str(link['repoId'])):
        raise ValueError('exact ready production deployment required')
    origin='https://'+result['url']
    if re.fullmatch(r'https://[a-z0-9-]+\.vercel\.app',origin) is None:
        raise ValueError('immutable deployment origin required')
    return result,origin


def service_artifacts(value):
    services=value.get('services',[])
    if type(services) is not list or {s.get('name') for s in services}!={'app','api'}:
        raise ValueError('frontend and API service manifests required')
    builds=value.get('lambdas',[])
    if not builds or any(b.get('readyState')!='READY' for b in builds):
        raise ValueError('ready function build inventory required')
    outputs=[output for build in builds for output in build.get('output',[]) if output.get('functionName')]
    if len(outputs)<2: raise ValueError('both service function artifacts required')
    return {kind:value['id']+'/'+name+'/'+digest({'service':next(s for s in services if s['name']==name),'builds':builds})
            for kind,name in [('frontend','app'),('api','api')]}


def runtime_env(path):
    values={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'): continue
        key,sep,raw=line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z_][A-Z0-9_]*',key) or key in values:
            raise ValueError('invalid production environment file')
        values[key]=json.loads(raw.replace('\\$', '$')) if raw.startswith('"') else raw
    # Vercel Secret values are deliberately blank in CLI exports. Use the
    # protected runtime-role credential only when the exported binding is absent.
    # The reviewed endpoint contract and live candidate probe still must agree.
    dsn=values.get('BUYEROS_DATABASE_URL') or os.environ.get('BUYEROS_SCHEMA_CHECK_DATABASE_URL','')
    if not dsn:raise ValueError('protected runtime schema credential unavailable')
    database_target_sha256(dsn)
    values['BUYEROS_DATABASE_URL']=dsn
    for key in ('BUYEROS_PAID_ADMISSION_ENABLED','BUYEROS_DELIVERY_ADMISSION_ENABLED','BUYEROS_CLOUDFLARE_EXECUTION_ENABLED'):
        if values.get(key,'false').lower() not in ('false','0'): raise ValueError('paid or delivery controls are not disabled')
    probe=os.environ.get('BUYEROS_RELEASE_PROBE_TOKEN','')
    if not probe or (values.get('BUYEROS_RELEASE_PROBE_TOKEN') and values['BUYEROS_RELEASE_PROBE_TOKEN']!=probe):
        raise ValueError('runtime probe credential not bound to production environment')
    values['BUYEROS_RELEASE_PROBE_TOKEN']=probe
    return values


async def schema_observation(dsn,contract):
    from sqlalchemy.ext.asyncio import create_async_engine
    engine=create_async_engine(dsn.replace('postgresql://','postgresql+psycopg://',1),connect_args={'connect_timeout':5})
    try:
        async with engine.connect() as connection:
            result=await inspect_schema(connection,contract)
        if not result.compatible: raise ValueError('independent runtime schema incompatible')
        return result.model_dump(mode='json',by_alias=True)
    finally:
        await engine.dispose()


def common(manifest):
    result={key:manifest[key] for key in ('source_sha','tree_sha','configuration_sha256','db_target_sha256')}
    return {**result,'deployment_id':manifest['candidate_deployment_id'],
            'checked_at':datetime.now(timezone.utc).isoformat(),'evidence_mode':'candidate_runtime'}


def collect_verified(reads,packet,tokens,origin):
    result=reads.collect(packet,tokens,origin)
    if result.get('all_checks_passed') is not True:
        raise ValueError('API controls failed')
    return result


def stage(ci_run_id,output):
    source=os.environ['GITHUB_SHA']
    if (os.environ.get('GITHUB_REF')!='refs/heads/main'
            or os.environ.get('GITHUB_WORKFLOW')!='BuyerOS protected runtime bundle'
            or os.environ.get('BUYEROS_ENABLE_PROTECTED_STAGE')!='true' or output.exists()):
        raise ValueError('reviewed protected main stage authorization required')
    controls=checked('stage_controls',current_controls,source,ci_run_id)
    # Private templates bind account scope and schema policy before any deployment.
    api=checked('stage_api_contract',private_json,'BUYEROS_G0_TARGET_JSON');schema=checked('stage_schema_contract',lambda:SchemaContract.model_validate(private_json('BUYEROS_SCHEMA_CONTRACT_JSON')))
    if (api.get('source_sha')!=source or schema.source_sha!=source or schema.evidence_mode!='candidate_runtime'
            or schema.target_receipt is None or schema.target!=schema.target_receipt
            or digest(api)!=os.environ.get('BUYEROS_G0_CONTRACT_SHA256')
            or digest(schema.model_dump(mode='json',by_alias=True))!=os.environ.get('BUYEROS_SCHEMA_CONTRACT_SHA256')
            or api.get('authorization_reference_sha256')!=os.environ.get('BUYEROS_RUNTIME_READ_SCOPE_SHA256')):
        raise ValueError('source-specific reviewed private templates required')
    reads=load_script('collect-workspace-observations.py')
    tokens={key:os.environ['BUYEROS_G0_'+key.upper()+'_TOKEN'] for key in reads.ACCOUNTS}
    checked('stage_account_scope',reads.validate,api,tokens,api['origin'])
    rollback_id=os.environ.get('BUYEROS_ROLLBACK_DEPLOYMENT_ID','')
    if re.fullmatch(r'dpl_[A-Za-z0-9_-]+',rollback_id) is None: raise ValueError('reviewed rollback deployment absent')
    rollback=checked('stage_rollback',vercel,'/v13/deployments/'+rollback_id+'?teamId='+controls['team_id'])
    if (rollback.get('id')!=rollback_id or rollback.get('projectId')!=controls['project_id']
            or rollback.get('ownerId')!=controls['team_id'] or rollback.get('target')!='production'
            or rollback.get('readyState')!='READY'):
        raise ValueError('exact compatible rollback deployment required')
    rollback_artifacts=checked('stage_rollback_artifacts',service_artifacts,rollback)
    pulled=ROOT/'.vercel/.env.production.local'
    try:
        checked('stage_pull',command,['vercel','pull','--yes','--environment=production'],timeout=120)
        values=checked('stage_environment',runtime_env,pulled)
        target=database_target_sha256(values['BUYEROS_DATABASE_URL'])
        expected_endpoint=database_endpoint_sha256(values['BUYEROS_DATABASE_URL'])
        if schema.target.endpoint_sha256!=expected_endpoint:
            raise ValueError('schema target endpoint differs from production binding')
        observed_schema=checked('stage_schema_probe',lambda:asyncio.run(schema_observation(values['BUYEROS_DATABASE_URL'],schema)))
        rollback_packet={**api,'origin':'https://'+rollback['url']}
        rollback_api=checked('stage_rollback_probe',collect_verified,reads,rollback_packet,tokens,rollback_packet['origin'])
        # Review main at the final boundary before the one staging call.
        checked('stage_recheck_controls',current_controls,source,ci_run_id)
        checked('stage_build',command,['vercel','build','--prod'],timeout=900)
        args=['vercel','deploy','--prebuilt','--prod','--skip-domain','--yes',
              '--env','BUYEROS_RUNTIME_SOURCE_SHA='+source,
              '--env','BUYEROS_NEON_STAGED_ORIGIN_ENABLED=1']
        values['BUYEROS_NEON_STAGED_ORIGIN_ENABLED']='1'
        meta={'githubCommitSha':source,'githubCommitOrg':'YNWAforever','githubCommitRepo':'BuyerOS',
              'githubCommitRepoId':str(controls['project']['link']['repoId']),'githubCommitRef':'main'}
        for key,value in meta.items(): args.extend(['--meta',key+'='+value])
        url=checked('stage_deploy',command,args,timeout=900).strip().splitlines()[-1]
        if re.fullmatch(r'https://[a-z0-9-]+\.vercel\.app',url) is None: raise ValueError('staging outcome unverified; do not retry')
        created=checked('stage_candidate_lookup',vercel,'/v13/deployments/'+url.removeprefix('https://')+'?teamId='+controls['team_id'])
        deployed,origin=checked('stage_candidate_verify',deployment,source,created['id'],controls)
        if (deployed.get('aliasAssigned') is not False
                or controls['project'].get('autoAssignCustomDomains') is not False
                or ('autoAssignCustomDomains' in deployed and deployed['autoAssignCustomDomains'] is not False)):
            raise ValueError('staged deployment unexpectedly assigned aliases')
        artifacts=checked('stage_candidate_artifacts',service_artifacts,deployed)
        manifest={'schema':'buyeros.release-manifest.v1','source_sha':source,
            'tree_sha':checked('stage_tree',command,['git','rev-parse',source+'^{tree}']).strip(),
            'configuration_sha256':pulled_configuration_sha256(values),'db_target_sha256':target,'schema_contract_sha256':observed_schema['contract_sha256'],
            'frontend_artifact':artifacts['frontend'],'api_artifact':artifacts['api'],'worker_artifact':None,
            'required_heads':observed_schema['observed_heads'],'ci_run_id':ci_run_id,
            'required_ci_jobs':sorted(release_gate().REQUIRED_CI_JOBS),'candidate_deployment_id':deployed['id'],
            'receipt_max_age_seconds':900,'rollback_artifacts':rollback_artifacts,
            'activation':{'auth':values.get('BUYEROS_AUTH_MODE','neon'),'providers':'disabled','worker':'disabled','delivery':'disabled'}}
        bound=checked('stage_binding_probe',load_script('collect-runtime-binding.py').collect_binding,manifest,origin,values['BUYEROS_DATABASE_URL'],os.environ['BUYEROS_RELEASE_PROBE_TOKEN'])
        observed_configuration=checked('stage_configuration_probe',load_script('collect-runtime-binding.py').collect_configuration,manifest,origin,os.environ['BUYEROS_RELEASE_PROBE_TOKEN'])
        observed_api=checked('stage_api_probe',collect_verified,reads,{**api,'origin':origin},tokens,origin)
        files={'manifest.json':manifest,'schema-observations.json':observed_schema,'api-observations.json':observed_api,
               'binding-observations.json':bound,'configuration-observations.json':observed_configuration,
               'build-evidence.json':{'ci':{'run_id':ci_run_id,'head_sha':source,'status':'completed','conclusion':'success',
                                          'jobs':{row['name']:row['conclusion'] for row in controls['jobs']['jobs']}},
                                     'artifacts':artifacts,'api_contract_sha256':observed_api['contract_sha256']},
               'rollback-receipt.json':{**common(manifest),'data':{**rollback_artifacts,'compatible':True,
                    'deployment_id':rollback_id,'api_observation_sha256':digest(rollback_api),
                    'schema_observation_sha256':digest(observed_schema)}}}
        packet={'schema':'buyeros.private-runtime-observations.v1','source_sha':source,
                'origin':origin,'files':files,'stage_run_id':int(os.environ['GITHUB_RUN_ID'])}
        encrypted=checked('stage_encrypt',encrypt_observation_packet,packet,os.environ['BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY'])
        checked('stage_write',write_encrypted,output,encrypted)
        with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as summary:
            summary.write('candidate_url='+origin+'\ndeployment_id='+deployed['id']+'\nsource_sha='+source+'\n')
    finally:
        # Never leave the pulled production DSN or build environment on the runner.
        pulled.unlink(missing_ok=True)


def write_encrypted(output,value):
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as handle: handle.write(canonical_json(value)+b'\n')


def sign(input_file,output):
    source=os.environ['GITHUB_SHA']
    if (os.environ.get('GITHUB_REF')!='refs/heads/main' or os.environ.get('GITHUB_WORKFLOW')!='BuyerOS protected runtime bundle'
            or output.exists()): raise ValueError('protected main signing required')
    envelope=release_gate().read_json(input_file)
    packet=decrypt_observation_packet(envelope,os.environ['BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY'])
    if packet['source_sha']!=source or packet['stage_run_id']!=int(os.environ['GITHUB_RUN_ID']):
        raise ValueError('same-run current-main observations required')
    files=packet['files'];manifest=files['manifest.json']
    controls=current_controls(source,manifest['ci_run_id'])
    _,origin=deployment(source,manifest['candidate_deployment_id'],controls)
    load_script('collect-runtime-binding.py').collect_configuration(manifest,origin,os.environ['BUYEROS_RELEASE_PROBE_TOKEN'])
    run=github('actions/runs/'+os.environ['GITHUB_RUN_ID'])
    if run.get('run_attempt')!=1: raise ValueError('rerun requires fresh stage and signoff')
    proof=verify_approval(github('actions/runs/'+os.environ['GITHUB_RUN_ID']+'/approvals'),
        initiator_id=run['triggering_actor']['id'],run_id=run['id'],source=source,deployment_id=manifest['candidate_deployment_id'])
    api=files['api-observations.json'];schema=files['schema-observations.json']
    canary={**common(manifest),'data':{**proof,'workspace_status':200,'correct_roles':True,'correct_project':True,
        'empty_membership_verified':True,'revoked_denied':True,'foreign_tenant_denied':True,'reload_retry_verified':True,
        'api_observation_sha256':digest(api),'schema_observation_sha256':digest(schema)}}
    manual={'workspace_canary':canary,'rollback':files['rollback-receipt.json']}
    # Acceptance can only be collected after staging the exact candidate. Read
    # the separately accepted protected input after actual human approval;
    # composition below still enforces the full candidate tuple and freshness.
    if manifest['activation']['auth'] in ('dual','neon'):
        manual['neon']=private_json('BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON')
    receipts=compose_workspace_receipts(manifest,{'schema':'buyeros.workspace-release-receipts.v1','items':manual},
        schema_observation=schema,api_observation=api,binding_observation=files['binding-observations.json'],
        configuration_observation=files['configuration-observations.json'],
        schema_observation_sha256=digest(schema),api_observation_sha256=digest(api),source_sha=source,**files['build-evidence.json'])
    bundle=build_workspace_bundle(manifest,receipts,source_sha=source)
    write_encrypted(output,encrypt_workspace_bundle(bundle,os.environ['BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY']))


def main(argv=None):
    global _failure_diagnostic
    _failure_diagnostic=None
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['stage','sign'])
    parser.add_argument('--ci-run-id',type=int)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--diagnostics-output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.operation=='stage': checked('stage',stage,args.ci_run_id,args.output)
        else: checked('sign',sign,args.input,args.output)
        print(json.dumps({'status':'encrypted_runtime_'+args.operation+'_complete'}))
        return 0
    except Exception:
        write_failure_diagnostic(args.diagnostics_output)
        print(json.dumps({'error':{'code':'PROTECTED_RUNTIME_'+args.operation.upper()+'_BLOCKED'}}))
        return 2


if __name__=='__main__': raise SystemExit(main())
