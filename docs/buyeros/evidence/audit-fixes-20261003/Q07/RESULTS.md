# Q07 / PR-14 local repair evidence — 2026-10-03

Base `c09eec2872b1fa73719c0894c14d01c23a13bbdc`; reviewed source **a2696e1a317342a64c9b9b29b0585ae8ddff54bf**; branch `codex/audit-fixes-20261003`. F09, A02/A07. [Exact seven-file diff](Q07.patch), [tested working/staged hashes](q07-tested-source.json), [author review](../../../review/2026-10-03-audit-fixes/Q07-review.md), [local PR-14 description](../../../review/2026-10-03-audit-fixes/Q07-pr.md). Local commits only; no push, remote PR, merge, deployment or production mutation. Deployed SHA null.

## Finding / changed files

F09 was still open at this base: two objective/tone combinations rendered identical subject/body while the UI offered tone as a control. The minimum approved remedy retains this free deterministic route, removes the ineffective selector, sends explicit fixed professional metadata, labels objective internal-only and states template language affects framing only. Offer facts and quoted sources retain their original language; no automatic translation or configurable CTA is promised. Manual edits retain Q15 protection and await Q12 grounding review.

| Changed path | Change |
|---|---|
| features/live/drafts.tsx | en/zh-HK limitation/next-step copy; internal objective/template-language labels; fixed tone, no selector |
| services/api/buyeros_api/execution/handlers/draft_generate.py | Docstring states existing fixed text and metadata semantics; renderer behavior unchanged |
| docs/buyeros/03_DATA_API_AND_STATE_CONTRACTS.md | Current fixed-template presentation contract |
| services/api/tests/test_draft.py | Two-language source/metadata/output comparison and grounding validation |
| services/api/tests/test_draft_persistence_db.py | Actual HTTP/DB admission retains tone/objective metadata, zero provider operations/holds |
| services/worker/tests/fixtures/audit_template.py | Bounded owner-verified fixture; actual shared fenced handler materialization/replay, never synthetic output |
| tests/e2e/audit-template-copy.spec.ts | Named A02/A07 actual output/copy, generated edits, mobile exact approval/download, negative viewer/delivery checks |

API fields/validation, current memberships/RLS/canonical actor, ActionIntent, immutable revisions, exact approval/context and financial guards remain compatible. One API/migration owner. No auth trust or Cloudflare HMAC change, paid model, mailbox/CRM or sending activation.

## Environment / limitations

[Exact versions](q07-environment.json): Windows PowerShell, Node24.18.0/pnpm11.25.0/uv0.11.27, locked Python3.14.6, Docker29.7.2/PostgreSQL16, Playwright1.63.0 Chromium. UI uses owned Linux Node22.23.2-bookworm-slim Vinext/Nitro dev,4CPU/6GiB, localhost5173→actual FastAPI8000/runtime-RLS DB. Test OIDC/PKCE identities and contact/purpose inputs are fictional. Validity labels in the fixture are not provider verification. Dispatch state for exactly one new zero-cost actor/project-bound draft intent is fixture-staged; the actual shared worker handler executes with its RLS role and generation fence, then rejects duplicate execution. No continuous Celery/Valkey, Cloudflare transport, built preview or live Auth0/Neon proof is inferred.

Required DB commands set BUYEROS_STRICT_INTEGRATION=1 and remove BUYEROS_TEST_DATABASE_URL/BUYEROS_DATABASE_URL before fixtures. Only guard-approved owned loopback Docker DBs used. [Three destructive guards unchanged](q07-db-guards.json); [positive-label fixture cleanup](q07-fixture-cleanup.json). [Original evidence](q07-input-integrity.json): safe ZIP path/CRC checks, required nested hash19369591..., outer hashf11c2c..., all31 original input hashes. No original98-case fields,25-task CSV or frozen plan rewritten. [Unrelated worktrees](q07-unrelated-worktrees.json) inspected read-only; original checkout clean671fed7, dirty Neon candidate preserved.

## RED / intermediate results

| Run | Actual result | Classification |
|---|---|---|
| [Meaningful UI RED](q07-ui-red.xml), [log](q07-ui-red.log) |1fail/0skip| Actual Tone selector count1 instead of0; [retained trace](red-audit-template-copy-A02-fi-dabff-s-keep-Q15-dirty-protection-trace.zip) |
| [API construction](q07-api-baseline.xml) |4pass/2fail/0skip| Invalid fictional non-UUID inputs; corrected test data without weakening source validation; not product RED |
| [API behavior before fix](q07-api-behavior.xml) |6pass/0fail/0skip| Confirms unchanged deterministic same-body and original source language |
| [First named UI](q07-ui-first.xml), [log](q07-ui-first.log) |1pass/1fail/0skip| A02 real generation/edits passed. A07 materialized/requested review but waited for zh checkbox in another reviewer's saved en locale; trace identified test assumption. Set locale through actual persisted UI, restored both actors; original60s timeout and assertions retained |
| [Second named UI](q07-ui-second.xml), [log](q07-ui-second.log) |2pass/0fail/0skip| A02 en desktop17.5s; A07 zh-HK mobile12.7s;1.3m total fixture lifecycle |

The original reproduce_audit.py was read completely. Its fake workspace query interface is obsolete after Q06; whole historical script was not rerun. Selected real renderer/HTTP/DB/UI tests reproduce the F09 behavior, with the original source package preserved.

## Final GREEN / exact commands

