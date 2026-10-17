# Native 政策啟用與回歸驗證

日期：2026-10-17（Asia/Hong_Kong）。候選基於 main `51532f19c19dd10ab3aa6c4a5fac87bc039856bb`；專用分支 `codex/controlled-policy-activation-20261017`。

本紀錄接續受控政策啟用與 provider 授權差異。較早交付文件的局部失敗與未測狀態保留為歷史；本次完整執行結果另列如下。

## 已執行的本機合成隔離測試

| Suite | 結果 |
|---|---|
| 完整 API | 2,978 passed；0 failure/error/skip |
| 完整 worker | 469 passed；0 failure/error/skip |
| Native browser | 19 passed；0 failure/error/skip |
| Lead intent client | 6 passed |
| Policy client | 11 passed |
| 發布控制及 CI registration | 192 passed（183 + 9）|
| TypeScript、受影響 UI lint、OpenAPI/types、124 operation routes | 通過 |

原 API 2,967 個 case 全部保留，新增 11 個回歸；worker 469 與 Native 19 的原 case IDs 全部保留。完整執行使用 owned disposable PostgreSQL 18.6、fixture Auth、API/worker 各自既有 frozen venv（Python 3.14.6）及 Node 24.18.0。測試前核對實際 container/endpoint/issuer，沒有正式 DATABASE_URL fallback。provider 正向情境均為 fake/mock；真實外呼為 0。

已測來源指紋為 `a3c296c96e3389050152edcb434e21a6bc36c07d3c4829efc72a95ebdaa4fc02`（1,441 個本機來源檔案；含未提交的工具生成說明檔）。提交前已重新比對完全一致。其後僅新增本報告，以及在 `vercel.json` 加入本專用分支停用 Git 自動部署的規則；後者另跑現有 Vercel 設定/代理測試。提交內容不包括工具生成 AGENTS/CLAUDE、fixture 輸出、備份或私有證據。

## 可重現入口與證據

完整原始 logs、JUnit、前後影像及 discovery 保留於本機 `.superpowers/sdd/2026-10-17-full-native-regression/`，不隨 PR 上傳。`VERIFICATION.zh-HK.md` 記錄實際完整命令；`final-results.json`、`source-freeze-07.json`、`final-source-compare.json` 綁定結果與來源。

標準入口為 `services/api/tools/run_policy_activation_tests.py --target-receipt <new-owned-receipt> --suite api|worker|browser`。Native 19 額外使用 `--native-browser`；完整 pytest 使用明確 `tests` root，配套 discovery 與 `scripts/check-required-tests.py`。本輪 owned target 已精準清理；重新驗證須建立新 receipt，不能重用已失效 port。

## 權限與發布界線

本 PR 包含尚未套用的 `0056_policy_activation` 來源、三張 append-only 政策表、精確 ACL、受控申請/批准/撤回、現行政策 proof 與 provider/account/contract/source 綁定。提交 SQL 不代表批准執行 migration、grant、owner designation 或任何正式變更。

付費 research、聯絡資料 enrichment、delivery/send、自動 outreach 的實際設定維持停用；用途批准不代表發送內容或收件人已獲批准。沒有真實 24 家/57 個來源提交。

上述為本機結果，不能代替遠端同 head 完整 CI、部署或公司帳戶 UAT。使用者本次只批准 commit/push/PR 與 exact-head CI；不 merge、不部署、不改正式 DB/權限。


## PR 發布階段的 CI 接線補修

PR #26 初始 head `30851d46407806cc6c6d28f5c5bd6f7473a2bb07` 的 run `39030436538` 揭示兩類舊接線：inventory guard 仍要求 API 2,852；legacy worker、capacity、PG18 及 browser fixture 未向新政策 proof 登記 owned target，或仍只新增 raw `permitted`。這些拒絕是受控閘門的預期行為，沒有改為放行。

補修只改 CI 與合成測試工具：legacy allocator 在建立前核對本機 Docker engine，在 SQL 前核對新 container ID、獨立 image、label、loopback port、mount、DB 與 fixture issuer；跨程序傳遞 exact receipt，再獨立 inspect。worker/smoke/zoom 不再繼承未經此 gate 證明的服務 DSN。每個申請仍使用真正的 designation/request/approval；渠道在新增後明列 contact ID、active sender 與公司/來源 domains，只授予 fake search/read、contact.read、template generation、內部 delivery.review；不授予 send 或 enrichment。沒有修改產品授權或測試原斷言。

補修後新增本機證據：完整 worker **469/469**；PG18 proof **38/38**；原 MVP journey **4/4**；原 audit research-intent/reground/template-copy **8/8**；最終 ownership/inventory/registration **41/41**；發布控制/registration **192/192**，均無 failure/error/skip。C61 evidence checker 163 及 Playwright discovery guard 16 亦通過。MVP 與 audit 使用各自新建的合成 owned DB；audit 的 compiled frontend 使用既有 Windows/Linux Docker harness，不能視為正常公司 Auth 或正式 UAT。

audit 第一次補測是 1 pass/7 fail，原始 logs、JUnit、traces 和 UI context 全部保留；修正指定渠道 proof 與明確 domain 後，第二次同 8 案完整通過。最初缺少 Vercel build 的失敗亦保留。這些結果存於上述 private evidence 的 `publish-01/ci-fix-01/`，沒有覆寫原始失敗。完整 API 2,978 與完整 12-job exact-head CI 以本 PR 的新 head run 另行核實，不以本段局部補測代替。


