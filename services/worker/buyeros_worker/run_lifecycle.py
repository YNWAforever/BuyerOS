RUN_STATES = (
    "draft",
    "queued",
    "running",
    "partial",
    "paused_budget",
    "completed",
    "failed",
    "cancel_requested",
    "cancelled",
    "blocked",
)
# Owner decision: only completed/cancelled are terminal. failed, partial and
# paused_budget are retryable and can return to queued.
TERMINAL = {"completed", "cancelled"}
# A capability-blocked run is halting (nothing retries it) but it is not a
# business-terminal outcome, so it is tracked separately from TERMINAL.
BLOCKED = {"blocked"}

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
    ("paused_budget", "retry"): "queued",
    ("paused_budget", "resume"): "running",
    ("cancel_requested", "cancel"): "cancelled",
    ("draft", "capability_block"): "blocked",
    ("queued", "capability_block"): "blocked",
    ("running", "capability_block"): "blocked",
    ("partial", "capability_block"): "blocked",
    ("paused_budget", "capability_block"): "blocked",
    ("cancel_requested", "capability_block"): "blocked",
}


def terminal(state: str) -> bool:
    return state in TERMINAL


def halted(state: str) -> bool:
    """Terminal or capability-blocked: no further transition is applied."""
    return state in TERMINAL or state in BLOCKED


def transition_run(current: str, event: str) -> str:
    if halted(current):
        return current
    return _TRANSITIONS.get((current, event), current)
