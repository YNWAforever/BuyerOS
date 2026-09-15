from buyeros_api.services.run_events import apply_event, next_sequence


def test_sequence_is_monotonic():
    assert next_sequence(0) == 1
    assert next_sequence(41) == 42


def test_duplicate_and_out_of_order_events_ignored():
    assert apply_event(applied=5, incoming=5) is False
    assert apply_event(applied=5, incoming=4) is False
    assert apply_event(applied=5, incoming=6) is True
