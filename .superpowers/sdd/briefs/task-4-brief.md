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

### Task 4: Handler registry and result types

**Files:**
- Create: `services/worker/buyeros_worker/registry.py`
- Create: `services/worker/tests/test_registry.py`

**Interfaces:**
- Produces: `HandlerResult(state: str, detail: str)`; `register(event_type: str)` decorator; `get_handler(event_type: str)` raising `UnknownHandler`; `HANDLERS: dict`.
- Consumes: nothing external.

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_registry.py
import pytest

from buyeros_worker.registry import HANDLERS, HandlerResult, UnknownHandler, get_handler, register


def test_unknown_handler_raises():
    with pytest.raises(UnknownHandler):
        get_handler("does.not.exist")


def test_registration_makes_handler_available():
    @register("test.event")
    def handler(session, context, payload):
        return HandlerResult(state="done", detail="ok")

    assert get_handler("test.event") is handler
    assert "test.event" in HANDLERS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/registry.py
from collections.abc import Callable
from dataclasses import dataclass


class UnknownHandler(Exception):
    pass


@dataclass(frozen=True)
class HandlerResult:
    state: str          # "done" | "blocked" | "retry"
    detail: str = ""


HANDLERS: dict[str, Callable] = {}


def register(event_type: str):
    def decorator(func: Callable) -> Callable:
        HANDLERS[event_type] = func
        return func

    return decorator


def get_handler(event_type: str) -> Callable:
    try:
        return HANDLERS[event_type]
    except KeyError as exc:  # pragma: no cover - exercised via test
        raise UnknownHandler(event_type) from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/registry.py services/worker/tests/test_registry.py
git commit -m "feat(worker): handler registry"
```

---
