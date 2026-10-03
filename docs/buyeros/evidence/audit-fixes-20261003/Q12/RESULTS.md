# Q12 / PR-15 — local manual source review evidence, 2026-10-03

Base `c7136fbceb1567bca87215b57d142e8137b8968d` → domain `63d140b4b5d4636b1fe9125ec3885d1e69bbecb4` → reviewed source **70d2e54ef613910ce5a684d90c4afce32f504e66**. [Exact17-file diff](Q12.patch), [committed/tested hashes](q12-committed-source.json), [local PR description](../../../review/2026-10-03-audit-fixes/Q12-pr.md), [author review](../../../review/2026-10-03-audit-fixes/Q12-review.md). No remote PR/push/deployment/production action; deployed SHA null.

## Changes / finding

F16 was still open: human edits cleared claims into needs_review and no manual source review route/UI existed. Canonical reviewDraftGrounding is reviewer/admin only and strict generated; it binds exact revision/hash/If-Match, all subject/body non-whitespace Unicode code points, versioned selected sources/approved selected offer facts, reason, actor/time and whole-message confirmation. Shared current approval context qualifies sources before any write; immutable successor preserves subject/body/language and adds proof/source-content binding/derived claims. Old exact review/approval invalidated; later edits remove proof. Source hashes/expiry/company/policy/recipient/sender/ICP are rechecked for replay/exact review/approval/export. No semantic-truth assertion, auto membership, identity link, paid provider or sending.

UI gives explicit unclassified line segments, Unicode split, source excerpts, per-segment/overall reasons and checkbox, stable ActionIntent retry, source-load recovery, current-scope protection and preserved failure buffers. Operator can prepare, reviewer attests. Q15 Save/Discard/Cancel remains intact.

## Environment / safety

[Environment](q12-environment.json), [exact commands](q12-commands.json): Windows PowerShell Node24.18.0/pnpm11.25.0/uv0.11.27, locked Python3.14.6, Docker29.7.2/PostgreSQL16, Playwright1.63.0 Chromium. Owned Linux Node22.23.2-bookworm-slim Vinext/Nitro dev4CPU/6GiB localhost5173 → real FastAPI8000/runtime-RLS disposable DB. Strict1 required DB suites; remove external DSNs first; [three destructive guards unchanged](q12-db-guards.json). Fictional OIDC/contact/purpose/source inputs; test source availability is not live source/provider verification. API-created zero-cost draft dispatch is fixture-staged; actual shared fenced worker materializes then rejects duplicate, paid operations/holds0→0. No continuous Celery/Valkey/Cloudflare/built preview claim.

[Safe original evidence check](q12-input-integrity.json): outerZIPf11c2c..., required nestedZIP19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a, CRCs/safe paths/no symlinks/all31hashes. Original98case fields/25task CSV/frozen plan unchanged. Historical reproduction script was read; obsolete fake-query shape after Q06 was not blindly run. [Unrelated worktree preservation](q12-preflight-preservation.json).

## RED / failures retained

| Run | Result | Meaning |
|---|---|---|
| [API RED](q12-api-red.xml), [log](q12-api-red.log) |1fail/0skip| Actual earlier approval + edit then new manual endpoint404 NOT_FOUND |
| [UI RED](q12-ui-red.xml), [log](q12-ui-red.log), trace directory q12-ui-red-artifacts |1fail/0skip| Actual saved edited Unicode draft lacks Manual source review region |
| [First API green](q12-api-first.xml) |23pass/0fail/0skip| Before further current-source/concurrency/role hardening; not final85 |
| [First UI](q12-ui-first-green.xml), traces q12-ui-first-green-artifacts |2pass/2fail/0skip| Success notice locator targeted inner panel; classification read empty region before source loaded. Corrected exact locator/wait, original60s timeout unchanged |
| [Second combined UI](q12-ui-second.xml), traces q12-ui-second-artifacts |15pass/1fail/0skip| All12 Q15/Q07 and most Q12 pass. Lost committed same-key/body retry passed; hard reload intentionally cleared in-memory bearer. Test reauthenticates same reviewer; no token persistence/auth change |
| [Broader dev transport UI](q12-ui-transport.xml), [log](q12-ui-transport.log), traces q12-ui-transport-artifacts |14pass/2fail/0skip| Initial listDrafts/getDraft unstructured500 x-unknown before manual actions, local dev read ECONNRESET/socket hang up. Exact socket/root cause unproven. No Neon/Q16 inference, fixture/timeouts/assertions/product proxy unchanged; **this run is failed** |

Generated map initially stale after adding canonical operation; regenerate, no hand edit. Lint initially found render-time Date.now; capture timestamp at completed source fetch. Root-relative shell prep run in services/api failed before write; one partial API run interrupted, not counted verification. Original tests/guards are not weakened, zero tests/skip not counted pass. Raw q12-ui-final duplicates transport failure, explicitly not final green.

