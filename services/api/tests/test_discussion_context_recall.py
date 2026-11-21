"""Exercise saved-turn context through the real API with an offline model adapter."""
import psycopg
import pytest

from buyeros_api.providers.conversation_model import validate_proposal
from buyeros_api.providers.opencode_model import OpenCodeGoModelClient
from tests.test_conversation_admission_db import paid_case, WS
from tests.test_conversation_reply_db import api, conversation_api, enabled, SOURCE
from tests.test_conversation_threads_api import create, ROOT, headers
from tests.test_conversation_turns_api import turn_on_thread


@pytest.fixture
def discussions(paid_case):
    client, dsn, _ = paid_case
    try:
        yield client
    finally:
        with psycopg.connect(dsn) as db:
            db.execute('DELETE FROM conversation_threads WHERE workspace_id=%s', (WS,))


def test_identical_questions_receive_only_their_saved_threads_buyer_names(discussions, monkeypatch):
    client = discussions
    seen = []

    async def offline_completion(self, basis, route):
        seen.append(basis)
        notes = [msg['text'] for msg in basis['history'] if msg['role'] == 'user']
        # Parse only the supplied model history, without consulting the test's expected answers.
        order = next(note for note in notes if note.startswith('Buyers in order: '))
        names = order.removeprefix('Buyers in order: ').split(', ')
        answer = names[1 if basis['question'] == 'Which buyer was second?' else 0]
        proposal = {'text': answer, 'status': 'needs_review', 'citations': [SOURCE]}
        return {'provider_ref': 'offline-' + str(len(seen)), 'model_id': self.model_id,
                'prompt_version': route.prompt_version, 'proposal': proposal,
                'assessment': validate_proposal(proposal, basis),
                'usage': {'input_tokens': 100, 'output_tokens': 10, 'total_tokens': 110}}

    monkeypatch.setattr(OpenCodeGoModelClient, 'complete', offline_completion)
    pairs = [('Alder', 'Birch'), ('Cedar', 'Willow')]
    threads = [create(client, messages=[{'text': f'Buyers in order: {first}, {second}'}],
                      sources=[{'id': SOURCE, 'label': 'Approved offer fact'}]) for first, second in pairs]
    for question, position in [('Which buyer was second?', 1), ('Which buyer was first?', 0)]:
        for index, thread in enumerate(threads):
            readback = client.get(f"{ROOT}/{thread['id']}", headers=headers())
            assert readback.status_code == 200, readback.text
            result = turn_on_thread(client, readback.json()['data'], text=question)
            assert result.status_code == 200, result.text
            data = result.json()['data']
            assert data['thread']['id'] == thread['id']
            assert [part['text'] for part in data['turn']['parts'] if part['kind'] == 'text'] == [pairs[index][position]], data['turn']
            assert seen[-1]['thread_id'] == thread['id']
            assert seen[-1]['question'] == question
            for name in pairs[1 - index]:
                assert all(name not in item['text'] for item in seen[-1]['history'])
    assert len(seen) == 4
