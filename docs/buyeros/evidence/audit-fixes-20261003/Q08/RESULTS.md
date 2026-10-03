# Q08 / PR-18 — bounded actor-bound maintenance manifest, local evidence

Base `80ecfc762a6b1aeb5ce6c205d0a641539aff54c1` → reviewed source **c98fb6860ce2d4f9ba1797abe919454edcb13204**,42 source paths. [Exact diff](Q08.patch), [committed/tested normalized hashes](q08-committed-source.json), [local PR description](../../../review/2026-10-03-audit-fixes/Q08-pr.md), [author review](../../../review/2026-10-03-audit-fixes/Q08-review.md). Local commits only; deployed SHA null, no remote PR/push/deployment/production action.

## Changes / F11

Canonical preview/read/execute adds three strictly generated operations. Frozen normalized filters/exclusions/operation/target/reason and every ordered ID/version bind canonical actor/workspace/project and SHA256 digest. One SQL statement snapshot streams250 rows; max10000,10001 atomically rejected without truncation. Existing ordinary selection/snapshot1000 stays. Fifteen-minute expiry, exact digest/If-Match/true confirmation, current membership/role/project/owner/list and RLS are checked. Same intent/key/body/precondition replay and concurrency produce one job/outbox/audit, no synthetic live rows. Synch100 and async101 boundary uses existing domain mutations and50-row fenced chunk engine; no provider activation.

Failed rows require a new explicit current-version preview, digest and child intent; manifest jobs reject legacy blind failed retry. UI en/zh-HK390px supports frozen metadata, colleague/list20-row paging, partial result20-row paging, read-only durable URL restore after reauth, same-key unknown response retry, A-B-A rejection, current-role denial and explicit cancel. Bearer stays in memory. Worker/Cloudflare HMAC/identity/memberships unchanged.

## Environment / integrity

[Environment](q08-environment.json), [commands](q08-commands.json). Windows PowerShell Node24.18.0/pnpm11.25.0/uv0.11.27/Python3.14.6, Docker29.7.2/PostgreSQL16. Owned Linux Node22.23.2 Vinext/Nitro dev4CPU6GiB, loopback FastAPI, actual restricted API/worker roles/RLS. Required DB strict1, external DSNs removed; [original three destructive guards unchanged](q08-db-guards.json). Fake OIDC/fit/fictional identities, manual shared worker chunks/drain: **fixture only**, no real provider/auth/continuous Celery/Valkey/Cloudflare/built preview acceptance.

[Input check](q08-input-integrity.json): all31 hashes and required evidence ZIP19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a retained; earlier safe nested ZIP/CRC/path inspection linked there. [Tracker integrity](q08-tracker-integrity.json): original98case fields/25task source CSV unchanged,92 other repair rows and24 other task records unchanged. [Preservation](q08-preservation.json): original root clean; unrelated Neon worktree193 dirty paths and raw diff hash unchanged.

## RED / failures retained

API RED1failure actual preview endpoint404; UI RED1failure absent Preview maintenance manifest control; Node RED1failure frozen intent body was mutable (2 other passes). These meaningful failures were observed before implementation. Construction executemany error is separate. Expanded API failures exposed missing existing data_mode envelope; second exposed stream Row rather than scalar. Contract made stricter/generated, no weakened assertion. Local10k test diagnosed loopback PG connection exhaustion with FATAL remaining connection slots reserved; existing per-request TestClient loops required a new Q08 lifespan wrapper. **Not evidence of Neon/Q16 cause.** Subsequent failures were wrong test CWD, lazy fake signing-key concurrency,51 cancellation requiring50+1chunks, stale settings cache/fixture column assumption; corrected setup/assertion to actual schema, no guard/timeouts/skips suppressed.

UI first failures exposed unnamed region/owned snapshot fixture cleanup. Later true recovery/overflow failures fixed explicit new child intent, old GET epoch invalidation and390px fieldset sizing. Token clearing on refresh requires reauth. Initial lint scope-effect fix derives state from current identity. Node-final mistakenly included a CLI traffic script without arguments; corrected dedicated CLI invocation, retains failed log. One PowerShell cp950 writer error and wrong output path are construction failures, not counted pass. All retained reports:

| Run | Actual report counts |
|---|---|
| [q08-10k-diagnostic](q08-10k-diagnostic.xml) |0 pass / 1 fail / 0 error / 0 skip |
| [q08-api-construction](q08-api-construction.xml) |0 pass / 1 fail / 0 error / 0 skip |
| [q08-api-expanded](q08-api-expanded.xml) |22 pass / 10 fail / 0 error / 0 skip |
| [q08-api-fifth](q08-api-fifth.xml) |34 pass / 3 fail / 0 error / 0 skip |
| [q08-api-first](q08-api-first.xml) |1 pass / 0 fail / 0 error / 0 skip |
| [q08-api-fourth](q08-api-fourth.xml) |30 pass / 2 fail / 0 error / 0 skip |
| [q08-api-red](q08-api-red.xml) |0 pass / 1 fail / 0 error / 0 skip |
| [q08-api-second](q08-api-second.xml) |27 pass / 5 fail / 0 error / 0 skip |
| [q08-api-sixth](q08-api-sixth.xml) |90 pass / 0 fail / 0 error / 0 skip |
| [q08-api-third](q08-api-third.xml) |31 pass / 1 fail / 0 error / 0 skip |
| [q08-db-corrections](q08-db-corrections.xml) |2 pass / 1 fail / 0 error / 0 skip |
| [q08-migrations-final](q08-migrations-final.xml) |39 pass / 0 fail / 0 error / 0 skip |
| [q08-migrations-first](q08-migrations-first.xml) |29 pass / 1 fail / 0 error / 0 skip |
| [q08-migrations-second](q08-migrations-second.xml) |17 pass / 0 fail / 0 error / 0 skip |
| [q08-ui-final](q08-ui-final.xml) |17 pass / 0 fail / 0 error / 0 skip |
| [q08-ui-first](q08-ui-first.xml) |0 pass / 1 fail / 5 error / 0 skip |
| [q08-ui-fourth](q08-ui-fourth.xml) |8 pass / 0 fail / 0 error / 0 skip |
| [q08-ui-red](q08-ui-red.xml) |0 pass / 1 fail / 0 error / 0 skip |
| [q08-ui-second](q08-ui-second.xml) |4 pass / 1 fail / 1 error / 0 skip |
| [q08-ui-third](q08-ui-third.xml) |6 pass / 1 fail / 1 error / 0 skip |

