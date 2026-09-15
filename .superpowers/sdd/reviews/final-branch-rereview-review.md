# final-branch-rereview review package
## commits
```
b4af79a docs: align p8 plan with implemented worker execution and dispatcher
8c62025 test(worker): db-backed fencing, idempotency, sweeper and blocked-handler tests
24933d3 fix(api): settable tenant context and complete model registration
a0950e9 feat(worker): RLS-aware dispatcher, re-enqueueing sweeper and CLI entrypoints
05979d7 feat(worker): enforce fencing and resolve intents from the database
443c970 feat(worker): blocked run state and atomic run-event emission
68bb1f9 feat(db): terminal outbox states, claim index and dispatcher workspace read
c715715 test(worker): restore broker url and poll valkey readiness
600e755 test(worker): disposable valkey broker integration check
ac4abb6 fix(worker): reuse engine, retry on retry state, ack unknown handlers
24c615b feat(worker): celery task entrypoint with commit-before-ack
32e4af0 fix(worker): dispatch using the persisted outbox intent key
d0ad91e feat(worker): outbox dispatcher with lease claims and sweeper
77df73c fix(worker): make failed/partial/paused_budget runs retryable
bfd2c81 feat(worker): run lifecycle transition table
5b5d384 fix(worker): block IPv6-literal and empty-host fetch URLs
5d2d0be fix(worker): fail closed on non-string fetch payload fields
ca3a23d fix(worker): make fetch.evidence payload handling fail closed
ba2d48d fix(worker): fail closed on malformed fetch URLs
cf1f57b feat(worker): SSRF-safe fetch.evidence validation handler
c1c6821 feat(worker): fail-closed handlers for unverified provider job types
6c70b28 feat(worker): handler registry
ce5f850 feat(worker): lease expiry and fencing primitives
c01ef8e feat(db): worker_leases table and outbox dispatch columns
6b92180 fix(build): make buyeros-api installable so the worker path dependency resolves
4264b03 feat(worker): bootstrap buyeros_worker package and celery app
1d0df22 chore: P8 build approval record and progress ledger
```
## stat (lockfiles excluded)
```
 .superpowers/sdd/progress.md                       |   7 +
 docs/buyeros/SHA256SUMS.txt                        |   3 +-
 .../decisions/BUILD_APPROVAL_RECORD.P8-worker.md   |  29 ++
 ...26-09-15-p8-worker-dispatcher-implementation.md | 532 +++++++++++++++++----
 .../api/alembic/versions/0006_worker_leases.py     |  56 +++
 .../alembic/versions/0007_outbox_terminal_state.py |  44 ++
 services/api/buyeros_api/db/__init__.py            |  36 +-
 services/api/buyeros_api/db/outbox.py              |  20 +-
 services/api/buyeros_api/db/session.py             |  14 +-
 services/api/buyeros_api/db/worker.py              |  29 ++
 services/api/pyproject.toml                        |   7 +
 services/api/tests/test_outbox_terminal_state.py   |  46 ++
 services/api/tests/test_tenant_context.py          |  11 +
 services/api/tests/test_tenant_isolation_db.py     |   1 +
 services/api/tests/test_worker_leases_model.py     |  32 ++
 services/worker/buyeros_worker/__init__.py         |   2 +
 services/worker/buyeros_worker/app.py              |  31 ++
 services/worker/buyeros_worker/cli.py              |  59 +++
 services/worker/buyeros_worker/config.py           |  18 +
 services/worker/buyeros_worker/dispatcher.py       | 149 ++++++
 services/worker/buyeros_worker/engine.py           |  52 ++
 .../worker/buyeros_worker/handlers/__init__.py     |   2 +
 .../buyeros_worker/handlers/capability_blocked.py  |  36 ++
 .../buyeros_worker/handlers/fetch_evidence.py      |  66 +++
 services/worker/buyeros_worker/leases.py           |  15 +
 services/worker/buyeros_worker/registry.py         |  30 ++
 services/worker/buyeros_worker/run_emitter.py      |  57 +++
 services/worker/buyeros_worker/run_lifecycle.py    |  54 +++
 services/worker/buyeros_worker/tasks.py            | 163 +++++++
 services/worker/pyproject.toml                     |  36 ++
 services/worker/tests/__init__.py                  |   0
 services/worker/tests/conftest.py                  | 188 ++++++++
 services/worker/tests/test_app.py                  |  31 ++
 services/worker/tests/test_capability_blocked.py   |  26 +
 services/worker/tests/test_cli.py                  |  35 ++
 services/worker/tests/test_dispatcher.py           | 103 ++++
 services/worker/tests/test_fetch_evidence.py       |  95 ++++
 services/worker/tests/test_leases.py               |  26 +
 services/worker/tests/test_registry.py             |  17 +
 services/worker/tests/test_run_emitter.py          |  18 +
 services/worker/tests/test_run_lifecycle.py        |  76 +++
 services/worker/tests/test_tasks.py                | 199 ++++++++
 services/worker/tests/test_valkey_integration.py   |  56 +++
 services/worker/tests/test_worker_integrity_db.py  | 170 +++++++
 44 files changed, 2568 insertions(+), 109 deletions(-)
```
## diff (lockfiles excluded)
```diff
diff --git a/.superpowers/sdd/progress.md b/.superpowers/sdd/progress.md
new file mode 100644
index 0000000..c322aa0
--- /dev/null
+++ b/.superpowers/sdd/progress.md
@@ -0,0 +1,7 @@
+# P8 worker/dispatcher - progress ledger
+
+Plan: docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md
+Branch: p8-worker-dispatcher
+Base commit: 36e67d5
+
+
diff --git a/docs/buyeros/SHA256SUMS.txt b/docs/buyeros/SHA256SUMS.txt
index d8180f7..48790d7 100644
--- a/docs/buyeros/SHA256SUMS.txt
+++ b/docs/buyeros/SHA256SUMS.txt
@@ -61,11 +61,12 @@ a4030ea5916ef050e471e3c87dcec8886515dba07c95c5709336914ec9ca1b79  plans/2026-09-
 fff7d7c34a37f35e7dfa7b9156592acc4ddcec857e3cd5ab266050c35d21753f  plans/2026-09-15-p4-contact-guardrails-implementation.md
 3371b162214eb358f521b86556b38eed24731a681ef6d3ec20cf5f3b4a6bb5fd  plans/2026-09-15-p5-draft-approval-export-implementation.md
 4937b367fadc1b327f0c35412dd685532d62543aeb08e51c1b44f55677a91de9  plans/2026-09-15-p6-hardening-pilot-implementation.md
 66c47ab3a60ccb7aecc9d269073e57c1027e665af654b4fdd8d412bcadee16f5  plans/2026-09-15-p7-delivery-design-implementation.md
 9fe83b53f163af200b07f45a390f86d9cfe755dba215a6c4e74bfc62bb212524  HANDOFF_INDEX.md
 3aa5d1f31bdf8e6bdb13facf5c48e3076e84dab2e355372917207e16c88322ce  PROGRESS.md
 44295f9fe1bbe047d5c37a267093b72065206f89efd8c69a44dbff1865482441  decisions/BUILD_APPROVAL_RECORD.template.md
 15f0824dff410942a097aee8b125112bc1a8c4a76360e301b038eab6e899c00d  verification/SOURCE_IMPORT_CHECKLIST.md
 b8d23868093d42452b222e9f3420cee7a331e37f316b86db49924486da6b9256  decisions/BUILD_APPROVAL_RECORD.BO-005.md
 de3c29a0259d4e6fc51fe9d158a49da9ffacd0608b503283bb38e0ce7eedf9e6  specs/2026-09-15-p8-worker-dispatcher-design.md
-972e2b28cf3a95cc0a4a32c42c8976f4fedb49b4cfe3b6f7c2417f4c015be1ba  plans/2026-09-15-p8-worker-dispatcher-implementation.md
+2bfb1c9232ca0a293a68675d3fb13065798eca592f9eb717a01a2eb78f9bdf27  plans/2026-09-15-p8-worker-dispatcher-implementation.md
+8c060ab8973e0a9da62f807edf29d03684a1d2df736243a715b867dad776311a  decisions/BUILD_APPROVAL_RECORD.P8-worker.md
diff --git a/docs/buyeros/decisions/BUILD_APPROVAL_RECORD.P8-worker.md b/docs/buyeros/decisions/BUILD_APPROVAL_RECORD.P8-worker.md
new file mode 100644
index 0000000..752eceb
--- /dev/null
+++ b/docs/buyeros/decisions/BUILD_APPROVAL_RECORD.P8-worker.md
@@ -0,0 +1,29 @@
+# Build approval record — P8 worker/dispatcher (dependency waiver)
+
+**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-15 (Hong Kong).
+
+## Approval fields
+
+| Field | Value |
+|---|---|
+| Phase/task | **P8 worker + dispatcher** (covers the pending BO-011 execution layer) |
+| Scope | Outbox dispatcher, Celery/Valkey worker, DB leases + fencing, sweeper/recovery, `worker_leases` migration, handler registry, `fetch.evidence` (validation), fail-closed handlers for `run.discover`/`contact.submit`/`draft.generate`, run/event lifecycle, tests |
+| Spec | `docs/buyeros/specs/2026-09-15-p8-worker-dispatcher-design.md` |
+| Plan | `docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md` |
+| Source baseline | `YNWAforever/BuyerOS` `main`; audited source `b804ba8d1514a1049b7202c861278dd72c473a75` (tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`) |
+| Current HEAD at approval | recorded in `docs/buyeros/PROGRESS.md` at execution time |
+| Allowed files | create `services/worker/**`; modify `services/api/buyeros_api/db/{outbox,worker}.py`; create `services/api/alembic/versions/0006_worker_leases.py`; add `services/api/tests/**` and `services/worker/tests/**` |
+| Dependencies with evidence | **BO-003/BO-004/BO-011 NOT complete** — see waiver |
+| Approver | Owner (session authorization, execution mode = subagent-driven) |
+| Environment/spend | none. Local disposable PostgreSQL and (optionally) a local `valkey/valkey:8` container only |
+| Explicitly excluded | remote commits/pushes, deployment, cloud resources, real-data migrations, paid provider calls, contact purchase, mailbox connections, sends, AGENTS.md/OpenCode config changes |
+
+## Dependency waiver (explicit)
+
+The owner authorized P8 Build with an explicit waiver of `depends_on` prerequisites (BO-003 contract freeze, BO-004 bearer identity, BO-011 outbox/task completion). Rationale: the dispatch/execution layer is independent of auth and the HTTP contract, and it builds directly on the P2–P5 tables already implemented and tested. Consequences accepted: later auth/contract changes may require rework; no provider is verified, so discover/contact/draft handlers remain fail-closed.
+
+This waiver does **not** mark BO-003, BO-004, or BO-011 complete, and does not authorize any other phase.
+
+## Sign-off (owner)
+
+> I approve implementation of the P8 worker/dispatcher phase against the imported source baseline, under the dependency waiver and exclusions above, executed subagent-by-task with review between tasks, and with no remote commits/pushes, deployment, real-data migration, provider, or delivery authorization.
diff --git a/docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md b/docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md
index 8041fcd..e60e35f 100644
--- a/docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md
+++ b/docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md
@@ -699,42 +699,57 @@ Expected: PASS (6 passed).
 git add services/worker/buyeros_worker/handlers/fetch_evidence.py services/worker/tests/test_fetch_evidence.py
 git commit -m "feat(worker): SSRF-safe fetch.evidence validation handler"
 ```
 
 ---
 
 ### Task 7: Run lifecycle transitions and event emission
 
 **Files:**
 - Create: `services/worker/buyeros_worker/run_lifecycle.py`
+- Create: `services/worker/buyeros_worker/run_emitter.py`
 - Create: `services/worker/tests/test_run_lifecycle.py`
+- Create: `services/worker/tests/test_run_emitter.py`
 
 **Interfaces:**
-- Produces: `RUN_STATES`; `transition_run(current, event) -> str` (no regression); `terminal(state) -> bool`.
-- Consumes: `buyeros_api.services.run_events.next_sequence`/`apply_event` (P3).
+- Produces: `RUN_STATES`; `TERMINAL = {"completed", "cancelled"}` (owner decision — `failed`, `partial` and `paused_budget` stay retryable); `BLOCKED = {"blocked"}`; `transition_run(current, event) -> str` (no regression from a terminal or blocked state); `terminal(state) -> bool`; `halted(state) -> bool`; `async emit_run_event(session, run_id, event_type, *, transition=None, payload=None) -> int` (status update + one `run_events` row in the caller's transaction).
+- Consumes: `buyeros_api.services.run_events.next_sequence`/`apply_event` (P3); `buyeros_api.db.runs.SearchRun`/`RunEvent`.
 
 - [ ] **Step 1: Write the failing test**
 
 ```python
 # services/worker/tests/test_run_lifecycle.py
-from buyeros_worker.run_lifecycle import terminal, transition_run
+from buyeros_worker.run_lifecycle import halted, terminal, transition_run
 
 
 def test_valid_progressions():
     assert transition_run("queued", "start") == "running"
     assert transition_run("running", "complete") == "completed"
     assert transition_run("running", "cancel") == "cancel_requested"
 
 
 def test_terminal_states_do_not_regress():
     assert transition_run("completed", "start") == "completed"
-    assert transition_run("failed", "start") == "failed"
+    assert transition_run("cancelled", "start") == "cancelled"
+
+
+def test_failed_and_paused_budget_are_retryable():
+    assert transition_run("failed", "retry") == "queued"
+    assert transition_run("partial", "retry") == "queued"
+    assert transition_run("paused_budget", "retry") == "queued"
+
+
+def test_capability_blocked_runs_halt():
+    assert transition_run("running", "capability_block") == "blocked"
+    assert transition_run("blocked", "retry") == "blocked"
+    assert halted("blocked") is True
+    assert terminal("blocked") is False
 
 
 def test_cancel_requested_is_not_terminal():
     assert terminal("cancel_requested") is False
     assert terminal("cancelled") is True
     assert terminal("completed") is True
 
 
 def test_unknown_event_is_ignored():
     assert transition_run("running", "bogus") == "running"
@@ -742,306 +757,623 @@ def test_unknown_event_is_ignored():
 
 - [ ] **Step 2: Run test to verify it fails**
 
 Run: `uv run pytest tests/test_run_lifecycle.py -v`
 Expected: FAIL — `ModuleNotFoundError`.
 
 - [ ] **Step 3: Write minimal implementation**
 
 ```python
 # services/worker/buyeros_worker/run_lifecycle.py
-RUN_STATES = ("draft", "queued", "running", "partial", "paused_budget", "completed", "failed", "cancel_requested", "cancelled")
-TERMINAL = {"completed", "failed", "cancelled"}
+RUN_STATES = ("draft", "queued", "running", "partial", "paused_budget", "completed", "failed", "cancel_requested", "cancelled", "blocked")
+# Owner decision: only completed/cancelled are terminal. failed, partial and
+# paused_budget are retryable and can return to queued.
+TERMINAL = {"completed", "cancelled"}
+# A capability-blocked run is halting (nothing retries it) but not a
+# business-terminal outcome, so it is tracked separately from TERMINAL.
+BLOCKED = {"blocked"}
 
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
+    ("paused_budget", "retry"): "queued",
+    ("paused_budget", "resume"): "running",
     ("cancel_requested", "cancel"): "cancelled",
+    ("draft", "capability_block"): "blocked",
+    ("queued", "capability_block"): "blocked",
+    ("running", "capability_block"): "blocked",
+    ("partial", "capability_block"): "blocked",
+    ("paused_budget", "capability_block"): "blocked",
+    ("cancel_requested", "capability_block"): "blocked",
 }
 
 
 def terminal(state: str) -> bool:
     return state in TERMINAL
 
 
+def halted(state: str) -> bool:
+    """Terminal or capability-blocked: no further transition is applied."""
+    return state in TERMINAL or state in BLOCKED
+
+
 def transition_run(current: str, event: str) -> str:
-    if terminal(current):
+    if halted(current):
         return current
     return _TRANSITIONS.get((current, event), current)
 ```
 
