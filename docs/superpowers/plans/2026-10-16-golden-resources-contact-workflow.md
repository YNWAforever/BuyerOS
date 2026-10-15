# Golden Resources Lead Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Golden Resources 24 家公司逐步整理為 8 家優先公司、6 家具名採購人、4 家直接商務渠道及 4 份聯絡準備稿，保存原生證據與恢復意圖，並以每月共用 US$10 政策控制新增服務費。

**Architecture:** 新的證據、複核、工作狀態及聯絡準備稿獨立於研究 Evidence、fit 與正式寄送審批；共用後端投影計數。保存採伺服器持久意圖與現有 idempotency／If-Match；預算投影沿用既有工作區鎖、預留及結算，補上外部費用對帳，不接供應商。

**Tech Stack:** 現有 React／TypeScript、FastAPI／Pydantic、SQLAlchemy／Alembic、PostgreSQL RLS、pytest、Node test runner、Playwright；不新增產品依賴或修改 lockfile。

**Spec:** `docs/superpowers/specs/2026-10-15-golden-resources-contact-workflow-design.md`，使用者已核准，並明確採用人物／採購職責 30 日、渠道歸屬 7 日複核期限。

**Date / status:** 2026-10-16，Asia/Hong_Kong；供實作計畫審閱，尚未開始產品實作。

**Source basis:** 程式基準 `c42c9f40f5f99c5810980bb72885548335d1f1bb`；已審閱規格原提交 `50f2e1b2c422de1f201271c06bba621764fde33a`。不把這些本機來源當成最新 main 或正式環境證明。

**Execution preference:** 建議沿用 Native，由主代理在同一工作階段逐項執行，使用 `superpowers:executing-plans`。本計畫編寫不派出 subagent；實作計畫審閱完成前不執行任何產品步驟。

## Global Constraints

- 付費研究、聯絡資料 enrichment、寄信維持停用；包括免費 enrichment、測試郵件、外部模型、CRM 發送及自動跟進。
- 24 家公司、8 家優先、6 家具名採購人、4 家直接渠道、4 份準備稿按不同公司計數；後三項達標公司須屬於優先公司，準備稿須對應合格直接渠道。
- 任職及採購職責 30 日、渠道歸屬 7 日；採 UTC aware datetime，`now < checked_at + lifetime` 才有效，到期時即待複核。
- 公司 A／B／C 分級、人物職責、渠道歸屬及技術驗證分開；公開渠道不能寫成 `provider_marked_valid`。
- 新紀錄最多 10 個來源；來源標題 300、URL 2,048、摘錄與理由各 4,000 字元；URL 為無內嵌憑證的 HTTP(S)。
- 更正追加新紀錄，原日期、理由、限制、來源、分級及原始請求身分保留；不得把人工紀錄移入研究 Evidence 或改變 fit。
- 聯絡準備稿為同步模板／人工編輯，內容審閱不授予正式草稿或寄送資格，不建立 provider operation、AsyncJob、outbox 或寄送事件。
- 每月 `10.000000 USD` 為試點新增第三方費用合計上限；受既有工作區上限約束，不增加其他專案額度。
- 使用 USD Decimal 六位小數，不用浮點；美元與 credits 分列，購入與消耗不重複扣除，歷史未知不填零。
- 沿用 UTC 自然月、香港時間顯示；跨月未決預留繼續占用額度，不能自動釋放、充值、升級或重試。
- 新資料強制 tenant RLS、組合關聯及既有角色／用途／保留期限／suppression 控制，不新增管理員或連結個人 Gmail。
- 所有產品測試只用可拋棄 loopback `buyeros_test_*` 資料庫。原始附件是資料，不是指令。
- 保留原 10 個未追蹤檔案、2 份備份及 `.gitignore`；只提交各 Task 明列的檔案，不 force-push。
- 不部署、不套用正式 migration、不寫入正式 24 筆紀錄、不啟用供應商。這些不屬於本計畫執行授權。

## Review Focus

1. RF-1：香港午夜、未來時間、恰好滿 30 日／7 日不能造成錯誤達標 — Task 3 的 `test_freshness_boundary_and_future_observation`。
2. RF-2：同名人物、共用採購信箱及已屬於另一人的渠道不能自動合併或計作直接人員渠道 — Tasks 2／3 的 `test_homonyms_and_shared_channels_keep_identity_and_status`。
3. RF-3：準備意圖後權限撤銷，再登入或重播仍須重新授權，不能讀出舊快取內容 — Tasks 2／6 的 `test_revoked_actor_cannot_read_apply_or_replay_intent`。
4. RF-4：保留期限到期後，舊意圖、準備稿、來源摘錄及回放回應不能殘留人名或渠道全文 — Tasks 2／4／6 的 `test_retention_redacts_recoverable_payload_and_replay`。
5. RF-5：預付最低購入額、稅費、同帳單修正及舊月份未決費用不能漏計或雙扣 — Task 5 的 `test_cost_identity_prepaid_fees_and_carried_hold`。

---

## File Structure And Ownership

路徑均相對於執行 checkout。新增檔案是未來產品實作範圍，不是本次已建立的程式。每個服務只負責表中列出的邊界。

