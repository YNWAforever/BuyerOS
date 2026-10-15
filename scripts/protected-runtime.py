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
from runtime_bundle import (canonical_json,unique_keys,encrypt_observation_packet,decrypt_observation_packet,
                            build_workspace_bundle,compose_workspace_receipts,encrypt_workspace_bundle)

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/api'))
from buyeros_api.services.release_binding import database_target_sha256,database_endpoint_sha256
from buyeros_api.services.release_configuration import pulled_configuration_sha256
from buyeros_api.services.schema_readiness import SchemaContract,inspect_schema


def load_script(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'scripts'/name)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def command(argv,*,timeout=45):
    return subprocess.run(argv,check=True,capture_output=True,text=True,timeout=timeout).stdout


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
    project_id=os.environ['VERCEL_PROJECT_ID'];team_id=os.environ['VERCEL_ORG_ID']
    if not re.fullmatch(r'prj_[A-Za-z0-9]+',project_id) or not re.fullmatch(r'team_[A-Za-z0-9]+',team_id):
        raise ValueError('exact project and team required')
    inputs=dict(source=source,ci_run_id=ci_run_id,branch=github('branches/main'),
        protection=github('branches/main/protection'),environment=github('environments/'+ENVIRONMENT),
        project=vercel('/v9/projects/'+project_id+'?teamId='+team_id),project_id=project_id,team_id=team_id,
        run=github('actions/runs/'+str(ci_run_id)),jobs=github('actions/runs/'+str(ci_run_id)+'/jobs?per_page=100'))
    verify_controls(**inputs)
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
    dsn=values.get('BUYEROS_DATABASE_URL','')
    database_target_sha256(dsn)
    for key in ('BUYEROS_PAID_ADMISSION_ENABLED','BUYEROS_DELIVERY_ADMISSION_ENABLED','BUYEROS_CLOUDFLARE_EXECUTION_ENABLED'):
        if values.get(key,'false').lower() not in ('false','0'): raise ValueError('paid or delivery controls are not disabled')
    if values.get('BUYEROS_RELEASE_PROBE_TOKEN')!=os.environ.get('BUYEROS_RELEASE_PROBE_TOKEN'):
        raise ValueError('runtime probe credential not bound to production environment')
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


