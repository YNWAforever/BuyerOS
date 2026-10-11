"""Read-only API observations. Never asserts G0, mapping, UI or rollback acceptance."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

ACCOUNTS = ('owned', 'foreign', 'empty', 'revoked')
MAX_BODY = 1024 * 1024
PACKET_KEYS = {'schema', 'source_sha', 'origin', 'api_prefix', 'authorization_reference_sha256', 'accounts', 'token_sha256'}
ROLES = {'viewer', 'operator', 'reviewer', 'workspace_admin'}


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def validate(packet, tokens, allowed_origin):
    if type(packet) is not dict or set(packet) != PACKET_KEYS or packet['schema'] != 'buyeros.workspace-api-target.v1':
        raise ValueError('invalid target packet')
    for key, length in [('source_sha', 40), ('authorization_reference_sha256', 64)]:
        if type(packet[key]) is not str or not re.fullmatch('[0-9a-f]{'+str(length)+'}', packet[key]):
            raise ValueError('missing reviewed source or authorization reference')
    origin = packet['origin']
    if type(origin) is not str or origin != allowed_origin or packet['api_prefix'] != '/v1':
        raise ValueError('origin or fixed read-only route scope mismatch')
    parsed = urllib.parse.urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment or parsed.port not in (None, 443)
            or origin != 'https://' + parsed.hostname
            or parsed.hostname == 'localhost' or parsed.hostname.endswith(('.localhost', '.local', '.internal'))):
        raise ValueError('exact public HTTPS origin required')
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError('IP literal is not a reviewed runtime origin')
    accounts = packet['accounts']
    if type(accounts) is not dict or set(accounts) != {'owned', 'foreign'}:
        raise ValueError('paired owned and foreign target controls required')
    for account in accounts.values():
        if type(account) is not dict or set(account) != {'workspace_id', 'project_id', 'roles'}:
            raise ValueError('invalid account target')
        for key in ('workspace_id', 'project_id'):
            value = account[key]
            if type(value) is not str or str(uuid.UUID(value)) != value:
                raise ValueError('canonical UUID required')
        roles = account['roles']
        if (type(roles) is not list or not roles or len(roles) > 4
                or any(type(role) is not str or role not in ROLES for role in roles) or len(set(roles)) != len(roles)):
            raise ValueError('bounded unique roles required')
    if accounts['owned']['workspace_id'] == accounts['foreign']['workspace_id']:
        raise ValueError('foreign control must be a different tenant')
    hashes = packet['token_sha256']
    if type(tokens) is not dict or set(tokens) != set(ACCOUNTS) or type(hashes) is not dict or set(hashes) != set(ACCOUNTS):
        raise ValueError('four distinct reviewed account credentials required')
    if any(type(token) is not str or not token or len(token) > 16384
           or not token.isascii() or any(char.isspace() or ord(char) < 33 or ord(char) > 126 for char in token)
           or hashes[key] != digest(token) for key, token in tokens.items()):
        raise ValueError('credential binding failed')
    if len(set(tokens.values())) != len(ACCOUNTS):
        raise ValueError('positive and negative credentials must be independent')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_json(url, token):
    """One TLS-verified GET; no redirects, retry, response logging or URL credentials."""
    request = urllib.request.Request(url, method='GET', headers={
        'Authorization': 'Bearer ' + token, 'Accept': 'application/json', 'User-Agent': 'BuyerOS-owned-read-canary/1'})
    # Ignore inherited proxy settings: a secret must only go to the approved TLS origin.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(request, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        status = response.code
        if 300 <= status < 400:
            raise ValueError('runtime redirects are refused')
        if response.headers.get_content_type() != 'application/json':
            raise ValueError('JSON envelope required')
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError('response too large')
        return status, json.loads(body.decode('utf-8'), object_pairs_hook=unique_keys)


def collect(packet, tokens, allowed_origin, *, get=get_json):
    validate(packet, tokens, allowed_origin)
    owned, foreign = packet['accounts']['owned'], packet['accounts']['foreign']
    base = packet['origin'] + packet['api_prefix']
    project = lambda account: '/workspaces/' + account['workspace_id'] + '/projects/' + account['project_id']
    def live(body):
        return (type(body) is dict and body.get('data_mode') == 'live'
                and type(body.get('data')) is dict and type(body.get('request_id')) is str
                and re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', body['request_id']) is not None)
    def directory(body):
        if not live(body):
            return False
        data = body['data']
        items = data.get('items')
        if (type(items) is not list or not 1 <= len(items) <= 100 or type(data.get('total')) is not int
                or data['total'] < len(items) or data.get('offset') != 0 or data.get('limit') != 100):
            return False
        if any(type(item) is not dict or type(item.get('id')) is not str for item in items):
            return False
        ids = [item['id'] for item in items]
        if len(ids) != len(set(ids)) or foreign['workspace_id'] in ids:
            return False
        matches = [item for item in items if type(item) is dict and item.get('id') == owned['workspace_id']]
        if len(matches) != 1:
            return False
        roles = matches[0].get('roles')
        return (type(roles) is list and all(type(role) is str for role in roles)
                and len(roles) == len(set(roles)) and sorted(roles) == sorted(owned['roles']))
    def known_project(body, account):
        return (live(body) and body['data'].get('data_mode') == 'live'
                and body['data'].get('id') == account['project_id']
                and body['data'].get('workspace_id') == account['workspace_id'])
    def empty(body):
        return (live(body) and body['data'].get('items') == [] and type(body['data'].get('total')) is int
                and body['data']['total'] == 0 and body['data'].get('offset') == 0 and body['data'].get('limit') == 100)
    def denied(body):
        return (type(body) is dict and set(body) == {'code', 'message', 'request_id', 'retryable'}
                and body['code'] == 'NOT_FOUND' and type(body['message']) is str
                and type(body['request_id']) is str and re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}', body['request_id']) is not None
                and body['retryable'] is False)
    observations = [
        ('owned_workspace_roles_response', 'owned', '/workspaces?offset=0&limit=100', 200, directory),
        ('owned_project_response', 'owned', project(owned), 200, lambda body: known_project(body, owned)),
        ('empty_directory_response', 'empty', '/workspaces?offset=0&limit=100', 200, empty),
        ('empty_account_project_not_found', 'empty', project(owned), 404, denied),
        ('revoked_account_project_not_found', 'revoked', project(owned), 404, denied),
        ('foreign_tenant_project_not_found', 'owned', project(foreign), 404, denied),
        ('foreign_account_owned_project_response', 'foreign', project(foreign), 200, lambda body: known_project(body, foreign)),
    ]
    checks = []
    for name, account, path, expected_status, predicate in observations:
        check = {'code': name, 'passed': False, 'observed_status': None, 'response_sha256': None}
        try:
            status, body = get(base + path, tokens[account])
            check['observed_status'] = status if type(status) is int and 100 <= status <= 599 else None
            check['response_sha256'] = digest(json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=True))
            check['passed'] = type(status) is int and status == expected_status and predicate(body) is True
        except Exception:
            # Neither raw response nor exception text crosses the evidence boundary.
            check['error_code'] = 'READ_OBSERVATION_UNAVAILABLE'
        checks.append(check)
    return {'schema': 'buyeros.workspace-api-observations.v1',
            'reviewed_source_sha': packet['source_sha'],
            'contract_sha256': digest(json.dumps(packet, sort_keys=True, separators=(',', ':'))),
            'checked_at': datetime.now(timezone.utc).isoformat(), 'scope': 'bounded_api_reads_only',
            'checks': checks, 'all_checks_passed': all(check['passed'] for check in checks), 'promotable': False,
            'acceptance_blockers': ['exact_deployment_db_binding_unproven', 'canonical_mapping_not_collected',
                                    'browser_canary_not_collected', 'compatible_frontend_api_rollback_not_collected']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', required=True, type=Path)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.contract.stat().st_size > 65536:
            raise ValueError('invalid input or immutable output exists')
        packet = json.loads(args.contract.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_keys)
        if type(packet) is not dict or packet.get('source_sha') != args.source_sha:
            raise ValueError('reviewed source mismatch')
        tokens = {key: os.environ.get('BUYEROS_G0_' + key.upper() + '_TOKEN', '') for key in ACCOUNTS}
        result = collect(packet, tokens, os.environ.get('BUYEROS_G0_ALLOWED_ORIGIN', ''))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            output.write(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'all_checks_passed': result['all_checks_passed'], 'promotable': False}))
        return 0 if result['all_checks_passed'] else 1
    except Exception:
        print(json.dumps({'error': {'code': 'INVALID_OR_UNAVAILABLE_WORKSPACE_OBSERVATION'}}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