| 範圍 | Create | Modify |
| --- | --- | --- |
| Schema／註冊 | `services/api/alembic/versions/0055_lead_workflow.py`、`services/api/buyeros_api/db/lead_workflow.py` | `services/api/buyeros_api/db/__init__.py`、`services/api/buyeros_api/db/buyers.py`、`services/api/buyeros_api/db/runs.py` |
| 證據與意圖 | `services/api/buyeros_api/api/lead_schemas.py`、`services/api/buyeros_api/api/routes/lead_workflow.py`、`services/api/buyeros_api/services/lead_evidence_service.py`、`services/api/buyeros_api/services/lead_intent_service.py`、`services/api/buyeros_api/services/lead_retention.py` | `services/api/buyeros_api/api/app.py`、`services/api/buyeros_api/api/deps.py`、`services/api/buyeros_api/services/retention.py` |
| 判定與進度 | `services/api/buyeros_api/services/lead_quality.py`、`services/api/buyeros_api/services/lead_review_service.py`、`services/api/buyeros_api/services/lead_progress_service.py` | 上述新路由／schemas |
| 準備稿 | `services/api/buyeros_api/services/lead_preparation_service.py`、`services/api/buyeros_api/api/routes/lead_preparations.py` | 新意圖 dispatcher、`api/app.py` |
| 預算 | `services/api/buyeros_api/services/pilot_budget_service.py`、`services/api/buyeros_api/api/routes/pilot_budgets.py` | `services/api/buyeros_api/services/budget_service.py`、新意圖 dispatcher、`api/app.py` |
| 契約 C | 無新增來源契約檔 | `docs/buyeros/contracts/openapi.proposed.yaml`、生成的 `services/generated/buyeros-api.ts`、`services/generated/operation-routes.ts` |
| Client | `services/live/lead-workflow.ts`、`services/live/lead-intents.ts`、`services/live/lead-preparations.ts`、`services/live/pilot-budgets.ts` | 不修改全域 `services/live/action-intent.ts` 的其他消費者 |
| 買家 UI | `features/live/lead-workflow/evidence-panel.tsx`、`case-panel.tsx` | `features/live/buyer-detail.tsx`、`buyer-results.tsx` |
| 準備稿 UI | `features/live/lead-workflow/preparations-panel.tsx` | `features/live/workspace-picker.tsx` |
| 進度／預算 UI | `features/live/lead-workflow/progress-panel.tsx`、`budget-panel.tsx` | `features/live/workspace-picker.tsx`、`features/live/locale.ts` |
| 測試共用 | `services/api/tests/lead_fixtures.py`、`services/api/tools/seed_lead_workflow_fixture.py`、`playwright.lead-workflow.config.ts` | `services/api/tools/serve_e2e_fixture.py` |
| 後端測試 | `services/api/tests/test_lead_workflow_migration_db.py`、`test_lead_evidence_db.py`、`test_lead_intents_db.py`、`test_lead_quality.py`、`test_lead_progress_db.py`、`test_lead_preparation_db.py`、`test_pilot_budget_db.py`、`test_lead_contract.py` | Appendix A 的當前 head 斷言及相關既有回歸測試 |
| Client／UI 測試 | `tests/lead-intents.test.mjs`、`tests/e2e/lead-evidence.spec.ts`、`lead-preparations.spec.ts`、`lead-workflow.spec.ts`、`pilot-budget.spec.ts` | 不改既有 browser suite 的 testMatch 或期望數量來隱藏測試 |
| CI／交付 | `docs/buyeros/golden-resources-lead-workflow.md`、`tests/test_lead_workflow_ci_registration.py` | `.github/workflows/buyeros-ci.yml`，只加入新驗收及有證據的新增 inventory |

同一列 Create 中省略目錄的檔名，沿用該列前一個完整路徑的目錄。具體六頁掛載集中於 `features/live/workspace-picker.tsx`，不把所有新 UI 加到既有正式草稿編輯器。

### 通用開發與驗收命令

後端命令的 cwd 為 `services/api`，前端／Node／Playwright 為 repo root。使用已安裝的 frozen 依賴；缺依賴時只依既有 lockfile 補齊，不升級套件。設定 `BUYEROS_STRICT_INTEGRATION=1`，讓缺少可拋棄資料庫成為失敗，不能算 skip 通過。

每個新增 API 的 Task 同時更新契約 C、`api/deps.py` 角色與 `api/app.py` 註冊；不先宣告尚未完成的端點。生成命令：

```powershell
node scripts/generate-api-types.mjs --write
uv run --frozen --project services/api python scripts/generate-operation-routes.py
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
```

以上 generator 命令在 root 執行。新路由的寫入 precondition 使用既有 transport carrier／middleware，不另設繞過 If-Match 的瀏覽器寫入路徑。

## Shared Interfaces And Contracts

### S1. 資料模型及意圖

新增模型均在 `db/lead_workflow.py` 註冊：

- `LeadCaseState`：每個工作區／專案／買家一筆，保存優先、理由、下一步、日期及 version；owner 從既有 `ProjectBuyer.owner_user_id` 讀取，指派仍走既有 `assignBuyerOwners` 權限。
- `LeadObservation`：不可覆寫的 claim、stance、subject 參照、查閱時間、摘要 hash、supersedes 及 recorded_by；公司來源紀錄保持原表。
- `LeadPrivatePayload`：來源 URL／摘錄等可能含個人資料的內容；獨立於不可覆寫 metadata，只有受控保留期限處理能清除內容。
- `LeadReview`、`LeadReviewEvidence`：人工判定、確切觀察關聯、理由、前一版及 context hash。
- `LeadPreparation`、`LeadPreparationRevision`、`LeadPreparationEvidence`、`LeadPreparationContentReview`：準備稿身分、修訂、組合外鍵引用及內容審閱，獨立於 `OutreachDraft`。
- `LeadActionIntent`：actor、action、scope、原 payload／hash、原 submission key、原 precondition、`prepared|applied|cancelled`、canonical resource 參照及 acknowledgement；不存供應商操作。
- `PilotBudgetPolicy`、`PilotCostEvent`、`PilotCreditObservation`、`PilotReconciliation`：版本化政策、不可覆寫費用事件、credits 觀察及人工對帳證據。

`api/lead_schemas.py` 定義：

- `LeadScope(workspace_id, project_id, buyer_id?, company_id?, actor_id, membership_version, roles)`，由伺服器解析，不接受 client 指定 actor／roles。
- `LeadSourceInput(title, url, excerpt, source_kind, published_on?, published_precision?)`；`source_kind=official|professional|other`，只有人工聲稱 official 仍不足以自動通過複核。
- `LeadObservationInput(claim, stance, person?, channel?, checked_at, sources, rationale, limitations?, supersedes_id?)`；`claim=employment|procurement_scope|channel_ownership`，`stance=supports|refutes|uncertain`。
- 新 person 可由 `{full_name, role}` 明確建立或用既有 `person_id`；channel 用既有 `contact_id` 或 `{type, value, person_id?}` 明確建立。兩種身分輸入互斥；不能接受 validity／verified 等 client 欄位。
- `LeadReviewInput(person_id, contact_id?, employment, procurement_scope, channel_ownership, observation_ids, conflict_resolution?, rationale, previous_review_id?)`；各判定為 `accepted|uncertain|rejected`，後端計算實際 freshness 與資格。
- `LeadCaseUpdate(priority, priority_reason, next_action, due_on?)`；owner 不在這個輸入。
- `LeadPreparationInput(person_id?, contact_id?, subject, body, language, product_fact_refs, observation_ids, lead_review_id?, previous_revision_id?)`；`language=en|zh-HK`，subject 上限 300、body 上限 12,000 字元。
- `LeadIntentInput(action, buyer_id?, target_id?, expected_version?, payload)`，payload 為 action 的嚴格 discriminated union；另有 `PilotCostInput`、`PilotCreditInput`、`PilotReconcileInput`。
- 輸出 DTO：`LeadObservationRecord`、`LeadEvidencePage`、`LeadReviewRecord`、`LeadCaseView`、`LeadProgressPage`、`LeadPreparationView`、`LeadPreparationPage`、`PilotBudgetView`、`LeadIntentView`、`LeadIntentReceipt`；均含 scope、version／hash、必要時間及明確 unavailable／unknown 狀態。兩個 Page 型別均為 items／offset／limit／total，items 分別為 observation 或 preparation records。

