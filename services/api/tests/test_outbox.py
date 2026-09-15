from buyeros_api.services.outbox_service import build_intent


def test_intent_is_deterministic_and_unique_per_index():
    a = build_intent("run.discover", {"run_id": "r1"}, 0)
    b = build_intent("run.discover", {"run_id": "r1"}, 0)
    c = build_intent("run.discover", {"run_id": "r1"}, 1)
    assert a == b
    assert a != c
    assert a.startswith("job:")


def test_intent_payload_order_independent():
    assert build_intent("t", {"a": 1, "b": 2}, 0) == build_intent("t", {"b": 2, "a": 1}, 0)
