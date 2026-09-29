from buyeros_api.services.policy_service import PURPOSES, effective_decision


def test_unknown_when_no_decision():
    assert effective_decision([], "contact_research") == "unknown"


def test_most_restrictive_wins():
    decisions = [
        {"purpose": "contact_research", "status": "permitted"},
        {"purpose": "contact_research", "status": "blocked"},
    ]
    assert effective_decision(decisions, "contact_research") == "blocked"


def test_purposes_are_separate():
    decisions = [{"purpose": "account_research", "status": "permitted"}]
    assert effective_decision(decisions, "outreach") == "unknown"


def test_requires_review_beats_permitted():
    decisions = [
        {"purpose": "export_contacts", "status": "permitted"},
        {"purpose": "export_contacts", "status": "requires_review"},
    ]
    assert effective_decision(decisions, "export_contacts") == "requires_review"


def test_purpose_registry():
    assert set(PURPOSES) == {"account_research", "contact_research", "draft_preparation", "outreach", "export_accounts", "export_contacts", "offer_research"}


def test_offer_research_permission_does_not_grant_account_research():
    decisions = [{"purpose": "offer_research", "status": "permitted"}]
    assert effective_decision(decisions, "account_research") == "unknown"
