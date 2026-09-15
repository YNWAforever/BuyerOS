# P8 worker/dispatcher — FIX WAVE report

Branch: `p8-worker-dispatcher` (no branch switch, no remote, no push/merge/rebase).
Base at start of wave: `c715715`. All commits local only.

## Status

COMPLETE. Every A–E finding in the brief is implemented, committed and tested.
No unresolved findings (see "Not resolved / limitations" for the one deliberate
partial test technique and the pre-existing deferral).

## Commands run (real output)

- `uv run pytest -q` (cwd `services/worker`, before): `55 passed, 1 warning in 1.15s`
- `uv run pytest -q` (cwd `services/api`, before): `108 passed, 20 warnings in 3.64s`
- `uv sync` (cwd `services/worker`): rebuilt `buyeros-api`/`buyeros-worker`; installed console script.
- `uv run pytest -q` (cwd `services/worker`, final): `85 passed, 4 warnings in 48.81s`
- `uv run pytest -q` (cwd `services/api`, final): `116 passed, 20 warnings in 36.18s`
- `uv run buyeros-worker --help` (cwd `services/worker`):
  ```
  usage: buyeros-worker [-h] {dispatch,sweep} ...
  BuyerOS outbox dispatcher and recovery sweeper
  positional arguments:
    {dispatch,sweep}
      dispatch        claim and publish ready outbox intents
      sweep           re-enqueue intents whose lease expired
  ```
- API tests start a disposable `postgres:16` container automatically (Docker 29.7.2 present).

## Commits by area

| SHA | Area | Message |
|---|---|---|
| `68bb1f9` | A3, B7(grant) | feat(db): terminal outbox states, claim index and dispatcher workspace read |
| `443c970` | C10 | feat(worker): blocked run state and atomic run-event emission |
| `05979d7` | A1, A2, A4, A5 | feat(worker): enforce fencing and resolve intents from the database |
| `a0950e9` | B6, B7, B8, B9 | feat(worker): RLS-aware dispatcher, re-enqueueing sweeper and CLI entrypoints |
| `24933d3` | D (prereq fixes) | fix(api): settable tenant context and complete model registration |
| `8c62025` | D11 | test(worker): db-backed fencing, idempotency, sweeper and blocked-handler tests |
| `b4af79a` | E13 | docs: align p8 plan with implemented worker execution and dispatcher |

## A. Worker execution integrity

- **A1 fencing enforced.** `tasks.load_intent` selects the `outbox_events` row by
  `intent_key` **under the tenant session** with `FOR UPDATE`; `run_intent`
  compares generations with `leases.fence_ok` and returns `"stale"` with no
  handler execution and no writes when it does not match. `mark_outbox_terminal`
  is also generation-guarded (`WHERE fencing_generation = :generation`).
- **A2 message is not the instruction source.** Celery task signature is now
  `execute_intent(intent_key, workspace_id, generation)`. `dispatcher` publishes
  exactly `{intent_key, workspace_id, generation}`; event type and payload are
  read from the DB row. Verified by unit test + DB test.
- **A3 terminal state + idempotency.** New migration
  `services/api/alembic/versions/0007_outbox_terminal_state.py` (owned by
  `buyeros_api`) adds `ck_outbox_events_state`
  (`ready|dispatched|done|failed`), index `ix_outbox_events_state_lease_expires_at`,
  and `GRANT SELECT ON workspaces`. Claim predicate is an allow-list
  (`state='ready' OR (state='dispatched' AND lease_expires_at <= now)`), so
  terminal rows are never re-claimed. The terminal write commits in the same
  transaction as the work; a second delivery of a terminal row returns
  `"duplicate"` (no-op).
- **A4 engine lifecycle.** `buyeros_worker/engine.py`: one engine is created and
  disposed per invocation on the same loop (`_with_engine`); `set_active_engine`
  tracks the in-flight engine and `dispose_engine` is wired to Celery
  `worker_shutdown` (`signals.worker_shutdown.connect`, `weak=False`). Tests:
  `test_each_invocation_creates_and_disposes_its_own_engine`,
  `test_worker_shutdown_disposes_the_in_flight_engine`.
- **A5 settings.** `build_app` calls `configure_eager(app, settings.eager)`;
  `claim_outbox_rows` takes `lease_seconds` (no hardcoded 120); CLI/tasks pass
  `WorkerSettings.lease_seconds`.

## B. Dispatcher, sweeper, entrypoints

- **B6 single transaction boundary.** `_dispatch_workspace` claims
  (lease + `fencing_generation` bump + `dispatched_at` + `state='dispatched'`)
  and commits via `tenant_session` **before** `publish`. On publish failure
  `release_claim` returns the row to `ready`; a lost publish is recovered by the
  lease expiring. Duplicate publish is harmless (A1/A3).
- **B7 RLS.** Dispatcher runs as `NOBYPASSRLS`; it enumerates tenants from
  `workspaces` (non-RLS root, read grant in 0007) and opens one transaction-local
  tenant context per workspace before claiming. Documented in `dispatcher.py`
  module docstring. DB test `test_dispatcher_claims_each_workspace_under_its_own_tenant_context`.
