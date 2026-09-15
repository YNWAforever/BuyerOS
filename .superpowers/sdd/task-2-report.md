# Task 2 Report — Worker lease model, outbox dispatch columns and migration

**Status:** DONE
**Branch:** `p8-worker-dispatcher` (no branch creation/switch)
**Commit:** `c01ef8eae3a08b1b88a3544e21f03f4cd90226b2` — `feat(db): worker_leases table and outbox dispatch columns`
**Commit scope:** 4 files changed, 124 insertions(+), 1 deletion(-) — exactly the four task files.

## Files

| Action | Path |
|--------|------|
| Create | `services/api/buyeros_api/db/worker.py` |
| Modify | `services/api/buyeros_api/db/outbox.py` |
| Create | `services/api/alembic/versions/0006_worker_leases.py` |
| Create | `services/api/tests/test_worker_leases_model.py` |

No files under `services/worker`. No other migrations. No other tests. No `git push`/`merge`/`rebase`.

## What was implemented

- `WorkerLease` (`buyeros_api.db.worker`): subclasses `Base, TenantMixin`; columns `intent_key`, `owner`, `expires_at`, `fencing_generation`, `state`, `attempts`; explicit `UniqueConstraint`/`ForeignKeyConstraint` names per the existing pattern (`uq_worker_leases_workspace_id`, `uq_worker_leases_intent`, `fk_worker_leases_workspace`).
- `OutboxEvent` gained `dispatched_at`, `lease_owner`, `lease_expires_at`, `fencing_generation`. Added `datetime` and `DateTime` imports to `outbox.py` (the brief flagged this requirement).
- `0006_worker_leases.py`: `down_revision = "0005_p3_tables"`; adds the four outbox columns, creates `worker_leases`, index `ix_worker_leases_workspace_id`, enables + forces RLS, creates `tenant_isolation` policy, grants to `buyeros_api, buyeros_worker`; mirrored downgrade.

## Exact commands and real output

### Step 2 — verify RED (cwd `services/api`)

Command: `uv run pytest tests/test_worker_leases_model.py -v`

```
ImportError while importing test module '...\tests\test_worker_leases_model.py'.
tests\test_worker_leases_model.py:5: in <module>
    from buyeros_api.db.worker import WorkerLease
E   ModuleNotFoundError: No module named 'buyeros_api.db.worker'
=========================== short test summary info ============================
ERROR tests/test_worker_leases_model.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.39s ===============================
EXITCODE=2
```

Fails for the expected reason (missing module), not a typo.

### Step 4 — verify GREEN (cwd `services/api`)

Command: `uv run pytest tests/test_worker_leases_model.py -v`

```
tests/test_worker_leases_model.py::test_worker_lease_table_and_unique_intent PASSED [ 25%]
tests/test_worker_leases_model.py::test_outbox_has_dispatch_columns PASSED [ 50%]
tests/test_worker_leases_model.py::test_migration_enables_rls_on_worker_leases PASSED [ 75%]
tests/test_worker_leases_model.py::test_only_worker_leases_is_new_tenant_table PASSED [100%]
======================== 4 passed, 1 warning in 0.37s =========================
EXITCODE=0
```

### Step 5 — migrations on a disposable database (cwd `services/api`)

Command: `uv run pytest tests/test_tenant_isolation_db.py -q`

```
.....                                                                    [100%]
5 passed, 2 warnings in 3.38s
EXITCODE=0
```

The session-scoped `migrated` fixture ran `command.upgrade(config, "head")`, which now applies `0006_worker_leases`. `BUYEROS_TEST_DATABASE_URL` is not set and no `buyeros-test-*` container remained afterward, so a disposable `postgres:16` container was used and removed. No persistent database was touched.

### Full suite (regression check, cwd `services/api`)

Command: `uv run pytest -q`

```
108 passed, 20 warnings in 3.53s
EXITCODE=0
```

All warnings are pre-existing third-party deprecations (`pytest_asyncio` event-loop policy, Alembic `path_separator`) — none originate from the new code.

## TDD compliance

- Wrote the brief's test verbatim first; watched it fail with the expected `ModuleNotFoundError`.
- Wrote minimal implementation to pass; watched all 4 pass.
- No production code existed before the failing test.

## Self-review

- `worker.py` and the migration match the brief's specified values verbatim.
- Explicit constraint names match the established convention; the earlier auto-naming collision is avoided.
- `outbox.py` remains importable (added `DateTime`/`datetime`); verified by the passing `test_outbox` tests and full suite.
- Test asserts `"worker_leases" in Base.metadata.tables`, satisfied because the test imports `WorkerLease` directly; no change to `db/models.py` or `db/__init__.py` was needed or made (would have violated the file constraint).
- Commit contains only the four intended files; the unrelated pre-existing modifications to `.superpowers/sdd/progress.md` and the plan doc were deliberately left unstaged.

## Deviations

None.
