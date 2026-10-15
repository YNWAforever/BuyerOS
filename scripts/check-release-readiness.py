"""Join immutable runtime/build receipts. Does not grant deployment authority."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

MANIFEST_KEYS={'schema','source_sha','tree_sha','configuration_sha256','db_target_sha256','schema_contract_sha256',
    'frontend_artifact','api_artifact','worker_artifact','required_heads','ci_run_id',
    'required_ci_jobs','candidate_deployment_id','receipt_max_age_seconds','rollback_artifacts','activation'}
COMMON_KEYS={'source_sha','tree_sha','configuration_sha256','db_target_sha256','deployment_id','checked_at','evidence_mode','data'}
WORKSPACE=('ci','artifacts','schema','workspace_canary','rollback','deployment_binding','runtime_configuration')
RESEARCH=WORKSPACE+('neon','worker','providers','quality','performance','staff_uat','journey')
GATES={'workspace':WORKSPACE,'research_export':RESEARCH,'native_send':RESEARCH+('auth0_retirement','delivery')}
# A submitted manifest cannot omit a failing original required job.
REQUIRED_CI_JOBS=frozenset({'frontend','api','worker','browser-smoke','browser-continuity','browser-zoom',
    'audit-fixes','owned-worker-capacity','cloudflare-controller','cloudflare-staff-acceptance',
    'c61-evidence-checker','release-readiness'})


def _time(value):
    if type(value) is not str: raise ValueError('invalid receipt time')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise ValueError('receipt time requires timezone')
    return result


def _manifest_valid(manifest):
    if type(manifest) is not dict or set(manifest)!=MANIFEST_KEYS or manifest['schema']!='buyeros.release-manifest.v1':return False
    for key,length in [('source_sha',40),('tree_sha',40),('configuration_sha256',64),('db_target_sha256',64),('schema_contract_sha256',64)]:
        if type(manifest[key]) is not str or not re.fullmatch('[0-9a-f]{'+str(length)+'}',manifest[key]):return False
    if type(manifest['ci_run_id']) is not int or manifest['ci_run_id']<=0:return False
    if type(manifest['receipt_max_age_seconds']) is not int or not 1<=manifest['receipt_max_age_seconds']<=900:return False
    for key in ['required_heads','required_ci_jobs']:
        values=manifest[key]
        if type(values) is not list or not values or len(values)>100 or any(type(v) is not str or not v for v in values) or len(set(values))!=len(values):return False
    if type(manifest['candidate_deployment_id']) is not str or not re.fullmatch(r'dpl_[A-Za-z0-9_-]+',manifest['candidate_deployment_id']):return False
    if type(manifest['rollback_artifacts']) is not dict or set(manifest['rollback_artifacts'])!={'frontend','api'}:return False
    if type(manifest['activation']) is not dict or set(manifest['activation'])!={'auth','providers','worker','delivery'}:return False
    if manifest['activation']['auth'] not in ('auth0','dual','neon'):return False
    if any(manifest['activation'][key] not in ('disabled','active') for key in ('providers','worker','delivery')):return False
    if set(manifest['required_ci_jobs'])!=REQUIRED_CI_JOBS:return False
    return True


def evaluate_release(manifest: dict, receipts: dict, gate: str) -> dict:
    result={'schema':'buyeros.release-evaluation.v1','gate':gate,'status':'malformed','promotable':False,'blockers':[]}
    if gate not in GATES or not _manifest_valid(manifest):
        result['blockers']=['invalid_manifest_or_gate'];return result
    if type(receipts) is not dict or set(receipts)!={'schema','items'} or receipts['schema']!='buyeros.release-receipts.v1' or type(receipts['items']) is not dict:
        result['blockers']=['invalid_receipt_bundle'];return result
    if not set(receipts['items'])<=set(GATES['native_send']):
        result['blockers']=['unknown_receipt_key'];return result
    blockers=result['blockers'];now=datetime.now(timezone.utc);items=receipts['items']
    def require(passed,code):
        if passed is not True:blockers.append(code)
    required_names=set(GATES[gate])
    if manifest['activation']['auth'] in ('dual','neon'):required_names.add('neon')
    for name in required_names|set(items):
        if name not in items:
            blockers.append('receipt_missing:'+name);continue
        receipt=items[name]
        if type(receipt) is not dict or set(receipt)!=COMMON_KEYS or type(receipt.get('data')) is not dict:
            blockers.append('receipt_malformed:'+name);continue
        for key in ['source_sha','tree_sha','configuration_sha256','db_target_sha256']:
            require(receipt[key]==manifest[key],'receipt_tuple_mismatch:'+name+':'+key)
        require(receipt['deployment_id']==manifest['candidate_deployment_id'],'receipt_deployment_mismatch:'+name)
        require(receipt['evidence_mode'] in ('candidate_runtime','production_readback'),'receipt_not_live:'+name)
        try:
            age=(now-_time(receipt['checked_at'])).total_seconds()
            require(-30<=age<=manifest['receipt_max_age_seconds'],'receipt_stale_or_future:'+name)
        except (ValueError,TypeError,OverflowError):blockers.append('receipt_time_invalid:'+name)
    def data(name):
        receipt=items.get(name,{})
        return receipt.get('data',{}) if type(receipt) is dict and type(receipt.get('data')) is dict else {}

    ci=data('ci')
    require(ci.get('run_id')==manifest['ci_run_id'] and type(ci.get('run_id')) is int,'ci_run_mismatch')
    require(ci.get('head_sha')==manifest['source_sha'],'ci_source_mismatch')
    require(ci.get('status')=='completed' and ci.get('conclusion')=='success','ci_not_completed_successfully')
    jobs=ci.get('jobs',{})
    require(type(jobs) is dict and all(jobs.get(job)=='success' for job in manifest['required_ci_jobs']),'ci_required_jobs_missing_or_failed')
    artifacts=data('artifacts')
    for key in ['frontend','api']+(['worker'] if gate!='workspace' else []):
        required=manifest[key+'_artifact']
        require(type(required) is str and bool(required) and artifacts.get(key)==required,'artifact_missing_or_mismatched:'+key)
    schema=data('schema')
    require(schema.get('schema')=='buyeros.schema-readiness.v1' and schema.get('source_sha')==manifest['source_sha'],'schema_receipt_source_mismatch')
    require(schema.get('contract_sha256')==manifest['schema_contract_sha256'],'schema_contract_mismatch')
    require(schema.get('compatible') is True and schema.get('target_match') is True and schema.get('blockers')==[],'schema_incompatible_or_target_unknown')
    require(schema.get('evidence_mode') in ('candidate_runtime','production_readback'),'schema_not_live')
    require(schema.get('observed_heads')==manifest['required_heads'],'schema_head_mismatch')
    checks=schema.get('checks')
    required_checks={'target_unproven_or_mismatched','runtime_role_mismatch','runtime_role_privileged','schema_head_unknown','required_revision_unproven',
        'relation_missing:public.user_identities','function_missing_or_denied:public.buyeros_workspace_directory(uuid,bigint,integer)'}
    required_checks|={'version_metadata_unreadable','schema_usage_missing:public','relation_missing:public.memberships',
        'relation_not_visible:public.user_identities','relation_not_visible:public.memberships',
        'relation_columns_missing:public.user_identities','relation_columns_missing:public.memberships',
        'privilege_missing:public.user_identities:SELECT','rls_not_forced:public.memberships',
        'function_contract_mismatch:public.buyeros_workspace_directory(uuid,bigint,integer)'}
    valid_checks=type(checks) is list and bool(checks) and all(type(c) is dict and set(c)=={'code','passed'} and type(c['code']) is str and c['passed'] is True for c in checks)
    codes=[c['code'] for c in checks] if valid_checks else []
    require(valid_checks and len(codes)==len(set(codes)) and required_checks<=set(codes),'schema_required_checks_missing_or_failed')
    try:require(-30<=(now-_time(schema.get('checked_at'))).total_seconds()<=manifest['receipt_max_age_seconds'],'schema_receipt_stale_or_future')
    except (ValueError,TypeError,OverflowError):blockers.append('schema_receipt_time_invalid')
    binding=data('deployment_binding')
    binding_keys={'schema','verified','source_sha','deployment_id','db_target_sha256','schema_head','api_origin_sha256'}
    require(set(binding)==binding_keys and binding.get('schema')=='buyeros.deployment-db-binding.v1'
        and binding.get('verified') is True
        and binding.get('source_sha')==manifest['source_sha']
        and binding.get('deployment_id')==manifest['candidate_deployment_id']
        and binding.get('db_target_sha256')==manifest['db_target_sha256']
        and [binding.get('schema_head')]==manifest['required_heads']==schema.get('observed_heads')
        and type(binding.get('api_origin_sha256')) is str
        and re.fullmatch(r'[0-9a-f]{64}',binding['api_origin_sha256']) is not None,
        'deployment_db_binding_unverified')
    configuration=data('runtime_configuration')
    effective=configuration.get('activation',{})
    require(set(configuration)=={'schema','source_sha','deployment_id','configuration_sha256','activation'}
        and configuration.get('schema')=='buyeros.runtime-configuration.v1'
        and configuration.get('source_sha')==manifest['source_sha']
        and configuration.get('deployment_id')==manifest['candidate_deployment_id']
        and configuration.get('configuration_sha256')==manifest['configuration_sha256']
        and type(effective) is dict and set(effective)=={'providers','worker','delivery','contact_enrichment'}
        and all(effective.get(key)==manifest['activation'][key] for key in ('providers','worker','delivery'))
        and effective.get('contact_enrichment') in ('disabled','unconfigured'),
        'effective_runtime_configuration_unverified')
    canary=data('workspace_canary')
    require(type(canary.get('workspace_status')) is int and canary.get('workspace_status')==200,'workspace_canary_failed')
    for key in ['correct_roles','correct_project','empty_membership_verified','revoked_denied','foreign_tenant_denied','reload_retry_verified']:
        require(canary.get(key) is True,'workspace_canary_missing:'+key)
    rollback=data('rollback')
    for key in ['frontend','api']:
        artifact=manifest['rollback_artifacts'][key]
        require(type(artifact) is str and bool(artifact) and rollback.get(key)==artifact,'rollback_artifact_missing_or_mismatched:'+key)
    require(rollback.get('compatible') is True,'rollback_not_verified')
    if manifest['activation']['auth'] in ('dual','neon'):
        require(data('neon').get('accepted') is True,'neon_activation_acceptance_missing')
        require(data('neon').get('neon_only_rollback_verified') is True,'neon_only_rollback_missing')
    if gate=='workspace':
        for capability in ('providers','worker','delivery'):
            require(manifest['activation'][capability]=='disabled','activation_exceeds_workspace_gate:'+capability)
    if gate=='research_export':
        require(manifest['activation']['delivery']=='disabled','delivery_requires_native_send_gate')
    if gate!='workspace':
        require(manifest['activation']['auth']=='neon','neon_not_active')
        require(manifest['activation']['providers']=='active','providers_not_active')
        require(manifest['activation']['worker']=='active','worker_not_active')
        for name in ['neon','worker','providers','quality','performance','staff_uat','journey']:
            require(data(name).get('accepted') is True,'acceptance_missing:'+name)
        require(data('neon').get('neon_only_rollback_verified') is True,'neon_only_rollback_missing')
        require(data('staff_uat').get('human_signoff') is True,'human_signoff_missing')
        require(data('journey').get('same_chain_verified') is True,'same_chain_not_verified')
    if gate=='native_send':
        require(manifest['activation']['delivery']=='active','delivery_not_active')
        require(data('auth0_retirement').get('accepted') is True,'auth0_not_retired')
        delivery=data('delivery')
        for key in ['authority_verified','recipient_scope_verified','cost_cap_verified','approved_revision_verified','single_submit_verified','callback_verified','suppression_verified','unknown_hold_preserved']:
            require(delivery.get(key) is True,'delivery_acceptance_missing:'+key)
        require(delivery.get('provider_state')=='delivered','delivery_not_delivered')
    result['blockers']=sorted(set(blockers))
    result['status']='blocked' if blockers else 'ready'
    result['promotable']=not blockers
    return result


def unique_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key')
        result[key]=value
    return result


def read_json(path):
    if path.stat().st_size>4*1024*1024:raise ValueError('input too large')
    return json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_keys)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Evaluate bound runtime receipts; no external writes')
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--receipts',required=True,type=Path)
    parser.add_argument('--gate',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output.exists():raise ValueError('immutable output already exists')
        result=evaluate_release(read_json(args.manifest),read_json(args.receipts),args.gate)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as output:output.write(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'blockers':result['blockers']}))
        return {'ready':0,'blocked':1,'malformed':2}[result['status']]
    except (ValueError,TypeError,OSError,UnicodeError,RecursionError):
        print(json.dumps({'status':'malformed','blockers':['invalid_input_or_output']}));return 2


if __name__=='__main__':raise SystemExit(main())