`PilotCostInput` 固定帶 `economic_charge_key`、`period_start`、`state`（committed／settled／unknown／corrected）、`reason`、`source_refs`，可有 `native_operation_id`、`previous_event_id`、原幣金額／幣別、`usd_amount`、`usd_upper_bound`、`fx_basis`；未知金額為 null，不填零。`PilotCreditInput` 帶 provider、unit、period_start／end、used／remaining、as_of、source_refs。`PilotReconcileInput` 帶 period_start、ledger_version／hash、coverage_start／end、shared_usage_known、reason、source_refs。source_refs 為有權限的私有 document_id 或無憑證公開 URL，不能只保存沒有依據的對帳旗標。

`LeadIntentReceipt` 只帶 `intent_id`、`resource_type`、`resource_id`、`resource_version`、`state` 及 `redacted`，不快取個人資料全文；client 以目前權限讀取該資源。`LeadCaseView` 固定包含 scope、version、priority／priority_reason、owner_user_id、next_action／due_on、selected_person_id／selected_contact_id、quality（LeadQuality）、observations／reviews 參照。

尚未建立 LeadCaseState 時，GET 回傳預設 version=1、`state_exists=false`，不寫資料。第一個實際 case write 在鎖定既有 ProjectBuyer 後建立初始 state，再以原 If-Match=1 變更成 version=2；所有影響 case 的觀察／複核寫入使用同一鎖與版本遞增，並行更新不能覆蓋。準備稿修訂仍使用它自己的版本。

共用讀取型別固定為：

- `LeadFilters(priority?: bool, stage?: str, owner_user_id?: UUID, due_before?: date, qualifies_for?: str)`；stage 僅接受 `find_person|verify_employment|verify_procurement|verify_channel|refresh_evidence|review_preparation|complete`，qualifies_for 僅接受 `company_card|priority_company|qualified_person|direct_channel|reviewed_preparation`，未知欄位或值拒絕。
- `LeadQuality(employment_current: bool, procurement_current: bool, channel_ownership_current: bool, qualified_person: bool, direct_channel: bool, needs_review: bool, blockers: list[str], expires_at: datetime | None)`。
- `LeadProgressPage(items: list[LeadCaseView], offset: int, limit: int, total: int, metrics: LeadMetrics, as_of: datetime, context_hash: str)`；`LeadMetrics` 的五個整數欄位為 `company_cards`、`priority_companies`、`qualified_people_companies`、`direct_channel_companies`、`reviewed_preparation_companies`。
- `PilotBudgetView` 使用 `limit`、`settled_total`、`reserved_total`、`carried_reserved`、`external_unsettled`、`remaining`、`currency`、`period_start`、`period_end`、`reconciliation_status`、`activation`、`credits`、`version`、`as_of`。金額輸出為 decimal string，remaining 未知時為 null；carried_reserved 是 reserved_total 的子集，不能再扣一次。reconciliation_status 為 `unknown|reconciled|stale`，本次 activation 固定 `disabled`。

Action allowlist：`observation.append`、`lead.review`、`case.update`、`preparation.create`、`preparation.revise`、`preparation.review`、`preparation.archive`、`pilot.policy`、`cost.record`、`credits.record`、`budget.reconcile`。只註冊已完成的 handler。

### S2. HTTP 契約

以下 `B=/v1/workspaces/{workspace_id}/projects/{project_id}`。GET 清單預設 20、上限 100，回傳既有 envelope。所有寫入先準備意圖，前端不能跳過原意圖自行換 key。

| Method／path | operationId | 權限與輸出 |
| --- | --- | --- |
| GET `B/buyers/{buyer_id}/lead-evidence` | `listLeadEvidence` | 買家讀取角色；觀察與複核參照、有界分頁 |
| GET `B/buyers/{buyer_id}/lead-workflow` | `getLeadCase` | 買家讀取角色；`LeadCaseView` |
| GET `B/lead-workflow` | `getLeadWorkflow` | 買家讀取角色；同條件 items、total、distinct-company metrics、as_of |
| POST `B/lead-intents` | `prepareLeadIntent` | Idempotency-Key；依 action 重新檢查原操作角色；201 |
| GET `B/lead-intents` | `listLeadIntents` | 只列同 actor 目前仍有權限的 prepared 及尚未 acknowledgement 的 applied 意圖 |
| GET `B/lead-intents/{intent_id}` | `getLeadIntent` | 同 actor／scope，重新檢查權限與資料保留期限 |
| POST `B/lead-intents/{intent_id}/apply` | `applyLeadIntent` | 原 submission key；mutable action 需原 If-Match；200 receipt |
| POST `B/lead-intents/{intent_id}/acknowledgements` | `acknowledgeLeadIntent` | 只確認已讀 canonical receipt，不再次執行 domain write |
| POST `B/lead-intents/{intent_id}/cancel` | `cancelLeadIntent` | 只取消已確認未 apply 的 prepared；已 apply 回讀結果，不撤銷歷史 |
| GET `B/buyers/{buyer_id}/lead-preparations` | `listLeadPreparations` | 既有草稿讀取角色，有界分頁 |
| GET `B/lead-preparations/{preparation_id}` | `getLeadPreparation` | 同專案與資料政策；`LeadPreparationView` |
| GET `B/pilot-budget` | `getPilotBudget` | operator／reviewer／workspace_admin；只讀投影 |
| GET `B/pilot-cost-events` | `listPilotCostEvents` | workspace_admin；費用／credits／對帳歷史有界分頁 |

所有 intent 先驗證 active membership／action permission，再讀回 replay。`observation.append`、`lead.review`、`case.update` 沿用 updateBuyer；準備稿編輯沿用 editDraft，內容已審只准 reviewer／workspace_admin；預算 action 只准 workspace_admin。保留既有 owner 指派角色，不能借 case.update 擴權。

### S3. 保存意圖與狀態

`prepareLeadIntent` 在伺服器保存原 action／body／target／precondition，產生固定 submission key；同 actor 同一個尚未解決的 exact fingerprint 只有一個 active intent。初次 prepare 回應不明時，重新登入後先列出伺服器原意圖，不從瀏覽器儲存重建個人資料。

`applyLeadIntent` 從已保存內容執行一個 allowlisted local handler，domain write、idempotency canonical resource 及 applied 狀態同交易提交。回應遺失後，原 intent 顯示 applied 且未 acknowledgement，讀回原結果即可；不能再建立第二筆。版本衝突保留意圖供使用者讀回差異，另一次明確編輯才是新意圖。

所有 replay 依目前角色與資料保留狀態產生安全 readback，不把過期或已刪除的 personal payload 從歷史 response JSON 重新送出。

---

### Task 1: 追加式資料模型與 0055 migration

**Files:** Schema／註冊列；Create `services/api/tests/test_lead_workflow_migration_db.py`。Modify Appendix A 中實際針對「目前 head」的斷言。

**Interfaces:** Produces S1 的全部模型及 `0055_lead_workflow`，`down_revision=0054_buyer_source_checks`。只加入必要組合 unique／FK，不改既有 Person、ContactPoint 或 ProjectBuyer 的身分與業務語義。

