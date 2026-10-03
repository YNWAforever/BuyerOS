# PR-17: align project job counts and lists (Q14/F17)

Local branch codex/audit-fixes-20261003, base092e8f555d7e98f0f2603ff86a7afecf8c65492e, source1aab3ddc0519bb6da8d1483efaf173eb5a87037e. [8file diff](../../evidence/audit-fixes-20261003/Q14/Q14.patch). No remote PR/push/deployment.

## Changes

Shared generated job query for count/list/deep link; explicit labelled workspace view, current actor restrictions retained; scoped cache/page resets and A-B-A aborts. Router query read/explicit URL write avoids incoming filter overwrite; read-only503Retry, en/zh390 and real20row pagination. No API/schema/auth/provider change.

## Evidence

StrictAPI18/UI10(6Q14+4Q03)/Node16 pass,0fail/error/skip; generated84/type/lint0. [Exact commands, RED/failures, screenshots and limitations](../../evidence/audit-fixes-20261003/Q14/RESULTS.md).8normalized committed hashes match tested bytes, original98fields/31inputs/3guards/193unrelatedpaths retained. Author review only; independentpending.

## Rollback / remaining gates

Revertsource8filecommit/reversepatch applicability0; retains all DB/auth/RLS/history, restoresoldscopebug. Runtime rollback not rehearsed. Fictional OIDC/jobs/dev fixture only; liveauth/provider/built/continuousworker/production/fullstaffUAT/performance unverified. Delivery403. NextQ09; Q16cause/Q17blocked, Q13waitsN02.
