"""Regenerate the recorded provider-acceptance fixtures (no network, no secrets).

The fixtures are the checked-in acceptance record: each one stores a synthetic
but contract-shaped provider exchange plus its expected classification. They are
replayed by ``buyeros_api.providers.acceptance`` in CI. Regenerate with:

    uv run python tools/generate_provider_acceptance_fixtures.py
"""
import hashlib
import json
from pathlib import Path

from buyeros_api.providers import conversation_model

ROOT = Path(__file__).resolve().parent.parent / 'tests' / 'provider_acceptance'
WORKSPACE = '11111111-1111-4111-8111-111111111111'
PROJECT = '22222222-2222-4222-8222-222222222222'
ACTOR = '44444444-4444-4444-8444-444444444444'
ICP = '55555555-5555-4555-8555-555555555555'
DOCUMENT = '66666666-6666-4666-8666-666666666666'
FACT = '77777777-7777-4777-8777-777777777777'
FACT_CITATION = f'fact:profile:{ICP}:{FACT}'
DOCUMENT_CITATION = f'document:{DOCUMENT}'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def basis(question='What changed in the Acme renewal terms?'):
    value = {
        'schema': conversation_model.SCHEMA,
        'workspace_id': WORKSPACE, 'project_id': PROJECT, 'actor_id': ACTOR,
        'icp_version_id': ICP, 'icp_hash': 'sha256:' + 'a' * 64,
        'offer_revision': 3, 'question': question,
        'sources': [
            {'citation': {'id': FACT_CITATION, 'label': 'Approved offer fact',
                          'locator': {'surface': 'profile', 'id': ICP}},
             'excerpts': ['The standard renewal term is 24 months.']},
            {'citation': {'id': DOCUMENT_CITATION, 'label': 'Offer document',
                          'locator': {'surface': 'document', 'id': DOCUMENT}},
             'excerpts': ['The renewal notice period is 60 days.']},
        ],
        'document_ids': [DOCUMENT],
    }
    value['basis_hash'] = hashlib.sha256(canonical(value).encode()).hexdigest()
    return value


def fixture(kind, case, expect, request, response):
    return {'schema': 'provider-acceptance.v1', 'kind': kind, 'case': case,
            'expect': expect, 'recorded_at': '2026-11-11T12:00:00Z',
            'request': request, 'response': response}


def model_output(citations, status='needs_review'):
    return {'text': 'The renewal term is 24 months with a 60-day notice period.',
            'citations': citations, 'status': status}


def write(name, value):
    path = ROOT / f'{name}.json'
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n',
                    encoding='utf-8')
    print('wrote', path.name)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    model_basis = basis()
    write('conversation-model-accepted', fixture(
        'conversation_model', 'grounded-review-reply', 'accepted',
        {'basis': model_basis},
        {'output': model_output([FACT_CITATION, DOCUMENT_CITATION]),
         'usage': {'model': 'opencode-go/placeholder', 'input_tokens': 1200,
                   'output_tokens': 80},
         'latency_ms': 1500}))
    write('conversation-model-unselected-citation', fixture(
        'conversation_model', 'unselected-citation', 'rejected',
        {'basis': model_basis},
        {'output': model_output(['document:' + '8' * 8 + '-8888-4888-8888-' + '8' * 12]),
         'usage': {'model': 'opencode-go/placeholder', 'input_tokens': 1200,
                   'output_tokens': 80}}))
    write('conversation-model-refusal', fixture(
        'conversation_model', 'refusal-status', 'rejected',
        {'basis': model_basis},
        {'output': model_output([FACT_CITATION], status='refused'),
         'usage': {'model': 'opencode-go/placeholder', 'input_tokens': 1200,
                   'output_tokens': 10}}))

    search_arguments = {'query': 'Acme GmbH', 'page': 1, 'page_size': 5}
    company_card = {'id': '9000001', 'company_name': 'Acme GmbH',
                    'social_url': 'https://example.test/acme',
                    'slogan': 'Industrial components', 'headquarters': 'Hamburg, Germany',
                    'country_code': 'DE', 'industry': 'Industrial Machinery',
                    'employees_num': 240, 'website': 'https://acme.example', 'founded': 1998}
    write('xverum-company-search-accepted', fixture(
        'xverum_mcp', 'company-search-projection', 'accepted',
        {'tool': 'search_company_xverum', 'arguments': search_arguments},
        {'request_id': 'req_accept_001', 'credits_used': 2, 'credits_remaining': 998,
         'result_type': 'company', 'results': [company_card], 'total_count': 1,
         'page': 1, 'page_size': 5}))
    write('xverum-email-no-email-accepted', fixture(
        'xverum_mcp', 'email-not-found-nonbillable', 'accepted',
        {'tool': 'get_email_xverum', 'arguments': {'id': '9000001'}},
        {'request_id': 'req_email_001', 'credits_used': 0, 'credits_remaining': 998,
         'has_email': False, 'emails': []}))
    write('xverum-company-search-page-drift', fixture(
        'xverum_mcp', 'search-page-drift', 'rejected',
        {'tool': 'search_company_xverum', 'arguments': search_arguments},
        {'request_id': 'req_accept_002', 'credits_used': 2, 'credits_remaining': 996,
         'result_type': 'company', 'results': [company_card], 'total_count': 1,
         'page': 2, 'page_size': 5}))
    write('xverum-dispatch-unknown', fixture(
        'xverum_mcp', 'dispatch-timeout-after-call', 'unknown',
        {'tool': 'search_company_xverum', 'arguments': search_arguments,
         'observed_phase': 'tools/call'},
        {'jsonrpc': '2.0', 'id': 2}))
    write('xverum-activation-rejected', fixture(
        'xverum_mcp', 'initialize-rejected-before-call', 'rejected',
        {'tool': 'search_company_xverum', 'arguments': search_arguments,
         'observed_phase': 'initialize'},
        {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32000, 'message': 'unauthorized'}}))


if __name__ == '__main__':
    main()
