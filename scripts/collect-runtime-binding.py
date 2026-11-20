"""Compare protected API reads with the independently reviewed release target."""
from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/api'))
from buyeros_api.services.release_binding import database_target_sha256
from runtime_failure_diagnostic import RuntimeProbeError, TRANSIENT_PROBE_FAILURES

BINDING_KEYS = {'schema', 'source_sha', 'deployment_id', 'schema_head', 'db_target_sha256'}
BINDING_FAILURES = {
    'source_matches': 'binding_source_mismatch',
    'deployment_matches': 'binding_deployment_mismatch',
    'database_target_matches': 'binding_database_mismatch',
    'schema_head_matches': 'binding_schema_head_mismatch',
}


def collector():
    spec = importlib.util.spec_from_file_location('bound_workspace_reads', ROOT / 'scripts/collect-workspace-observations.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_document(read, url, token):
    status, body = read(url, token)
    if type(body) is not dict:
        raise RuntimeProbeError('runtime_malformed_response', http_status=status)
    if status != 200 or type(status) is not int:
        raise RuntimeProbeError.for_http_status(status)
    return body


def binding_matches(body, source_sha, deployment_id, database_target, required_heads):
    if (type(body) is not dict or set(body) != BINDING_KEYS or body['schema'] != 'buyeros.runtime-db-binding.v1'
            or any(type(body[key]) is not str for key in BINDING_KEYS)):
        raise RuntimeProbeError('runtime_malformed_response', http_status=200)
    return {
        'source_matches': body['source_sha'] == source_sha,
        'deployment_matches': body['deployment_id'] == deployment_id,
        'database_target_matches': body['db_target_sha256'] == database_target,
        'schema_head_matches': [body['schema_head']] == required_heads if required_heads is not None else None,
    }


def collect_binding(manifest, origin, database_url, token, *, get=None):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or parsed.path or parsed.query or parsed.fragment or parsed.username
            or parsed.password or not parsed.hostname or not parsed.hostname.endswith('.vercel.app')
            or parsed.port is not None or len(token) < 32 or len(token) > 512 or not token.isascii()
            or any(c.isspace() for c in token)):
        raise ValueError('bounded staged origin and probe credential required')
    expected = database_target_sha256(database_url)
    if expected != manifest['db_target_sha256']:
        raise RuntimeProbeError('binding_independent_target_mismatch')
    read = get or collector().get_json
    url = origin + '/v1/internal/release-binding'
    try:
        body = probe_document(read, url, token)
    except RuntimeProbeError as error:
        if error.category not in TRANSIENT_PROBE_FAILURES:
            raise
        time.sleep(3)
        body = probe_document(read, url, token)
    matches = binding_matches(body, manifest['source_sha'], manifest['candidate_deployment_id'],
                              expected, manifest['required_heads'])
    for check, category in BINDING_FAILURES.items():
        if not matches[check]:
            raise RuntimeProbeError(category, http_status=200)
    common = {key: manifest[key] for key in ('source_sha', 'tree_sha', 'configuration_sha256', 'db_target_sha256')}
    return {**common, 'deployment_id': manifest['candidate_deployment_id'],
            'checked_at': datetime.now(timezone.utc).isoformat(), 'evidence_mode': 'candidate_runtime',
            'data': {'schema': 'buyeros.deployment-db-binding.v1', 'verified': True,
                     'source_sha': body['source_sha'], 'deployment_id': body['deployment_id'],
                     'db_target_sha256': expected, 'schema_head': body['schema_head'],
                     'api_origin_sha256': hashlib.sha256(origin.encode()).hexdigest()}}


def collect_configuration(manifest, origin, token, *, get=None):
    if (re.fullmatch(r'https://[a-z0-9-]+\.vercel\.app', origin) is None or len(token) < 32
            or len(token) > 512 or not token.isascii() or any(c.isspace() for c in token)):
        raise ValueError('bounded staged origin and probe credential required')
    body = probe_document(get or collector().get_json, origin + '/v1/internal/release-configuration', token)
    if (set(body) != {'schema', 'source_sha', 'deployment_id', 'configuration_sha256', 'activation'}
            or body['schema'] != 'buyeros.runtime-configuration.v1'):
        raise RuntimeProbeError('runtime_malformed_response', http_status=200)
    for field, manifest_field, category in (
        ('source_sha', 'source_sha', 'binding_source_mismatch'),
        ('deployment_id', 'candidate_deployment_id', 'binding_deployment_mismatch'),
        ('configuration_sha256', 'configuration_sha256', 'configuration_fingerprint_mismatch'),
    ):
        if body[field] != manifest[manifest_field]:
            raise RuntimeProbeError(category, http_status=200)
    activation = body['activation']
    if (type(activation) is not dict or set(activation) != {'providers', 'worker', 'delivery', 'contact_enrichment'}
            or any(activation[key] != 'disabled' for key in ('providers', 'worker', 'delivery'))
            or activation['contact_enrichment'] not in ('disabled', 'unconfigured')):
        raise RuntimeProbeError('configuration_activation_mismatch', http_status=200)
    common = {key: manifest[key] for key in ('source_sha', 'tree_sha', 'configuration_sha256', 'db_target_sha256')}
    return {**common, 'deployment_id': manifest['candidate_deployment_id'],
            'checked_at': datetime.now(timezone.utc).isoformat(), 'evidence_mode': 'candidate_runtime', 'data': body}
