"""Guard: the turn routes must not read fields that ``TurnPayload`` does not have.

`TurnPayload` is ``{id, status, parts, notices}``; the thread id lives on the
loaded thread row. Reading ``turn.thread_id`` raises ``AttributeError`` inside the
route and surfaces as a 500 on every turn response, which is exactly what the
PostgreSQL suite caught. This offline guard keeps the mistake out of the routes
without needing a database.
"""
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / 'buyeros_api' / 'api' / 'routes' / 'conversation_turns.py'


def test_turn_routes_use_the_loaded_thread_row_for_thread_identity():
    source = ROUTES.read_text(encoding='utf-8')
    assert 'turn.thread_id' not in source, (
        'TurnPayload has no thread_id; use the loaded thread row (`thread.id`)')
    # The decoration must still be wired with a real thread id for every turn route.
    assert source.count('decorate_turn_payload(') >= 4
    assert source.count('thread.id') >= 4


def test_turn_payload_has_no_thread_identity_field():
    from buyeros_api.sales.turn_contracts import TurnPayload
    assert 'thread_id' not in TurnPayload.model_fields, (
        'if TurnPayload gains thread_id, update the route guard and contract together')
