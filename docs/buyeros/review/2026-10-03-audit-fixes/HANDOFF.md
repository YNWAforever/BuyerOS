# BuyerOS 首輪修復交接 — 2026-10-03

## 本次交付及來源

本次完成 Q11 baseline 與 Q01／Q03／Q04／Q15 的本地實作、測試、四個可獨立回退的 task commits、精確 PR 描述和 binary diffs。分支 `codex/audit-fixes-20261003`；worktree `C:/Users/laich/.codex/worktrees/audit-fixes-20261003/BuyerOS` 保留供 review。沒有 push、GitHub PR、merge 或部署。

- Audit／本輪起點／remote main：`a78859fe474f5722be3755b10e2586436b53bf97`；交接前唯讀再次核對相同。
- Reviewed code source：`3efd1f3f97036e1988751d1dfb54d37d48d0929a`。
- 實際測試的 Git tree：`ae62fa34c8601a826e0056c5e66de9cac2e48d57`。最後補強測試納回各 task commit 後 tree 完全相同；其後只加入交接文件／證據。
- 本輪 deployed SHA：**無**。稽核報告的舊 deployment `dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp` 不是本輪修復的部署證據。
- Q11 baseline commit：`576c3b182819b392f8b73697457769d6f16a496c`；只完成凍結及分能力記錄，未關閉全產品 release gates。
- 原 checkout HEAD `671fed7aa580f2c700aa04110f4a5a44e23a2ac1` 仍 clean；另一個 dirty Neon worktree 未改動，仍在 audit SHA。

## 四個 PR 邊界

| Task／finding／cases | Commit | 實作 | Review artifacts |
|---|---|---|---|
| Q01 · F01/F02/F15 · U02/U03/U13（U01 受阻） | `8251027ddcf781e5cae713da4190d32a77a81dbd` | hydration initializing 狀態；無會員／錯誤仍能選語言及唯讀重查；不補會員 | [PR 描述](Q01-pr.md) · [完整 diff](../../evidence/audit-fixes-20261003/diffs/Q01.patch) |
| Q03 · F05 · B10/B11 | `f5936cef6b363e3662c9b84c6153ea2c43f8117b` | generated AsyncJob／BulkItemResult.id；20 列分頁；21/101 真 schema API payload 全讀；拒絕舊 job/page/A-B-A 回應 | [PR 描述](Q03-pr.md) · [完整 diff](../../evidence/audit-fixes-20261003/diffs/Q03.patch) |
| Q04 · F08 · B05/B06 | `fc8fae75dfd743feaf590e73a099443d23e34788` | 既有 ActionIntent 綁完整正規化 body／actor／workspace／project／ICP；token renew 不換 key；未知結果同意圖 Retry；route remount 保留 body/key | [PR 描述](Q04-pr.md) · [完整 diff](../../evidence/audit-fixes-20261003/diffs/Q04.patch) |
| Q15 · F19 · D02 | `3efd1f3f97036e1988751d1dfb54d37d48d0929a` | Refresh／Open／Job 共用 Save／Discard／Cancel；失敗保留 buffer/baseline；412 比對及實際複製；focus／Escape／單一 transition／scope fence | [PR 描述](Q15-pr.md) · [完整 diff](../../evidence/audit-fixes-20261003/diffs/Q15.patch) |

四個 diff 有各自精確 base/head。建議依 Q01 → Q03 → Q04 → Q15 review；Q01 提供共用 audit config，其他三項產品邏輯獨立。如果要四個同 main base 的 PR，先分出 Q01 測試 infrastructure，再依描述 cherry-pick；不要直接將累積分支當成四個相同 diff。

## 測試證據

全部數字依 pass／fail／skip。必要 backend suites 均 `BUYEROS_STRICT_INTEGRATION=1`，使用既有 guard 接受的 owned Docker PostgreSQL，沒有 Neon／正式／shared DSN，沒有移除 guard。

