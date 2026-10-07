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

## 既有修復、入職與資料庫

### C61-01 — 鎖定證據、分支差異及交付基準

**映射：** A26-01;Q11 · F13;F22  
**優先／狀態：** P1／待開始  
**負責／估工：** Release / Codex；0.5–1 人日  
**依賴：** 無

**Files（現有檢視／按需要修改）：**

- `TASKS.json`
- `docs/buyeros/CURRENT_STATUS.md`
- `.github/workflows/buyeros-ci.yml`

**Create（計劃新增）：**

- `docs/buyeros/decisions/2026-10-06-fix-integration.md`
- `docs/buyeros/release-candidate.json`

**Interfaces**

- Consumes：輸入 ZIP SHA256 與 E07 source/release manifest；工作目錄目前的 HEAD、git status、AGENTS.md。
- Produces：候選清單 JSON：source_sha、tree_sha、base_sha、ci_run_id、deployment_id、api_sha、schema_head、worker_sha、runtime_selector、epoch、evidence_paths；未知欄位為 null，不能推算。

**案例：** R01, R05, O26-15。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** 完整性檢查須為 75 ZIP members、74 manifest hashes match。確認 main/a788… 與候選/bbaf… 的 diff；PR #11 的 base 是 codex/n00-native-ipc-isolation。最新 HEAD 若已改變，逐項記 added/changed/already-fixed，不直接覆蓋目前成果。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 建立隔離 worktree，保留使用者修改；逐一核對既有 Q 修復提交。以可審閱 merge/cherry-pick 選擇 ADR 整合，禁止把整條 spike 歷史盲目合入 main。修正 CURRENT_STATUS 的 code / test / deployment 三種狀態。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
git status --short
git rev-parse HEAD HEAD^{tree}
git log -8 --oneline
git diff --stat a78859fe474f5722be3755b10e2586436b53bf97 bbaf8ecd1f7ef755b89cdc29c8e01c505ad96442
```

- [ ] **5 — 驗收與commit：** 每個既有修復有實際 commit/path 與採用決定；八模組 live 驗收仍標未完成。原 ZIP 不更改。命令是本地核對，不代表發布。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-01: 鎖定證據、分支差異及交付基準` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 刪除未採用的隔離 worktree；不 reset 使用者分支，不改原 audit。

### C61-02 — 整合並驗收已存在的 Q 修復

**映射：** A26-03;Q01;Q02;Q03;Q04;Q05;Q06;Q07;Q08;Q12;Q14;Q15 · F01;F02;F03;F04;F05;F06;F07;F08;F09;F11;F15;F16;F17;F19  
**優先／狀態：** P1／待驗收  
**負責／估工：** Full stack / QA；3–5 人日  
**依賴：** C61-01

**Files（現有檢視／按需要修改）：**

- `features/live/workspace-picker.tsx`
- `features/live/settings.tsx`
- `features/live/operations.tsx`
- `features/live/bulk-actions.tsx`
- `features/live/bulk-manifest.tsx`
- `features/live/drafts.tsx`
- `features/live/draft-grounding-review.tsx`
- `features/live/draft-dirty-guard.tsx`
- `services/live/job-poller.ts`
- `services/live/job-query.ts`
- `services/api/buyeros_api/services/bulk_manifest.py`
- `services/api/buyeros_api/services/draft_grounding.py`
- `services/api/tests/test_membership_directory_db.py`
- `services/api/tests/test_bulk_manifest_db.py`
- `services/api/tests/test_manual_grounding_db.py`

**Create（計劃新增）：**

- `docs/buyeros/evidence/c61/integration-results.md`

**Interfaces**

- Consumes：C61-01 選定的修復提交；既有 OpenAPI / 84 operation contract；0037_bulk_manifests migration。
- Produces：保留既有公開契約；輸出逐 Q 的 source_sha、test case count、fail/error/skip、artifact、deployment_status，不建立第二份業務實作。

**案例：** U02, U03, U05, U06, U07, U08, B01, B02, B03, B04, B05, B06, B07, B08, B09, B10, B11, B12, B13, B14, B15, B16, A02, A07, P04, S06, U13, U15, D01, D02, D03, WF01, WF02, O26-04, O26-05, O26-06, O26-09。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** Q01/02：250 成員可達、同名可辨、撤權即拒絕、最後 admin 競態；Q03：結果用 id，第二頁可達；Q04：202 response lost、雙擊仍同 key/run/outbox；Q05/08：100/101、1000/1001、10000/10001 邊界與失敗重試；Q06：每 view in-flight≤1；Q07：固定模板文案與實際輸出一致；Q12/15：dirty 保留且新 revision 重新 grounding/approval；Q14：專案 A=0/B=5。已有正確測試先直接跑，只有缺口才新增失敗測試。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 每組修復單獨 review/commit；比對 migration grant/index/runtime role；保留 manifest 15 分鐘 TTL、最多 10000、stream 250、async chunk 50、100/101 sync/async 邊界。修正整合衝突，不重寫已通過的功能。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
node --test tests/audit-*.test.mjs tests/job-poller-checks.mjs
pnpm exec playwright test --config playwright.audit-fixes.config.ts
uv run --frozen --project services/api pytest services/api/tests/test_membership_directory_db.py services/api/tests/test_bulk_manifest_db.py services/api/tests/test_manual_grounding_db.py services/api/tests/test_job_summary_db.py services/api/tests/test_job_scope_db.py --junitxml=artifacts/c61-q.xml
python scripts/check-required-tests.py --junit artifacts/c61-q.xml
```

- [ ] **5 — 驗收與commit：** 隔離 PG16 strict tests：0 fail/error/skip；fixture UI 與 API/DB 對照一致。既有 44 units / 812 API 是歷史參照，不能硬編碼未來總數或把它們相加。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-02: 整合並驗收已存在的 Q 修復` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 按修復組 revert；保留 append-only、manifest、accepted/unknown operation 記錄；禁止破壞式降 schema。

### C61-03 — 打通授權員工的工作區入職及恢復

**映射：** A26-02;Q01;Q02 · F01;F03;F04  
**優先／狀態：** P1／待開始  
**負責／估工：** Backend / Admin / QA；1–2 人日  
**依賴：** C61-02

**Files（現有檢視／按需要修改）：**

- `features/live/workspace-picker.tsx`
- `features/live/settings.tsx`
- `services/api/buyeros_api/api/deps.py`
- `services/api/tests/test_membership_directory_db.py`
- `tests/e2e/audit-access-revocation.spec.ts`

**Create（計劃新增）：**

- `docs/buyeros/runbooks/staff-onboarding.md`
- `services/api/tools/reconcile_staff_membership.py`
- `services/api/tests/test_staff_onboarding_db.py`

**Interfaces**

- Consumes：現有 Principal(issuer, subject)、canonical User.id、Membership；workspace 900cd19b-4e03-4446-bdd6-7cb199d96060 只作指定目標，不能當授權。
- Produces：受控 CLI：reconcile_staff_membership.py --manifest PATH [--apply]；manifest 每列 canonical_user_id/workspace_id/roles/reason/proof_ref/expected_version；預設 dry-run，只由既有授權管理身份執行，輸出逐列結果與 audit ref。

**案例：** U01, U02, U03, U05, U06, U07, U08, S06, U13, NA06, NA07, NA08, NA09, NA10, O26-01, O26-09。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_onboarding_dry_run_no_write、test_same_email_no_link、test_conflict_no_escalation、test_last_admin_survives：dry-run 寫入=0；email 不決定身分；角色衝突拒絕；成功重跑不新增 membership。新帳戶若尚未有 verified identity，保持 pending。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先提供可重複核對的運維入職路徑與支援文案；沿用既有 membership 服務和鎖，禁止腳本直接繞過角色規則。取得可用 operator/reviewer/admin 測試帳戶後進指定 scope。Settings 成員目錄不能標示為完整邀請系統；如日後要 self-service invite，需另立 single-use/expiry/acceptance 規格。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_staff_onboarding_db.py services/api/tests/test_membership_directory_db.py --junitxml=artifacts/c61-onboarding.xml
python scripts/check-required-tests.py --junit artifacts/c61-onboarding.xml
```

- [ ] **5 — 驗收與commit：** 有正確帳戶與 membership 的 UI/API 讀回證據；0-membership 仍不能進 workspace，提供雙語重試和聯絡路徑。沒有有效帳戶時只標受阻，不改密碼或提升自己權限。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-03: 打通授權員工的工作區入職及恢復` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 撤回本批新增 membership 須依正常管理流程並保留 audit；不刪 canonical users 或歷史 actor。

### C61-04 — 取得 workspace 500 根因證據

**映射：** A26-07;Q16 · F21  
**優先／狀態：** P1／受阻  
**負責／估工：** SRE / Backend；1–2 人日  
**依賴：** C61-01

**Files（現有檢視／按需要修改）：**

- `docs/buyeros/incidents/2026-10-03-workspace-500.md`
- `services/api/buyeros_api/api/errors.py`
- `services/api/buyeros_api/api/deps.py`
- `services/api/buyeros_api/db/session.py`

**Create（計劃新增）：**

- `services/api/tests/test_error_diagnostics.py`

**Interfaces**

- Consumes：歷史 request_id 1d123054-2633-40b7-8e07-b6aed83dad98 的 OperationalError；當時環境/版本若不可取得要記缺失。
- Produces：脫敏 incident record：request_id、error_class、sqlstate、pool_wait_ms、connection_timeout、schema_head、runtime_role、source_sha；logging 不包含參數/DSN/token。

