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
import sys
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
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


class PinnedCurlFixture:
    def setUp(self):
        import os
        self.package_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.package_temp.cleanup)
        self.package = Path(self.package_temp.name)
        (self.package / 'dist').mkdir()
        (self.package / 'dist/vc.js').write_text('// synthetic CLI')
        (self.package / 'package.json').write_text(json.dumps({
            'name': 'vercel', 'version': '50.28.0', 'bin': {'vercel': './dist/vc.js'}}))
        self.env_patch = patch.dict(os.environ, {'BUYEROS_VERCEL_CURL_PACKAGE': str(self.package)})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

class PinnedCurlTests(PinnedCurlFixture, unittest.TestCase):
    def test_curl_maps_only_after_private_auth_insertion(self):
        import os
        from vercel_cli_auth import authenticated_command
        argv = ['vercel', 'curl', '/v1/workspaces', '--scope', 'team_fixture', '--', '--config', '-']
        with patch.dict(os.environ, {'VERCEL_TOKEN': 'syntheticsecret'}):
            with authenticated_command(argv) as command:
                self.assertEqual(command[:3], ['node', str(self.package / 'dist/vc.js'), 'curl'])
                self.assertLess(command.index('--global-config'), command.index('--'))
                self.assertEqual(command[command.index('--') + 1:], ['--config', '-'])
                self.assertNotIn('syntheticsecret', repr(command))
            for verb in ('api', 'build', 'deploy', 'promote', 'pull'):
                with authenticated_command(['vercel', verb]) as command:
                    self.assertEqual(command[:2], ['vercel', verb])

    def test_missing_or_invalid_pin_refuses_before_execution(self):
        import os
        from vercel_cli_auth import authenticated_command
        original = (self.package / 'package.json').read_text()
        for fault in ('missing', 'relative', 'version', 'name', 'bin', 'entrypoint', 'json'):
            with self.subTest(fault=fault):
                (self.package / 'package.json').write_text(original)
                value = str(self.package)
                data = json.loads(original)
                if fault == 'missing': value = ''
                elif fault == 'relative': value = 'relative/package'
                elif fault == 'version': data['version'] = '54.17.2'
                elif fault == 'name': data['name'] = 'other'
                elif fault == 'bin': data['bin']['vercel'] = '../other.js'
                elif fault == 'entrypoint': (self.package / 'dist/vc.js').unlink()
                if fault == 'json': (self.package / 'package.json').write_text('{')
                else: (self.package / 'package.json').write_text(json.dumps(data))
                with patch.dict(os.environ, {'BUYEROS_VERCEL_CURL_PACKAGE': value, 'VERCEL_TOKEN': ''}):
                    with self.assertRaisesRegex(ValueError, '^protected curl CLI pin is invalid$'):
                        with authenticated_command(['vercel', 'curl', '/']): self.fail('must refuse')
                (self.package / 'dist/vc.js').write_text('// synthetic CLI')


class FreshRunnerCliAuthentication(PinnedCurlFixture, unittest.TestCase):
    def test_private_auth_file_exists_only_during_command_and_never_in_argv(self):
        import os
        import stat
        from vercel_cli_auth import authenticated_command
        secret='private-runner-token'
        for suffix in (['api','/v2/user'],['curl','/v1/internal/release-binding','--','--config','-']):
            argv=['vercel',*suffix]
            with patch.dict(os.environ,{'VERCEL_TOKEN':secret}):
                with authenticated_command(argv) as command:
                    config=Path(command[command.index('--global-config')+1])
                    self.assertEqual(json.loads((config/'auth.json').read_text()),{'token':secret})
                    self.assertNotIn(secret,repr(command))
                    self.assertEqual(argv,['vercel',*suffix])
                    if '--' in argv:self.assertLess(command.index('--global-config'),command.index('--'))
                    if os.name!='nt':self.assertEqual(stat.S_IMODE((config/'auth.json').stat().st_mode),0o600)
                self.assertFalse(config.exists())

    def test_private_auth_cleanup_on_failed_command(self):
        import os
        import subprocess
        from vercel_cli_auth import authenticated_command
        for error in (RuntimeError('command failed'),subprocess.TimeoutExpired(['vercel'],45)):
            with patch.dict(os.environ,{'VERCEL_TOKEN':'private-runner-token'}):
                with self.assertRaises(type(error)):
                    with authenticated_command(['vercel','api','/v2/user']) as command:
                        config=Path(command[-1])
                        raise error
                self.assertFalse(config.exists())

    def test_unrelated_commands_and_local_login_without_token_are_unchanged(self):
        import os
        from vercel_cli_auth import authenticated_command
        for token,argv in [('', ['vercel','api','/v2/user']),('private', ['gh','api','user'])]:
            with patch.dict(os.environ,{'VERCEL_TOKEN':token}):
                with authenticated_command(argv) as command:self.assertEqual(command,argv)


