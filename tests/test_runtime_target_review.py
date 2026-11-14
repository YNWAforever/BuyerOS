"""Offline privacy, destination and evidence-boundary tests; no real service access."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from test_release_input_review import environment, recipient, decrypt

SPEC = importlib.util.spec_from_file_location('runtime_target_review', Path(__file__).parents[1] / 'scripts/review-runtime-target.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


@pytest.fixture
def state(environment):
    env = copy.deepcopy(environment)
    env['VERCEL_TOKEN'] = 'unit-only-management-credential-value'
    env['BUYEROS_RELEASE_PROBE_TOKEN'] = 'unit-only-runtime-probe-credential-value'
    deployment = {'id': 'dpl_unitreview', 'projectId': module.PROJECT, 'ownerId': module.TEAM,
                  'target': 'production', 'readyState': 'READY', 'url': 'buyer-aaaaaaaaa-owned-project.vercel.app',
                  'meta': {'githubCommitSha': 'b' * 40, 'githubCommitOrg': 'YNWAforever', 'githubCommitRepo': 'BuyerOS'},
                  'env': ['BUYEROS_DATABASE_URL']}
    alias = {'alias': 'buyer-os-nu.vercel.app', 'deploymentId': deployment['id'], 'redirect': None}
    def management(path, token):
        assert token == env['VERCEL_TOKEN']
        return copy.deepcopy(alias if path == module.ALIAS_PATH else deployment)
    database = {'status': 'read', 'schema_head': '0065_sales_lifecycle', 'role': 'buyeros_api', 'read_only': True,
                'target_sha256': module.database_target_sha256(env['BUYEROS_SCHEMA_CHECK_DATABASE_URL']),
                'endpoint_sha256': module.database_endpoint_sha256(env['BUYEROS_SCHEMA_CHECK_DATABASE_URL'])}
    return env, deployment, alias, Mock(side_effect=management), Mock(return_value=database), Mock(return_value=(503, {'message': 'unavailable'}))


def prepare(state, **kwargs):
    env, _, _, api, database, get = state
    return module.prepare(env, api=api, db_read=database, get=get, now=1000, **kwargs)


def test_partial_diagnostics_are_encrypted_and_never_release_evidence(state, recipient):
    review = prepare(state)
    assert review['source_sha'] == 'a' * 40
    assert review['canonical']['source_sha'] == 'b' * 40
    assert review['legacy_binding'] == {'http_status': 503, 'matched_legacy_deployment': False}
    assert review['account_diagnostics']['reads']['status'] == 'not_attempted_seed_target_differs'
    assert all(review[key] is False for key in ('promotable', 'acceptance', 'deployment_binding_verified'))
    envelope = module.INPUT.encrypt_review(review, recipient[1])
    assert decrypt(envelope, recipient[0]) == review
    serialized = module.INPUT.canonical(envelope).decode()
    assert state[0]['VERCEL_TOKEN'] not in serialized
    assert state[0]['BUYEROS_RELEASE_PROBE_TOKEN'] not in serialized
    assert '0065_sales_lifecycle' not in serialized
    state[5].assert_called_once_with('https://' + state[1]['url'] + '/v1/internal/release-binding', state[0]['BUYEROS_RELEASE_PROBE_TOKEN'])


@pytest.mark.parametrize('key,value', [('GITHUB_EVENT_NAME', 'push'), ('GITHUB_REF', 'refs/heads/other'),
    ('GITHUB_REPOSITORY', 'other/BuyerOS'), ('GITHUB_ACTOR_ID', '42'), ('GITHUB_RUN_ATTEMPT', '2'), ('GITHUB_SHA', 'bad')])
def test_context_rejected_before_any_network_or_database(state, key, value):
    state[0][key] = value
    with pytest.raises(ValueError): prepare(state)
    for call in state[3:]: call.assert_not_called()


@pytest.mark.parametrize('field,value', [('projectId', 'prj_other'), ('ownerId', 'team_other'), ('target', 'preview'),
    ('readyState', 'BUILDING'), ('url', 'attacker.example'), ('url', 'buyer-os-nu.vercel.app'), ('id', 'dpl_other')])
def test_wrong_target_never_receives_probe_or_database_access(state, field, value):
    state[1][field] = value
    with pytest.raises(ValueError): prepare(state)
    state[4].assert_not_called(); state[5].assert_not_called()


@pytest.mark.parametrize('field,value', [('githubCommitOrg', 'attacker'), ('githubCommitRepo', 'other'), ('githubCommitSha', 'not-a-sha')])
def test_wrong_repository_or_source_never_receives_probe(state, field, value):
    state[1]['meta'][field] = value
    with pytest.raises(ValueError): prepare(state)
    state[5].assert_not_called()


def test_alias_race_prevents_artifact_preparation(state):
    original = state[3].side_effect
    calls = 0
    def race(path, token):
        nonlocal calls
        calls += 1
        result = original(path, token)
        if calls == 3: result['deploymentId'] = 'dpl_changed'
        return result
    state[3].side_effect = race
    with pytest.raises(ValueError, match='assignment changed'): prepare(state)


def test_matching_legacy_binding_still_cannot_close_current_release(state):
    state[5].return_value = (200, {'schema': 'buyeros.runtime-db-binding.v1', 'source_sha': 'b' * 40,
        'deployment_id': 'dpl_unitreview', 'schema_head': '0065_sales_lifecycle',
        'db_target_sha256': state[4].return_value['target_sha256']})
    review = prepare(state)
    assert review['legacy_binding']['matched_legacy_deployment'] is True
    assert review['source_sha'] != review['canonical']['source_sha']
    assert review['deployment_binding_verified'] is review['acceptance'] is review['promotable'] is False


@pytest.mark.parametrize('field,value', [('source_sha', 'c' * 40), ('deployment_id', 'dpl_other'),
    ('schema_head', 'unknown_head'), ('db_target_sha256', 'f' * 64), ('schema', 'other')])
def test_wrong_binding_is_diagnostic_failure_not_attestation(state, field, value):
    body = {'schema': 'buyeros.runtime-db-binding.v1', 'source_sha': 'b' * 40, 'deployment_id': 'dpl_unitreview',
            'schema_head': '0065_sales_lifecycle', 'db_target_sha256': state[4].return_value['target_sha256']}
    body[field] = value; state[5].return_value = (200, body)
    assert prepare(state)['legacy_binding']['matched_legacy_deployment'] is False


def test_exceptions_and_response_bodies_never_cross_review_boundary(state):
    marker = state[0]['VERCEL_TOKEN']
    state[4].side_effect = RuntimeError(marker)
    state[5].return_value = (500, {'message': marker, 'arbitrary': state[0]['BUYEROS_SCHEMA_CHECK_DATABASE_URL']})
    review = prepare(state)
    assert review['protected_database']['status'] == 'unavailable'
    assert marker not in json.dumps(review)
    assert 'arbitrary' not in json.dumps(review)


def test_expired_claim_is_only_unverified_metadata(state):
    packet = json.loads(state[0]['BUYEROS_G0_TARGET_JSON'])
    for name in module.INPUT.COLLECTOR.ACCOUNTS:
        encoded = base64.urlsafe_b64encode(json.dumps({'exp': 99}).encode()).decode().rstrip('=')
        value = 'unit.' + encoded + '.' + name
        state[0]['BUYEROS_G0_' + name.upper() + '_TOKEN'] = value
        packet['token_sha256'][name] = hashlib.sha256(value.encode()).hexdigest()
    state[0]['BUYEROS_G0_TARGET_JSON'] = json.dumps(packet)
    diagnostics = prepare(state)['account_diagnostics']
    assert set(diagnostics['expiration_claim_state'].values()) == {'past'}
    assert diagnostics['claim_metadata_is_unverified'] is True
    assert 'revoked' in diagnostics['expiration_claim_state']  # Label only, never revocation proof.
    assert 'authenticated' not in diagnostics


@pytest.mark.parametrize('value', [None, True, '99', float('inf'), {}, []])
def test_invalid_expiry_claim_is_unknown(value):
    encoded = base64.urlsafe_b64encode(json.dumps({'exp': value}).encode()).decode().rstrip('=')
    assert module.expiration_claim('unit.' + encoded + '.signature', 1000) == 'unknown'


def test_account_reads_only_use_exact_original_source_and_origin(state):
    packet = json.loads(state[0]['BUYEROS_G0_TARGET_JSON'])
    packet['origin'] = 'https://' + state[1]['url']
    state[0]['BUYEROS_G0_TARGET_JSON'] = json.dumps(packet)
    state[5].return_value = (401, {'message': 'unit unregistered'})
    review = prepare(state)
    assert review['account_diagnostics']['reads']['status'] == 'collected'
    assert len(review['account_diagnostics']['reads']['checks']) == 7
    assert state[5].call_count == 8  # One binding + the existing seven bounded reads.
    assert all(not check['passed'] for check in review['account_diagnostics']['reads']['checks'])
    assert review['acceptance'] is False


def test_recipient_rejected_before_inspecting_seeds_or_network(state):
    state[0]['BUYEROS_REVIEW_RECIPIENT_PUBLIC_KEY'] = 'invalid public key'
    with pytest.raises(ValueError): prepare(state)
    for call in state[3:]: call.assert_not_called()


def test_cli_failure_has_fixed_private_safe_message(state, monkeypatch, capsys, tmp_path):
    for key, value in state[0].items(): monkeypatch.setenv(key, value)
    marker = state[0]['BUYEROS_RELEASE_PROBE_TOKEN']
    monkeypatch.setattr(module, 'prepare', Mock(side_effect=ValueError(marker)))
    assert module.main(['--output', str(tmp_path / 'output.json')]) == 1
    captured = capsys.readouterr()
    assert captured.out == '' and captured.err.strip() == module.FAILURE
    assert marker not in captured.err
    assert not (tmp_path / 'output.json').exists()


@pytest.mark.parametrize('query', ['hostaddr=198.51.100.8', 'options=-csearch_path=other'])
def test_standalone_database_reader_rejects_target_overrides_before_connect(monkeypatch, query):
    import psycopg
    connect = Mock()
    monkeypatch.setattr(psycopg, 'connect', connect)
    with pytest.raises(ValueError):
        module.database_read('postgresql://buyeros_api:unit-only-db-credential@ep-unit.aws.neon.tech/unit_db?' + query)
    connect.assert_not_called()


def test_database_reader_establishes_readonly_before_select_and_rolls_back(monkeypatch):
    import psycopg
    class Result:
        def __init__(self, rows): self.rows = rows
        def fetchone(self): return self.rows[0]
        def __iter__(self): return iter(self.rows)
    class Connection:
        read_only = False
        rolled_back = False
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, statement):
            if statement == 'SET TRANSACTION READ ONLY':
                self.read_only = True
                return None
            assert self.read_only, 'metadata must never be queried in a writable transaction'
            if statement.startswith('SET LOCAL statement_timeout='): return None
            assert statement.startswith('SELECT '), 'mutation is forbidden'
            if 'current_user,session_user' in statement: return Result([('buyeros_api', 'buyeros_api')])
            if 'EXISTS' in statement: return Result([(False,)])
            return Result([('0065_sales_lifecycle',)])
        def rollback(self): self.rolled_back = True
    connection = Connection()
    monkeypatch.setattr(psycopg, 'connect', Mock(return_value=connection))
    report = module.database_read('postgresql://buyeros_api:unit-only-db-credential@ep-unit.aws.neon.tech/unit_db?sslmode=require')
    assert connection.read_only and connection.rolled_back
    assert report['read_only'] is True and report['role'] == 'buyeros_api'


@pytest.mark.parametrize('path', ['/v1/other', '/v13/deployments/dpl_unit?teamId=other', 'https://attacker.example'])
def test_management_rejects_routes_before_creating_transport(monkeypatch, path):
    transport = Mock()
    monkeypatch.setattr(module.urllib.request, 'build_opener', transport)
    with pytest.raises(ValueError): module.management(path, 'unit-only-management-credential-value')
    transport.assert_not_called()


def test_workflow_has_owner_main_context_and_ciphertext_only_upload():
    filename = Path(__file__).parents[1] / '.github/workflows/buyeros-runtime-target-review.yml'
    workflow = yaml.safe_load(filename.read_text())
    assert workflow['permissions'] == {'contents': 'read'}
    job = workflow['jobs']['review']
    assert job['environment'] == 'buyeros-runtime-readonly'
    assert "github.actor_id == '201698560'" in job['if'] and 'github.run_attempt == 1' in job['if']
    assert "github.ref == 'refs/heads/main'" in job['if']
    checkout = job['steps'][0]
    assert checkout['with']['ref'] == '${{ github.sha }}' and checkout['with']['persist-credentials'] is False
    uploads = [step for step in job['steps'] if 'uses' in step and step['uses'].startswith('actions/upload-artifact@')]
    assert len(uploads) == 1 and uploads[0]['with']['retention-days'] == 1
    assert uploads[0]['with']['path'].endswith('.encrypted.json')
    assert all('id-token' not in permissions for permissions in [workflow['permissions']])
