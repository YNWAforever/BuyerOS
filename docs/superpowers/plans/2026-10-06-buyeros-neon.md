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

Neon Auth 遷移。完整全域環境、release順序和case追蹤請讀 `2026-10-06-buyeros-gpt61-fixes.md`；本份依賴關係不能省略。

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

