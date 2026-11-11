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
    return _meta(_parse(_read(path)))


def _read(path) -> bytes:
    raw = Path(path).read_bytes()
    if len(raw) > MAX_FIXTURE_BYTES:
        raise AcceptanceError('provider fixture exceeds the byte cap')
    return raw


def _parse(raw: bytes) -> dict:
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
    return value


def _meta(value: dict) -> dict:
    return {'kind': value['kind'], 'case': value['case'], 'expect': value['expect'],
            'digest': digest(value)}


def recorded_cases(directory=FIXTURE_DIR) -> set[str]:
    """Case ids backed by a checked-in recording; live runs may only use these."""
    return {_meta(_parse(_read(path)))['case'] for path in Path(directory).glob('*.json')}


def _jsonrpc_error(response):
    error = response.get('error')
    if not isinstance(error, dict):
        return None
    code = error.get('code')
    if type(code) is not int or not isinstance(error.get('message'), str):
        raise AcceptanceError('recorded MCP error is malformed')
    if not 1 <= len(error['message']) <= 500:
        raise AcceptanceError('recorded MCP error message is unbounded')
    return error


def _validate_phase_evidence(response: dict, phase: str) -> None:
    """A phase fixture must carry the recorded transport evidence it classifies."""
    if _jsonrpc_error(response) is not None:
        return
    if phase in ('initialize', 'tools/list'):
        raise AcceptanceError('recorded MCP phase rejection needs a JSON-RPC error')
    # tools/call may have begun before the connection failed: the recording is a
    # (possibly partial) JSON-RPC envelope, not an invented provider payload.
    if response.get('jsonrpc') != '2.0' or type(response.get('id')) is not int:
        raise AcceptanceError('recorded tools/call observation is not a JSON-RPC envelope')


def _replay_model(fixture):
    basis_raw = fixture['request'].get('basis')
    if not isinstance(basis_raw, dict):
        raise AcceptanceError('recorded model request has no basis')
    basis = conversation_model.validate_basis(basis_raw)
    output = fixture['response'].get('output')
    if output is None:
        raise AcceptanceError('recorded model response is not structured output')
    return conversation_model.validate_proposal(output, basis)


def _replay_xverum(fixture):
    request = fixture['request']
    tool = request.get('tool')
    # Arguments are validated first, for every MCP recording.
    arguments = xverum_mcp.validate_arguments(tool, request.get('arguments'))
    phase = request.get('observed_phase')
    if phase is not None:
        # A recorded transport observation, not a provider payload: validate the
        # recorded evidence, then classify exactly as the production transport
        # does (tools/call is unknown, earlier phases are definite rejections).
        if phase not in ('initialize', 'tools/list', 'tools/call'):
            raise AcceptanceError('recorded MCP phase is not supported')
        _validate_phase_evidence(fixture['response'], phase)
        raise xverum_mcp.XverumTransportError(phase)
    return xverum_mcp.projection(tool, fixture['response'], arguments).model_dump(mode='json')


def replay(path) -> dict:
    """Replay one recorded provider exchange and assert its classification."""
    # One read, one parse: the receipt digest describes exactly what replayed.
    value = _parse(_read(path))
    meta = _meta(value)
    try:
        if meta['kind'] == 'conversation_model':
            detail = _replay_model(value)
        else:
            detail = _replay_xverum(value)
        outcome = 'accepted'
    except AcceptanceError:
        # A malformed recording is never a provider rejection.
        raise
    except xverum_mcp.XverumTransportError as error:
        # A definite nonacceptance is a clean rejection; only a failure after
        # tools/call begins is unknown (never auto-retried by callers).
        outcome = 'unknown' if error.outcome == 'unknown' else 'rejected'
        detail = {'code': error.code, 'phase': error.phase}
        if meta['kind'] == 'xverum_mcp' and value['request'].get('observed_phase') is not None:
            detail['recorded_response_digest'] = digest(value['response'])
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
    if env.get(LIVE_ENV) != '1':
        raise LiveAcceptanceRefused('live provider acceptance is not enabled')
    raw = env.get(CREDIT_CAP_ENV, '')
    # Canonical positive integer only: no whitespace, sign, underscore or bool.
    if not isinstance(raw, str) or not re.fullmatch(r'[1-9][0-9]{0,3}', raw):
        raise LiveAcceptanceRefused('live provider acceptance needs a credit cap')
    cap = int(raw)
    if cap > 1000:
        raise LiveAcceptanceRefused('live provider acceptance credit cap must be 1..1000')
    return cap


def run_live(case: str, call, *, env, directory=FIXTURE_DIR) -> dict:
    """Execute exactly one gated live case through the injected client callable."""
    cap = live_credit_cap(env)
    if not _CASE.match(case or '') or not callable(call):
        raise AcceptanceError('live acceptance needs a bounded case and a client callable')
    if case not in recorded_cases(directory):
        raise AcceptanceError('live acceptance case must match a recorded fixture')
    result = call(credit_cap=cap)
    if not isinstance(result, dict):
        raise AcceptanceError('live provider acceptance returned no receipt')
    try:
        receipt_digest = digest(result)
    except (TypeError, ValueError) as error:
        raise AcceptanceError('live provider acceptance returned non-JSON evidence') from error
    receipt = {'case': case, 'credit_cap': cap, 'digest': receipt_digest,
               'outcome': result.get('outcome')}
    if receipt['outcome'] != 'accepted':
        raise AcceptanceError(f'live provider acceptance case {case} was not accepted')
    return receipt
