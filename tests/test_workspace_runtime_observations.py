"""Owned transport controls, never live workspace acceptance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
from email.message import Message
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
TOKENS = {key: 'owned-fixture-token-' + key for key in ('owned', 'foreign', 'empty', 'revoked')}
W1, W2 = '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002'
P1, P2 = '00000000-0000-4000-8000-000000000003', '00000000-0000-4000-8000-000000000004'


def load():
    path = ROOT / 'scripts/collect-workspace-observations.py'
    assert path.exists(), 'read-only workspace runtime observation collector is absent'
    spec = importlib.util.spec_from_file_location('workspace_observations', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def packet():
    return {'schema': 'buyeros.workspace-api-target.v1', 'source_sha': 'a'*40,
            'origin': 'https://owned-candidate.example.test', 'api_prefix': '/api/v1',
            'authorization_reference_sha256': 'b'*64,
            'accounts': {key: {'workspace_id': workspace, 'project_id': project, 'roles': ['viewer']}
                         for key, workspace, project in [('owned', W1, P1), ('foreign', W2, P2)]},
            'token_sha256': {key: hashlib.sha256(value.encode()).hexdigest() for key, value in TOKENS.items()}}


def envelope(data):
    return {'data': data, 'request_id': W1, 'data_mode': 'live'}


class WorkspaceRuntimeObservationsTests(unittest.TestCase):
    def setUp(self):
        self.packet = packet()
        self.calls = []
        self.responses = [
            (200, envelope({'items': [{'id': W1, 'roles': ['viewer']}], 'total': 1, 'offset': 0, 'limit': 100})),
            (200, envelope({'id': P1, 'workspace_id': W1, 'data_mode': 'live'})),
            (200, envelope({'items': [], 'total': 0, 'offset': 0, 'limit': 100})),
            (404, {'error': {'code': 'NOT_FOUND'}, 'request_id': W1}),
            (404, {'error': {'code': 'NOT_FOUND'}, 'request_id': W1}),
            (404, {'error': {'code': 'NOT_FOUND'}, 'request_id': W1}),
            (200, envelope({'id': P2, 'workspace_id': W2, 'data_mode': 'live'})),
        ]

    def get(self, url, token):
        self.calls.append((url, token))
        response = self.responses[len(self.calls)-1]
        if isinstance(response, Exception):
            raise response
        return response

    def collect(self, tokens=None, allowed=None):
        return load().collect(self.packet, TOKENS if tokens is None else tokens,
                              allowed or self.packet['origin'], get=self.get)

    def assert_blocked_before_http(self, tokens=None, allowed=None):
        with self.assertRaises(ValueError):
            self.collect(tokens, allowed)
        self.assertEqual(self.calls, [])

    def test_paired_owned_controls_observe_seven_gets_without_acceptance_claim(self):
        result = self.collect()
        self.assertTrue(result['all_checks_passed'])
        self.assertFalse(result['promotable'])
        self.assertEqual(len(self.calls), 7)
        self.assertNotIn('receipts', result)
        self.assertIn('browser_canary_not_collected', result['acceptance_blockers'])
        self.assertIn('exact_deployment_db_binding_unproven', result['acceptance_blockers'])

    def test_http_200_without_known_workspace_is_not_success(self):
        self.responses[0] = (200, envelope({'items': [], 'total': 0, 'offset': 0, 'limit': 100}))
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_unexpected_role_is_not_success(self):
        self.responses[0][1]['data']['items'][0]['roles'] = ['workspace_admin']
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_duplicate_roles_are_not_success(self):
        self.responses[0][1]['data']['items'][0]['roles'] = ['viewer', 'viewer']
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_wrong_project_is_not_success(self):
        self.responses[1][1]['data']['id'] = P2
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_empty_response_does_not_hide_an_error(self):
        self.responses[2] = (503, envelope({'items': [], 'total': 0}))
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_fixture_data_mode_is_rejected(self):
        self.responses[1][1]['data_mode'] = 'fixture'
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_expired_token_is_not_revocation_evidence(self):
        self.responses[4] = (401, {'error': {'code': 'UNAUTHENTICATED'}})
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_foreign_denial_requires_exact_not_found_contract(self):
        self.responses[5] = (404, {'error': {'code': 'UNKNOWN_FAILURE'}})
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_foreign_denial_has_matching_foreign_owned_success_control(self):
        self.responses[6] = (404, {'error': {'code': 'NOT_FOUND'}})
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_transport_timeout_is_bounded_failure_without_retry_or_driver_text(self):
        self.responses[1] = TimeoutError('secret-from-driver')
        result = self.collect()
        self.assertFalse(result['all_checks_passed'])
        self.assertEqual(len(self.calls), 7)
        self.assertNotIn('secret-from-driver', json.dumps(result))

    def test_raw_tokens_names_and_workspace_ids_are_not_in_output(self):
        self.responses[0][1]['data']['items'][0]['name'] = 'private staff workspace'
        result = json.dumps(self.collect())
        for private in list(TOKENS.values()) + [W1, W2, P1, P2, self.packet['origin'], 'private staff workspace']:
            self.assertNotIn(private, result)

    def test_arbitrary_route_prefix_is_rejected(self):
        self.packet['api_prefix'] = '/api/v1/provider/submit'
        self.assert_blocked_before_http()

    def test_origin_not_allowlisted_is_rejected(self):
        self.assert_blocked_before_http(allowed='https://other.example.test')

    def test_plain_http_is_rejected(self):
        self.packet['origin'] = 'http://owned-candidate.example.test'
        self.assert_blocked_before_http()

    def test_embedded_origin_credentials_are_rejected(self):
        self.packet['origin'] = 'https://secret@owned-candidate.example.test'
        self.assert_blocked_before_http()

    def test_loopback_target_is_rejected(self):
        self.packet['origin'] = 'https://127.0.0.1'
        self.assert_blocked_before_http()

    def test_missing_token_is_rejected_before_http(self):
        tokens = copy.deepcopy(TOKENS)
        del tokens['revoked']
        self.assert_blocked_before_http(tokens)

    def test_token_hash_mismatch_is_rejected_before_http(self):
        tokens = dict(TOKENS, empty='different-secret')
        self.assert_blocked_before_http(tokens)

    def test_same_token_cannot_stand_for_positive_and_negative_accounts(self):
        tokens = dict(TOKENS, empty=TOKENS['owned'])
        self.packet['token_sha256']['empty'] = self.packet['token_sha256']['owned']
        self.assert_blocked_before_http(tokens)

    def test_unknown_packet_field_cannot_assert_live_acceptance(self):
        self.packet['accepted'] = True
        self.assert_blocked_before_http()

    def test_same_tenant_cannot_stand_for_foreign_control(self):
        self.packet['accounts']['foreign']['workspace_id'] = W1
        self.assert_blocked_before_http()

    def test_foreign_workspace_in_owned_directory_is_rejected(self):
        self.responses[0][1]['data']['items'].append({'id': W2, 'roles': ['viewer']})
        self.responses[0][1]['data']['total'] = 2
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_duplicate_workspace_rows_are_rejected(self):
        self.responses[0][1]['data']['items'].append({'id': W1, 'roles': ['viewer']})
        self.responses[0][1]['data']['total'] = 2
        self.assertFalse(self.collect()['all_checks_passed'])

    def test_signed_partial_observations_cannot_enter_alias_path(self):
        path = ROOT / 'scripts/promote-candidate.py'
        spec = importlib.util.spec_from_file_location('reject_partial', path)
        promotion = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(promotion)
        with tempfile.TemporaryDirectory() as directory:
            bundle, output = Path(directory)/'partial.json', Path(directory)/'result.json'
            bundle.write_text(json.dumps(self.collect()), encoding='utf-8')
            with patch.object(promotion, 'command') as command:
                self.assertEqual(promotion.main(['--bundle', str(bundle), '--gate', 'workspace', '--output', str(output), '--execute']), 1)
                command.assert_not_called()
            self.assertFalse(json.loads(output.read_text())['promoted'])

    def test_origin_query_cannot_expand_request_scope(self):
        self.packet['origin'] += '?submit=1'
        self.assert_blocked_before_http()

    def test_header_injection_is_rejected_before_http(self):
        tokens = dict(TOKENS, owned='valid\r\nX-Forwarded-Host: other')
        self.packet['token_sha256']['owned'] = hashlib.sha256(tokens['owned'].encode()).hexdigest()
        self.assert_blocked_before_http(tokens)

    def test_source_mismatch_cli_has_no_http_side_effect(self):
        module = load()
        with tempfile.TemporaryDirectory() as directory:
            contract, output = Path(directory)/'contract.json', Path(directory)/'result.json'
            contract.write_text(json.dumps(self.packet), encoding='utf-8')
            with patch.object(module, 'collect') as collect:
                self.assertEqual(module.main(['--contract', str(contract), '--source-sha', 'c'*40, '--output', str(output)]), 2)
                collect.assert_not_called()
            self.assertFalse(output.exists())

    def test_existing_output_cli_is_immutable_before_http(self):
        module = load()
        with tempfile.TemporaryDirectory() as directory:
            contract, output = Path(directory)/'contract.json', Path(directory)/'result.json'
            contract.write_text(json.dumps(self.packet), encoding='utf-8')
            output.write_text('retained baseline', encoding='utf-8')
            with patch.object(module, 'collect') as collect:
                self.assertEqual(module.main(['--contract', str(contract), '--source-sha', 'a'*40, '--output', str(output)]), 2)
                collect.assert_not_called()
            self.assertEqual(output.read_text(), 'retained baseline')


class BoundedHttpTests(unittest.TestCase):
    class Response:
        code = 200
        def __init__(self, body, content_type='application/json'):
            self.body = body
            self.headers = Message()
            self.headers['Content-Type'] = content_type
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return self.body[:limit]

    def request(self, response):
        module = load()
        with patch.object(module.urllib.request, 'build_opener') as build:
            opener = build.return_value
            opener.open.return_value = response
            result = module.get_json('https://owned.example.test/api/v1/workspaces', 'private-bearer')
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(opener.open.call_args.kwargs['timeout'], 5)
            self.assertNotIn('private-bearer', request.full_url)
            self.assertEqual(build.call_args.args[0].proxies, {})
            return result

    def test_native_driver_uses_one_get_and_bounded_timeout(self):
        self.assertEqual(self.request(self.Response(b'{"data": {}}')), (200, {'data': {}}))

    def test_native_driver_refuses_oversized_response(self):
        with self.assertRaises(ValueError):
            self.request(self.Response(b'a'*(1024*1024+1)))

    def test_native_driver_refuses_duplicate_json_keys(self):
        with self.assertRaises(ValueError):
            self.request(self.Response(b'{"data": {}, "data": {"accepted": true}}'))

    def test_native_driver_refuses_html_login_page(self):
        with self.assertRaises(ValueError):
            self.request(self.Response(b'<html>login</html>', 'text/html'))

    def test_native_driver_never_forwards_bearer_on_redirect(self):
        module = load()
        headers = Message()
        headers['Content-Type'] = 'application/json'
        with patch.object(module.urllib.request, 'build_opener') as build:
            build.return_value.open.side_effect = urllib.error.HTTPError('https://owned.example.test', 302, 'redirect', headers, None)
            with self.assertRaises(ValueError):
                module.get_json('https://owned.example.test', 'private-bearer')
            self.assertEqual(build.return_value.open.call_count, 1)
        self.assertIsNone(module.NoRedirect().redirect_request(None, None, 302, 'redirect', headers, 'https://foreign.example.test'))


if __name__ == '__main__':
    unittest.main()