- [ ] **Step 1: 寫 RED migration 測試。** `test_lead_workflow_schema_is_tenant_scoped_and_append_only` 斷言 14 個 S1 模型表、RLS／FORCE RLS、跨 workspace／project／company FK、必要索引及 journal SELECT／INSERT 無普通 UPDATE／DELETE。`test_0054_upgrade_preserves_original_source_checks_and_fences` 先建 0054 資料，升到 0055 後原始內容不變，search／model／contact 三個 fence 均為 true。

  代表性斷言（以下 code block 都是指定測試內的斷言片段）：

  ```python
  assert head == "0055_lead_workflow"
  assert source_checks_after == source_checks_before
  assert receipt_fences == (True, True, True)
  assert ordinary_journal_update_delete == (False, False)
  ```

- [ ] **Step 2: 執行 RED。** `uv run --frozen pytest tests/test_lead_workflow_migration_db.py -q`；預期因新 revision／表不存在失敗，不能因 Docker 或 skip 算 RED。
- [ ] **Step 3: 實作 migration 與模型。** 在 `db/__init__.py` 註冊；新關聯完整綁定 `(workspace,project,buyer,company)`，人物／渠道綁同 company。移植現有精確 schema receipt fence 到 0055；有資料時 downgrade 明確拒絕，不刪除資料換取 rollback 成功。所有 journal 敏感內容經 `LeadPrivatePayload`，其受控清除路徑在 Task 2 實作。
- [ ] **Step 4: 執行 GREEN。** 同上命令，再跑 `uv run --frozen pytest tests/test_buyer_source_checks_db.py tests/test_identity_migration_db.py tests/test_checkpoint_schema_privileges_db.py tests/test_schema_readiness_db.py -q`；全部通過、零 skip。保留 0054 歷史升級斷言；只把當前 head 期望更新為精確 0055。
- [ ] **Step 5: Commit。** 僅 stage 本 Task 模型、migration、測試及 Appendix A 的明列變更；`feat: add tenant-scoped lead workflow journal`。

### Task 2: 原生人物／渠道觀察與持久保存意圖

**Files:** 證據與意圖列、契約 C；Create `services/api/tests/lead_fixtures.py`、`test_lead_evidence_db.py`、`test_lead_intents_db.py`、`test_lead_contract.py`。

**Interfaces:** Consumes Task 1 models。`lead_fixtures.py` 提供 `lead_api`（TestClient＋既有 test principals）與 `lead_case`（同／異 tenant、company、角色及已保存來源），新測試顯式 import fixture。

Produces async functions：`resolve_lead_scope(session: AsyncSession, *, workspace_id: UUID, project_id: UUID, buyer_id: UUID | None, principal: Principal) -> LeadScope`；`append_observation(session: AsyncSession, *, scope: LeadScope, data: LeadObservationInput, now: datetime) -> LeadObservationRecord`；`prepare_intent(session: AsyncSession, *, scope: LeadScope, data: LeadIntentInput, key: str) -> LeadIntentView`；`apply_intent(session: AsyncSession, *, scope: LeadScope, intent_id: UUID, key: str, if_match: str | None, now: datetime) -> LeadIntentReceipt`。

同檔定義：`read_intent(session: AsyncSession, *, scope: LeadScope, intent_id: UUID, now: datetime) -> LeadIntentView`；`list_intents(session: AsyncSession, *, scope: LeadScope, offset: int, limit: int, now: datetime) -> dict`（items／offset／limit／total）；`acknowledge_intent(session: AsyncSession, *, scope: LeadScope, intent_id: UUID, key: str, now: datetime) -> LeadIntentView`；`cancel_intent(session: AsyncSession, *, scope: LeadScope, intent_id: UUID, key: str, now: datetime) -> LeadIntentView`。

- [ ] **Step 1: 寫 RED API／資料測試。** `test_observation_payload_scope_and_limits` 驗證 1／10／11 來源、4,000／4,001 摘錄、未知欄位、credential URL、未來 checked_at 及不一致 company。`test_homonyms_and_shared_channels_keep_identity_and_status` 驗證同名不合併，共用渠道不偷改 person_id，任何 client validity 欄位被拒絕。`test_intent_prepare_unknown_apply_unknown_and_exact_replay` 驗證兩次回應遺失都可回讀，只有一筆 domain record。加入 RF-3／RF-4 指定測試。

  ```python
  assert replay["resource_id"] == first_receipt["resource_id"]
  assert observation_count_after - observation_count_before == 1
  assert cross_company_response.status_code == 404
  assert revoked_replay.status_code == 403
  ```

- [ ] **Step 2: 執行 RED。** `uv run --frozen pytest tests/test_lead_evidence_db.py tests/test_lead_intents_db.py tests/test_lead_contract.py -q`；預期缺少新服務／端點／契約。
- [ ] **Step 3: 實作 S1／S2／S3 的觀察、scope、意圖與恢復。** handler 先只註冊 observation.append；建立 manual Person／ContactPoint 與第一筆觀察同交易，技術狀態保持 unverified_public。個人資料保存沿用既有 account_research／contact_research 用途及保留期限政策，缺少許可時明確阻擋，不自動記錄 permitted，也不要求開啟 enrichment。新增 `redact_lead_subject(session: AsyncSession, *, workspace_id: UUID, subject_type: str, subject_id: UUID, now: datetime) -> dict`，由既有 `retention.py` 的 contact／source 到期流程呼叫，並涵蓋尚未建立 ContactPoint 的 Person 到期。0055 的窄權限 redaction function 必須驗證 tenant、canonical subject 已到期及保留期限，不開放一般 journal UPDATE。稽核與 response 只保留安全身分／hash；加上 new routes、角色及契約 C。
- [ ] **Step 4: 執行 GREEN。** 同 RED 命令，加 `uv run --frozen pytest tests/test_retention_authorization_db.py tests/test_api_routes_contract.py -q`；零 fail／error／skip。測試直接證明被撤權 actor 不能利用 cached replay，且 redaction 不能清除另一 tenant 或未到期內容。
- [ ] **Step 5: Commit。** `feat: persist manual lead evidence and recoverable write intents`。

### Task 3: 30／7 日品質判定、人工複核與同條件進度

**Files:** 判定與進度列、契約 C；Create `services/api/tests/test_lead_quality.py`、`test_lead_progress_db.py`。

**Interfaces:** Consumes S1 DTO、Task 2 scope／journal。Produces `evaluate_lead_quality(*, observations: list[LeadObservationRecord], review: LeadReviewRecord | None, now: datetime) -> LeadQuality`（純函數）；async `append_lead_review(session: AsyncSession, *, scope: LeadScope, data: LeadReviewInput, expected_version: int, now: datetime) -> LeadReviewRecord`；async `update_lead_case(session: AsyncSession, *, scope: LeadScope, data: LeadCaseUpdate, expected_version: int) -> LeadCaseView`；async `get_lead_case(session: AsyncSession, *, scope: LeadScope, now: datetime) -> LeadCaseView`；async `get_lead_progress(session: AsyncSession, *, scope: LeadScope, filters: LeadFilters, offset: int, limit: int, now: datetime) -> LeadProgressPage`。