- **B8 sweeper re-enqueues.** `sweep_once` re-claims expired `dispatched` rows
  (bumping generation, refreshing lease) and publishes them. DB test
  `test_expired_in_progress_intent_is_reclaimed_and_reenqueued` covers the
  "kill between commit and enqueue" case (lease expiry then exactly-once
  re-enqueue per cycle).
- **B9 entrypoints.** `buyeros_worker/cli.py` (`dispatch`, `sweep`) registered as
  console script `buyeros-worker` in `services/worker/pyproject.toml`; Celery
  `beat_schedule` ("buyeros-sweep-expired" → `buyeros.sweep`) plus the `sweep`
  task. No deployment.

## C. Run/event emission

- `buyeros_worker/run_emitter.py::emit_run_event` runs on the caller's tenant
  transaction: `SELECT ... FOR UPDATE` on `search_runs`, `next_sequence` +
  `apply_event`, `transition_run`, then one `run_events` insert.
- `run_lifecycle` gained a `blocked` state, `BLOCKED`, `halted()` and
  `capability_block` edges. **`TERMINAL = {completed, cancelled}` is unchanged**
  (owner decision); `failed`/`partial`/`paused_budget` remain retryable.
- `capability_blocked.blocked` is now async: it transitions the run to `blocked`
  and emits exactly one `capability_blocked` event. `run.discover` /
  `contact.submit` / `draft.generate` still make **no external call**.
  `fetch.evidence` stays validation-only (no live fetch).

## D. Tests

- Worker DB tests reuse a disposable-Postgres conftest
  (`services/worker/tests/conftest.py`, `tests/test_worker_integrity_db.py`),
  running against the least-privilege `buyeros_api` role so RLS is exercised:
  1. stale generation → `"stale"`, zero `run_events`, outbox untouched
     (matching generation then succeeds);
  2. duplicate delivery of a terminal intent → `"duplicate"`, one event only;
  3. expired in-progress intent re-claimed and re-enqueued exactly once;
  4. blocked handler → run `blocked`, outbox `failed`, exactly one event, no
     external call;
  5. dispatcher claims each workspace under its own tenant context.
- Unit tests updated/added: `test_tasks.py`, `test_dispatcher.py`, `test_app.py`,
  `test_run_lifecycle.py`, `test_run_emitter.py`, `test_capability_blocked.py`,
  `test_cli.py`, `test_outbox_terminal_state.py`, `test_tenant_context.py`.
- Existing tests all pass (worker 85, api 116).

## E. Docs

- `docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md`:
  Task 7 (TERMINAL/retry/blocked/halted + run_emitter), Task 8 (RLS fan-out,
  persisted `intent_key`, terminal states, lease from settings, sweeper
  re-enqueue, no `store.py`), Task 9 (DB-sourced intent, fencing, per-invocation
  engine + shutdown hook, opaque message), and Self-Review updated.
- `docs/buyeros/SHA256SUMS.txt`: plan hash recomputed in place
  (`2bfb1c9232ca0a293a68675d3fb13065798eca592f9eb717a01a2eb78f9bdf27`), order
  preserved; no new docs files, so no additions.

## Deviations

1. **Editable path dependency + worker packaging.** `services/worker/pyproject.toml`
   now declares `buyeros-api = { path = "../api", editable = true }`, a
   `[build-system]` (hatchling) and `[project.scripts]`. Reason: the previous
   non-editable wheel copy of `buyeros_api` did not reflect API source changes,
   and the console script would not install without packaging. Lockfile updated
   (`services/worker/uv.lock`).
2. **Two latent API bugs fixed** (revealed by the new DB tests):
   - `db/session.py` used `SET LOCAL app.workspace_id = :ws`, which is a syntax
     error with a bound parameter; now `SELECT set_config('app.workspace_id', :ws, true)`.
   - `db/__init__.py` now imports all model modules, so `Base.metadata` is
     complete (fixes the `SearchRun` mapper FK resolution error and the logged
     "worker_leases absent from autogenerate" gap).
3. **Scope extension on docs:** Task 9 + Self-Review were updated in addition to
   the literal Task 7/8, because the task signature and engine lifecycle changed.
4. **Windows test-only event loop pin:** `services/worker/tests/conftest.py` sets
   `WindowsSelectorEventLoopPolicy`, because psycopg's async driver cannot run on
   the Windows default Proactor loop. Production is unaffected.
5. **Blocked handler outbox state** is mapped to terminal `failed` (the only
   non-`done` terminal state). The run itself is `blocked`, not terminal
   (`terminal("blocked") is False`), preserving the owner's TERMINAL set.

## Not resolved / limitations

- The "no external call" assertion for blocked handlers combines behavioural
  assertions (exactly one DB event, no run-external effects) with a static check
  that the handler module imports no network client. A runtime socket trap was
  deliberately not used because it would intercept psycopg's own connection.
- `fetch.evidence` remains validation-only with no live HTTP client (explicit
  scope constraint, not a regression).
