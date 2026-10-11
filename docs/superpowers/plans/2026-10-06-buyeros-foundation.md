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

既有修復、入職與資料庫。完整全域環境、release順序和case追蹤請讀 `2026-10-06-buyeros-gpt61-fixes.md`；本份依賴關係不能省略。

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

