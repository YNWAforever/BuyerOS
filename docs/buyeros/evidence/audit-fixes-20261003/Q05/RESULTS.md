# Q05 / PR-12 local repair evidence — 2026-10-03

Base `6e7a78c6994664cb47c5325d8c0eecd8cfdde573`; reviewed source `4cd0f484814be7d4333ca265c9637de940d398fa`; branch `codex/audit-fixes-20261003`. F06, cases B02/B03/B04/B07/B16. Seven-file product/test boundary in [Q05.patch](Q05.patch); [author review](../../../review/2026-10-03-audit-fixes/Q05-review.md), [local PR description](../../../review/2026-10-03-audit-fixes/Q05-pr.md). These are local review artifacts; no GitHub PR, push, deployment or production mutation occurred.

## Finding classification and implementation

F06 was still open at this task's base: the actual UI kept confirmation checked after a sixth buyer changed a confirmed five-buyer selection, and offered no eligible-colleague picker. Q05 fixes the local UI portion. Existing server eligibility/version/caller/tenant checks were already present and are retained with fresh persistence evidence; synchronous inactive-owner 422 satisfies the original B04 rejection alternative. The original audit source/package is preserved, rather than rewritten as passing.

The UI consumes generated `listEligibleAssignees`, with bounded search and 20-row pages, full canonical IDs and self/eligible colleague/no-owner choices. Confirmation binds actor/workspace/project/operation, sorted explicit IDs+versions or snapshot+sorted exclusions, owner membership and trimmed reason. A material change clears confirmation; page-only changes preserve it. The preview freezes a copied generated body before submitting through the existing ActionIntent. Unknown outcomes keep that exact body/key; edits are locked and only explicit same-assignment Retry can reconcile. Route/scope return shows the frozen target/count/reason, while obsolete scope responses cannot update another scope. Known 4xx releases the uncertain state. Partial responses keep blocked/conflict IDs, reason codes and current versions visible.

No API product handler, schema, OpenAPI/generated contract or migration was changed in Q05. Existing canonical users/memberships/audit/job actors, RLS, current Auth0 and independent Cloudflare HMAC remain the authority. No email linking, role grant, synthetic live rows, delivery/provider activation or framework/DB migration was introduced.

## Environment and boundaries

Windows PowerShell, host Node24.18.0/pnpm11.25.0/uv0.11.27, locked Python3.14.6, Docker29.7.2, Chromium/Playwright1.63.0. Browser fixture uses owned Linux Node22.23.2-bookworm-slim Vinext/Nitro dev with 4CPU/6GiB; localhost5173 proxies the real local FastAPI HTTP API8000. Disposable PostgreSQL16 uses the existing least-privilege runtime role and RLS. Fictional OIDC principals and test-controlled job processing are fixture evidence, not real Auth0/Neon/provider/continuous-worker verification. API envelopes may carry `data_mode: live` because the real domain handler executes; artifacts explicitly mark `fixture_only: true`.

Both database DSN environment variables are removed before required pytest; `BUYEROS_STRICT_INTEGRATION=1`. Existing destructive fixture guards were not weakened: [three guard hashes](q05-db-guards.json). No production/shared database or Neon branch DSN was passed to pytest. Each audit_bulk invocation proves the existing owner_dsn once and restricts mutations to known fictional workspaces; no owner-proof caching across cases.

## RED and intermediate failures

| Evidence | Result | Classification and correction |
|---|---|---|
| [UI RED](q05-ui-red.log), B02 sixth buyer | 1 fail / 0 pass / 0 skip | Meaningful reproduced product regression: expected unchecked, received checked |
| [Unit import RED](q05-unit-red.log) | Module import failure | Construction evidence before the new module exists; not claimed as a reproduced product defect |
| [Unresolved-intent guard RED](q05-unresolved-guard-red.log) | 1 fail / 0 pass / 0 skip | Only Recovery.begin mismatch guard removed, restored in finally; expected rejection was absent |
| [First UI execution](q05-ui-first-green.log) | 8 fixture errors | Required fictional project version missing; product journey not reached |
| [Second UI execution](q05-ui-second.xml) | 3 pass / 5 fail / 0 skip | Three fixture seed/startup delays, one wrong project-selection assumption, one real mobile picker overflow; fixed bounded fixture work, explicit scope selection and responsive control layout |
| [First API execution](q05-api-first.xml) | 12 pass / 1 fail / 0 skip | New test used entity_id instead of real audit subject_id |
| [Wrong-cwd retry](q05-api-cwd-error.xml) | 12 pass / 1 fail / 0 skip | Intended source edit failed from API cwd; old test ran again. Correct root edit follows |
| [Eight-case UI green](q05-ui-third.xml) | 8 pass / 0 fail / 0 skip | Intermediate named suite; final combined run below includes final fixture isolation |
| [First combined UI](q05-ui-locale-leak.xml) | 26 pass / 11 fail / 0 skip | Ten D02 selectors affected by fictional operator locale leakage; one Q04 reload remained initializing at its assertion. Q05 fixture restores en via real preference API; Q04 assertions/timeouts unchanged |
| [Completion-tool first error](q05-task-done-first-error.log) | Gate failed on ESLint child ETIMEDOUT | 60s wrapper limit, after positive JUnit/unit/types checks; extended wrapper child budget to180s. No product/test assertion, timeout or required skip policy relaxed |