- [ ] **Step 1: 寫 RED 品質及進度測試。** RF-1 測試以同一 UTC instant 比較香港時間，`29d23:59:59`／`6d23:59:59` 有效，正好 30／7 日失效，未來觀察拒絕。`test_conflicting_new_evidence_requires_new_review` 驗證新反證使舊複核待重審。`test_progress_counts_distinct_priority_companies` 用 24 個 fixture company、8 個優先、6 個合格人、4 個直接渠道，加入重複人物、通用信箱及 2 家非優先公司，斷言仍為 `24/8/6/4`，非優先不計入達標。

  ```python
  assert at_30_days.qualified_person is False
  assert at_7_days.direct_channel is False
  assert [m.company_cards, m.priority_companies, m.qualified_people_companies, m.direct_channel_companies] == [24, 8, 6, 4]
  ```

- [ ] **Step 2: 執行 RED。** `uv run --frozen pytest tests/test_lead_quality.py tests/test_lead_progress_db.py -q`。
- [ ] **Step 3: 實作純判定及投影。** 任職／職責／渠道分開；至少一項官方來源支持任職或採購角色，所有必要事實有來源，通用管理職稱不夠。新增 lead.review／case.update handler；全專案彙總不以已分頁 rows 計 total，detail 與 list 使用同一 predicates／as_of，批次讀取依賴資料。stage 優先處理已核實資料的到期／衝突為 refresh_evidence，其次依序找人、核任職、核採購、核渠道、審內容，全部完成為 complete。overview 不帶 filters；結果頁套用卡片同一 qualifies_for，total 及該項 metric 必須一致，其他 metrics 亦在同一 filtered base 計算。優先資格一律檢查完整專案的優先身分。owner 仍走原指派操作。
- [ ] **Step 4: 執行 GREEN。** 同上，加 `uv run --frozen pytest tests/test_buyer_review_db.py tests/test_buyer_management_db.py -q`，確保新的工作狀態不改原 fit 或 HumanReview。
- [ ] **Step 5: Commit。** `feat: add evidence-based lead review and progress projection`。

### Task 4: 零外部呼叫的聯絡準備稿與內容審閱

**Files:** 準備稿列、契約 C；Create `services/api/tests/test_lead_preparation_db.py`；延伸 Task 2 的受控 redaction。

**Interfaces:** Consumes Tasks 2／3。Produces async `create_preparation(session: AsyncSession, *, scope: LeadScope, data: LeadPreparationInput, now: datetime) -> LeadPreparationView`；`revise_preparation(session: AsyncSession, *, scope: LeadScope, preparation_id: UUID, data: LeadPreparationInput, expected_version: int, now: datetime) -> LeadPreparationView`；`review_preparation(session: AsyncSession, *, scope: LeadScope, preparation_id: UUID, expected_version: int, revision_id: UUID, context_hash: str, reason: str, now: datetime) -> LeadPreparationView`。

另定義 async `get_preparation(session: AsyncSession, *, scope: LeadScope, preparation_id: UUID, now: datetime) -> LeadPreparationView`；`list_preparations(session: AsyncSession, *, scope: LeadScope, offset: int, limit: int, now: datetime) -> dict`（items／offset／limit／total）；`archive_preparation(session: AsyncSession, *, scope: LeadScope, preparation_id: UUID, expected_version: int, reason: str, now: datetime) -> LeadPreparationView`。

- [ ] **Step 1: 寫 RED。** `test_preparation_public_channel_is_not_formal_recipient` 斷言公開未技術驗證渠道可做準備稿，但不產生 OutreachDraft／正式收件人。`test_preparation_review_binds_revision_sources_and_product_facts` 驗證改正文、產品事實、人物、渠道、反證及時間到期均使舊審閱失效。`test_preparation_calls_no_provider_worker_or_delivery` 以 spy 計數全為 0，資料庫 provider／job／outbox 增量為 0；加入 RF-4 replay 清除檢查。

  ```python
  assert current_preparation.state == "needs_review"
  assert formal_draft_count_after == formal_draft_count_before
  assert (provider_calls, model_calls, worker_dispatches, send_calls) == (0, 0, 0, 0)
  ```

- [ ] **Step 2: 執行 RED。** `uv run --frozen pytest tests/test_lead_preparation_db.py -q`。
- [ ] **Step 3: 實作準備服務與 handlers。** 純模板只插入已選且仍有效的產品事實與來源；缺事實不生成供貨承諾。狀態 editing／review_requested／reviewed／needs_review／archived；內容審閱僅 reviewer／workspace_admin；讀取及 mutation 都算 current context。註冊 preparation.* handlers 與 S2 兩個讀取端點，不更改正式 draft_service 或 approval_service 的 eligible-recipient 條件。
- [ ] **Step 4: 執行 GREEN。** 同上，加 `uv run --frozen pytest tests/test_draft_approval_context_db.py tests/test_buyer_source_checks_db.py -q`；準備稿經複核仍無法使既有 delivery admission 通過。
- [ ] **Step 5: Commit。** `feat: add reviewed lead preparations without delivery eligibility`。

### Task 5: 共用 US$10、外部費用對帳與跨月預留

**Files:** 預算列、契約 C；Create `services/api/tests/test_pilot_budget_db.py`。不建立供應商 adapter、憑證或 runtime 啟用操作。

**Interfaces:** Consumes Task 1 policy／cost models 與既有 budget lock。Produces async `project_pilot_budget(session: AsyncSession, *, scope: LeadScope, now: datetime) -> PilotBudgetView`；`record_pilot_cost(session: AsyncSession, *, scope: LeadScope, data: PilotCostInput, expected_version: int, now: datetime) -> dict`（event_id／version）；`record_credit_observation(session: AsyncSession, *, scope: LeadScope, data: PilotCreditInput, expected_version: int, now: datetime) -> dict`（event_id／version）；`reconcile_pilot_budget(session: AsyncSession, *, scope: LeadScope, data: PilotReconcileInput, expected_version: int, now: datetime) -> PilotBudgetView`；`assert_pilot_admission(session: AsyncSession, *, workspace_id: UUID, project_id: UUID, operation_id: UUID, upper_bound: Decimal, now: datetime) -> None`。pilot.policy handler 在同檔設定上限並回傳 PilotBudgetView，不修改 BudgetAccount。

