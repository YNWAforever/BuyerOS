from buyeros_api.services.policy_service import PURPOSES, effective_decision


def test_unknown_when_no_decision():
    assert effective_decision([], "contact_lookup") == "unknown"


def test_most_restrictive_wins():
    decisions = [
        {"purpose": "contact_lookup", "status": "permitted"},
        {"purpose": "contact_lookup", "status": "blocked"},
    ]
    assert effective_decision(decisions, "contact_lookup") == "blocked"


def test_purposes_are_separate():
    decisions = [{"purpose": "research", "status": "permitted"}]
    assert effective_decision(decisions, "outreach") == "unknown"


def test_requires_review_beats_permitted():
    decisions = [
        {"purpose": "export", "status": "permitted"},
        {"purpose": "export", "status": "requires_review"},
    ]
    assert effective_decision(decisions, "export") == "requires_review"


def test_purpose_registry():
    assert set(PURPOSES) == {"research", "contact_lookup", "export", "outreach"}
