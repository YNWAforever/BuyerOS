from buyeros_api.services.usage import outcome_chain, safe_ratio


def test_zero_denominator_is_none():
    assert safe_ratio("2.400000", 0) is None
    assert safe_ratio("2.400000", 2) == "1.200000"


def test_ratio_rounds_to_six_places():
    assert safe_ratio("1.000000", 3) == "0.333333"


def test_outcome_chain_keeps_latest_non_superseded():
    events = [
        {"buyer_id": "b1", "stage": "meeting", "superseded": False},
        {"buyer_id": "b1", "stage": "replied", "superseded": True},
    ]
    assert outcome_chain(events)["b1"] == "meeting"


def test_outcome_chain_handles_multiple_buyers():
    events = [
        {"buyer_id": "b1", "stage": "replied", "superseded": False},
        {"buyer_id": "b2", "stage": "meeting", "superseded": False},
    ]
    assert outcome_chain(events) == {"b1": "replied", "b2": "meeting"}