- [ ] **Step 1: 寫 RED。** RF-5 測試完整最低購入額／稅費入帳，預付消耗不雙扣，相同 economic_charge_key 的結算與修正取代原承諾且不重複加總。`test_unknown_history_is_not_zero_and_does_not_grant_budget` 驗證未對帳 `remaining=null` 且 provider disabled；policy=10 不提高現有預算。`test_atomic_pilot_cap_allows_only_one_of_two_040_requests` 用隔離 DB 模擬已占用 9.50，兩個不同 operation 各 0.40，最多一個成功。`test_utc_rollover_carries_unknown_hold` 驗證舊月份預留仍扣額度且保留原意圖。

  ```python
  assert unknown_budget.remaining is None
  assert successful_new_reservations == 1
  assert remaining_after_reservation == Decimal("0.100000")
  assert provider_calls == send_calls == 0
  ```

- [ ] **Step 2: 執行 RED。** `uv run --frozen pytest tests/test_pilot_budget_db.py -q`；不以真實付費呼叫來驗證預算。
- [ ] **Step 3: 實作投影及原子邊界。** 預設政策上限 10.000000，不能高於已核准值；未知、超額與 disable 狀態分開。GET 預算純讀取，不建立 policy、BudgetAccount 或 reservation；只有明確的管理員意圖可建立 policy。沿用 workspace budget lock，納入 settled、active/carried holds 及未被它們涵蓋的外部承諾。以 native operation ID／帳單 economic key 去重；credits 有自己單位與期間。`budget_service.reserve_operation` 在新增預留前呼叫 guard，只有已配置 pilot policy 的 project 受新規則影響，原 replay 不新建負債。外部實際超額費用仍可如實記錄並凍結，不隱藏帳單。註冊四個管理員 budget handlers 及 S2 budget reads，無自動充值或外部查詢。
- [ ] **Step 4: 執行 GREEN。** 同上，加 `uv run --frozen pytest tests/test_budget_atomicity_db.py tests/test_contact_job_migration.py -q`；worker 的 `tests/test_contact_uncertainty_db.py` 由 Task 10 在 worker cwd 的完整測試覆蓋，不混用兩個服務的測試路徑。
- [ ] **Step 5: Commit。** `feat: enforce shared pilot budget and auditable external costs`。

### Task 6: 型別化 client、跨重載恢復及隔離 browser fixture

**Files:** Client、測試共用列；Create `tests/lead-intents.test.mjs`。需要的 C 生成檔必須與實際 API 一致。

**Interfaces:** Consumes S2 generated operations。以下 client／session 型別均為 `LiveClient`／`SessionScope`，所有 DTO 由生成契約匯出。

- `loadLeadProgress(client, session, filters: LeadFilters, signal?: AbortSignal): Promise<LeadProgressPage>`；`loadLeadCase(client, session, buyerId: string, signal?: AbortSignal): Promise<LeadCaseView>`；`listLeadEvidence(client, session, buyerId: string, offset: number, limit: number, signal?: AbortSignal): Promise<LeadEvidencePage>`。LeadEvidencePage 為 S2 的 items／offset／limit／total，items 型別為 LeadObservationRecord。
- `prepareLeadIntent(client, session, input: LeadIntentInput): Promise<LeadIntentView>`；`applyLeadIntent(client, session, intent: LeadIntentView): Promise<LeadIntentReceipt>`；`recoverLeadIntents(client, session, signal?: AbortSignal): Promise<LeadIntentView[]>`；`getLeadIntent(client, session, intentId: string, signal?: AbortSignal): Promise<LeadIntentView>`；`acknowledgeLeadIntent(client, session, intentId: string): Promise<LeadIntentView>`；`cancelLeadIntent(client, session, intentId: string): Promise<LeadIntentView>`。ack／cancel 使用包含 intent ID 與動作的固定 idempotency key，不重用 domain apply 的 operation scope。
- `loadLeadPreparations(client, session, buyerId: string, offset: number, limit: number, signal?: AbortSignal): Promise<LeadPreparationPage>`；`getLeadPreparation(client, session, preparationId: string, signal?: AbortSignal): Promise<LeadPreparationView>`；`loadPilotBudget(client, session, signal?: AbortSignal): Promise<PilotBudgetView>`。LeadPreparationPage 為 S2 的 items／offset／limit／total，items 型別為 LeadPreparationView。

- [ ] **Step 1: 寫 RED client 測試。** `test_prepare_and_apply_unknown_recover_original_intent` 模擬兩個不同斷線位置，斷言原 key、hash、body、precondition 不變。`test_revoked_actor_cannot_read_apply_or_replay_intent` 與 `test_scope_transition_discards_old_result_without_changing_intent` 覆蓋 RF-3。`test_retention_redacts_recoverable_payload_and_replay` 覆蓋 RF-4，斷言 localStorage／sessionStorage／console 無人名、電郵或全文；過期 replay 只呈現安全 tombstone。

  ```javascript
  assert.equal(recovered.id, original.id);
  assert.equal(recovered.submission_key, original.submission_key);
  assert.deepEqual(persistentBrowserStorage, {});
  ```

- [ ] **Step 2: 執行 RED。** Root：`node --test tests/lead-intents.test.mjs`。
- [ ] **Step 3: 實作 clients 與 fixture。** 透過現有 createOperationClient 與 captured WriteContext，不修改全域 ActionIntent 的其他流程。進頁／重登入先列 unresolved server intents，已 apply 先讀回後 acknowledgement；沒有自動 apply。建立 `seed_lead_workflow_fixture(dsn: str) -> None`，只供既有 test-only fixture server 在 loopback buyeros_test_* DB、`BUYEROS_E2E_SEED_LEAD_WORKFLOW=1` 時使用，無正式 API seed 入口。新 Playwright config 沿用 buyer webServer，獨立 testMatch 四個新 spec、workers=1、JUnit 到 `test-results/lead-workflow.xml`。
- [ ] **Step 4: 執行 GREEN。** `node --test tests/lead-intents.test.mjs`、`node scripts/generate-api-types.mjs --check`、`pnpm exec tsc --noEmit`；無型別錯誤、無額外 browser storage。
- [ ] **Step 5: Commit。** `feat: add scoped lead clients and durable intent recovery`。

### Task 7: 買家證據／採購人／渠道 UI 與逐家公司恢復

**Files:** 買家 UI 列；Modify `features/live/locale.ts`；Create `tests/e2e/lead-evidence.spec.ts`。

**Interfaces:** Consumes Tasks 3／6 clients。Produces `LeadEvidencePanel({buyerId, locale, canEdit, onChanged})`、`LeadCasePanel({buyerId, locale, canEdit, canAssign, onChanged})`，workspace／project 由現有 session 取得；onChanged 只在同 scope canonical readback 後通知。

