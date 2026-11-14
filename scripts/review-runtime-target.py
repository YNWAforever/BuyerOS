"""Owner/main-only read-only diagnostics; encrypted output is never release evidence."""
import base64
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/api'))
from sqlalchemy.engine import make_url
from buyeros_api.services.release_binding import database_target_sha256, database_endpoint_sha256

SPEC = importlib.util.spec_from_file_location('input_review', ROOT / 'scripts/prepare-release-input-review.py')
INPUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INPUT)
TEAM = 'team_qvzlsFmfCsLkgItSypqHjw3z'
PROJECT = 'prj_qLOzTdqNiKvoS5rBjy5zZ2GeZgMw'
ALIAS_PATH = '/v4/aliases/buyer-os-nu.vercel.app?teamId=' + TEAM
FAILURE = 'BLOCKED: encrypted runtime-target review could not be prepared'


def management(path, token):
    if (path != ALIAS_PATH and re.fullmatch(r'/v13/deployments/dpl_[A-Za-z0-9_-]+\?teamId=' + TEAM, path) is None):
        raise ValueError('fixed management route required')
    if not isinstance(token, str) or not 20 <= len(token) <= 512 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError('bounded management credential required')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), INPUT.COLLECTOR.NoRedirect())
    request = urllib.request.Request('https://api.vercel.com' + path,
                                     headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
    with opener.open(request, timeout=10) as response:
        if response.status != 200 or response.geturl() != request.full_url or response.headers.get_content_type() != 'application/json':
            raise ValueError('fixed JSON management result required')
        raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('bounded management result required')
    return INPUT.private_json(raw.decode()) if len(raw) <= INPUT.MAX_JSON_BYTES else json.loads(raw, object_pairs_hook=INPUT.COLLECTOR.unique_keys, parse_constant=INPUT.reject_constant)


def canonical_target(environment, api):
    alias = api(ALIAS_PATH, environment['VERCEL_TOKEN'])
    deployment_id = alias.get('deploymentId') if type(alias) is dict else None
    if (type(alias) is not dict or alias.get('alias') != 'buyer-os-nu.vercel.app' or alias.get('redirect') is not None
            or not isinstance(deployment_id, str) or re.fullmatch(r'dpl_[A-Za-z0-9_-]+', deployment_id) is None):
        raise ValueError('canonical assignment required')
    deployment = api('/v13/deployments/' + deployment_id + '?teamId=' + TEAM, environment['VERCEL_TOKEN'])
    if type(deployment) is not dict or type(deployment.get('meta')) is not dict:
        raise ValueError('closed deployment metadata required')
    metadata = deployment['meta']
    host = deployment.get('url')
    source = metadata.get('githubCommitSha') if type(metadata) is dict else None
    if (deployment.get('id') != deployment_id or deployment.get('projectId') != PROJECT or deployment.get('ownerId') != TEAM
            or deployment.get('target') != 'production' or deployment.get('readyState') != 'READY'
            or str(metadata.get('githubCommitOrg', '')).casefold() != 'ynwaforever'
            or str(metadata.get('githubCommitRepo', '')).casefold() != 'buyeros'
            or not isinstance(source, str) or re.fullmatch(r'[0-9a-f]{40}', source) is None
            or not isinstance(host, str) or re.fullmatch(INPUT.COLLECTOR.IMMUTABLE_VERCEL_HOST, host) is None):
        raise ValueError('exact owned immutable canonical deployment required')
    names = deployment.get('env')
    return {'deployment_id': deployment_id, 'source_sha': source, 'origin': 'https://' + host,
            'runtime_source_setting_listed': 'BUYEROS_RUNTIME_SOURCE_SHA' in names if type(names) in (list, dict) else None}


def database_read(dsn):
    import psycopg
    # Keep the same target/query-option guard even when called independently.
    database_target_sha256(dsn)
    url = make_url(dsn)
    if url.username != 'buyeros_api' or not (url.host or '').endswith('.neon.tech'):
        raise ValueError('protected Neon runtime-role credential required')
    normalized = dsn.replace('postgresql+psycopg://', 'postgresql://', 1).replace('postgresql+asyncpg://', 'postgresql://', 1)
    with psycopg.connect(normalized, connect_timeout=5) as connection:
        connection.execute('SET TRANSACTION READ ONLY')
        connection.execute("SET LOCAL statement_timeout='3000ms'")
        role = connection.execute('SELECT current_user,session_user').fetchone()
        privileged = connection.execute("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE pg_has_role(current_user,oid,'MEMBER') AND (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication))").fetchone()[0]
        heads = [row[0] for row in connection.execute('SELECT version_num FROM public.alembic_version LIMIT 2')]
        if tuple(role) != ('buyeros_api', 'buyeros_api') or privileged or len(heads) != 1 or re.fullmatch(r'[A-Za-z0-9_]{1,128}', heads[0]) is None:
            raise ValueError('unprivileged runtime login and single head required')
        connection.rollback()
    return {'status': 'read', 'schema_head': heads[0], 'role': 'buyeros_api', 'read_only': True,
            'target_sha256': database_target_sha256(dsn), 'endpoint_sha256': database_endpoint_sha256(dsn)}


def expiration_claim(token, now):
    """An unverified hint only; never token validity or a revocation assertion."""
    try:
        pieces = token.split('.')
        if len(pieces) != 3 or len(token) > 16384 or re.fullmatch(r'[A-Za-z0-9_-]+', pieces[1]) is None:
            return 'unknown'
        claims = INPUT.private_json(base64.urlsafe_b64decode(pieces[1] + '=' * (-len(pieces[1]) % 4)).decode())
        value = claims.get('exp')
        if type(value) not in (int, float) or not math.isfinite(value):
            return 'unknown'
        return 'past' if value <= now else 'future'
    except Exception:
        return 'unknown'


def prepare(environment, *, api=management, db_read=database_read, get=INPUT.COLLECTOR.get_json, now=None):
    source = INPUT.require_context(environment)
    INPUT.recipient_key(environment['BUYEROS_REVIEW_RECIPIENT_PUBLIC_KEY'])
    seed = INPUT.prepare_review(environment)  # Existing strict schemas/hash binding; retain source values.
    target = canonical_target(environment, api)
    dsn = environment['BUYEROS_SCHEMA_CHECK_DATABASE_URL']
    probe = environment['BUYEROS_RELEASE_PROBE_TOKEN']
    if not isinstance(probe, str) or not 32 <= len(probe) <= 512 or not probe.isascii() or any(c.isspace() for c in probe):
        raise ValueError('bounded protected probe credential required')
    try:
        database = db_read(dsn)
    except Exception as error:
        category = 'metadata_privilege_denied' if getattr(error, 'sqlstate', None) == '42501' else 'connection_or_metadata_read_unavailable'
        database = {'status': 'unavailable', 'failure_category': category}
    binding = {'http_status': None, 'matched_legacy_deployment': False}
    try:
        status, body = get(target['origin'] + '/v1/internal/release-binding', probe)
        binding['http_status'] = status if type(status) is int and 100 <= status <= 599 else None
        keys = {'schema', 'source_sha', 'deployment_id', 'schema_head', 'db_target_sha256'}
        binding['matched_legacy_deployment'] = bool(type(status) is int and status == 200 and type(body) is dict and set(body) == keys
            and body['schema'] == 'buyeros.runtime-db-binding.v1' and body['source_sha'] == target['source_sha']
            and body['deployment_id'] == target['deployment_id'] and body['db_target_sha256'] == database_target_sha256(dsn)
            and database.get('status') == 'read' and body['schema_head'] == database['schema_head'])
    except Exception:
        pass
    tokens = {name: environment['BUYEROS_G0_' + name.upper() + '_TOKEN'] for name in INPUT.COLLECTOR.ACCOUNTS}
    api_seed = seed['api_seed']
    accounts = {'claim_metadata_is_unverified': True,
                'expiration_claim_state': {name: expiration_claim(value, time.time() if now is None else now) for name, value in tokens.items()},
                'reads': {'status': 'not_attempted_seed_target_differs'}}
    # A stale seed is never rebound to a new source or origin for these diagnostics.
    if api_seed['source_sha'] == target['source_sha'] and api_seed['origin'] == target['origin']:
        observed = INPUT.COLLECTOR.collect(api_seed, tokens, target['origin'], get=get)
        accounts['reads'] = {'status': 'collected', 'all_checks_passed': observed['all_checks_passed'],
                             'checks': [{key: check[key] for key in ('code', 'passed', 'observed_status')} for check in observed['checks']]}
    after = api(ALIAS_PATH, environment['VERCEL_TOKEN'])
    if after.get('alias') != 'buyer-os-nu.vercel.app' or after.get('deploymentId') != target['deployment_id'] or after.get('redirect') is not None:
        raise ValueError('canonical assignment changed during diagnostic')
    review = {'schema': 'buyeros.private-runtime-target-review.v1', 'source_sha': source,
              'canonical': target, 'protected_database': database, 'legacy_binding': binding, 'account_diagnostics': accounts,
              'seed_sources': seed['seed_sources'], 'promotable': False, 'acceptance': False, 'deployment_binding_verified': False}
    db_credential = getattr(make_url(dsn), 'pass' + 'word')
    forbidden = [dsn, probe, environment['VERCEL_TOKEN'], *tokens.values(), *([db_credential] if db_credential else [])]
    if any(secret in item for item in INPUT.strings(review) for secret in forbidden):
        raise ValueError('credential material in diagnostic metadata')
    return review


def main(argv=None):
    try:
        INPUT.require_context(os.environ)
        parser = INPUT.SafeParser(add_help=False)
        parser.add_argument('--output', type=Path, required=True)
        args = parser.parse_args(argv)
        review = prepare(os.environ)
        envelope = INPUT.encrypt_review(review, os.environ['BUYEROS_REVIEW_RECIPIENT_PUBLIC_KEY'])
        with args.output.open('xb') as handle:
            handle.write(INPUT.canonical(envelope))
        print(json.dumps({'status': 'encrypted_runtime_target_review', 'source_sha': review['source_sha']}))
        return 0
    except Exception:
        print(FAILURE, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