**案例：** U16, C61T-15。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_database_error_diagnostics_redacts_secrets：注入 password-bearing DSN / JWT / SQL bind 值後，輸出完全不含這些值；保留 SQLSTATE 與 request ID。分別模擬 pool exhaustion、connect timeout、missing relation/privilege，不能都歸類為 cold start。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先讀已有 logs，再加入結構化診斷；歷史無資料時在相同版本隔離環境受控重現。記錄證據能排除及不能排除的原因，輸出一項可驗證的根因假設或明確 blocked。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_error_diagnostics.py --junitxml=artifacts/c61-diag.xml
```

- [ ] **5 — 驗收與commit：** 只有能連接 request → driver/SQLSTATE → 實際故障位置的證據才解除 C61-05 的阻塞；僅加 logging 不算 F21 已修。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-04: 取得 workspace 500 根因證據` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 關閉新增診斷或 revert logging；保留事故報告。

### C61-05 — 修正已證實的 500 原因

**映射：** A26-08;Q17 · F21  
**優先／狀態：** P1／受阻  
**負責／估工：** Backend / SRE；根因確認後估算  
**依賴：** C61-04

**Files（現有檢視／按需要修改）：**

- `docs/buyeros/incidents/2026-10-03-workspace-500.md`

**Create（計劃新增）：**

- `services/api/tests/test_workspace_500_regression.py`

**Interfaces**

- Consumes：C61-04 confirmed cause 及精確檔案/符號；未確認就不能進入本任務實作。
- Produces：修復 PR 必須先補上實際修改檔案清單與重現條件，再改程式；維持 GET /v1/workspaces response/授權契約。

**案例：** U16。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_workspace_read_recovers_from_confirmed_cause：固定原錯誤條件，修前重現相同錯誤/SQLSTATE，修後正常讀回或可恢復分類；跨 tenant 資料=0。再測冷/熱及故障恢復。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 只修已證實的查詢、連線生命週期、schema/grant 或 pool 問題。禁止無證據增加 pool、retry 或吞掉錯誤。未知寫入不自動重播。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_workspace_500_regression.py services/api/tests/test_workspace_listing_db.py --junitxml=artifacts/c61-500.xml
python scripts/check-required-tests.py --junit artifacts/c61-500.xml
```

- [ ] **5 — 驗收與commit：** 根因、失敗重現、修後結果與相同 SHA 清楚連結；歷史無法重現則仍 open，不為關單而捏造原因。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-05: 修正已證實的 500 原因` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** revert 單一修復/相容設定；保留診斷和事件時間線。

### C61-06 — 把 workspace discovery 改為有界查詢

**映射：** A26-04;Q13;N02 dependency · F18  
**優先／狀態：** P1／待開始  
**負責／估工：** Backend / DB；2–4 人日  
**依賴：** C61-01, C61-02

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/api/routes/workspaces.py`
- `services/api/buyeros_api/api/deps.py`
- `services/api/buyeros_api/db/models.py`
- `services/api/tests/test_workspace_listing_db.py`
- `services/api/tests/benchmark_workspace_directory_case.py`
- `scripts/benchmark-workspace-directory.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/services/identity_resolver.py`
- `services/api/buyeros_api/services/workspace_directory.py`
- `docs/buyeros/decisions/2026-10-06-workspace-discovery.md`
- `services/api/tests/test_identity_resolver_db.py`

**Interfaces**

- Consumes：現有 users(issuer,subject) 唯一鍵；先檢視 peer codex/q13-workspace-discovery / fa198ae…，該版本僅 metadata 已知、未於本計劃驗證。
- Produces：async resolve_user_id(session: AsyncSession, principal: Principal) -> UUID | None；async list_authorized_workspaces(session: AsyncSession, *, user_id: UUID, offset: int, limit: int) -> WorkspacePage。WorkspacePage 沿用既有 route schema。

**案例：** P09, P10, O26-12, C61T-01。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_directory_queries_bounded_with_unrelated_workspaces：W=1/10/100/1000，查詢≤6且不隨 W 增長；分頁無漏重；revocation 下一 request 失效；不提供 user_id 的外部偽造入口；pool 重用後另一身份看不到前一人的 directory。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先 review/reuse peer 的 RLS-safe 設計；讓 route 與 load_membership 共用 resolver。SQL 只查可見 membership 的 page+count，不先讀全部 workspace。若採受限 DB function，ADR 必须定義可信 canonical actor 的 server 綁定、固定 search_path、最小 EXECUTE grants、readonly 與撤權行為；不得放寬 tenant RLS、給 runtime BYPASSRLS/superuser。migration 在讀取最新 heads 後分配，不硬套 0038。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```python
assert report["queries"]["max"] <= 6
assert visible_ids_b == authorized_ids_b
assert unrelated_workspace_count_does_not_change_query_count
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_workspace_listing_db.py services/api/tests/test_identity_resolver_db.py services/api/tests/test_workspace_benchmark_tools.py --junitxml=artifacts/c61-directory.xml
python scripts/benchmark-workspace-directory.py --samples 30 --actors 1 --output artifacts/c61-directory-new.json
```

- [ ] **5 — 驗收與commit：** owned PG16 benchmark CLI exit 0 且 SQL gate=true；舊 4/22/202/2002 查詢數只作 baseline。EXPLAIN/query 計數/role/RLS 證據齊備；n=30 p99 只標不穩定。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-06: 把 workspace discovery 改為有界查詢` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 先停新查詢入口並切回相容 route；保留新增 schema。若舊路徑恢復 O(W)，記效能退化，不放鬆授權。

## Neon Auth 遷移

### C61-07 — 完成 N00：Neon 的真實產品登入契約

**映射：** A26-06;N00 · F20  
**優先／狀態：** P1／待驗收  
**負責／估工：** Auth / Frontend；2–4 人日  
**依賴：** C61-01

**Files（現有檢視／按需要修改）：**

- `docs/buyeros/decisions/2026-10-03-neon-auth-contract.md`
- `package.json`
- `pnpm-lock.yaml`
- `scripts/neon-real-preflight.mjs`
- `scripts/neon-real-runtime.mjs`
- `tests/e2e/audit-neon-runtime-built.spec.ts`
- `playwright.neon-runtime-built.config.ts`

**Create（計劃新增）：**

- `docs/buyeros/decisions/2026-10-06-neon-production-contract.md`

**Interfaces**

- Consumes：@neondatabase/auth 0.5.0-beta 僅為證據 snapshot 的 devDependency；不假設當前 SDK/Neon server 契約未變。
- Produces：版本化 ADR：SDK version、official documentation URL/date、Neon project/branch、session endpoint、API JWT mechanism、issuer/audience/JWKS/algorithm、cookie/CSRF、supported callback/logout、return path、Google 是否已配置、portable/Vercel artifact 測試矩陣。

**案例：** NA01, NA04, NA05, O26-11。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** 在同一 BuyerOS build 測 email sign-in → callback/session → API JWT → authenticated GET → reload → logout；Google 已配置才執行且要列必要 gate，未配置保留 NA05 blocked。追蹤原 302 fixture failure：測試是否覆蓋官方支援產品路徑，保留原失敗證據，不能刪 assertion 或把 unknown 改 pass。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 執行時查 Neon 官方文件並讀 pinned SDK source，核對 Vinext/Nitro 產物。採官方支援 client/server entrypoint；不得直接將 Auth0 authorize/oauth/token/v2/logout URL 字串換成 Neon。N00 的 diagnostic proxy/spike 不直接升格正式 middleware。若現 framework 不相容，產出最小 route adapter 修補或明確架構決定，不能私自重寫整個 framework。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
pnpm exec playwright test --config playwright.neon-runtime-built.config.ts
node scripts/neon-real-preflight.mjs --help
```

- [ ] **5 — 驗收與commit：** fixture 與真實 Neon 分開記錄；真實隔離 branch、built portable 及 Vercel preview 都過產品流程才 N00 完成。--help 只確認 runner 用法，實際 run 用 ADR 中已核對的 flags，不能以 help 成功關單。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-07: 完成 N00：Neon 的真實產品登入契約` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 維持 Auth0 現有路徑；移除未採用 spike overlay。真實 Neon 測試帳戶只依 owner/nonce 精確清理。

### C61-08 — 完成 N01：環境與 auth server 邊界

**映射：** A26-06;N01 · F20  
**優先／狀態：** P1／待開始  
**負責／估工：** Auth / Platform；1–2 人日  
**依賴：** C61-07

**Files（現有檢視／按需要修改）：**

- `package.json`
- `pnpm-lock.yaml`
- `services/api/buyeros_api/settings.py`
- `services/live/auth.ts`
- `tests/e2e/audit-neon-compat.spec.ts`

**Create（計劃新增）：**

- `lib/auth/neon-server.ts`
- `lib/auth/neon-config.ts`
- `app/api/auth/[...path]/route.ts`
- `tests/neon-production-config.test.mjs`

**Interfaces**

- Consumes：C61-07 ADR 決定的 SDK 公開 API、cookie/session/token 路徑與部署環境。
- Produces：loadNeonConfig(env: Record<string,string|undefined>): NeonConfig；NeonConfig={authUrl:string, publicOrigin:string, cookieSecret:string} 僅在 server 解析；SDK 初始化參數以 N00 官方契約映射。前端只拿無秘密的 provider/readiness 設定。

