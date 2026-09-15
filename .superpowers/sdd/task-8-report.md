# Task 8 report: DB dispatcher and sweeper

## Status
COMPLETE

## Commit
`d0ad91ec42ce6321df110741653d520e1325d184` — `feat(worker): outbox dispatcher with lease claims and sweeper` (local only, branch `p8-worker-dispatcher`; not pushed)

## Files
- Created: `services/worker/buyeros_worker/dispatcher.py`
- Created: `services/worker/tests/test_dispatcher.py`

No other files touched. No `store.py` was created (per the brief, all DB helpers live in `dispatcher.py`).

## TDD steps
1. Wrote failing test — `services/worker/tests/test_dispatcher.py` transcribed verbatim from the brief (`test_only_ready_rows_are_selected`, `test_batch_is_bounded`).
2. Verified RED — `uv run pytest tests/test_dispatcher.py -v` → `ModuleNotFoundError: No module named 'buyeros_worker.dispatcher'` (collection error, expected).
3. Wrote minimal implementation — `select_ready`, `claim_outbox_rows`, `mark_dispatched`, `sweep_expired`, `dispatch_once`, transcribed verbatim from the brief.
4. Verified GREEN — 2 passed.
5. Committed the two files only.

## Test summary
`uv run pytest tests/test_dispatcher.py -v` → 2 passed. Full worker suite `uv run pytest -q` → 49 passed, 1 pre-existing DeprecationWarning from pytest-asyncio (`asyncio.get_event_loop_policy`).

## Notes / decisions
- Reused Task 3 `can_claim` and `lease_expiry` from `buyeros_worker.leases`; reused `buyeros_api.services.outbox_service.build_intent` inside `dispatch_once`. Nothing reimplemented.
- `claim_outbox_rows` is the only DB-touching path (raw `sqlalchemy.text` with `FOR UPDATE SKIP LOCKED`, per the brief); the tests exercise the pure `select_ready` only, so no database or network is required.
- `publish` is a plain injected callable; no broker/network calls occur in tests.
- LF→CRLF conversion warnings emitted by git on commit (repo autocrlf behavior); no content impact.

## Concerns
- Interface drift: the brief's Interfaces section types `sweep_expired(...) -> list[str]`, but the brief's authoritative implementation body returns `list[int]` row ids. I transcribed the implementation verbatim (returns `list[int]`). Task 9 should treat the returned values as row ids.
- `dispatch_once` hardcodes `logical_index=0` when calling `build_intent` (verbatim from the brief). Two outbox events with identical `event_type`+`payload` would therefore derive the same deterministic intent id; if duplicate-intent uniqueness is required, `logical_index` needs a per-row discriminator (out of scope for Task 8).
- Task 9 is expected to consume `dispatch_once`; it is defined but not yet wired into any worker entrypoint here.

## Corrective fix (follow-up)
- Commit `32e4af01c4bad21161e1e8bde1485b4dadf76496` — `fix(worker): dispatch using the persisted outbox intent key` (local only, branch `p8-worker-dispatcher`; not pushed).
- `dispatch_once` now publishes `row["intent_key"]` (the id persisted by the enqueue path) instead of recomputing via `build_intent(..., 0)`; removed the `build_intent` import from this module.
- `sweep_expired` return annotation was already `-> list[int]` on this branch, so no change was required.
- Files touched: `services/worker/buyeros_worker/dispatcher.py`, `services/worker/tests/test_dispatcher.py` (only).
- `uv run pytest -q` from `services/worker` → 51 passed, 1 pre-existing DeprecationWarning.