+```python
+# services/worker/buyeros_worker/run_emitter.py
+import uuid
+
+from sqlalchemy import func, select
+
+from buyeros_api.db.runs import RunEvent, SearchRun
+from buyeros_api.services.run_events import apply_event, next_sequence
+
+from .run_lifecycle import transition_run
+
+
+async def emit_run_event(session, run_id, event_type: str, *, transition: str | None = None, payload: dict | None = None) -> int:
+    """Advance the run (if ``transition``) and append exactly one event.
+
+    Runs on the caller's tenant transaction, so the status update and the
+    ``run_events`` insert commit with the work or roll back with it. Returns the
+    sequence, or 0 when there is nothing to do. Never makes an external call.
+    """
+    if session is None or run_id is None:
+        return 0
+    run_key = run_id if isinstance(run_id, uuid.UUID) else uuid.UUID(str(run_id))
+    result = await session.execute(select(SearchRun).where(SearchRun.id == run_key).with_for_update())
+    run = result.scalar_one_or_none()
+    if run is None:
+        return 0
+    last = (await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(RunEvent.run_id == run_key))).scalar_one()
+    sequence = next_sequence(int(last))
+    if not apply_event(int(last), sequence):
+        return 0
+    if transition is not None:
+        new_status = transition_run(run.status, transition)
+        if new_status != run.status:
+            run.status = new_status
+    session.add(RunEvent(workspace_id=run.workspace_id, run_id=run_key, sequence=sequence, event_type=event_type, payload=payload or {}))
+    return sequence
+```
+
+
 - [ ] **Step 4: Run test to verify it passes**
 
 Run: `uv run pytest tests/test_run_lifecycle.py -v`
 Expected: PASS (4 passed).
 
 - [ ] **Step 5: Commit**
 
 ```bash
 git add services/worker/buyeros_worker/run_lifecycle.py services/worker/tests/test_run_lifecycle.py
 git commit -m "feat(worker): run lifecycle transition table"
 ```
 
 ---
 
 ### Task 8: DB dispatcher and sweeper
 
 **Files:**
 - Create: `services/worker/buyeros_worker/dispatcher.py`
-- Create: `services/worker/buyeros_worker/store.py`
 - Create: `services/worker/tests/test_dispatcher.py`
 
 **Interfaces:**
-- Produces: `async def claim_outbox_rows(session, owner, limit, now) -> list[dict]` (atomic conditional update, increments `fencing_generation`); `async def mark_dispatched(session, ids, now)`; `async def sweep_expired(session, now) -> list[str]`; `async def dispatch_once(session, publish, owner, now, limit) -> list[str]`.
-- Consumes: `can_claim`, `lease_expiry` (Task 3); `OutboxEvent` (Task 2).
+- Produces: `claimable(state, lease_expires_at, now) -> bool`; `select_ready(rows, now, limit) -> list[dict]`; `async def list_workspace_ids(session) -> list`; `async def claim_outbox_rows(session, owner, limit, now, lease_seconds, *, expired_only=False) -> list[dict]` (atomic conditional update, increments `fencing_generation`, never re-claims terminal rows); `async def release_claim(session, intent_key)`; `async def dispatch_once(engine, publish, owner, now, limit, lease_seconds) -> list[str]`; `async def sweep_once(engine, publish, owner, now, limit, lease_seconds) -> list[str]` (re-enqueues expired in-progress intents).
+- Consumes: `lease_expiry` (Task 3); `OutboxEvent`/`TERMINAL_STATES` (Task 2); `buyeros_api.db.session.tenant_session`, `Workspace`.
+- **RLS decision:** the dispatcher cannot read all tenants' `outbox_events`, so it enumerates tenants from `workspaces` (non-RLS tenant root, read grant added by migration `0007`) and sets the transaction-local tenant context per workspace via `tenant_session` before claiming.
+- **Ordering:** the claim (lease + `fencing_generation` bump + `state='dispatched'`) commits before the publish, so a crash between them is recovered by the sweeper's lease expiry; a publish failure calls `release_claim` to put the row straight back to `ready`. The published message carries only opaque ids.
 
 - [ ] **Step 1: Write the failing test** (pure selection logic, no DB)
 
 ```python
 # services/worker/tests/test_dispatcher.py
+import asyncio
+from contextlib import asynccontextmanager
 from datetime import datetime, timedelta, timezone
 
-from buyeros_worker.dispatcher import select_ready
+from buyeros_worker.dispatcher import claimable, dispatch_once, select_ready
 
 NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
 
 
-def test_only_ready_rows_are_selected():
+def test_only_ready_and_expired_rows_are_selected():
     rows = [
         {"id": 1, "state": "ready", "lease_expires_at": None},
         {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
-        {"id": 3, "state": "ready", "lease_expires_at": NOW - timedelta(seconds=1)},
+        {"id": 3, "state": "dispatched", "lease_expires_at": NOW - timedelta(seconds=1)},
+        {"id": 4, "state": "done", "lease_expires_at": None},
+        {"id": 5, "state": "failed", "lease_expires_at": NOW - timedelta(days=1)},
     ]
     assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]
 
 
 def test_batch_is_bounded():
     rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
     assert len(select_ready(rows, NOW, limit=5)) == 5
+
+
+def test_terminal_rows_are_never_claimable():
+    assert claimable("done", NOW - timedelta(days=1), NOW) is False
+    assert claimable("failed", None, NOW) is False
+
+
+def test_dispatch_once_publishes_only_opaque_ids(monkeypatch):
+    """The broker message never carries the instruction (event type/payload)."""
+
+    async def fake_workspace_ids(engine):
+        return ["ws-1"]
+
+    @asynccontextmanager
+    async def fake_tenant_session(engine, workspace_id):
+        yield object()
+
+    async def fake_claim(session, owner, limit, now, lease_seconds, *, expired_only=False):
+        return [{"id": 1, "workspace_id": "ws-1", "intent_key": "job:aaa",
+                 "event_type": "fetch.evidence", "payload": {"url": "https://e.com"}, "fencing_generation": 7}]
+
+    monkeypatch.setattr("buyeros_worker.dispatcher._workspace_ids", fake_workspace_ids)
+    monkeypatch.setattr("buyeros_worker.dispatcher.tenant_session", fake_tenant_session)
+    monkeypatch.setattr("buyeros_worker.dispatcher.claim_outbox_rows", fake_claim)
+    messages = []
+    out = asyncio.run(dispatch_once(object(), messages.append, "owner", NOW, 10, 120))
+    assert out == ["job:aaa"]
+    assert messages == [{"intent_key": "job:aaa", "workspace_id": "ws-1", "generation": 7}]
 ```
 
 - [ ] **Step 2: Run test to verify it fails**
 
 Run: `uv run pytest tests/test_dispatcher.py -v`
 Expected: FAIL — `ModuleNotFoundError`.
 
 - [ ] **Step 3: Write minimal implementation**
 
 ```python
 # services/worker/buyeros_worker/dispatcher.py
+from collections.abc import Callable
 from datetime import datetime
-from typing import Callable
 
-from .leases import can_claim, lease_expiry
+from sqlalchemy import text
+from sqlalchemy.ext.asyncio import async_sessionmaker
+
+from buyeros_api.db.models import Workspace
+from buyeros_api.db.outbox import DISPATCHED_STATE, READY_STATE
+from buyeros_api.db.session import tenant_session
+
+from .leases import lease_expiry
+
+_CLAIM_COLUMNS = "id, workspace_id, intent_key, event_type, payload, fencing_generation"
+
+# Terminal rows (done/failed) are deliberately absent: the predicate is an
+# allow-list, so a terminal row can never be re-claimed or re-run.
+_CLAIMABLE_PREDICATE = "state = 'ready' OR (state = 'dispatched' AND lease_expires_at <= :now)"
+_EXPIRED_PREDICATE = "state = 'dispatched' AND lease_expires_at <= :now"
+
+
+def claimable(state: str, lease_expires_at: datetime | None, now: datetime) -> bool:
+    if state == READY_STATE:
+        return True
+    return state == DISPATCHED_STATE and lease_expires_at is not None and lease_expires_at <= now
 
 
 def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
-    selected = [r for r in rows if can_claim(r.get("state", "free"), r.get("lease_expires_at"), now)]
+    selected = [r for r in rows if claimable(r.get("state", READY_STATE), r.get("lease_expires_at"), now)]
     return selected[:limit]
 
 
-async def claim_outbox_rows(session, owner: str, limit: int, now: datetime) -> list[dict]:
-    """Claim ready outbox rows atomically, bumping the fencing generation."""
-    from sqlalchemy import text
+async def list_workspace_ids(session) -> list:
+    from sqlalchemy import select
+
+    return list((await session.execute(select(Workspace.id).order_by(Workspace.id))).scalars().all())
 
+
+async def claim_outbox_rows(
+    session, owner: str, limit: int, now: datetime, lease_seconds: int, *, expired_only: bool = False
+) -> list[dict]:
+    """Claim ready (or expired in-progress) rows, bumping the fencing generation."""
+    predicate = _EXPIRED_PREDICATE if expired_only else _CLAIMABLE_PREDICATE
     result = await session.execute(
         text(
-            """
+            f"""
             UPDATE outbox_events
                SET lease_owner = :owner,
                    lease_expires_at = :expires,
+                   dispatched_at = :now,
+                   attempts = attempts + 1,
                    fencing_generation = fencing_generation + 1,
                    state = 'dispatched'
              WHERE id IN (
                    SELECT id FROM outbox_events
-                    WHERE state = 'ready'
-                       OR (state = 'dispatched' AND lease_expires_at <= :now)
+                    WHERE {predicate}
                     ORDER BY created_at
                     LIMIT :limit
                     FOR UPDATE SKIP LOCKED
              )
-         RETURNING id, intent_key, event_type, payload, fencing_generation
+         RETURNING {_CLAIM_COLUMNS}
             """
         ),
-        {"owner": owner, "expires": lease_expiry(now, 120), "now": now, "limit": limit},
+        {"owner": owner, "expires": lease_expiry(now, lease_seconds), "now": now, "limit": limit},
     )
     return [dict(r._mapping) for r in result]
 
 
-async def mark_dispatched(session, ids: list[int], now: datetime) -> None:
-    from sqlalchemy import text
-
-    if not ids:
-        return
-    await session.execute(text("UPDATE outbox_events SET dispatched_at = :now WHERE id = ANY(:ids)"), {"now": now, "ids": ids})
+async def release_claim(session, intent_key: str) -> None:
+    """Return a claimed row to the claimable pool (publish failure recovery)."""
+    await session.execute(
+        text(
+            "UPDATE outbox_events SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL"
+            " WHERE intent_key = :key AND state = 'dispatched'"
+        ),
+        {"key": intent_key},
+    )
 
 
-async def sweep_expired(session, now: datetime) -> list[int]:
-    """Return ids of dispatched rows whose lease expired (re-claimable)."""
-    from sqlalchemy import text
+async def _workspace_ids(engine) -> list:
+    maker = async_sessionmaker(engine, expire_on_commit=False)
+    async with maker() as session:
+        return await list_workspace_ids(session)
 
-    result = await session.execute(
-        text("SELECT id FROM outbox_events WHERE state = 'dispatched' AND lease_expires_at <= :now"),
-        {"now": now},
-    )
-    return [r[0] for r in result]
 
+async def _dispatch_workspace(
+    engine, workspace_id, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
+) -> list[str]:
+    async with tenant_session(engine, workspace_id) as session:
+        claimed = await claim_outbox_rows(session, owner, limit, now, lease_seconds, expired_only=expired_only)
+    # The claim above committed, so dispatch state is durable before the publish.
+    published: list[str] = []
+    for row in claimed:
+        message = {
+            "intent_key": row["intent_key"],
+            "workspace_id": str(row["workspace_id"]),
+            "generation": row["fencing_generation"],
+        }
+        try:
+            publish(message)
+        except Exception:
+            async with tenant_session(engine, workspace_id) as session:
+                await release_claim(session, row["intent_key"])
+            raise
+        published.append(row["intent_key"])
+    return published
 
-async def dispatch_once(session, publish: Callable, owner: str, now: datetime, limit: int) -> list[str]:
-    from buyeros_api.services.outbox_service import build_intent
 
-    claimed = await claim_outbox_rows(session, owner, limit, now)
+async def _fan_out(
+    engine, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
+) -> list[str]:
     published: list[str] = []
-    for row in claimed:
-        intent = build_intent(row["event_type"], row["payload"], 0)
-        publish(intent, row)
-        published.append(intent)
-    await mark_dispatched(session, [row["id"] for row in claimed], now)
+    for workspace_id in await _workspace_ids(engine):
+        published.extend(
+            await _dispatch_workspace(
+                engine, workspace_id, publish, owner, now, limit, lease_seconds, expired_only=expired_only
+            )
+        )
     return published
+
+
+async def dispatch_once(
+    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
+) -> list[str]:
+    """Claim and publish ready intents across all workspaces."""
+    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=False)
+
+
+async def sweep_once(
+    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
+) -> list[str]:
+    """Re-enqueue intents whose lease expired without a terminal state."""
+    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=True)
 ```
 
 - [ ] **Step 4: Run test to verify it passes**
 
 Run: `uv run pytest tests/test_dispatcher.py -v`
-Expected: PASS (2 passed).
+Expected: PASS (7 passed).
 
 - [ ] **Step 5: Commit**
 
 ```bash
-git add services/worker/buyeros_worker/dispatcher.py services/worker/buyeros_worker/store.py services/worker/tests/test_dispatcher.py
-git commit -m "feat(worker): outbox dispatcher with lease claims and sweeper"
+git add services/worker/buyeros_worker/dispatcher.py services/worker/tests/test_dispatcher.py
+git commit -m "feat(worker): RLS-aware dispatcher, re-enqueueing sweeper and CLI entrypoints"
 ```
 
 ---
 
 ### Task 9: Celery task entrypoint (ack after commit)
 
 **Files:**
+- Create: `services/worker/buyeros_worker/engine.py`
 - Create: `services/worker/buyeros_worker/tasks.py`
+- Create: `services/worker/buyeros_worker/cli.py`
 - Create: `services/worker/tests/test_tasks.py`
 
 **Interfaces:**
-- Produces: `execute_intent(intent_key: str, event_type: str, payload: dict, generation: int) -> str` Celery task returning the terminal state; `run_intent(handler, payload, session_factory, context) -> str` pure orchestration helper.
-- Consumes: `get_handler` (Task 4), `fence_ok` (Task 3), `HandlerResult` (Task 4).
+- Produces: `engine.async_database_url(url)`/`create_engine()`/`set_active_engine(engine)`/`dispose_engine(**kwargs)`; `execute_intent_sync(intent_key, workspace_id, generation) -> str`; `async run_intent(session, context, intent_key, generation) -> str`; `async load_intent(session, intent_key)`; `async mark_outbox_terminal(session, intent_key, generation, state) -> int`; `execute_intent(intent_key, workspace_id, generation)` Celery task (acks late, retries on `RetryRequested`); `sweep` Celery task.
+- Consumes: `get_handler`/`UnknownHandler` (Task 4), `fence_ok` (Task 3), `TERMINAL_STATES`/`OutboxEvent` (Task 2), `create_engine`/`dispose_engine` (this task).
+- **Message contract:** the task signature is `(intent_key, workspace_id, generation)` only. The broker is never the instruction source: `run_intent` loads the row from the database, and the event type and payload come from that row.
+- **Fencing:** `load_intent` takes a `FOR UPDATE` lock and `fence_ok` compares the presented generation with the row's before any handler runs; a stale call returns `"stale"` with no handler execution and no writes.
+- **Engine lifecycle:** one engine is created and disposed per invocation on the same event loop (no singleton reused across `asyncio.run` loops). `dispose_engine` is connected to Celery's `worker_shutdown` signal as a mid-run safety net.
+
 
 - [ ] **Step 1: Write the failing test**
 
 ```python
 # services/worker/tests/test_tasks.py
+import asyncio
+from contextlib import asynccontextmanager
+
 import pytest
 
+import buyeros_worker.engine as engine_mod
+import buyeros_worker.tasks as tasks
 from buyeros_worker.registry import HandlerResult, UnknownHandler
-from buyeros_worker.tasks import run_intent
 
 
-class FakeSession:
+class FakeEngine:
     def __init__(self):
-        self.committed = False
+        self.disposed = False
 
-    async def __aenter__(self):
-        return self
+    async def dispose(self):
+        self.disposed = True
 
-    async def __aexit__(self, *exc):
-        return False
 
-    async def commit(self):
-        self.committed = True
+def test_each_invocation_creates_and_disposes_its_own_engine(monkeypatch):
+    created = []
 
+    def fake_create_engine():
+        engine = FakeEngine()
+        created.append(engine)
+        return engine
 
-def test_run_intent_returns_handler_state():
-    session = FakeSession()
+    @asynccontextmanager
+    async def fake_tenant_session(engine, workspace_id):
+        yield object()
 
-    async def handler(s, context, payload):
-        return HandlerResult(state="done", detail="ok")
+    async def fake_run_intent(session, context, intent_key, generation):
+        return "done"
+
+    monkeypatch.setattr(tasks, "create_engine", fake_create_engine)
+    monkeypatch.setattr(tasks, "tenant_session", fake_tenant_session)
+    monkeypatch.setattr(tasks, "run_intent", fake_run_intent)
+    assert tasks.execute_intent_sync("job:1", "ws", 1) == "done"
+    assert tasks.execute_intent_sync("job:2", "ws", 1) == "done"
+    assert len(created) == 2
+    assert all(engine.disposed for engine in created)
+
+
+def _row(state="dispatched", generation=1, event_type="fetch.evidence", payload=None):
+    return {"state": state, "event_type": event_type, "payload": payload or {}, "fencing_generation": generation}
+
+
+def test_run_intent_rejects_a_stale_generation_without_running_the_handler(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row(generation=9)
+
+    called = []
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda *args: called.append(event_type))
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "stale"
+    assert called == []
+
+
+def test_run_intent_marks_the_row_done(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row()
+
+    terminal = []
 
-    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
-    assert state == "done"
-    assert session.committed is True
+    async def fake_mark(session, intent_key, generation, state):
+        terminal.append((intent_key, generation, state))
+        return 1
 
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
+    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda s, c, p: HandlerResult(state="done"))
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "done"
+    assert terminal == [("job:1", 1, "done")]
 
-def test_run_intent_reports_blocked_without_raising():
-    session = FakeSession()
 
-    async def handler(s, context, payload):
-        return HandlerResult(state="blocked", detail="no provider")
+def test_worker_shutdown_disposes_the_in_flight_engine():
+    from celery import signals
 
-    state = __import__("asyncio").run(run_intent(handler, {}, session, context={"workspace_id": "w"}))
-    assert state == "blocked"
+    engine = FakeEngine()
+    engine_mod.set_active_engine(engine)
+    signals.worker_shutdown.send(sender=None)
+    assert engine.disposed is True
+    assert engine_mod._active_engine is None
 ```
 
 - [ ] **Step 2: Run test to verify it fails**
 
 Run: `uv run pytest tests/test_tasks.py -v`
 Expected: FAIL — `ModuleNotFoundError`.
 
 - [ ] **Step 3: Write minimal implementation**
 