**案例：** S04, S05, NA01, NA02, NA03, O26-11。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_neon_config_rejects_missing_or_wrong_environment：缺任何必要值、preview 指向錯 branch、origin 不匹配即 fail closed；production emitted client bundle 不含 cookieSecret、service key、test credentials、fixture trust。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 新增最薄 SDK server wrapper/catch-all handler；若 N00 證實路由形狀不同，以 ADR 更新本檔案表再實作。把 auth cookie 邊界限定於 auth route；業務 gateway 不轉發 cookies。production 依需要將 SDK 改 runtime dependency，保持 lockfile frozen；不要順手升級其他依賴。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
node --test tests/neon-production-config.test.mjs
pnpm exec tsc --noEmit
pnpm build
node scripts/run-vercel.mjs build
```

- [ ] **5 — 驗收與commit：** 兩類 build 可用且 secret scan 無漏出；環境矩陣無默認 fallback 到 production；新增設定文件不含值。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-08: 完成 N01：環境與 auth server 邊界` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** auth provider gate 回 Auth0；保留 Neon branch，勿使既有使用者無法登入。

### C61-09 — 完成 N02：不可變 canonical identity 映射

**映射：** A26-06;N02 · F20  
**優先／狀態：** P1／待開始  
**負責／估工：** Backend / DB；2–4 人日  
**依賴：** C61-06, C61-07

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/db/models.py`
- `services/api/buyeros_api/api/deps.py`
- `services/api/buyeros_api/api/routes/workspaces.py`
- `services/api/tests/test_auth_routes_db.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/services/identity_linking.py`
- `services/api/tools/link_user_identities.py`
- `services/api/tests/test_identity_linking_db.py`

**Interfaces**

- Consumes：C61-06 resolve_user_id(session, principal)；現有 User.id、membership/owner/approval/audit FK；C61-07 verified principal contract。
- Produces：新增 UserIdentity(issuer,subject,user_id,status,proof_ref,created_at)，unique(issuer,subject)；async link_identity(session, *, user_id:UUID, issuer:str, subject:str, proof_ref:str) -> UUID；resolve_user_id 簽名不變，改讀 active mapping。

**案例：** U04, U05, U06, U07, U08, S06, NA06, NA07, NA08, NA09, NA24, NA25, NA26, O26-09, O26-10, C61T-02。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_link_keeps_all_historical_foreign_keys、test_same_email_cannot_link、test_link_conflict_atomic、test_link_replay_idempotent：canonical UUID 與歷史 FK 完全不變；同 email 不自動合併；同 principal 指向不同 user 直接 conflict；重跑同映射只一列。test_identity_revoked_next_request_denied 必須覆蓋 cache。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 新增向後相容 migration（先分配最新 revision）；回填原 Auth0 issuer/sub→原 User.id，再驗證 row counts/uniqueness。舊 User issuer/sub 暫留；Neon linking 需已驗證舊新身份或管理員核實且有 proof_ref，不能僅 email。CLI dry-run 預設、expected version、每列結果；Neon-only 新戶依目前必填 User 欄位建立唯一 canonical row，再依正常流程分配 membership。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```python
assert canonical_ids_after == canonical_ids_before
assert historical_foreign_keys_after == historical_foreign_keys_before
assert revoked_identity_response.status_code in (401, 403, 404)
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_identity_linking_db.py services/api/tests/test_identity_resolver_db.py services/api/tests/test_auth_routes_db.py --junitxml=artifacts/c61-identities.xml
python scripts/check-required-tests.py --junit artifacts/c61-identities.xml
```

- [ ] **5 — 驗收與commit：** 映射前後 UUID/FK hash 對照一致；新舊 auth 同人得到同一 canonical id；不同身份不越權；tenant/session pool 重用不殘留上一 actor。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-09: 完成 N02：不可變 canonical identity 映射` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 保留 additive mapping；回舊 verifier 仍用原 User 欄位；不能回退成刪 Neon-only users 或清空其 ownership。

### C61-10 — 完成 N03：隔離信任設定的 API JWT verifier

**映射：** A26-06;N03 · F20  
**優先／狀態：** P1／待開始  
**負責／估工：** Backend / Security；2–3 人日  
**依賴：** C61-07, C61-08, C61-09

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/api/auth.py`
- `services/api/buyeros_api/api/verifier.py`
- `services/api/buyeros_api/api/jwks.py`
- `services/api/buyeros_api/settings.py`
- `services/api/tests/test_auth_cache_lifecycle.py`
- `services/api/tests/test_auth_tenant.py`
- `services/api/tests/test_api_auth.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/api/auth_trust.py`
- `services/api/tests/test_neon_verifier.py`

**Interfaces**

- Consumes：Principal(issuer:str,subject:str) 仍是 verifier 輸出；C61-07 exact trust；C61-09 canonical resolver。
- Produces：TrustConfig(issuer:str,audience:str,jwks_url:str,algorithms:tuple[str,...],key_types:tuple[str,...])；TokenVerifier.verify(token:str)->Principal；cache key=(issuer,jwks_url,kid)，每 provider 獨立。

**案例：** S01, NA11, NA12, NA13, NA14, NA15, NA16, NA24, NA25, NA26, O26-11。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_neon_exact_trust、test_same_kid_other_issuer_rejected、test_algorithm_confusion_rejected、test_rotation_hard_stale、test_invalid_claim_types_401：錯 issuer/aud/branch、none/HS/非 allowlist、jku/x5u、錯 key type、exp/nbf/sub 型別拒絕；未知 kid 有界刷新；過 hard stale 拒絕。NA11 的 EdDSA 必須由官方 contract 支持且限定在 Neon trust，不能放寬 Auth0。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 保留 Auth0 RS256；按核實結果支援 Neon key parser（例如正式 contract 指定的 OKP/Ed25519），不讓 token 自選算法或 JWKS URL。驗簽後才解析 canonical id，權限仍由 BuyerOS DB。沿用已驗證 cache TTL/stale/rate-limit 行為，配置及測試不得偷換成 fixture 值。若實際 token 不符合既定 audience 契約，回 N00 解決，不能刪 aud check。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_neon_verifier.py services/api/tests/test_auth_cache_lifecycle.py services/api/tests/test_auth_tenant.py services/api/tests/test_api_auth.py --junitxml=artifacts/c61-verifier.xml
```

- [ ] **5 — 驗收與commit：** 雙信任只在具到期時間的遷移設定開啟；驗證錯誤為可預期 401 而非 500；JWT role claim 不授予 workspace role。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-10: 完成 N03：隔離信任設定的 API JWT verifier` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 回到已驗證 Auth0 trust 設定；不放寬 issuer/algorithm 以救登入。

### C61-11 — 完成 N04：Neon session、刷新與跨 tab 登出

**映射：** A26-06;N04 · F20;F01;F08  
**優先／狀態：** P1／待開始  
**負責／估工：** Frontend / Auth；2–4 人日  
**依賴：** C61-08, C61-09, C61-10

**Files（現有檢視／按需要修改）：**

- `services/live/auth.ts`
- `services/live/session.ts`
- `features/providers/workspace-session.tsx`
- `features/live/workspace-picker.tsx`
- `tests/e2e/audit-auth-entry.spec.ts`

**Create（計劃新增）：**

- `services/live/neon-auth.ts`
- `tests/neon-session.test.mjs`
- `tests/e2e/neon-session-production.spec.ts`

**Interfaces**

- Consumes：現有 AuthAdapter：signIn(returnPath):Promise<void>、completeCallback():Promise<void>、getAccessToken():Promise<string>、signOut():Promise<void>、subject():string、returnPath():string、expiresAt():number。
- Produces：createNeonAuthAdapter(config: PublicNeonConfig): AuthAdapter；PublicNeonConfig={authPath:string}。若 SDK 需 async hydration，增加單一初始化狀態而非假回空 membership。

**案例：** U01, U02, U03, B05, B06, U13, U14, NA04, NA05, NA10, NA17, NA18, NA19, NA20, NA21, NA22, NA23, O26-01, O26-04, O26-11, C61T-03, C61T-04。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_refresh_single_flight_same_intent：20 同時請求只1 renewal；mutating retry 維持原 intent key/body。test_old_session_response_cannot_restore_scope：logout/scope-switch 後晚到 response 不寫回。test_cross_tab_logout_clears_polling：兩 tab token/scope/poller 歸零；reload/deep link 恢復正確 workspace/project。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 保留 SDK cookie session 防護與現有 scope generation/abort；access token 不落 localStorage。401/expired 只一次 single-flight refresh 與一次同意圖重試，仍失敗則登入恢復；不得任意 replay mutation。登入/登出導向限制本站 /app。跨 tab 僅傳 logout/invalidated 事件，不广播 token。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```javascript
assert.equal(refreshCalls, 1);
assert.equal(runCount, 1);
assert.equal(outboxCount, 1);
assert.equal(sessionRestoredByStaleResponse, false);
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
node --test tests/neon-session.test.mjs
pnpm exec playwright test tests/e2e/neon-session-production.spec.ts --config playwright.neon-runtime-built.config.ts
```

- [ ] **5 — 驗收與commit：** 修改該 config 的 testMatch 使新 spec 被 discovery 收錄，並確認 case count>0；built UI email/token/API/reload/logout 完成；Safari 實機與 runner 分开記錄。登出後已發 JWT 剩餘壽命要實測記錄，不能聲稱瞬時全域撤銷。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-11: 完成 N04：Neon session、刷新與跨 tab 登出` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** provider gate 回相容 adapter；清理 client session/暫存，不刪後端 identity mapping。

### C61-12 — 完成 N05：身份與租戶負向驗收

**映射：** A26-06;N05 · F20;F01;F04  
**優先／狀態：** P1／待開始  
**負責／估工：** QA / Security；1–2 人日  
**依賴：** C61-03, C61-10, C61-11

**Files（現有檢視／按需要修改）：**

- `services/api/tests/test_auth_tenant.py`
- `services/api/tests/test_auth_routes_db.py`
- `tests/e2e/audit-access-revocation.spec.ts`
- `tests/e2e/audit-memberships.spec.ts`