def packet():
    return {'schema': 'buyeros.workspace-api-target.v1', 'source_sha': 'a'*40,
            'origin': 'https://owned-candidate.example.test', 'api_prefix': '/v1',
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
            (404, {'code': 'NOT_FOUND', 'message': 'workspace not found', 'request_id': W1, 'retryable': False}),
            (404, {'code': 'NOT_FOUND', 'message': 'workspace not found', 'request_id': W1, 'retryable': False}),
            (404, {'code': 'NOT_FOUND', 'message': 'workspace not found', 'request_id': W1, 'retryable': False}),
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

    def test_reads_use_current_native_workspace_router_prefix(self):
        sys.path.insert(0, str(ROOT/'services/api'))
        from buyeros_api.api.routes.workspaces import router
        self.collect()
        self.assertEqual(urllib.parse.urlsplit(self.calls[0][0]).path, router.prefix)

    def test_denials_use_current_native_error_body(self):
        sys.path.insert(0, str(ROOT/'services/api'))
        from starlette.requests import Request
        from buyeros_api.api.errors import error_body
        request = Request({'type': 'http', 'headers': []})
        request.state.request_id = W1
        for index in (3, 4, 5):
            self.responses[index] = (404, error_body(request, code='NOT_FOUND', message='workspace not found'))
        self.assertTrue(self.collect()['all_checks_passed'])

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


class ProtectedVercelHttpTests(PinnedCurlFixture, unittest.TestCase):
    origin = 'https://buyeros-a1b2c3d4e-owner-projects.vercel.app'
    path = '/v1/internal/release-binding'

    def invoke(self, raw=None, *, url=None, code=0, error=None, token='private-bearer'):
        module = load()
        url = url or self.origin + self.path
        if raw is None:
            raw = b'{"data":{}}\n200\napplication/json\n' + url.encode()
        def run(command, **kwargs):
            self.command, self.options = command, kwargs
            # CLI 50.28 prepends --url and its protection header before our flags.
            # Thus --disable is not first: the private curlrc must really exist.
            curl_home = Path(kwargs['env']['CURL_HOME'])
            self.assertEqual((curl_home / '.curlrc').read_bytes(), b'')
            self.assertEqual((curl_home / '_curlrc').read_bytes(), b'')
            for key in ('HOME', 'USERPROFILE', 'APPDATA', 'XDG_CONFIG_HOME'):
                self.assertEqual(kwargs['env'].get(key), module.os.environ.get(key))
            if error:
                raise error
            kwargs['stdout'].write(raw)
            return module.subprocess.CompletedProcess(command, code)
        with patch.dict(module.os.environ, {'VERCEL_TOKEN': 'private-vercel', 'VERCEL_ORG_ID': 'team_test'}), \
                patch.object(module.subprocess, 'run', side_effect=run) as execute, \
                patch.object(module.urllib.request, 'build_opener') as native:
            try:
                return module.get_json(url, token)
            finally:
                self.assertLessEqual(execute.call_count, 1)
                native.assert_not_called()

    def test_protected_read_keeps_bearer_in_stdin_and_exact_origin_in_argv(self):
        self.assertEqual(self.invoke(), (200, {'data': {}}))
        argv = self.command
        self.assertEqual(argv[:8], ['node', str(self.package / 'dist/vc.js'), 'curl', self.path, '--deployment', self.origin, '--scope', 'team_test'])
        self.assertNotIn('private-bearer', repr(argv))
        self.assertNotIn('private-vercel', repr(argv))
        self.assertIn(b'Authorization: Bearer private-bearer', self.options['input'])
        self.assertEqual(self.options['timeout'], 30)
        for flag in ('--no-location', '--no-insecure', '--max-filesize', '--noproxy'):
            self.assertIn(flag, argv)
        query_url = self.origin + '/v1/workspaces?offset=0&limit=100'
        self.assertEqual(self.invoke(url=query_url), (200, {'data': {}}))
        self.assertEqual(self.command[3], '/v1/workspaces?offset=0&limit=100')

    def test_protected_read_preserves_http_denial_status(self):
        raw = b'{"code":"NOT_FOUND"}\n404\napplication/json; charset=utf-8\n' + (self.origin + self.path).encode()
        self.assertEqual(self.invoke(raw), (404, {'code': 'NOT_FOUND'}))

    def test_protected_read_rejects_redirect_and_changed_effective_origin(self):
        for status, url in [('302', self.origin + self.path), ('200', 'https://evil.test' + self.path),
                            ('200', self.origin + '/v1/workspaces')]:
            with self.subTest(status=status, url=url), self.assertRaises(ValueError):
                self.invoke(('{}\n' + status + '\napplication/json\n' + url).encode())

    def test_protected_read_refuses_scope_expansion_before_subprocess(self):
        module = load()
        with patch.object(module.subprocess, 'run') as run:
            for target in ['/relative', 'https://evil.test/v1/internal/release-binding',
                           'https://buyeros.vercel.app/v1/internal/release-binding']:
                with self.subTest(target=target), self.assertRaises(ValueError):
                    module.protected_get_json(target, 'bearer')
            run.assert_not_called()
        for url in [self.origin.replace('https://', 'http://') + self.path,
                    self.origin.replace('https://', 'https://user@') + self.path,
                    self.origin + ':443' + self.path, self.origin + self.path + '#fragment',
                    self.origin + '/v1/../admin', self.origin + '//evil.test',
                    self.origin + self.path + '?url=https://evil.test']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.invoke(url=url)

    def test_protected_read_refuses_header_injection_and_escapes_config(self):
        with self.assertRaises(ValueError):
            self.invoke(token='secret\nurl = "https://evil.test"')
        self.invoke(token='secret"\\suffix')
        self.assertIn(b'secret\\"\\\\suffix', self.options['input'])

    def test_protected_read_bounds_body_with_and_without_valid_metadata(self):
        body = b'"' + b'a' * (1024 * 1024 - 2) + b'"'
        self.assertEqual(len(self.invoke(body + b'\n200\napplication/json\n' +
                                         (self.origin + self.path).encode())[1]), 1024 * 1024 - 2)
        for raw in [b'x' * (1024 * 1024 + 2049),
                    b' ' * (1024 * 1024) + b'{}\n200\napplication/json\n' + (self.origin + self.path).encode()]:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                self.invoke(raw)

    def test_protected_read_rejects_html_duplicate_keys_and_invalid_status(self):
        for body, status, mime in [('{}', '200', 'text/html'), ('{"a":1,"a":2}', '200', 'application/json'),
                                   ('{}', '000', 'application/json'), ('not json', '200', 'application/json')]:
            with self.subTest(body=body, status=status, mime=mime), self.assertRaises(ValueError):
                self.invoke((body + '\n' + status + '\n' + mime + '\n' + self.origin + self.path).encode())

    def test_protected_read_sanitizes_cli_failure_and_timeout_without_retry(self):
        module = load()
        for code, error in [(1, None), (0, OSError('private-secret')),
                            (0, module.subprocess.TimeoutExpired(['private-secret'], 30))]:
            with self.subTest(code=code, error=type(error)), self.assertRaisesRegex(ValueError, '^protected runtime read unavailable$'):
                self.invoke(code=code, error=error)

    def test_missing_scope_fails_closed(self):
        module = load()
        with patch.dict(module.os.environ, {'VERCEL_TOKEN': 'private', 'VERCEL_ORG_ID': ''}), \
                patch.object(module.subprocess, 'run') as run, self.assertRaises(ValueError):
            module.get_json(self.origin + self.path, 'bearer')
        run.assert_not_called()

    def test_cli_linkage_uses_explicit_scope_without_lone_org_environment(self):
        module = load()
        with patch.dict(module.os.environ, {'VERCEL_PROJECT_ID': ''}):
            self.assertEqual(self.invoke(), (200, {'data': {}}))
        self.assertNotIn('VERCEL_ORG_ID', self.options['env'])
        self.assertEqual(self.command[self.command.index('--scope') + 1], 'team_test')

    def test_cli_linkage_preserves_complete_workflow_project_environment(self):
        module = load()
        with patch.dict(module.os.environ, {'VERCEL_PROJECT_ID': 'prj_test'}):
            self.assertEqual(self.invoke(), (200, {'data': {}}))
        self.assertEqual(self.options['env']['VERCEL_ORG_ID'], 'team_test')
        self.assertEqual(self.options['env']['VERCEL_PROJECT_ID'], 'prj_test')

    def test_normal_hosts_aliases_and_missing_vercel_token_keep_native_transport(self):
        module = load()
        cases = [(self.origin + self.path, ''), ('https://buyeros.vercel.app' + self.path, 'private'),
                 ('https://buyeros-a1b2c3d4e-owner.vercel.app.evil.test' + self.path, 'private')]
        for url, credential in cases:
            with self.subTest(url=url), patch.dict(module.os.environ, {'VERCEL_TOKEN': credential}), \
                    patch.object(module.urllib.request, 'build_opener') as build, \
                    patch.object(module.subprocess, 'run') as run:
                build.return_value.open.return_value = BoundedHttpTests.Response(b'{}')
                self.assertEqual(module.get_json(url, 'bearer'), (200, {}))
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
