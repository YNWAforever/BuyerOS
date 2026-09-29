from buyeros_api.services.provider_op import should_hold, submit_outcome, transition


def test_timeout_is_unknown_not_failed():
    assert submit_outcome("timeout") == "unknown"
    assert submit_outcome("error") == "unknown"


def test_unknown_holds_cost_success_releases():
    assert should_hold("unknown") is True
    assert should_hold("submitting") is True
    assert should_hold("succeeded") is False


def test_no_regression_after_terminal_or_unknown():
    assert transition("succeeded", "pending") == "succeeded"
    assert transition("unknown", "accepted") == "unknown"
    assert transition("submitting", "accepted") == "accepted"


def test_unknown_requires_authoritative_event_before_reconciliation():
    import pytest
    from buyeros_api.services.provider_op import reconcile_transition

    assert transition("unknown", "succeeded") == "unknown"
    with pytest.raises(ValueError):
        reconcile_transition("unknown", "succeeded", authoritative_event_id="")
    assert reconcile_transition("unknown", "succeeded",
                                authoritative_event_id="provider-charge-1") == "succeeded"
    assert reconcile_transition("unknown", "pending",
                                authoritative_event_id="provider-pending-1") == "unknown"


def test_cancel_transition_is_only_safe_before_submission():
    assert transition("intent", "cancelled") == "cancelled"
    assert transition("reserved", "cancelled") == "cancelled"
    assert transition("submitting", "cancelled") == "submitting"
    assert should_hold("cancelled") is False