**Create（計劃新增）：**

- `services/api/tests/test_neon_security_db.py`
- `tests/e2e/neon-security-production.spec.ts`

**Interfaces**

- Consumes：C61-10 verifier、C61-11 session、C61-09 mappings、既有 OPERATION_ROLES/tenant RLS。
- Produces：NA01–NA27 case evidence matrix，逐案例記 fixture/live/built/role/source_sha；把新 security spec 收入 built runner discovery。

**案例：** U04, U05, U06, U07, U08, S01, S04, S05, S06, U14, NA02, NA03, NA10, NA11, NA12, NA13, NA14, NA15, NA16, NA17, NA18, NA19, NA20, NA21, NA22, NA23, NA24, NA25, NA26, NA27, O26-09, O26-11。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** 測 CSRF/origin/state、returnTo open redirect、cookie path/SameSite、role claim 注入、跨 issuer kid、identity disabled、member revoked、最後 admin 競態、API bearer 與 worker serviceauth 分離；沒有會員者仍 403/404，別的 workspace 的 existence/data 不洩漏。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 以實際 HTTP+DB strict 測試補足單元驗簽；業務 proxy 的 cookie/service secret header 不向第三方透傳；必要 cases 不可 skip，外部條件不足標 blocked 並保留完整 test intent。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_neon_security_db.py services/api/tests/test_auth_tenant.py services/api/tests/test_membership_directory_db.py --junitxml=artifacts/c61-neon-security.xml
python scripts/check-required-tests.py --junit artifacts/c61-neon-security.xml
```

- [ ] **5 — 驗收與commit：** API DB 負向零資料外洩；real session 測試可定位 cookie/CSRF 邊界；不以 decoded JWT 或 UI hide 作授權證據。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-12: 完成 N05：身份與租戶負向驗收` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 關閉新增 provider admission；保留負向測試與 evidence。

### C61-13 — 完成 N06：身份遷移及回退演練

**映射：** A26-06;N06 · F20  
**優先／狀態：** P1／待開始  
**負責／估工：** Release / DB / QA；1–2 人日  
**依賴：** C61-09, C61-12

**Files（現有檢視／按需要修改）：**

- `docs/buyeros/decisions/2026-10-03-neon-auth-contract.md`
- `services/api/tests/test_backup_restore_t28.py`

**Create（計劃新增）：**

- `docs/buyeros/runbooks/neon-cutover.md`
- `services/api/tests/test_neon_cutover_db.py`

**Interfaces**

- Consumes：已核實 mapping manifest、雙 trust 限期設定、原 Auth0 baseline、Neon-only 新戶 dataset。
- Produces：cutover runbook：expand/backfill/verify/canary/switch/monitor/retire；回退優先使用支援 Neon 的上一版 app artifact，provider-only fallback 的適用帳戶範圍另列。

**案例：** R02, R03, R04, R06, NA06, NA07, NA08, NA09, NA29, NA30, O26-10, C61T-05。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_neon_cutover_rollback_preserves_new_users：遷移前後相同歷史 FK；Neon-only 用戶在相容上一版本仍可登入及使用原資料；identity collision 使批次停止而不半連結；回退不釋放 unknown provider hold。 test_restore_replays_deletion_before_reopen：復原舊備份後先重放retention/deletion tombstones再開放資料，已刪除資料不得復活；ledger與unknown holds對帳，舊worker epoch無法接續提交。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 在隔離備份演練 schema+mapping+app rollback；保留新舊身份，不匯出密碼。舊 email/password 帳戶提供 Neon 官方支援的建立/重設流程及可追查 linking proof。設定可衡量 canary 停止條件：任何錯 actor/tenant、critical login 失敗、replay side effect 立即停止。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```python
assert neon_only_login_after_rollback is True
assert canonical_ids_after == canonical_ids_before
assert unknown_holds_after == unknown_holds_before
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_neon_cutover_db.py services/api/tests/test_backup_restore_t28.py --junitxml=artifacts/c61-cutover.xml
python scripts/check-required-tests.py --junit artifacts/c61-cutover.xml
```

- [ ] **5 — 驗收與commit：** 演練有時間線、row count/hash、可登入驗證及 rollback artifact；「改回 Auth0」不算 Neon-only 新戶回退方案。 restore/retention rehearsal須用隔離資料驗證，未重放刪除及對帳前不開放readiness。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-13: 完成 N06：身份遷移及回退演練` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 停止切換，保留支援現有用戶的 auth artifact，按 runbook 回復相容配置。

### C61-14 — 完成 N07：有限期雙信任後退役 Auth0

**映射：** A26-06;N07 · F20  
**優先／狀態：** P1／待開始  
**負責／估工：** Release / Auth；1–2 人日及觀察窗  
**依賴：** C61-13, C61-29

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/settings.py`
- `services/api/buyeros_api/api/auth_trust.py`（前序task新增後修改）
- `services/live/auth.ts`
- `docs/buyeros/CURRENT_STATUS.md`

**Create（計劃新增）：**

- `docs/buyeros/evidence/c61/neon-retirement.md`

**Interfaces**

- Consumes：C61-29 production canary/readback；C61-13 cutover/rollback；尚未完成 linking 的帳戶清單。
- Produces：Neon-only 生產信任設定及 NA28–NA30 readback；Auth0 移除需獨立 commit，舊相容 artifact 保留到 rollback 窗結束。

**案例：** NA28, NA29, NA30。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_auth0_rejected_after_retirement：原 Auth0 token 401；Neon 正確映射照常；錯分支仍拒絕。Neon-only 與歷史遷移用戶各驗登入/角色/owner/approval/audit。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 依事先記錄的 canary 觀察窗及帳戶遷移覆蓋決定退役；關閉 Auth0 admission，移除不再用的 runtime config/dependency，不刪 identity 歷史。若仍有未迁移用戶，標 blocked 並給具體支援清單，不能無限默認雙信任。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_neon_verifier.py services/api/tests/test_neon_cutover_db.py --junitxml=artifacts/c61-retirement.xml
```

- [ ] **5 — 驗收與commit：** Neon 真正成為唯一用戶 auth；production readback 與 source/config 對上。此項在 C61-29 後做，不是前端換 logo 即完成。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-14: 完成 N07：有限期雙信任後退役 Auth0` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 只在已授權 rollback 窗恢復審核過的有限期 trust；canonical mapping 與歷史資料不刪。

## 真實研究及寄送

### C61-15 — 定義並核實真實供應商接駁契約

**映射：** A26-05;Q11 · F10  
**優先／狀態：** P1／待開始  
**負責／估工：** Integrations / Product；1–2 人日  
**依賴：** C61-01

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/providers/base.py`
- `services/api/buyeros_api/providers/search.py`
- `services/api/buyeros_api/providers/model.py`
- `services/api/buyeros_api/providers/contact.py`
- `services/api/tests/test_provider_contracts.py`

**Create（計劃新增）：**

- `docs/buyeros/decisions/2026-10-06-provider-selection.md`
- `services/api/buyeros_api/providers/registry.py`
- `services/api/tests/test_provider_registry.py`

**Interfaces**

- Consumes：現有 SELECTED_LIVE_PROVIDERS 為空；ProviderCapability/ProviderIntent/Money/ProviderAdapter；尚無用戶指定的 search/model/contact vendor。
- Produces：resolve_provider(service: Service, *, environment: str) -> ProviderAdapter；按版本封存每供應商 auth、markets/languages、pricing、liability、idempotency/status/callback/cancel、retention、official source URL/日期與 sandbox evidence。

**案例：** P08, S04, S05。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_unverified_provider_stays_blocked、test_fixture_cannot_activate_in_production、test_price_change_requires_reconfirm：未核實/無價格/無 status semantics/超 budget 時不可 admission；Money 仍 Decimal USD 6 位，不用 float。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先查 repo/環境已核准供應商，沒有則做可審阅的選型比較和成本上限；確定 vendor 與測試額度後再啟用外部 calls。不把 registry allowlist 設為任意字串，不硬編假價格。把 blocker reason/action 給 Settings/readiness UI。delivery 獨立於現有 search/model/contact 三類。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_provider_registry.py services/api/tests/test_provider_contracts.py --junitxml=artifacts/c61-providers.xml
```

- [ ] **5 — 驗收與commit：** 每類供應商有可驗證 contract；選型/credential/額度缺失只阻塞相應 live gate，離線 contract/fixture 開發可繼續。禁止以解除 503 當功能完成。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-15: 定義並核實真實供應商接駁契約` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 清空本次未核實 provider activation，維持 capability_blocked。

### C61-16 — 實作真實搜尋、來源抓取及公司對應

**映射：** A26-05 · F10;F12  
**優先／狀態：** P1／待開始  
**負責／估工：** Integrations / Backend；3–5 人日  
**依賴：** C61-15

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/providers/search.py`
- `services/api/buyeros_api/execution/provider_dispatch.py`
- `services/api/buyeros_api/execution/external_runner.py`
- `services/api/buyeros_api/execution/handlers/capability_blocked.py`
- `services/api/tests/test_provider_contracts.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/providers/live_search.py`
- `services/api/tests/test_live_search_adapter.py`
- `services/api/tests/test_live_search_db.py`

**Interfaces**

- Consumes：既有 SearchAdapter.search(query:str,market:str,language:str,limit:int)->list[SearchResult]；durable ProviderAdapter.estimate/submit/status；C61-15 registry。
- Produces：LiveSearchAdapter 符合 ProviderAdapter，內部使用 SearchAdapter；intent 對應 payload/evidence 由 DB ref 取得，不把外部呼叫繞過 execute_external。每筆 source 記 canonical company ref、URL、retrieved_at、content hash、usage/ref。

