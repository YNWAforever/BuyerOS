# Q14 / PR-17 — same project job count/list scope

Base `092e8f555d7e98f0f2603ff86a7afecf8c65492e` → reviewed source **1aab3ddc0519bb6da8d1483efaf173eb5a87037e**,8 source files. [Exact diff](Q14.patch), [committed/tested hashes](q14-committed-source.json), [local PR description](../../../review/2026-10-03-audit-fixes/Q14-pr.md), [author review](../../../review/2026-10-03-audit-fixes/Q14-review.md). No push/remote PR/deployment/production action; deployed SHA null.

## F17 / U15 implementation

Shared `JobScope` and `buildJobQuery` bind project_id for selected-project count, generated listAsyncJobs page and failed-job navigation. Explicit workspace view omits project_id and labels Workspace jobs; existing server current actor/admin and tenant guard unchanged. Full frozen query selection resets pages/results by current session generation/scope/status/page; own abort guards reject A-B-A slow count/list responses. Current scope counts do not reuse stale cache.20-row real job pagination and typed Q03 item IDs preserved; read failure shows unavailable plus read-only Retry.

Router query state reads incoming job_scope/job_status. Only deliberate scope/status choices update URL; default no-project workspace fallback is not persisted over a later project choice. Pending requested project waits for authoritative selection. No membership, canonical identity, role, approval, job actor, Auth0/Cloudflare HMAC or delivery change. API/schema/generated contract unchanged; no provider calls.

## Environment / preservation

[Environment](q14-environment.json), [exact commands](q14-commands.json). Windows PowerShell Node24.18.0/pnpm11.25.0/uv0.11.27/Python3.14.6, Docker29.7.2, owned loopback PostgreSQL16 and actual restricted API/RLS. Owned Linux Node22.23.2 Vinext/Nitro dev4CPU6GiB → FastAPI8000; fake OIDC identity and fictional job rows only. **Fixture proof, not live login/provider/job execution/built preview/production verification.** Required DB strict1, external DSNs removed, zero skip.

[Preservation](q14-preservation.json): original31 inputs/hashes/required ZIP19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a unchanged,3 destructive guards unchanged, original checkout clean, unrelated Neon worktree193paths/rawdiffSHA unchanged. Original98case fields/25task CSV retained; [tracker integrity](q14-tracker-integrity.json) preserves97 other case rows/24 other task records and84-operation70+14 inventory.

## Meaningful RED / retained failures

| Run | Actual result / reason |
|---|---|
| [UI RED](q14-ui-red.xml), [log](q14-ui-red.log), q14-ui-red-artifacts |1 fail/0 skip. Actual selected project A has0failed; card displayed5 from project B |
| [First type/lint](q14-type-first.log), [lint](q14-lint-first.log) |exit2: JSX closing brace construction error; fixed without test change |
| [First UI](q14-ui-first.xml), [log](q14-ui-first.log), q14-ui-first-artifacts |2 pass/4 fail/0 skip,8.9m fixture lifecycle. Incoming job_status overwritten on mount; implicit workspace default persisted after project switch; consequently B project-specific race request never issued. Fixed router query read, explicit URL writes and pending-project guard |

Race test strengthened to hold both real B count+list responses before returning to A; no assertion/timeout/guard weakened. Initial selector used anchored B11 that selected8 rather than10; list output exposed mismatch, corrected to explicit titles, actual final10 executed. Listing is not a test pass.

## Final GREEN

| Check | Exact result |
|---|---|
| Strict API/DB/contracts |**18 pass/0 fail/error/skip**,126.17s,9 dependency warnings;3 new project/actor/21/101 cases+15related authorization/contracts; [JUnit](q14-api-final.xml), [log](q14-api-final.log) |
| Actual required Q14+Q03 UI |**10 pass/0 fail/skip**,5.2m fixture lifecycle;6Q14+4Q03 real result paging/zero/late job/page/scope; [JUnit](q14-ui-second.xml), [log](q14-ui-second.log), [actual selection10](q14-ui-selection.log) |
| Related Node |**16 pass/0 fail/skip**, [fresh gate](q14-gate-node.log).3new query tests; file checks include74adapter/8OIDC crypto assertions, not actual live auth |
| Generated/routes/type/lint |exit0 each;84operations=70original+14extensions; [routes](q14-routes-check.log), [completion gate](task-1-tests.log). No generated edits |
| Completion ledger |[Task1complete](progress.md); gate verifies8source hashes, freshly reruns Node/generated/type/lint and reads actual18/10JUnit. **Readback is not a new DB/UI run** |

U15 actual API-backed A0/B5/workspace5, reviewer-own5/operator3/admin8/viewer0, other actor detail404/cross tenant404; count/list consistent, complete21/101job lists20/page; scope reset0–0/0, held count+list A-B-A rejected; en/zh390 no overflow, filter/URL preserved through refresh+same-actor reauth,503 read retry succeeds. Q03 real producer21/101 result IDs fully traversed20/page; zero and late result/scope regression pass. No write on user reads; strict owned DB asserts outbox remains0.

[EN screenshot](q14-en-scope.png), [actual fixture metadata/url](q14-en-scope.json), [zh-HK390 screenshot](q14-zh-mobile.png). Mobile visually inspected. These are dev fixture screenshots, not live UAT.

## Rollback / limits / next

**0 migrations**, existing source head0037 retained; only normal guarded fixture upgrades, no production migration/schema/role change. Revert source commit `1aab3ddc0519bb6da8d1483efaf173eb5a87037e` or reverse [Q14.patch](Q14.patch); [reverse applicability](q14-rollback-check.log) exit0. This restores the earlier scope/count defect; all durable records/auth/RLS/actors/history remain. **Runtime/browser/production rollback not rehearsed.** No DB restore/downgrade.

[Cleanup](q14-fixture-cleanup.json): normal owned fixture teardown markers absent; positively owner-labelled cache retained for Q09. Unlabelled/other resources untouched. Independent review pending, no owner approval fabricated. User timing/human error/completion metrics/live performance not measured;5.2m is test lifecycle, not SLA. True login/provider/built/continuous transport/production/whole8-module journey gates remain unverified. Q16 underlying SQLSTATE/driver/pool cause blocked; Q17 not guessed; Q13 waitsN02. **Next eligible local task Q09** (Q01/Q02/Q05/Q14/Q15 satisfied), human staff UAT still needs actual participants. Code implemented, fixture verified, local integration verified; deployed no.

Evidence-builder-only first run hit Windows cp950 decoding the completed UTF-8 ledger before any document write; explicit UTF-8 read corrected it. No application source/test/guard changed, no fabricated test result.
