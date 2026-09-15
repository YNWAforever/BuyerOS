# Task 3 Report — Lease and fencing primitives

**Status:** DONE
**Branch:** `p8-worker-dispatcher` (no branch creation/switch)
**Commit:** `ce5f850c3c1df76152d1b5a2f788838f704de5a4` — `feat(worker): lease expiry and fencing primitives`
**Commit scope:** 2 files changed, 41 insertions(+) — exactly the two task files.

## Files

| Action | Path |
|--------|------|
| Create | `services/worker/buyeros_worker/leases.py` |
| Create | `services/worker/tests/test_leases.py` |

No files under `services/api`, no other worker modules, no other tests. No `git push`/`merge`/`rebase`. No external calls or provider usage.

## What was implemented

Transcribed the brief verbatim:

- `lease_expiry(now: datetime, seconds: int) -> datetime` — returns `now + timedelta(seconds=seconds)`.
- `can_claim(state: str, expires_at: datetime | None, now: datetime) -> bool` — `True` when `state == "free"` or `expires_at is None`, else `expires_at <= now`.
- `fence_ok(worker_generation: int, row_generation: int) -> bool` — equality check.

Pure functions only; no imports beyond `datetime`. The module is dependency-free so Task 8 (dispatcher) and Task 9 (task entrypoint) can import it without pulling in DB/Celery state.

## Exact commands and real output

### Step 2 — verify RED (cwd `services/worker`)

Command: `uv run pytest tests/test_leases.py -v`

```
ImportError while importing test module '...\tests\test_leases.py'.
tests\test_leases.py:3: in <module>
    from buyeros_worker.leases import can_claim, fence_ok, lease_expiry
E   ModuleNotFoundError: No module named 'buyeros_worker.leases'
=========================== short test summary info ============================
ERROR tests/test_leases.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.12s ===============================
EXITCODE=2
```

Fails for the expected reason (missing module), not a typo.

### Step 4 — verify GREEN (cwd `services/worker`)

Command: `uv run pytest tests/test_leases.py -v`

```
tests/test_leases.py::test_free_lease_can_be_claimed PASSED              [ 20%]
tests/test_leases.py::test_unexpired_lease_cannot_be_claimed PASSED      [ 40%]
tests/test_leases.py::test_expired_lease_can_be_claimed PASSED           [ 60%]
tests/test_leases.py::test_lease_expiry_adds_seconds PASSED              [ 80%]
tests/test_leases.py::test_fence_rejects_stale_worker PASSED             [100%]
======================== 5 passed, 1 warning in 0.03s =========================
EXITCODE=0
```

### Full worker suite (regression check, cwd `services/worker`)

Command: `uv run pytest -q`

```
........                                                                 [100%]
8 passed, 1 warning in 0.25s
EXITCODE=0
```

8 = the 5 new lease tests + the 3 pre-existing `tests/test_app.py` tests. The single warning is a pre-existing third-party `pytest_asyncio` deprecation (`asyncio.get_event_loop_policy`), unrelated to the new code.

## TDD compliance

- Wrote the brief's test verbatim first; watched it fail with the expected `ModuleNotFoundError`.
- Wrote the minimal implementation to pass; watched all 5 pass.
- No production code existed before the failing test.

## Self-review

- `leases.py` matches the brief's specified values verbatim (signatures, comparison operators, default-free behaviour).
- `can_claim` treats `None` expiry as claimable independent of `state`, which is the brief's intent.
- `expires_at <= now` (inclusive) matches `test_expired_lease_can_be_claimed` with a 1-second-past timestamp.
- No type annotations beyond the brief were added; no comments added.
- Commit contains only the two intended files; unrelated pre-existing modifications to `.superpowers/sdd/progress.md` and `docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md`, and untracked report/brief/review artifacts, were deliberately left unstaged.
- `git diff --cached` was inspected before committing; line-ending warnings (LF→CRLF) are the repo's normal Windows behaviour and match existing files.

## Deviations

None.

## Concerns

- `can_claim` accepts a `state: str` and is only correct if callers pass the exact literal `"free"`; a typo or a future richer state (e.g. `"released"`) would be treated as held unless `expires_at` is null or past. This is the brief's specified behaviour and is not changed here, but Task 8 should keep state constants centralized.
- No ruff/lint target is configured in `services/worker/pyproject.toml`, so no lint step was run; the module is trivially clean (no unused imports, standard formatting).
