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
## 子計劃範圍

UI、品質、維護及發布。完整全域環境、release順序和case追蹤請讀 `2026-10-06-buyeros-gpt61-fixes.md`；本份依賴關係不能省略。

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