**案例：** A01, A03, A04, A05, A06, A08, S02, O26-02, O26-03, C61T-06。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_search_wrong_entity_not_attached、test_search_timeout_unknown_not_resubmitted、test_fetch_redirect_private_blocked：同名/子公司不自動合併；timeout 留 unknown；URL redirect、DNS 重解析、private/link-local/loopback、超大內容及超時不可繞過 fetch 邊界；偽造來源 instruction 當資料。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先用可注入 transport 的離線契約測試，再用核准 vendor sandbox。公司 dedupe 用可追查 evidence（域名/名稱/地區等）與人工 review 閾值；不確定就 needs_review。抓取限制以集中 fetch policy 實作，不能讓模型直接打任意 URL。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_live_search_adapter.py services/api/tests/test_live_search_db.py --junitxml=artifacts/c61-search.xml
python scripts/check-required-tests.py --junit artifacts/c61-search.xml
```

- [ ] **5 — 驗收與commit：** 真實公司和來源持久化且可重開讀回；provider receipt/帳本/觀測成本對得上；無成功 receipt 不假稱研究完成。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-16: 實作真實搜尋、來源抓取及公司對應` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 關 search capability admission；保留已接受任務及 sources，未知項走 status reconciliation。

### C61-17 — 實作真實 model fit、證據驗證及人工審核銜接

**映射：** A26-05;Q10 · F10;F12  
**優先／狀態：** P1／待開始  
**負責／估工：** Backend / AI integrations；3–5 人日  
**依賴：** C61-15, C61-16

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/providers/model.py`
- `services/api/buyeros_api/execution/fit_runner.py`
- `services/api/buyeros_api/execution/fit_execution.py`
- `services/api/buyeros_api/execution/research_graph.py`
- `services/worker/buyeros_worker/fit_runner.py`
- `services/worker/tests/test_research_graph.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/providers/live_model.py`
- `services/api/tests/test_live_model_adapter.py`
- `services/worker/tests/test_live_fit_db.py`

**Interfaces**

- Consumes：既有 ModelRoute/ProviderCapability；FitDomainRunner.load_basis/hard_exclusions/fit/verify/persist；C61-16 source IDs/hash；既有 fit/domain schema。
- Produces：LiveModelAdapter 符合 ProviderAdapter；輸出只通過既有 domain validator 成為 proposal/assessment，graph checkpoint 仍只存 ID/flags；model/prompt/offer/ICP/evidence revisions 可追溯。

**案例：** A01, A03, A04, A05, A06, A08, O26-02, O26-03, C61T-07。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_model_citation_must_resolve_to_current_company、test_stale_basis_cannot_persist_match、test_source_instruction_cannot_change_tools：hallucinated/另一公司/過期 citation 不能 Match；offer/ICP 變更導致 review 或 stale conflict；硬排除不能由模型翻轉；不確定輸出 needs_review。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 用結構化輸出解析及 deterministic evidence checks 包住模型；unknown、parse error、timeout 不當成功。保留人工改稿/grounding/approval 分離，不能把 syntax-valid citation 當語義正確。共享 API execution core，worker wrapper 不另複製一套規則。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_live_model_adapter.py services/api/tests/test_fit.py services/api/tests/test_fit_eval.py --junitxml=artifacts/c61-model.xml
uv run --frozen --project services/worker pytest services/worker/tests/test_live_fit_db.py services/worker/tests/test_research_graph.py --junitxml=artifacts/c61-fit.xml
```

- [ ] **5 — 驗收與commit：** 真實 result→evidence→fit/review 可持久化；三次 provider run 尚須 C61-24 準確度 gate，單元通過不宣稱 factual accuracy。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-17: 實作真實 model fit、證據驗證及人工審核銜接` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 停 model admission；既有 proposal/assessment 保留，不自動將未驗證結果升級為 Match。

### C61-18 — 實作 Contact quote、確認及真實結果

**映射：** A26-05 · F10;F12  
**優先／狀態：** P1／待開始  
**負責／估工：** Integrations / Backend；2–4 人日  
**依賴：** C61-15, C61-16

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/providers/contact.py`
- `services/api/buyeros_api/execution/handlers/contact_submit.py`
- `services/api/buyeros_api/services/contact_result_service.py`
- `features/live/contact-quote.tsx`
- `services/api/tests/test_contact_confirm_atomicity_db.py`
- `services/worker/tests/test_contact_uncertainty_db.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/providers/live_contact.py`
- `services/api/tests/test_live_contact_adapter.py`

**Interfaces**

- Consumes：C61-15 contact capability/價目；既有 quote/confirm/submit/result 分界、current role、suppression/policy。
- Produces：LiveContactAdapter 符合 ProviderAdapter；沿用既有 quote id/pricing version/confirmation digest，結果保留供應商 ref 與 company/person evidence。

**案例：** A01, A03, A04, A05, A06, A08, S03, O26-02, O26-03。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_contact_quote_stale_price_blocks、test_contact_wrong_company_quarantined、test_contact_unknown_retains_hold：價格或policy改變需重新確認；格式有效但錯公司不可當 verified contact；超時保留 unknown/hold，只有 proven-unsent 可釋放。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 在現有 contact handler 接 registry 與 durable boundary；不得自動猜 email 當已驗證。確認前展示成本/範圍/依據；錯誤有逐筆原因與恢復入口。提供真實供應商結果抽查資料給 C61-24。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_live_contact_adapter.py services/api/tests/test_contact_confirm_atomicity_db.py --junitxml=artifacts/c61-contact.xml
uv run --frozen --project services/worker pytest services/worker/tests/test_contact_uncertainty_db.py --junitxml=artifacts/c61-contact-worker.xml
```

- [ ] **5 — 驗收與commit：** quote→explicit confirm→single operation→可驗證 contact result；錯公司/禁用 contact 輸出=0（樣本內），未驗證項清楚標示。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-18: 實作 Contact quote、確認及真實結果` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 關 contact admission；不得釋放 unknown 費用或重複購買。

### C61-19 — 接通真正可恢复的 research run

**映射：** A26-05;Q04;Q11 · F10;F08  
**優先／狀態：** P1／待開始  
**負責／估工：** Backend / Worker / Platform；3–5 人日  
**依賴：** C61-02, C61-16, C61-17, C61-18

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/api/routes/runs.py`
- `services/api/buyeros_api/services/run_admission.py`
- `services/api/buyeros_api/execution/provider_dispatch.py`
- `services/api/buyeros_api/execution/external_runner.py`
- `services/api/buyeros_api/execution/handlers/capability_blocked.py`
- `services/worker/tests/test_research_restart_db.py`
- `services/worker/tests/test_t30_broker_research.py`

**Create（計劃新增）：**

- `services/worker/tests/test_live_research_journey_db.py`

**Interfaces**

- Consumes：execute_external(engine,workspace_id:UUID,operation_id:UUID,generation:int,adapter:ProviderAdapter,intent:ProviderIntent,*,environment:str="production",outbox_intent_key:str|None=None)->str；C61-15 registry。
- Produces：selected_run_capability() 保持既有 tuple[dict|None,str]，只回已核实 capability；admit_run 仍 atomic run/outbox/intent；worker selector/epoch 显式 readback。

**案例：** B05, B06, P08, S03, S04, S05, R02, R03, R04, R06, O26-02, O26-04, C61T-08。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_lost202_single_run_outbox、test_crash_after_provider_acceptance_reconciles、test_old_epoch_cannot_commit、test_role_revoked_before_admission_blocks：回應遺失只一 run/outbox；provider accepted 之後 crash 不重送；unknown→status；kill/restart/lease fencing 不產生重複 side effect；最終 UI 與 DB/receipt 一致。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 把 disabled handler 逐項改接已驗證 adapter；禁止長 DB transaction 跨 external await。Job 進度須區分 queued/running/awaiting_reconciliation/failed/completed 及 retryability，沿用現有 domain enum，沒有的狀態須先改 OpenAPI 再生成型別。C61-15不滿足時仍 503 且具可行 blocker action。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```python
assert provider_submit_count == 1
assert persisted_run_count == 1
assert persisted_outbox_intent_count == 1
assert stale_epoch_commit_count == 0
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/worker pytest services/worker/tests/test_live_research_journey_db.py services/worker/tests/test_research_restart_db.py services/worker/tests/test_t30_broker_research.py --junitxml=artifacts/c61-research.xml
python scripts/check-required-tests.py --junit artifacts/c61-research.xml
```

- [ ] **5 — 驗收與commit：** 實際 preview 同一 project 完成 Offer/ICP→run→buyers/evidence/fit→contact→人工 review；provider費用/帳本一致，accepted/unknown無盲目重送。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-19: 接通真正可恢复的 research run` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 停新 admission、保留 reconciliation；停止舊 epoch，不能以回退應用清除 outbox/holds。

### C61-20 — 新增可追蹤站內寄送連接器

**映射：** A26-12 · F10  
**優先／狀態：** P1／待開始  
**負責／估工：** Integrations / Backend / QA；5–10+ 人日  
**依賴：** C61-13, C61-15, C61-18, C61-19

**Files（現有檢視／按需要修改）：**

- `services/api/buyeros_api/api/routes/drafts.py`
- `services/api/buyeros_api/services/draft_service.py`
- `services/api/buyeros_api/api/routes/provider_callbacks.py`
- `services/api/tests/test_provider_callbacks_db.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/providers/delivery.py`
- `services/api/buyeros_api/services/delivery_service.py`
- `services/api/buyeros_api/api/routes/delivery_callbacks.py`
- `services/api/tests/test_delivery_db.py`
- `tests/e2e/delivery-sandbox.spec.ts`

