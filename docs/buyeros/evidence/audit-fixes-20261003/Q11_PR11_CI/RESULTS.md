# Q11 — PR11 CI repair checkpoint (2026-10-06)

Author-reviewed source `546a03770b32430f9ff90b7ac21c00fa74dd2166`, parent `38c55228489a12bfc493f27d2ed27e177117366e`, branch `codex/n00-api-request-context`. Existing Draft [PR11](https://github.com/YNWAforever/BuyerOS/pull/11) targets `codex/n00-native-ipc-isolation`, not `main`. **Local required gates verified; full Q11/N00/F20/NA01 remain OPEN.** Hosted CI after the pending push is a separate readback, not claimed by this commit.

## Changes and root causes

| File | Reviewable change |
| --- | --- |
| .github/workflows/buyeros-ci.yml | API checkout fetch-depth0 supplies actual Q06 baseline history; other jobs unchanged |
| services/api/tests/test_api_buyers.py | Six already implemented extensions declared; every declared method/path checked against runtime OpenAPI |
| tests/e2e/daily-workbench.spec.ts | Held preference GET permits manual locale, zero premature PATCH, exact If-Match, real DB saved version restored after reload/sign-in |
| playwright.workbench.config.ts | Scope outputDir to test-results/workbench/browser; protect sibling ignored evidence |
| docs/superpowers/plans/2026-10-06-q11-ci-audit-gates.md | Constraints, interfaces, RED/GREEN gates, publication and rollback |

The six extensions are listEligibleAssignees, getAsyncJobSummary, reviewDraftGrounding, previewBulkManifest, getBulkManifest and executeBulkManifest. No business/API/auth runtime or schema change; generated contracts remain 70 original +14 extensions=84. Application source remains `5aaf6492ec10078e4f1a4fa5b17efd41c5673eba`. Auth0/canonical IDs/memberships/RLS/historical actors/HMAC/delivery403 are preserved. No production mutation, paid provider, external email, manual deploy or auth/Cloudflare cutover.

## Exact local gates

| Gate | Pass | Fail | Error | Skip | Producer duration |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full strict API | 812 | 0 | 0 | 0 | 1990.119s JUnit;1990.14s pytest;172warnings |
| Final daily workbench | 8 | 0 | 0 | 0 | 85.567841s |
| Q01 actual built Linux entry | 7 | 0 | 0 | 0 | 127.74405s |
| Original T29 RED witness | 0 | 1 | 0 | 0 | 67.732543s |
| First corrected full workbench | 5 | 0 | 3 | 0 | 297.457946s |

Each final suite passed the required nonzero/no-failure/error/skip checker. TypeScript, scoped ESLint, generated contracts and operation-route checks exited0. Discovery812 API and7 Q01 is separately recorded and not counted as passing execution. Checks overlap; do not sum them as unique product cases. The prior N00 root/crypto/browser gate was not rerun in this CI repair.

Environment: Windows, Node24.18.0, Python3.14.6, Playwright1.63.0, Docker29.8.1; owned PostgreSQL16 only, BUYEROS_STRICT_INTEGRATION=1, production/shared DSNs unset. Workbench used retained matching .vercel/output application bytes. Q01 performed a fresh local owned Linux Node22.23.2/Nitro node-server build before executing7cases; its build warnings remain in auth-entry.log. No fresh hosted build or provider/live compatibility is claimed. Fake OIDC/mocked negative-access responses are fixtures; preferences and the complete API persistence suite use guarded actual HTTP/Postgres.

## Findings and cases

| Finding/case | Current result |
| --- | --- |
| F13/R05/Q11 | Current local status/CI repair evidence reconciled; external release comparison/full Q11 open; only this tracker row updated |
| F01/U02 | Existing Q01 no-membership recovery regression verified; no membership creation/grant; live membership/account journey not newly verified |
| F02/U03 | Existing negative403/404/500,manual locale/late response,read-only retry/expired sign-in verified in fixture |
| F15/U13 | Existing pre-hydration SSR has no false configuration alert; actual built Linux UI fixture verified |
| F20/NA01/N00 | Original partial status unchanged; OS boundary/true Neon/original302 remain open |

All other97 case rows and their original15 audit columns remain unchanged. Other24 root task objects and all31 legacy task objects, production-source/auth checkpoint fields and3741 original tracked input/evidence file bytes are preserved; following metadata validation records this. Original source/evidence packages are not modified. Independent review pending; this is author review under the no-agents instruction.

## RED, intermediate errors and historical evidence

[Original CI run37360072047](https://github.com/YNWAforever/BuyerOS/actions/runs/37360072047): API810pass2fail0skip, oldworkbench7pass1fail0skip; six other jobs passed. Raw job logs/metadata are included. Registry failure exposed the actual six operations; Q06 failed git show on default shallow checkout. Local actual shallow bare clone exit128 then full-history fetch exit0 read the exact baseline b083ea43988ed73e9d8e9ab112ba3d6305f2c941, source SHA2569731c9a299d99c902070cccec577c05a4579c27a56c782d9dcce215b2ed543dd (see history-proof.json). No synthetic baseline/fixture-only timing substituted for replay.

Initial registry invocation from root produced FileNotFound; correct service-cwd RED then targeted8pass occurred before old Playwright cleanup. The unscoped workbench default output directory started deleting ignored test-results siblings, including early fresh temporary reports, a clone and the ignored preceding finishing outputs. The exact owned runner was interrupted; no tests were counted. Original tracked audit/evidence remained unchanged. The new scoped outputDir prevents recurrence; original CI logs were recollected, scoped RED/XML and all subsequent attempts retained. Do not claim those deleted ignored reports are still available; the preceding committed N0081-member evidence remains intact. Early setup/clone attempts not retained as raw files are disclosed here, not fabricated. The later CP950 console read failure was corrected with PYTHONUTF8 and changed no tests.

The first corrected full workbench produced5pass/3beforeEach30s setup errors while full API was running; none of those failed setup cases reached the new assertion. Raw XML/log and three contexts remain included. Final serialized8pass retained the same30s helper/test caps and all application assertions. No retry configuration, timeout increase or disabled language control was introduced. A plan-only extra EOF line failed git diff --check exit2; removal passed0 before source commit.

## Performance conditions and results

Unchanged Q06 test: logical60seconds,10fictional current admins/views,1000persisted job results,simulated2500msRTT. Every scheduled request was replayed through actual runtime-role HTTP and captured SQL; production120/minute-per-actor limiter retained, fresh fixture windows between independent modes. This is traffic/bytes/DB-work comparison, **not wall-clock or production latency**.

| Measurement | Historical source | Current source |
| --- | ---: | ---: |
| Actual HTTP requests (all200) | 1250 | 140 |
| Response body bytes | 9293390 | 69440 |
| DB executes | 10000 | 840 |
| async_job_items executes | 2500 | 0 |
| Max concurrent per view | 13 | 1 |

Raw schedule,samples,Nodeoutput and measured results included. Windows API wall time1990.14s is this environment's test duration, not production performance.

## Commands, source and cleanup

See commands-environment.json,source-proof.json,source.patch,checks.json and raw JUnit/logs. Commands were run from services/api for pytest, root for others:

```powershell
$env:PYTHONUTF8='1'
$env:BUYEROS_STRICT_INTEGRATION='1'
# Unset DATABASE_URL,BUYEROS_TEST_DATABASE_URL,BUYEROS_DATABASE_URL,
# BUYEROS_EXECUTION_DATABASE_URL,BUYEROS_RUNTIME_ADMIN_DATABASE_URL.
uv run --frozen pytest -q --junitxml=../../test-results/pr11-ci-followup-20261006/api-full.xml
# Root; also unset BUYEROS_REUSE_TEST_SERVER.
$env:BUYEROS_E2E_FRONTEND='vercel-built'
node node_modules/@playwright/test/cli.js test --config playwright.workbench.config.ts tests/e2e/daily-workbench.spec.ts --reporter=line,junit
$env:BUYEROS_AUDIT_UI_RUNTIME='built'
node node_modules/@playwright/test/cli.js test --config playwright.audit-fixes.config.ts tests/e2e/audit-auth-entry.spec.ts --reporter=line,junit
services/api/.venv/Scripts/python.exe scripts/check-required-tests.py --junit REPORT
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js tests/e2e/daily-workbench.spec.ts playwright.workbench.config.ts --max-warnings=0
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
# services/api, read only:
uv run --frozen alembic heads
```

PLAYWRIGHT_JUNIT_OUTPUT_FILE selected each named report. Git text normalization is explicitly recorded; committed repair logical bytes match tested files. Four generated tracked Cloudflare test outputs were archived under generated/then restored to the exact existing HEAD, preserving prior evidence. Fixture finally/globalteardown removed owned API/DB/UI containers and markers; owned dependency cache retained. No global process/container prune. Screenshots include final en/zh mobile Operations and restored locale; that restored-locale frame has background profile/usage loading, not a completed whole staff journey.

## Rollback / remaining gates

Revert the following evidence/status checkpoint, then `546a03770b32430f9ff90b7ac21c00fa74dd2166`; source.patch supports reverse applicability proof. No new schema revision or data rollback; inspected single Alembic head0037_bulk_manifests. Do not reverse existing N00 hold/admission state or automatically resend unknown requests. Rollback is an applicability check, not a production rehearsal.

Publication/readback remains a separate authorized step for the existing PR only. No merge/main integration or manual deployment. Next eligible local work remains full N00 trusted parent/broker/browser/control-plane OS egress isolation composition, raw APIRequestContext/arbitrary provider CLI; real Neon/Google/admin cleanup only after full boundary review and fresh exact authorization. Original302,independent review,fullQ11/external comparison and live eight-module staff acceptance remain OPEN. No deployed SHA is asserted.

## Packaging-format follow-up

The first metadata git diff --check exited2 because the original Playwright failure JUnit CDATA and context source excerpts contain producer trailing spaces. Raw files were not edited. Whitespace exemptions apply only to copied producer XML/context/log/patch artifacts; source checks and all required tests retain their gates. metadata-whitespace-red.log records this attempt. Final staged formatting and raw manifest checks follow.
