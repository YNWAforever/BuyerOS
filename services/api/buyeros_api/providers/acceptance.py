"""Provider-acceptance harness: recorded fixtures replay, live mode gated.

Fixture replay is pure and deterministic: it loads a recorded provider exchange,
re-runs the *same* strict validation the production adapter uses and checks the
fixture's expected classification (``accepted`` / ``rejected`` / ``unknown``).
No network, no credential, no paid call.

A live acceptance run is only possible when an operator explicitly opts in
(`BUYEROS_PROVIDER_ACCEPTANCE_LIVE=1`) and states a positive per-case credit cap
(`BUYEROS_PROVIDER_ACCEPTANCE_CREDIT_CAP`). The harness never discovers
credentials, never retries a dispatch and never runs from recorded fixtures.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import conversation_model, xverum_mcp

FIXTURE_SCHEMA = 'provider-acceptance.v1'
FIXTURE_KINDS = ('conversation_model', 'xverum_mcp')
EXPECTATIONS = ('accepted', 'rejected', 'unknown')
LIVE_ENV = 'BUYEROS_PROVIDER_ACCEPTANCE_LIVE'
CREDIT_CAP_ENV = 'BUYEROS_PROVIDER_ACCEPTANCE_CREDIT_CAP'
MAX_FIXTURE_BYTES = 64 * 1024
FIXTURE_DIR = Path(__file__).resolve().parents[2] / 'tests' / 'provider_acceptance'
_CASE = re.compile(r'^[a-z0-9][a-z0-9-]{2,80}$')
_RECORDED_AT = re.compile(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
_FIXTURE_KEYS = {'schema', 'kind', 'case', 'expect', 'recorded_at', 'request', 'response'}


class AcceptanceError(ValueError):
    """The recording or its replay is not an acceptable provider exchange."""


class LiveAcceptanceRefused(PermissionError):
    """Live provider acceptance is not enabled; recorded replay is all that runs."""


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _object(value, what):
    if not isinstance(value, dict) or not value:
        raise AcceptanceError(f'{what} must be a non-empty object')
    return value


def load_fixture(path) -> dict:
    """Read one recorded exchange and validate its envelope; no replay yet."""
    raw = Path(path).read_bytes()
    if len(raw) > MAX_FIXTURE_BYTES:
        raise AcceptanceError('provider fixture exceeds the byte cap')
    try:
        value = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AcceptanceError('provider fixture is not valid UTF-8 JSON') from error
    if not isinstance(value, dict) or set(value) != _FIXTURE_KEYS:
        raise AcceptanceError('provider fixture must have exactly the contract keys')
    if value['schema'] != FIXTURE_SCHEMA or value['kind'] not in FIXTURE_KINDS:
        raise AcceptanceError('unsupported provider fixture contract')
    if not isinstance(value['case'], str) or not _CASE.match(value['case']):
        raise AcceptanceError('provider fixture case must be a bounded lowercase slug')
    if value['expect'] not in EXPECTATIONS:
        raise AcceptanceError('provider fixture expectation is not supported')
    if not isinstance(value['recorded_at'], str) or not _RECORDED_AT.match(value['recorded_at']):
        raise AcceptanceError('provider fixture needs a UTC recording time')
    _object(value['request'], 'provider fixture request')
    _object(value['response'], 'provider fixture response')
    return {'kind': value['kind'], 'case': value['case'], 'expect': value['expect'],
            'digest': digest(value)}


def _replay_model(fixture):
    basis = conversation_model.validate_basis(fixture['request']['basis'])
    output = fixture['response'].get('output')
    if output is None:
        raise AcceptanceError('recorded model response is not structured output')
    return conversation_model.validate_proposal(output, basis)


def _replay_xverum(fixture):
    request = fixture['request']
    tool = request.get('tool')
    phase = request.get('observed_phase')
    if phase is not None:
        # A recorded transport observation, not a provider payload: classify it
        # exactly as the production transport does (tools/call is unknown).
        if phase not in ('initialize', 'tools/list', 'tools/call'):
            raise AcceptanceError('recorded MCP phase is not supported')
        raise xverum_mcp.XverumTransportError(phase)
    arguments = xverum_mcp.validate_arguments(tool, request.get('arguments'))
    return xverum_mcp.projection(tool, fixture['response'], arguments).model_dump(mode='json')


def replay(path) -> dict:
    """Replay one recorded provider exchange and assert its classification."""
    meta = load_fixture(path)
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    try:
        if meta['kind'] == 'conversation_model':
            detail = _replay_model(value)
        else:
            detail = _replay_xverum(value)
        outcome = 'accepted'
    except xverum_mcp.XverumTransportError as error:
        # A definite nonacceptance is a clean rejection; only a failure after
        # tools/call begins is unknown (never auto-retried by callers).
        outcome = 'unknown' if error.outcome == 'unknown' else 'rejected'
        detail = {'code': error.code, 'phase': error.phase}
    except ValueError as error:
        if meta['expect'] == 'accepted':
            raise AcceptanceError(f'accepted fixture failed replay: {error}') from error
        outcome, detail = 'rejected', {'code': 'CONTRACT_REJECTED'}
    if outcome != meta['expect']:
        raise AcceptanceError(f'fixture expected {meta["expect"]}, replayed {outcome}')
    receipt = {'kind': meta['kind'], 'case': meta['case'], 'outcome': outcome,
               'digest': meta['digest'], 'detail': detail}
    if outcome == 'accepted' and meta['kind'] == 'xverum_mcp':
        receipt['credits_used'] = detail['credits_used']
    return receipt


def replay_all(directory=FIXTURE_DIR) -> list[dict]:
    paths = sorted(Path(directory).glob('*.json'))
    if not paths:
        raise AcceptanceError('no recorded provider fixtures found')
    return [replay(path) for path in paths]


def live_credit_cap(env) -> int:
    """Refuse live execution unless an operator opted in and capped the spend."""
    if env.get(LIVE_ENV) not in ('1', 'true'):
        raise LiveAcceptanceRefused('live provider acceptance is not enabled')
    raw = env.get(CREDIT_CAP_ENV, '')
    try:
        cap = int(raw)
    except (TypeError, ValueError):
        raise LiveAcceptanceRefused('live provider acceptance needs a credit cap') from None
    if type(cap) is not int or cap < 1 or cap > 1000:
        raise LiveAcceptanceRefused('live provider acceptance credit cap must be 1..1000')
    return cap


def run_live(case: str, call, *, env) -> dict:
    """Execute exactly one gated live case through the injected client callable."""
    cap = live_credit_cap(env)
    if not _CASE.match(case or '') or not callable(call):
        raise AcceptanceError('live acceptance needs a bounded case and a client callable')
    result = call(credit_cap=cap)
    if not isinstance(result, dict):
        raise AcceptanceError('live provider acceptance returned no receipt')
    receipt = {'case': case, 'credit_cap': cap, 'digest': digest(result),
               'outcome': result.get('outcome')}
    if receipt['outcome'] != 'accepted':
        raise AcceptanceError(f'live provider acceptance case {case} was not accepted')
    return receipt
