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

### Task 8: DB dispatcher and sweeper

**Files:**
- Create: `services/worker/buyeros_worker/dispatcher.py`
- Create: `services/worker/tests/test_dispatcher.py`

**Interfaces:**
- Produces: `async def claim_outbox_rows(session, owner, limit, now) -> list[dict]` (atomic conditional update, increments `fencing_generation`); `async def mark_dispatched(session, ids, now)`; `async def sweep_expired(session, now) -> list[str]`; `async def dispatch_once(session, publish, owner, now, limit) -> list[str]`.
- Consumes: `can_claim`, `lease_expiry` (Task 3); `OutboxEvent` (Task 2).

- [ ] **Step 1: Write the failing test** (pure selection logic, no DB)

```python
# services/worker/tests/test_dispatcher.py
from datetime import datetime, timedelta, timezone

from buyeros_worker.dispatcher import select_ready

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_only_ready_rows_are_selected():
    rows = [
        {"id": 1, "state": "ready", "lease_expires_at": None},
        {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
        {"id": 3, "state": "ready", "lease_expires_at": NOW - timedelta(seconds=1)},
    ]
    assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]


def test_batch_is_bounded():
    rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
    assert len(select_ready(rows, NOW, limit=5)) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dispatcher.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# services/worker/buyeros_worker/dispatcher.py
from datetime import datetime
from typing import Callable

from .leases import can_claim, lease_expiry


def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
    selected = [r for r in rows if can_claim(r.get("state", "free"), r.get("lease_expires_at"), now)]
    return selected[:limit]


async def claim_outbox_rows(session, owner: str, limit: int, now: datetime) -> list[dict]:
    """Claim ready outbox rows atomically, bumping the fencing generation."""
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            UPDATE outbox_events
               SET lease_owner = :owner,
                   lease_expires_at = :expires,
                   fencing_generation = fencing_generation + 1,
                   state = 'dispatched'
             WHERE id IN (
                   SELECT id FROM outbox_events
                    WHERE state = 'ready'
                       OR (state = 'dispatched' AND lease_expires_at <= :now)
                    ORDER BY created_at
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
             )
         RETURNING id, intent_key, event_type, payload, fencing_generation
            """
        ),
        {"owner": owner, "expires": lease_expiry(now, 120), "now": now, "limit": limit},
    )
    return [dict(r._mapping) for r in result]


async def mark_dispatched(session, ids: list[int], now: datetime) -> None:
    from sqlalchemy import text

    if not ids:
        return
    await session.execute(text("UPDATE outbox_events SET dispatched_at = :now WHERE id = ANY(:ids)"), {"now": now, "ids": ids})


async def sweep_expired(session, now: datetime) -> list[int]:
    """Return ids of dispatched rows whose lease expired (re-claimable)."""
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT id FROM outbox_events WHERE state = 'dispatched' AND lease_expires_at <= :now"),
        {"now": now},
    )
    return [r[0] for r in result]


async def dispatch_once(session, publish: Callable, owner: str, now: datetime, limit: int) -> list[str]:
    from buyeros_api.services.outbox_service import build_intent

    claimed = await claim_outbox_rows(session, owner, limit, now)
    published: list[str] = []
    for row in claimed:
        intent = build_intent(row["event_type"], row["payload"], 0)
        publish(intent, row)
        published.append(intent)
    await mark_dispatched(session, [row["id"] for row in claimed], now)
    return published
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dispatcher.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add services/worker/buyeros_worker/dispatcher.py services/worker/tests/test_dispatcher.py
git commit -m "feat(worker): outbox dispatcher with lease claims and sweeper"
```

---
