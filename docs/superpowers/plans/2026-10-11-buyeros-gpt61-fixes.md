# BuyerOS 修復及剩餘開發 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本交接指定 Codex GPT‑6.1 Sol，按任務順序執行；沒有要求自動開啟多代理。

**Goal:** 恢復正式工作區，完成 Auth0 → Neon Auth，讓授權員工可以在同一資料鏈完成研究、覆核、草稿、核准匯出，以及另行驗收的站內寄送。

**Architecture:** 保留現有 React／TypeScript 前端、FastAPI API、PostgreSQL／Alembic、worker 及 durable intent／receipt 設計。先修正經證實的資料庫與應用不相容，再驗收已有 Neon、provider、bulk 和 delivery 實作。每個發布階段分開記錄 source、test、deployment、activation、live acceptance。

**Tech Stack:** 現有 pnpm lockfile、React、Vite／portable 與 Vercel runtime、`@neondatabase/auth`（稽核版本 `0.5.0-beta`）、FastAPI、SQLAlchemy／psycopg、Alembic、pytest、Node test runner、Playwright；worker backend 以實際 runtime selector 為準。

**Spec:** `BuyerOS_Audit_2026-10-11_Evidence.zip` 內的報告、Findings／Cases／Tasks／Operations／UI Actions、E01–E09，以及獨立輸入 `buyeros-20261011-workspace-error.jpg`。原始 33 個 C61 任務與 148 個 case ID 保留於 `traceability.json`；不可改寫原始證據。

**計劃日期：**2026-10-11。**執行時 repo 放置位置：**`docs/superpowers/plans/2026-10-11-buyeros-gpt61-fixes.md`。本文件是待執行計劃，不是已修復、已測試或已發布證明。

