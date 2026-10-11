# BuyerOS Codex GPT‑6.1 Sol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 根據 2026-10-06 稽核，交付可驗收、可回退的 BuyerOS 修復、Neon Auth、真實研究及外展流程。

**Architecture:** 保留 React/Vinext 前端、Python API、PostgreSQL tenant RLS 與既有 durable outbox/worker。優先整合已存在 Q 修復；以 canonical User UUID 連接 Neon 身份，透過已核實 provider contract 接通研究。寄送連接器獨立啟用，所有 UI 數量、權限及狀態以 server 持久化結果為準。

**Tech Stack:** 證據版：React 19.2.6、Vinext 1.0.0-beta.5、Nitro 3.0.260903-beta、TypeScript 5.9.3、pnpm 11.25.0；Python 3.12、API/SQLAlchemy/Alembic/PostgreSQL16測試、worker/Cloudflare controller、Vercel；Neon SDK 0.5.0-beta 為未完成 spike，實作先核實契約。

**Spec:** `docs/buyeros/audits/2026-10-06/BuyerOS_Audit_2026-10-06_zhHK.md`、同目錄 findings/cases/tasks CSV，以及 `evidence/BuyerOS_Audit_2026-10-06_Evidence.zip`。必須同時閱讀；原 audit 內 E01–E08 路徑以解壓 ZIP 為準。

