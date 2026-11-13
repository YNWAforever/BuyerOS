"""Encrypt validated private seed metadata for owner review; never advance release.

No network, database connection, token decoding, secret mutation, source rebinding,
approval or acceptance generation occurs. Recipient private keys stay off Actions.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services' / 'api'))
from buyeros_api.services.release_binding import database_endpoint_sha256, database_target_fields, database_target_sha256
from buyeros_api.services.schema_readiness import SchemaContract

COLLECTOR_SPEC = importlib.util.spec_from_file_location('release_review_api_validator', ROOT / 'scripts' / 'collect-workspace-observations.py')
COLLECTOR = importlib.util.module_from_spec(COLLECTOR_SPEC)
COLLECTOR_SPEC.loader.exec_module(COLLECTOR)

MAX_JSON_BYTES = 1024 * 1024
ENVELOPE_SCHEMA = 'buyeros.private-release-input-review-envelope.v1'
ALGORITHM = 'RSA-OAEP-SHA256+A256GCM'
OAEP_LABEL = b'buyeros.release-input-review.v1'
PUBLIC_PEM = re.compile(r'\s*-----BEGIN (PUBLIC KEY|RSA PUBLIC KEY)-----\r?\n[A-Za-z0-9+/=\r\n]+-----END \1-----\s*')
DIAGNOSTIC = 'BLOCKED: private release-input review could not be prepared'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def reject_constant(value):
    raise ValueError('nonfinite JSON is forbidden')


def private_json(raw):
    if not isinstance(raw, str) or not raw or len(raw.encode('utf-8')) > MAX_JSON_BYTES:
        raise ValueError('bounded seed JSON required')
    return json.loads(raw, object_pairs_hook=COLLECTOR.unique_keys, parse_constant=reject_constant)


def require_context(environment):
    if (environment.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or environment.get('GITHUB_REF') != 'refs/heads/main'
            or environment.get('GITHUB_REPOSITORY') != 'YNWAforever/BuyerOS'
            or environment.get('GITHUB_ACTOR_ID') != '201698560'
            or environment.get('GITHUB_RUN_ATTEMPT') != '1'):
        raise ValueError('fresh owner main review required')
    source = environment.get('GITHUB_SHA', '')
    if not re.fullmatch(r'[0-9a-f]{40}', source):
        raise ValueError('review source SHA required')
    return source


def recipient_key(pem):
    if not isinstance(pem, str) or len(pem) > 8192 or not PUBLIC_PEM.fullmatch(pem):
        raise ValueError('single public PEM required')
    public = serialization.load_pem_public_key(pem.encode('ascii'))
    if not isinstance(public, rsa.RSAPublicKey) or not 2048 <= public.key_size <= 4096:
        raise ValueError('bounded RSA public recipient required')
    der = public.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return public, hashlib.sha256(der).hexdigest()


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def prepare_review(environment):
    source = require_context(environment)
    api = private_json(environment['BUYEROS_G0_TARGET_JSON'])
    schema = SchemaContract.model_validate(private_json(environment['BUYEROS_SCHEMA_CONTRACT_JSON']))
    tokens = {name: environment['BUYEROS_G0_' + name.upper() + '_TOKEN'] for name in COLLECTOR.ACCOUNTS}
    COLLECTOR.validate(api, tokens, api.get('origin') if isinstance(api, dict) else None)
    dsn = environment['BUYEROS_SCHEMA_CHECK_DATABASE_URL']
    fields = database_target_fields(dsn)
    endpoint = database_endpoint_sha256(dsn)
    review = {
        'schema': 'buyeros.private-release-input-review.v1',
        'kind': 'private_release_input_review',
        'source_sha': source,
        'api_seed': api,
        'schema_seed': schema.model_dump(mode='json', by_alias=True),
        'seed_sources': {
            'api_matches_current_source': api['source_sha'] == source,
            'schema_matches_current_source': schema.source_sha == source,
        },
        'database_target_fingerprints': {
            'target_sha256': database_target_sha256(dsn),
            'endpoint_sha256': endpoint,
            'matches_schema_seed_target': schema.target.database == fields['database'] and schema.target.endpoint_sha256 == endpoint,
        },
        'promotable': False,
        'acceptance': False,
        'deployment_binding_verified': False,
    }
    if len(canonical(review)) > MAX_JSON_BYTES:
        raise ValueError('bounded review required')
    # Closed schemas prevent arbitrary fields; also reject known credential values
    # accidentally placed inside an otherwise schema-valid metadata string.
    url = make_url(dsn)
    credential = getattr(url, 'pass' + 'word')
    forbidden = [*tokens.values(), dsn, *([credential] if credential else [])]
    if any(secret in item for item in strings(review) for secret in forbidden):
        raise ValueError('credential value in metadata')
    return review


def encrypt_review(review, public_pem):
    public, fingerprint = recipient_key(public_pem)
    header = {'schema': ENVELOPE_SCHEMA, 'algorithm': ALGORITHM, 'recipient_key_sha256': fingerprint}
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, canonical(review), canonical(header))
    wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=OAEP_LABEL))
    return {**header, 'wrapped_key': base64.b64encode(wrapped).decode('ascii'),
            'nonce': base64.b64encode(nonce).decode('ascii'), 'ciphertext': base64.b64encode(ciphertext).decode('ascii')}


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid review command')


def main(argv=None):
    try:
        require_context(os.environ)
        parser = SafeParser(add_help=False)
        parser.add_argument('--output', type=Path, required=True)
        args = parser.parse_args(argv)
        # Validate the recipient before inspecting seed material.
        public_pem = os.environ['BUYEROS_REVIEW_RECIPIENT_PUBLIC_KEY']
        recipient_key(public_pem)
        review = prepare_review(os.environ)
        envelope = encrypt_review(review, public_pem)
        with args.output.open('xb') as handle:
            handle.write(canonical(envelope))
        print(json.dumps({'status': 'encrypted_private_release_input_review',
                          'source_sha': review['source_sha'], 'recipient_key_sha256': envelope['recipient_key_sha256']}))
        return 0
    except Exception:
        # Never render exception messages, seed contents, credentials or paths.
        print(DIAGNOSTIC, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