+```python
+# services/worker/buyeros_worker/engine.py  (async engine lifecycle)
+def async_database_url(url: str) -> str:
+    """Force the psycopg (v3) async driver for SQLAlchemy async engines."""
+    if url.startswith("postgresql+"):
+        return url
+    if url.startswith("postgresql://"):
+        return url.replace("postgresql://", "postgresql+psycopg://", 1)
+    return url
+
+
+def create_engine():
+    from buyeros_api.settings import get_settings
+    return create_async_engine(async_database_url(get_settings().database_url))
+
+
+def dispose_engine(**_) -> None:
+    """Dispose the in-flight engine. Wired to Celery's ``worker_shutdown``."""
+    global _active_engine
+    with _active_lock:
+        engine, _active_engine = _active_engine, None
+    if engine is not None:
+        asyncio.run(engine.dispose())
+```
+
 ```python
 # services/worker/buyeros_worker/tasks.py
 import asyncio
+from collections.abc import Callable
+from datetime import datetime, timezone
+
+from celery import signals
+from sqlalchemy import select, update
 
+from buyeros_api.db.outbox import DISPATCHED_STATE, TERMINAL_STATES, OutboxEvent
+from buyeros_api.db.session import tenant_session
+
+from . import handlers  # noqa: F401  (import registers handlers)
 from .app import celery_app
-from .registry import get_handler
+from .engine import create_engine, dispose_engine, set_active_engine
+from .leases import fence_ok
+from .registry import UnknownHandler, get_handler
 
+# Handler result state -> terminal outbox state. ``retry`` is absent: it leaves
+# the row non-terminal and asks Celery for a bounded retry.
+TERMINAL_FOR_RESULT = {"done": "done", "blocked": "failed"}
 
-async def run_intent(handler, payload, session, context) -> str:
-    """Execute one handler inside the tenant session and commit before ack.
 
-    The caller passes a session already scoped with the transaction-local
-    tenant context; nothing is committed if the handler raises.
-    """
-    result = handler(session, context, payload)
+class RetryRequested(Exception):
+    """The handler asked for a bounded Celery retry; the transaction rolls back."""
+
+
+class StaleFenced(Exception):
+    """A superseded worker lost the fencing race; nothing may be committed."""
+
+
+async def load_intent(session, intent_key: str) -> dict | None:
+    """Lock and read the intent from the database (never from the message)."""
+    row = (await session.execute(select(OutboxEvent).where(OutboxEvent.intent_key == intent_key).with_for_update())).scalar_one_or_none()
+    if row is None:
+        return None
+    return {"state": row.state, "event_type": row.event_type, "payload": row.payload, "fencing_generation": row.fencing_generation}
+
+
+async def mark_outbox_terminal(session, intent_key: str, generation: int, state: str) -> int:
+    """Terminal write guarded by the fencing generation; returns rows updated."""
+    result = await session.execute(
+        update(OutboxEvent)
+        .where(OutboxEvent.intent_key == intent_key, OutboxEvent.fencing_generation == generation, OutboxEvent.state == DISPATCHED_STATE)
+        .values(state=state, lease_owner=None, lease_expires_at=None)
+    )
+    return result.rowcount or 0
+
+
+async def run_intent(session, context, intent_key: str, generation: int) -> str:
+    row = await load_intent(session, intent_key)
+    if row is None:
+        return "unknown_intent"
+    if row["state"] in TERMINAL_STATES:
+        return "duplicate"
+    if not fence_ok(generation, row["fencing_generation"]):
+        return "stale"
+    try:
+        handler = get_handler(row["event_type"])
+    except UnknownHandler:
+        await mark_outbox_terminal(session, intent_key, generation, "failed")
+        return "unknown_handler"
+    handler_context = dict(context or {})
+    handler_context["event_type"] = row["event_type"]
+    result = handler(session, handler_context, row["payload"])
     if asyncio.iscoroutine(result):
         result = await result
-    await session.commit()
+    if result.state == "retry":
+        raise RetryRequested()
+    terminal = TERMINAL_FOR_RESULT.get(result.state)
+    if terminal is not None and await mark_outbox_terminal(session, intent_key, generation, terminal) == 0:
+        raise StaleFenced()
     return result.state
 
 
-@celery_app.task(name="buyeros.execute_intent", acks_late=True)
-def execute_intent(intent_key: str, event_type: str, payload: dict, generation: int) -> str:
-    handler = get_handler(event_type)
+async def _with_engine(body: Callable):
+    """Create an engine, run ``body`` on a fresh loop, always dispose it."""
+    engine = create_engine()
+    set_active_engine(engine)
+    try:
+        return await body(engine)
+    finally:
+        try:
+            await engine.dispose()
+        finally:
+            set_active_engine(None)
+
+
+def execute_intent_sync(intent_key: str, workspace_id: str, generation: int) -> str:
+    async def body(engine):
+        async with tenant_session(engine, workspace_id) as session:
+            return await run_intent(session, {"workspace_id": workspace_id}, intent_key, generation)
 
-    async def _run() -> str:
-        from buyeros_api.db.session import tenant_session
+    try:
+        return asyncio.run(_with_engine(body))
+    except StaleFenced:
+        return "stale"
 
-        engine = _engine()
-        async with tenant_session(engine, payload["workspace_id"]) as session:
-            return await run_intent(handler, payload, session, context={"workspace_id": payload["workspace_id"]})
 
-    return asyncio.run(_run())
+def publish_message(message: dict) -> None:
+    celery_app.send_task("buyeros.execute_intent", args=[message["intent_key"], message["workspace_id"], message["generation"]])
 
 
-def _engine():
-    from sqlalchemy.ext.asyncio import create_async_engine
+def sweep_sync() -> list[str]:
+    from .config import get_settings
+    from .dispatcher import sweep_once
+
+    settings = get_settings()
+    now = datetime.now(timezone.utc)
+
+    async def body(engine):
+        return await sweep_once(engine, publish_message, "buyeros-sweeper", now, settings.batch_size, settings.lease_seconds)
+
+    return asyncio.run(_with_engine(body))
 
-    from buyeros_api.settings import get_settings
 
-    return create_async_engine(get_settings().database_url)
+@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
+def execute_intent(self, intent_key: str, workspace_id: str, generation: int) -> str:
+    try:
+        return execute_intent_sync(intent_key, workspace_id, generation)
+    except RetryRequested:
+        raise self.retry(countdown=30, max_retries=3)
+
+
+@celery_app.task(name="buyeros.sweep")
+def sweep() -> int:
+    """Periodic recovery task (see ``beat_schedule`` in ``app.build_app``)."""
+    return len(sweep_sync())
+
+
+signals.worker_shutdown.connect(dispose_engine, weak=False)
 ```
 
 - [ ] **Step 4: Run test to verify it passes**
 
 Run: `uv run pytest tests/test_tasks.py -v`
-Expected: PASS (2 passed).
+Expected: PASS (12 passed).
 
 - [ ] **Step 5: Commit**
 
 ```bash
-git add services/worker/buyeros_worker/tasks.py services/worker/tests/test_tasks.py
-git commit -m "feat(worker): celery task entrypoint with commit-before-ack"
+git add services/worker/buyeros_worker/engine.py services/worker/buyeros_worker/tasks.py services/worker/tests/test_tasks.py
+git commit -m "feat(worker): enforce fencing and resolve intents from the database"
 ```
 
 ---
 
 ### Task 10: Disposable Valkey integration test
 
 **Files:**
 - Create: `services/worker/tests/test_valkey_integration.py`
 
 **Interfaces:**
@@ -1108,19 +1440,19 @@ Expected: all tests PASS (integration SKIP if Docker is unavailable).
 
 ```bash
 git add services/worker/tests/test_valkey_integration.py
 git commit -m "test(worker): disposable valkey broker integration check"
 ```
 
 ---
 
 ## Self-Review
 
-- **Spec coverage:** A (Tasks 1, 2), B (Tasks 2, 3, 8, 9), C (Tasks 4, 5, 6, 7), D (Tasks 7, 9), E (Tasks 2 Step 5, 10) are mapped. Gaps intentionally deferred: the **live HTTP fetch client with DNS/IP pinning**, the sweeper's periodic schedule wiring, and dispatcher/worker CLI commands — noted as follow-ups, not silently omitted.
-- **Placeholder scan:** no `TBD`/`TODO`; every code step shows complete code. `store.py` is created but currently unused by the pure tests; it is reserved for the DB-backed dispatch test in a follow-up task and should either gain a test or be removed before Build.
-- **Type consistency:** `HandlerResult(state, detail)`, `register`/`get_handler`, `can_claim`/`lease_expiry`/`fence_ok`, `select_ready`/`claim_outbox_rows`/`sweep_expired`/`dispatch_once`, `transition_run`/`terminal`, `run_intent`/`execute_intent` are consistent across tasks and reuse `buyeros_api` names (`build_intent`, `next_sequence`, `apply_event`, `normalize_url`, `is_blocked_host`, `tenant_session`).
+- **Spec coverage:** A (Tasks 1, 2), B (Tasks 2, 3, 8, 9), C (Tasks 4, 5, 6, 7), D (Tasks 7, 9), E (Tasks 2 Step 5, 10) are mapped. The sweeper's periodic schedule (Celery `beat_schedule` + `buyeros.sweep`) and the `buyeros-worker dispatch`/`sweep` CLI are delivered in Task 9 and registered as a console script; the only intentional gap is the **live HTTP fetch client with DNS/IP pinning** (Task 6 stays validation-only).
+- **Placeholder scan:** no `TBD`/`TODO`; every code step shows complete code. `store.py` was removed from the plan and the tree: the dispatcher reads and writes `outbox_events` directly.
+- **Type consistency:** `HandlerResult(state, detail)`, `register`/`get_handler`, `lease_expiry`/`fence_ok`, `claimable`/`select_ready`/`claim_outbox_rows`/`release_claim`/`dispatch_once`/`sweep_once`, `transition_run`/`terminal`/`halted`/`emit_run_event`, `load_intent`/`mark_outbox_terminal`/`run_intent`/`execute_intent` are consistent across tasks and reuse `buyeros_api` names (`next_sequence`, `apply_event`, `TERMINAL_STATES`, `normalize_url`, `is_blocked_host`, `tenant_session`). There is no engine singleton: `_with_engine` creates and disposes one engine per invocation.
 
 ## Global Notes
 
 - No remote commits, pushes, deploys, cloud resources, real-data migrations, provider calls, or sends are performed by this plan.
 - Every command is **NOT RUN** until executed under explicit approval; record exact output in `PROGRESS.md`.
 - Execution requires the recorded dependency waiver (BO-003/BO-004/BO-011 incomplete) and may use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
