# U05 / F04 — current membership withdrawal local candidate (2026-10-04)

Source `25694d3b938e704e883f9915cf0604bbdbac1daf`; base `e8e478c9e5a5812d43169759d39ddea1d5529098`. Local source commits `540696bc58c66ff75b3a8d95c283bc13dbef4328` and `25694d3b938e704e883f9915cf0604bbdbac1daf`. Auth0 remains the login adapter; no deployed SHA.

## Implemented

- JSON and export-content scoped 403/404 notify only the current identity/workspace. The existing paginated workspace API rechecks current DB membership; a denial alone never proves withdrawal.
- Confirmed withdrawal clears workspace/project/profile and actor-bound job/draft URL pointers, unmounts private UI and aborts old scope requests. The bearer stays in memory and the person can select another authorized workspace. No automatic switch or grant.
- Check access again remains available on an open page. Ordinary forbidden/missing resources retain legitimate scope; current role downgrade updates controls while preserving dirty Unicode subject/body/language. Failed membership rechecks retain the editor and offer explicit retry.
- Denials received during an in-flight check coalesce into one subsequent current-identity read. No write replay. New users, memberships and identity links are not created by the application.

## Environment and exact gates

Windows PowerShell; host Node24.18.0/uv0.11.27, frozen Python API environment. Actual owned Linux Node22.23.2 built Vinext/Nitro node-server UI,4CPU/6GiB, localhost5173; loopback API8000, owned disposable PostgreSQL16, non-owner runtime/RLS. Fake OIDC identities and fictional jobs/drafts; no live Auth0/Neon/provider/worker acceptance.

All DB variables `BUYEROS_DATABASE_URL`, `DATABASE_URL`, `TEST_DATABASE_URL`, `BUYEROS_TEST_DATABASE_URL` were removed before destructive tests. `BUYEROS_STRICT_INTEGRATION=1`; existing guards unchanged.

| Command (cwd repo unless stated) | Exact result |
|---|---|
| `pwsh.exe -NoProfile -File test-results/u05-native-gate.ps1` via executing-plans task-done | **36pass/0fail/0error/0skip/0flaky**, 476.869216s;10 U05 +7 auth-entry +10 dirty-draft +9 membership cases |
| `node --test tests/audit-access-denial.test.mjs tests/audit-auth-render.test.mjs tests/audit-member-contract.test.mjs tests/audit-draft-guard.test.mjs tests/audit-research-intent.test.mjs` | **17pass/0fail/0skip**, final source |
| `services/api`: `uv run --frozen pytest -q tests/test_auth_routes_db.py tests/test_membership_directory_db.py tests/test_exports_authorization_db.py tests/test_auth_cache_lifecycle.py tests/test_retention_authorization_db.py tests/test_api_routes_contract.py --junitxml=../../test-results/u05-api.xml` | **38pass/0fail/0error/0skip**,50.33s;12 deprecation warnings retained; backend source unchanged through final candidate |
| `node --test 'tests/*.test.mjs'` | **42pass/2fail/0skip** at initial U05 candidate; legacy teardown-name assertion and missing `.vercel/output/functions/__server.func/index.mjs`; both reproduced from base-exported files/configs. Not a green whole-branch gate. Assertions unchanged |
| `node` each `tests/*checks.mjs` | domain11, poller11, adapter74, auth8, runs4 pass; no failures/skips; retained individual logs |
| `node node_modules/typescript/bin/tsc --noEmit` | exit0 |
| `node node_modules/eslint/bin/eslint.js services/live/client.ts features/live/workspace-picker.tsx tests/e2e/audit-access-revocation.spec.ts tests/audit-access-denial.test.mjs --max-warnings=0` | exit0 |
| `node scripts/generate-api-types.mjs --check` | exit0 |
| `services/api`: `uv run --frozen python ../../scripts/generate-operation-routes.py --check` | exit0;84 operations=70original+14existing extensions;0new U05 operations |
| `services/api`: `uv run --frozen alembic heads` |0037_bulk_manifests(head);0new migrations |

Gate wrapper and exact task-done invocation/output are retained under reports. TestMatch genuinely selected the new audit spec. These suite times are test wall time; no SLA/p95/p99, production workload or goldset benchmark was run.

## RED, review fix and durable evidence

Initial dev-overlay sign-in failure and a GET-vs-POST fixture response wait error are retained separately as setup failures. Client contract RED4 missing notifier failures is separate from the meaningful behavioral RED: real admin withdrawal committed version2; subsequent reads/writes404; UI still had Project selector1 instead of0. First new9 and combined35 green checkpoints are retained.

Author review found the same-generation held-directory race. New real HTTP/DB test RED Project1 instead of0; one coalesced follow-up fix passed the whole36 suite. Author review only; human prohibited agents, independent review remains open.

Final JSON contains 6 raw HTTP/SQL proof bodies. U05 en/zh-HK390 screenshot files now capture the exact asserted scenario locale; earlier first-green filenames followed a later language toggle and are historical, not rendered-language evidence. Proofs show active=false/version2, read/write404, unchanged user/membership counts, one denied draft PATCH and stored revision1; ordinary403 role downgrade retains dirty Unicode fields. Held old data/access responses complete or abort before assertions; A/B scope race and failed recheck recovery pass.

## Source / data preservation

Six tested LF-normalized files match source commit blobs; actual runtime application hashes match the two edited application files. Original31 pack inputs, Q09FINAL161 and Q09KEYBOARD141 raw files match their manifests. All98 historical first15 fields,97other case rows,24other tasks,84operation records,4destructive guards and unrelated root/Neon worktrees preserved. Case U05 repair fields and Q02 follow-up only updated. Fixture setup/cleanup is explicit and disposable, not production reactivation.

## Rollback

`git apply --reverse --check docs/buyeros/evidence/audit-fixes-20261003/U05/reports/u05-source-rollback.patch` passed exit0. The patch covers five application/test/fixture files only and retains evidence/plan/status documents. Apply reverse and commit only if rollback is selected. DB authority stays intact; never reactivate a withdrawn membership or restore the DB to undo this UI change. Runtime/browser/production rollback was **not rehearsed**. No production migration, membership/identity mutation, auth/Cloudflare cutover, push, merge, deployment, paid activation or delivery action occurred.

## Remaining gates / rulings

- Whole-root Node inherited2 failures require separate gate work; independent review and actual staff/screen-reader/provider/production acceptance remain open. Q16 underlying cause, Q17 and N00–N07 remain separate; no cause inferred.
- Selected U05 adds one Q02 follow-up; other scopes remain unverified if this boundary is insufficient.
- Human forbids agents; author review has less independence.
- Task-done was run before source commits to satisfy tests-before-commit. Its printed range ends an earlier commit; final source/hash checks above define the candidate, never a deployed SHA.
- Retain inherited/environment Node2 failures without weakening assertions; branch promotion is blocked by that non-green whole-root gate. Local U05 regression gate is verified.
