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
