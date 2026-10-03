# PR-13 local description — Q06: bounded actor-bound job progress

Base `b083ea43988ed73e9d8e9ab112ba3d6305f2c941` → source `b3477e341c35807bcdcbb400edfed7cceaa46de4` on `codex/audit-fixes-20261003`;17 product/test files. Local commits/review description only, no GitHub PR/push/deploy.

## Purpose / F07

Add strict getAsyncJobSummary with shared current actor/admin/tenant guard and no result rows. Use one shared abortable poller in bulk/Operations: one in-flight, post-settlement2s, timeout10s, bounded backoff/Retry-After/visibility/scope/terminal handling. Load selected20-row results only on demand, terminal refresh once; retain complete generated IDs. Fix recovered poll errors without clearing unrelated Operations errors.

## Evidence

Strict API/DB/contracts24 and full audit UI44 pass, zero failures/errors/skips;29 units pass;2 Node file tests hold74 adapter+8 auth checks. Contract80/type/changed-file lint and3 manual rollback checks pass. Before→after at fixed fake-clock1000-results/10-view/60s/RTT2.5s:1250→140 requests,9,293,390→69,440 actual response bytes,10,000→840 SQL executes, max in-flight13→1. Every scheduled call replayed on actual guarded disposable DB; no wall-clock/live SLA claim. Failed43/1 transport run and meaningful REDs retained.

Full commands/artifacts/screenshots/hashes/cases/limits: `docs/buyeros/evidence/audit-fixes-20261003/Q06/RESULTS.md`. Source patch17 paths and proof attached there; original input31/98-case columns unchanged. Migration0/head0036; existing disposable migration rollback tested.

## Rollback / review

Use reviewed manual-refresh-rollback.patch, preserving API/schema/data and stopping automatic polling. Do not revert to old full-page interval;3 scratch behavior checks pass, browser/deployment rollback unverified. Independent review pending; production/live identity/provider/Neon/worker/8-module UAT remain unverified. No external action authorized by this PR description. Next eligible localQ07, with Q15 predecessor complete.
