# Task 9 Report: Celery task entrypoint (ack after commit)

## Status
COMPLETE

## Commit
`24c615b73ba3bcae0badb7bed386589b9cf98c50`
Message: `feat(worker): celery task entrypoint with commit-before-ack`
Branch: `p8-worker-dispatcher` (local only; no push/merge/rebase)

## Files
- `services/worker/buyeros_worker/tasks.py` (new)
- `services/worker/tests/test_tasks.py` (new)

No other files touched.

## Implementation
Transcribed the brief's code faithfully:
- `run_intent(handler, payload, session, context) -> str` — awaits coroutine handlers,
  commits the session, returns `result.state`; nothing is committed if the handler raises.
- `execute_intent(intent_key, event_type, payload, generation) -> str` — Celery task
  `buyeros.execute_intent`, `acks_late=True`, resolves the handler via `get_handler`,
  opens `buyeros_api.db.session.tenant_session(engine, payload["workspace_id"])`,
  runs `run_intent`, and returns the terminal state.
- `_engine()` — lazily builds the async engine from `buyeros_api.settings.get_settings().database_url`.

Extra required change (resolves earlier cross-task review finding): module-level
`from . import handlers  # noqa: F401  (import registers handlers)` in `tasks.py`, so the
production entrypoint imports the handlers package and its handlers self-register.
`handlers/__init__.py` was NOT changed.

## Tests
`services/worker/tests/test_tasks.py` transcribed from the brief, including the `FakeSession`
double and both `asyncio.run(...)` tests. No real database, broker, or network access; the
Celery task object is never invoked in tests.

## Verification (evidence)
- `uv run pytest tests/test_tasks.py -v` → `2 passed, 1 warning` (warning: pytest-asyncio
  `get_event_loop_policy` deprecation on Python 3.14; unrelated to this change).
- `uv run pytest -q` (full worker suite) → `53 passed, 1 warning`.

## Concerns
- None blocking. The `execute_intent` task body (`_engine`, `tenant_session`, `asyncio.run`)
  is not exercised by tests (per brief); it is expected to be covered in a later
  integration/e2e task.
- The brief's test file imports `UnknownHandler` without using it; kept verbatim as the brief
  is authoritative. No linter is configured in `services/worker`, so no lint failure results.

## Corrective fix (review findings: engine leak, retry ack, poison redelivery)

### Status
COMPLETE

### Changes
- `services/worker/buyeros_worker/tasks.py`
  - Replaced per-call `_engine()` with a module-level lazy singleton `get_engine()`
    guarded by a `threading.Lock`, plus `dispose_engine()` for shutdown.
  - Added pure helper `resolve_handler_state(event_type)` returning `"unknown_handler"`
    or `"known"`, used by `execute_intent` so unknown handlers return terminally
    instead of raising (poison-message redelivery).
  - `execute_intent` is now a bound task (`bind=True`) so it can call
    `self.retry(countdown=30, max_retries=3)` when the handler state is `"retry"`,
    instead of acking the retry intent.
  - Task name `buyeros.execute_intent` and `acks_late=True` unchanged. `run_intent`
    contract unchanged.
- `services/worker/tests/test_tasks.py`
  - Removed unused `pytest` and `UnknownHandler` imports.
  - Added `test_unknown_handler_state_is_terminal` exercising the guard logic directly.

### Verification (evidence)
- `uv run pytest -q` (from `services/worker`) → `54 passed, 1 warning`
  (pre-existing pytest-asyncio deprecation warning; unrelated).

### Concerns
- `dispose_engine()` resets the module global to `None` but does not `await engine.dispose()`
  (sync shutdown hook); the instruction specified this exact body. A real worker shutdown
  should `await` dispose via an async hook.
