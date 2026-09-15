# P8 worker/dispatcher - progress ledger

Plan: docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md
Branch: p8-worker-dispatcher
Base commit: 36e67d5


Task 1: complete (commits 1d0df22..6b92180, review clean)
  Minor (for final review triage):
  - services/worker/tests/test_app.py: does not assert result_backend unset despite test name
  - services/worker/buyeros_worker/config.py: WorkerSettings.eager is never wired into build_app
  - services/worker/buyeros_worker/app.py: autodiscover_tasks targets a not-yet-existing tasks module
  - plan defect feedback: brief pyproject path dependency was not installable; fixed by adding build-system to services/api
  Important resolved-by-approval: services/api/pyproject.toml change approved via explicit owner scope extension
Task 2: complete (commits 6b92180..c01ef8e, review clean)
  Minor (for final review triage):
  - test_tenant_isolation_db.py forced-RLS enumeration omits worker_leases (textual RLS check only)
  - 0006 downgrade relies on DROP TABLE instead of explicit REVOKE (house-style inconsistency)
  - no index on outbox_events(state, lease_expires_at) for dispatcher/sweeper queries
  - WorkerLease not imported by alembic env.py / db package, so it is absent from Base.metadata at autogenerate time
Task 3: complete (commits c01ef8e..ce5f850, review clean)
  Minor: 'free' magic string in can_claim; naive/aware datetime mixing unguarded; negative seconds unvalidated
Task 4: complete (commits ce5f850..6c70b28, review clean)
  Minor: global HANDLERS mutated in tests with no cleanup (no worker conftest); duplicate registration silently overwrites; misleading coverage pragma
Task 5: complete (commits 6c70b28..c1c6821, review clean)
  Cross-task gap (being resolved in Tasks 6 and 9): no production entrypoint imports the handlers package, so handler registration only happens as a test/import side effect. Task 6 will make handlers/__init__.py import its submodules; Task 9 will import the handlers package in tasks.py.
  Minor: blocked() assumes payload is a mapping (truthy non-dict raises AttributeError)
Task 6: complete (commits c1c6821..5b5d384, review clean after 3 fix rounds)
  Resolved: malformed URL, non-string payload fields, HIGH IPv6-literal/empty-host SSRF bypass (all fail closed now).
  LOW (final review triage):
  - hostnames accepted by design; non-canonical numeric hosts (e.g. http://2130706433/x) fall to the hostname branch; live retrieval client must resolve+pin IPs
  - services/api safe_fetch.normalize_url drops IPv6 brackets (out of P8 scope) - flagged for follow-up
Task 7: complete (commits 5b5d384..77df73c, review clean after 1 fix round)
  Owner decision recorded: TERMINAL={completed,cancelled}; failed/partial/paused_budget are retryable. Plan document Task 7 code block is now stale vs code - update docs before final commit.
Task 8: complete (commits 77df73c..32e4af0, review clean after 1 fix round)
  Fixed: dispatch_once now publishes the persisted outbox intent_key (was recomputing with logical_index=0 -> collisions)
  Low (final review triage): no DB-backed test exercises claim/mark/sweep SQL; select_ready predicate diverges from the SQL predicate and is unused by dispatch_once; sweep_expired is read-only (wiring re-enqueue is deferred); tautological annotation test
Task 9: complete (commits 32e4af0..ac4abb6, review clean after 1 fix round)
  Fixed: engine singleton (was per-call leak); retry state now raises self.retry (bounded); unknown handler acked (no poison redelivery)
  Open (final review triage): singleton async engine reused across per-task asyncio.run event loops (medium); dispose_engine only nulls and is not wired to worker_shutdown; no tests for retry path or engine reuse
Task 10: complete (commits ac4abb6..c715715, review clean after 1 fix round)
  Fixed: broker_url restored in finally; bounded readiness poll replaces fixed sleep.
  Minor (final review triage): cleanup gap if the process is SIGKILLed between docker run and try; tautological broker_url assertion; exclusion path of select_ready not asserted in the integration test.

FINAL WHOLE-BRANCH REVIEW (36e67d5..c715715): NOT READY TO MERGE
Critical:
- Fencing never enforced: execute_intent ignores intent_key/generation; fence_ok has no production caller
Important:
- Intent not re-resolved from the DB (broker payload is the instruction source); tenant context not authoritatively re-derived
- No terminal outbox state / duplicate-delivery idempotency: a completed row whose lease expires is re-claimable and re-run
- Sweeper is read-only; no re-enqueue and no periodic/beat task
- No production entrypoints (nothing calls dispatch_once / sweep_expired / execute_intent)
- No run/event emission coupled to transitions; capability-blocked handlers do not transition a run
- Dispatcher cannot operate under RLS: outbox claim runs with no tenant context
- dispatch_once has no transaction boundary; publishes before persisting
- Engine singleton reused across per-task asyncio.run loops; dispose_engine not wired to worker_shutdown
- fetch.evidence validates but does not fetch (documented deferral)
- Plan docs stale vs code (run-lifecycle retry semantics, persisted intent_key, engine singleton, store.py)
Must-fix-docs: plan Task 7/8 text + SHA256SUMS regeneration; dead settings (eager unused, lease_seconds hardcoded 120)

FIX WAVE: complete (commits 05979d7, 68bb1f9, 443c970, a0950e9, 8c62025, 24933d3, b4af79a)
Tests: worker 85 passed; api 116 passed; buyeros-worker CLI works.
FINAL RE-REVIEW (36e67d5..b4af79a): READY TO MERGE - all 8 blocking findings resolved in code with tests.
Deferred minors: worker_leases table unused (leases live on outbox_events); can_claim/select_ready unused+divergent; plan nits; dispose_engine shutdown race; blocked intents recorded as outbox failed; emit_run_event only exercised by blocked handler.
