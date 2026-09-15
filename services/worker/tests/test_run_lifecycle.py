from buyeros_worker.run_lifecycle import terminal, transition_run


def test_valid_progressions():
    assert transition_run("queued", "start") == "running"
    assert transition_run("running", "complete") == "completed"
    assert transition_run("running", "cancel") == "cancel_requested"


def test_terminal_states_do_not_regress():
    assert transition_run("completed", "start") == "completed"
    assert transition_run("failed", "start") == "failed"


def test_cancel_requested_is_not_terminal():
    assert terminal("cancel_requested") is False
    assert terminal("cancelled") is True
    assert terminal("completed") is True


def test_unknown_event_is_ignored():
    assert transition_run("running", "bogus") == "running"