| Gate | 結果 | Exact output / artifact |
|---|---|---|
| 最終全 audit UI | **22／0／0** | `22 passed (3.2m)`；JUnit tests22/failures0/errors0/skipped0，194.822486s；`final-ui-green.log`／`final-ui.xml` |
| Q01 render + UI | 1／0／0 + 7／0／0 | `Q01-render-green.log`／`Q01-ui.xml` |
| Q03 UI | 4／0／0 | `Q03-ui.xml`；21/101 actual API JSON payloads |
| Q04 UI + intent unit | 1／0／0 + 3／0／0 | `Q04-ui.xml`／`Q04-unit-final.log`／`final-audit-research-intent.json` |
| Q15 UI + guard unit | 10／0／0 + 7／0／0 | `Q15-ui.xml`／`Q15-unit-final.log`；最終 22-case gate 另包含 clipboard 及研究雙擊 |
| Q01 strict auth/routes/contract | 13／0／0 | `13 passed, 7 warnings in 16.90s` |
| Q03 strict bulk DB | 10／0／0 | `10 passed, 9 warnings in 36.93s` |
| Q04 strict admission validation + integration | 14／0／0 | `14 passed, 7 warnings in 23.53s` |
| Q15 strict draft persistence + approval | 27／0／0 | `27 passed, 7 warnings in 124.80s (0:02:04)` |
| Q15 strict grounded worker | 11／0／0 | `11 passed, 4 warnings in 29.20s` |
| 最終新 unit/render 合併 | 11／0／0 | `final-unit.log` |
| 現有 auth checks | 8／0／0 | `8 live auth checks passed including OIDC crypto`；檔名有 live，仍是 fixture 檢查 |
| 現有 adapter checks | 74／0／0 | `74 live adapter checks passed`；不代表 provider 已驗證 |
| generated contracts/routes | exit0／exit0 | `Operation route map matches OpenAPI: 78 operations` |
| strict TypeScript / changed-file lint | exit0／exit0 | `final-types-verified.log`／`final-lint-verified.log`；實際 paths 在 `final-lint-paths.json` |

Exact commands、cwd、environment、counts 逐項列於 [commands.json](../../evidence/audit-fixes-20261003/commands.json)。完整 logs/JUnit/screenshots 都在 [evidence directory](../../evidence/audit-fixes-20261003)。沒有把 0 tests、collect-only 或 skip 算作通過。

### RED → GREEN

- Q01：實際 callback render RED 1 fail；UI RED 1 pass／5 fail，disabled locale 被重現。修正後 render1／UI7 pass。
- Q03：UI RED 3 fail（結果 ID／分頁），GREEN4 pass。
- Q04：先讓 real API commit，再丟 202；Retry 的 key 改變，RED 實際 DB 變成 **2 runs／2 admission outboxes／2 economic ceilings**。GREEN key/body/run ID 相同，DB **1／1／1**。最終 gate 的兩次同步 UI Start handler 也只造成一次 request；token renew／完整 body delta／A-B-A 有真正服務 unit assertions。
- Q15：有效 RED 是 Refresh 把 `Local unsaved body` 覆蓋成 `Fictional draft 1 content`，1 fail。GREEN10 包含 Save 等待真正 PATCH、401／412／503 buffer/baseline 保留、Cancel/Escape、job materialization 及 zh-HK/390px。
- 環境／fixture 失敗另存：Windows dev transport、最初 port mapping、locator、test-owned result field／pagination、shared DB locale，以及 native Windows clipboard CRLF。這些沒有拿來當產品 RED，也沒有刪掉歷史失敗。最終 clipboard raw/normalized 都保留，除平台換行外逐字比對。

### 環境及可解讀範圍

Windows PowerShell；host Node24.18.0／pnpm11.25.0／uv0.11.27；API/worker Python3.14.6；Docker29.7.2；Chromium/Playwright1.63.0。UI 使用既有 Vinext/Nitro Node target，在 owned Linux `node:22.23.2-bookworm-slim`（4 CPU／6 GiB）執行；image digest 在 `final-integrity.json`。API 是 127.0.0.1:8000，UI 是 localhost:5173，同源 proxy；fictional RSA/OIDC principals；DB 是 owned local PostgreSQL16。

