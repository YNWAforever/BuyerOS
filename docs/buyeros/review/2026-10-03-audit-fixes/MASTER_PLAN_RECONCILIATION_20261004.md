# Master-plan reconciliation — 2026-10-04 HKT

Reviewed local N00 source `261a9e51d9d038c68be1d0d67002fcbe6e1eff6c`; active branch `codex/neon-auth-compatibility-local-20261004`. Remote GitHub main read-only SHA `a78859fe474f5722be3755b10e2586436b53bf97` (matches audit source). Local main ref3f10f419 differs; no reset/fetch/push. Original evidence ZIP SHA19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a and31inputs unchanged. Source/evidence graphs from the historical dirty worktree were not copied.

## Interpretation / constraints

The immutable master plan is docs/superpowers/plans/2026-10-03-buyeros-gpt61-fixes.md. Its historical plan-only sentence is superseded by the human local execution request; local code/tests/commits are authorized. Specific production/deployment/accounts/linking/roles/email/provider/paid/Cloudflare actions require their own current authority. Expired preview approvals were not reused. No agents; independent review remains pending. Canonical users.id/memberships/owner/approval/audit/job actor, one domain API/migration owner, Auth0 release path, independent HMAC and delivery403 are retained.

Statuses for earlier Q tasks below are carried from committed TASKS.json and linked task evidence, not fresh reruns or live acceptance in this continuation. Fresh checks here cover only the N00 local transport component, generated types and immutable preservation. The ledger label outside-current-scope means not implemented in this selected local continuation, never completed or cancelled.

## All 25 task IDs / exact master predecessors

| ID | Master predecessor | Current evidence/status |
|---|---|---|
| N00 | 無 | partial：本輪 transport verified；strict callback/真 Neon gate open |
| N01 | N00 | 未開始；等 N00 精確 trust/runtime 契約 |
| N02 | N00 | 未開始；等 N00；canonical mapping 尚未實作 |
| N03 | N01、N02 | 未開始；等 N01/N02；診斷驗簽不等於 domain adapter |
| N04 | N01、N03、Q01、Q04 | 未開始；等 N01/N03；Auth0 UI 仍保留 |
| N05 | N02、N03、N04 | 未開始；等 N02/N03/N04；Neon 八模組回歸未執行 |
| N06 | N05、Q12、Q15 | 未開始；等 N05；人類帳戶 mapping/rehearsal 另需授權 |
| N07 | N06、Q11 | 未開始；等 N06/Q11-Auth；無 production cutover |
| Q01 | 無 | local fixture verified；真帳戶 U01 gate 仍未由此關閉 |
| Q02 | Q01 | local integration/fixture verified |
| Q03 | Q01 | local integration/fixture verified |
| Q04 | Q01 | local durable lost-response intent verified |
| Q05 | Q02 | local integration/fixture verified |
| Q06 | Q03 | local summary/polling verified；非 live SLA |
| Q07 | Q15 | local template/grounding fixture verified |
| Q08 | Q05、Q06 | local durable 10k manifest integration verified |
| Q09 | Q01、Q02、Q05、Q14、Q15 | local candidate；U05 続接修復已有證據；screen reader/staff human gates open |
| Q10 | Q06、Q08、Q12、Q13、Q09 | partial tools/controlled baseline；SQL gate FAIL；Q13/真 accuracy/live perf 未完成 |
| Q11 | 無 | baseline recorded；分能力 release gates 未全部關閉 |
| Q12 | Q15 | local manual-proof/approval integration verified；完整 journey gate 獨立 |
| Q13 | N02 | 未開始；等 N02 resolver；P09/P10 仍 open |
| Q14 | Q03 | local current-scope count/list verified |
| Q15 | Q01 | local Save/Discard/Cancel integration verified |
| Q16 | 無 | blocked：只有 OperationalError；沒有 driver/SQLSTATE/pool/compute 根因 |
| Q17 | Q16 | 未開始；Q16 無根因，不猜測修法 |

## Execution decision / next eligible

Continue **N00**, rather than restart Q11/Q01 or mark later N tasks done. This checkpoint adds counted owned HTTP transport and two official-SDK built tests;80relatedNodepass/0skip, each wholebuilt7cases6pass1fail0skip. Original302assertion fails portable500/Vercel200; fullN00/NA01 remains open. Nine overlay hashes and all89/2214emittedfiles match the previous actual build archives; no new build/live provider verification.

Next local work: prepare real-only built runtime/configuration and full SDK/browser/CLI accounting with exact target readback; keep fixtures separate. The concrete external gate is the fresh runbook neon-auth-n00-real-roundtrip-20261004.md: new empty isolated Auth project and one human-operated Google test identity, US$0/no subscription upgrade, at most200checks with20cleanup reserve, two-hour cleanup, no production/Cloudflare/accounts linking/memberships/email. It remains a proposal; NULL IDs/issuer/audience/JWKS are not approval/readback. Actual actions cannot proceed on continue alone.

N01/N02 require N00, Q13 requires N02; Q10 full SQL/accuracy/perf acceptance remains open; Q09 human screen-reader and staff UAT metrics remain NULL. Q16 requires underlying driver/SQLSTATE/time/pool/compute evidence for request1d123054-2633-40b7-8e07-b6aed83dad98 at2026-10-02T19:40:34Z, before Q17 is eligible. No Neon cold-start/pool hypothesis is treated as a diagnosis.

## Evidence / rollback

[Current N00 results](../../evidence/audit-fixes-20261003/N00_COUNTED_TRANSPORT/RESULTS.md), [exact commands](../../evidence/audit-fixes-20261003/N00_COUNTED_TRANSPORT/COMMANDS.md), [local PR boundary](N00-pr.md). Revert261a9e5 plus this metadata checkpoint; reverse source patch applicability checked0, no runtime/data/resource rollback performed. Existing84operation rows (70original+14extensions) unchanged; no new live coverage. Code implemented / fixture verified / actual loopback integration verified / external auth blocked-unverified / deployednone are separate facts. No eight-module live or product-ready claim.