Original logs/JUnit are retained without converting failed runs to pass. Early cp950 capture and file-edit errors are tooling errors; successful UTF-8 captures are retained. Initial RED trace files were overwritten by later Playwright runs; no retained-trace claim is made.

## Final GREEN commands and exact results

Commands run at worktree root except the API command's explicitly stated cwd. No zero-tests or skip counts are accepted.

| Gate | Executed command | Final result / artifact |
|---|---|---|
| Required strict DB/API, cwd `services/api` | `uv run --frozen pytest -q tests/test_bulk_jobs_db.py --junitxml=../../test-results/q05-api-final.xml` with strict env and both DSNs unset | **13 pass / 0 fail / 0 error / 0 skip**, 9 warnings, console58.44s; [log](q05-api-final.log), [JUnit](q05-api-final.xml) |
| All audit UI specs, current source | `node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts` | **37 pass / 0 fail / 0 error / 0 skip**, console12.0min, JUnit623.122s; [log](q05-ui-final.log), [JUnit](q05-ui-final.xml). Q01=7, Q05=8, Q15=10, Q02=7, Q03=4, Q04=1 |
| Related unit | `node --test tests/audit-bulk-confirmation.test.mjs tests/audit-member-contract.test.mjs tests/audit-research-intent.test.mjs tests/audit-draft-guard.test.mjs tests/audit-auth-render.test.mjs` | **18 pass / 0 fail / 0 skip**; [captured run](q05-unit-final.log), final completion-wrapper rerun1246.6289ms in [gate log](q05-final-gate.log) |
| Generated types | `node scripts/generate-api-types.mjs --check` | exit0, contract matches; [log](q05-contract-types.log), fresh rerun in gate log |
| Operation routes | `uv run --frozen --project services/api python scripts/generate-operation-routes.py --check` | exit0, **79 operations** = original70 + nine extensions; [log](q05-contract-routes.log). No Q05 extension added |
| TypeScript | `node node_modules/typescript/bin/tsc --noEmit` | exit0, no diagnostics; [log](q05-types-final.log), fresh rerun in gate log |
| Changed-file lint | `node node_modules/eslint/bin/eslint.js features/live/bulk-actions.tsx features/live/buyer-results.tsx services/live/bulk-confirmation.ts tests/e2e/audit-bulk-confirmation.spec.ts` | exit0, no diagnostics/rule suppression; [final gate log](q05-final-gate.log) |
| Strict report checks | `python scripts/check-required-tests.py --junit test-results/q05-api-final.xml` and same for `q05-ui-final.xml` | respectively13/0/0/0 and37/0/0/0; [report verification](q05-checkpoint-integrity.json) |
| Plan completion | `task-done .superpowers/sdd/q05-bulk-confirmation/q05-bulk-confirmation.md 1 6e7a78c6994664cb47c5325d8c0eecd8cfdde573 -- node test-results/q05-final-gate.mjs` | exit0; [tool output](q05-task-done.log), [script](q05-final-gate.mjs), [ledger](q05-task-ledger.md). The script reads actual final13/37 positive JUnit counts and reruns lightweight units/types/lint; it does not claim another heavy DB/UI run |

## Cases and concrete persistence evidence