diff --git a/services/api/alembic/versions/0006_worker_leases.py b/services/api/alembic/versions/0006_worker_leases.py
new file mode 100644
index 0000000..7640098
--- /dev/null
+++ b/services/api/alembic/versions/0006_worker_leases.py
@@ -0,0 +1,56 @@
+"""worker leases and outbox dispatch columns"""
+
+from collections.abc import Sequence
+
+import sqlalchemy as sa
+from alembic import op
+from sqlalchemy.dialects import postgresql
+
+revision: str = "0006_worker_leases"
+down_revision: str | None = "0005_p3_tables"
+branch_labels: str | Sequence[str] | None = None
+depends_on: str | Sequence[str] | None = None
+
+UUID = postgresql.UUID(as_uuid=True)
+
+
+def upgrade() -> None:
+    op.add_column("outbox_events", sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True))
+    op.add_column("outbox_events", sa.Column("lease_owner", sa.String(128), nullable=True))
+    op.add_column("outbox_events", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
+    op.add_column(
+        "outbox_events",
+        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
+    )
+    op.create_table(
+        "worker_leases",
+        sa.Column("id", UUID, primary_key=True),
+        sa.Column("workspace_id", UUID, nullable=False),
+        sa.Column("intent_key", sa.String(128), nullable=False),
+        sa.Column("owner", sa.String(128), nullable=True),
+        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
+        sa.Column("fencing_generation", sa.Integer(), nullable=False, server_default="0"),
+        sa.Column("state", sa.String(16), nullable=False, server_default="free"),
+        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
+        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
+        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
+        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
+        sa.UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
+        sa.UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
+    )
+    op.create_index("ix_worker_leases_workspace_id", "worker_leases", ["workspace_id"])
+    op.execute("ALTER TABLE worker_leases ENABLE ROW LEVEL SECURITY;")
+    op.execute("ALTER TABLE worker_leases FORCE ROW LEVEL SECURITY;")
+    op.execute(
+        "CREATE POLICY tenant_isolation ON worker_leases "
+        "USING (workspace_id = current_setting('app.workspace_id')::uuid) "
+        "WITH CHECK (workspace_id = current_setting('app.workspace_id')::uuid);"
+    )
+    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON worker_leases TO buyeros_api, buyeros_worker;")
+
+
+def downgrade() -> None:
+    op.execute("DROP POLICY IF EXISTS tenant_isolation ON worker_leases;")
+    op.drop_table("worker_leases")
+    for column in ("fencing_generation", "lease_expires_at", "lease_owner", "dispatched_at"):
+        op.drop_column("outbox_events", column)
diff --git a/services/api/alembic/versions/0007_outbox_terminal_state.py b/services/api/alembic/versions/0007_outbox_terminal_state.py
new file mode 100644
index 0000000..7c238c0
--- /dev/null
+++ b/services/api/alembic/versions/0007_outbox_terminal_state.py
@@ -0,0 +1,44 @@
+"""terminal outbox states, claim index and dispatcher workspace read
+
+Revision ID: 0007_outbox_terminal_state
+Revises: 0006_worker_leases
+Create Date: 2026-09-15
+
+Completing an outbox intent records a terminal ``done``/``failed`` state in the
+same transaction as the work. The claim query only ever re-claims ``ready`` rows
+or ``dispatched`` rows whose lease expired, so a terminal row is never re-run and
+a duplicate broker delivery is a no-op. The index supports that predicate.
+
+The dispatcher runs under row-level security and cannot read tenant tables
+without a workspace context, so it enumerates tenants from ``workspaces`` (the
+tenant root, not RLS-protected). That requires a read grant, added here.
+"""
+
+from collections.abc import Sequence
+
+from alembic import op
+
+revision: str = "0007_outbox_terminal_state"
+down_revision: str | None = "0006_worker_leases"
+branch_labels: str | Sequence[str] | None = None
+depends_on: str | Sequence[str] | None = None
+
+
+def upgrade() -> None:
+    op.create_check_constraint(
+        "state",
+        "outbox_events",
+        "state IN ('ready', 'dispatched', 'done', 'failed')",
+    )
+    op.create_index(
+        "ix_outbox_events_state_lease_expires_at",
+        "outbox_events",
+        ["state", "lease_expires_at"],
+    )
+    op.execute("GRANT SELECT ON workspaces TO buyeros_api, buyeros_worker;")
+
+
+def downgrade() -> None:
+    op.execute("REVOKE SELECT ON workspaces FROM buyeros_api, buyeros_worker;")
+    op.drop_index("ix_outbox_events_state_lease_expires_at", table_name="outbox_events")
+    op.drop_constraint("ck_outbox_events_state", "outbox_events", type_="check")
diff --git a/services/api/buyeros_api/db/__init__.py b/services/api/buyeros_api/db/__init__.py
index df0ff3b..59c7b02 100644
--- a/services/api/buyeros_api/db/__init__.py
+++ b/services/api/buyeros_api/db/__init__.py
@@ -1 +1,35 @@
-"""Database layer (BO-005)."""
+"""Database layer (BO-005).
+
+Importing this package registers every model on ``Base.metadata``. Mapper
+configuration and Alembic autogenerate therefore always see the complete schema
+(including ``worker_leases``), and a `select()` of one model can resolve its
+foreign keys to tables declared in another module.
+"""
+
+from . import (  # noqa: F401
+    budget,
+    buyers,
+    contact,
+    drafts,
+    icp,
+    models,
+    outcomes,
+    outbox,
+    policy,
+    runs,
+    worker,
+)
+
+__all__ = [
+    "budget",
+    "buyers",
+    "contact",
+    "drafts",
+    "icp",
+    "models",
+    "outcomes",
+    "outbox",
+    "policy",
+    "runs",
+    "worker",
+]
diff --git a/services/api/buyeros_api/db/outbox.py b/services/api/buyeros_api/db/outbox.py
index 7fddc10..db0a09f 100644
--- a/services/api/buyeros_api/db/outbox.py
+++ b/services/api/buyeros_api/db/outbox.py
@@ -1,27 +1,43 @@
 """Transactional outbox (BO-011).
 
 Business intent and its outbox row commit in the same transaction; the
 dispatcher publishes deterministic task IDs to the single Celery/Valkey broker.
 Queue acknowledgement is not durable business completion.
+
+Terminal states (``done``/``failed``) end the row's life: the worker writes one
+in the same transaction as the work, and the claim query never re-claims them,
+so a duplicate broker delivery after completion is a no-op.
 """
 
-from sqlalchemy import ForeignKeyConstraint, Integer, String, UniqueConstraint
+from datetime import datetime
+
+from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
 from sqlalchemy.dialects.postgresql import JSONB
 from sqlalchemy.orm import Mapped, mapped_column
 
 from .base import Base, TenantMixin
 
+READY_STATE = "ready"
+DISPATCHED_STATE = "dispatched"
+OUTBOX_STATES = (READY_STATE, DISPATCHED_STATE, "done", "failed")
+TERMINAL_STATES = frozenset({"done", "failed"})
+
 
 class OutboxEvent(Base, TenantMixin):
     __tablename__ = "outbox_events"
     __table_args__ = (
+        CheckConstraint("state IN ('ready', 'dispatched', 'done', 'failed')", name="state"),
         UniqueConstraint("workspace_id", "id", name="uq_outbox_events_workspace_id"),
         UniqueConstraint("workspace_id", "intent_key", "event_type", name="uq_outbox_events_intent_type"),
         ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_outbox_events_workspace"),
     )
 
     intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
     event_type: Mapped[str] = mapped_column(String(64), nullable=False)
     payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
     attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
-    state: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
+    state: Mapped[str] = mapped_column(String(32), nullable=False, default=READY_STATE)
+    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
+    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
+    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
+    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
diff --git a/services/api/buyeros_api/db/session.py b/services/api/buyeros_api/db/session.py
index 762a0b7..b3f9dac 100644
--- a/services/api/buyeros_api/db/session.py
+++ b/services/api/buyeros_api/db/session.py
@@ -1,26 +1,30 @@
 """Transaction-local tenant context (BO-005).
 
 Every domain query runs inside a transaction that first sets
-``app.workspace_id`` with ``SET LOCAL``. RLS policies read that setting, so a
-missing context causes no rows to be visible (fail-closed) rather than leaking
-another tenant's data. The setting is transaction-local, so it never survives a
-pooled connection being reused by a different request.
+``app.workspace_id`` with ``set_config(..., true)`` (the function form of
+``SET LOCAL``, which - unlike ``SET`` - accepts a bound parameter). RLS
+policies read that setting, so a missing context causes no rows to be visible
+(fail-closed) rather than leaking another tenant's data. The setting is
+transaction-local, so it never survives a pooled connection being reused by a
+different request.
 """
 
 import contextlib
 import uuid
 from collections.abc import AsyncIterator
 
 from sqlalchemy import text
 from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
 
 
 @contextlib.asynccontextmanager
 async def tenant_session(engine: AsyncEngine | None, workspace_id: uuid.UUID | None) -> AsyncIterator[AsyncSession]:
     if engine is None or workspace_id is None:
         raise ValueError("tenant context requires an engine and a workspace_id")
     maker = async_sessionmaker(engine, expire_on_commit=False)
     async with maker() as session:
         async with session.begin():
-            await session.execute(text("SET LOCAL app.workspace_id = :ws"), {"ws": str(workspace_id)})
+            await session.execute(
+                text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": str(workspace_id)}
+            )
             yield session
diff --git a/services/api/buyeros_api/db/worker.py b/services/api/buyeros_api/db/worker.py
new file mode 100644
index 0000000..15b3495
--- /dev/null
+++ b/services/api/buyeros_api/db/worker.py
@@ -0,0 +1,29 @@
+"""Durable worker leases and fencing generations (P8).
+
+Leases are the database-side half of the dispatcher/worker handshake: the
+dispatcher claims an outbox intent by writing a lease row, and the worker must
+present the matching fencing generation before its writes are accepted.
+"""
+
+from datetime import datetime
+
+from sqlalchemy import DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint
+from sqlalchemy.orm import Mapped, mapped_column
+
+from .base import Base, TenantMixin
+
+
+class WorkerLease(Base, TenantMixin):
+    __tablename__ = "worker_leases"
+    __table_args__ = (
+        UniqueConstraint("workspace_id", "id", name="uq_worker_leases_workspace_id"),
+        UniqueConstraint("workspace_id", "intent_key", name="uq_worker_leases_intent"),
+        ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_worker_leases_workspace"),
+    )
+
+    intent_key: Mapped[str] = mapped_column(String(128), nullable=False)
+    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
+    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
+    fencing_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
+    state: Mapped[str] = mapped_column(String(16), nullable=False, default="free")
+    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
diff --git a/services/api/pyproject.toml b/services/api/pyproject.toml
index 6503bce..9598246 100644
--- a/services/api/pyproject.toml
+++ b/services/api/pyproject.toml
@@ -17,10 +17,17 @@ dev = [
   "pytest-asyncio>=0.24,<1",
 ]
 
 [tool.pytest.ini_options]
 testpaths = ["tests"]
 pythonpath = ["."]
 
 # NOTE (BO-005 spike): fastapi, asyncpg and pyjwt[crypto] are intentionally
 # omitted here; they are added when BO-004 (bearer identity) and the HTTP
 # layer (BO-003/BO-007+) are implemented. No auth or API route exists yet.
+
+[build-system]
+requires = ["hatchling"]
+build-backend = "hatchling.build"
+
+[tool.hatch.build.targets.wheel]
+packages = ["buyeros_api"]
diff --git a/services/api/tests/test_outbox_terminal_state.py b/services/api/tests/test_outbox_terminal_state.py
new file mode 100644
index 0000000..aa8de33
--- /dev/null
+++ b/services/api/tests/test_outbox_terminal_state.py
@@ -0,0 +1,46 @@
+"""Terminal outbox states and the dispatcher claim index (0007)."""
+
+from pathlib import Path
+
+from buyeros_api.db.outbox import OUTBOX_STATES, TERMINAL_STATES, OutboxEvent
+
+MIGRATION = Path("alembic/versions/0007_outbox_terminal_state.py")
+
+
+def test_terminal_states_are_done_and_failed():
+    assert TERMINAL_STATES == frozenset({"done", "failed"})
+
+
+def test_known_states_are_enumerated():
+    assert OUTBOX_STATES == ("ready", "dispatched", "done", "failed")
+
+
+def test_terminal_states_are_not_dispatchable():
+    assert TERMINAL_STATES.isdisjoint({"ready", "dispatched"})
+
+
+def test_model_enforces_the_state_set():
+    checks = {
+        constraint.name
+        for constraint in OutboxEvent.__table__.constraints
+        if constraint.__class__.__name__ == "CheckConstraint"
+    }
+    assert "ck_outbox_events_state" in checks
+
+
+def test_migration_revision_chains_from_0006():
+    src = MIGRATION.read_text(encoding="utf-8")
+    assert 'revision: str = "0007_outbox_terminal_state"' in src
+    assert 'down_revision: str | None = "0006_worker_leases"' in src
+
+
+def test_migration_names_the_state_constraint_and_index_explicitly():
+    src = MIGRATION.read_text(encoding="utf-8")
+    assert "ck_outbox_events_state" in src
+    assert "ix_outbox_events_state_lease_expires_at" in src
+    assert "'done'" in src and "'failed'" in src
+
+
+def test_migration_grants_workspaces_read_for_dispatch():
+    src = MIGRATION.read_text(encoding="utf-8")
+    assert "GRANT SELECT ON workspaces TO buyeros_api, buyeros_worker;" in src
diff --git a/services/api/tests/test_tenant_context.py b/services/api/tests/test_tenant_context.py
index dbe9fe3..4807426 100644
--- a/services/api/tests/test_tenant_context.py
+++ b/services/api/tests/test_tenant_context.py
@@ -1,20 +1,31 @@
 import asyncio
+from pathlib import Path
 
 import pytest
 
 from buyeros_api.db.session import tenant_session
 
 
 def test_tenant_session_rejects_missing_engine():
     with pytest.raises(ValueError):
         asyncio.run(_open(None, "00000000-0000-4000-8000-000000000001"))
 
 
 def test_tenant_session_rejects_missing_workspace():
     with pytest.raises(ValueError):
         asyncio.run(_open(object(), None))
 
 
+def test_tenant_session_uses_a_parameterisable_set_config():
+    # `SET LOCAL ... = %s` is a syntax error; the function form accepts a bound
+    # parameter. This is exercised end-to-end by the worker DB integration tests.
+    text_source = (Path(__file__).resolve().parents[1] / "buyeros_api" / "db" / "session.py").read_text(
+        encoding="utf-8"
+    )
+    assert "set_config('app.workspace_id'" in text_source
+    assert "SET LOCAL app.workspace_id" not in text_source
+
+
 async def _open(engine, workspace_id):
     async with tenant_session(engine, workspace_id):
         pass
diff --git a/services/api/tests/test_tenant_isolation_db.py b/services/api/tests/test_tenant_isolation_db.py
index 5e5b3bb..06051fb 100644
--- a/services/api/tests/test_tenant_isolation_db.py
+++ b/services/api/tests/test_tenant_isolation_db.py
@@ -70,12 +70,13 @@ def test_rls_is_forced_on_p4_p5_tables(seeded):
         "approvals",
         "outcome_events",
         "export_jobs",
         "audit_events",
         "search_runs",
         "run_events",
         "raw_candidates",
         "company_aliases",
         "people",
         "contact_points",
+        "worker_leases",
     }
     assert expected <= protected, expected - protected