**Interfaces**

- Consumes：精確 approved draft revision、recipient、sender identity、policy/suppression、現有 outbox/operation/economic ledger；現時 delivery403 為有效保護邊界。
- Produces：新增獨立 DeliveryAdapter：estimate(intent:DeliveryIntent)->Money；async submit(intent:DeliveryIntent)->SubmissionResult；async status(provider_ref:str)->StatusResult。DeliveryIntent={key:str,workspace_id:UUID,draft_revision_id:UUID,recipient_ref:UUID,sender_identity_id:UUID,approval_id:UUID,payload_digest:str}。service 再從 immutable revision 解析 body，不能接受 client 任意 body。

**案例：** P08, S03, S04, S05, R02, R03, R04, R06, O26-07, O26-16, C61T-12, C61T-13。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_delivery_same_intent_once、test_delivery_unknown_not_resent、test_policy_revoked_before_send、test_webhook_duplicate_out_of_order、test_delivery_old_approval_rejected：network loss/重試只一 message；未知受理不新 key 重送；撤銷 policy/suppression 阻擋；signature/timestamp/replay 防護；重複/亂序 webhook 不能回退狀態或把 accepted 當 delivered。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先定 vendor/official送信與webhook契約、sender/domain verification、sandbox recipients/額度；新增狀態機與唯一 intent/event keys、callback簽章/expiry、bounce/unsubscribe/suppression；寄送前再驗 approval/policy/recipient。不得冒用 contact Service 枚舉來繞過成本 gate。每項 protocol/schema/route 變更同步生成；加 operation、index、RLS 時 migration 號按當前 heads 分配。 delivery liability/capability 採獨立 schema 並接既有 ledger；若擴充共用 Service enum，必須逐一更新 exhaustive dispatch、價格/權限/activation tests，不將 delivery 冒作 contact。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```python
assert provider_message_count == 1
assert duplicate_webhook_state_changes == 0
assert revoked_policy_submit_count == 0
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_delivery_db.py services/api/tests/test_provider_callbacks_db.py --junitxml=artifacts/c61-delivery.xml
python scripts/check-required-tests.py --junit artifacts/c61-delivery.xml
```

- [ ] **5 — 驗收與commit：** 只向已核准隔離收件人做 sandbox 測試；O26-16 有 receipt/event/readback 證據後才能進 C61-30。C61-20 未交付時 UI 明示「核准匯出／手動結果」，保留 403，不宣稱站內 outreach send 已完成。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-20: 新增可追蹤站內寄送連接器` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 关 delivery gate/停止新 admission；已送 email 無法撤回，保留帳本與 webhook reconciliation。

## UI、品質、維護及發布

### C61-21 — 讓 Overview 今日待辦直接到正確資料

**映射：** A26-09;Q09;Q14 · F14;F17  
**優先／狀態：** P2／待開始  
**負責／估工：** Frontend / Backend；2–3 人日  
**依賴：** C61-02, C61-06

**Files（現有檢視／按需要修改）：**

- `features/live/overview.tsx`
- `features/live/operations.tsx`
- `services/live/job-query.ts`
- `services/api/buyeros_api/api/routes/jobs.py`
- `services/api/tests/test_daily_ux_db.py`
- `services/api/tests/test_job_scope_db.py`
- `services/api/buyeros_api/api/routes/drafts.py`
- `services/api/buyeros_api/api/routes/buyers.py`

**Create（計劃新增）：**

- `services/api/buyeros_api/services/work_queue.py`
- `services/api/buyeros_api/api/routes/work_queue.py`
- `services/live/work-queue.ts`
- `tests/e2e/work-queue-counts.spec.ts`

**Interfaces**

- Consumes：canonical user/DB roles、workspace/project scope、既有 list filters 与 jobScopeLink；不把 workspace total 顯示成 project total。
- Produces：GET /v1/workspaces/{workspace_id}/projects/{project_id}/work-queue → {as_of:string,items:WorkQueueItem[]}；WorkQueueItem={kind,count:number,filters:{review?:"awaiting_review",queue?:"unassigned"|"unknown",status?:"failed",approval?:"pending",acceptance?:"unknown"}}。kind 固定 awaiting_review/pending_approval/unassigned/failed_job/unknown_fit/unknown_acceptance；對應列表共用同一 server predicate。

**案例：** U15, C61T-09。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_work_queue_count_equals_filtered_list：fixture A/B 每種不同數量，卡片 count 與同 scope 同 filter total 一致；未知/失敗不顯示0。test_work_queue_scope_race：切 workspace 後晚到 response 不覆蓋；as_of 由成功取得資料時間更新。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 新增有界聚合 query，role 決定可見 action；前端以 typed filter 產生 deep link。Pending approvals 與 unknown acceptance 不再導到未篩選 Operations。保留原始整數 count 和 filter chips，刷新只讀必要 summary。 新 approval/acceptance filter 先在對應列表 API/OpenAPI 增加 typed enum，再讓卡片与列表共用 predicate；不只修改 URL。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_daily_ux_db.py services/api/tests/test_job_scope_db.py --junitxml=artifacts/c61-queue.xml
pnpm exec playwright test tests/e2e/work-queue-counts.spec.ts --config playwright.audit-fixes.config.ts
```

- [ ] **5 — 驗收與commit：** 將新 spec 收入該 config 的 discovery，0 tests 不算通過；6 張卡片在角色/scope/空/錯誤狀態皆準確；新增 operation 類型生成無 drift。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-21: 讓 Overview 今日待辦直接到正確資料` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** UI gate 回舊導覽但文案要誠實；保留新 API 相容 response，不動業務資料。

### C61-22 — 把改稿與來源覆核變成可完成的日常流程

**映射：** A26-09;Q07;Q12;Q15 · F09;F14;F16;F19  
**優先／狀態：** P2／待開始  
**負責／估工：** Frontend / UX / QA；2–3 人日  
**依賴：** C61-02

**Files（現有檢視／按需要修改）：**

- `features/live/drafts.tsx`
- `features/live/draft-grounding-review.tsx`
- `features/live/draft-dirty-guard.tsx`
- `services/live/draft-grounding.ts`
- `tests/e2e/audit-draft-dirty.spec.ts`
- `tests/e2e/audit-draft-reground.spec.ts`

**Create（計劃新增）：**

- `services/live/text-selection-offsets.ts`
- `tests/text-selection-offsets.test.mjs`

**Interfaces**

- Consumes：既有 revision/grounding segment 的 Unicode code-point offset 契約；sender identity/policy/approval 版本化資料。
- Produces：selectionToCodePoints(text:string,startUtf16:number,endUtf16:number):{start:number,end:number}；來源卡顯示 title/url/date/company；技術 ID 和 digest 置於可展開 details。

**案例：** A02, A07, D01, D02, D03, O26-06, C61T-10。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_selection_with_emoji_and_combining_marks：對「中😀é文」選取結果精確對應 code-point ranges，無半 surrogate；重疊/缺口由現有 validator 拒絕。test_dirty_cancel_and_reground：Cancel 保留輸入，Save 成功才切換，revision 改後舊 approval 無效。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 用選取文字/可鍵盤操作的分段方式代替要求輸入 code-point；保留純鍵盤替代路徑。Sender details 摺疊並重用已核准 identity，保存後仍以 server version 驗證。顯示 edit→review sources→approve exact revision→export 步驟及 blocker，不暗中自動 grounded；tone/objective 沒有實效的選项按 Q07 誠實處理。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```javascript
assert.deepEqual(selectionToCodePoints("中😀é文", 1, 3), {start: 1, end: 2});
assert.equal(cancelPreservesDirtyText, true);
assert.equal(oldApprovalValidForNewRevision, false);
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
node --test tests/text-selection-offsets.test.mjs tests/audit-draft-guard.test.mjs tests/audit-draft-grounding.test.mjs
pnpm exec playwright test tests/e2e/audit-draft-dirty.spec.ts tests/e2e/audit-draft-reground.spec.ts --config playwright.audit-fixes.config.ts
```

- [ ] **5 — 驗收與commit：** 中英混合/emoji/換行/長稿可完成改稿至下載；grounding 完整覆蓋不等於語義真實，真人覆核仍保留。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-22: 把改稿與來源覆核變成可完成的日常流程` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** revert UI helper，不改 immutable revision/approval/grounding history；不能回退成丟棄未儲存內容。

### C61-23 — 改善大批維護、Settings 及可達性

**映射：** A26-09;Q02;Q05;Q08;Q09 · F03;F04;F06;F11;F14  
**優先／狀態：** P2／待開始  
**負責／估工：** Frontend / UX / QA；2–3 人日  
**依賴：** C61-02, C61-03, C61-21, C61-22

**Files（現有檢視／按需要修改）：**

- `features/live/bulk-manifest.tsx`
- `features/live/bulk-actions.tsx`
- `features/live/settings.tsx`
- `features/live/operations.tsx`
- `tests/e2e/audit-bulk-manifest.spec.ts`
- `tests/e2e/audit-keyboard-workbench.spec.ts`
- `tests/e2e/audit-daily-journey.spec.ts`

**Create（計劃新增）：**

- `docs/buyeros/runbooks/bulk-maintenance.md`

**Interfaces**

- Consumes：existing manifest exact digest/actor/scope/version/TTL；可搜尋成員目錄與逐列 result。
- Produces：不變更 manifest execution payload；UI 呈現清楚的 filter chips、selected/eligible/excluded/conflict counts、owner display name、reason、progress、resume link 及「只重試失敗」。

