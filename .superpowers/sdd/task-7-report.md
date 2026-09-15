# Task 7 report: Run lifecycle transitions and event emission

## Status
COMPLETE

## Commit
`bfd2c815d871c2df0e071d47ee5f876c762ebafd` — `feat(worker): run lifecycle transition table` (local only, branch `p8-worker-dispatcher`; not pushed)

## Files
- Created: `services/worker/buyeros_worker/run_lifecycle.py`
- Created: `services/worker/tests/test_run_lifecycle.py`

No other files touched.

## TDD steps
1. Wrote failing test — `services/worker/tests/test_run_lifecycle.py` transcribed verbatim from the brief.
2. Verified RED — `uv run pytest tests/test_run_lifecycle.py -v` → `ModuleNotFoundError: No module named 'buyeros_worker.run_lifecycle'` (collection error, expected).
3. Wrote minimal implementation — `RUN_STATES`, `TERMINAL`, `_TRANSITIONS`, `terminal`, `transition_run`, transcribed verbatim from the brief.
4. Verified GREEN — 4 passed.
5. Committed the two files only.

## Test summary
`uv run pytest tests/test_run_lifecycle.py -v` → 4 passed. Full worker suite `uv run pytest -q` → 43 passed, 1 pre-existing DeprecationWarning from pytest-asyncio.

## Notes / decisions
- `next_sequence`/`apply_event` were listed as consumed interfaces but are not exercised by this task's tests; no code paths in this task call them. Nothing imported from `buyeros_api`.
- LF→CRLF conversion warnings emitted by git on commit (repo autocrlf behavior); no content impact.

## Concerns
- None functional. The module is pure/self-contained; later tasks must wire `transition_run` into actual DB/run_events writes.

---

# Task 7 corrective fix: retryable failures

## Status
COMPLETE

## Commit
`77df73cd2eeaa2308de482b293e834579b8275e2` — `fix(worker): make failed/partial/paused_budget runs retryable` (local only, branch `p8-worker-dispatcher`; not pushed)

## Rationale
Owner decision resolved the plan contradiction: runs now use "retryable failures" semantics, so `failed` is no longer terminal.

## Changes
`services/worker/buyeros_worker/run_lifecycle.py`:
- `TERMINAL = {"completed", "cancelled"}` (`failed` removed).
- `RUN_STATES` unchanged.
- Added transitions `(paused_budget, retry) -> queued` and `(paused_budget, resume) -> running`; existing `(failed, retry) -> queued` and `(partial, retry) -> queued` retained.
- `terminal()`/`transition_run()` unchanged: terminal states never regress, unknown events return the current state.

`services/worker/tests/test_run_lifecycle.py`:
- Updated `test_terminal_states_do_not_regress` to assert on `cancelled` instead of `failed` (no longer terminal).
- Added `test_failed_and_paused_budget_are_retryable`, `test_only_completed_and_cancelled_are_terminal`, `test_terminal_states_never_regress_even_on_retry`, `test_remaining_edges` (verbatim from brief).

## Test summary
`uv run pytest -q` from `services/worker` → 47 passed, 1 pre-existing pytest-asyncio DeprecationWarning.

## Concerns
- None functional. Files outside the allowed set were left modified/untracked in the working tree and were NOT staged or committed.