此證據是 local HTTP/UI/SQL integration，不是 Vercel/Cloudflare built-output deployment proof、真 Auth0 login、Neon preview、真 provider 或員工 UAT。Q04 admission 不建立 provider operation／reservation，兩者實際是0；一個經濟意圖指一個 bounded run budget account，不聲稱 hold/provider acceptance 已驗證。Q15 test-owned job completion與既有 worker 持久化測試分開報告。

## 全部 F-ID 現況

| Finding | 本輪結論 | 證據／未完成原因 |
|---|---|---|
| F01 | recovery UI 已修；正式 access gate 仍 open | U02 fixture-pass；U01 真帳戶／membership journey 未驗證，未增會員 |
| F02 | local fixture verified | Q01／U03 |
| F03 | still open；未重測 | audit-source 部分 unchanged；outside selected scope |
| F04 | still open；未重測 | outside selected scope |
| F05 | local integration/UI verified | Q03／B10/B11 |
| F06 | still open；未重測完整案例 | Q03 有結果頁 A-B-A，但未把 Q06／B16 完整 selection/resume 說成完成 |
| F07 | still open；未重測 | outside selected scope |
| F08 | local durability/UI verified | Q04／B05/B06；DB1/1/1 |
| F09 | still open；未重測 | outside selected scope |
| F10 | external gate open | 真 provider allowlist 未啟用；fixture 不算 live |
| F11 | still open；未重測 | outside selected scope |
| F12 | external gate open | performance／goldset／真 journey 未測 |
| F13 | Q11 baseline 部分完成；release gates open | 單一 current record 已建；production schema/role/selector/epoch/recovery 未 readback |
| F14 | still open；未重測 | outside selected scope |
| F15 | local render/UI verified | Q01／U13 |
| F16 | still open；未重測 | 手工 grounding／Q12 outside selected scope |
| F17 | still open；未重測 | outside selected scope |
| F18 | still open；未重測 | outside selected scope |
| F19 | local buffer/UI/persistence verified | Q15／D02 |
| F20 | outside selected scope；auth migration gate open | Auth0 保留；N00 built compatibility 未執行；沒有切 Neon |
| F21 | Q16 root-cause blocked；Q17 未開始 | 同 request runtime log 只有 OperationalError，缺 driver/SQLSTATE/timeout/pool 診斷 |

main 與 audit source 相同；沒有以另一個 worktree 的未提交 Neon 候選當成 main 的已修證據。以上 closed/verified 只表示本地首輪範圍，release_status 皆 not-deployed。

98 個原 case 的每一列結果及 source/evidence 都在 [新 tracker](../../remaining/AUDIT_FIX_CASE_STATUS_20261003.csv)：**8 local fixture/integration pass、U01 external blocked、U16 root-cause blocked、88 not-retested**。原 CSV 的 actual/result/evidence_state 等原始欄位原封不動；新結果用新增欄位，不覆蓋稽核。原 operation inventory44列、generated public operation78個均保留；無新增 extension/API，也未宣稱78個都已 live 驗收。

## 稽核完整性及 Q16

Evidence ZIP SHA256 再核對 `19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a`。安全 ZIP 檢查、CRC、outer8／nested31 manifests 在 baseline 完成；交接再次驗證31 hashes／98-case所有原欄位／25 tasks／原 plan bytes。原 ZIP／Downloads／證據包未更動。`evidence/reproduce_audit.py` 已讀，未執行；fake identity/connection/query counts 不是持久化或 live 性能證據。

Q16 唯讀抓到相同 request `1d123054-2633-40b7-8e07-b6aed83dad98`、UTC `2026-10-02T19:40:34Z`、GET `/v1/workspaces` 500、JWKS200、OperationalError；[調查](../../incidents/2026-10-03-workspace-500.md) 及 `Q16-runtime-log.md` 保留完整 redacted 結果。下一步由 SRE/Backend 提供 sanitized driver／SQLSTATE／timeout／connection/pool timeline；無此證據不猜 cold start/pool，也不解鎖 Q17。沒有診斷 code patch，所以不製造形式 RED test。

