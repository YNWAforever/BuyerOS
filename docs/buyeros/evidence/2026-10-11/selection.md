# October 11 selection — retained audit current fields

All 33 parents remain open until their full acceptance contracts pass. Existing source is reused; no Neon/provider/bulk/delivery rewrite. F21 historical unknown; F23 distinct missing relation; F22 only audit-version gap closed. G0 does not require paid providers.

| ID | Decision | Existing path / evidence | Remaining condition |
|---|---|---|---|
| C61-01 | modify | TASKS.json; docs/buyeros/CURRENT_STATUS.md; .github/workflows/buyeros-ci.yml @ cbbe0e93 | 本次 SHA／PR／alias 已核對；需把版本資料寫回 authoritative release 文件。 |
| C61-02 | reuse | features/live/workspace-picker.tsx; features/live/settings.tsx; features/live/operations.tsx @ cbbe0e93 | PR12 已合併並部署，hosted main CI 通過；正式 user acceptance 仍受阻。 |
| C61-03 | acceptance-only | features/live/workspace-picker.tsx; features/live/settings.tsx; services/api/buyeros_api/api/deps.py @ cbbe0e93 | 員工 reconciliation source 已存在；F23 解決後讀回真實 canonical UUID／membership。 |
| C61-04 | blocked | docs/buyeros/incidents/2026-10-03-workspace-500.md; services/api/buyeros_api/api/errors.py; services/api/buyeros_api/api/deps.py @ cbbe0e93 | 本次新 42P01 已取得 request-correlated 證據；Oct2 舊根因仍未知。 |
| C61-05 | blocked | docs/buyeros/incidents/2026-10-03-workspace-500.md @ cbbe0e93 | 保留針對舊 F21 的根因調查；新 F23 用 C61-31/32 處理。 |
| C61-06 | acceptance-only | services/api/buyeros_api/api/routes/workspaces.py; services/api/buyeros_api/api/deps.py; services/api/buyeros_api/db/models.py @ cbbe0e93 | 0038 有界 directory 已實作；production schema／成功查詢驗收受阻。 |
| C61-07 | acceptance-only | package.json; pnpm-lock.yaml; playwright.neon-runtime-built.config.ts @ cbbe0e93 | ADR及 pinned Neon SDK 已存在；真實 target branch/session/provider acceptance 未完成。 |
| C61-08 | acceptance-only | package.json; pnpm-lock.yaml; services/api/buyeros_api/settings.py @ cbbe0e93 | server/config/route boundary 已實作，本次 Node tests 覆蓋；尚未 live activation。 |
| C61-09 | acceptance-only | services/api/buyeros_api/db/models.py; services/api/buyeros_api/api/deps.py; services/api/buyeros_api/api/routes/workspaces.py @ cbbe0e93 | 0039 identity mapping 已實作，但 production resolver 所需 relation 缺失。 |
| C61-10 | acceptance-only | services/api/buyeros_api/api/auth.py; services/api/buyeros_api/api/verifier.py; services/api/buyeros_api/api/jwks.py @ cbbe0e93 | Neon verifier 已實作，本次離線 verifier tests 通過；實際 Neon JWT trust 未驗收。 |
| C61-11 | acceptance-only | services/live/auth.ts; services/live/session.ts; features/providers/workspace-session.tsx @ cbbe0e93 | Neon session/cross-tab/renewal 已實作，本次本地測試通過；live Auth0 reload 仍重新要求 Sign in。 |
| C61-12 | acceptance-only | services/api/tests/test_auth_tenant.py; services/api/tests/test_auth_routes_db.py; tests/e2e/audit-access-revocation.spec.ts @ cbbe0e93 | 負向測試在 hosted/local；真實 tenant／角色登入 readback 仍待做。 |
| C61-13 | acceptance-only | services/api/tests/test_backup_restore_t28.py @ cbbe0e93 | owned DB migration/cutover suites 在 hosted CI；production target 與rollback兼容需先 C61-31/32。 |
| C61-14 | activation-only | services/api/buyeros_api/settings.py; services/api/buyeros_api/api/auth_trust.py; services/live/auth.ts @ cbbe0e93 | 未切 Neon-only，live Auth0 仍 active；不能直接刪 Auth0 或以 email 自動連結。 |
| C61-15 | modify | services/api/buyeros_api/providers/base.py; services/api/buyeros_api/providers/search.py; services/api/buyeros_api/providers/model.py @ cbbe0e93 | DEFAULT_REGISTRY 空；需選定驗證的 immutable account/contract/cost scope。 |
| C61-16 | acceptance-only | services/api/buyeros_api/providers/search.py; services/api/buyeros_api/execution/provider_dispatch.py; services/api/buyeros_api/execution/external_runner.py @ cbbe0e93 | live_search adapter 已實作；本次 mock transport tests 通過；real sandbox 未驗收。 |
| C61-17 | acceptance-only | services/api/buyeros_api/providers/model.py; services/api/buyeros_api/execution/fit_runner.py; services/api/buyeros_api/execution/fit_execution.py @ cbbe0e93 | live_model 與 research handoff source 已實作；real grounded output 品質未驗收。 |
| C61-18 | acceptance-only | services/api/buyeros_api/providers/contact.py; services/api/buyeros_api/execution/handlers/contact_submit.py; services/api/buyeros_api/services/contact_result_service.py @ cbbe0e93 | live_contact quote/receipt/adapter 已實作；real account/cost/contact acceptance 未驗收。 |
| C61-19 | acceptance-only | services/api/buyeros_api/api/routes/runs.py; services/api/buyeros_api/services/run_admission.py; services/api/buyeros_api/execution/provider_dispatch.py @ cbbe0e93 | durable research orchestration 與unknown回復有 hosted coverage；正式 provider未選定。 |
| C61-20 | activation-only | services/api/buyeros_api/api/routes/drafts.py; services/api/buyeros_api/services/draft_service.py; services/api/buyeros_api/api/routes/provider_callbacks.py @ cbbe0e93 | delivery ledger/admission/status/native/Resend候選已實作；authorization=None，無啟用。 |
| C61-21 | acceptance-only | features/live/overview.tsx; features/live/operations.tsx; services/live/job-query.ts @ cbbe0e93 | 六卡範圍與列表 fixture 通過；正式資料量一致性未驗收。 |
| C61-22 | acceptance-only | features/live/drafts.tsx; features/live/draft-grounding-review.tsx; features/live/draft-dirty-guard.tsx @ cbbe0e93 | grounding/dirty/Unicode source已實作；需真實同revision核准／匯出驗收。 |
| C61-23 | acceptance-only | features/live/bulk-manifest.tsx; features/live/bulk-actions.tsx; features/live/settings.tsx @ cbbe0e93 | bulk manifest、expiry、Settings與keyboard已加測；正式站受阻。 |
| C61-24 | blocked | services/api/tools/evaluate_research_goldset.py; services/api/tools/quality_metrics.py; services/api/tests/test_quality_tools.py @ cbbe0e93 | real gold set、成本及誤判指標仍無本次結果。 |
| C61-25 | acceptance-only | scripts/benchmark-workspace-directory.py; scripts/benchmark-buyeros.py; scripts/benchmark-buyer-mutations.py @ cbbe0e93 | harness與hosted容量測試存在；本次沒有真實成功請求performance baseline。 |
| C61-26 | acceptance-only | tests/e2e/fixtures/staff-journey.ts; tests/e2e/audit-daily-journey.spec.ts; tests/e2e/audit-research-intent.spec.ts @ cbbe0e93 | 完整八模組流程 BLOCKED_AT_WORKSPACE。 |
| C61-27 | blocked | docs/buyeros/CURRENT_STATUS.md @ cbbe0e93 | 真實員工 mobile／screen reader UAT 尚未完成。 |
| C61-28 | modify | .github/workflows/buyeros-ci.yml; scripts/check-required-tests.py; scripts/generate-api-types.mjs @ cbbe0e93 | 證據 checker存在，但今回未阻止schema不相容程式到正式 alias；加入 C61-33。 |
| C61-29 | activation-only | docs/buyeros/CURRENT_STATUS.md; TASKS.json; docs/buyeros/runbooks/worker-runtime.md @ cbbe0e93 | 程式已部署，Release A acceptance仍 NOT_ACCEPTED；需修復後實際readback。 |
| C61-30 | activation-only | features/live/drafts.tsx; features/live/operations.tsx; docs/buyeros/CURRENT_STATUS.md @ cbbe0e93 | native send尚未啟用，無真實寄送receipt。 |
| C61-31 | modify | plan-specified new gap @ cbbe0e93 | 只讀查 actual database/branch/search_path、alembic_version、to_regclass、0038 function、0039 grants、legacy exact mapping counts；保留已遮蔽證據。 |
| C61-32 | blocked | plan-specified new gap @ cbbe0e93 | 依 C61-31 結果選擇已證明相容 rollback 或 additive migration；先隔離副本排練；0039包含原 UUID backfill、trigger、grants，不只建空表。 |
| C61-33 | modify | plan-specified new gap @ cbbe0e93 | 更新release manifest；以固定 source/API/worker/schema tuples 驗證；CI成功後在candidate以runtime role測requiredrelations/grants/mapping及known-account workspace；失敗禁止promote。 |
