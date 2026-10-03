# Q08 isolated execution

### Task 1: Q08 · 10k分段維護manifest

**交付：** PR-18｜**問題：** F11｜**優先：** P2｜**前置：** Q05、Q06

**證據／驗收案例：** E03；B01;B08;B09;B14;B15。責任角色：Backend＋Frontend。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/services/buyer_selection.py`、`services/api/buyeros_api/services/bulk_service.py`、`services/api/buyeros_api/db/outbox.py`、`features/live/buyer-results.tsx`、`features/live/bulk-actions.tsx`、`docs/buyeros/contracts/openapi.proposed.yaml`。
- 新增：`services/api/buyeros_api/services/bulk_manifest.py`、`services/api/buyeros_api/api/routes/bulk_manifests.py`、`services/api/tests/test_bulk_manifest_db.py`、`tests/e2e/audit-bulk-manifest.spec.ts`。
- 測試：`services/api/tests/test_bulk_manifest_db.py`、`tests/e2e/audit-bulk-manifest.spec.ts`、`services/api/tests/test_bulk_jobs_db.py`。

**Interfaces／設計決定：** 新增 manifest preview/execute 流程：POST /v1/workspaces/{workspace_id}/projects/{project_id}/bulk-manifests 凍結 filter、排除集合、operation、target、reason及 IDs+versions；回 manifest_id、count、digest、expires_at、status。POST .../{manifest_id}/execute 必須確認 digest、If-Match、Idempotency-Key。建議上限10000、preview TTL15分鐘；超出明確拒絕分段篩選，不能靜默截斷。AsyncJob/AsyncJobItem 與既有50列chunk engine復用；snapshot1000上限不直接放大。

- [ ] **1.** B01/B08/B09/B14/B15/B16：100/101、1000/1001、10000、10001；10k 內50列 stale版本，assert 9950成功／50conflict、每ID只一結果，oversize不漏截。
- [ ] **2.** 先在 owned PG 建立 manifest 一致性測試；preview 在同一一致性快照 freeze ID/version，生成完成前不能 execute。
- [ ] **3.** 實作 durable preview、digest 確認及頁面恢復，交易中的 outbox admission 確保同 key 只一 job；execute 再檢角色／scope／target。
- [ ] **4.** 工作 crash/cancel 保留已commit，下一個 chunk 恢復；失敗集 retry 必須由人重新預覽目前版本並建立子意圖，不重做成功列。
- [ ] **5.** 記憶體與 SQL 按有界 chunk 處理，UI 用 Q06 summary+按需結果。小批同步與大批非同步保留既有契約，權限管理不使用此 endpoint。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q08` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_bulk_manifest_db.py tests/test_bulk_jobs_db.py；CONTRACT；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-bulk-manifest.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 停新 manifest admission；已入列工作按明確 cancel/recovery 保留結果；不盲目 Undo。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