**案例：** U05, U06, U07, U08, U10, U11, U12, B01, B02, B03, B04, B07, B08, B09, B10, B11, B14, B15, B16, S06, O26-05, O26-09, O26-13, C61T-11。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_expired_manifest_requires_new_preview：15分鐘到期/更動 owner/filter/exclusions/scope 後確認失效；10000 可見、10001 明確拒絕。test_partial_retry_excludes_success_rows：80 success+20 failed 只重預覽 failed，版本重讀，成功不重播。鍵盤 focus 在 error/dialog 關閉後回原控制項；live region 不每次 poll 洗版。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 讓繁複技術欄位可展開；不用下載全部結果才能畫第一頁。設定顯示角色責任、capability blocker、具體恢復步驟；不以 tooltip 隱藏必要操作。維持 en/zh-HK、390px、桌面及200% zoom，長表採區域捲動不讓整頁橫向溢出。

關鍵 assertion 契約（fixture變數由本task測試建立；不能用硬編結果取代實際觀測）：

```python
assert executed_success_rows_again == 0
assert len(new_failed_only_manifest_rows) == 20
assert expired_confirmation_accepted is False
```

- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
pnpm exec playwright test --config playwright.audit-keyboard.config.ts
pnpm exec playwright test --config playwright.audit-responsive.config.ts
pnpm exec playwright test --config playwright.audit-zoom.config.ts
```

- [ ] **5 — 驗收與commit：** 五項員工任務均可鍵盤完成且 scope 清楚；實際 screen reader/人員完成率留 C61-27，不能用 axe 或截圖替代。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-23: 改善大批維護、Settings 及可達性` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** UI revert 不改 frozen manifest 和審計；保留失敗重試及 server checks。

### C61-24 — 驗收真實研究準確度與成本

**映射：** A26-10;Q10 · F12;F10  
**優先／狀態：** P1／待開始  
**負責／估工：** QA / Product / Domain reviewers；3–5 人日，標註另計  
**依賴：** C61-17, C61-18, C61-19

**Files（現有檢視／按需要修改）：**

- `services/api/tools/evaluate_research_goldset.py`
- `services/api/tools/quality_metrics.py`
- `services/api/tests/test_quality_tools.py`

**Create（計劃新增）：**

- `docs/buyeros/quality/research-gate.md`
- `services/api/tools/capture_research_predictions.py`
- `services/api/tests/test_research_capture.py`

**Interfaces**

- Consumes：既有 buyeros.research-goldset.v1 / research-predictions.v1；至少200不同公司、兩名獨立標註者、分歧由第三人裁決；固定 holdout、三次獨立 run。
- Produces：capture CLI --manifest PATH --output NEWPATH，從已完成實際 run 讀 DB/receipt/evidence，不重觸 provider；輸出既有 predictions schema 及另存 provenance。

**案例：** A01, A03, A04, A05, A06, A08, S02, O26-03。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test_capture_excludes_wrong_company_and_preserves_abstention：不能丟掉失敗/needs_review；holdout 每公司每 run 恰一列；三次不能合併成3n獨立樣本。goldset 覆蓋同名/子公司/地區/語言/矛盾過期/提示注入；contact 抽查實際公司關係。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 封存標註與provider/model/prompt/price版本及 input hash，先凍結門檻再跑。沿用 precision estimate≥95%、safety violations=0 為提議起點；報 recall/coverage/abstention 與 Wilson95% CI，各分層樣本數不足就標不足。產品另記可接受 recall/coverage/成本上限，不能測後降門檻。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
uv run --frozen --project services/api pytest services/api/tests/test_quality_tools.py services/api/tests/test_research_capture.py
uv run --frozen --project services/api python services/api/tools/evaluate_research_goldset.py --goldset artifacts/c61-goldset.json --predictions artifacts/c61-predictions.json --output artifacts/c61-quality-new.json
```

- [ ] **5 — 驗收與commit：** offline evaluator 仍 live_verified=false，另以 provider receipt/source review/標註獨立性證據作實際驗收；0 wrong-company/unsupported citation/禁用 contact，三次門檻及成本均符合已記錄值。沒有真人標註時不能宣稱達標。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-24: 驗收真實研究準確度與成本` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 停測及 admission；保留原報告、holdout、失敗案例，按精確 dataset marker 清理隔離資料。

### C61-25 — 驗收效能、輪詢、worker 公平性及容量

**映射：** A26-10;Q06;Q10;Q13 · F07;F12;F18  
**優先／狀態：** P1／待開始  
**負責／估工：** QA / Backend / SRE；2–4 人日  
**依賴：** C61-06, C61-19, C61-21, C61-23

**Files（現有檢視／按需要修改）：**

- `scripts/benchmark-workspace-directory.py`
- `scripts/benchmark-buyeros.py`
- `scripts/benchmark-buyer-mutations.py`
- `services/api/tools/quality_metrics.py`
- `services/worker/tests/benchmark_dispatcher_case.py`
- `tests/job-poller-checks.mjs`

**Create（計劃新增）：**

- `docs/buyeros/performance/c61-budget.md`
- `scripts/c61-performance-harness.py`

**Interfaces**

- Consumes：已凍結相同資料量/來源 SHA/schema/role/region/actor/repetition 的 baseline；Q06 logical60s 數據只作邏輯流量對照。
- Produces：測試 manifest + raw samples：latency_ms/sql_ms/queries/bytes/status/invalid_context；另記 pool_wait、queue_wait/oldest_age、provider cost、device/network/region、冷/暖、repeats。

**案例：** B12, B13, P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, O26-12。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** W=1/10/100/1000 每 actor30暖樣本、SQL≤6；10/25 actors階梯；1k/10k名單；poll RTT2500ms max in-flight=1、hidden pause、429 backoff；每租戶 backlog 與 worker restart，無 starvation；所有 timeout/非2xx 留在分母。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** owned PG 與核准 preview 做分開測試；效能預算起點：HK暖 UI p95≤2s/冷≤4s，API暖p95≤800ms/p99≤1.5s、5xx<1%、tenant errors=0，LCP≤2.5s/INP≤200ms/CLS≤0.1。記量測方法和環境，RUM p75 與實驗室結果不可混用；p99 n<1000標不穩定，1000亦非穩定保證。針對實測瓶頸做 index/query/pagination/cache/poll修復後同條件重跑。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
python scripts/benchmark-workspace-directory.py --samples 30 --actors 1 --output artifacts/c61-directory-final.json
node --test tests/job-poller-checks.mjs
python scripts/c61-performance-harness.py --manifest artifacts/c61-performance-manifest.json --output artifacts/c61-performance-new.json
```

- [ ] **5 — 驗收與commit：** 每項 gate 有 raw samples/樣本數/環境/SQL/成本/錯誤分母；不把 local API benchmark 說成 HK production 使用體驗。超標指出具體改善與重測，不用增加 timeout 隱藏。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-25: 驗收效能、輪詢、worker 公平性及容量` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 停止隔離負載；回退造成退化的 query/index/config 變更（schema保留相容）；不提高正式配額。

### C61-26 — 八模組同一資料鏈端到端驗收

**映射：** A26-11;Q11 · F01;F10;F12;F14;F20;F22  
**優先／狀態：** P1／待開始  
**負責／估工：** QA / Staff owner；2–3 人日  
**依賴：** C61-03, C61-12, C61-19, C61-21, C61-22, C61-23, C61-24, C61-25

**Files（現有檢視／按需要修改）：**

- `tests/e2e/fixtures/staff-journey.ts`
- `tests/e2e/audit-daily-journey.spec.ts`
- `tests/e2e/audit-research-intent.spec.ts`
- `tests/e2e/audit-draft-reground.spec.ts`

**Create（計劃新增）：**

- `playwright.c61-acceptance.config.ts`
- `tests/e2e/c61-eight-module.spec.ts`
- `docs/buyeros/evidence/c61/journey-ledger.json`

**Interfaces**

- Consumes：同一 preview artifact/Neon branch/DB schema/worker selector+epoch/provider registry；operator/reviewer/admin 分開帳戶；固定 isolated dataset。
- Produces：journey-ledger 每步含 module、role、workspace/project/entity ids、revision、request_id、job/operation/provider ref、expected/actual、artifact、cleanup marker；不保存 token/secret。

**案例：** U01, U09, B01, B02, B03, B04, B07, B08, B09, B16, D01, D02, D03, WF01, WF02, WF03, NA04, NA05, NA27, O26-01, O26-02, O26-06, O26-07, O26-08, O26-14。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** Overview 找待辦→Offer 保存/ICP批准→Buyers 匯入/去重/owner→Research runs 真實研究→Results evidence/fit/review/contact→Drafts 改稿/重ground/精確批准/export→手動 outcome append及修正→Settings member/policy/readiness→Operations progress/failed-only retry；最後 logout/reopen 讀回同資料。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 新 acceptance config 必須打實際 built preview；fixture回歸另跑不替代。注入 lost response、stale offer、跨scope晚到response、撤權、worker restart、partial bulk、unknown acceptance；每步 DB/receipt/匯出內容對照。delivery flag off 時 WF03/O26-07 仍 403；站內 send 另由 C61-30 驗收。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
pnpm exec playwright test --config playwright.c61-acceptance.config.ts
```

- [ ] **5 — 驗收與commit：** 八模組至少各一段可追查證據且整鏈成功；required cases count>0、零 fail/error/skip，環境缺失標 blocked。live唯讀smoke不等於此驗收。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-26: 八模組同一資料鏈端到端驗收` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 停止新測試任務；保留已受理/unknown任務與審計，cleanup 僅本次 marker，禁止粗略刪整個 workspace。