## Schema、回退及清理

- Alembic source heads 已讀：`0036_checkpoint_schema_grants (head)`。本輪新 migration **0**；domain schema/contracts/endpoints／canonical users.id／memberships／歷史 actors／Cloudflare HMAC 未改。
- Strict bulk suite 在空白 owned DB 做既有 migration downgrade 至0015，再 upgrade 至0036，見 `Q03-db.log`。這不是正式 migration／rollback 演練。
- 各 task 可 `git revert <其 commit>`；需要整輪回退時按 Q15 → Q04 → Q03 → Q01。先保留／複製 local dirty drafts；不要刪 revisions／approvals，或以整庫 restore 回退。Q04 保留既有 runs/outbox/holds/ceilings，unknown 操作不換 key 重播。
- Source/document whitespace check 完成；raw tool logs 的 trailing spaces 及 verbatim binary diffs 原樣保留，故 source/document `git diff --check` 排除該 raw `.log`／`.xml`／`.patch` 路徑；没有修改 assertion／DB guard／skip。
- Teardown 已刪本輪 owned UI/API DB containers；只在 owner label `052d6a686de9` 核對後刪本輪 dependency volume。其他 Docker resources、base image、原／dirty worktrees 保留。本輪 review worktree 不刪。

## Review 及仍受阻項

作者另外做了 diff／requirements review：scope generation與intent identity分離、generated ID/page schema、全部body/actor-bound intent、unknown response不auto replay、dirty baseline不被412採納、現有 destructive guard不變、no production source/config/DB/provider activation。獨立 reviewer 未執行，沒有 spawn agent、偽造 owner approval 或宣稱已被獨立核准。

待後續具體範圍／授權：真帳戶 access/完整 staff journey、Q16 底層診斷、N00 built Vinext/Nitro handler/session/token 相容性、production schema/role/worker readback、provider/cost canary、性能/goldset/8-module UAT，以及 push/PR/部署。這些沒有阻止四項本地修復完成。

Auth0 正式路徑保留；Neon Auth、DB搬遷/Data API／framework／Cloudflare cutover均未混入本輪。Mailbox/CRM/sending 停用，delivery仍403。所有UI test durations只是本地測試耗時，沒有凍結 HK cold/warm n30、1k/10k workload 或 goldset，因此不報p95/p99/SLA/accuracy。**本輪未宣稱八模組已 live 驗收。**


## Continuation: Q02 completed locally

Reviewed source `fb184819d038dc2ad56b7f1746362fe9b7a6089a`. [Q02 PR description](Q02-pr.md) and [exact results/screenshots/rollback](../../evidence/audit-fixes-20261003/Q02/RESULTS.md). Final strict API72, combinedUI29 and unit13 pass, allzero fail/skip. Contract79operations; no migration/deployment. NexteligibleQ05. Earlier four repair boundaries above remain historical, separate commits.

## Continuation: Q05 completed locally

Reviewed source `4cd0f484814be7d4333ca265c9637de940d398fa`; base6e7a78c. [Q05 PR-12 description](Q05-pr.md), [author review](Q05-review.md), [exact results/screenshots/rollback](../../evidence/audit-fixes-20261003/Q05/RESULTS.md). Final strict DB13, combinedUI37 and unit18 pass, zero fail/error/skip.79 operations retained, no new schema/API migration/deployment. F06 local confirmation/colleague/unknown-result/scope checks B02/B03/B04/B07/B16 now pass; hard-browser intent recovery/live gates remain unverified. The earlier F-ID table is the preserved first-round snapshot; CURRENT_STATUS and the case tracker hold current results. Original audit case columns/package remain unchanged. Next eligible local task Q06; independent review and external activation remain separate.
