# Local verification gates — 2026-10-04

Reviewed test source `d7ab5b6323402adf139d9b94e4e499f1631006b4`, base `cbb67ddbb907b8b989b175588ba73ed205e2c2d8`. Application source remains `25694d3b938e704e883f9915cf0604bbdbac1daf`; no application/API/schema code changed. Local source commit only; no remote PR/push/deployment. Deployed SHA is null.

## What changed

`tests/e2e-fixture-cleanup.test.mjs` now imports each real Playwright configuration and invokes its configured teardown in a fresh isolated temporary directory. Twenty API fixture configurations each remove a uniquely named, newly owned Docker sentinel and marker. The audit wrapper also removes its labelled UI sentinel; wrong UI ownership and unrecognized database markers are refused and retained for explicit test cleanup. All fallback deletion checks this run's label. These are container-lifecycle tests: sentinel containers run sleep, not Postgres, and are not database integration or live auth/provider verification. Existing four destructive guards/teardown source remain unchanged.

The Vercel check needed a genuine build artifact. Existing `scripts/run-vercel.mjs build` was run with the Nitro `vercel` preset in a newly owned local Linux container, frozen pnpm dependencies and a safe secret-excluding source inventory. The emitted `__server.func/index.mjs` was tested directly, with no synthetic function or node-server substitute. Runtime/source/output hashes and reproduction helpers are in reports; no deployment configuration changed.

## Exact gates

| Command / environment | Result |
|---|---|
| Baseline `node --test tests/e2e-fixture-cleanup.test.mjs tests/vercel-render.test.mjs` | 0 pass / 2 fail / 0 skip: stale direct-filename check and missing emitted artifact |
| `node --test tests/e2e-fixture-cleanup.test.mjs` | 24 pass / 0 fail / 0 skip, 71429.0015 ms before final zero-case/finally hardening |
| Remove audit's `cleanupDatabase()` invocation, run same test, restore original bytes in finally | 22 pass / 2 fail / 0 skip; delegated database marker retained; final restore SHA verified. Parent and failed child both counted by Node |
| Each bounded local `corepack pnpm install --frozen-lockfile && timeout --signal=TERM --kill-after=10s 180s node scripts/run-vercel.mjs build` | Two local builds exit0; actual first Linux SSR3 pass; first Docker copy failed on Windows symlink privilege, retained. Second resolves symlinks in tar and extracts genuine artifact successfully |
| Linux `node --test tests/vercel-render.test.mjs` final | 3 pass / 0 fail / 0 skip,449.838376 ms |
| Windows same direct emitted-function test | 3 pass / 0 fail / 0 skip,658.5276 ms |
| **Final `node --test --test-reporter=spec --test-reporter-destination=stdout --test-reporter=junit --test-reporter-destination=test-results/local-gates/root-node-final.xml 'tests/*.test.mjs'`** | **69 pass / 0 fail / 0 cancelled / 0 skip / 0 todo;96210.0865 ms**. Includes cleanup and SSR, not additive independent counts |
| `node node_modules/typescript/bin/tsc --noEmit` | exit0 |
| `node node_modules/eslint/bin/eslint.js tests/e2e-fixture-cleanup.test.mjs --max-warnings=0` | exit0 |
| `node scripts/generate-api-types.mjs --check` | exit0 |
| `uv run --frozen --project services/api python scripts/generate-operation-routes.py --check` | exit0,84 operations =70 original +14 existing extensions;0 new |
| `uv run --frozen alembic heads` (services/api) | sole `0037_bulk_manifests`;0 migrations added/applied |
| `git apply --reverse --check docs/buyeros/evidence/audit-fixes-20261003/LOCAL_GATES/reports/test-rollback.patch` | applicability exit0; no runtime/production rollback rehearsal |

Node counts include the successful cleanup parent: JUnit contains68 leaf cases, including23 cleanup effects/negative leaves. It is not69 unique leaf scenarios. Exact individual results and raw XML/log retained. Host Windows Node24.18.0; local built runtime Node22.23.2/image48e4b67d...,4CPU/6GiB; Docker context desktop-linux. Existing source/lockfile frameworks remain unchanged. Root cleanup test now requires an available local Docker daemon and cached/pullable `node:22.23.2-bookworm-slim`; missing prerequisites fail, never skip. Linux CI already builds the emitted function before its rendering test.

