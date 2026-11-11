"""Provider-acceptance harness: recorded fixtures replay, live mode gated.

No network, no credential, no database. The recorded fixtures are checked-in
synthetic contract exchanges; replay runs the same strict validation as the
production adapters. Live mode is only reached through an explicit opt-in and a
positive credit cap, and a fake client proves there is exactly one dispatch.
"""
import json
from pathlib import Path

import pytest

from buyeros_api.providers import acceptance

FIXTURES = Path(__file__).resolve().parent / 'provider_acceptance'


def _load(name):
    return json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))


def _write(tmp_path, name, value):
    path = tmp_path / name
    path.write_text(json.dumps(value), encoding='utf-8')
    return path


def test_every_recorded_fixture_replays_and_classifies():
    receipts = acceptance.replay_all()
    assert len(receipts) == len(list(FIXTURES.glob('*.json'))) >= 8
    assert len({receipt['digest'] for receipt in receipts}) == len(receipts)
    assert {receipt['kind'] for receipt in receipts} == {'conversation_model', 'xverum_mcp'}
    assert {'accepted', 'rejected', 'unknown'} <= {receipt['outcome'] for receipt in receipts}


def test_accepted_model_reply_is_review_only_with_selected_citations():
    receipt = acceptance.replay(FIXTURES / 'conversation-model-accepted.json')
    assert receipt['outcome'] == 'accepted'
    detail = receipt['detail']
    assert detail['status'] == 'needs_review' and detail['fixture'] is False
    assert {citation['id'] for citation in detail['citations']} == {
        f'fact:profile:{_load("conversation-model-accepted")["request"]["basis"]["icp_version_id"]}'
        ':77777777-7777-4777-8777-777777777777',
        'document:66666666-6666-4666-8666-666666666666'}


def test_unselected_citation_is_a_clean_rejection():
    receipt = acceptance.replay(FIXTURES / 'conversation-model-unselected-citation.json')
    assert receipt['outcome'] == 'rejected'
    assert receipt['detail'] == {'code': 'CONTRACT_REJECTED'}


def test_refusal_status_is_rejected_not_coerced_into_review():
    assert acceptance.replay(FIXTURES / 'conversation-model-refusal.json')['outcome'] == 'rejected'


def test_unknown_mcp_outcome_is_never_reported_as_rejected():
    receipt = acceptance.replay(FIXTURES / 'xverum-dispatch-unknown.json')
    assert receipt['outcome'] == 'unknown'
    assert receipt['detail']['phase'] == 'tools/call'
    assert 'credits_used' not in receipt


def test_accepted_mcp_receipt_carries_the_reported_credits():
    receipt = acceptance.replay(FIXTURES / 'xverum-company-search-accepted.json')
    assert receipt['outcome'] == 'accepted'
    assert receipt['credits_used'] == 2


def test_fixture_loader_rejects_malformed_or_unbounded_recordings(tmp_path):
    base = _load('xverum-company-search-accepted')
    cases = {
        'wrong-schema': {**base, 'schema': 'provider-acceptance.v0'},
        'unknown-kind': {**base, 'kind': 'unknown_provider'},
        'bad-case': {**base, 'case': 'UPPER Case! '},
        'unknown-expectation': {**base, 'expect': 'maybe'},
        'bad-time': {**base, 'recorded_at': 'yesterday'},
        'extra-key': {**base, 'token': 'should-never-be-recorded'},
        'empty-request': {**base, 'request': {}},
    }
    for name, value in cases.items():
        with pytest.raises(acceptance.AcceptanceError):
            acceptance.replay(_write(tmp_path, f'{name}.json', value))
    broken = tmp_path / 'broken.json'
    broken.write_text('{not json', encoding='utf-8')
    with pytest.raises(acceptance.AcceptanceError):
        acceptance.load_fixture(broken)
    oversized = tmp_path / 'oversized.json'
    oversized.write_bytes(b'{' + b' ' * acceptance.MAX_FIXTURE_BYTES + b'}')
    with pytest.raises(acceptance.AcceptanceError):
        acceptance.load_fixture(oversized)


def test_expected_classification_mismatch_is_caught(tmp_path):
    value = _load('xverum-dispatch-unknown')
    value['expect'] = 'accepted'
    with pytest.raises(acceptance.AcceptanceError):
        acceptance.replay(_write(tmp_path, 'mismatch.json', value))


def test_digest_is_stable_and_content_bound():
    path = FIXTURES / 'conversation-model-accepted.json'
    first = acceptance.load_fixture(path)['digest']
    assert first == acceptance.load_fixture(path)['digest']
    assert first == acceptance.digest(_load('conversation-model-accepted'))
    assert len(first) == 64 and int(first, 16) >= 0


def test_missing_fixture_directory_is_an_error(tmp_path):
    with pytest.raises(acceptance.AcceptanceError):
        acceptance.replay_all(tmp_path)


def test_live_mode_is_refused_without_explicit_opt_in_and_cap():
    for env in ({}, {acceptance.LIVE_ENV: '0'},
                {acceptance.CREDIT_CAP_ENV: '5'},
                {acceptance.LIVE_ENV: '1'},
                {acceptance.LIVE_ENV: '1', acceptance.CREDIT_CAP_ENV: '0'},
                {acceptance.LIVE_ENV: '1', acceptance.CREDIT_CAP_ENV: 'many'},
                {acceptance.LIVE_ENV: '1', acceptance.CREDIT_CAP_ENV: '1001'}):
        with pytest.raises(acceptance.LiveAcceptanceRefused):
            acceptance.live_credit_cap(env)


def test_live_mode_dispatches_exactly_one_capped_case():
    calls = []

    def fake_call(**kwargs):
        calls.append(kwargs)
        return {'outcome': 'accepted', 'credits_used': 2, 'request_id': 'req_live_001'}

    receipt = acceptance.run_live('company-search-projection', fake_call,
        env={acceptance.LIVE_ENV: '1', acceptance.CREDIT_CAP_ENV: '5'})
    assert [call['credit_cap'] for call in calls] == [5]
    assert receipt == {'case': 'company-search-projection', 'credit_cap': 5,
                       'digest': acceptance.digest({'outcome': 'accepted', 'credits_used': 2,
                                                    'request_id': 'req_live_001'}),
                       'outcome': 'accepted'}


def test_live_mode_fails_closed_without_a_retry():
    calls = []

    def unknown_after_dispatch(**kwargs):
        calls.append(kwargs)
        return {'outcome': 'unknown'}

    with pytest.raises(acceptance.AcceptanceError):
        acceptance.run_live('dispatch-timeout-after-call', unknown_after_dispatch,
            env={acceptance.LIVE_ENV: '1', acceptance.CREDIT_CAP_ENV: '1'})
    assert len(calls) == 1

    def raise_after_dispatch(**kwargs):
        calls.append(kwargs)
        raise TimeoutError('no live retry')

    with pytest.raises(TimeoutError):
        acceptance.run_live('dispatch-timeout-after-call', raise_after_dispatch,
            env={acceptance.LIVE_ENV: '1', acceptance.CREDIT_CAP_ENV: '1'})
    assert len(calls) == 2