def stage(ci_run_id,output):
    source=os.environ['GITHUB_SHA']
    if (os.environ.get('GITHUB_REF')!='refs/heads/main'
            or os.environ.get('GITHUB_WORKFLOW')!='BuyerOS protected runtime bundle'
            or os.environ.get('BUYEROS_ENABLE_PROTECTED_STAGE')!='true' or output.exists()):
        raise ValueError('reviewed protected main stage authorization required')
    controls=current_controls(source,ci_run_id)
    # Private templates bind account scope and schema policy before any deployment.
    api=private_json('BUYEROS_G0_TARGET_JSON');schema=SchemaContract.model_validate(private_json('BUYEROS_SCHEMA_CONTRACT_JSON'))
    if (api.get('source_sha')!=source or schema.source_sha!=source or schema.evidence_mode!='candidate_runtime'
            or schema.target_receipt is None or schema.target!=schema.target_receipt
            or digest(api)!=os.environ.get('BUYEROS_G0_CONTRACT_SHA256')
            or digest(schema.model_dump(mode='json',by_alias=True))!=os.environ.get('BUYEROS_SCHEMA_CONTRACT_SHA256')
            or api.get('authorization_reference_sha256')!=os.environ.get('BUYEROS_RUNTIME_READ_SCOPE_SHA256')):
        raise ValueError('source-specific reviewed private templates required')
    reads=load_script('collect-workspace-observations.py')
    tokens={key:os.environ['BUYEROS_G0_'+key.upper()+'_TOKEN'] for key in reads.ACCOUNTS}
    reads.validate(api,tokens,api['origin'])
    rollback_id=os.environ.get('BUYEROS_ROLLBACK_DEPLOYMENT_ID','')
    if re.fullmatch(r'dpl_[A-Za-z0-9_-]+',rollback_id) is None: raise ValueError('reviewed rollback deployment absent')
    rollback=vercel('/v13/deployments/'+rollback_id+'?teamId='+controls['team_id'])
    if (rollback.get('id')!=rollback_id or rollback.get('projectId')!=controls['project_id']
            or rollback.get('ownerId')!=controls['team_id'] or rollback.get('target')!='production'
            or rollback.get('readyState')!='READY'):
        raise ValueError('exact compatible rollback deployment required')
    rollback_artifacts=service_artifacts(rollback)
    pulled=ROOT/'.vercel/.env.production.local'
    try:
        command(['vercel','pull','--yes','--environment=production'],timeout=120)
        values=runtime_env(pulled)
        target=database_target_sha256(values['BUYEROS_DATABASE_URL'])
        expected_endpoint=database_endpoint_sha256(values['BUYEROS_DATABASE_URL'])
        if schema.target.endpoint_sha256!=expected_endpoint:
            raise ValueError('schema target endpoint differs from production binding')
        observed_schema=asyncio.run(schema_observation(values['BUYEROS_DATABASE_URL'],schema))
        rollback_packet={**api,'origin':'https://'+rollback['url']}
        rollback_api=reads.collect(rollback_packet,tokens,rollback_packet['origin'])
        if not rollback_api['all_checks_passed']: raise ValueError('rollback API compatibility failed')
        # Review main at the final boundary before the one staging call.
        current_controls(source,ci_run_id)
        command(['vercel','build','--prod'],timeout=900)
        args=['vercel','deploy','--prebuilt','--prod','--skip-domain','--yes',
              '--env','BUYEROS_RUNTIME_SOURCE_SHA='+source]
        meta={'githubCommitSha':source,'githubCommitOrg':'YNWAforever','githubCommitRepo':'BuyerOS',
              'githubCommitRepoId':str(controls['project']['link']['repoId']),'githubCommitRef':'main'}
        for key,value in meta.items(): args.extend(['--meta',key+'='+value])
        url=command(args,timeout=900).strip().splitlines()[-1]
        if re.fullmatch(r'https://[a-z0-9-]+\.vercel\.app',url) is None: raise ValueError('staging outcome unverified; do not retry')
        created=vercel('/v13/deployments/'+url.removeprefix('https://')+'?teamId='+controls['team_id'])
        deployed,origin=deployment(source,created['id'],controls)
        if deployed.get('aliasAssigned') not in (False,None) or deployed.get('autoAssignCustomDomains') is not False:
            raise ValueError('staged deployment unexpectedly assigned aliases')
        artifacts=service_artifacts(deployed)
        manifest={'schema':'buyeros.release-manifest.v1','source_sha':source,
            'tree_sha':command(['git','rev-parse',source+'^{tree}']).strip(),
            'configuration_sha256':pulled_configuration_sha256(values),'db_target_sha256':target,'schema_contract_sha256':observed_schema['contract_sha256'],
            'frontend_artifact':artifacts['frontend'],'api_artifact':artifacts['api'],'worker_artifact':None,
            'required_heads':observed_schema['observed_heads'],'ci_run_id':ci_run_id,
            'required_ci_jobs':sorted(release_gate().REQUIRED_CI_JOBS),'candidate_deployment_id':deployed['id'],
            'receipt_max_age_seconds':900,'rollback_artifacts':rollback_artifacts,
            'activation':{'auth':values.get('BUYEROS_AUTH_MODE','auth0'),'providers':'disabled','worker':'disabled','delivery':'disabled'}}
        bound=load_script('collect-runtime-binding.py').collect_binding(manifest,origin,values['BUYEROS_DATABASE_URL'],os.environ['BUYEROS_RELEASE_PROBE_TOKEN'])
        observed_configuration=load_script('collect-runtime-binding.py').collect_configuration(manifest,origin,os.environ['BUYEROS_RELEASE_PROBE_TOKEN'])
        observed_api=reads.collect({**api,'origin':origin},tokens,origin)
        if observed_api['all_checks_passed'] is not True: raise ValueError('candidate API controls failed')
        files={'manifest.json':manifest,'schema-observations.json':observed_schema,'api-observations.json':observed_api,
               'binding-observations.json':bound,'configuration-observations.json':observed_configuration,
               'build-evidence.json':{'ci':{'run_id':ci_run_id,'head_sha':source,'status':'completed','conclusion':'success',
                                          'jobs':{row['name']:row['conclusion'] for row in controls['jobs']['jobs']}},
                                     'artifacts':artifacts,'api_contract_sha256':observed_api['contract_sha256']},
               'rollback-receipt.json':{**common(manifest),'data':{**rollback_artifacts,'compatible':True,
                    'deployment_id':rollback_id,'api_observation_sha256':digest(rollback_api),
                    'schema_observation_sha256':digest(observed_schema)}}}
        if manifest['activation']['auth'] in ('dual','neon'):
            files['neon-receipt.json']=private_json('BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON')
        packet={'schema':'buyeros.private-runtime-observations.v1','source_sha':source,
                'origin':origin,'files':files,'stage_run_id':int(os.environ['GITHUB_RUN_ID'])}
        encrypted=encrypt_observation_packet(packet,os.environ['BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY'])
        write_encrypted(output,encrypted)
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
    if 'neon-receipt.json' in files: manual['neon']=files['neon-receipt.json']
    receipts=compose_workspace_receipts(manifest,{'schema':'buyeros.workspace-release-receipts.v1','items':manual},
        schema_observation=schema,api_observation=api,binding_observation=files['binding-observations.json'],
        configuration_observation=files['configuration-observations.json'],
        schema_observation_sha256=digest(schema),api_observation_sha256=digest(api),source_sha=source,**files['build-evidence.json'])
    bundle=build_workspace_bundle(manifest,receipts,source_sha=source)
    write_encrypted(output,encrypt_workspace_bundle(bundle,os.environ['BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY']))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['stage','sign'])
    parser.add_argument('--ci-run-id',type=int)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.operation=='stage': stage(args.ci_run_id,args.output)
        else: sign(args.input,args.output)
        print(json.dumps({'status':'encrypted_runtime_'+args.operation+'_complete'}))
        return 0
    except Exception:
        print(json.dumps({'error':{'code':'PROTECTED_RUNTIME_'+args.operation.upper()+'_BLOCKED'}}))
        return 2


if __name__=='__main__': raise SystemExit(main())
