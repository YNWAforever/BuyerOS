"""Offline tests use controlled dummy seeds/keys only; no credential or service access."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SPEC = importlib.util.spec_from_file_location('release_input_review', Path(__file__).parents[1] / 'scripts' / 'prepare-release-input-review.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


@pytest.fixture(scope='module')
def recipient():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode('ascii')
    return private, public


@pytest.fixture
def environment(recipient):
    tokens = {name: 'unit-only-' + name + '-opaque-bearer-value' for name in ('owned', 'foreign', 'empty', 'revoked')}
    api = {
        'schema': 'buyeros.workspace-api-target.v1', 'source_sha': 'b' * 40,
        'origin': 'https://buyer-review-fixture.vercel.app', 'api_prefix': '/v1',
        'authorization_reference_sha256': 'd' * 64,
        'accounts': {
            'owned': {'workspace_id': 'a1000000-0000-4000-8000-000000000001', 'project_id': 'a2000000-0000-4000-8000-000000000001', 'roles': ['workspace_admin']},
            'foreign': {'workspace_id': 'a3000000-0000-4000-8000-000000000001', 'project_id': 'a4000000-0000-4000-8000-000000000001', 'roles': ['viewer']},
        },
        'token_sha256': {name: hashlib.sha256(token.encode()).hexdigest() for name, token in tokens.items()},
    }
    dsn = 'postgresql+psycopg://unit_operator:unit-private-passphrase-for-tests@ep-unit-review.aws.neon.tech/unit_review_db?sslmode=require'
    target = {'database': 'unit_review_db', 'endpoint_sha256': module.database_endpoint_sha256(dsn), 'metadata_receipt_sha256': 'e' * 64}
    schema = {
        'contract_version': 'buyeros.schema-contract.v1', 'source_sha': 'c' * 40,
        'required_revisions': ['0065_sales_lifecycle'], 'compatible_heads': ['0065_sales_lifecycle'],
        'required_relations': {'public.memberships': ['id', 'workspace_id']},
        'required_functions': ['public.buyeros_resolve_identity(text,text)'],
        'required_privileges': [{'relation': 'public.memberships', 'columns': ['id'], 'privilege': 'SELECT'}],
        'required_rls': ['public.memberships'], 'runtime_role_policy': {'role': 'buyeros_api', 'superuser': False, 'bypass_rls': False},
        'target': target, 'target_receipt': copy.deepcopy(target), 'evidence_mode': 'candidate_runtime',
    }
    return {
        'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_REF': 'refs/heads/main',
        'GITHUB_REPOSITORY': 'YNWAforever/BuyerOS', 'GITHUB_ACTOR_ID': '201698560',
        'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_SHA': 'a' * 40,
        'BUYEROS_REVIEW_RECIPIENT_PUBLIC_KEY': recipient[1],
        'BUYEROS_G0_TARGET_JSON': json.dumps(api), 'BUYEROS_SCHEMA_CONTRACT_JSON': json.dumps(schema),
        'BUYEROS_SCHEMA_CHECK_DATABASE_URL': dsn,
        **{'BUYEROS_G0_' + name.upper() + '_TOKEN': token for name, token in tokens.items()},
    }


def decrypt(envelope, private):
    header = {name: envelope[name] for name in ('schema', 'algorithm', 'recipient_key_sha256')}
    key = private.decrypt(base64.b64decode(envelope['wrapped_key']), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=b'buyeros.release-input-review.v1'))
    plain = AESGCM(key).decrypt(base64.b64decode(envelope['nonce']), base64.b64decode(envelope['ciphertext']), module.canonical(header))
    return json.loads(plain)


def test_decrypted_review_has_exact_allowlist_and_retains_stale_sources(environment, recipient, monkeypatch):
    monkeypatch.setattr(module.COLLECTOR, 'protected_get_json', Mock(side_effect=AssertionError('network forbidden')))
    original = copy.deepcopy(environment)
    review = module.prepare_review(environment)
    envelope = module.encrypt_review(review, recipient[1])
    assert set(envelope) == {'schema', 'algorithm', 'recipient_key_sha256', 'wrapped_key', 'nonce', 'ciphertext'}
    assert len(base64.b64decode(envelope['nonce'])) == 12
    payload = decrypt(envelope, recipient[0])
    assert set(payload) == {'schema', 'kind', 'source_sha', 'api_seed', 'schema_seed', 'seed_sources', 'database_target_fingerprints', 'promotable', 'acceptance', 'deployment_binding_verified'}
    assert payload['kind'] == 'private_release_input_review'
    assert payload['api_seed'] == json.loads(environment['BUYEROS_G0_TARGET_JSON'])
    assert payload['schema_seed'] == module.SchemaContract.model_validate(json.loads(environment['BUYEROS_SCHEMA_CONTRACT_JSON'])).model_dump(mode='json', by_alias=True)
    assert payload['source_sha'] == 'a' * 40
    assert payload['api_seed']['source_sha'] == 'b' * 40
    assert payload['schema_seed']['source_sha'] == 'c' * 40
    assert payload['seed_sources'] == {'api_matches_current_source': False, 'schema_matches_current_source': False}
    assert payload['promotable'] is payload['acceptance'] is payload['deployment_binding_verified'] is False
    assert environment == original
    assert module.COLLECTOR.protected_get_json.call_count == 0


def test_matching_sources_still_cannot_assert_acceptance(environment):
    for key in ('BUYEROS_G0_TARGET_JSON', 'BUYEROS_SCHEMA_CONTRACT_JSON'):
        seed = json.loads(environment[key])
        seed['source_sha'] = environment['GITHUB_SHA']
        environment[key] = json.dumps(seed)
    review = module.prepare_review(environment)
    assert all(review['seed_sources'].values())
    assert not any(review[key] for key in ('promotable', 'acceptance', 'deployment_binding_verified'))


def test_tokens_dsn_and_unrelated_secrets_are_not_exported(environment, recipient):
    environment['UNRELATED_PRIVATE_SECRET'] = 'unit-only-unrelated-sensitive-value'
    environment['BUYEROS_NEON_COOKIE_SECRET'] = 'unit-only-cookie-sensitive-value'
    payload = decrypt(module.encrypt_review(module.prepare_review(environment), recipient[1]), recipient[0])
    plain = module.canonical(payload).decode()
    for key in ('BUYEROS_G0_OWNED_TOKEN', 'BUYEROS_G0_FOREIGN_TOKEN', 'BUYEROS_G0_EMPTY_TOKEN', 'BUYEROS_G0_REVOKED_TOKEN', 'BUYEROS_SCHEMA_CHECK_DATABASE_URL', 'UNRELATED_PRIVATE_SECRET', 'BUYEROS_NEON_COOKIE_SECRET'):
        assert environment[key] not in plain
    assert 'unit-private-passphrase-for-tests' not in plain
    assert set(payload['database_target_fingerprints']) == {'target_sha256', 'endpoint_sha256', 'matches_schema_seed_target'}
    assert payload['database_target_fingerprints'] == {
        'target_sha256': module.database_target_sha256(environment['BUYEROS_SCHEMA_CHECK_DATABASE_URL']),
        'endpoint_sha256': module.database_endpoint_sha256(environment['BUYEROS_SCHEMA_CHECK_DATABASE_URL']),
        'matches_schema_seed_target': True,
    }


@pytest.mark.parametrize('key', ['BUYEROS_G0_TARGET_JSON', 'BUYEROS_SCHEMA_CONTRACT_JSON'])
def test_extra_seed_fields_are_rejected(environment, key):
    seed = json.loads(environment[key])
    seed['unreviewed_extra'] = 'must not export'
    environment[key] = json.dumps(seed)
    with pytest.raises(ValueError):
        module.prepare_review(environment)


@pytest.mark.parametrize('key', ['BUYEROS_G0_TARGET_JSON', 'BUYEROS_SCHEMA_CONTRACT_JSON'])
def test_duplicate_json_keys_are_rejected(environment, key):
    environment[key] = environment[key][:-1] + ',"source_sha":"' + 'f' * 40 + '"}'
    with pytest.raises(ValueError):
        module.prepare_review(environment)


@pytest.mark.parametrize('mutation', ['wrong-token', 'duplicate-token', 'wrong-hash', 'foreign-tenant', 'extra-account-field'])
def test_invalid_account_or_credential_binding_is_rejected(environment, mutation):
    seed = json.loads(environment['BUYEROS_G0_TARGET_JSON'])
    if mutation == 'wrong-token':
        environment['BUYEROS_G0_OWNED_TOKEN'] = 'unit-only-wrong-unbound-token'
    elif mutation == 'duplicate-token':
        environment['BUYEROS_G0_FOREIGN_TOKEN'] = environment['BUYEROS_G0_OWNED_TOKEN']
        seed['token_sha256']['foreign'] = seed['token_sha256']['owned']
    elif mutation == 'wrong-hash':
        seed['token_sha256']['empty'] = 'f' * 64
    elif mutation == 'foreign-tenant':
        seed['accounts']['foreign']['workspace_id'] = seed['accounts']['owned']['workspace_id']
    else:
        seed['accounts']['owned']['unreviewed_extra'] = True
    environment['BUYEROS_G0_TARGET_JSON'] = json.dumps(seed)
    with pytest.raises(ValueError):
        module.prepare_review(environment)


@pytest.mark.parametrize('secret_kind', ['token', 'dsn-fragment'])
def test_known_credentials_hidden_in_valid_schema_strings_are_rejected(environment, secret_kind):
    seed = json.loads(environment['BUYEROS_SCHEMA_CONTRACT_JSON'])
    seed['runtime_role_policy']['role'] = environment['BUYEROS_G0_OWNED_TOKEN'] if secret_kind == 'token' else 'unit-private-passphrase-for-tests'
    environment['BUYEROS_SCHEMA_CONTRACT_JSON'] = json.dumps(seed)
    with pytest.raises(ValueError):
        module.prepare_review(environment)


def test_target_mismatch_is_reported_without_claiming_binding(environment):
    seed = json.loads(environment['BUYEROS_SCHEMA_CONTRACT_JSON'])
    seed['target']['endpoint_sha256'] = 'f' * 64
    environment['BUYEROS_SCHEMA_CONTRACT_JSON'] = json.dumps(seed)
    review = module.prepare_review(environment)
    assert review['database_target_fingerprints']['matches_schema_seed_target'] is False
    assert review['schema_seed']['target'] != review['schema_seed']['target_receipt']
    assert review['deployment_binding_verified'] is False


@pytest.mark.parametrize('case', ['broken', 'ec', 'small-rsa', 'oversized-rsa', 'private', 'two-keys'])
def test_invalid_recipients_are_rejected(recipient, case):
    if case == 'broken':
        pem = 'not a PEM'
    elif case == 'ec':
        pem = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    elif case == 'small-rsa':
        pem = rsa.generate_private_key(public_exponent=65537, key_size=1024).public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    elif case == 'oversized-rsa':
        # A syntactically loadable public modulus tests the upper bound without
        # spending time generating an unnecessary large private key.
        oversized = rsa.RSAPublicNumbers(65537, (1 << 8191) + 1).public_key()
        pem = oversized.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    elif case == 'private':
        pem = recipient[0].private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    else:
        pem = recipient[1] + recipient[1]
    with pytest.raises(ValueError):
        module.recipient_key(pem)


def test_4096_bit_rsa_recipient_is_accepted():
    private = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    public, fingerprint = module.recipient_key(pem)
    assert public.key_size == 4096 and len(fingerprint) == 64


def test_encryption_is_random_and_integrity_bound(environment, recipient):
    review = module.prepare_review(environment)
    first = module.encrypt_review(review, recipient[1])
    second = module.encrypt_review(review, recipient[1])
    assert first['nonce'] != second['nonce'] and first['wrapped_key'] != second['wrapped_key']
    first['recipient_key_sha256'] = 'f' * 64
    with pytest.raises(InvalidTag):
        decrypt(first, recipient[0])


@pytest.mark.parametrize(('key', 'value'), [
    ('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_REF', 'refs/heads/feature'),
    ('GITHUB_REPOSITORY', 'other/repository'), ('GITHUB_ACTOR_ID', '123'),
    ('GITHUB_RUN_ATTEMPT', '2'), ('GITHUB_SHA', 'invalid'),
])
def test_main_refuses_wrong_context_with_fixed_diagnostic(environment, monkeypatch, tmp_path, capsys, key, value):
    environment[key] = value
    monkeypatch.setattr(module.os, 'environ', environment)
    output = tmp_path / 'review.encrypted.json'
    assert module.main(['--output', str(output)]) == 1
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == module.DIAGNOSTIC + '\n'
    assert not output.exists()


def test_main_writes_only_encrypted_artifact_and_safe_stdout(environment, recipient, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(module.os, 'environ', environment)
    output = tmp_path / 'review.encrypted.json'
    assert module.main(['--output', str(output)]) == 0
    captured = capsys.readouterr()
    status = json.loads(captured.out)
    assert set(status) == {'status', 'source_sha', 'recipient_key_sha256'}
    assert status['status'] == 'encrypted_private_release_input_review' and status['source_sha'] == environment['GITHUB_SHA']
    assert captured.err == ''
    artifact = json.loads(output.read_text())
    assert decrypt(artifact, recipient[0])['api_seed']['source_sha'] == 'b' * 40
    assert list(tmp_path.iterdir()) == [output]


def test_main_sanitizes_private_failure_and_does_not_overwrite(environment, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(module.os, 'environ', environment)
    output = tmp_path / 'review.encrypted.json'
    output.write_bytes(b'controlled existing encrypted artifact')
    assert module.main(['--output', str(output)]) == 1
    assert output.read_bytes() == b'controlled existing encrypted artifact'
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == module.DIAGNOSTIC + '\n'
    bad_seed = json.loads(environment['BUYEROS_SCHEMA_CONTRACT_JSON'])
    bad_seed['private_validation_sentinel'] = 'unit-only-do-not-render-validation-input'
    environment['BUYEROS_SCHEMA_CONTRACT_JSON'] = json.dumps(bad_seed)
    refused = tmp_path / 'refused.json'
    assert module.main(['--output', str(refused)]) == 1
    assert not refused.exists()
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == module.DIAGNOSTIC + '\n'
    monkeypatch.setattr(module, 'prepare_review', Mock(side_effect=ValueError('unit-only-private-exception-sentinel')))
    assert module.main(['--output', str(tmp_path / 'different.json')]) == 1
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err == module.DIAGNOSTIC + '\n'


def test_workflow_is_fresh_owner_main_readonly_and_uploads_only_ciphertext():
    path = Path(__file__).parents[1] / '.github' / 'workflows' / 'buyeros-release-input-review.yml'
    workflow = yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    assert set(workflow['on']) == {'workflow_dispatch'}
    assert set(workflow['on']['workflow_dispatch']['inputs']) == {'recipient_public_key'}
    assert workflow['permissions'] == {'contents': 'read'}
    job = workflow['jobs']['review']
    assert job['environment'] == 'buyeros-runtime-readonly'
    for guard in ("github.event_name == 'workflow_dispatch'", "github.ref == 'refs/heads/main'", "github.repository == 'YNWAforever/BuyerOS'", "github.actor_id == '201698560'", 'github.run_attempt == 1'):
        assert guard in job['if']
    checkout = job['steps'][0]
    assert checkout['with'] == {'ref': '${{ github.sha }}', 'persist-credentials': 'false'}
    prepare = next(step for step in job['steps'] if step.get('name') == 'Encrypt validated seeds for owner review only')
    assert set(prepare['env']) == {'BUYEROS_REVIEW_RECIPIENT_PUBLIC_KEY', 'BUYEROS_G0_TARGET_JSON', 'BUYEROS_SCHEMA_CONTRACT_JSON', 'BUYEROS_SCHEMA_CHECK_DATABASE_URL', 'BUYEROS_G0_OWNED_TOKEN', 'BUYEROS_G0_FOREIGN_TOKEN', 'BUYEROS_G0_EMPTY_TOKEN', 'BUYEROS_G0_REVOKED_TOKEN'}
    assert prepare['run'] == 'services/api/.venv/bin/python scripts/prepare-release-input-review.py --output "$RUNNER_TEMP/buyeros-release-input-review.encrypted.json"'
    uploads = [step for step in job['steps'] if step.get('uses', '').startswith('actions/upload-artifact@')]
    assert len(uploads) == 1 and 'if' not in uploads[0]
    assert uploads[0]['with']['path'] == '${{ runner.temp }}/buyeros-release-input-review.encrypted.json'
    assert uploads[0]['with']['retention-days'] == '1'
    assert 'GH_TOKEN' not in prepare['env'] and 'GITHUB_TOKEN' not in prepare['env']