diff --git a/services/api/tests/test_worker_leases_model.py b/services/api/tests/test_worker_leases_model.py
new file mode 100644
index 0000000..568a088
--- /dev/null
+++ b/services/api/tests/test_worker_leases_model.py
@@ -0,0 +1,32 @@
+from pathlib import Path
+
+from buyeros_api.db.base import Base
+from buyeros_api.db.outbox import OutboxEvent
+from buyeros_api.db.worker import WorkerLease
+
+MIGRATION = Path("alembic/versions/0006_worker_leases.py")
+
+
+def test_worker_lease_table_and_unique_intent():
+    table = WorkerLease.__table__
+    uniques = {
+        tuple(sorted(c.name for c in constraint.columns))
+        for constraint in table.constraints
+        if constraint.__class__.__name__ == "UniqueConstraint"
+    }
+    assert ("intent_key", "workspace_id") in uniques
+
+
+def test_outbox_has_dispatch_columns():
+    for column in ("dispatched_at", "lease_owner", "lease_expires_at", "fencing_generation"):
+        assert column in OutboxEvent.__table__.columns
+
+
+def test_migration_enables_rls_on_worker_leases():
+    src = MIGRATION.read_text(encoding="utf-8")
+    assert "FORCE ROW LEVEL SECURITY" in src
+    assert '"worker_leases"' in src
+
+
+def test_only_worker_leases_is_new_tenant_table():
+    assert "worker_leases" in Base.metadata.tables
diff --git a/services/worker/buyeros_worker/__init__.py b/services/worker/buyeros_worker/__init__.py
new file mode 100644
index 0000000..07c5de9
--- /dev/null
+++ b/services/worker/buyeros_worker/__init__.py
@@ -0,0 +1,2 @@
+__all__ = ["__version__"]
+__version__ = "0.1.0"
diff --git a/services/worker/buyeros_worker/app.py b/services/worker/buyeros_worker/app.py
new file mode 100644
index 0000000..b2765ed
--- /dev/null
+++ b/services/worker/buyeros_worker/app.py
@@ -0,0 +1,31 @@
+from celery import Celery
+
+from .config import get_settings
+
+
+def configure_eager(app: Celery, enabled: bool) -> None:
+    app.conf.task_always_eager = bool(enabled)
+
+
+def build_app() -> Celery:
+    settings = get_settings()
+    app = Celery("buyeros_worker", broker=settings.broker_url)
+    app.conf.update(
+        task_ignore_result=True,
+        task_acks_late=True,
+        worker_prefetch_multiplier=1,
+        broker_connection_retry_on_startup=True,
+        beat_schedule={
+            "buyeros-sweep-expired": {
+                "task": "buyeros.sweep",
+                "schedule": float(settings.sweep_seconds),
+            }
+        },
+    )
+    configure_eager(app, settings.eager)
+    return app
+
+
+celery_app = build_app()
+
+celery_app.autodiscover_tasks(["buyeros_worker"])
diff --git a/services/worker/buyeros_worker/cli.py b/services/worker/buyeros_worker/cli.py
new file mode 100644
index 0000000..e488f98
--- /dev/null
+++ b/services/worker/buyeros_worker/cli.py
@@ -0,0 +1,59 @@
+"""Operator CLI for the dispatcher and sweeper roles.
+
+    buyeros-worker dispatch [--limit N] [--owner NAME]
+    buyeros-worker sweep    [--limit N] [--owner NAME]
+
+Both commands run once and exit; the worker process serves the broker, and
+Celery beat schedules the sweeper (``buyeros.sweep``). No deployment is implied.
+"""
+
+import argparse
+import asyncio
+from datetime import datetime, timezone
+
+from .config import get_settings
+from .dispatcher import dispatch_once, sweep_once
+from .engine import create_engine
+from .tasks import publish_message
+
+
+def _run(command: str, limit: int | None, owner: str) -> list[str]:
+    settings = get_settings()
+    now = datetime.now(timezone.utc)
+    batch = limit if limit is not None else settings.batch_size
+
+    async def body() -> list[str]:
+        engine = create_engine()
+        try:
+            if command == "dispatch":
+                return await dispatch_once(engine, publish_message, owner, now, batch, settings.lease_seconds)
+            return await sweep_once(engine, publish_message, owner, now, batch, settings.lease_seconds)
+        finally:
+            await engine.dispose()
+
+    return asyncio.run(body())
+
+
+def build_parser() -> argparse.ArgumentParser:
+    parser = argparse.ArgumentParser(prog="buyeros-worker", description="BuyerOS outbox dispatcher and recovery sweeper")
+    sub = parser.add_subparsers(dest="command", required=True)
+    for name, help_text in (
+        ("dispatch", "claim and publish ready outbox intents"),
+        ("sweep", "re-enqueue intents whose lease expired"),
+    ):
+        command = sub.add_parser(name, help=help_text)
+        command.add_argument("--limit", type=int, default=None, help="max intents per workspace")
+        command.add_argument("--owner", default=None, help="lease owner label")
+    return parser
+
+
+def main(argv: list[str] | None = None) -> int:
+    args = build_parser().parse_args(argv)
+    owner = args.owner or f"buyeros-{args.command}"
+    published = _run(args.command, args.limit, owner)
+    print(f"{args.command}: published {len(published)} intents")
+    return 0
+
+
+if __name__ == "__main__":  # pragma: no cover
+    raise SystemExit(main())
diff --git a/services/worker/buyeros_worker/config.py b/services/worker/buyeros_worker/config.py
new file mode 100644
index 0000000..f08d03b
--- /dev/null
+++ b/services/worker/buyeros_worker/config.py
@@ -0,0 +1,18 @@
+from functools import lru_cache
+
+from pydantic_settings import BaseSettings, SettingsConfigDict
+
+
+class WorkerSettings(BaseSettings):
+    model_config = SettingsConfigDict(env_prefix="BUYEROS_", extra="ignore")
+
+    broker_url: str = "redis://localhost:6379/0"
+    eager: bool = False
+    lease_seconds: int = 120
+    batch_size: int = 10
+    sweep_seconds: int = 60
+
+
+@lru_cache
+def get_settings() -> WorkerSettings:
+    return WorkerSettings()
diff --git a/services/worker/buyeros_worker/dispatcher.py b/services/worker/buyeros_worker/dispatcher.py
new file mode 100644
index 0000000..6706115
--- /dev/null
+++ b/services/worker/buyeros_worker/dispatcher.py
@@ -0,0 +1,149 @@
+"""Outbox dispatcher and recovery sweeper.
+
+**RLS choice:** the dispatcher runs as a least-privilege, ``NOBYPASSRLS`` role,
+so it cannot read any tenant's ``outbox_events`` without a workspace context. It
+therefore enumerates tenants from ``workspaces`` (the tenant root, which is not
+RLS-protected) and opens one transaction-local tenant context per workspace,
+claiming within it. No tenant query ever runs without a context, and a claim
+made under one workspace can never match another workspace's rows.
+
+**Ordering:** a claim persists its lease and increments ``fencing_generation``
+in one transaction *before* the broker publish. If the process dies between the
+commit and the publish, the lease expires and the sweeper re-enqueues the row;
+a publish that raises puts the row straight back to claimable. Duplicate
+publishes are harmless because the worker only executes a non-terminal row whose
+generation still matches.
+"""
+
+from collections.abc import Callable
+from datetime import datetime
+
+from sqlalchemy import text
+from sqlalchemy.ext.asyncio import async_sessionmaker
+
+from buyeros_api.db.models import Workspace
+from buyeros_api.db.outbox import DISPATCHED_STATE, READY_STATE
+from buyeros_api.db.session import tenant_session
+
+from .leases import lease_expiry
+
+_CLAIM_COLUMNS = "id, workspace_id, intent_key, event_type, payload, fencing_generation"
+
+# Terminal rows (done/failed) are deliberately absent: the predicate is an
+# allow-list, so a terminal row can never be re-claimed or re-run.
+_CLAIMABLE_PREDICATE = "state = 'ready' OR (state = 'dispatched' AND lease_expires_at <= :now)"
+_EXPIRED_PREDICATE = "state = 'dispatched' AND lease_expires_at <= :now"
+
+
+def claimable(state: str, lease_expires_at: datetime | None, now: datetime) -> bool:
+    if state == READY_STATE:
+        return True
+    return state == DISPATCHED_STATE and lease_expires_at is not None and lease_expires_at <= now
+
+
+def select_ready(rows: list[dict], now: datetime, limit: int = 10) -> list[dict]:
+    selected = [r for r in rows if claimable(r.get("state", READY_STATE), r.get("lease_expires_at"), now)]
+    return selected[:limit]
+
+
+async def list_workspace_ids(session) -> list:
+    from sqlalchemy import select
+
+    return list((await session.execute(select(Workspace.id).order_by(Workspace.id))).scalars().all())
+
+
+async def claim_outbox_rows(
+    session, owner: str, limit: int, now: datetime, lease_seconds: int, *, expired_only: bool = False
+) -> list[dict]:
+    """Claim ready (or expired in-progress) rows, bumping the fencing generation."""
+    predicate = _EXPIRED_PREDICATE if expired_only else _CLAIMABLE_PREDICATE
+    result = await session.execute(
+        text(
+            f"""
+            UPDATE outbox_events
+               SET lease_owner = :owner,
+                   lease_expires_at = :expires,
+                   dispatched_at = :now,
+                   attempts = attempts + 1,
+                   fencing_generation = fencing_generation + 1,
+                   state = 'dispatched'
+             WHERE id IN (
+                   SELECT id FROM outbox_events
+                    WHERE {predicate}
+                    ORDER BY created_at
+                    LIMIT :limit
+                    FOR UPDATE SKIP LOCKED
+             )
+         RETURNING {_CLAIM_COLUMNS}
+            """
+        ),
+        {"owner": owner, "expires": lease_expiry(now, lease_seconds), "now": now, "limit": limit},
+    )
+    return [dict(r._mapping) for r in result]
+
+
+async def release_claim(session, intent_key: str) -> None:
+    """Return a claimed row to the claimable pool (publish failure recovery)."""
+    await session.execute(
+        text(
+            "UPDATE outbox_events SET state = 'ready', lease_owner = NULL, lease_expires_at = NULL"
+            " WHERE intent_key = :key AND state = 'dispatched'"
+        ),
+        {"key": intent_key},
+    )
+
+
+async def _workspace_ids(engine) -> list:
+    maker = async_sessionmaker(engine, expire_on_commit=False)
+    async with maker() as session:
+        return await list_workspace_ids(session)
+
+
+async def _dispatch_workspace(
+    engine, workspace_id, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
+) -> list[str]:
+    async with tenant_session(engine, workspace_id) as session:
+        claimed = await claim_outbox_rows(session, owner, limit, now, lease_seconds, expired_only=expired_only)
+    # The claim above committed, so dispatch state is durable before the publish.
+    published: list[str] = []
+    for row in claimed:
+        message = {
+            "intent_key": row["intent_key"],
+            "workspace_id": str(row["workspace_id"]),
+            "generation": row["fencing_generation"],
+        }
+        try:
+            publish(message)
+        except Exception:
+            async with tenant_session(engine, workspace_id) as session:
+                await release_claim(session, row["intent_key"])
+            raise
+        published.append(row["intent_key"])
+    return published
+
+
+async def _fan_out(
+    engine, publish: Callable, owner: str, now: datetime, limit: int, lease_seconds: int, *, expired_only: bool
+) -> list[str]:
+    published: list[str] = []
+    for workspace_id in await _workspace_ids(engine):
+        published.extend(
+            await _dispatch_workspace(
+                engine, workspace_id, publish, owner, now, limit, lease_seconds, expired_only=expired_only
+            )
+        )
+    return published
+
+
+async def dispatch_once(
+    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
+) -> list[str]:
+    """Claim and publish ready intents across all workspaces."""
+    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=False)
+
+
+async def sweep_once(
+    engine, publish: Callable, owner: str, now: datetime, limit: int = 10, lease_seconds: int = 120
+) -> list[str]:
+    """Re-enqueue intents whose lease expired without a terminal state."""
+    return await _fan_out(engine, publish, owner, now, limit, lease_seconds, expired_only=True)
diff --git a/services/worker/buyeros_worker/engine.py b/services/worker/buyeros_worker/engine.py
new file mode 100644
index 0000000..d4d1020
--- /dev/null
+++ b/services/worker/buyeros_worker/engine.py
@@ -0,0 +1,52 @@
+"""Async engine lifecycle for the worker.
+
+A Celery task is synchronous and drives its own ``asyncio.run`` loop, and an
+async engine is bound to the loop that created it. Reusing one engine across
+per-task loops is invalid, so every invocation creates an engine, uses it, and
+disposes it on that same loop.
+
+The module also tracks the in-flight engine so Celery's ``worker_shutdown``
+signal can dispose it if the process is asked to stop mid-run. In normal
+operation there is nothing left to dispose by then (each invocation already
+disposed its own engine); the hook is the safety net.
+"""
+
+import asyncio
+from threading import Lock
+
+from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
+
+
+def async_database_url(url: str) -> str:
+    """Force the psycopg (v3) async driver for SQLAlchemy async engines."""
+    if url.startswith("postgresql+"):
+        return url
+    if url.startswith("postgresql://"):
+        return url.replace("postgresql://", "postgresql+psycopg://", 1)
+    return url
+
+
+def create_engine() -> AsyncEngine:
+    from buyeros_api.settings import get_settings
+
+    return create_async_engine(async_database_url(get_settings().database_url))
+
+
+_active_engine: AsyncEngine | None = None
+_active_lock = Lock()
+
+
+def set_active_engine(engine: AsyncEngine | None) -> None:
+    global _active_engine
+    with _active_lock:
+        _active_engine = engine
+
+
+def dispose_engine(**_: object) -> None:
+    """Dispose the in-flight engine. Wired to Celery's ``worker_shutdown``."""
+    global _active_engine
+    with _active_lock:
+        engine = _active_engine
+        _active_engine = None
+    if engine is not None:
+        asyncio.run(engine.dispose())
diff --git a/services/worker/buyeros_worker/handlers/__init__.py b/services/worker/buyeros_worker/handlers/__init__.py
new file mode 100644
index 0000000..f7b26e4
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/__init__.py
@@ -0,0 +1,2 @@
+"""Worker handlers. Importing this package registers its handlers."""
+from . import capability_blocked, fetch_evidence  # noqa: F401
diff --git a/services/worker/buyeros_worker/handlers/capability_blocked.py b/services/worker/buyeros_worker/handlers/capability_blocked.py
new file mode 100644
index 0000000..665b181
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/capability_blocked.py
@@ -0,0 +1,36 @@
+from ..registry import HandlerResult, register
+from ..run_emitter import emit_run_event
+
+BLOCKED_EVENTS = frozenset({"run.discover", "contact.submit", "draft.generate"})
+
+
+async def blocked(session, context, payload) -> HandlerResult:
+    """Fail closed: no verified provider/model, so make no external call.
+
+    When the intent carries a run id, the run is moved to the explicit
+    ``blocked`` state and exactly one ``run_events`` row is written in the same
+    transaction as the work. Every other path stays a pure, side-effect-free
+    refusal.
+    """
+    event_type = None
+    if isinstance(context, dict):
+        event_type = context.get("event_type")
+    if event_type is None and isinstance(payload, dict):
+        event_type = payload.get("event_type")
+    event_type = event_type or "unknown"
+    detail = f"{event_type}: no verified provider or model is configured"
+
+    run_id = payload.get("run_id") if isinstance(payload, dict) else None
+    if run_id is not None:
+        await emit_run_event(
+            session,
+            run_id,
+            "capability_blocked",
+            transition="capability_block",
+            payload={"event_type": event_type, "detail": detail},
+        )
+    return HandlerResult(state="blocked", detail=detail)
+
+
+for _event in BLOCKED_EVENTS:
+    register(_event)(blocked)
diff --git a/services/worker/buyeros_worker/handlers/fetch_evidence.py b/services/worker/buyeros_worker/handlers/fetch_evidence.py
new file mode 100644
index 0000000..82ac135
--- /dev/null
+++ b/services/worker/buyeros_worker/handlers/fetch_evidence.py
@@ -0,0 +1,66 @@
+from urllib.parse import urlsplit
+
+from buyeros_api.services.safe_fetch import is_blocked_host, normalize_url
+
+from ..registry import HandlerResult, register
+
+MAX_DECODED_BYTES = 2 * 1024 * 1024
+ALLOWED_CONTENT_TYPES = frozenset({"text/html", "text/plain", "text/markdown", "application/xhtml+xml"})
+
+
+class FetchRejected(Exception):
+    pass
+
+
+def _reject_if_blocked_host(host: str) -> None:
+    try:
+        blocked = is_blocked_host(host)
+    except ValueError:
+        return  # hostname; DNS/IP pinning happens at connection time
+    if blocked:
+        raise FetchRejected(f"blocked host {host}")
+
+
+def validate_fetch(url: str, content_type: str, size: int) -> None:
+    try:
+        normalize_url(url)
+    except ValueError:
+        raise FetchRejected(f"malformed url: {url}") from None
+    parts = urlsplit(url)
+    if parts.scheme not in {"http", "https"}:
+        raise FetchRejected(f"unsupported scheme {parts.scheme}")
+    host = parts.hostname
+    if not host:
+        raise FetchRejected("missing host")
+    _reject_if_blocked_host(host)
+    if size < 0 or size > MAX_DECODED_BYTES:
+        raise FetchRejected("decoded body size out of range")
+    media_type = (content_type or "").split(";")[0].strip().lower()
+    if media_type not in ALLOWED_CONTENT_TYPES:
+        raise FetchRejected(f"content type {media_type} not allowed")
+
+
+@register("fetch.evidence")
+def handle(session, context, payload) -> HandlerResult:
+    """Validate and (in the fetch client) retrieve permitted evidence.
+
+    The live HTTP client is intentionally not wired here: it must run with
+    DNS/IP pinning against the deployed egress policy. Validation is enforced
+    now so an unsafe URL can never be dispatched.
+    """
+    if not isinstance(payload, dict):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")
+    url = payload.get("url")
+    content_type = payload.get("content_type")
+    size = payload.get("size", 0)
+    if not isinstance(url, str) or not isinstance(content_type, str):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid payload")
+    try:
+        size_value = int(size)
+    except (TypeError, ValueError):
+        return HandlerResult(state="blocked", detail="fetch.evidence: invalid size")
+    try:
+        validate_fetch(url, content_type, size_value)
+    except FetchRejected as exc:
+        return HandlerResult(state="blocked", detail=str(exc))
+    return HandlerResult(state="done", detail="validated; retrieval client is not enabled in this phase")
diff --git a/services/worker/buyeros_worker/leases.py b/services/worker/buyeros_worker/leases.py
new file mode 100644
index 0000000..256ec9a
--- /dev/null
+++ b/services/worker/buyeros_worker/leases.py
@@ -0,0 +1,15 @@
+from datetime import datetime, timedelta
+
+
+def lease_expiry(now: datetime, seconds: int) -> datetime:
+    return now + timedelta(seconds=seconds)
+
+
+def can_claim(state: str, expires_at: datetime | None, now: datetime) -> bool:
+    if state == "free" or expires_at is None:
+        return True
+    return expires_at <= now
+
+
+def fence_ok(worker_generation: int, row_generation: int) -> bool:
+    return worker_generation == row_generation
diff --git a/services/worker/buyeros_worker/registry.py b/services/worker/buyeros_worker/registry.py
new file mode 100644
index 0000000..baec808
--- /dev/null
+++ b/services/worker/buyeros_worker/registry.py
@@ -0,0 +1,30 @@
+from collections.abc import Callable
+from dataclasses import dataclass
+
+
+class UnknownHandler(Exception):
+    pass
+
+
+@dataclass(frozen=True)
+class HandlerResult:
+    state: str          # "done" | "blocked" | "retry"
+    detail: str = ""
+
+
+HANDLERS: dict[str, Callable] = {}
+
+
+def register(event_type: str):
+    def decorator(func: Callable) -> Callable:
+        HANDLERS[event_type] = func
+        return func
+
+    return decorator
+
+
+def get_handler(event_type: str) -> Callable:
+    try:
+        return HANDLERS[event_type]
+    except KeyError as exc:  # pragma: no cover - exercised via test
+        raise UnknownHandler(event_type) from exc
diff --git a/services/worker/buyeros_worker/run_emitter.py b/services/worker/buyeros_worker/run_emitter.py
new file mode 100644
index 0000000..b32af59
--- /dev/null
+++ b/services/worker/buyeros_worker/run_emitter.py
@@ -0,0 +1,57 @@
+"""Run state transitions committed atomically with a run event (BO-016).
+
+A handler calls :func:`emit_run_event` from inside its own transaction on the
+tenant-scoped session. The ``search_runs`` status update and the ``run_events``
+insert therefore either commit with the work or roll back with it; the sequence
+is derived from the current maximum under a row lock so concurrent emitters for
+one run cannot collide or reorder.
+"""
+
+import uuid
+
+from sqlalchemy import func, select
+
+from buyeros_api.db.runs import RunEvent, SearchRun
+from buyeros_api.services.run_events import apply_event, next_sequence
+
+from .run_lifecycle import transition_run
+
+
+async def emit_run_event(session, run_id, event_type: str, *, transition: str | None = None, payload: dict | None = None) -> int:
+    """Advance the run (if ``transition``) and append exactly one event.
+
+    Returns the assigned sequence, or ``0`` when there is nothing to do (no
+    session/run, unknown run, or a non-newer sequence). Never performs any
+    external call.
+    """
+    if session is None or run_id is None:
+        return 0
+    run_key = run_id if isinstance(run_id, uuid.UUID) else uuid.UUID(str(run_id))
+
+    result = await session.execute(select(SearchRun).where(SearchRun.id == run_key).with_for_update())
+    run = result.scalar_one_or_none()
+    if run is None:
+        return 0
+
+    last = (
+        await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(RunEvent.run_id == run_key))
+    ).scalar_one()
+    sequence = next_sequence(int(last))
+    if not apply_event(int(last), sequence):
+        return 0
+
+    if transition is not None:
+        new_status = transition_run(run.status, transition)
+        if new_status != run.status:
+            run.status = new_status
+
+    session.add(
+        RunEvent(
+            workspace_id=run.workspace_id,
+            run_id=run_key,
+            sequence=sequence,
+            event_type=event_type,
+            payload=payload or {},
+        )
+    )
+    return sequence
diff --git a/services/worker/buyeros_worker/run_lifecycle.py b/services/worker/buyeros_worker/run_lifecycle.py
new file mode 100644
index 0000000..090f846
--- /dev/null
+++ b/services/worker/buyeros_worker/run_lifecycle.py
@@ -0,0 +1,54 @@
+RUN_STATES = (
+    "draft",
+    "queued",
+    "running",
+    "partial",
+    "paused_budget",
+    "completed",
+    "failed",
+    "cancel_requested",
+    "cancelled",
+    "blocked",
+)
+# Owner decision: only completed/cancelled are terminal. failed, partial and
+# paused_budget are retryable and can return to queued.
+TERMINAL = {"completed", "cancelled"}
+# A capability-blocked run is halting (nothing retries it) but it is not a
+# business-terminal outcome, so it is tracked separately from TERMINAL.
+BLOCKED = {"blocked"}
+
+_TRANSITIONS = {
+    ("draft", "enqueue"): "queued",
+    ("queued", "start"): "running",
+    ("running", "complete"): "completed",
+    ("running", "partial"): "partial",
+    ("running", "pause_budget"): "paused_budget",
+    ("running", "fail"): "failed",
+    ("running", "cancel"): "cancel_requested",
+    ("partial", "retry"): "queued",
+    ("failed", "retry"): "queued",
+    ("paused_budget", "retry"): "queued",
+    ("paused_budget", "resume"): "running",
+    ("cancel_requested", "cancel"): "cancelled",
+    ("draft", "capability_block"): "blocked",
+    ("queued", "capability_block"): "blocked",
+    ("running", "capability_block"): "blocked",
+    ("partial", "capability_block"): "blocked",
+    ("paused_budget", "capability_block"): "blocked",
+    ("cancel_requested", "capability_block"): "blocked",
+}
+
+
+def terminal(state: str) -> bool:
+    return state in TERMINAL
+
+
+def halted(state: str) -> bool:
+    """Terminal or capability-blocked: no further transition is applied."""
+    return state in TERMINAL or state in BLOCKED
+
+
+def transition_run(current: str, event: str) -> str:
+    if halted(current):
+        return current
+    return _TRANSITIONS.get((current, event), current)
diff --git a/services/worker/buyeros_worker/tasks.py b/services/worker/buyeros_worker/tasks.py
new file mode 100644
index 0000000..eed0aed
--- /dev/null
+++ b/services/worker/buyeros_worker/tasks.py
@@ -0,0 +1,163 @@
+"""Celery task entrypoints: execute one outbox intent, ack only after commit.
+
+The broker message is deliberately **not** the instruction source. It carries
+only opaque ids (``intent_key``, ``workspace_id``, ``generation``); the event
+type and payload are read from the ``outbox_events`` row inside the
+transaction-local tenant context, and the row's fencing generation must still
+match before any handler runs.
+"""
+
+import asyncio
+from collections.abc import Callable
+from datetime import datetime, timezone
+
+from celery import signals
+from sqlalchemy import select, update
+
+from buyeros_api.db.outbox import DISPATCHED_STATE, TERMINAL_STATES, OutboxEvent
+from buyeros_api.db.session import tenant_session
+
+from . import handlers  # noqa: F401  (import registers handlers)
+from .app import celery_app
+from .engine import create_engine, dispose_engine, set_active_engine
+from .leases import fence_ok
+from .registry import UnknownHandler, get_handler
+
+# Handler result state -> terminal outbox state. ``retry`` is absent: it leaves
+# the row non-terminal and asks Celery for a bounded retry.
+TERMINAL_FOR_RESULT = {"done": "done", "blocked": "failed"}
+
+
+class RetryRequested(Exception):
+    """The handler asked for a bounded Celery retry; the transaction rolls back."""
+
+
+class StaleFenced(Exception):
+    """A superseded worker lost the fencing race; nothing may be committed."""
+
+
+async def load_intent(session, intent_key: str) -> dict | None:
+    """Lock and read the intent from the database (never from the message)."""
+    row = (
+        await session.execute(select(OutboxEvent).where(OutboxEvent.intent_key == intent_key).with_for_update())
+    ).scalar_one_or_none()
+    if row is None:
+        return None
+    return {
+        "state": row.state,
+        "event_type": row.event_type,
+        "payload": row.payload,
+        "fencing_generation": row.fencing_generation,
+    }
+
+
+async def mark_outbox_terminal(session, intent_key: str, generation: int, state: str) -> int:
+    """Terminal write guarded by the fencing generation; returns rows updated."""
+    result = await session.execute(
+        update(OutboxEvent)
+        .where(
+            OutboxEvent.intent_key == intent_key,
+            OutboxEvent.fencing_generation == generation,
+            OutboxEvent.state == DISPATCHED_STATE,
+        )
+        .values(state=state, lease_owner=None, lease_expires_at=None)
+    )
+    return result.rowcount or 0
+
+
+async def run_intent(session, context, intent_key: str, generation: int) -> str:
+    """Resolve the intent from the DB, enforce fencing, then run one handler.
+
+    Everything happens on one tenant-scoped transaction: the handler's writes
+    and the terminal outbox write commit together, or neither does.
+    """
+    row = await load_intent(session, intent_key)
+    if row is None:
+        return "unknown_intent"
+    if row["state"] in TERMINAL_STATES:
+        return "duplicate"
+    if not fence_ok(generation, row["fencing_generation"]):
+        return "stale"
+
+    try:
+        handler = get_handler(row["event_type"])
+    except UnknownHandler:
+        await mark_outbox_terminal(session, intent_key, generation, "failed")
+        return "unknown_handler"
+
+    handler_context = dict(context or {})
+    handler_context["event_type"] = row["event_type"]
+    result = handler(session, handler_context, row["payload"])
+    if asyncio.iscoroutine(result):
+        result = await result
+
+    if result.state == "retry":
+        raise RetryRequested()
+
+    terminal = TERMINAL_FOR_RESULT.get(result.state)
+    if terminal is not None and await mark_outbox_terminal(session, intent_key, generation, terminal) == 0:
+        raise StaleFenced()
+    return result.state
+
+
+async def _with_engine(body: Callable):
+    """Create an engine, run ``body`` on a fresh loop, always dispose it."""
+    engine = create_engine()
+    set_active_engine(engine)
+    try:
+        return await body(engine)
+    finally:
+        try:
+            await engine.dispose()
+        finally:
+            set_active_engine(None)
+
+
+def execute_intent_sync(intent_key: str, workspace_id: str, generation: int) -> str:
+    async def body(engine):
+        async with tenant_session(engine, workspace_id) as session:
+            return await run_intent(session, {"workspace_id": workspace_id}, intent_key, generation)
+
+    try:
+        return asyncio.run(_with_engine(body))
+    except StaleFenced:
+        return "stale"
+
+
+def publish_message(message: dict) -> None:
+    celery_app.send_task(
+        "buyeros.execute_intent",
+        args=[message["intent_key"], message["workspace_id"], message["generation"]],
+    )
+
+
+def sweep_sync() -> list[str]:
+    from .config import get_settings
+    from .dispatcher import sweep_once
+
+    settings = get_settings()
+    now = datetime.now(timezone.utc)
+
+    async def body(engine):
+        return await sweep_once(
+            engine, publish_message, "buyeros-sweeper", now, settings.batch_size, settings.lease_seconds
+        )
+
+    return asyncio.run(_with_engine(body))
+
+
+@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
+def execute_intent(self, intent_key: str, workspace_id: str, generation: int) -> str:
+    try:
+        return execute_intent_sync(intent_key, workspace_id, generation)
+    except RetryRequested:
+        raise self.retry(countdown=30, max_retries=3)
+
+
+@celery_app.task(name="buyeros.sweep")
+def sweep() -> int:
+    """Periodic recovery task (see ``beat_schedule`` in ``app.build_app``)."""
+    return len(sweep_sync())
+
+
+signals.worker_shutdown.connect(dispose_engine, weak=False)
diff --git a/services/worker/pyproject.toml b/services/worker/pyproject.toml
new file mode 100644
index 0000000..ca764cc
--- /dev/null
+++ b/services/worker/pyproject.toml
@@ -0,0 +1,36 @@
+[project]
+name = "buyeros-worker"
+version = "0.1.0"
+requires-python = ">=3.12"
+dependencies = [
+  "buyeros-api",
+  "celery>=5.4,<6",
+  "redis>=5,<6",
+  "psycopg[binary]>=3.2,<4",
+  "pydantic-settings>=2.5,<3",
+]
+
+[tool.uv.sources]
+buyeros-api = { path = "../api", editable = true }
+
+[project.scripts]
+buyeros-worker = "buyeros_worker.cli:main"
+
+# NOTE (P8 worker): `buyeros_api` is installed from the local path `../api`.
+# `services/api` declares a hatchling build-system that packages only
+# `buyeros_api`, so the path dependency builds and `import buyeros_api` works
+# at runtime (not just under pytest).
+
+[dependency-groups]
+dev = ["pytest>=8.3,<9", "pytest-asyncio>=0.24,<1"]
+
+[tool.pytest.ini_options]
+testpaths = ["tests"]
+pythonpath = ["."]
+
+[build-system]
+requires = ["hatchling"]
+build-backend = "hatchling.build"
+
+[tool.hatch.build.targets.wheel]
+packages = ["buyeros_worker"]
diff --git a/services/worker/tests/__init__.py b/services/worker/tests/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/services/worker/tests/conftest.py b/services/worker/tests/conftest.py
new file mode 100644
index 0000000..2feef4a
--- /dev/null
+++ b/services/worker/tests/conftest.py
@@ -0,0 +1,188 @@
+"""Disposable-PostgreSQL fixtures for worker integration tests.
+
+The worker/store code runs against the least-privilege ``buyeros_api`` runtime
+role so row-level security is actually exercised, not bypassed. This mirrors
+``services/api/tests/conftest.py``; migrations remain owned by ``buyeros_api``
+and are applied from ``services/api/alembic``.
+"""
+
+import json
+import os
+import shutil
+import subprocess
+import sys
+import time
+import uuid
+from datetime import datetime
+from pathlib import Path
+
+import pytest
+
+# psycopg's async driver cannot run on Windows' default ProactorEventLoop; the
+# worker uses asyncio.run directly, so tests pin the selector loop here.
+if sys.platform == "win32":
+    import asyncio
+
+    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
+
+WORKER_ROOT = Path(__file__).resolve().parents[1]
+API_ROOT = WORKER_ROOT.parent / "api"
+ALEMBIC_INI = API_ROOT / "alembic.ini"
+
+POSTGRES_IMAGE = "postgres:16"
+DB_USER = "buyeros"
+DB_PASSWORD = "buyeros"
+DB_NAME = "buyeros"
+API_ROLE = "buyeros_api"
+API_ROLE_PASSWORD = "test-only"
+
+WS_A = "11111111-1111-4111-8111-111111111111"
+WS_B = "22222222-2222-4222-8222-222222222222"
+PROJECT_A = "a0000000-0000-4000-8000-000000000001"
+ICP_A = "b0000000-0000-4000-8000-0000000000a1"
+RUN_A = "d0000000-0000-4000-8000-0000000000a1"
+
+
+def _docker(*args: str) -> subprocess.CompletedProcess:
+    return subprocess.run(["docker", *args], capture_output=True, text=True)
+
+
+def _start_container() -> tuple[str, str]:
+    name = f"buyeros-worker-test-{uuid.uuid4().hex[:8]}"
+    created = _docker(
+        "run", "-d", "--name", name,
+        "-e", f"POSTGRES_PASSWORD={DB_PASSWORD}",
+        "-e", f"POSTGRES_USER={DB_USER}",
+        "-e", f"POSTGRES_DB={DB_NAME}",
+        "-p", "127.0.0.1::5432",
+        POSTGRES_IMAGE,
+    )
+    if created.returncode != 0:
+        pytest.skip(f"could not start postgres container: {created.stderr.strip()}")
+
+    deadline = time.time() + 60
+    while time.time() < deadline:
+        if "accepting connections" in _docker("exec", name, "pg_isready", "-U", DB_USER).stdout:
+            break
+        time.sleep(1)
+    else:
+        _docker("rm", "-f", name)
+        pytest.skip("postgres container did not become ready")
+
+    mapping = _docker("port", name, "5432").stdout.strip().splitlines()[0]
+    port = mapping.rsplit(":", 1)[1]
+    return name, f"postgresql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:{port}/{DB_NAME}"
+
+
+def runtime_role_dsn(dsn: str) -> str:
+    return dsn.replace(f"{DB_USER}:{DB_PASSWORD}", f"{API_ROLE}:{API_ROLE_PASSWORD}", 1)
+
+
+@pytest.fixture(scope="session")
+def pg_dsn():
+    env_dsn = os.environ.get("BUYEROS_TEST_DATABASE_URL")
+    if env_dsn:
+        yield env_dsn
+        return
+    if shutil.which("docker") is None:
+        pytest.skip("set BUYEROS_TEST_DATABASE_URL or install docker for DB tests")
+    name, dsn = _start_container()
+    try:
+        yield dsn
+    finally:
+        _docker("rm", "-f", name)
+
+
+@pytest.fixture(scope="session")
+def migrated(pg_dsn):
+    from alembic import command
+    from alembic.config import Config
+
+    from buyeros_api.settings import get_settings
+
+    os.environ["BUYEROS_DATABASE_URL"] = pg_dsn
+    get_settings.cache_clear()
+
+    config = Config(str(ALEMBIC_INI))
+    config.set_main_option("script_location", str(API_ROOT / "alembic"))
+    command.upgrade(config, "head")
+
+    import psycopg
+
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        conn.execute("DELETE FROM workspaces WHERE id IN (%s, %s)", (WS_A, WS_B))
+        conn.execute(
+            "INSERT INTO workspaces(id, name, data_mode) VALUES (%s, 'A', 'live'), (%s, 'B', 'live')",
+            (WS_A, WS_B),
+        )
+        conn.execute(
+            "INSERT INTO projects(id, workspace_id, name) VALUES (%s, %s, 'ProjectA')",
+            (PROJECT_A, WS_A),
+        )
+        conn.execute(
+            "INSERT INTO icp_versions(id, workspace_id, project_id, number, content, content_hash)"
+            " VALUES (%s, %s, %s, 1, '{}'::jsonb, 'hash')",
+            (ICP_A, WS_A, PROJECT_A),
+        )
+        conn.execute(f"ALTER ROLE {API_ROLE} LOGIN PASSWORD '{API_ROLE_PASSWORD}'")
+        conn.execute(f"GRANT USAGE ON SCHEMA public TO {API_ROLE}")
+    return pg_dsn
+
+
+@pytest.fixture(scope="session")
+def runtime_dsn(migrated):
+    return runtime_role_dsn(migrated)
+
+
+@pytest.fixture
+def worker_database_url(migrated, runtime_dsn, monkeypatch):
+    """Point the worker engine at the RLS-enforcing runtime role for one test."""
+    from buyeros_api.settings import get_settings
+
+    monkeypatch.setenv("BUYEROS_DATABASE_URL", runtime_dsn)
+    get_settings.cache_clear()
+    yield runtime_dsn
+    get_settings.cache_clear()
+
+
+def reset_tenant(conn, workspace_id: str = WS_A) -> None:
+    conn.execute("DELETE FROM run_events WHERE workspace_id = %s", (workspace_id,))
+    conn.execute("DELETE FROM search_runs WHERE workspace_id = %s", (workspace_id,))
+    conn.execute("DELETE FROM outbox_events WHERE workspace_id = %s", (workspace_id,))
+
+
+def seed_run(conn, run_id: str = RUN_A, workspace_id: str = WS_A, status: str = "running") -> None:
+    conn.execute(
+        "INSERT INTO search_runs(id, workspace_id, project_id, icp_version_id, status)"
+        " VALUES (%s, %s, %s, %s, %s)",
+        (run_id, workspace_id, PROJECT_A, ICP_A, status),
+    )
+
+
+def seed_outbox(
+    conn,
+    *,
+    intent_key: str,
+    event_type: str = "fetch.evidence",
+    payload: dict | None = None,
+    workspace_id: str = WS_A,
+    state: str = "ready",
+    generation: int = 0,
+    lease_expires_at: datetime | None = None,
+    outbox_id: str | None = None,
+) -> None:
+    conn.execute(
+        "INSERT INTO outbox_events"
+        " (id, workspace_id, intent_key, event_type, payload, state, fencing_generation, lease_expires_at)"
+        " VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)",
+        (
+            outbox_id or str(uuid.uuid4()),
+            workspace_id,
+            intent_key,
+            event_type,
+            json.dumps(payload or {}),
+            state,
+            generation,
+            lease_expires_at,
+        ),
+    )
diff --git a/services/worker/tests/test_app.py b/services/worker/tests/test_app.py
new file mode 100644
index 0000000..99a58b6
--- /dev/null
+++ b/services/worker/tests/test_app.py
@@ -0,0 +1,31 @@
+from buyeros_worker.app import build_app, celery_app, configure_eager
+from buyeros_worker.config import WorkerSettings
+
+
+def test_settings_defaults_are_safe():
+    s = WorkerSettings()
+    assert s.lease_seconds == 120
+    assert s.batch_size == 10
+    assert s.eager is False
+    assert s.sweep_seconds == 60
+
+
+def test_celery_app_is_named_and_has_no_result_backend():
+    assert celery_app.main == "buyeros_worker"
+    assert celery_app.conf.task_ignore_result is True
+
+
+def test_eager_mode_can_be_enabled():
+    configure_eager(celery_app, True)
+    assert celery_app.conf.task_always_eager is True
+    configure_eager(celery_app, False)
+    assert celery_app.conf.task_always_eager is False
+
+
+def test_build_app_applies_eager_setting_and_beat_schedule(monkeypatch):
+    monkeypatch.setattr("buyeros_worker.app.get_settings", lambda: WorkerSettings(eager=True, sweep_seconds=15))
+    app = build_app()
+    assert app.conf.task_always_eager is True
+    schedule = app.conf.beat_schedule["buyeros-sweep-expired"]
+    assert schedule["task"] == "buyeros.sweep"
+    assert schedule["schedule"] == 15.0
diff --git a/services/worker/tests/test_capability_blocked.py b/services/worker/tests/test_capability_blocked.py
new file mode 100644
index 0000000..5d2390a
--- /dev/null
+++ b/services/worker/tests/test_capability_blocked.py
@@ -0,0 +1,26 @@
+import asyncio
+
+from buyeros_worker.handlers.capability_blocked import BLOCKED_EVENTS, blocked
+from buyeros_worker.registry import get_handler
+
+
+def test_blocked_handlers_are_registered():
+    for event in BLOCKED_EVENTS:
+        assert get_handler(event) is blocked
+
+
+def test_blocked_result_makes_no_external_call():
+    result = asyncio.run(blocked(session=None, context=None, payload={}))
+    assert result.state == "blocked"
+    assert "no verified provider" in result.detail.lower()
+
+
+def test_blocked_uses_context_event_type():
+    result = asyncio.run(blocked(session=None, context={"event_type": "run.discover"}, payload={}))
+    assert result.state == "blocked"
+    assert "run.discover" in result.detail
+
+
+def test_blocked_without_a_run_id_skips_emission():
+    result = asyncio.run(blocked(session=object(), context={"event_type": "contact.submit"}, payload={}))
+    assert result.state == "blocked"
diff --git a/services/worker/tests/test_cli.py b/services/worker/tests/test_cli.py
new file mode 100644
index 0000000..8548f3d
--- /dev/null
+++ b/services/worker/tests/test_cli.py
@@ -0,0 +1,35 @@
+import pytest
+
+from buyeros_worker import cli
+
+
+def test_parser_requires_a_command():
+    with pytest.raises(SystemExit):
+        cli.build_parser().parse_args([])
+
+
+def test_parser_accepts_dispatch_and_sweep():
+    dispatch = cli.build_parser().parse_args(["dispatch", "--limit", "3", "--owner", "me"])
+    assert dispatch.command == "dispatch"
+    assert dispatch.limit == 3
+    assert dispatch.owner == "me"
+
+    sweep = cli.build_parser().parse_args(["sweep"])
+    assert sweep.command == "sweep"
+    assert sweep.limit is None
+    assert sweep.owner is None
+
+
+def test_main_runs_the_selected_command(monkeypatch, capsys):
+    calls = []
+    monkeypatch.setattr(cli, "_run", lambda command, limit, owner: calls.append((command, limit, owner)) or ["job:1"])
+    assert cli.main(["dispatch", "--limit", "2", "--owner", "me"]) == 0
+    assert calls == [("dispatch", 2, "me")]
+    assert "dispatch: published 1 intents" in capsys.readouterr().out
+
+
+def test_main_defaults_the_owner_from_the_command(monkeypatch):
+    calls = []
+    monkeypatch.setattr(cli, "_run", lambda command, limit, owner: calls.append((command, limit, owner)) or [])
+    cli.main(["sweep"])
+    assert calls == [("sweep", None, "buyeros-sweep")]
diff --git a/services/worker/tests/test_dispatcher.py b/services/worker/tests/test_dispatcher.py
new file mode 100644
index 0000000..01514a3
--- /dev/null
+++ b/services/worker/tests/test_dispatcher.py
@@ -0,0 +1,103 @@
+import asyncio
+from contextlib import asynccontextmanager
+from datetime import datetime, timedelta, timezone
+
+import pytest
+
+import buyeros_worker.dispatcher as dispatcher
+from buyeros_worker.dispatcher import claimable, dispatch_once, select_ready, sweep_once
+
+NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
+
+
+def _wire(monkeypatch, rows, workspaces=("ws-1",)):
+    async def fake_workspace_ids(engine):
+        return list(workspaces)
+
+    @asynccontextmanager
+    async def fake_tenant_session(engine, workspace_id):
+        yield object()
+
+    calls = []
+
+    async def fake_claim(session, owner, limit, now, lease_seconds, *, expired_only=False):
+        calls.append(expired_only)
+        return list(rows)
+
+    released = []
+
+    async def fake_release(session, intent_key):
+        released.append(intent_key)
+
+    monkeypatch.setattr(dispatcher, "_workspace_ids", fake_workspace_ids)
+    monkeypatch.setattr(dispatcher, "tenant_session", fake_tenant_session)
+    monkeypatch.setattr(dispatcher, "claim_outbox_rows", fake_claim)
+    monkeypatch.setattr(dispatcher, "release_claim", fake_release)
+    return calls, released
+
+
+def _row(intent_key="job:aaa", generation=7, workspace_id="ws-1"):
+    return {
+        "id": 1,
+        "workspace_id": workspace_id,
+        "intent_key": intent_key,
+        "event_type": "fetch.evidence",
+        "payload": {"url": "https://e.com"},
+        "fencing_generation": generation,
+    }
+
+
+def test_only_ready_and_expired_rows_are_selected():
+    rows = [
+        {"id": 1, "state": "ready", "lease_expires_at": None},
+        {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
+        {"id": 3, "state": "dispatched", "lease_expires_at": NOW - timedelta(seconds=1)},
+        {"id": 4, "state": "done", "lease_expires_at": None},
+        {"id": 5, "state": "failed", "lease_expires_at": NOW - timedelta(days=1)},
+    ]
+    assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]
+
+
+def test_batch_is_bounded():
+    rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
+    assert len(select_ready(rows, NOW, limit=5)) == 5
+
+
+def test_terminal_rows_are_never_claimable():
+    assert claimable("done", NOW - timedelta(days=1), NOW) is False
+    assert claimable("failed", None, NOW) is False
+
+
+def test_dispatch_once_publishes_only_opaque_ids(monkeypatch):
+    calls, _ = _wire(monkeypatch, [_row()])
+    messages = []
+    out = asyncio.run(dispatch_once(object(), messages.append, "owner", NOW, 10, 120))
+    assert out == ["job:aaa"]
+    assert messages == [{"intent_key": "job:aaa", "workspace_id": "ws-1", "generation": 7}]
+    assert calls == [False]
+
+
+def test_publish_failure_releases_the_claim(monkeypatch):
+    _, released = _wire(monkeypatch, [_row(generation=3)])
+
+    def boom(message):
+        raise RuntimeError("broker down")
+
+    with pytest.raises(RuntimeError):
+        asyncio.run(dispatch_once(object(), boom, "owner", NOW, 10, 120))
+    assert released == ["job:aaa"]
+
+
+def test_sweep_once_only_targets_expired_rows(monkeypatch):
+    calls, _ = _wire(monkeypatch, [_row(generation=2)])
+    messages = []
+    out = asyncio.run(sweep_once(object(), messages.append, "sweeper", NOW, 10, 120))
+    assert out == ["job:aaa"]
+    assert calls == [True]
+    assert messages[0] == {"intent_key": "job:aaa", "workspace_id": "ws-1", "generation": 2}
+
+
+def test_dispatch_fans_out_over_every_workspace(monkeypatch):
+    calls, _ = _wire(monkeypatch, [], workspaces=("ws-a", "ws-b", "ws-c"))
+    asyncio.run(dispatch_once(object(), lambda message: None, "owner", NOW, 10, 120))
+    assert calls == [False, False, False]
diff --git a/services/worker/tests/test_fetch_evidence.py b/services/worker/tests/test_fetch_evidence.py
new file mode 100644
index 0000000..d4b7923
--- /dev/null
+++ b/services/worker/tests/test_fetch_evidence.py
@@ -0,0 +1,95 @@
+import pytest
+
+from buyeros_worker.handlers.fetch_evidence import (
+    MAX_DECODED_BYTES,
+    FetchRejected,
+    handle,
+    validate_fetch,
+)
+from buyeros_worker.registry import get_handler
+
+
+def test_blocked_host_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("http://127.0.0.1/x", "text/html", 10)
+
+
+def test_private_host_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("http://10.0.0.1/x", "text/html", 10)
+
+
+def test_oversized_body_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "text/html", MAX_DECODED_BYTES + 1)
+
+
+def test_disallowed_content_type_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "application/octet-stream", 10)
+
+
+def test_valid_public_html_passes():
+    validate_fetch("https://example.com/x", "text/html; charset=utf-8", 100)
+
+
+def test_handler_is_registered():
+    assert get_handler("fetch.evidence") is not None
+
+
+def test_malformed_url_is_rejected_not_raised():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com:notaport/x", "text/html", 10)
+
+
+def test_handler_blocks_malformed_url():
+    result = handle(None, None, {"url": "https://example.com:notaport/x", "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
+
+
+def test_non_numeric_size_is_blocked_not_raised():
+    result = handle(None, None, {"url": "https://example.com/x", "content_type": "text/html", "size": "abc"})
+    assert result.state == "blocked"
+
+
+def test_none_payload_is_blocked_not_raised():
+    result = handle(None, None, None)
+    assert result.state == "blocked"
+
+
+def test_negative_size_is_rejected():
+    with pytest.raises(FetchRejected):
+        validate_fetch("https://example.com/x", "text/html", -1)
+
+
+@pytest.mark.parametrize("bad", [None, 123, [1], {"a": 1}, True])
+def test_non_string_url_is_blocked_not_raised(bad):
+    result = handle(None, None, {"url": bad, "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
+
+
+@pytest.mark.parametrize("bad", [None, 123, ["text/html"], True])
+def test_non_string_content_type_is_blocked_not_raised(bad):
+    result = handle(None, None, {"url": "https://example.com/x", "content_type": bad, "size": 1})
+    assert result.state == "blocked"
+
+
+@pytest.mark.parametrize(
+    "url",
+    [
+        "http://[::1]/x",
+        "https://[fe80::1]/x",
+        "http://[fc00::1]/x",
+        "http://[::ffff:10.0.0.1]/x",
+        "http:///x",
+    ],
+)
+def test_ipv6_and_empty_host_are_rejected(url):
+    with pytest.raises(FetchRejected):
+        validate_fetch(url, "text/html", 10)
+
+
+@pytest.mark.parametrize("url", ["http://[::1]/x", "http:///x"])
+def test_ipv6_and_empty_host_blocked_via_handle(url):
+    result = handle(None, None, {"url": url, "content_type": "text/html", "size": 1})
+    assert result.state == "blocked"
diff --git a/services/worker/tests/test_leases.py b/services/worker/tests/test_leases.py
new file mode 100644
index 0000000..b3741bb
--- /dev/null
+++ b/services/worker/tests/test_leases.py
@@ -0,0 +1,26 @@
+from datetime import datetime, timedelta, timezone
+
+from buyeros_worker.leases import can_claim, fence_ok, lease_expiry
+
+NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
+
+
+def test_free_lease_can_be_claimed():
+    assert can_claim("free", None, NOW) is True
+
+
+def test_unexpired_lease_cannot_be_claimed():
+    assert can_claim("held", NOW + timedelta(seconds=30), NOW) is False
+
+
+def test_expired_lease_can_be_claimed():
+    assert can_claim("held", NOW - timedelta(seconds=1), NOW) is True
+
+
+def test_lease_expiry_adds_seconds():
+    assert lease_expiry(NOW, 120) == NOW + timedelta(seconds=120)
+
+
+def test_fence_rejects_stale_worker():
+    assert fence_ok(3, 3) is True
+    assert fence_ok(2, 3) is False
diff --git a/services/worker/tests/test_registry.py b/services/worker/tests/test_registry.py
new file mode 100644
index 0000000..391c66e
--- /dev/null
+++ b/services/worker/tests/test_registry.py
@@ -0,0 +1,17 @@
+import pytest
+
+from buyeros_worker.registry import HANDLERS, HandlerResult, UnknownHandler, get_handler, register
+
+
+def test_unknown_handler_raises():
+    with pytest.raises(UnknownHandler):
+        get_handler("does.not.exist")
+
+
+def test_registration_makes_handler_available():
+    @register("test.event")
+    def handler(session, context, payload):
+        return HandlerResult(state="done", detail="ok")
+
+    assert get_handler("test.event") is handler
+    assert "test.event" in HANDLERS
diff --git a/services/worker/tests/test_run_emitter.py b/services/worker/tests/test_run_emitter.py
new file mode 100644
index 0000000..e7608d9
--- /dev/null
+++ b/services/worker/tests/test_run_emitter.py
@@ -0,0 +1,18 @@
+import asyncio
+import uuid
+
+from buyeros_worker.run_emitter import emit_run_event
+
+RUN_ID = "00000000-0000-4000-8000-0000000000aa"
+
+
+def test_emit_without_a_session_is_a_noop():
+    assert asyncio.run(emit_run_event(None, RUN_ID, "run.started")) == 0
+
+
+def test_emit_without_a_run_id_is_a_noop():
+    assert asyncio.run(emit_run_event(object(), None, "run.started")) == 0
+
+
+def test_emit_accepts_uuid_or_string_run_ids():
+    assert asyncio.run(emit_run_event(None, uuid.UUID(RUN_ID), "run.started")) == 0
diff --git a/services/worker/tests/test_run_lifecycle.py b/services/worker/tests/test_run_lifecycle.py
new file mode 100644
index 0000000..58d11c1
--- /dev/null
+++ b/services/worker/tests/test_run_lifecycle.py
@@ -0,0 +1,76 @@
+from buyeros_worker.run_lifecycle import halted, terminal, transition_run
+
+
+def test_valid_progressions():
+    assert transition_run("queued", "start") == "running"
+    assert transition_run("running", "complete") == "completed"
+    assert transition_run("running", "cancel") == "cancel_requested"
+
+
+def test_terminal_states_do_not_regress():
+    assert transition_run("completed", "start") == "completed"
+    assert transition_run("cancelled", "start") == "cancelled"
+
+
+def test_cancel_requested_is_not_terminal():
+    assert terminal("cancel_requested") is False
+    assert terminal("cancelled") is True
+    assert terminal("completed") is True
+
+
+def test_unknown_event_is_ignored():
+    assert transition_run("running", "bogus") == "running"
+
+
+def test_failed_and_paused_budget_are_retryable():
+    assert transition_run("failed", "retry") == "queued"
+    assert transition_run("partial", "retry") == "queued"
+    assert transition_run("paused_budget", "retry") == "queued"
+    assert transition_run("paused_budget", "resume") == "running"
+
+
+def test_only_completed_and_cancelled_are_terminal():
+    assert terminal("completed") is True
+    assert terminal("cancelled") is True
+    assert terminal("failed") is False
+    assert terminal("partial") is False
+    assert terminal("paused_budget") is False
+
+
+def test_terminal_states_never_regress_even_on_retry():
+    assert transition_run("completed", "retry") == "completed"
+    assert transition_run("cancelled", "retry") == "cancelled"
+
+
+def test_remaining_edges():
+    assert transition_run("draft", "enqueue") == "queued"
+    assert transition_run("running", "fail") == "failed"
+    assert transition_run("running", "partial") == "partial"
+    assert transition_run("running", "pause_budget") == "paused_budget"
+    assert transition_run("cancel_requested", "cancel") == "cancelled"
+
+
+def test_capability_block_reaches_the_blocked_state():
+    assert transition_run("draft", "capability_block") == "blocked"
+    assert transition_run("queued", "capability_block") == "blocked"
+    assert transition_run("running", "capability_block") == "blocked"
+
+
+def test_blocked_is_halting_but_not_terminal():
+    assert terminal("blocked") is False
+    assert halted("blocked") is True
+
+
+def test_blocked_never_regresses_or_retries():
+    assert transition_run("blocked", "start") == "blocked"
+    assert transition_run("blocked", "retry") == "blocked"
+    assert transition_run("blocked", "capability_block") == "blocked"
+
+
+def test_halted_covers_completed_cancelled_and_blocked():
+    assert halted("completed") is True
+    assert halted("cancelled") is True
+    assert halted("blocked") is True
+    assert halted("failed") is False
+    assert halted("running") is False
+
diff --git a/services/worker/tests/test_tasks.py b/services/worker/tests/test_tasks.py
new file mode 100644
index 0000000..36ea966
--- /dev/null
+++ b/services/worker/tests/test_tasks.py
@@ -0,0 +1,199 @@
+import asyncio
+from contextlib import asynccontextmanager
+
+import pytest
+
+import buyeros_worker.engine as engine_mod
+import buyeros_worker.tasks as tasks
+from buyeros_worker.registry import HandlerResult, UnknownHandler
+
+
+class FakeEngine:
+    def __init__(self):
+        self.disposed = False
+
+    async def dispose(self):
+        self.disposed = True
+
+
+def _patch_engine(monkeypatch):
+    created = []
+
+    def fake_create_engine():
+        engine = FakeEngine()
+        created.append(engine)
+        return engine
+
+    @asynccontextmanager
+    async def fake_tenant_session(engine, workspace_id):
+        yield object()
+
+    monkeypatch.setattr(tasks, "create_engine", fake_create_engine)
+    monkeypatch.setattr(tasks, "tenant_session", fake_tenant_session)
+    return created
+
+
+def _row(state="dispatched", generation=1, event_type="fetch.evidence", payload=None):
+    return {"state": state, "event_type": event_type, "payload": payload or {}, "fencing_generation": generation}
+
+
+def test_each_invocation_creates_and_disposes_its_own_engine(monkeypatch):
+    created = _patch_engine(monkeypatch)
+
+    async def fake_run_intent(session, context, intent_key, generation):
+        return "done"
+
+    monkeypatch.setattr(tasks, "run_intent", fake_run_intent)
+    assert tasks.execute_intent_sync("job:1", "ws", 1) == "done"
+    assert tasks.execute_intent_sync("job:2", "ws", 1) == "done"
+    assert len(created) == 2
+    assert all(engine.disposed for engine in created)
+
+
+def test_stale_fencing_returns_stale_and_disposes(monkeypatch):
+    created = _patch_engine(monkeypatch)
+
+    async def fake_run_intent(session, context, intent_key, generation):
+        raise tasks.StaleFenced()
+
+    monkeypatch.setattr(tasks, "run_intent", fake_run_intent)
+    assert tasks.execute_intent_sync("job:1", "ws", 1) == "stale"
+    assert created[0].disposed is True
+
+
+def test_run_intent_is_a_noop_for_a_terminal_row(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row(state="done")
+
+    called = []
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda *args: called.append(event_type))
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "duplicate"
+    assert called == []
+
+
+def test_run_intent_rejects_a_stale_generation_without_running_the_handler(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row(generation=9)
+
+    called = []
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda *args: called.append(event_type))
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "stale"
+    assert called == []
+
+
+def test_run_intent_marks_the_row_done(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row()
+
+    terminal = []
+
+    async def fake_mark(session, intent_key, generation, state):
+        terminal.append((intent_key, generation, state))
+        return 1
+
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
+    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda s, c, p: HandlerResult(state="done"))
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "done"
+    assert terminal == [("job:1", 1, "done")]
+
+
+def test_run_intent_marks_blocked_as_terminal_failed(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row(event_type="run.discover")
+
+    terminal = []
+
+    async def fake_mark(session, intent_key, generation, state):
+        terminal.append(state)
+        return 1
+
+    async def handler(session, context, payload):
+        return HandlerResult(state="blocked")
+
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
+    monkeypatch.setattr(tasks, "get_handler", lambda event_type: handler)
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "blocked"
+    assert terminal == ["failed"]
+
+
+def test_run_intent_requests_a_retry_without_a_terminal_write(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row()
+
+    called = []
+
+    async def fake_mark(*args):
+        called.append(args)
+        return 1
+
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
+    monkeypatch.setattr(tasks, "get_handler", lambda event_type: lambda s, c, p: HandlerResult(state="retry"))
+    with pytest.raises(tasks.RetryRequested):
+        asyncio.run(tasks.run_intent(object(), {}, "job:1", 1))
+    assert called == []
+
+
+def test_run_intent_marks_unknown_handlers_terminal(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row(event_type="nope.nope")
+
+    terminal = []
+
+    async def fake_mark(session, intent_key, generation, state):
+        terminal.append(state)
+        return 1
+
+    def fake_get_handler(event_type):
+        raise UnknownHandler(event_type)
+
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
+    monkeypatch.setattr(tasks, "get_handler", fake_get_handler)
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "unknown_handler"
+    assert terminal == ["failed"]
+
+
+def test_run_intent_reports_unknown_intent(monkeypatch):
+    async def fake_load(session, intent_key):
+        return None
+
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    assert asyncio.run(tasks.run_intent(object(), {}, "job:1", 1)) == "unknown_intent"
+
+
+def test_run_intent_passes_the_db_event_type_into_context(monkeypatch):
+    async def fake_load(session, intent_key):
+        return _row(event_type="fetch.evidence")
+
+    seen = {}
+
+    def fake_get_handler(event_type):
+        def handler(session, context, payload):
+            seen["context"] = context
+            return HandlerResult(state="done")
+
+        return handler
+
+    async def fake_mark(session, intent_key, generation, state):
+        return 1
+
+    monkeypatch.setattr(tasks, "load_intent", fake_load)
+    monkeypatch.setattr(tasks, "mark_outbox_terminal", fake_mark)
+    monkeypatch.setattr(tasks, "get_handler", fake_get_handler)
+    asyncio.run(tasks.run_intent(object(), {"workspace_id": "ws"}, "job:1", 1))
+    assert seen["context"] == {"workspace_id": "ws", "event_type": "fetch.evidence"}
+
+
+def test_worker_shutdown_disposes_the_in_flight_engine():
+    from celery import signals
+
+    engine = FakeEngine()
+    engine_mod.set_active_engine(engine)
+    signals.worker_shutdown.send(sender=None)
+    assert engine.disposed is True
+    assert engine_mod._active_engine is None
diff --git a/services/worker/tests/test_valkey_integration.py b/services/worker/tests/test_valkey_integration.py
new file mode 100644
index 0000000..6f1c5b4
--- /dev/null
+++ b/services/worker/tests/test_valkey_integration.py
@@ -0,0 +1,56 @@
+import shutil
+import subprocess
+import time
+import uuid
+from datetime import datetime, timezone
+
+import pytest
+
+from buyeros_worker.app import celery_app
+from buyeros_worker.dispatcher import select_ready
+
+
+def _valkey_container():
+    if shutil.which("docker") is None:
+        pytest.skip("docker unavailable")
+    name = f"buyeros-valkey-{uuid.uuid4().hex[:8]}"
+    run = subprocess.run(
+        ["docker", "run", "-d", "--name", name, "-p", "127.0.0.1::6379", "valkey/valkey:8"],
+        capture_output=True,
+        text=True,
+    )
+    if run.returncode != 0:
+        pytest.skip(f"could not start valkey: {run.stderr.strip()}")
+    return name
+
+
+def test_broker_is_reachable_and_dispatcher_selection_is_pure():
+    original = celery_app.conf.broker_url
+    name = None
+    try:
+        name = _valkey_container()
+        port_output = subprocess.run(["docker", "port", name, "6379"], capture_output=True, text=True).stdout.strip()
+        if not port_output:
+            pytest.skip(f"could not resolve valkey port for {name}")
+        port = port_output.splitlines()[0].rsplit(":", 1)[1]
+        celery_app.conf.broker_url = f"redis://127.0.0.1:{port}/0"
+        for _ in range(15):
+            try:
+                with celery_app.connection() as conn:
+                    conn.ensure_connection(max_retries=1)
+            except Exception:
+                time.sleep(1)
+            else:
+                break
+        else:
+            pytest.skip("valkey broker did not become ready")
+        assert celery_app.conf.broker_url.endswith("/0")
+        selected = select_ready(
+            [{"id": 1, "state": "ready", "lease_expires_at": None}],
+            datetime.now(timezone.utc),
+        )
+        assert selected[0]["id"] == 1
+    finally:
+        celery_app.conf.broker_url = original
+        if name is not None:
+            subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)
diff --git a/services/worker/tests/test_worker_integrity_db.py b/services/worker/tests/test_worker_integrity_db.py
new file mode 100644
index 0000000..b5b54b7
--- /dev/null
+++ b/services/worker/tests/test_worker_integrity_db.py
@@ -0,0 +1,170 @@
+"""DB-backed integrity tests for the worker/dispatcher (RLS runtime role).
+
+Each test runs the real worker code against the disposable PostgreSQL from
+``tests/conftest.py`` as the least-privilege ``buyeros_api`` role.
+"""
+
+import asyncio
+from datetime import datetime, timedelta, timezone
+from pathlib import Path
+
+import psycopg
+
+from buyeros_worker.dispatcher import dispatch_once, sweep_once
+from buyeros_worker.engine import create_engine
+from buyeros_worker.tasks import execute_intent_sync
+from tests.conftest import RUN_A, WS_A, WS_B, reset_tenant, seed_outbox, seed_run
+
+NOW = datetime.now(timezone.utc)
+
+
+def _scalar(conn, sql, *params):
+    return conn.execute(sql, params).fetchone()[0]
+
+
+async def _dispatch(publish, now, *, limit=10, lease_seconds=60):
+    engine = create_engine()
+    try:
+        return await dispatch_once(engine, publish, "test-dispatcher", now, limit, lease_seconds)
+    finally:
+        await engine.dispose()
+
+
+async def _sweep(publish, now, *, limit=10, lease_seconds=60):
+    engine = create_engine()
+    try:
+        return await sweep_once(engine, publish, "test-sweeper", now, limit, lease_seconds)
+    finally:
+        await engine.dispose()
+
+
+def test_fencing_rejects_a_stale_generation_with_no_writes(worker_database_url, pg_dsn):
+    intent = "job:fence"
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        reset_tenant(conn)
+        seed_run(conn)
+        seed_outbox(
+            conn,
+            intent_key=intent,
+            payload={"url": "https://example.com/x", "content_type": "text/html", "size": 10, "run_id": RUN_A},
+            state="dispatched",
+            generation=1,
+            lease_expires_at=NOW + timedelta(hours=1),
+        )
+
+    assert execute_intent_sync(intent, WS_A, 0) == "stale"
+
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        assert _scalar(conn, "SELECT count(*) FROM run_events WHERE run_id = %s", RUN_A) == 0
+        assert conn.execute(
+            "SELECT state, fencing_generation FROM outbox_events WHERE intent_key = %s", (intent,)
+        ).fetchone() == ("dispatched", 1)
+
+    # The generation the worker presents is what decides; the matching one works.
+    assert execute_intent_sync(intent, WS_A, 1) == "done"
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "done"
+
+
+def test_duplicate_delivery_of_a_terminal_intent_is_a_noop(worker_database_url, pg_dsn):
+    intent = "job:duplicate"
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        reset_tenant(conn)
+        seed_run(conn)
+        seed_outbox(
+            conn,
+            intent_key=intent,
+            event_type="run.discover",
+            payload={"run_id": RUN_A},
+            state="dispatched",
+            generation=1,
+            lease_expires_at=NOW + timedelta(hours=1),
+        )
+
+    assert execute_intent_sync(intent, WS_A, 1) == "blocked"
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "failed"
+        assert _scalar(conn, "SELECT count(*) FROM run_events WHERE run_id = %s", RUN_A) == 1
+
+    assert execute_intent_sync(intent, WS_A, 1) == "duplicate"
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        assert _scalar(conn, "SELECT count(*) FROM run_events WHERE run_id = %s", RUN_A) == 1
+        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "failed"
+
+
+def test_expired_in_progress_intent_is_reclaimed_and_reenqueued(worker_database_url, pg_dsn):
+    intent = "job:sweep"
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        reset_tenant(conn)
+        seed_outbox(
+            conn,
+            intent_key=intent,
+            payload={"url": "https://example.com/x", "content_type": "text/html", "size": 1},
+            state="ready",
+        )
+
+    published = []
+    base = datetime.now(timezone.utc)
+
+    assert asyncio.run(_dispatch(published.append, base)) == [intent]
+    # A fresh lease is not re-dispatched.
+    assert asyncio.run(_dispatch(published.append, base + timedelta(seconds=5))) == []
+    # The publish was "lost" (process died between commit and enqueue). After the
+    # lease expires the sweeper re-enqueues it exactly once for the cycle.
+    assert asyncio.run(_sweep(published.append, base + timedelta(seconds=61))) == [intent]
+    assert asyncio.run(_sweep(published.append, base + timedelta(seconds=62))) == []
+
+    assert [message["intent_key"] for message in published] == [intent, intent]
+    assert [message["generation"] for message in published] == [1, 2]
+    assert set(published[0]) == {"intent_key", "workspace_id", "generation"}
+
+
+def test_dispatcher_claims_each_workspace_under_its_own_tenant_context(worker_database_url, pg_dsn):
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        reset_tenant(conn, WS_A)
+        reset_tenant(conn, WS_B)
+        seed_outbox(conn, intent_key="job:a", payload={"url": "https://a.example"}, workspace_id=WS_A)
+        seed_outbox(conn, intent_key="job:b", payload={"url": "https://b.example"}, workspace_id=WS_B)
+
+    published = []
+    asyncio.run(_dispatch(published.append, datetime.now(timezone.utc)))
+
+    by_intent = {message["intent_key"]: message["workspace_id"] for message in published}
+    assert by_intent == {"job:a": WS_A, "job:b": WS_B}
+
+
+def test_blocked_handler_emits_exactly_one_event_and_makes_no_external_call(worker_database_url, pg_dsn):
+    import buyeros_worker.handlers.capability_blocked as capability_blocked
+
+    intent = "job:blocked"
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        reset_tenant(conn)
+        seed_run(conn, status="running")
+        seed_outbox(
+            conn,
+            intent_key=intent,
+            event_type="run.discover",
+            payload={"run_id": RUN_A, "target_companies": 5},
+            state="dispatched",
+            generation=1,
+            lease_expires_at=NOW + timedelta(hours=1),
+        )
+
+    assert execute_intent_sync(intent, WS_A, 1) == "blocked"
+
+    with psycopg.connect(pg_dsn, autocommit=True) as conn:
+        assert _scalar(conn, "SELECT state FROM outbox_events WHERE intent_key = %s", intent) == "failed"
+        assert _scalar(conn, "SELECT status FROM search_runs WHERE id = %s", RUN_A) == "blocked"
+        events = conn.execute(
+            "SELECT event_type, sequence, payload FROM run_events WHERE run_id = %s ORDER BY sequence", (RUN_A,)
+        ).fetchall()
+
+    assert len(events) == 1
+    assert events[0][0] == "capability_blocked"
+    assert events[0][1] == 1
+    assert events[0][2]["event_type"] == "run.discover"
+
+    # No provider client is imported anywhere in the fail-closed handler.
+    source = Path(capability_blocked.__file__).read_text(encoding="utf-8")
+    for forbidden in ("http", "urllib", "requests", "socket", "httpx", "aiohttp"):
+        assert forbidden not in source, forbidden

```
## lockfile stat (contents omitted)
```
 services/api/uv.lock    |   2 +-
 services/worker/uv.lock | 711 ++++++++++++++++++++++++++++++++++++++++++++++++
 2 files changed, 712 insertions(+), 1 deletion(-)
```