| Case | Verified outcome | Limits |
|---|---|---|
| B02 | Sixth selection, owner, reason or snapshot exclusion change clears confirmation; equivalent ordering and page-only change preserve it. Immutable body includes versions/actor/scope/trimmed reason | Fictional fixture and unit scope; no live staff UAT |
| B03 | Search ten eligible colleagues, assign ten via real API and read owner/version2 in DB, clear ten durably; explicit error/retry with no fake fallback; viewer controls hidden and direct API403; en and zh-HK390px | [assignment](q05-colleague-assignment.json); no production membership grant |
| B04 | After preview, inactive target rejected422 with unchanged buyers/audits; concurrent changed buyer conflicts with current version and is not overwritten. Post-enqueue target deactivation gives101 blocked rows | [UI result](q05-owner-revalidation.json); strict DB suite recreates transaction/session/event loop per chunk, not a real broker/process restart |
| B07 |100requested =25updated +25unchanged +25blocked +25conflicts;100distinct IDs; durable versions/owners and25 canonical actor audit events match owner/reason digest; same-key replay adds no audits | Actual disposable DB state and generated schemas; provider acceptance is irrelevant/unexecuted |
| B16 | Committed response lost: only one POST before explicit Retry; remount retains frozen colleague/count/body/key and buyers reach version2 once. Held101-job B response cannot update A; returnB retries same key/job; B read200/A read404 | [lost response](q05-lost-response.json), [scope recovery](q05-scope-recovery.json). Memory recovery is verified for route/scope/token renewal, not hard browser/process restart |

## Screenshots

[English](q05-bulk-en.png) shows the real fictional assignment controls after clear-owner verification; [zh-HK mobile](q05-bulk-zh-mobile.png) is390×2770 with wrapped full IDs and no horizontal overflow. Images were visually inspected. They are fixture screenshots, not deployed/live evidence.

## Source, migration, rollback and cleanup

Seven product/test files are exactly listed in [tested source hashes](q05-tested-source.json). Working bytes and committed Git blobs differ where Git normalizes CRLF/LF; each matches after newline normalization, both hashes retained, independently rechecked in [checkpoint proof](q05-checkpoint-integrity.json). Do not describe them as byte-identical. The original31 package hashes,98 original case columns and approved plan bytes remain unchanged. Nested evidence ZIP SHA256 reverified: `19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a`; [input proof](q05-input-integrity.json).

Source/authored-document whitespace checks pass. Raw captured logs, JUnit, JSON, the executed gate script and ledger retain their original bytes under `* -text`; Git flags preserved CRLF as trailing whitespace, so the source/document check explicitly excludes those raw captures. No captured output is reformatted to hide an error.

New migrations: **0**. `uv run --frozen alembic heads` in `services/api` returned `0036_checkpoint_schema_grants (head)`. Existing strict bulk suite downgrades an empty disposable DB to0015 then upgrades to0036; no production migration/rollback is claimed.

Rollback: `git revert 4cd0f484814be7d4333ca265c9637de940d398fa` as the complete seven-file Q05 source/test boundary, after preserving unresolved intent details for read reconciliation. [Reverse applicability check](rollback-check.log) ran `git apply --reverse --check docs/buyeros/evidence/audit-fixes-20261003/Q05/Q05.patch` and exited0; no actual revert executed. Keep already successful assignments, versions and audit records; any compensating owner change needs current version/authority, not automatic Undo or replay with a new key.

Fixture global teardown removed this run's owned containers/markers. Dependency volume `buyeros-audit-ui-deps-052d6a686de9` was inspected for matching `buyeros.audit.owner=052d6a686de9` then removed; [cleanup proof](q05-fixture-cleanup.json). Inherited resources and unrelated worktrees remain untouched. The review branch/worktree is retained.

## Remaining gates and next eligible task

Author review only; independent review is pending. Hard-browser unknown-assignment recovery is unverified; Q06 covers bounded job summary polling/refresh and must not be described as adding persistent assignment storage. Live accounts/Neon preview/built-output/auth cutover/Cloudflare/paid providers/production deployment are unexecuted. Q16 remains blocked on SQLSTATE/driver/pool evidence; Q17 is not guessed. Local elapsed times include startup/fixtures/host contention, not production p95/p99 or SLA. Full release performance/accessibility/eight-module live UAT remain open. Mailbox/CRM/sending remain disabled and delivery activation was not changed.

**Code implemented; fixture and local HTTP/DB integration verified; externally gated checks unverified; deployed SHA null. Next eligible local task: Q06**, predecessor Q03 satisfied. No new activation request is needed to complete this local checkpoint.
