"""Workspace-only signed bundle composition and authenticated encryption."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_SCHEMA = 'buyeros.attested-runtime-bundle.v1'
ENVELOPE_SCHEMA = 'buyeros.encrypted-runtime-bundle.v1'
ENVELOPE_KEYS = {'schema', 'algorithm', 'source_sha', 'nonce', 'ciphertext'}
BUNDLE_KEYS = {'schema', 'manifest', 'receipts'}
AAD_PREFIX = b'BuyerOS workspace release bundle v1:'
MAX_BUNDLE_BYTES = 4 * 1024 * 1024


def _release_gate():
    spec = importlib.util.spec_from_file_location('release_readiness_for_bundle', ROOT/'scripts/check-release-readiness.py')
    if spec is None or spec.loader is None:
        raise ValueError('workspace release gate unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def canonical_json(value: Any) -> bytes:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValueError('bundle input is not canonical JSON') from error
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError('runtime bundle too large')
    return raw


def _key_bytes(key_hex: str) -> bytes:
    if type(key_hex) is not str or re.fullmatch(r'[0-9a-fA-F]{64}', key_hex) is None:
        raise ValueError('runtime bundle encryption key unavailable')
    return bytes.fromhex(key_hex)


API_EXPECTED = {
    'owned_workspace_roles_response': 200, 'owned_project_response': 200,
    'empty_directory_response': 200, 'empty_account_project_not_found': 404,
    'revoked_account_project_not_found': 404, 'foreign_tenant_project_not_found': 404,
    'foreign_account_owned_project_response': 200,
}


def _fresh(value, maximum):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None or not -30 <= (datetime.now(timezone.utc)-stamp).total_seconds() <= maximum:
        raise ValueError('runtime evidence is stale or future')


def _digest(value):
    return type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def _api_valid(api, source, contract, maximum):
    keys = {'schema','reviewed_source_sha','contract_sha256','checked_at','scope','checks',
            'all_checks_passed','promotable','acceptance_blockers'}
    if (type(api) is not dict or set(api) != keys
            or api['schema'] != 'buyeros.workspace-api-observations.v1'
            or api['reviewed_source_sha'] != source or api['contract_sha256'] != contract
            or not _digest(contract) or api['scope'] != 'bounded_api_reads_only'
            or api['all_checks_passed'] is not True or api['promotable'] is not False
            or type(api['checks']) is not list or len(api['checks']) != len(API_EXPECTED)):
        raise ValueError('complete bounded API read observations required')
    names = []
    for check in api['checks']:
        if (type(check) is not dict or set(check) != {'code','passed','observed_status','response_sha256'}
                or check.get('passed') is not True or check.get('code') not in API_EXPECTED
                or type(check['observed_status']) is not int
                or check['observed_status'] != API_EXPECTED[check['code']] or not _digest(check['response_sha256'])):
            raise ValueError('complete bounded API read observations required')
        names.append(check['code'])
    if len(set(names)) != len(API_EXPECTED):
        raise ValueError('unique bounded API observations required')
    _fresh(api['checked_at'], maximum)


def _human_canary(canary):
    if (canary.get('human_signoff') is not True
            or any(type(canary.get(key)) is not int or canary[key] <= 0
                   for key in ('reviewer_id','initiator_id','approval_run_id'))
            or canary['reviewer_id'] == canary['initiator_id']
            or any(not _digest(canary.get(key)) for key in ('browser_canary_sha256','approval_comment_sha256',
                                                          'api_observation_sha256','schema_observation_sha256'))):
        raise ValueError('verified non-self human browser signoff required')


def compose_workspace_receipts(manifest: dict, protected_receipts: dict, *, schema_observation: dict,
                               api_observation: dict, schema_observation_sha256: str,
                               api_observation_sha256: str, api_contract_sha256: str,
                               ci: dict, artifacts: dict, source_sha: str,
                               binding_observation: dict | None = None,
                               configuration_observation: dict | None = None) -> dict:
    """Join actual candidate reads with separately verified human/rollback evidence."""
    gate = _release_gate()
    if not gate._manifest_valid(manifest) or manifest['source_sha'] != source_sha:
        raise ValueError('release manifest source mismatch')
    expected_manual = {'workspace_canary','rollback'}
    if manifest['activation']['auth'] in ('dual','neon'):
        expected_manual.add('neon')
    if (type(protected_receipts) is not dict or set(protected_receipts) != {'schema','items'}
            or protected_receipts['schema'] != 'buyeros.workspace-release-receipts.v1'
            or type(protected_receipts['items']) is not dict or set(protected_receipts['items']) != expected_manual):
        raise ValueError('protected workspace canary and rollback receipts required')
    if not _digest(schema_observation_sha256) or not _digest(api_observation_sha256):
        raise ValueError('native observation digests required')
    _api_valid(api_observation, source_sha, api_contract_sha256, manifest['receipt_max_age_seconds'])
    canary = protected_receipts['items']['workspace_canary'].get('data', {})
    if (canary.get('api_observation_sha256') != api_observation_sha256
            or canary.get('schema_observation_sha256') != schema_observation_sha256):
        raise ValueError('reviewed browser canary must bind current read observations')
    _human_canary(canary)
    if (type(artifacts) is not dict or set(artifacts) != {'frontend','api'}
            or any(artifacts[key] != manifest[key+'_artifact'] for key in artifacts)):
        raise ValueError('verified candidate service artifacts do not match the manifest')
    common = {key: manifest[key] for key in ('source_sha','tree_sha','configuration_sha256','db_target_sha256')}
    common.update(deployment_id=manifest['candidate_deployment_id'],
                  checked_at=datetime.now(timezone.utc).isoformat(), evidence_mode='candidate_runtime')
    items = json.loads(canonical_json(protected_receipts['items']))
    items['workspace_canary']['data']['api_observation'] = api_observation
    items.update(ci={**common, 'data':ci}, artifacts={**common, 'data':artifacts},
                 schema={**common, 'data':schema_observation}, deployment_binding=binding_observation,
                 runtime_configuration=configuration_observation)
    receipts = {'schema':'buyeros.release-receipts.v1','items':items}
    if gate.evaluate_release(manifest, receipts, 'workspace')['promotable'] is not True:
        raise ValueError('workspace release receipts do not pass the complete live gate')
    return receipts


def build_workspace_bundle(manifest: dict, receipts: dict, *, source_sha: str, gate: str = 'workspace') -> dict:
    """Return a bundle only when the complete fresh workspace gate passes."""
    if gate != 'workspace':
        raise ValueError('workspace gate only')
    if type(source_sha) is not str or re.fullmatch(r'[0-9a-f]{40}', source_sha) is None:
        raise ValueError('reviewed main source required')
    if type(manifest) is not dict or manifest.get('source_sha') != source_sha:
        raise ValueError('workspace release receipts do not match the reviewed source')
    evaluation = _release_gate().evaluate_release(manifest, receipts, 'workspace')
    if evaluation.get('status') != 'ready' or evaluation.get('promotable') is not True:
        raise ValueError('workspace release receipts do not pass the complete live gate')
    canary = receipts['items']['workspace_canary']['data']
    _human_canary(canary)
    _api_valid(canary.get('api_observation'), source_sha, canary.get('api_observation', {}).get('contract_sha256'), manifest['receipt_max_age_seconds'])
    bundle = {'schema': BUNDLE_SCHEMA, 'manifest': manifest, 'receipts': receipts}
    canonical_json(bundle)
    return bundle


def encrypt_workspace_bundle(bundle: dict, key_hex: str) -> dict:
    """Encrypt full customer/runtime receipts; only the ciphertext is publishable."""
    if type(bundle) is not dict or set(bundle) != BUNDLE_KEYS or bundle.get('schema') != BUNDLE_SCHEMA:
        raise ValueError('invalid workspace runtime bundle')
    source_sha = bundle.get('manifest', {}).get('source_sha') if type(bundle.get('manifest')) is dict else None
    if type(source_sha) is not str or re.fullmatch(r'[0-9a-f]{40}', source_sha) is None:
        raise ValueError('invalid workspace bundle source')
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key_bytes(key_hex)).encrypt(nonce, canonical_json(bundle), AAD_PREFIX + source_sha.encode('ascii'))
    return {
        'schema': ENVELOPE_SCHEMA,
        'algorithm': 'AES-256-GCM',
        'source_sha': source_sha,
        'nonce': base64.b64encode(nonce).decode('ascii'),
        'ciphertext': base64.b64encode(ciphertext).decode('ascii'),
    }


def _validate_envelope(envelope: dict) -> tuple[str, bytes, bytes]:
    if (type(envelope) is not dict or set(envelope) != ENVELOPE_KEYS
            or envelope.get('schema') != ENVELOPE_SCHEMA or envelope.get('algorithm') != 'AES-256-GCM'
            or type(envelope.get('source_sha')) is not str
            or re.fullmatch(r'[0-9a-f]{40}', envelope['source_sha']) is None):
        raise ValueError('encrypted workspace bundle required')
    try:
        nonce = base64.b64decode(envelope['nonce'], validate=True)
        ciphertext = base64.b64decode(envelope['ciphertext'], validate=True)
    except (TypeError, ValueError) as error:
        raise ValueError('invalid encrypted workspace bundle') from error
    if len(nonce) != 12 or not 16 < len(ciphertext) <= MAX_BUNDLE_BYTES + 16:
        raise ValueError('invalid encrypted workspace bundle size')
    return envelope['source_sha'], nonce, ciphertext


def is_encrypted_workspace_bundle(envelope: dict) -> bool:
    try:
        _validate_envelope(envelope)
    except ValueError:
        return False
    return True


def decrypt_workspace_bundle(envelope: dict, key_hex: str) -> dict:
    source_sha, nonce, ciphertext = _validate_envelope(envelope)
    try:
        plaintext = AESGCM(_key_bytes(key_hex)).decrypt(nonce, ciphertext, AAD_PREFIX + source_sha.encode('ascii'))
        if len(plaintext) > MAX_BUNDLE_BYTES:
            raise ValueError('runtime bundle too large')
        bundle = json.loads(plaintext.decode('utf-8'), object_pairs_hook=unique_keys)
    except (InvalidTag, ValueError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('encrypted workspace bundle authentication failed') from error
    if (type(bundle) is not dict or set(bundle) != BUNDLE_KEYS or bundle.get('schema') != BUNDLE_SCHEMA
            or type(bundle.get('manifest')) is not dict or bundle['manifest'].get('source_sha') != source_sha):
        raise ValueError('invalid decrypted workspace bundle')
    return bundle


def bundle_request_digest(source_sha: str, manifest: dict, receipts: dict) -> str:
    """Exact disclosure authorization for one reviewed source and receipt payload."""
    request = {
        'source_sha': source_sha,
        'manifest_sha256': hashlib.sha256(canonical_json(manifest)).hexdigest(),
        'receipts_sha256': hashlib.sha256(canonical_json(receipts)).hexdigest(),
        'candidate_deployment_id': manifest.get('candidate_deployment_id') if type(manifest) is dict else None,
        'artifact_scope': 'encrypted-workspace-release-bundle-v1',
    }
    return hashlib.sha256(canonical_json(request)).hexdigest()


OBSERVATION_SCHEMA = 'buyeros.encrypted-observation-packet.v1'
OBSERVATION_AAD = b'BuyerOS private runtime observations v1:'


def encrypt_observation_packet(packet: dict, key_hex: str) -> dict:
    source = packet.get('source_sha') if type(packet) is dict else None
    if (packet.get('schema') != 'buyeros.private-runtime-observations.v1'
            or type(source) is not str or re.fullmatch(r'[0-9a-f]{40}', source) is None):
        raise ValueError('invalid private runtime observations')
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key_bytes(key_hex)).encrypt(nonce, canonical_json(packet), OBSERVATION_AAD+source.encode())
    return {'schema':OBSERVATION_SCHEMA,'algorithm':'AES-256-GCM','source_sha':source,
            'nonce':base64.b64encode(nonce).decode(),'ciphertext':base64.b64encode(ciphertext).decode()}


def decrypt_observation_packet(envelope: dict, key_hex: str) -> dict:
    if type(envelope) is not dict or envelope.get('schema') != OBSERVATION_SCHEMA:
        raise ValueError('encrypted observations required')
    validation = {**envelope, 'schema':ENVELOPE_SCHEMA}
    source, nonce, ciphertext = _validate_envelope(validation)
    try:
        value = AESGCM(_key_bytes(key_hex)).decrypt(nonce, ciphertext, OBSERVATION_AAD+source.encode())
        packet = json.loads(value.decode(), object_pairs_hook=unique_keys)
        if (type(packet) is not dict or packet.get('schema') != 'buyeros.private-runtime-observations.v1'
                or packet.get('source_sha') != source):
            raise ValueError('invalid observations')
        return packet
    except (InvalidTag, ValueError, UnicodeError, TypeError) as error:
        raise ValueError('encrypted observations authentication failed') from error
