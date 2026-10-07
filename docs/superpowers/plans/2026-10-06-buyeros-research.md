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

真實研究及寄送。完整全域環境、release順序和case追蹤請讀 `2026-10-06-buyeros-gpt61-fixes.md`；本份依賴關係不能省略。

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