## Final required GREEN

| Check | Exact result / report |
|---|---|
| Required strict API/DB/contracts/roles | **85pass/0fail/0error/0skip**,83.205s,7 dependency warnings; [log](q12-api-final.log), [JUnit](q12-api-final.xml).31new manual-grounding cases +54related |
| Required actual Q12 UI | **4pass/0fail/0skip**,1.5m fixture lifecycle; [log](q12-ui-named-final.log), [JUnit](q12-ui-named-final.xml). Actual audit-*.spec.ts executed with existing audit config/testMatch |
| Related Node | **14pass/0fail/0skip**; [log](q12-unit-final.log).12unitguard/intent/codepoint +2 file tests containing74adapter+8auth internal checks |
| Generated contracts / type / focused lint | exit0 each; [fresh aggregate](q12-task-done.log), [operation map](q12-operation-map-check.log). **81=70original+11extensions**; [actual original API baseline](original-70-api-operation-coverage.csv), [coverage](q12-operation-coverage.json); generated artifacts regenerated from canonical contract |
| Alembic source | [0036_checkpoint_schema_grants (head)](q12-alembic-heads.log); **0new revisions/migrations**, no production DB access |
| Completion ledger | [Task1complete](progress.md), [gate](q12-final-gate.mjs). Gate checks exact completed DB/UI JUnit/output, freshly reruns Node/contract/type/lint/rollback; report reading is not a new DB/UI run |

No passing full16final UI run is asserted. Predecessor12passed on identical17-file application code in the prior15/1run; required4Q12passed in a fresh owned fixture. Broader transport instability remains an environment/release limitation.

## Case results / artifacts

| Case | Current classification | Actual evidence |
|---|---|---|
| D01/F16 | Fixed with local fixture/integration; live rollout unverified | Human edit → full segment qualification → immutable successor → new exact review → approval/export; old approval invalidated, exact original text retained, SQL history and actor audit |
| D03/F16 | Fixed with local fixture/integration; live source truth unverified | Unreviewed edits denied; full current source/content/tenant/role/policy/sender/recipient/ICP checks; gap/overlap/UTF16/emoji/expired/digest/stale and injected actor denied atomically |
| U09/F14 | **Partial draft slice verified; full staff journey open** | Draft edit/source/approval/export/refresh+reauth/roles/scope slice only; no whole8-module/live staff acceptance |

[EN proof/result](q12-en-output.json), [same-key committed-drop Retry](q12-en-retry.json), [download](q12-en-export.txt), [EN approved screenshot](q12-en-approved-export.png); [zh-HK proof/result](q12-zh-output.json), [download](q12-zh-export.txt), [390px source-review screenshot](q12-zh-mobile-review.png), [approved/export screenshot](q12-zh-mobile-approved-export.png). Mobile source review visually inspected; viewport overflow assertion passed. Viewer export403 and approved draft delivery403 DELIVERY_DISABLED. Separate interpreter + new app/engine reads stored proof; concurrent same key creates exactly1successor/audit. Test OIDC sign-in and session remount are not Neon/Auth0 live verification.

## Rollback / remaining limits

[Pause-entry patch](q12-grounding-pause-rollback.patch) disables manual submit and returns403 at only new endpoint; preserve source-proof/context validation, immutable revisions/audit/approvals and Q15 buffers. Patch applicability and [full diff reverse applicability](q12-rollback-check.log) exit0. **Runtime/browser/production rollback not rehearsed.** No DB downgrade. Avoid reverting shared proof validation while reviewed rows remain; old logic would reject valid non-factual manual history. Keep all persisted history.

[Cleanup](q12-fixture-cleanup.json): normal UI/DB teardown markers absent, labelled UI containers absent, exact owner-labelled dependency volume removed. Unlabelled `buyeros-test-d9323d06` may be interrupted API fixture but ownership not proven, intentionally untouched; older/other Docker resources untouched. Review worktree retained.

Performance conditions: subject≤300/body≤20000 code points, ≤200segments, per-segment evidence≤50/facts≤20; bounded structural qualification. Test duration is not production latency/SLA; no live p95/p99/performance acceptance. Independent review pending. True Auth0/Neon account rehearsal/N00 built compatibility, provider/worker/Cloudflare/live auth/build/production/full journey gates unverified. Q16 lacks SQLSTATE/driver/pool root cause; Q17 not guessed. Q13 waitsN02; next eligible local task **Q08**. Code implemented; fixture verified; local integration verified; deployed no, live product acceptance unverified.

Evidence construction initially tried the audit UI OP01 inventory for API coverage; its integrity assertion rejected that wrong input. Coverage uses the separate original70 API_OPERATION_COVERAGE.csv instead. No original audit inventory or application assertion changed. Checkpoint construction scripts are historical evidence, not commands to blindly rerun against the completed tracker.