## 完整 CI 發現的後續邊界補修

- 初始完整 API run 的結果為 2,974 pass/4 fail；四項都是獨立 benchmark 的無 DB collection 子程序誤繼承父 CI `PYTEST_PLUGINS`/target receipt。子程序現在清除這些外來上下文；獨立 benchmark 仍先拒絕所有可供 client/migrator 使用的繼承 endpoint，包括 `BUYEROS_DATABASE_MIGRATION_URL`。collection 沒有 observations 仍拒絕，沒有把 collect 當執行。
- Cloudflare 的 101-row fixture 會超過 100-domain 契約上限。申請現在只列有來源證據的公司 domain 與實際來源 domain；不擴大上限或任意截取前 100 項。既有 fake lookup 正向案例只在 `BUYEROS_E2E_SEED_QUOTES` 的 owned fixture 中，經指定 owner 批准 `fixture-test` 的精確 contract。quote 與 adapter 共用同一 immutable fake capability metadata，實際 provider/寄信保持停用。
- Native19 與 policy8 在 run `39033264452` 都實際通過，但 guard 找不到舊 discovery 路徑。現在從 runner 已於執行前保存的原檔，按當前 parent run ID 唯一選取，保留 bytes/mtime 複製至 artifact；缺失、歧義或覆寫均拒絕。沒有在執行後重新產生 discovery。
- broker fixture 的 review timestamp 原先每個程序均不同，令正確的精確 contract gate 回 `policy_blocked`。同一份公開 fictional review packet 現在用固定 UTC 日期；獨立程序 hash 比對已保留 RED（不同）及 GREEN（相同）。正常 runtime 的 hash、expiry、permission、hold、epoch 與禁止重送核對均未改動。
- 繁中 390px Settings 的長 designation UUID/select/history 造成水平溢位。只新增政策面板專屬 class 與 min-width/wrapping 規則；原 U06 搜尋、失敗重試及 viewport 斷言保持不變並已通過。

這組補修後，本機完整 worker 469/469 通過、原 case IDs 全部保留；完整 quality-tools 41/41、101-company/24/57 DB regression、原手機 U06 1/1、完整 local Cloudflare Queue/Workflow acceptance 7/7、TypeScript、panel lint、release/registration 192/192 通過。API 亦在先核實的全新 owned target 完整 discovery 2,978，與原 inventory 一項不差；這是 discovery，完整執行仍以新 head CI 為準。

local Cloudflare acceptance 包含實際 compiled handler、local Queue/Workflow、101-row restart、fake unknown lookup hold 與角色拒絕，source fingerprint `03a9994d593ed1e9bbfa5127aebdaaaad71132b58e7a66ca360a5e0b0f42ab0e` 前後一致。之後只增加 benchmark migration-endpoint 的拒絕/negative assertion 及本文件。沒有公司正常 Auth 或正式 UAT 證據。

另有一輪額外 Windows opt-in broker probe 未取得完整 JUnit：lease 完成，redelivery/unknown 在 worker restart 後未出現第二次工作事件，accepted 未有終態回執，wrapper 到 600 秒上限。它不計入 469 或通過結果。原事件、logs、跨程序 hash 證據與 exact PG/broker 停止資料均保留，未重送或更改 hold；所需 Linux broker4 將在完整 12-job CI 重新核實。較早 Docker 中斷的 local Cloudflare run 沒有完結回執，獨立標為 interrupted，其 exact DB 已保留停止；後來的全新 target 7/7 不能回填該中斷歷史。

所有新/舊 tracked JUnit/PNG 測試產物均先留證據，再恢復原 tracked 版本；沒有把新輸出當成原報告或提交 fixture 產物。今輪仍不 merge/deploy、不改正式 DB/權限/憑證、不得提交真實 24/57 或啟用真實付費/寄信。


## Joined workflow 與獨立 admission 子程序的最後接線

`0f42f7f3` 的 CI 已通過完整 audit140、Native19/policy8、Cloudflare7、worker469、30分鐘 workload2、Linux broker4 及 bulk3。後續 joined17 有8項失敗：四項唯讀 readback 仍硬編碼0055，其餘四項專用 unknown-search journal adapter 未帶明確 binding。現在 readback 嚴格要求已批准實作的 `0056_policy_activation`，沒有改為接受任意版本；專用 adapter 與正常 fixture 使用同一 typed fake research binding，driver 重用已核實 container/label/image/port 的 owner gate。原 journal exclusive-create、intent/status key、原 hold、成功列不重播及精確 export/readback 斷言均保留。

同 run 的最後 API-admission case 顯示 plain seed 子程序沒有自己驗明 parent receipt。它現在必須取得明確 receipt，先獨立 `inspect_target` 再進入 `_setup`/首次 SQL；缺 proof 的純 RED/GREEN 驗證，以及實際 owned DB 子程序 readback 均通過（兩筆 fake unknown/accepted、hold0.6、cost0，沒有 provider submit）。

最後本機完整 joined17/17、Unicode4/4、actual child probe1/1 與 C61 evidence controls163/163 通過，無失敗/錯誤/跳過。JUnit、命令、logs 與原檔在 private evidence `publish-01/ci-fix-03/`。這四個 source 補修不增加/刪除原 testcase IDs，不修改產品授權或 schema/migration SQL；完整12-job CI必須在更新後同一 head 重新通過，不能拼合舊 head 結果。