- [ ] **Step 1: 寫 RED browser 測試。** 固定五個 test：`company_person_channel_have_separate_statuses`、`unknown_save_survives_reload_and_company_switch`、`duplicate_apply_and_stale_edit_do_not_duplicate_or_overwrite`、`viewer_and_revoked_actor_cannot_edit_or_replay`、`source_checks_and_research_fit_remain_unchanged`。第二項在 server 已提交後截斷回應，重載後找回同 intent，換公司不誤寫；兩種語言以同一 test 的迴圈驗證，保持明確 inventory。

  ```typescript
  expect(secondReceipt.resource_id).toBe(firstReceipt.resource_id);
  expect(afterReload.observationCount).toBe(beforeSave.observationCount + 1);
  expect(afterReload.researchEvidenceIds).toEqual(beforeSave.researchEvidenceIds);
  ```

- [ ] **Step 2: 執行 RED。** `pnpm exec playwright test --config playwright.lead-workflow.config.ts tests/e2e/lead-evidence.spec.ts --workers=1`；預期缺新 UI，而不是放寬 timeout。
- [ ] **Step 3: 實作兩個小 panel 並掛入明細。** 顯示日期精度、來源摘錄、角色／渠道狀態與缺口；舊公司來源卡分開呈現。priority／next action 與 owner 指派分開權限；未解決保存有明確讀回／取消入口，清空表單只發生在已確認保存後。
- [ ] **Step 4: 執行 GREEN。** 同 RED 命令；另跑既有 `pnpm exec playwright test --config playwright.buyer.config.ts tests/e2e/buyer-source-checks.spec.ts --workers=1`，以及 `pnpm exec tsc --noEmit`。
- [ ] **Step 5: Commit。** `feat: add evidence-based buyer contact preparation panels`。

### Task 8: 聯絡準備稿 UI 與產品來源銜接

**Files:** 準備稿 UI 列；Modify `features/live/locale.ts`；Create `tests/e2e/lead-preparations.spec.ts`。

**Interfaces:** Consumes Task 4 API／Task 6 clients。Produces `LeadPreparationsPanel({locale, canEdit, canReview})`，掛在 `/app/outreach` 的獨立「聯絡準備稿」區，不改 LiveDraftEditor 的正式批准條件。

- [ ] **Step 1: 寫 RED。** 固定四個 browser test：`public_channel_preparation_is_reviewable_but_unsendable`、`material_change_or_expiry_invalidates_content_review`、`preparation_reload_restores_revision_and_original_intent`、`missing_product_fact_or_extraction_caveat_is_visible`。斷言來源回到原附件／頁碼，沒有來源的 MOQ／認證不出現在模板；無 send／export-to-sender 操作。

  ```typescript
  expect(preparation.state).toBe('reviewed');
  expect(formalDraftCountAfter).toBe(formalDraftCountBefore);
  expect(counters).toEqual({provider: 0, model: 0, worker: 0, send: 0});
  ```

- [ ] **Step 2: 執行 RED。** `pnpm exec playwright test --config playwright.lead-workflow.config.ts tests/e2e/lead-preparations.spec.ts --workers=1`。
- [ ] **Step 3: 實作 panel。** 展示確切文案與引用版本、reviewer 內容複核及待完成事項；支援編輯、歷史與封存。從既有產品資料及 offer document 讀取狀態，不重新解析簡報、不啟動 worker 或外部模型。所有寫入走持久意圖。
- [ ] **Step 4: 執行 GREEN。** 同上，`pnpm exec tsc --noEmit`；既有原生附件及買家匯入驗收留到 Task 10 同候選執行。
- [ ] **Step 5: Commit。** `feat: add cited lead preparation editor without sending`。

### Task 9: 六頁進度串接、研究工作清單與預算 UI

**Files:** 進度／預算 UI 列；Create `tests/e2e/lead-workflow.spec.ts`、`pilot-budget.spec.ts`。

**Interfaces:** Consumes Task 3 的同條件投影與 Task 5／6 預算 client。Produces `LeadProgressPanel({mode: 'overview'|'queue', locale, onNavigate})`、`PilotBudgetPanel({locale, isAdmin})`；同一 server filters 連到結果頁，不從前端切片重新計數。

- [ ] **Step 1: 寫 RED。** Workflow 固定四個 test：`six_pages_preserve_project_and_progress_after_reload`、`metrics_and_filtered_results_count_distinct_companies`、`read_failure_is_unavailable_not_zero`、`followup_due_date_never_starts_a_job`。Budget 固定四個 test：`monthly_policy_and_disabled_activation_are_separate`、`unknown_spend_and_shared_provider_usage_require_reconciliation`、`prepaid_settlement_and_correction_are_not_double_counted`、`utc_rollover_keeps_unknown_holds_and_local_display`。

  ```typescript
  expect(budget.limit).toBe('10.000000');
  expect(budget.activation).toBe('disabled');
  expect(unreconciledBudget.remaining).toBeNull();
  expect(filteredResults.total).toBe(overview.metrics.direct_channel_companies);
  ```

- [ ] **Step 2: 執行 RED。** `pnpm exec playwright test --config playwright.lead-workflow.config.ts tests/e2e/lead-workflow.spec.ts tests/e2e/pilot-budget.spec.ts --workers=1`。
- [ ] **Step 3: 實作掛載。** `/app` 加 overview；`/app/operations` 加人工查核 queue；`/app/settings` 加專案預算投影及管理員對帳。沿用既有產品頁、買家結果及準備稿入口；超期、衝突及未授權都顯示具體下一步。預算尚未保存與歷史未對帳不能默認已花零；設定不得開啟研究／enrichment／寄信。中英文文案同義。
- [ ] **Step 4: 執行 GREEN。** 同上，加 `pnpm exec tsc --noEmit`、`pnpm lint`、`pnpm build`；不以 fixture 登入結果宣稱公司 Google 帳戶驗收完成。
- [ ] **Step 5: Commit。** `feat: connect lead workflow progress and pilot budget across pages`。

### Task 10: 同候選回歸、CI 註冊與待發布交付

**Files:** CI／交付列；必要的新增 test inventory 登記。其他產品檔案只有新失敗提供證據時才修改。

**Interfaces:** Consumes Tasks 1–9。Produces source SHA／完整 discovery／JUnit／build／停用控制的交付紀錄及 `docs/buyeros/golden-resources-lead-workflow.md`。不是正式發布或 24 家實際達標紀錄。

- [ ] **Step 1: 加入必須失敗的 CI registration 測試。** 在 `tests/test_lead_workflow_ci_registration.py`（Create）檢查 CI 包含新的 Node client suite、17 個新 browser test 的 discovery／execution／JUnit guard，及原檔案中定義的五項 source-check browser test 也被實際執行；缺其中一段、零 inventory 或 skip 均不通過。Root：`python -m unittest discover -s tests -p test_lead_workflow_ci_registration.py -v` 預期 RED。

  ```python
  assert new_browser_inventory == {"lead-evidence.spec.ts": 5, "lead-preparations.spec.ts": 4, "lead-workflow.spec.ts": 4, "pilot-budget.spec.ts": 4}
  assert source_check_inventory == 5
  assert executed_ids == discovered_ids
  assert failed == errors == skipped == 0
  ```

