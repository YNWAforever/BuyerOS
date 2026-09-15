RUN_STATES = ("draft", "queued", "running", "partial", "paused_budget", "completed", "failed", "cancel_requested", "cancelled")
TERMINAL = {"completed", "failed", "cancelled"}

_TRANSITIONS = {
    ("draft", "enqueue"): "queued",
    ("queued", "start"): "running",
    ("running", "complete"): "completed",
    ("running", "partial"): "partial",
    ("running", "pause_budget"): "paused_budget",
    ("running", "fail"): "failed",
    ("running", "cancel"): "cancel_requested",
    ("partial", "retry"): "queued",
    ("failed", "retry"): "queued",
    ("cancel_requested", "cancel"): "cancelled",
}


def terminal(state: str) -> bool:
    return state in TERMINAL


def transition_run(current: str, event: str) -> str:
    if terminal(current):
        return current
    return _TRANSITIONS.get((current, event), current)