## Failure history and provenance

First behavior-harness run misclassified Docker's lowercase `no such object` response; fixed case handling only, retained failing log. First build/render succeeded but recursive Docker copy lacked Windows symlink privilege; second local build used `tar -chzf` to export actual resolved files. Build warnings for unresolved optional nf3 traceInclude entries/plugin timing are retained and are not called a warning-free build. Mutation driver cp950 print failed after the expected red and exact restoration/proof had succeeded; verified that existing proof without rerunning the mutation. Artifact hash collector initially compared a relative path to an absolute root; corrected and rerun. These setup/diagnostic failures are not product REDs or hidden passes.

No paid provider/Auth0/Neon request, secret write, database/membership mutation, mail, service activation or deployment occurred. Owned sentinel/build containers were removed; only the label-verified existing dependency cache and ignored emitted output/source archives remain for review. Empty setup-error temporary directories were checked within the task prefix and removed.

## Preservation and review

U05's91, Q09 FINAL161 and KEYBOARD141 producer files still match their frozen manifests. Root remains clean at671fed7...; unrelated Neon worktree193 paths/raw diff SHA32ad7260... unchanged. Original98-case tracker and all operation rows unchanged; only Q11's follow-up evidence is added to TASKS. No new F-ID closure is claimed; U05/F04 remains its earlier local UI/strict-DB result, not newly run here. No UI/DB suite was rerun for this test-only delta, and no existing fixture result becomes live proof.

Author review of `cbb67ddbb907b8b989b175588ba73ed205e2c2d8..d7ab5b6323402adf139d9b94e4e499f1631006b4` and build/runtime/hash evidence found no Critical/Important or deferred Minor in this delta. Human forbids agents: independent review is still pending. Earlier U05 root Node42pass/2fail records remain immutable historical results; this new69pass gate resolves those two local prerequisites without rewriting history.

## Rulings I made

1. `continue` selects the recommended local gates follow-up after an optional pending scope question; no external work. If review-only was intended, the extra cost is local test execution/one test repair.
2. Human no-agents instruction overrides skill reviewer delegation; author review has less independence, so fresh review stays open.
3. Human tests-before-commit rule controls task-done: printed range cbb67dd..cbb67dd is precommit, not final reviewed/deployed SHA. Tested LF hash matches `d7ab5b6323402adf139d9b94e4e499f1631006b4` Git blob; misreading it would attribute proof to the wrong tree.
4. Full product live acceptance, human staff/screen-reader UAT, provider/performance/Q16 evidence and Neon/Cloudflare cutover remain separate: calling this gate release acceptance would claim untested capabilities.

Deferred minors: none in this delta. No benchmark/p95/p99/goldset claim follows from suite duration. Q16 remains blocked on underlying evidence; N00 remains a separate compatibility scope. No new eligible task selected; this is a reviewable local candidate.

## Rollback and reproduction

The reverse patch restores only the prior test, retaining task/evidence/status records and all application/database data. It will reinstate the stale literal-filename gate and remove new lifecycle coverage; no user membership/role/identity restoration is involved. Applicability only was tested. For a clean Linux checkout, install frozen pnpm dependencies, run `node scripts/run-vercel.mjs build`, ensure the local Docker daemon/image is available, then run the final root command above. The Windows-owned builder is preserved in reports/build-linux.mjs; it requires the recorded label-matching cached volume and refuses existing emitted output. First/second input manifests identify their separate owned resources. The ignored27,344,314-byte faithful build archive SHA is `fb37cbacf5402efa738c65cb4f835c49360d2e266a87faff7f9d56a04a086380`;2611 emitted file hashes are retained, actual bundle stays ignored.

## Raw-byte policy

Exact-prefix -text policy preserves captured bytes. Raw whitespace check exit2 reports 34 producer-only findings in logs/diff/patch/XML, retained unchanged; curated check excluding those identified producer files exits0. All four original fixture guard SHA256 values match. This is artifact formatting, not a hidden test failure.
