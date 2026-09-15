# Task 4 Report: Handler registry and result types

## Status
COMPLETE

## Commit
- Local commit: `6c70b28d691d3f7f60cf3f2d8d5ed3f4aa02bd21` (`feat(worker): handler registry`)
- Branch: `p8-worker-dispatcher` (not created/switched; no push/merge/rebase)

## Files
- Created: `services/worker/buyeros_worker/registry.py`
- Created: `services/worker/tests/test_registry.py`
- No other files modified or staged.

## TDD Step Order (followed exactly)
1. Wrote failing test `tests/test_registry.py` (transcribed verbatim from brief).
2. Ran `uv run pytest tests/test_registry.py -v` → FAIL with
   `ModuleNotFoundError: No module named 'buyeros_worker.registry'` (collection error, as expected).
3. Wrote minimal implementation `buyeros_worker/registry.py` (transcribed verbatim from brief):
   `UnknownHandler`, frozen dataclass `HandlerResult(state, detail="")`, `HANDLERS: dict[str, Callable]`,
   `register(event_type)` decorator, `get_handler(event_type)` raising `UnknownHandler`.
4. Ran `uv run pytest tests/test_registry.py -v` → 2 passed.
5. Ran full worker suite `uv run pytest -v` → 10 passed, 1 pre-existing warning.
6. Committed only the two new files.

## Test Summary
`uv run pytest` from `services/worker`: **10 passed, 1 warning** (target file: 2 passed).
The single warning is pre-existing `DeprecationWarning: 'asyncio.get_event_loop_policy' is deprecated`
emitted from the installed `pytest_asyncio` plugin, unrelated to this change.

## Interfaces Produced
- `HandlerResult(state: str, detail: str = "")` — frozen dataclass.
- `register(event_type: str)` — decorator registering a handler and returning it.
- `get_handler(event_type: str) -> Callable` — raises `UnknownHandler`.
- `HANDLERS: dict[str, Callable]` — module-level registry.
- `UnknownHandler(Exception)`.

## Concerns
- None blocking. Tests 5/6 can register handlers into `HANDLERS`; Task 9 resolves via `get_handler`.
- Registry is process-global mutable state (by design per brief); handlers registered at import time
  must not collide across tests (the test uses a namespaced `test.event` key).
