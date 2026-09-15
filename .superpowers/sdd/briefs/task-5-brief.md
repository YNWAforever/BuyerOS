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

### Task 5: Capability-blocked handlers

**Files:**
- Create: `services/worker/buyeros_worker/handlers/__init__.py`
- Create: `services/worker/buyeros_worker/handlers/capability_blocked.py`
- Create: `services/worker/tests/test_capability_blocked.py`

**Interfaces:**
- Produces: `BLOCKED_EVENTS = {"run.discover", "contact.submit", "draft.generate"}`; `blocked(session, context, payload) -> HandlerResult(state="blocked", detail=...)`; handlers registered for each blocked event.
- Consumes: `register`, `HandlerResult` (Task 4).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_capability_blocked.py
from buyeros_worker.handlers.capability_blocked import BLOCKED_EVENTS, blocked
from buyeros_worker.registry import get_handler


def test_blocked_handlers_are_registered():
    for event in BLOCKED_EVENTS:
        assert get_handler(event) is blocked


def test_blocked_result_makes_no_external_call():
    result = blocked(session=None, context=None, payload={})
    assert result.state == "blocked"
    assert "no verified provider" in result.detail.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_capability_blocked.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/handlers/__init__.py
"""Worker handlers."""
```

```python
# services/worker/buyeros_worker/handlers/capability_blocked.py
from ..registry import HandlerResult, register

BLOCKED_EVENTS = frozenset({"run.discover", "contact.submit", "draft.generate"})


def blocked(session, context, payload) -> HandlerResult:
    """Fail closed: no verified provider/model, so make no external call."""
    event_type = (payload or {}).get("event_type", "unknown")
    return HandlerResult(state="blocked", detail=f"{event_type}: no verified provider or model is configured")


for _event in BLOCKED_EVENTS:
    register(_event)(blocked)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_capability_blocked.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/handlers services/worker/tests/test_capability_blocked.py
git commit -m "feat(worker): fail-closed handlers for unverified provider job types"
```

---