**Repository：**[YNWAforever/BuyerOS](https://github.com/YNWAforever/BuyerOS) · **正式後台：**[buyer-os-nu.vercel.app/app](https://buyer-os-nu.vercel.app/app)。本計劃以已核對的稽核版本及來源作判斷，沒有在編寫期間重新登入或修改正式站。

## Global Constraints

- 稽核基準：`cbbe0e93b0132ae07ff0d87f6cc57f871f13200e`；正式部署 `dpl_DWwUAPyLxDR6pLU95BgcUxgseAFZ`；main CI `38117173377`。執行前重新取得 current main／API／worker／部署資料，不能假定仍相同。
- ZIP SHA‑256：`538ccba296a9a2abc569189b652911882a7ef82aac21cc9da7bc89ac52bc087d`；JPG SHA‑256：`dd42e056995d6f824896c530b7e4bf9defab18a95df8dbf6c83ec1570dc6ff06`。本次核對 ZIP 的 28 個內容 hash；連 manifest 共 29 檔。
- F23 是本次 `ProgrammingError / 42P01 / user_identities`；F21 是歷史 `OperationalError`，仍未確定根因。兩案不得合併關單。
- 保留 canonical user UUID、所有歷史 FK、revoked identity、tenant／role 邊界、immutable intent、approval revision、provider receipt 和 unknown budget hold。
- 不以 email 自動 link，不改用 client claim 授予 workspace role，不把 bearer token 放入 localStorage，不把零 membership 與服務錯誤混為一談。
- 不盲目 `alembic upgrade head`、不只建空 `user_identities`、不 `stamp` 假裝 migration 已完成，不在 request／build／startup hook 自動跑正式 migration。
- 不解除 RLS、擴大權限、換 UUID 或用 fallback 200 空列表掩蓋 schema 錯誤。維持非 superuser／NOBYPASSRLS 的 runtime 驗證。
- Provider credential、feature flag、CI pass、Vercel READY、fixture pass 均不能單獨證明 live acceptance；native send 與研究／匯出分開驗收。
- 使用既有 lockfile 和實作；僅為已證實缺口作修改。不趁此重寫框架、換 ORM／worker、引入 Neon Data API／Functions 或做無關套件升級。
- 一般讀取、隔離環境修復、測試、文件及 draft PR 可持續完成；正式 schema／auth 切換、供應商 activation、付費和寄送，先準備具體變更、對象、上限及回退，再核對已有授權。不重複索取已給予的授權。
- 測試只使用 owned disposable DB。既有 `BUYEROS_TEST_DATABASE_URL` 的 loopback／`buyeros_test_*` 防線及 `BUYEROS_STRICT_INTEGRATION=1` 必須保留；不可把正式 DSN 放入 destructive fixture。
- 每批 commit 更新 current evidence；blocked／not run／inconclusive 如實保留。舊 pass 不改作本批 pass，也不硬編碼歷史 suite 總數。

## Review Focus

1. **同一 DB head、不同 branch／role／search_path：**必須拒絕錯 target 或不可用 relation；由 C61-31／33 的 `test_same_head_wrong_target_is_blocked`、`test_runtime_role_cannot_see_required_relation` 鎖定。
2. **Neon-only 新用戶遇上 rollback：**仍可登入且身份／ownership 不變；由 C61-13 的 `test_compatible_rollback_keeps_neon_only_user_access` 鎖定。
3. **已接受請求但回應遺失／worker 重啟：**恢復原 intent，不重複付費或寄送；由 C61-19／20 的 lost-ack 與 provider call-count 斷言鎖定。
4. **跨頁批量確認前 membership／資料版本改變：**不能沿用過期權限或靜默套用舊 scope；由 C61-23 的跨租戶、revocation、expiry、10k partial-result 測試鎖定。
5. **中英混合及 emoji 編輯後沿用舊 approval：**保留 dirty text，但拒絕舊 revision 匯出／寄送；由 C61-22／20 的 Unicode、revision、stale-approval 測試鎖定。

## 1. 決策與交付次序

目前最先要修的是工作區資料庫相容性。截圖 request ID `b7aea690-a1a4-4c58-b85e-27dc02a7e7c8` 與 E03 的 `42P01` 相符；圖片本身不能證明漏跑 migration，亦不能證明用戶沒有 membership。Neon 大部分程式碼已存在，正式站當時仍使用 Auth0。修復工作區不代表真實 search／model／contact 或寄送已啟用。

| 階段 | 交付結果 | 必須通過 | 仍獨立保留的狀態 |
|---|---|---|---|
| G0 工作區恢復 | 已授權員工可登入並讀到正確 workspace／roles | C61-31 → 32；必要的 33 基礎 promotion gate；N11-02／03／04／11／14 | Neon-only、研究、send 尚未接受 |
| GN Neon canary | 真實 Neon session、mapping、API trust、reload／logout、回退可用 | C61-07…13；真實隔離環境及有限正式 canary | Auth0 退役在 C61-14；不可無限期 dual trust |
| GA Research + approved export | 八模組同一資料鏈、品質／成本／效能／員工 UAT、發布讀回 | C61-15…19、21…29、完整 33 gate；GN | native send 未接受，UI 如實標示 |
| GS Native outreach | 同一 approved revision 經授權 sender／recipient 單次送出並可對帳 | C61-14、20、30；GA；signed callback／suppression／unknown recovery | 只按收件人及成本授權範圍擴大 |

**依賴調整必須顯式記錄：**原 C61-33 依賴 C61-28，而 28 是整個 GA 驗收；不可因此讓工作區故障等到全產品完成才恢復。將 33 拆成「33a：G0 schema／版本 gate」和「33b：GA／GS 完整 promotion gate」，28 拆成「28a：CI evidence foundation」和「28b：release acceptance」。父 ID 及原依賴保留，只有全部子項完成才關父任務。這是執行分期，沒有降低 GA／GS 門檻。

C61-14 仍在 C61-29 後正式退役 Auth0。GN 可以先把 Neon 登入在限定範圍接受驗證，並保留有截止時間的 dual trust；不能為等待供應商而無限延長。若期限不足，維持／回復已驗證的相容方案並重新記錄具體切換決定。

F21 無法追溯時不得假稱已修；C61-28b 必須列為 unresolved residual risk。若要在它未結案時發布，需有記錄原因、影響、告警及負責人的明確 release exception，而不是刪除 C61-05 依賴。F22 只就稽核版本差距關閉；新批次重新核對版本。

## 2. 檔案責任與執行約定

以下路徑相對 repository root；「既有」已在稽核 checkout 核對，「新增」是本計劃建議，執行 kickoff 先檢查 current main 有否等效實作。

| 責任 | 既有修改入口 | 建議新增，僅在缺少等效實作時建立 |
|---|---|---|
| 身份／workspace | `services/api/buyeros_api/services/identity_resolver.py`、`services/api/buyeros_api/services/workspace_directory.py`（同一 API package）、`services/api/buyeros_api/api/routes/workspaces.py`、`services/api/buyeros_api/db/session.py` | `services/api/buyeros_api/services/schema_readiness.py`、`services/api/tools/check_schema_readiness.py` |
| migration | `services/api/alembic/versions/0038_c61_workspace_directory.py`、`0039_c61_user_identities.py`、`0050_c61_delivery_authorizations.py` | 必要時新增下一個唯一 revision；不改已發布 migration 的歷史意義 |
| auth | `lib/auth/neon-config.ts`、`neon-server.ts`、`neon-boundary.ts`、`public-auth.ts`；`services/live/auth.ts`、`neon-auth.ts`；`features/providers/workspace-session.tsx` | 真實 Neon acceptance config／spec，與 synthetic built fixture 分開 |
| 發布 | `.github/workflows/buyeros-ci.yml`、`vercel.json`、`scripts/check-c61-evidence.py`、`docs/buyeros/release-candidate.json` | `scripts/check-release-readiness.py`、`docs/buyeros/release/schema-contract.json`、`docs/buyeros/runbooks/schema-recovery.md` |
| providers | `services/api/buyeros_api/providers/registry.py`、`live_search.py`、`live_model.py`、`live_contact.py` | 僅在實際選定 account／contract 後建立 server-owned activation 設定模組 |
| daily UX | `features/live/workspace-picker.tsx`、`overview.tsx`、`drafts.tsx`、`bulk-manifest.tsx`、`operations.tsx`、`settings.tsx` | `tests/e2e/audit-workspace-recovery.spec.ts`，加入現有 discovery |
| native send | `services/api/buyeros_api/api/routes/delivery.py`、`services/api/buyeros_api/providers/resend_delivery.py`、`services/delivery_*`、`features/live/delivery-history.tsx` | server-owned delivery selection；`tests/e2e/delivery-sandbox.spec.ts`（如 current main 尚缺） |

每個下列任務採用同一小步循環：先定位現有行為與測試；缺陷先有能重現的失敗測試；作最小修改；跑對應 focused tests；檢查 diff／evidence；獨立 commit。若現有實作和測試已滿足，不為了製造 red 重写測試或功能，轉做缺少的真實環境驗收。新增測試名稱是規格，不聲稱目前已有。

## 3. C61-01：鎖定版本及建立可追查工作清單

**優先／依賴：**P0 啟動工作；無。**處理：**F13、F22。**交付：**current baseline 和本批 selection。

**既有：**`docs/buyeros/CURRENT_STATUS.md`、`docs/buyeros/release-candidate.json`、`TASKS.json`、本計劃附帶 `traceability.json`。**新增記錄：**`docs/buyeros/evidence/2026-10-11/baseline.json`、`selection.md`。

- [ ] 讀 repo 適用的 `AGENTS.md`／README／runbook；`git status --short`、`git rev-parse HEAD`、`git log -8 --oneline`。保留用戶未提交修改，需要隔離時按 worktree 技能操作。
- [ ] 核對兩個輸入 hash，讀 E01／E03／E05 和 task current 欄位。取得 current main、部署來源、API／worker version；列出相對 `cbbe…` 的變更。無部署權限時標示 blocked，繼續本地工作。
- [ ] 對 33 個 task 填寫 `reuse / modify / activation-only / acceptance-only / blocked`，記具體 path／commit，禁止把 baseline proposed-new-files 當成仍未實作。
- [ ] baseline 記 source SHA／tree、工作分支、lockfile hash、測試環境、DB／auth／provider 未知項。私密 target 只留內部 receipt／digest，報告不放 DSN、cookie、JWT、identity subject。
- [ ] 提交 `docs: pin October 11 repair baseline and gap selection`。驗收：33 個 ID 全保留，24 findings 和 148 cases 可查，沒有修改原 ZIP。

**回退：**只撤回本批文件；不 reset 用戶分支。

## 4. C61-31：先證實正式 DB target、schema、role 與 mapping

**優先／依賴：**P0；C61-01。**處理：**F23、F18；N11-03／04／11。**估算：**0.25–0.5 人日，不含存取等候。

**讀取：**`services/api/buyeros_api/db/session.py`、`settings.py`、`services/api/buyeros_api/api/routes/workspaces.py`、`services/api/buyeros_api/services/identity_resolver.py`、0038／0039 及當前 Alembic graph。**新增：**`services/api/tools/check_schema_readiness.py`、`services/api/buyeros_api/services/schema_readiness.py`、`services/api/tests/test_schema_readiness_db.py`。

**介面決策：**`inspect_schema(connection: AsyncConnection, expected: SchemaContract) -> SchemaReadiness`，只讀取；不 migrate、不修 grants、不建立用戶。`SchemaContract` 固定 `contract_version`、`source_sha`、`required_revisions`、`required_relations`、`required_functions`、`required_privileges`、`runtime_role_policy`。target 比對另消費受信任部署／DB metadata receipt，不能單靠 `current_database()` 證明 Neon branch 正確。

`SchemaContract` 與 `SchemaReadiness` 定義於同一新增 `schema_readiness.py`，採用專案現有 typed-model 慣例。`SchemaReadiness` 輸出 `schema="buyeros.schema-readiness.v1"`、`source_sha`、`checked_at`、`target_match`、`observed_heads`、`compatible`、`checks[]`、`blockers[]`、`evidence_mode`；private receipt 可存 role／schema，公開錯誤只回安全 code／request ID。CLI 用 `--contract`、`--output` 及 `BUYEROS_SCHEMA_CHECK_DATABASE_URL` secret env 讀 DSN；不把 DSN 放 argv／stdout。以只讀 transaction、有限 statement timeout 執行；fixture 仍只用自己的 test DB，不能讀取此 production secret。exit 0=全部所需檢查通過；1=不相容／未知；2=輸入錯誤。未知不得視為 pass。

- [ ] 取得同 deployment 的連線設定來源與預期 target metadata；只讀核對 branch／database／endpoint fingerprint、`current_database()`、`current_user`、`session_user`、`current_schema()`、`current_setting('search_path')`、PostgreSQL version。
- [ ] 以實際 runtime role 查 `to_regclass('public.user_identities')`、Alembic version、0038 function 的精確 signature、schema USAGE、必要欄位 SELECT／function EXECUTE、RLS／NOBYPASSRLS；owner 視角僅用來分辨「真的沒有」和「runtime 看不到」，不能替代 runtime 結果。
- [ ] 在已授權內部查詢核對 exact legacy issuer／subject → canonical UUID／active status 與 membership；外部報告只保留去識別 count／hash／pass，不輸出身份值。
- [ ] 新增 `test_missing_identity_relation_blocks_readiness`、`test_same_head_wrong_target_is_blocked`、`test_runtime_role_cannot_see_required_relation`、`test_expanded_compatible_schema_is_allowed`、`test_unknown_schema_is_not_ready`；assert 不執行寫入，missing／wrong／unknown 均非 ready，兼容的新 head 不因字串不同被錯拒。
- [ ] 用 §22 的 strict API runner 執行新增 DB 檔案，預期 0 fail/error/skip。保存 `db-readback.redacted.json` 和根因決策表；提交 `feat: add read-only runtime schema compatibility probe`。

**決策輸出：**只能選有證據的一支：A 漏跑必要 migration；B deployment 連錯 target；C schema／search_path／grant 不相容；D 混合／其他，繼續定位。不把所有分支一併「修」到正式環境。

## 5. C61-32：相容修復及 G0 工作區恢復

**優先／依賴：**P0；C61-31。**處理：**F23、F01、F04；N11-02／03／04／11／14。**估算：**0.5–1.5 人日，按根因調整。

**既有測試：**`services/api/tests/test_identity_migration_db.py`、`test_identity_resolver_db.py`、`test_workspace_listing_db.py`、`test_workspace_directory_function_db.py`、`test_identity_linking_db.py`。**文件：**新增 `docs/buyeros/runbooks/schema-recovery.md`。需要新的 repair migration 才新增 revision，先核對 current head 避免撞號。

- [ ] 用隔離副本重現 C61-31 已證實原因；記錄修前 API failure、實際 head、canonical／FK／revoked hash。以目前 artifact 的必需 schema 建 compatibility matrix，涵蓋 API 與實際 worker；不能只看到 0039 就忽略後續依賴，也不能直接升至未知 head。
- [ ] A：排練從實際 head 到核准 target 的完整 additive migration／backfill／grant；B：只校正已確認錯誤的環境 target，保留原資料；C：精確修正 schema visibility／缺少的最小 grants；D：繼續診斷。每支都先取得預期正確 mapping 的 readback。
- [ ] 對缺陷增加 regression assertions：既有 Auth0 principal 得到同一 UUID；revoked identity 不復活；零會員返回真 empty；兩個 tenant 資料隔離；限制 role 可讀必要欄位而非整張敏感表；重跑 repair 不重複 link／audit。
- [ ] 執行 focused DB suite，再排練 compatible application rollback。rollback 保留 additive schema／歷史／holds；只有已證實相容的前端及 API artifact 才可選，不能把故障版 label 當 rollback。
- [ ] 準備正式 change set：精確 target receipt、source／artifact、from/to heads、SQL／migration revision 清單、預估鎖定與 timeout、restore point、觀測窗口、rollback 觸發及負責人。取得該具體變更已有授權後才執行正式步驟。
- [ ] 同版本重測合法員工登入 → workspace 200 → 正確 role／project；retry／reload；零會員 empty；撤銷／錯 tenant 拒絕。保存 N11 case 的 request IDs、schema receipt、前後 hash。提交 `fix: restore workspace schema compatibility`，G0 僅在實際讀回成功後接受。

**停止／回退條件：**錯 target、身份／FK 改變、越權、不可解釋資料差異、migration 鎖超出已定預算立即停止新寫入並用已排練相容 artifact；不得 drop identities 或清空資料作回退。

## 6. C61-33a／28a：在 promotion 前攔截相同故障

**優先／依賴：**P1，但 G0 推廣前要有基本檢查；31 的契約與 32 的隔離通過證據。**處理：**F24、F13；N11-17／18、C61T-14。

**修改：**`.github/workflows/buyeros-ci.yml`、`scripts/check-c61-evidence.py`、`docs/buyeros/release-candidate.json`、`docs/buyeros/runbooks/release.md`。**新增：**`scripts/check-release-readiness.py`、`tests/test_release_readiness.py`、`docs/buyeros/release/schema-contract.json`。

**介面：**`evaluate_release(manifest: dict, receipts: dict, gate: str) -> dict`；gate 僅 `workspace / research_export / native_send`。CLI `--manifest PATH --receipts PATH --gate NAME --output PATH`，exit 0=所有該 gate 的 required receipts 相符；1=blocked；2=malformed。消費 C61-31 `SchemaReadiness`，不再自行查 DB 或做外部寫入。

- [ ] 定义 machine-readable manifest：schema version、source／tree、frontend／API／worker artifact IDs、configuration digest、DB target receipt digest、required/observed heads、CI run ID／required job conclusions、schema check receipt、candidate deployment ID、known-account canary、activation statuses、rollback artifacts。
- [ ] 分開 `schema_compatible`、`workspace_read_ready`、`research_ready`、`delivery_ready`。G0 不要求付費 provider 或 worker ready；research gate 要相應 worker heartbeat／epoch／provider，delivery 再要 send authority。`/health/live` 保留 liveness，不曝露 DB 私密資料。
- [ ] 添加 negative tests：缺 relation、錯 branch、錯 role、同 SHA 但錯 config、stale receipt、CI pending／failure、缺 required job、unknown manifest key／gate、缺 rollback artifact 都不得 promote。`test_declared_true_without_receipt_is_blocked` 禁止只改 JSON boolean 通過。
- [ ] 把 gate 接到**实际** alias promotion 路徑，檢查 GitHub required checks、Vercel auto production promotion 和目前部署設定；有自動直推時改為 candidate → completed checks → runtime schema/canary → promote，驗證壞 candidate 不會改 alias。只加一個無人引用的 CI job 不算完成。
- [ ] 用一次故意缺 0039 的隔離 candidate 和一次正常 candidate 驗證拒絕／通過；留 promotion receipt，不在 production 故意破壞 schema。repo root 執行 `services/api/.venv/bin/python -m pytest tests/test_release_readiness.py -q` 及既有 evidence checker suite exit 0。
- [ ] 提交 `ci: gate promotion on runtime schema and artifact evidence`。full 33b 尚待 GA／GS receipt；CURRENT_STATUS 分清 33a done 與 33 parent open。

**避免 manifest 自指：**commit 內只放 schema／template／靜態需求；build／release receipt 固定被測 SHA，存為不可變 CI artifact／release record。後續 docs commit 不要把測試 SHA 偽裝成它自己的 SHA。不得用易變 JSON 宣告控制外部 authority。

## 7. C61-02／03／06：整合已有修復、入職與 workspace recovery UX

**依賴：**01；正式驗收依賴 G0。**處理：**F01／02／03／04／15／18。**既有：**`features/live/workspace-picker.tsx`、`features/live/navigation.tsx`、`services/api/tools/reconcile_staff_membership.py`、`services/api/buyeros_api/services/workspace_directory.py`、`services/api/tests/test_workspace_listing_db.py`、`tests/e2e/audit-memberships.spec.ts`、`audit-auth-entry.spec.ts`。

- [ ] 保留 PR12 已整合成果。為 identity、workspace service error、permission、empty membership 建明確 UI state；服務 error 保留 request ID／last checked／retry，不能顯示「沒有工作區」或反覆要求已登入者再登入。
- [ ] `workspace-picker.tsx` 的 copy handler 改為 `async ...: Promise<void>`，await clipboard write、捕捉拒絕，成功顯示「診斷資料已複製」，失敗顯示「未能複製，請選取以下診斷資料」。提供可選取去識別文字和 `aria-live`；retry pending 禁止重複提交。英文等義，既有繁中切換保留。
- [ ] 在新增 `tests/e2e/audit-workspace-recovery.spec.ts` 測 copy success／clipboard unavailable／denied、retry pending、403／empty／503、keyboard focus 和繁中；`test_copy_failure_preserves_selectable_diagnostics` assert 有回饋而非只檢查呼叫 API。加入 `playwright.audit-fixes.config.ts` discovery 與 CI required-file。
- [ ] 用既有 staff reconciliation dry-run 核对已授權員工 exact mapping／roles。需 membership 寫入時先產生精確差异清單，再按正常 admin 流程；不提升自己權限、不用測試資料覆蓋員工。
- [ ] 驗證 directory 有界 SQL：1／10／100／1000 workspace 不因總租戶數線性查詢；cursor／limit／role 一致，撤銷後下一請求拒絕，pool context 清理。用既有 tests 及 §18 benchmark，未超標不作 speculative index rewrite。
- [ ] 提交 `fix: make workspace recovery and diagnostics actionable`。驗收 N11-03／04／09、U／NA相關案例；copy 原 inconclusive 只有新實測才可改 pass。

**回退：**revert UI change 保留安全後端邊界；入職修正有 audit，不刪 canonical users。

## 8. C61-04／05：歷史 F21 獨立處理

**依賴：**01；可與其他隔離工作交錯進行。**既有：**API errors／middleware 的診斷入口（kickoff 用 `rg` 定位）、`services/api/buyeros_api/db/session.py`。**輸出：**`docs/buyeros/evidence/2026-10-11/f21-investigation.md`。

- [ ] 按歷史 request／日期尋找 driver／SQLSTATE／部署／DB correlation；只保留 allowlisted diagnostic，不輸出 SQL params／DSN／tokens。
- [ ] 如可重現，為具體 root cause 建失敗測試並修最小範圍；若是 timeout／pool 才量測 pool-wait，不把 F23 當成它的答案。
- [ ] 跑該 regression 和 workspace focused suite，保存修前／後同 SHA 對照，提交獨立 `fix: address confirmed historical workspace failure`。
- [ ] 缺歷史證據時記 `unresolved / not reproducible with retained evidence`，31／32 照常推進；28b 的 release exception 流程明示，不能填成 fixed。

## 9. C61-07／08：確認真實 Neon Auth 契約及環境邊界

**依賴：**01；live 需 G0。**處理：**F20、F15。**既有：**`docs/buyeros/decisions/2026-10-06-neon-production-contract.md`、`lib/auth/neon-config.ts`、`neon-server.ts`、`neon-boundary.ts`、`public-auth.ts`、`services/api/buyeros_api/settings.py`、`tests/neon-production-config.test.mjs`、`neon-auth-boundary.test.mjs`、`neon-auth-server-production.test.mjs`。

- [ ] 對照當日 Neon 官方文件、目前 installed SDK 與既有 ADR，固定產品為 Managed Neon Auth；使用現有 `@neondatabase/auth` adapter，不能套用舊 Stack Auth 文件或換成裸 Better Auth client。除非有具體相容問題，不先升 SDK。
- [ ] 在已核對的隔離 target 記 project／branch／auth base URL、issuer／audience／JWKS、trusted origins／callback／return path、cookie／CSRF 行為及 email／Google 登入需求；preview 不默認讀 production auth 或 DB。設定 secret 不入 source／client bundle。
- [ ] 按官方 production checklist 核對 custom SMTP、FIMMICK BuyerOS application name、自己的 Google OAuth credentials、email verification 政策、production 禁用 localhost。只把明確正式 origin 加入正式 trusted domains；preview 使用獨立範圍。若 target 的 IP Allow／Private Networking 或區域不受 Managed Auth 支援，記錄阻塞及可review方案，不關掉保護或擅自搬遷。
- [ ] 核對 `BUYEROS_AUTH_PROVIDER`、`BUYEROS_NEON_AUTH_ROUTE_ENABLED` 以及 API `BUYEROS_AUTH_MODE` 和 trust 設定一致；實際 env key 以 settings／ADR 為準。缺必需設定顯示 configuration error，不靜默 fallback 或導向未預期 provider。
- [ ] 使用既有兩類 build（portable／Vercel）驗證 server route、cookie、trusted return path、拒絕任意 redirect／CSRF／secret leakage。Node focused tests 全通過；synthetic protocol 的 built tests 註明 fixture。
- [ ] 新增 `playwright.neon-real-acceptance.config.ts` 與 `tests/e2e/neon-real-acceptance.spec.ts`，只連明確 allowlisted 隔離站點，不 mock identity/JWKS/session。分開 email 登入、需要的新戶 enrollment／verification／reset、Google 成功／取消／callback error；只向已授權測試地址發驗證郵件。
- [ ] 提交 `auth: verify Neon production contract and environment boundaries`。真實 session receipt 缺失時 C61-07 保持 blocked，不以 `--help`／單純SDK安裝／fixture pass 關單。

**官方參考：**[Neon Auth overview](https://neon.com/docs/auth/overview.md)、[production checklist](https://neon.com/docs/auth/production-checklist.md)、[trusted domains](https://neon.com/docs/auth/guides/configure-domains.md)。執行時按實際 account 再核對 SMTP／OAuth／網絡限制；本計劃不假定 Auth0 密碼或 subject 可直接匯入。

## 10. C61-09／10／12：canonical mapping、JWT trust 與租戶負向驗收

**依賴：**31／32、07／08；完整12還需11。**既有：**`services/api/buyeros_api/services/identity_linking.py`、`identity_resolver.py`、`services/api/tools/link_user_identities.py`、`services/api/buyeros_api/api/auth.py`、`services/api/buyeros_api/api/auth_trust.py`、`services/api/buyeros_api/api/jwks.py`、0039；`test_identity_*`、`test_neon_verifier.py`、`test_neon_security_db.py`。

- [ ] 明確既有介面 `resolve_user_id(session: AsyncSession, principal: Principal) -> UUID | None`：僅 exact issuer＋subject＋active 查詢，不 create／link。mapping 寫入只走既有 proof／version／current admin 校驗的 bounded atomic CLI。
- [ ] 在隔離資料以 old Auth0 與新 Neon principals 證明同人同 UUID；同 email 不同 subject 不自動合併；conflict、revoked、unknown-commit 維持拒絕／read-only reconciliation；批次任一衝突全 rollback。
- [ ] JWT 用 issuer-scoped JWKS/cache；錯 issuer／audience／alg／kid、過期／future／rotation／JWKS timeout 有界失敗；dual trust 必須有明確截止時間。JWT role claim 不授權，DB 現時 membership 才授權。
- [ ] 增補未覆蓋的 `test_wrong_branch_token_rejected`、`test_email_match_does_not_link_identity`、`test_revoked_identity_denied_with_warm_jwt`、`test_pool_reuse_does_not_leak_actor`；已有等效測試則記映射，不複製。
- [ ] 兩個 tenant × viewer／operator／reviewer／admin 真實 session 測允許及拒絕；跨 tenant URL／body／job／export／bulk 不外洩。角色撤銷和 identity 撤銷要用同一仍有效 JWT 測下一 request。
- [ ] API identity／Neon strict suite 通過、migration 前後 UUID／FK hash 相符，提交 `auth: complete canonical identity and tenant verification`。NA01…30 依原 case 真實結果逐項更新。

**回退：**保留 additive mappings／revokes；關閉新 link 寫入，不退到 email-link、不刪 Neon-only ownership。

## 11. C61-11／13：session 恢復與可用的 auth rollback

**依賴：**08…10；13 的完整驗收再依賴12。**既有：**`services/live/neon-auth.ts`、`services/live/auth.ts`、`features/providers/workspace-session.tsx`、`tests/neon-session.test.mjs`、`playwright.neon-runtime-built.config.ts`、`tests/e2e/neon-session-production.spec.ts`、`neon-security-production.spec.ts`、`services/api/tests/test_neon_cutover_db.py`、`docs/buyeros/runbooks/neon-cutover.md`。

- [ ] 用現有 session bootstrap 驗證首次載入／reload 可恢復登入，pending 有可見狀態，silent refresh 有 single-flight；20 個同時401只觸發一次 refresh，不無限 retry。
- [ ] refresh 後 mutating request 沿用原 intent／key，不能自動產生新付費 submission；scope epoch、abort、logout 使晚到的 response 不覆蓋新租戶／新帳戶。
- [ ] 跨 tab logout／expired session 清除 cache 與敏感 view；cookie logout 與已發 JWT 剩餘有效期分開記錄。DB membership／identity revocation 的下一請求拒絕，不宣稱 SDK logout 自動撤銷所有已發 JWT。
- [ ] 既有 built fixture 和真實 Neon spec 分開 discovery／JUnit；實際 Chrome／Safari 的測試來源分開。新增／復用 `test_compatible_rollback_keeps_neon_only_user_access`，以獨立舊版相容 frontend＋API 進程驗 migrated、Neon-only、revoked 帳戶。
- [ ] 排練 cold restore 時按既有 runbook 停 ingress／worker、提升 epoch、重放外部 retention tombstones、對帳 unknown holds 後才恢復 read；不可把舊 backup 的任務當新請求重送。
- [ ] 保存 GN canary／rollback artifact IDs、mapping／FK hashes、token lifetime 觀測；提交 `auth: prove session recovery and compatible rollback`。GN 接受不等於 C61-14 已完成。

## 12. C61-15：把 provider 契約與 activation 做成可維護設定

**依賴：**01；可先做離線檢查。**處理：**F10、F12。**既有：**`services/api/buyeros_api/providers/base.py`、`registry.py`、`docs/buyeros/decisions/2026-10-06-provider-selection.md`、`services/api/tests/test_provider_registry.py`、`test_provider_contracts.py`、`services/api/buyeros_api/api/routes/health.py`。

- [ ] 先記目前 `DEFAULT_REGISTRY` 空，`selected_delivery_authorization()` 為 None；這是未啟用，不是三個 adapters 都未開發。現有 enum 候選包括 Brave Search／OpenAI Responses／Hunter，不能因此假設用戶已選定帳戶／model／價目。
- [ ] 為每項 service 形成 reviewed contract：provider/account reference、版本、真實市場／語言配對、model ID／prompt version／token limit、pricing version、每次最大 liability、timeout、idempotency/status／callback 行為、retention、sandbox receipt 與授權引用。
- [ ] 復用 `ProviderRegistration`／`ProviderRegistry`／`contract_hash`；activation factory 只接受 server-owned reviewed selection。credential 不代表 active；不支援的 filter／缺支出上限／過期價目仍 fail closed，不能發網絡請求才檢查。
- [ ] 補測 `test_unselected_provider_makes_zero_calls`、`test_changed_price_requires_reconfirmation`、`test_market_language_pairs_are_not_cartesian`、`test_capability_ui_matches_registry_blockers`；保留現有等效測試。
- [ ] 令 `health.py` capabilities 由同一 readiness contract 產生正確狀態，移除與真實 activation 矛盾的永久 `unconfigured` 文案；會員只看到可操作 blocker，不看到 credential／私密 account details。
- [ ] 提交 `feat: bind reviewed provider selection to capability readiness`。沒有 account／額度時完成離線 contract 與UI，只有 live gate blocked；不要求先開新服務才可寫測試。

## 13. C61-16／17：真實搜尋、公司對應、fit 與人工覆核

**依賴：**15。**既有：**`services/api/buyeros_api/providers/live_search.py`、`services/api/buyeros_api/providers/live_model.py`、`services/api/buyeros_api/execution/provider_dispatch.py`、`services/api/buyeros_api/execution/external_runner.py`、`services/api/buyeros_api/execution/fit_runner.py`、`services/api/buyeros_api/execution/fit_execution.py`、`services/api/buyeros_api/execution/research_graph.py`（均在 API package）；`services/worker/buyeros_worker/fit_runner.py`；`features/live/research-candidates.tsx`。

- [ ] 沿用現有 adapters，逐項比對 account-specific contract／輸入輸出；保存 search receipt、正規化 domain、company match、來源時間／URL／摘錄、run／ICP revision。重開頁面可讀回，錯公司／不確定保持 needs_review。
- [ ] source fetch 拒絕內網／loopback／metadata endpoint／非HTTP schemes；每次 redirect 重新檢查；內容大小／時間／次數有界。來源中的指令當資料，不允許操控 provider tools、secrets 或發送行為。
- [ ] model fit 採固定 schema／route／prompt／token與repair限制；用 claim→source support 關係銜接 reviewer。不要以confidence高取代人工核對；unsupported／無來源不得自動approve。
- [ ] 執行 `test_live_search_adapter.py`、`test_live_model_adapter.py` 與現有 DB／worker fit suites；補 `test_wrong_domain_requires_review`、`test_redirect_to_private_address_is_rejected`、`test_source_instruction_cannot_change_authority`、`test_fit_receipt_survives_restart` 的缺口。
- [ ] 在已授權 sandbox 作有上限的真實 run，保存每一步 source／receipt／cost；C61-24 的 gold gate 未過前不宣稱 accuracy。提交 `feat: complete evidence-backed research provider handoff`。

**回退：**停新 admissions，保留原 receipts／來源／review 決定；未知操作只 status reconcile。

## 14. C61-18／19：Contact 與 durable research run

**依賴：**15／16／17；02。**既有：**`services/api/buyeros_api/providers/live_contact.py`、`services/api/buyeros_api/execution/handlers/contact_submit.py`、`services/api/buyeros_api/services/contact_result_service.py`、`services/api/buyeros_api/services/run_admission.py`、`services/api/buyeros_api/api/routes/runs.py`（API package）；`features/live/contact-quote.tsx`、`run-progress.tsx`；`services/worker/tests/test_research_restart_db.py`、`test_contact_uncertainty_db.py`。

- [ ] quote 明確顯示公司／lookup scope／currency／expiry／最大費用；explicit confirm 固定 quote revision、actor、workspace、project、key。費率／scope 改變重新確認，不捏造 email，不把 unverified 顯示為 verified。
- [ ] 在現有 state machine 實現／驗證 accepted、running、needs_review、completed、failed、cancelled、unknown；UI 說明下一步。接受後回應遺失，reload／relogin／tab switch 從持久 intent 找回同 operation。
- [ ] fault-injection：丟202、提交timeout、worker在commit前後停止、重複queue delivery、role撤銷。assert 原 intent／key 不變；每個外部 submit ≤1（在provider契約允許的replay界線內）；unknown 不新建請求、不釋放未知 hold；取消不假稱已取消不可逆外部作業。
- [ ] 執行 `tests/audit-research-intent.test.mjs`、API `test_live_contact_adapter.py`／`test_contact_confirm_atomicity_db.py` 與 worker restart／uncertainty suites；缺少串接時新增 `services/worker/tests/test_live_research_journey_db.py`，明示 fixture transport，不冒充live。
- [ ] 同一隔離 project 真實完成 Offer／ICP → run → candidates／fit → contact receipt → human review；cost ledger 逐筆對帳。提交 `fix: complete resumable research and contact journey`，未拿真實 receipt 留 live blocked。

## 15. C61-21／22：Overview、改稿、來源覆核與 exact export

**依賴：**02／06；真實資料依賴19。**處理：**F09／16／17／19。**既有：**`features/live/overview.tsx`、`drafts.tsx`、`draft-grounding-review.tsx`、`draft-dirty-guard.tsx`；`services/live/work-queue.ts`、`draft-grounding.ts`、`text-selection-offsets.ts`；`services/api/buyeros_api/services/work_queue.py`、`services/api/buyeros_api/api/routes/work_queue.py`。

- [ ] Overview 六張卡與點入列表共享 workspace／project／role／filter；count 是 total 不只是本頁數量。0、loading、error 分開；change scope 清旧response；卡列更新時間／範圍／下一動作。
- [ ] 草稿保留 unsaved text，網絡／權限／version conflict 不清 buffer；離頁、換tab／account／project按既有 dirty guard 處理。save conflict 讓人比較版本，不默默覆蓋。
- [ ] 修改 body／tone／objective 產生對應 revision 並重新核對事實／來源；舊 approval 失效。Unicode 選取沿用明確 offset 協議，測中英／emoji／換行；覆蓋範圍完整與語義有支持分開。
- [ ] approved export 僅取已核准的 exact revision；export download text/hash 與 approval 對得上。權限撤銷或revision改變拒絕；未啟用native send時主動作為「核准匯出」，如已有manual outcome則明示由員工記錄，不能標成provider delivered。
- [ ] 執行 `tests/e2e/work-queue-counts.spec.ts`、`audit-draft-dirty.spec.ts`、`audit-draft-reground.spec.ts`、`c61-unicode-joined-fixture.spec.ts` 及對應DB test；添加缺少的 stale-approval／scope-switch斷言。
- [ ] 提交 `fix: align work queues and approved draft revisions`。以實際草稿下載readback驗收，不只截圖。

## 16. C61-23：Bulk、Settings、Operations 與日常可用性

**依賴：**02／03／21／22。**處理：**F03／05／06／11／14。**既有：**`features/live/bulk-manifest.tsx`、`bulk-actions.tsx`、`operations.tsx`、`settings.tsx`、`member-directory.tsx`；`services/api/tests/test_bulk_manifest_db.py`；`tests/e2e/audit-bulk-manifest.spec.ts`、`audit-keyboard-workbench.spec.ts`、`audit-maintenance-settings.spec.ts`。

- [ ] 選取區分「本頁 X 筆」與「全部符合 Y 筆」；preview 固定 workspace／project／filter query digest／entity版本／action／owner／actor／expiry。換scope清selection；expired必須重preview。
- [ ] Confirm 前後重新校驗 current role／policy，不依UI隱藏按鈕授權；10k manifest分批處理、有界request／results paging。結果保留success／conflict／denied／failed／unknown；僅 failed child manifest 安全重試，成功項不再送。
- [ ] Operations 顯示用途、建立者、scope、進度、耗時、last updated、原intent／receipt、錯誤分組。unknown 只提供 reconciliation；permanent deny 不自動重試；篩選／頁碼可恢復，不下載未授權完整清單。
- [ ] Settings 將members／roles、budget、provider contracts／readiness分區；每個blocker有可理解原因、可執行動作、負責角色。單區失敗可獨立retry；編輯衝突保留輸入；admin診斷不依賴付費provider已開啟。
- [ ] 10k隔離case：50個版本衝突＋worker中途重啟 → 9,950 success／50 conflict、總數10,000、重複處理0。另測confirm後撤銷role、scope switch、expiry、lost acknowledgement，逐項count對DB。
- [ ] 驗證390px、200%zoom、keyboard／focus／aria-live、繁中／英文。bulk toolbar、dialog、table可操作；自動axe只能補充，真人screen reader留27。
- [ ] 更新 `docs/buyeros/runbooks/bulk-maintenance.md`：preview→confirm→monitor→failed-only retry→unknown reconcile；提交 `feat: finish bounded bulk maintenance and recovery UX`。

## 17. C61-24：真實品質與成本 gate

**依賴：**17／18／19。**既有：**`services/api/tools/evaluate_research_goldset.py`、`evaluate_frozen_research.py`、`capture_research_predictions.py`、`quality_metrics.py`；`services/api/tests/test_quality_tools.py`。**輸出：**`docs/buyeros/quality/research-gate.md` 與受控去識別raw evidence。

- [ ] 在執行前由產品／技術負責人固定dataset／門檻／sample plan／允許成本，避免看完結果才改門檻。保留原 case 的 A01…A08定義；報告第8節的A01等表格標籤是情境分類，不覆蓋CSV case ID。
- [ ] 至少60家公司gold set，包含HK／中英、同名／子公司／錯domain／過期來源；至少100事實claims，含Unicode、無支持、誤引及prompt injection。人工標註與待評model輸出分開，兩位reviewers記分歧。
- [ ] 建議採用 company precision ≥95%；**已核准輸出** wrong-company／unsupported claim／禁用contact=0（樣本內）；100% approved factual claims有人審支持。raw候選錯誤要留在分母並導向needs_review，不能因人工剔除後0錯便宣稱原model100%准确。
- [ ] 同一凍結設定做3個有界run；保存sourceURL／段落／時間、prediction、adjudication、實際provider receipts／charge、max liability、unknown holds，逐筆ledger對帳。成本門檻取自已採用contract，不在計劃捏造費率。
- [ ] evaluator結果只代表該資料集；offline輸出維持 `live_verified=false`，真正live receipt另存並交叉引用。未真人標註／無實收費用readback則相應gate blocked。
- [ ] 提交 `test: record real research quality and cost acceptance`；失敗先修對應adapter／review規則，重新評未看過的保留樣本，不只刪壞case。

## 18. C61-25：效能、輪詢與維護容量

**依賴：**06／19／21／23；directory隔離benchmark可提前。**處理：**F07／11／12／18。**既有：**`scripts/benchmark-workspace-directory.py`、`c61-performance-harness.py`、`benchmark-buyeros.py`、`benchmark-buyer-mutations.py`、`benchmark-worker-capacity.py`、`tests/job-poller-checks.mjs`。

| 測試 | 資料與方法 | 驗收／輸出 |
|---|---|---|
| Directory | owned PG16、實際buyeros_api role；W=1/10/100/1000；actors=1/10/25；每actor每stage 30–100warm samples | 既有ceiling p95≤800ms、p99≤1500ms、SQL≤6、tenant error0；逐stage分母／raw timings；少量p99標不穩定 |
| Bulk | 50／500／10,000，50 conflict及restart | 結果完整、重複0、bounded memory／payload／paging；列queue age與duration，時間目標先採用再量 |
| Polling | 多tab／多job、hidden／offline／resume／scope switch | 無無限poll、無重複active poller；abort舊scope；記request rate與SSE fallback，先定網絡預算 |
| Worker | backlog、tenant大小不均、restart／lease expiry | 小tenant不飢餓、unknown不resubmit、epoch fencing；實際backend量測，不把另一種worker fixture當正式容量 |
| UI | 桌面／390px、受限CPU／network、列表／bulkpreview | 建議LCP≤2.5s、INP≤200ms、CLS≤0.1；lab與field分開，無RUM則不填field pass |
| Same-chain | 同project成功flow | 拆auth／DB／queue／provider／render的p50/p95與失敗率；不用tool round-trip代替站點latency |

- [ ] 使用既有 owned runner，從repo root執行下列三次。**這個 benchmark runner 只接受它自己建立的 Docker PG16**；執行前依 `DATABASE_VARIABLES` 清除該子進程繼承的DB設定，不變更其他shell／正式環境。輸出必須是新檔；重跑用新run目錄，不覆蓋舊證據：

```bash
services/api/.venv/bin/python scripts/benchmark-workspace-directory.py --samples 100 --actors 1 --output artifacts/repair/directory-1.json
services/api/.venv/bin/python scripts/benchmark-workspace-directory.py --samples 100 --actors 10 --output artifacts/repair/directory-10.json
services/api/.venv/bin/python scripts/benchmark-workspace-directory.py --samples 100 --actors 25 --output artifacts/repair/directory-25.json
```

- [ ] 依既有 harness schema 凍結manifest／source bridge／budget／report hashes，再跑 `services/api/.venv/bin/python scripts/c61-performance-harness.py --manifest artifacts/repair/performance-manifest.json --output artifacts/repair/performance-report.json`。這個harness只評已有樣本，不會產生新流量，也不等於live acceptance。
- [ ] 留意目前harness對5xx使用 `>= ceiling` 判失敗，且directory有效性還要求所有測試請求無錯；因此實際更嚴，1%邊界不可宣稱pass。保持0錯誤的owned成功batch；若調整SLO比較運算，另有明確boundary test和採用決定，不暗中放寬。
- [ ] 超標按 trace定位才修改SQL／index／pool／payload／route bundle／polling。保存EXPLAIN、querycount、poolwait（無法量到就unknown）、response bytes、memory。F23不是cold-start問題。
- [ ] 正式站恢復後只作已授權有界canary；壓測在隔離代表性環境。門檻未採用、樣本／環境不符不填pass。提交 `perf: address measured bottlenecks and retain raw benchmarks`。

## 19. C61-26／27：八模組同一資料鏈與真人 UAT

**依賴：**03／12／19／21／22／23／24／25。**既有：**`tests/e2e/c61-eight-module-fixture.spec.ts`、`audit-daily-journey.spec.ts`、`fixtures/staff-journey.ts`。**新增或補足：**`playwright.c61-acceptance.config.ts`、`tests/e2e/c61-eight-module.spec.ts`、`docs/buyeros/uat/c61-staff-protocol.md`、`c61-staff-results.csv`、`docs/buyeros/evidence/c61/journey-ledger.json`。

**Journey ledger** 至少含 `source_sha`、`environment`、`auth_provider`、去識別actor/role、workspace／project、offer/ICP revision、run/intent、candidate/source/review、buyer/contact receipt、draft revision／grounding／approval、export hash、每段case/evidence reference；send另加message／sender／recipient scope／event，不塞入GA已完成標記。

| 模組 | 必須完成的一段 | 驗收讀回 |
|---|---|---|
| Overview | 選workspace/project、從待辦卡進入 | count及filter與下一頁一致 |
| Offer | 建產品及來源、ICP revision核准 | version／sources／approval |
| Buyers | 開run、覆核candidate、去重及分派owner | company/source/reviewer decision |
| Results | 看fit／支持來源、contact quote／confirm | receipt、verified狀態、費用 |
| Research runs | 看progress、reload恢復、失敗/unknown處理 | 同intent/run，無重複charge |
| Drafts | 生成／改稿／reground／核准／下載 | exact approved revision/hash |
| Settings | 核對role／policy／budget／provider readiness | API current authority與UI一致 |
| Operations | 找同run/job、看結果及failed-only retry | result counts、receipt、audit |

- [ ] fixture先串通，再真實隔離auth／API／worker／provider同鏈；不能用八個互不相關demo畫面拼成成功。沒有外部存取時 fixture可完成，但real spec標blocked。
- [ ] 用角色分工完成一条链；另作負向wrongtenant／viewer不能操作、revoked拒絕、dirtyconflict、unknown recovery。required discovery非空、執行集合與收錄集合一致、0fail/error/skip。
- [ ] 真人operator及reviewer各做5項日常工作：啟動研究、辨識錯公司、補來源改稿並匯出、跨頁分派／批量維護、查失敗及只重試失敗項。記完成時間、錯誤、求助次數及阻礙；390px／keyboard／實際screen reader另記。
- [ ] UAT完成門檻：核心任務可完成、无錯tenant／重複cost／資料丟失、沒有阻止完成的UI缺陷；耗時／求助門檻在開始前與owner固定。Codex不得假扮員工簽核。
- [ ] 提交 `test: accept same-chain research workflow and staff usability`。GA驗收缺人或真實provider receipt時保持blocked，繼續可獨立完成的工作。

## 20. C61-28b／29／33b：Release A、文件與發布讀回

**依賴：**完整02／06／13／24／25／26／27；F21依§1明示；33a已落地。**修改：**`.github/workflows/buyeros-ci.yml`、`scripts/check-c61-evidence.py`、`scripts/check-required-tests.py`、`docs/buyeros/CURRENT_STATUS.md`、`TASKS.json`、release manifest／runbook。

- [ ] 以同一candidate跑原CI所有required jobs及新增tests。API／workerstrictDB、frontendbuilt、auth／migration／contract各層0fail/error/skip；保留discovery與JUnit。不能固定用325／2525等歷史總數作新成果；測試減少需具體原因。
- [ ] 執行 generated types／operation routes drift check；93是稽核版本inventory，不是未來永遠固定的數量。新operation必須有auth／role／scope／response／error及generated mapping，不因「有路由」標endpoint測試完成。
- [ ] current狀態區分 `implemented_at_sha`、`tested_at_sha`、`deployed_at_sha`、`activated`、`live_accepted_at`；每一boolean有證據引用。歷史文件保留並標historical，更新讀者入口，避免再稱PR12 draft或Neon可以開始。
- [ ] §6 release gate `research_export` 必須接收GN、quality、performance、UAT、worker／schema／provider receipts。缺一項拒絕GA；UI可誠實顯示有限可用性，但不得宣稱研究全可用。
- [ ] 準備確切production artifact／config／schema／provider activation差異、上限、已驗證rollback及告警；核對授權後promotion。從正式alias重新讀source／API／worker／schema digest，再用合法帳戶做有界readback。
- [ ] 保存 `docs/buyeros/release/c61-production-readback.json`：workspace、八模組同鏈對照、未知項及rollout觀察。paid/writejourney要沿用已授權testproject及budget，唯讀smoke不能取代它。
- [ ] 提交 `release: reconcile Research A evidence and production readback`。若正式讀回失敗，停止擴大、按已驗證artifact回退，保留migration及unknown receipts。GA可接受但GS仍false。

## 21. C61-14／20／30：Auth0 退役與獨立 native send

### C61-14：退役 Auth0

**依賴：**13、29。**修改：**`services/api/buyeros_api/settings.py`、`services/api/buyeros_api/api/auth_trust.py`、`services/live/auth.ts`、`docs/buyeros/runbooks/neon-cutover.md`、CURRENT_STATUS。

- [ ] 確认GN／GA實際使用Neon且migrated與Neon-only角色可用，記dualtrust確切截止時間及觀察窗，保留相容Neonfrontend／APIrollback。
- [ ] 在有具體切換授權時收窄APItrust至Neon、前端預設Neon；重測Auth0token被拒絕、Neon有效token／reload／roles正常。停止舊登入入口不等於刪Auth0帳戶或資料。
- [ ] 觀察遷移失敗率、未知identity、401／403／workspace5xx；有identity／tenant錯誤即停止rollout。依保留期再移除無用secret／code，不能提前讓Neon-only用戶無路可回。
- [ ] 提交 `auth: retire Auth0 after verified Neon cutover`；有productionreceipt才標 `neon_only_accepted=true`。

### C61-20／30：完善送信與完整外展

**依賴：**工程可於13／15／18／19後隔離驗證；正式GS必須14、20、29。**既有：**`services/api/buyeros_api/api/routes/delivery.py`、`delivery_callbacks.py`、`delivery_history.py`；`services/api/buyeros_api/services/delivery_admission.py`、`delivery_budget.py`、`delivery_submission.py`、`delivery_reconciliation.py`；`services/api/buyeros_api/providers/delivery.py`、`resend_delivery.py`；`features/live/delivery-history.tsx`、`drafts.tsx`、`operations.tsx`。沿用0048…0050與現有ledger，舊disabled `/deliver` 不偷偷打開。

**既有介面保留：**`selected_delivery_authorization(*, workspace_id: UUID, draft_id: UUID, actor_id: UUID) -> DeliveryBudgetAuthorization | None`。以已review server-ownedregistry提供authority；flag／browser payload／credential不能直接選account、sender、price或recipient。

- [ ] 建立可review的selection：account／sender verification／recipient test allowlist／scope、approved revision、policy／suppression、currency／pricing／cost cap、expiry／contract hash、授權引用。無selection仍403／503且外部call=0。
- [ ] 復用既有admission→ledger→native runner→signed callback/status reconciliation；提交前再查currentmembership、approval、policy、suppression。token／requestbody無法改serverauthority；unknown保持原reference／hold，不換provider重寄。
- [ ] 新增或復用：同key同revisionreplay不重寄；同key改body409／拒絕；編輯後舊approval拒絕；role撤銷零POST；POSTtimeoutunknown只GETstatus；偽造／重放／乱序callback不倒退；bounce／complaint／unsubscribe阻止後續寄送。
- [ ] 執行現有API `test_delivery_*`、`test_resend_delivery_*`及sender／suppression相关tests；新增spec必須收錄，不因沒有收錄而「全綠」。修正UI預覽sender／recipient／subject／body／revision，確認後顯示messagehistory，accepted與delivered分開。
- [ ] 先準備實際message、testrecipient、sender、costcap及rollback再核對寄送授權；只向已授權隔離收件人做單次真實send，保留providerreceipt、callback、readback及費用。模擬callback不能取代真正delivered證據。
- [ ] GS gate通過才標站內outreach完成。按範圍逐步啟用；回退只停止新admission／submit，保留status／callback對帳及suppression。提交 `feat: activate independently verified native outreach`。

## 22. 執行命令、證據與關單規則

以下命令是供執行者使用，**本次編寫計劃沒有重新執行產品測試**。先建立 `artifacts/repair/`；Node／pnpm／uv版本跟currentCI，稽核本地的24.19.0／11.25.0／0.12.23只作歷史記錄。任何命令缺prerequisite先記blocked，不降低strict或移除case。

**Repo root，安裝及已核對focused Node：**

```bash
pnpm install --frozen-lockfile
node --test --test-reporter=spec tests/neon-session.test.mjs tests/neon-production-config.test.mjs tests/neon-auth-boundary.test.mjs tests/neon-security-proxy.test.mjs tests/audit-research-intent.test.mjs tests/audit-bulk-manifests.test.mjs tests/audit-draft-grounding.test.mjs tests/audit-job-query.test.mjs
```

**`services/api`，focused身份／workspace（owned DB）：**

```bash
uv sync --frozen --group dev
BUYEROS_STRICT_INTEGRATION=1 uv run --frozen pytest tests/test_identity_migration_db.py tests/test_identity_resolver_db.py tests/test_identity_linking_db.py tests/test_workspace_listing_db.py tests/test_workspace_directory_function_db.py tests/test_neon_cutover_db.py tests/test_neon_security_db.py -q --junitxml=../../artifacts/repair/auth-workspace.xml
uv run --frozen pytest tests/test_provider_registry.py tests/test_neon_verifier.py tests/test_live_search_adapter.py tests/test_live_model_adapter.py tests/test_live_contact_adapter.py tests/test_delivery_protocol.py -q --junitxml=../../artifacts/repair/provider-contracts.xml
uv run --frozen python ../../scripts/generate-operation-routes.py --check
```

**新增schema檔案後，`services/api`：**

```bash
BUYEROS_STRICT_INTEGRATION=1 uv run --frozen pytest tests/test_schema_readiness_db.py -q --junitxml=../../artifacts/repair/schema-readiness.xml
```

**Repo root，built fixture discovery與execution：**

```bash
pnpm exec playwright test --config playwright.audit-fixes.config.ts --list --reporter=json > artifacts/repair/ui-discovery.json
pnpm exec playwright test --config playwright.audit-fixes.config.ts
pnpm exec playwright test --config playwright.neon-runtime-built.config.ts --list --reporter=json > artifacts/repair/neon-built-discovery.json
pnpm exec playwright test --config playwright.neon-runtime-built.config.ts
```

對新增real configs同樣先 `--list` 再執行，明確目標／帳戶／是否允許write；不能把上述名含production的synthetic specs當真實Neon。使用既有`check-required-tests.py`核對discovery/JUnit，新增required檔案時同步更新expected集合，0 tests拒絕。

**最後一批才跑全量（各自working directory）：**API用 `BUYEROS_STRICT_INTEGRATION=1 uv run --frozen pytest -q --junitxml=../../artifacts/repair/api-full.xml`；worker在`services/worker`先`uv sync --frozen`再同樣執行pytest輸出`worker-full.xml`。依currentCI跑lint、build、Cloudflare及其他requiredjobs；不要因平台目前未用就私自刪requiredgate。Focused足以驗小修時不反覆重跑全量。

**每個case evidence最少欄位：**case ID、finding/task ID、source SHA、環境、執行時間／actor role、前置條件、實際步驟、expected／actual、result、request/run/intent/revision references、log／JUnit／readbackhash、cleanup結果。遮罩PII、secret、DSN；raw證據放受控位置。

**狀態規則：**`planned → implemented → tested → deployed → activated → live_accepted` 分欄，不當單一線性boolean；不適用填理由。runtime沒看到／尚未取得account填blocked；clipboards等沒有充分證據填inconclusive；fixture只能關fixture驗收。更新 `current_*` 欄位，保留baseline。

## 23. 工作量與交接範圍

| 批次 | 工作量估算 | 說明 |
|---|---|---|
| G0診斷／修復／33a | 約1.75–4人日 | 31為0.25–0.5、32為0.5–1.5、33為1–2；取決於真實target／head |
| Neon剩餘gap及GN | 約3–7人日 | 大量code已存在；不重套舊「從零開發」估算 |
| providers／workflow／bulk | 約5–10人日 | 由selection與live gaps決定；真實contract缺失會延長 |
| quality／performance／UAT／GA | 約3–6人日 | 不含真人、帳戶或觀測等待 |
| native send／GS | 約3–6人日 | 沿用現有ledger／runner；sender與recipient授權另計 |

這是初步人日範圍，不能當日曆承諾或把各舊task估算直接相加。C61-01完成後以差異清單重新估算；先交付G0，再按各gate回報。

**每批給使用者的回報只需：**完成甚麼及使用者現在可以做甚麼；commit／PR與測試證據；仍blocked的確切條件；下一批；是否需要某個已準備好的外部變更授權。沒有新證據不能宣稱已修好全流程。

## 24. 完成定義與本計劃自查

- F01–F24都有對應任務；F21保留unknown，F22保留僅版本差距closed的範圍。
- C61-01…33完整沿用；28／33分期有明示、14在29後、30在14／20／29後；沒有循環依賴。
- 148個原case ID保留在附帶traceability；N11的工作區／Neon／同鏈／native／performance／quality／promotion缺口有明確gate。case inventory不是148個新pass。
- 既有檔案先復用，新增檔案明示；每個實作批次有可檢查步驟、focused驗證、證據及回退邊界。
- G0、GN、GA、GS分開接受；只有GS通過才可宣稱「全研究及站內外展可完成」。
- 本計劃完成的是文件與交接，不包含product code修改、schema／auth／provider切換、付費、寄送或重新live測試。
