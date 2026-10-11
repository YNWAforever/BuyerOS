"""Prepare protected read scopes and redact partial observations. No acceptance signing."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'services/api'))
from buyeros_api.services.schema_readiness import SchemaContract


def collector():
    spec = importlib.util.spec_from_file_location('workspace_reads', ROOT/'scripts/collect-workspace-observations.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def publication_request(source_sha, api_digest, schema_digest):
    return {'source_sha': source_sha, 'api_contract_sha256': api_digest, 'schema_contract_sha256': schema_digest,
            'artifact_scope': 'public-redacted-observations-v1'}


def prepare(directory, environment):
    """Require source-specific protected settings before creating any private files."""
    reads = collector()
    source = environment.get('GITHUB_SHA', '')
    if environment.get('GITHUB_REF') != 'refs/heads/main' or not re.fullmatch('[0-9a-f]{40}', source):
        raise ValueError('reviewed main source required')
    def private_json(key):
        value = environment.get(key, '')
        if len(value.encode()) > 65536:
            raise ValueError('private packet too large')
        return json.loads(value, object_pairs_hook=reads.unique_keys)
    api, schema = private_json('BUYEROS_G0_TARGET_JSON'), private_json('BUYEROS_SCHEMA_CONTRACT_JSON')
    tokens = {key: environment.get('BUYEROS_G0_'+key.upper()+'_TOKEN', '') for key in reads.ACCOUNTS}
    reads.validate(api, tokens, environment.get('BUYEROS_G0_ALLOWED_ORIGIN', ''))
    contract = SchemaContract.model_validate(schema)
    if (api['source_sha'] != source or contract.source_sha != source or contract.evidence_mode != 'candidate_runtime'
            or contract.target_receipt is None or contract.target != contract.target_receipt):
        raise ValueError('runtime source or independently reviewed target proof missing')
    if environment.get('BUYEROS_RUNTIME_READ_SCOPE_SHA256') != api['authorization_reference_sha256']:
        raise ValueError('read scope authorization not bound')
    api_digest, schema_digest = canonical_digest(api), canonical_digest(contract.model_dump(mode='json'))
    if (environment.get('BUYEROS_G0_CONTRACT_SHA256') != api_digest
            or environment.get('BUYEROS_SCHEMA_CONTRACT_SHA256') != schema_digest):
        raise ValueError('protected reviewed contract digest mismatch')
    # Public workflow existence/conclusion is itself a disclosure, even when
    # detailed artifact publication is disabled. Bind that scope separately.
    workflow_request = dict(publication_request(source, api_digest, schema_digest), artifact_scope='public-workflow-status-v1')
    if environment.get('BUYEROS_RUNTIME_WORKFLOW_REQUEST_SHA256') != canonical_digest(workflow_request):
        raise ValueError('exact public workflow status disclosure authorization absent')
    publish = environment.get('PUBLISH_OBSERVATIONS', 'false')
    if publish not in ('true', 'false'):
        raise ValueError('invalid publication selection')
    if publish == 'true' and (environment.get('BUYEROS_RUNTIME_PUBLICATION_SCOPE') != 'public-redacted-observations-v1'
            or environment.get('BUYEROS_RUNTIME_PUBLICATION_REQUEST_SHA256') != canonical_digest(publication_request(source, api_digest, schema_digest))):
        raise ValueError('exact publication payload authorization absent')
    if directory.exists():
        raise ValueError('immutable private packet directory exists')
    directory.mkdir(mode=0o700, parents=True)
    for name, value in [('api-contract.json', api), ('schema-contract.json', contract.model_dump(mode='json'))]:
        descriptor = os.open(directory/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(json.dumps(value, indent=2)+'\n')
    return {'source_sha': source, 'publish': publish == 'true'}


def summarize(directory, source_sha):
    """Export only fixed counters, hashes and status; never whole private receipts."""
    reads = collector()
    def native(name, schema):
        try:
            path = directory/name
            raw = path.read_bytes()
            if len(raw) > reads.MAX_BODY:
                raise ValueError('receipt too large')
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=reads.unique_keys)
            if type(value) is not dict or value.get('schema') != schema:
                raise ValueError('wrong native receipt')
            return value, hashlib.sha256(raw).hexdigest()
        except (OSError, ValueError, UnicodeError):
            return {}, None
    api, api_digest = native('api-observations.json', 'buyeros.workspace-api-observations.v1')
    schema, schema_digest = native('schema-observations.json', 'buyeros.schema-readiness.v1')
    api_checks = api.get('checks', [])
    schema_checks = schema.get('checks', [])
    api_pass = (api.get('reviewed_source_sha') == source_sha and api.get('all_checks_passed') is True
                and type(api_checks) is list and len(api_checks) == 7
                and all(type(check) is dict and check.get('passed') is True for check in api_checks))
    schema_pass = (schema.get('source_sha') == source_sha and schema.get('evidence_mode') == 'candidate_runtime'
                   and schema.get('compatible') is True and schema.get('target_match') is True
                   and schema.get('blockers') == [] and type(schema_checks) is list and bool(schema_checks)
                   and all(type(check) is dict and check.get('passed') is True for check in schema_checks))
    return {'schema': 'buyeros.runtime-observations.v1', 'reviewed_source_sha': source_sha,
            'api': {'receipt_sha256': api_digest, 'checks_passed': api_pass},
            'database': {'receipt_sha256': schema_digest, 'checks_passed': schema_pass},
            'all_read_checks_passed': api_pass and schema_pass, 'promotable': False,
            'acceptance_blockers': ['exact_deployment_db_binding_unproven', 'canonical_mapping_not_collected',
                                    'browser_canary_not_collected', 'compatible_frontend_api_rollback_not_collected']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'summarize'])
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.operation == 'prepare':
            print(json.dumps(prepare(args.directory, dict(os.environ))))
            return 0
        if args.output is None or args.output.exists():
            raise ValueError('immutable summary output required')
        result = summarize(args.directory, os.environ['GITHUB_SHA'])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            output.write(json.dumps(result, indent=2)+'\n')
        print(json.dumps({'all_read_checks_passed': result['all_read_checks_passed'], 'promotable': False}))
        return 0 if result['all_read_checks_passed'] else 1
    except Exception:
        print(json.dumps({'error': {'code': 'INVALID_OR_UNAVAILABLE_RUNTIME_OBSERVATIONS'}}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