**Targets:** [GitHub / BuyerOS](https://github.com/YNWAforever/BuyerOS)；[live site](https://buyer-os-nu.vercel.app/)；[指定後台 workspace](https://buyer-os-nu.vercel.app/app?workspace=900cd19b-4e03-4446-bdd6-7cb199d96060)。上述正式URL是核對目標，不可直接當測試fixture環境。

## Global Constraints

- 本文件是實作交接計劃，不是本輪已修改程式或重新驗收網站的報告。日期是輸入證據日期；每次執行另記實際 UTC 時間。
- 預設由 Codex GPT‑6.1 Sol 按 `superpowers:executing-plans` 原生執行；上方技能通用標頭不是開啟 subagents 的授權。本計劃不要求另開代理。
- 原始 F01–F22、A26-01–13、Q/N 與 114 case IDs 保留；新增任務用 C61-xx，新增案例用 C61T-xx。歷史 actual/result 不可覆寫成本次結果。
- 稽核上線版與開發修復版不同。code implemented、fixture verified、preview accepted、production readback、human UAT 各自記錄，不能互代。
- canonical User UUID 及歷史 membership/owner/approval/audit FK 不變。不得按 email 自動合併身份或授予角色；BuyerOS DB 是角色來源。
- runtime RLS 不放寬；production 不信任 fixture keys/providers；JWT trust 按 issuer/audience/JWKS/algorithm/branch 明確配置。
- intent/digest/revision/scope/actor 不可在 retry 時偷偷改寫。accepted/unknown 副作用需對帳，不能盲重送或提早釋放 hold。
- bulk manifest：最多10000、10001拒絕、TTL15分鐘、stream batch250、sync≤100、async≥101及chunk50；server重新檢查角色和版本，成功列不重做。
- UI 以 en/zh-HK、390px／桌面／200% zoom／鍵盤與實際screen reader驗收。技術ID可展開，但不得隱藏必要決策資料。
- 使用 frozen lockfiles；Node≥22.13.0（沿用CI Node24）、pnpm11.25.0；不要把本計劃當成全面框架升級或重寫授權。
- 寫入、外部收費、寄送及發布只在執行時既有授權範圍內進行。可先完成可審閱程式、測試及payload；缺外部帳戶/credential只阻塞相應live gate。

## Review Focus

1. Pool/session重用殘留上一身份：C61-06/09、C61T-01/02；下一request依目前canonical identity和membership判定。
2. Provider已受理但回應遺失／worker崩潰：C61-19/20、C61T-08/12；不重送、不錯釋unknown hold。
3. UTF‑16選取遇emoji/combining mark：C61-22、C61T-10；後端code-point引用仍精確且新revision重新覆核。
4. Neon-only新使用者遇回退：C61-13、C61T-05；使用者、歷史FK和登入路徑保留。
5. 15分鐘manifest到期後只重試失敗：C61-23、C61T-11；重新preview，不重播成功列或沿用失效確認。

---
## 建議交付次序

先交付修復整合及有界 workspace 查詢，再完成 Neon 與真實研究接駁，最後以同一候選版本驗收和发布。這是30個可審閱任務，並非30個必須一次合入的大改動。估工為人日粗估，不含等帳戶、供應商選型、真人標註／UAT排期；不能直接當日曆承諾。

| 批次 | 任務 | 可交付結果 | 外部阻塞時可繼續的工作 |
|---|---|---|---|
| 0 | C61-01 → C61-02；C61-04/07/15 | 鎖定差異、整合既有修復、取得事故與契約證據 | 診斷/SDK/provider各自獨立，勿全案停工 |
| 1 | C61-03/06、C61-21/22/23 | 員工入職、查詢改善、日常與批量維護 | 先owned fixtures，真人/live留待验收 |
| 2 | C61-08 → 09 → 10 → 11 → 12 → 13 | Neon相容、映射、驗證器、session及回退演練 | 缺真實Neon時做offline negative tests，不稱遷移完成 |
| 3 | C61-16/17/18 → 19 | 真實search/model/contact與可恢复run | vendor缺失保留blocked，不用fixture假裝live |
| 4 | C61-24/25 → 26 → 27 → 28 → 29 | 真實準確度、效能、八模組、人員、CI及正式readback | F21無根因仍open；發布前明列風險 |
| 5 | C61-14；C61-20 → 30 | Neon-only退役；獨立完成站內寄送 | 未完成send時只能宣稱research+approved export |

C61-14依賴C61-29，C61-30依賴14/20/29；任務編號是穩定ID，不等於必須按數字從頭到底執行。依dependency選下一個可開始任務，不得形成N07與發布互等。

### 各階段gate，避免發布前後互相等待

- C61-28輸出 `predeploy_ready`：只要求當前階段的同SHA preview/DB/provider/UAT案例。production readback、Auth0退役和native send的後續案例有明確owner與執行位置，不能被當成已pass。
- C61-29先執行production readback再輸出 `release_accepted`。U01/R01/O26-01/O26-15等原本要求正式環境的案例，發布前仍標pending postdeploy；preview的對應測試是另一筆環境證據。
- C61-14通過NA28及NA30最終Neon-only readback後才輸出 `neon_only_accepted`。這些後置條件不阻塞C61-28開始canary，但會阻塞「Auth0已完全取代」的完成聲明。
- C61-30通過O26-16/C61T-16才輸出 `native_send_accepted`。未交付send並不阻塞已驗證的research/export發布，總產品狀態仍明列native send未完成。
- 每個原case有本階段適用性：required / postdeploy / later-release / superseded-with-approved-successor。變更必須帶contract/evidence與owner，不能藉此排除失敗。B14歷史1000上限以B15/O26-05作明確successor；原列不改pass，114個case都須有處置，但不要求過期contract在新版本仍成立。

## 證據固定點與目前缺口

| 項目 | 2026-10-06證據 | 實作含義 |
|---|---|---|
| Input ZIP | SHA256 `eaa797614dfa6baec8c91d92fe28a9a8c90bcdec9dcd96d0602ef8ec4c85262d`；75 members、74 manifest matches | 保留原bytes；先drift review |
| 正式main | `a78859fe474f5722be3755b10e2586436b53bf97`；Vercel `dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp` | 不是候選修復已上線 |
| 已審候選 | `bbaf8ecd1f7ef755b89cdc29c8e01c505ad96442` | 本計劃檔案核對的baseline |
| PR11 | merge `05d8a4aad52857ca4388aec4ee338cfbc197372c`；base `codex/n00-native-ipc-isolation` | 並非main合併 |
| Hosted CI | run37403378632，checkout `767f13e1c66321bc8a7e87b590c1795135a8cba4` | 三者tree同為 `7c06894c7664aa15661b1a1249e85338c16ac2e9`，不是任意SHA皆已驗證 |
| 合約/schema | main78、candidate84 operations；candidate0037_bulk_manifests | production schema/worker/selector/epoch仍未知 |
| 既有修復 | Q01–Q08/Q12/Q14/Q15已有fixture證據；Q09/Q10/Q11/N00僅部分；Q16受阻 | 先整合驗收；Q13/Q17/N01–N07尚待交付 |
| 登入/live | Oct6顯示Wrong email or password；8模組live E2E為0/8 | 舊無membership觀察不能當本次登入成功 |
| Research/send | selected_run_capability回None、研究503；delivery固定403 | 需真正provider接駁；不能只移除保護回應 |
| Auth | 真實app仍Auth0，Neon是dev spike | N00–N07全程規劃，非改設定即可 |
| Workspace效能 | W=1/10/100/1000，SQL=4/22/202/2002 | C61-06目標≤6且不隨無關W增長 |
| 原500 | Oct2 request ID `1d123054-2633-40b7-8e07-b6aed83dad98` OperationalError | 原因未明，不猜pool/cold start |

證據內candidate44個unit及hosted API812 pass為獨立歷史紀錄；不能相加成「856項本次全部通過」。Q06流量比較是logical60s，不是production wall-clock。benchmark通過資料捕捉不代表SQL gate通過。此計劃沒有重新登入、跑產品tests、改auth或發布。

## 執行規則與共用測試環境

1. 先讀 repo 的 AGENTS.md 與所有適用指令，確認工作樹和最新branch。若檔案已移動或修復已存在，記錄mapping後沿用；不覆蓋使用者修改。
2. 每個新行為先補指定失敗測試，確認是預期assertion失敗，再做最小修復，跑focused suite，最後commit。既有正確修復先驗收，不為製造red而破壞程式；文件與人工gate只做相應核對。
3. 全部命令預設repo root。先依CI `pnpm install --frozen-lockfile`、API/worker `uv sync --frozen`。建立 `artifacts/`。Python DB suites 必須使用自行擁有的loopback PostgreSQL16、`buyeros_test_`開頭DB名及 `BUYEROS_STRICT_INTEGRATION=1`；測試用runtime role無BYPASSRLS，migration owner另分。worker需要的Valkey/queue按現有CI準備。
4. 禁止把production/Neon DSN帶進destructive fixture。directory benchmark自行管理PG，會拒絕继承 `DATABASE_URL`、`BUYEROS_DATABASE_URL`、`BUYEROS_TEST_DATABASE_URL`、`BUYEROS_WORKER_DATABASE_URL`；使用隔離process env，只清理本次owned容器/nonce，不修改全域環境。
5. 每個command保存exit code/JUnit/trace/source SHA/時間/環境；required DB tests為0 fail/error/skip。`pytest --collect-only`或Playwright `--list`先檢查新增spec被收錄，0 tests不是pass。新config/testMatch列入實作，不能讓新增suite被audit-*排除。
6. 每個API變更改server schema/OpenAPI source，再執行generated types/operation routes工具；不手改generated檔案。新的routes要注册、設定OPERATION_ROLES、tenant context、rate limits及required tests。
7. 新Alembic revision在讀取heads後分配並檢查peer branch；此計劃不預佔0038等號碼。先expand及向後相容，再backfill/cutover；runtime grants/RLS以真實受限role驗證。
8. 每個任務結果記 `code_status / verification_status / release_status / blockers / evidence_paths`；工作狀態使用待開始/進行中/受阻/待驗收/已驗證完成。完成某task不代表相關finding已在production關閉。

## 測試證據分層與新增驗收

| 層級 | 能證明 | 不能代替 |
|---|---|---|
| L0 static/unit | 合約、意圖、parser/guard邏輯 | DB授權、真實登入／provider |
| L1 owned PG16 + HTTP + fixture UI | RLS、競態、持久化、UI流程 | vendor正確性、正式部署 |
| L2 built portable/Vercel preview +真實Neon/provider | 實際artifact、cookie、成本、receipt與端到端 | production讀回及真人可用性 |
| L3 authorized production readback | alias/SHA/schema/worker/auth一致和只讀smoke | 完整寫入流程、真人screen reader |
| L4 human/goldset | 員工完成率、source語義、contact正確性 | 無樣本範圍外的100%準確保證 |

`BuyerOS_C61_Case_Traceability_2026-10-06.csv` 原114列及全部原欄位逐值保留，新增plan_task_ids與execution_status。`BuyerOS_C61_New_Test_Cases_2026-10-06.csv` 另列16個高風險新增case；兩份全部初始not-run。task內其餘具名測試可新增更細粒度case，但不可重編原ID。

B14的1000/1001描述是原歷史上限，不可改原expected：重播baseline保留原狀，candidate以B15/O26-05的10000/10001 successor驗收。WF03/O26-07在delivery gate off環境仍要求403；native send以O26-16/C61T-16新增路徑，不把原failed/not-tested偷改pass。NA11若官方token algorithm契約與原預期不同，保留原case、記已審核contract amendment及successor，不能靜默刪除驗證。

## 分檔計劃

本包按四個子系統分檔；每份使用同一任務ID、共用契約及dependency。合併閱讀版包含全部内容，實作者可以只開對應子計劃及spec。

- `docs/superpowers/plans/2026-10-06-buyeros-foundation.md`：C61-01–06。
- `docs/superpowers/plans/2026-10-06-buyeros-neon.md`：C61-07–14。
- `docs/superpowers/plans/2026-10-06-buyeros-research.md`：C61-15–20。
- `docs/superpowers/plans/2026-10-06-buyeros-product-release.md`：C61-21–30。

## 檔案責任地圖（先讀再改）

所有路徑相對repo root。每task另列完整existing/create清單；「新增」是本計劃設計，並非聲稱repo已有。修改其他檔案前先記錄必要原因。

| 邊界 | 現有核心 | 計劃新增／收斂責任 |
|---|---|---|
| 身份與租戶 | `services/api/buyeros_api/api/auth.py`、`api/verifier.py`、`api/deps.py`、`db/models.py` | `services/identity_resolver.py`、`services/identity_linking.py`、`api/auth_trust.py` |
| 目錄查詢 | `api/routes/workspaces.py`、workspace benchmark | `services/workspace_directory.py`，有界 SQL 與可信actor |
| 登入/session | `services/live/auth.ts`、`session.ts`、`features/providers/workspace-session.tsx` | `lib/auth/neon-server.ts`、`neon-config.ts`、`services/live/neon-auth.ts` |
| Provider | `providers/base.py`、search/model/contact、`execution/external_runner.py` | registry及每種live adapter；durable boundary不繞過 |
| 改稿/bulk | `features/live/drafts.tsx`、grounding、bulk-manifest；API對應service | 小型text selection helper；既有精確revision/manifest契約保留 |
| 每日待辦 | `features/live/overview.tsx`、job-query、jobs route | work_queue service/route，與列表共享predicate |
| 寄送 | `api/routes/drafts.py`現在disabled boundary | delivery adapter/service/callback，獨立gate與狀態機 |
| 維護與發布 | `.github/workflows/buyeros-ci.yml`、`TASKS.json`、CURRENT_STATUS | case/source evidence checker、runbooks、同版本manifest |

## 任務索引

| ID | 任務 | 原任務 | 依賴 |
|---|---|---|---|
| C61-01 | 鎖定證據、分支差異及交付基準 | A26-01;Q11 | — |
| C61-02 | 整合並驗收已存在的 Q 修復 | A26-03;Q01;Q02;Q03;Q04;Q05;Q06;Q07;Q08;Q12;Q14;Q15 | C61-01 |
| C61-03 | 打通授權員工的工作區入職及恢復 | A26-02;Q01;Q02 | C61-02 |
| C61-04 | 取得 workspace 500 根因證據 | A26-07;Q16 | C61-01 |
| C61-05 | 修正已證實的 500 原因 | A26-08;Q17 | C61-04 |
| C61-06 | 把 workspace discovery 改為有界查詢 | A26-04;Q13;N02 dependency | C61-01, C61-02 |
| C61-07 | 完成 N00：Neon 的真實產品登入契約 | A26-06;N00 | C61-01 |
| C61-08 | 完成 N01：環境與 auth server 邊界 | A26-06;N01 | C61-07 |
| C61-09 | 完成 N02：不可變 canonical identity 映射 | A26-06;N02 | C61-06, C61-07 |
| C61-10 | 完成 N03：隔離信任設定的 API JWT verifier | A26-06;N03 | C61-07, C61-08, C61-09 |
| C61-11 | 完成 N04：Neon session、刷新與跨 tab 登出 | A26-06;N04 | C61-08, C61-09, C61-10 |
| C61-12 | 完成 N05：身份與租戶負向驗收 | A26-06;N05 | C61-03, C61-10, C61-11 |
| C61-13 | 完成 N06：身份遷移及回退演練 | A26-06;N06 | C61-09, C61-12 |
| C61-14 | 完成 N07：有限期雙信任後退役 Auth0 | A26-06;N07 | C61-13, C61-29 |
| C61-15 | 定義並核實真實供應商接駁契約 | A26-05;Q11 | C61-01 |
| C61-16 | 實作真實搜尋、來源抓取及公司對應 | A26-05 | C61-15 |
| C61-17 | 實作真實 model fit、證據驗證及人工審核銜接 | A26-05;Q10 | C61-15, C61-16 |
| C61-18 | 實作 Contact quote、確認及真實結果 | A26-05 | C61-15, C61-16 |
| C61-19 | 接通真正可恢复的 research run | A26-05;Q04;Q11 | C61-02, C61-16, C61-17, C61-18 |
| C61-20 | 新增可追蹤站內寄送連接器 | A26-12 | C61-13, C61-15, C61-18, C61-19 |
| C61-21 | 讓 Overview 今日待辦直接到正確資料 | A26-09;Q09;Q14 | C61-02, C61-06 |
| C61-22 | 把改稿與來源覆核變成可完成的日常流程 | A26-09;Q07;Q12;Q15 | C61-02 |
| C61-23 | 改善大批維護、Settings 及可達性 | A26-09;Q02;Q05;Q08;Q09 | C61-02, C61-03, C61-21, C61-22 |
| C61-24 | 驗收真實研究準確度與成本 | A26-10;Q10 | C61-17, C61-18, C61-19 |
| C61-25 | 驗收效能、輪詢、worker 公平性及容量 | A26-10;Q06;Q10;Q13 | C61-06, C61-19, C61-21, C61-23 |
| C61-26 | 八模組同一資料鏈端到端驗收 | A26-11;Q11 | C61-03, C61-12, C61-19, C61-21, C61-22, C61-23, C61-24, C61-25 |
| C61-27 | 用真實員工驗收可用性與輔助工具 | A26-09;A26-11;Q09 | C61-26 |
| C61-28 | 把同版本驗收變成 CI 和維護門檻 | A26-13;Q11 | C61-02, C61-05, C61-06, C61-13, C61-24, C61-25, C61-26, C61-27 |
| C61-29 | 發布研究與核准匯出版本並讀回驗證 | A26-13;Q11 | C61-28 |
| C61-30 | 獨立啟用站內寄送並完成全外展驗收 | A26-12;A26-13 | C61-14, C61-20, C61-29 |

## 問題覆蓋與關閉條件

| Finding | 實作／驗收任務 | 關閉規則 |
|---|---|---|
| F01 | C61-02, C61-03, C61-11, C61-12, C61-26 | 同候選preview＋production讀回；所屬case完成 |
| F02 | C61-02 | 同候選preview＋production讀回；所屬case完成 |
| F03 | C61-02, C61-03, C61-23 | 同候選preview＋production讀回；所屬case完成 |
| F04 | C61-02, C61-03, C61-12, C61-23 | 同候選preview＋production讀回；所屬case完成 |
| F05 | C61-02 | 同候選preview＋production讀回；所屬case完成 |
| F06 | C61-02, C61-23 | 同候選preview＋production讀回；所屬case完成 |
| F07 | C61-02, C61-25 | 同候選preview＋production讀回；所屬case完成 |
| F08 | C61-02, C61-11, C61-19 | 同候選preview＋production讀回；所屬case完成 |
| F09 | C61-02, C61-22 | 同候選preview＋production讀回；所屬case完成 |
| F10 | C61-15, C61-16, C61-17, C61-18, C61-19, C61-20, C61-24, C61-26, C61-30 | 研究/export與native send分開；native send須C61-30，不可提早全關 |
| F11 | C61-02, C61-23 | 同候選preview＋production讀回；所屬case完成 |
| F12 | C61-16, C61-17, C61-18, C61-24, C61-25, C61-26 | 真實goldset、分層指標、provider/readback、已採納效能預算 |
| F13 | C61-01, C61-28, C61-29 | 實際alias/SHA/CI/schema/worker/auth readback一致 |
| F14 | C61-21, C61-22, C61-23, C61-26, C61-27 | 八模組同資料鏈＋至少3位員工＋screen reader實測 |
| F15 | C61-02 | 同候選preview＋production讀回；所屬case完成 |
| F16 | C61-02, C61-22 | 同候選preview＋production讀回；所屬case完成 |
| F17 | C61-02, C61-21 | 同候選preview＋production讀回；所屬case完成 |
| F18 | C61-06, C61-25 | SQL≤6／無關W不影響，role/RLS及分頁驗收 |
| F19 | C61-02, C61-22 | 同候選preview＋production讀回；所屬case完成 |
| F20 | C61-07, C61-08, C61-09, C61-10, C61-11, C61-12, C61-13, C61-14, C61-26, C61-29 | N00–N07、NA01–NA30；Neon-only及rollback驗收 |
| F21 | C61-04, C61-05 | 已確認根因＋失敗重現＋修後證據；僅診斷不得關閉 |
| F22 | C61-01, C61-26, C61-28, C61-29, C61-30 | 實際alias/SHA/CI/schema/worker/auth readback一致 |

## 完成定義與手交紀錄

單一task「已驗證完成」須有本次結果；不能用原ZIP的歷史pass填本次status。整體Release A須C61-01–13、15–19、21–29的必要gate（含已證實根因修復或正式記錄未解風險），以及真實Neon/研究/角色流程。Neon-only再須C61-14。完整站內外展寄送另須C61-20/30；未交付項明列open。

每次Codex交接輸出：本次source SHA、完成task、修改檔案、實際測試命令與數量、結果artifact、未解blocker、下一個可開始task、回退點。任何測試被外部条件阻塞，都寫明缺甚麼證據，不將not-run改skip/pass。

本計劃自我檢查：22 findings、13 A26 groups、114原cases均有任務；30任務dependency graph無環；16新增case各有owner；既有檔案存在於候選snapshot，新增檔案明确標示。未進行本輪實作、登入、vendor call、production測試或部署。
