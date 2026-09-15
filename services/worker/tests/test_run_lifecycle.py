from buyeros_worker.run_lifecycle import terminal, transition_run


def test_valid_progressions():
    assert transition_run("queued", "start") == "running"
    assert transition_run("running", "complete") == "completed"
    assert transition_run("running", "cancel") == "cancel_requested"


def test_terminal_states_do_not_regress():
    assert transition_run("completed", "start") == "completed"
    assert transition_run("cancelled", "start") == "cancelled"


def test_cancel_requested_is_not_terminal():
    assert terminal("cancel_requested") is False
    assert terminal("cancelled") is True
    assert terminal("completed") is True


def test_unknown_event_is_ignored():
    assert transition_run("running", "bogus") == "running"


def test_failed_and_paused_budget_are_retryable():
    assert transition_run("failed", "retry") == "queued"
    assert transition_run("partial", "retry") == "queued"
    assert transition_run("paused_budget", "retry") == "queued"
    assert transition_run("paused_budget", "resume") == "running"


def test_only_completed_and_cancelled_are_terminal():
    assert terminal("completed") is True
    assert terminal("cancelled") is True
    assert terminal("failed") is False
    assert terminal("partial") is False
    assert terminal("paused_budget") is False


def test_terminal_states_never_regress_even_on_retry():
    assert transition_run("completed", "retry") == "completed"
    assert transition_run("cancelled", "retry") == "cancelled"


def test_remaining_edges():
    assert transition_run("draft", "enqueue") == "queued"
    assert transition_run("running", "fail") == "failed"
    assert transition_run("running", "partial") == "partial"
    assert transition_run("running", "pause_budget") == "paused_budget"
    assert transition_run("cancel_requested", "cancel") == "cancelled"
