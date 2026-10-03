# PR-18: bounded maintenance manifest (Q08/F11)

## Source

Local branch codex/audit-fixes-20261003, base80ecfc762a6b1aeb5ce6c205d0a641539aff54c1, commitc98fb6860ce2d4f9ba1797abe919454edcb13204. [42-file diff](../../evidence/audit-fixes-20261003/Q08/Q08.patch). No remote PR/push/deployment.

## Changes

- Actor-bound immutable filter/target/reason/id/version preview/read/execute,10000limit/10001atomic rejection; ordinarysnapshot1000 unchanged.
- Canonical sync100/async101 shared50row engine, forcedRLS/currentroles, stableunknownreplay,20row results; new explicit failed-onlychild.
- en/zh-HK390UI/read-onlyrestore/current-scopeguard/cancel/partialresults, strictly generated84operations.
- Additive0037, immutabilityguards, safeemptyroundtrip/populateddowngraderefusal; existing migration security/workercompatiblehead assertions reconciled.

## Verification

StrictAPI90, migration39, actualUI17(9Q08+8Q05),Node22 pass,0fail/error/skip; generated/type/lint exit0. [Exact reports/commands/failed runs/screenshots](../../evidence/audit-fixes-20261003/Q08/RESULTS.md). Author review only; independentpending. Original31inputs/98casefields/3guards/unrelated193worktreepaths preserved.

## Rollback / risks

Pause new admissions using supplied checked patch; retain manifests/jobresults/history/recovery. Production migration unperformed; populated downgrade refuses. Actual runtime rollback not rehearsed. B08/B09variant/B14partial, fixturefakeOIDC/manualworkerchunks, no liveprovider/continuousbroker/build/performance/fullstaffUATclaim. Delivery403, Auth0retained/NeonandCloudflarecutoverseparate. NextQ14.
