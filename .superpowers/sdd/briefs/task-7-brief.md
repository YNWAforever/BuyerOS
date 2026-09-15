# P8 Worker and Dispatcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Build is NOT authorized by this document**; execution requires explicit approval under the recorded dependency waiver.

**Goal:** Turn committed outbox intents into durable worker work via a Celery/Valkey dispatcher and worker with DB leases, fencing, a recovery sweeper, run/event emission, and a handler registry containing one real handler (`fetch.evidence`).

**Architecture:** `services/worker/` (`buyeros_worker`) depends on `buyeros_api` by local path so there is one domain package. The dispatcher claims `outbox_events` rows with a DB lease and publishes deterministic intent IDs to Celery/Valkey; the worker resolves the intent, re-derives tenant context, executes a registered handler, and commits state + `run_events` atomically before acking. A sweeper re-enqueues expired leases; fencing generations reject stale writers.

**Tech Stack:** Python 3.12+ + Celery 5 + Valkey/Redis, SQLAlchemy 2 + Alembic (in `buyeros_api`), PostgreSQL 16, uv.

## Global Constraints

- Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; audited source imported at `b804ba8d` tree `b4c6b538…`).
- Plan-only artifact. No commits to remote, pushes, deploys, cloud resources, real migrations on real data, paid calls, mailboxes, or sends.
- One domain package: worker must **not** duplicate models, authorization, budget or policy rules; it imports `buyeros_api`.
- No provider is verified: `run.discover`, `contact.submit`, `draft.generate` are **fail-closed**. Only `fetch.evidence` executes external reads.
- Every unexecuted check is **NOT RUN**.

**File ownership:** `services/worker/**` (new), plus these `buyeros_api` changes: `db/worker.py` (new), `db/outbox.py` (columns), `alembic/versions/0006_worker_leases.py` (new), and `tests/**`. Worker tests live in `services/worker/tests/`.

---

### Task 7: Run lifecycle transitions and event emission

**Files:**
- Create: `services/worker/buyeros_worker/run_lifecycle.py`
- Create: `services/worker/tests/test_run_lifecycle.py`

**Interfaces:**
- Produces: `RUN_STATES`; `transition_run(current, event) -> str` (no regression); `terminal(state) -> bool`.
- Consumes: `buyeros_api.services.run_events.next_sequence`/`apply_event` (P3).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_run_lifecycle.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_run_lifecycle.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/run_lifecycle.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_run_lifecycle.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/run_lifecycle.py services/worker/tests/test_run_lifecycle.py
git commit -m "feat(worker): run lifecycle transition table"
```

---