- [ ] **Step 2: 註冊新驗收並保留原全部閘門。** 在現有 frontend job 加 Node client；現有 browser job 加獨立 lead config 的 17 tests（5＋4＋4＋4）與 source-check 五項，保留原 timeout、PG16 preload、原 job、原 suite、required checks。API／worker full discovery 的期望數量只能按保留原 IDs 加新 IDs 的清單增加，不得刪原測試、改成 `>=`、忽略 skips 或以較小 inventory 替代。
- [ ] **Step 3: 執行完整同候選驗收。** API cwd：`uv run --frozen pytest tests --collect-only -q` 後執行 `uv run --frozen pytest tests -q --junitxml=artifacts/lead-workflow-api.xml`。Worker cwd：相同命令、輸出 `artifacts/lead-workflow-worker.xml`。Root：Node client、API types／operation routes check、`pnpm exec tsc --noEmit`、`pnpm lint`、`pnpm build`、新 17 項 browser suite、既有 source checks、buyer import、native attachments 及正式草稿回歸。保留 discovery／JUnit 並用現有 `scripts/check-required-tests.py` 驗證原生 IDs、無缺項／重複／skip；這是預定執行，不能先填通過。
- [ ] **Step 4: 逐項核對 GR-01–GR-20 及 RF-1–RF-5。** 讀回 provider／model／worker／delivery counters 及相關資料表增量為零。文件記錄 exact SHA、驗收層級、未完成的真實公司資料與發布門檻，核對原始 24 家／57 個連結保留，不觸發正式保存。失敗先保留 evidence，再修復並對同一新 SHA 重跑受影響驗收。
- [ ] **Step 5: Commit 及交付審閱。** `test: register and verify the native lead workflow`。之後如需 PR，先確認既有推送／PR 授權範圍；任何建立的 PR 都要 attach。確認遠端 exact-head required CI 全部通過才可稱 CI 通過；本計畫不 merge、dispatch release、部署或寫入正式資料。

Task 10 的新 browser 原生驗收命令（root；只是計畫，現在不執行）：

```powershell
New-Item -ItemType Directory -Path artifacts/lead-workflow -Force
pnpm exec playwright test --config playwright.lead-workflow.config.ts --list --reporter=json > artifacts/lead-workflow/discovery.json
python scripts/check-required-tests.py --playwright-discovery artifacts/lead-workflow/discovery.json --expected-count 17 --expected-file lead-evidence.spec.ts --expected-file lead-preparations.spec.ts --expected-file lead-workflow.spec.ts --expected-file pilot-budget.spec.ts --discovery-only
pnpm exec playwright test --config playwright.lead-workflow.config.ts --workers=1
python scripts/check-required-tests.py --playwright-discovery artifacts/lead-workflow/discovery.json --expected-count 17 --expected-file lead-evidence.spec.ts --expected-file lead-preparations.spec.ts --expected-file lead-workflow.spec.ts --expected-file pilot-budget.spec.ts --junit test-results/lead-workflow.xml
```

舊 source-check、buyer-import、native-attachments 分別用原 config 做同一套 discovery → execution → JUnit 驗證，期望為 5／4／4；保留各自報告，不把新測試數量併入舊分母。

## Appendix A: 當前 Schema Head 斷言清單

基準中下列檔案有 `0054_buyer_source_checks` 字串。Task 1 逐處區分「當前 head」與「歷史 fixture／receipt」：只更新前者至精確 `0055_lead_workflow`，不做全庫搜尋取代，不降低歷史 provenance 斷言。

`services/api/tests/`：

```text
cutover_fixtures.py
test_admin_operations_db.py
test_backup_restore_t28.py
test_budget_atomicity_db.py
test_bulk_jobs_db.py
test_bulk_manifest_db.py
test_buyer_management_db.py
test_buyer_source_checks_db.py
test_checkpoint_schema_privileges_db.py
test_cloudflare_migration_db.py
test_cloudflare_recovery_boundaries_db.py
test_contact_job_migration.py
test_contact_quote_migration.py
test_delivery_admission_db.py
test_delivery_ledger_db.py
test_delivery_numeric_contract_db.py
test_document_upload_schema_db.py
test_draft_approval_migration.py
test_draft_integrity_migration.py
test_export_migration.py
test_identity_migration_db.py
test_outcome_migration.py
test_policy_lifecycle_db.py
test_private_storage_migration.py
test_project_constraints_db.py
test_release_binding.py
test_release_binding_db.py
test_research_checkpoint_migration.py
test_retention_authorization_db.py
test_schema_readiness_db.py
test_sender_identity_migration.py
```

另有 `tests/e2e/fixtures/c61-owned-readback.py` 的當前 owned schema 讀回。保留獨立 0054 upgrade fixture，確認新 migration 前後原來源紀錄內容一致。migration 編號若在執行時已被其他已確認來源占用，先對照最新來源並修訂此計畫，不重寫既有 migration 或硬套舊 schema contract。

## Spec Coverage And Self-Review

| 規格／驗收 | 負責 Task |
| --- | --- |
| 目的、範圍、停用、資料保留及發布邊界 | Global Constraints；Tasks 1／2／10 |
| 六頁流程、24／8／6／4、共同計數 | Tasks 3／7／8／9 |
| 證據品質、來源限制、30／7 日、衝突及歷史 | Tasks 1／2／3／7 |
| 資料契約、RLS、角色、原請求恢復 | Tasks 1／2／6／7 |
| 準備稿、引用、內容複核、正式資格分離 | Tasks 4／8 |
| US$10、費用去重、未知、credits、跨月預留 | Tasks 5／9 |
| 原始 24 家／57 來源及發布邊界 | Tasks 1／7／10 |
| GR-01／02／03／04／18 | Tasks 2／6／7／9 |
| GR-05／06／08／09 | Tasks 3／4／7／8／9 |
| GR-07／10／11／12 | Tasks 2／4／8／10 |
| GR-13／14／15／16 | Tasks 5／9 |
| GR-17／19／20 | Tasks 1／7／8／10 |
| RF-1／2／3／4／5 | Tasks 3；2／3；2／6；2／4／6；5 |

自審須在提交前完成：規格每節有負責 Task；跨 Task 型別／函式／action／operationId 一致；沒有只寫「加適當測試」的空步驟；每 Task 都有 RED、實作、GREEN 與獨立提交；所有成本測試與 browser fixture 都不呼叫真實供應商。

## Execution Handoff

請使用者審閱這份計畫。建議沿用 Native；所有 Task 完成後再作整體檢查，保留當時技能要求的程式審閱，但不因此變更遠端 PR reviewer 政策。規格與計畫核准不構成正式部署、migration、live seeding 或外部服務啟用授權。

計畫審閱確認後，才使用 `superpowers:executing-plans` 執行。這份文件只有實作步驟與預期驗收，沒有聲稱產品功能、CI 或 Golden Resources 真實採購人名單已完成。