[Command/environment inventory](q07-commands.json); all commands root except stated cwd. [Completion gate](q07-task-done.log) verifies current JUnit/output evidence and reruns unit/contract/type/lint checks; this is not a second DB/UI execution.

| Check | Command | Exact result |
|---|---|---|
| Strict API/DB/contracts (cwd services/api) | `uv run --frozen pytest -q tests/test_draft.py tests/test_draft_persistence_db.py tests/test_draft_approval_context_db.py tests/test_exports_authorization_db.py tests/test_api_routes_contract.py tests/test_contract_required_fields.py --junitxml=../../test-results/q07-api-final.xml` | **47pass/0fail/0error/0skip**,7 dependency warnings,47.79s; [log](q07-api-final.log), [JUnit](q07-api-final.xml) |
| Strict worker/DB (cwd services/worker) | `uv run --frozen pytest -q tests/test_grounded_drafts.py --junitxml=../../test-results/q07-worker-final.xml` | **11pass/0fail/0error/0skip**,4 dependency warnings,9.54s; [log](q07-worker-final.log), [JUnit](q07-worker-final.xml) |
| Actual Q07+Q15 UI | `node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts tests/e2e/audit-template-copy.spec.ts tests/e2e/audit-draft-dirty.spec.ts` | **12pass/0fail/0skip**,2.3m fixture lifecycle;10 Q15+2 Q07; [log](q07-ui-final.log), [JUnit](q07-ui-final.xml). testMatch actually executes audit-template-copy.spec.ts |
| Related Node tests | `node --test tests/audit-draft-guard.test.mjs tests/audit-research-intent.test.mjs tests/live-adapter-checks.mjs tests/live-auth-checks.mjs` | **12pass/0fail/0skip** =10 guard/intent unit+2 file tests containing74adapter+8auth internal assertions; [log](q07-unit-final.log) |
| Generated contracts / type / edited UI lint | `node scripts/generate-api-types.mjs --check`; `node node_modules/typescript/bin/tsc --noEmit`; `node node_modules/eslint/bin/eslint.js features/live/drafts.tsx tests/e2e/audit-template-copy.spec.ts` | exit0 each, fresh [aggregate output](q07-final-gate.log); **80 operations=70 original+10 existing extensions**, no new operation here |
| Alembic source (cwd services/api) | `uv run --frozen alembic heads` | **0036_checkpoint_schema_grants (head)**; [log](q07-alembic-heads.log); **0 new migrations**, no production DB access |
| Backout applicability | `git apply --check docs/buyeros/evidence/audit-fixes-20261003/Q07/generation-pause-rollback.patch` | exit0; [patch](generation-pause-rollback.patch), [log](q07-rollback-check.log); browser/runtime/deployment backout not rehearsed |

## Case results / actual artifacts

| Case | Current closure | Evidence |
|---|---|---|
| F09 / A02 | Fixed with local fixture + HTTP/DB/UI evidence; external rollout unverified | [Two actual generated outputs](q07-A02-output.json), [English edits screenshot](q07-template-en-edited.png). Same subject/body with distinct objectives; fixed professional UI metadata; Cancel keeps dirty manual edits and Save creates needs_review revision, exact review unavailable until separate Q12 |
| F09 / A07 | Fixed with local fixture + HTTP/DB/UI evidence; true provider/auth/transport unverified | [Actual generated output/materialization](q07-A07-output.json), [downloaded copy](q07-A07-export.txt), [zh-HK mobile template](q07-template-zh-mobile.png), [separate reviewer exact approval/export](q07-template-zh-approved-export.png). Full generated body and English source quote retained in authorized UTF8 download; viewer403, delivery403 DELIVERY_DISABLED |
| D02 / Q15 predecessor | All10 related UI regressions pass; original tracker remains unchanged | Save/Discard/Cancel for Refresh/Open/job materialization; failed401/412/503 buffer/baseline retained; awaited Save; scope race; mobile keyboard/dialog and clipboard |

Three materializations in the final A02/A07 artifacts produce done then duplicate with one revision, and provider_operations/budget_reservations remain0→0. This is actual handler/DB verification with explicitly staged dispatch, not a live provider or restart/continuous-transport rehearsal. Q07 has no performance benchmark acceptance requirement; fixture execution times above are test durations, not live latency/SLA. Prior Q06 performance comparison retains its stated fake-clock conditions separately.

## Rollback / remaining gates

Apply [generation-pause-rollback.patch](generation-pause-rollback.patch) to this reviewed source to disable only UI preparation, while preserving honest template limitations, existing revisions, editing/review and API guards. API zero-cost admission remains available under its existing authorization. Retain all history and grounded/context checks. No DB downgrade; no paid generation activation. A full source revert would restore the misleading tone option and is not recommended. Patch applicability and source reverse-check are recorded; actual browser/production rollback is unverified.

Q12 manual Unicode/source grounding review remains the next eligible local task (Q15 complete). Independent review pending; this is an author-reviewed local candidate. Real Auth0/Neon account rehearsal, N00 built handler/session/token compatibility, paid/provider activation, continuous worker/broker/Cloudflare, external policy decisions, production deployment, full8-module live staff acceptance and live performance remain separate unverified gates. Q16 lacks SQLSTATE/driver/pool evidence for the original OperationalError; Q17 is not guessed. Mailbox/CRM disabled, delivery403. **Code implemented**, **fixture verified**, **local integration verified**; **deployed: no**, **live product acceptance: unverified**.