## Final required GREEN

| Check | Result |
|---|---|
| Strict API/DB/contracts |**90 pass/0 fail/error/skip**,243.45s,18 dependency warnings;19 new Q08 plus71 related; [JUnit](q08-api-sixth.xml), [log](q08-api-sixth.log) |
| Migration/rollback/backup compatibility |**39 pass/0 fail/error/skip**,88.62s,69 dependency warnings; [JUnit](q08-migrations-final.xml), [log](q08-migrations-final.log). Original shell argument grouping not retained; exact equivalent selectors reconstructed from actual JUnit in commands.json, explicitly identified |
| Actual UI |**17 pass/0 fail/skip**,4.4m fixture lifecycle:9 Q08+8 Q05; [JUnit](q08-ui-final.xml), [log](q08-ui-final.log), actual audit-*.spec.ts matched |
| Related Node |**22 pass/0 fail/skip**, [fresh gate log](q08-gate-node.log); one file test contains74 adapter assertions, not74 additional Node cases |
| Generated / routes / TypeScript / focused lint |exit0 each; [completion ledger log](task-1-tests.log), [routes](q08-routes-required.log).84operations=70original+14extensions; [coverage](q08-operation-coverage.json) |
| Task completion |[Task1complete](progress.md); gate freshly runs Node/generation/type/lint/hash/patch checks and reads actual90/17/39 JUnit. **Report reading is not a new DB/UI run** |

## Cases / screenshots

| Case | Actual evidence / scope |
|---|---|
| B01 |100/101/1000/1001 API and100/101/1001 UI, exactly once sync/async, no writes before confirmation |
| B08 |**Variant verified**:101 with1failed UI,10k with50failed DB; new current-version failed child; original100with20failed not run |
| B09 |**Variant verified**:101 UI cancel preserves50committed/51cancelled;10k DB uncommitted chunk rollback and independent Python-process restart resume. No continuous Celery OS-kill/restart rehearsal |
| B14 |**Partial**:1001 clipped warning UI and1000 snapshot DB bound; original select-all click/disabled assertion not separately executed |
| B15 |10000 fully frozen/9950updated/50conflicts,100APIpages/10kuniqueIDs, successful rows not repeated. Existing Q08 plan engine200x50 supersedes original CSV proposal10chunks |
| B16 |A-B-A held preview/current generation, project reselect; retains Q05/Q06 evidence. Same actor renewed token keeps intent key; refresh reauth reads durable metadata |

[EN100](q08-en-100.png), [EN101](q08-en-101.png), [EN1001](q08-en-1001.png), [zh-HK390px](q08-zh-mobile.png), [review](q08-review-en.png), [cancel](q08-cancel-en.png). Mobile visually inspected and overflow assertion passed. DB output proof q08-ui-100/101/1001.json; [unknown response recovery](q08-ui-unknown-recovery.json), [failed child](q08-ui-child.json), [cancel](q08-ui-cancel.json). Job results20-row paging visits all1001 rows over51pages. No whole8-module live acceptance.

## Migration / rollback / performance / limits

Inspected sole0036head before allocating additive **0037_bulk_manifests**; one Alembic owner. Forced tenant RLS, immutable frozen basis/items, runtime schema-version read-only guards preserved. Only owned disposable DB upgrades/empty downgrade-reupgrade/populated refusal tested; **production not migrated**. Necessary worker compatibility allowlist now includes0037; unknown schemas still rejected and selector unchanged. No actual backend selector/cutover change.

[Pause-admission patch](q08-pause-admission.patch) returns403 MANIFEST_ADMISSION_DISABLED only on new preview/execute POST; GET/recovery/cancel/results/chunks retained. Applicability exit0, [log](q08-rollback-check.log); **runtime/browser/production rollback not rehearsed**. Populated downgrade refuses by design. Preserve manifests/items/jobs/audits/results; no blind undo or database restore. Local unused code can be reverted before any durable manifests exist; do not erase populated history.

Performance conditions: server cursor250, workerchunk50, metadata≤10000exclusions, APIresult100/page, UI20/page; actual10k functional workload includes restart/100page traversal, not peak RSS/p95/p99/production SLA. [Logical poller traffic](q08-traffic.json) reuses Q06 samples: fake60s/10views/RTT2500ms, requests1250→140,maxaggregate130→10/perview13→1. Deterministic fake time only, not new live/HTTP/wallclock performance proof.

[Cleanup](q08-fixture-cleanup.json): normal fixture markers and owned labelled containers absent; exact owner-labelled dependency cache retained for Q14. Unlabelled resources untouched. Independent review pending; Q16 lacks underlying SQLSTATE/driver/pool evidence, Q17 not guessed; Q13 waitsN02, Neon N00 built compatibility/auth rehearsal separate. Real auth/provider/continuous transport/built preview/production/full staff journey/performance gates remain unverified. **Next eligible Q14**. Code implemented, fixture verified, local integration verified; deployed no.