### C61-27 — 用真實員工驗收可用性與輔助工具

**映射：** A26-09;A26-11;Q09 · F14  
**優先／狀態：** P2／待開始  
**負責／估工：** Product / UX / 3–5 staff；1–2 人日及排期  
**依賴：** C61-26

**Files（現有檢視／按需要修改）：**

- `docs/buyeros/CURRENT_STATUS.md`

**Create（計劃新增）：**

- `docs/buyeros/uat/c61-staff-protocol.md`
- `docs/buyeros/uat/c61-staff-results.csv`

**Interfaces**

- Consumes：C61-26同一dataset；五項任務：找待辦、分派、研究失敗恢復、改稿審批、失敗批量重試。
- Produces：匿名化 task observations：participant、role、task、device/viewport/zoom/AT、started/completed、duration、error、help、scope_error、data_loss、feedback。

**案例：** U10, U11, U12, O26-13。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** 至少3位代表員工（目標3–5）各做5任務；至少覆蓋390px/desktop/200%/keyboard與實際screen reader。預先採納目標≥90%無協助完成、錯scope=0、資料丟失=0；15次任務須至少14次成功，分母不能只計完成者。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先用固定腳本做 baseline，再以相同任務/重設資料做修後測；記錄學習效應，報中位時間及高錯誤步驟。針對真實阻礙修UI後只重測受影響任務和必要安全回歸。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
人工執行 docs/buyeros/uat/c61-staff-protocol.md；把每筆原始結果寫入 CSV，保留匿名證據連結。
```

- [ ] **5 — 驗收與commit：** 真人簽核不由 Codex 模擬；缺人或screen reader未測保持 blocked，不能套用 fixture結果填pass。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-27: 用真實員工驗收可用性與輔助工具` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** UI revert 限于造成阻礙的變更；保留觀察紀錄。

### C61-28 — 把同版本驗收變成 CI 和維護門檻

**映射：** A26-13;Q11 · F13;F22  
**優先／狀態：** P1／待開始  
**負責／估工：** Release / QA / SRE；1–2 人日  
**依賴：** C61-02, C61-05, C61-06, C61-13, C61-24, C61-25, C61-26, C61-27

**Files（現有檢視／按需要修改）：**

- `.github/workflows/buyeros-ci.yml`
- `scripts/check-required-tests.py`
- `scripts/generate-api-types.mjs`
- `scripts/generate-operation-routes.py`
- `TASKS.json`
- `docs/buyeros/CURRENT_STATUS.md`

**Create（計劃新增）：**

- `docs/buyeros/release/c61-go-no-go.md`
- `scripts/check-c61-evidence.py`
- `tests/test_c61_evidence.py`

**Interfaces**

- Consumes：所有採用變更的同一candidate SHA/tree、各gate report、114原始case+新增case映射；C61-05若受阻只可記未解風險，不能默認通過。
- Produces：check-c61-evidence.py --manifest PATH：驗 source/tree/environment、unique case ids、test discovery>0、required fail/error/skip=0、thresholds、blocked/open；輸出 predeploy_ready 與具體 blockers。

**案例：** R01, R02, R03, R04, R05, R06, O26-15, C61T-14。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** test evidence checker：缺一本階段required case、混用舊SHA、空JUnit、skip或重複報告都使exit1；historical baseline 不計本次成功；同一JUnit不可重複加總。驗schema migration从受支持舊head升級到candidate，runtime role無BYPASSRLS且必要grants可用。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 將新增 focused suites 加到對應 CI job；保留 frozen lockfiles與 generated契約檢查。只抽出已變更熱點的共用服務（identity/provider/work_queue），不全庫重構。交付操作/回退/入職/bulk維護runbook、告警owner、request/job追蹤、secret管理；readiness來源統一服務端。F21仍無根因時predeploy_ready=false，只有release owner明確記錄風險接受才可另決定發布，問題仍open。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
python -m unittest discover -s tests -p test_c61_evidence.py
pnpm exec tsc --noEmit
pnpm lint
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
pnpm build
node scripts/run-vercel.mjs build
pnpm cloudflare:types
pnpm cloudflare:lint
pnpm cloudflare:bindings
pnpm cloudflare:test
python scripts/check-c61-evidence.py --manifest artifacts/c61-release-manifest.json
```

- [ ] **5 — 驗收與commit：** 全量 API/worker strict PG16及CI原有job依原工作流程成功，新tests被收錄；812歷史數字不是最低/固定值，但測試減少須解釋。每個open finding 明確列出，無修復完成=上線的混淆。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-28: 把同版本驗收變成 CI 和維護門檻` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 保留PR/CI evidence；不以停用tests或改門檻解除block。

### C61-29 — 發布研究與核准匯出版本並讀回驗證

**映射：** A26-13;Q11 · F13;F20;F22  
**優先／狀態：** P1／待開始  
**負責／估工：** Release / SRE；1–2 人日及觀察窗  
**依賴：** C61-28

**Files（現有檢視／按需要修改）：**

- `docs/buyeros/CURRENT_STATUS.md`
- `TASKS.json`
- `docs/buyeros/runbooks/worker-runtime.md`

**Create（計劃新增）：**

- `docs/buyeros/release/c61-production-readback.json`

**Interfaces**

- Consumes：C61-28具體go/no-go、C61-13回退演練、同SHApreview、expand migrations、已核准provider/Neon設定。
- Produces：production manifest：alias/deployment/source/tree/API/schema/worker/selector/epoch/provider version/auth issuer/CI/UAT；記錄canary與監控數據。 postdeploy checks全部通過後才標release_accepted；C61-28的predeploy_ready並不是production acceptance。

**案例：** U01, R01, R02, R03, R04, R05, R06, NA30, O26-01, O26-15。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** 發布前後核對 actor/tenant、登入、workspace列表、project讀回；新admission只在schema/runtime compatible後開啟。任何錯actor/tenant、double side effect、critical login失敗立即停新admission；效能/5xx按C61-25已採納門檻觀察。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先備妥可審閱migration/grants/環境差異/deploy/rollback；只有本次session或既有授權涵蓋發布才執行。順序：expand schema→相容API/worker→preview確認→canary→alias/promote→readback。Neon遷移期有截止時間，C61-14完成後才能稱Neon-only。站內delivery仍off，產品copy清楚。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
以現有CI/release runbook發布；部署後執行只讀smoke，並封存 docs/buyeros/release/c61-production-readback.json。
```

- [ ] **5 — 驗收與commit：** 合併到 main 及 production alias 的實際SHA一致性可查，不能用PRmerge代替；登入/八模組readback/告警可用。真實付費/外寄驗收不由唯讀smoke自動執行。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-29: 發布研究與核准匯出版本並讀回驗證` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 關新admission，切回已演練相容artifact與selector；fence舊epoch，保持accepted/unknown對帳；不downgrade刪migration資料。

### C61-30 — 獨立啟用站內寄送並完成全外展驗收

**映射：** A26-12;A26-13 · F10;F22  
**優先／狀態：** P1／待開始  
**負責／估工：** Release / Integrations / QA；1–2 人日及觀察窗  
**依賴：** C61-14, C61-20, C61-29

**Files（現有檢視／按需要修改）：**

- `features/live/drafts.tsx`
- `features/live/operations.tsx`
- `docs/buyeros/CURRENT_STATUS.md`
- `tests/e2e/delivery-sandbox.spec.ts`（前序task新增後修改）

**Create（計劃新增）：**

- `docs/buyeros/release/c61-delivery-go-no-go.md`

**Interfaces**

- Consumes：C61-20 connector證據、C61-14 Neon-only、已核准recipient/sender/policy、message intent + exact approval revision。
- Produces：獨立send capability gate與release manifest；完整 Offer→Research→Review→Draft→Approve→Send→receipt/events/outcomes 資料鏈證據。

**案例：** WF03, O26-07, O26-14, O26-16, C61T-16。原始逐列expected見case CSV。

- [ ] **1 — 核對現況及測試契約：** 隔離核准收件人完整journey；重複點擊/遺失回應/worker crash/webhook重複亂序不雙寄；bounce/unsubscribe阻擋後續send；失效approval/recipient變更無效；deliveryoff時原O26-07仍403。
- [ ] **2 — 建立可重現差異：** 新行為依上述具名測試先觀察預期失敗；既有修復直接重跑並核對assertions；外部／人工gate記實際前置條件，缺失標blocked。
- [ ] **3 — 完成最小實作／交付：** 先sandbox再小批canary，收件對象/文案/額度須在已有授權範圍；未授權發送先完成可審閱draft與payload再於執行時取得必要授權。UI按真實receipt顯示accepted/sent/delivered/failed，不將manual outcome偽裝provider確認。
- [ ] **4 — 驗證：** 執行以下指令／步驟；自動suite預期exit0、required cases>0及0 fail/error/skip；負向測試的被測API拒絕是預期結果，整體suite仍須pass。

```text
pnpm exec playwright test tests/e2e/delivery-sandbox.spec.ts --config playwright.c61-acceptance.config.ts
```

- [ ] **5 — 驗收與commit：** 新send spec 明確加入discovery；完整「站內寄送」完成只在此gate通過後宣稱。未做此階段，狀態永遠是research+export可用／native send未交付。 保存source/環境/結果後，只stage本task實際修改檔案，以 `C61-30: 獨立啟用站內寄送並完成全外展驗收` 為commit/PR主旨；不執行 `git add .`。人工或readback任務提交脫敏紀錄，不新增空程式。

**Rollback：** 關send admission，繼續callback/status reconciliation；已寄不可撤回，也不可rollback成重新寄送。

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
