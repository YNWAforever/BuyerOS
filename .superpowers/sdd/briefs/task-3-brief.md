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

### Task 3: Lease and fencing primitives

**Files:**
- Create: `services/worker/buyeros_worker/leases.py`
- Create: `services/worker/tests/test_leases.py`

**Interfaces:**
- Produces: `lease_expiry(now, seconds) -> datetime`; `can_claim(state, expires_at, now) -> bool`; `fence_ok(worker_generation, row_generation) -> bool`.
- Consumes: `WorkerLease` (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# services/worker/tests/test_leases.py
from datetime import datetime, timedelta, timezone

from buyeros_worker.leases import can_claim, fence_ok, lease_expiry

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_free_lease_can_be_claimed():
    assert can_claim("free", None, NOW) is True


def test_unexpired_lease_cannot_be_claimed():
    assert can_claim("held", NOW + timedelta(seconds=30), NOW) is False


def test_expired_lease_can_be_claimed():
    assert can_claim("held", NOW - timedelta(seconds=1), NOW) is True


def test_lease_expiry_adds_seconds():
    assert lease_expiry(NOW, 120) == NOW + timedelta(seconds=120)


def test_fence_rejects_stale_worker():
    assert fence_ok(3, 3) is True
    assert fence_ok(2, 3) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_leases.py -v` (cwd `services/worker`)
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/leases.py
from datetime import datetime, timedelta


def lease_expiry(now: datetime, seconds: int) -> datetime:
    return now + timedelta(seconds=seconds)


def can_claim(state: str, expires_at: datetime | None, now: datetime) -> bool:
    if state == "free" or expires_at is None:
        return True
    return expires_at <= now


def fence_ok(worker_generation: int, row_generation: int) -> bool:
    return worker_generation == row_generation
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_leases.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/leases.py services/worker/tests/test_leases.py
git commit -m "feat(worker): lease expiry and fencing primitives"
```

---
