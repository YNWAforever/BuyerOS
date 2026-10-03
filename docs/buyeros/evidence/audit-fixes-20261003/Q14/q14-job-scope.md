# Q14 inline plan

### Task 1: Q14 job scope

### Q14 · 工作數與列表使用相同scope

**交付：** PR-17｜**問題：** F17｜**優先：** P2｜**前置：** Q03

**證據／驗收案例：** E03；U15。責任角色：Frontend。

**檔案邊界：**

- 修改／核對：`features/live/overview.tsx`、`features/live/operations.tsx`。
- 新增：`services/live/job-query.ts`、`tests/e2e/audit-job-scope.spec.ts`。
- 測試：`tests/e2e/audit-job-scope.spec.ts`。

**Interfaces／設計決定：** `JobScope = {kind:'project';workspaceId:string;projectId:string} | {kind:'workspace';workspaceId:string}`；`buildJobQuery(scope, {status,offset,limit}):URLSearchParams` 供 count、list、deep link 共用。選 project 時必含 project_id；workspace view 必須明示範圍且保留 server actor restriction。

- [ ] **1.** U15：project A=0 failed、B=5 failed；assert A卡=0且點入A列表=0，workspace view=5且標籤清楚。
- [ ] **2.** 先證明現版畫面 scope/count 不一致；實作 shared query builder。
- [ ] **3.** scope 變動清頁碼及舊結果；URL 保留 scope/status。
- [ ] **4.** 測非 admin 只能看自己的 job，即使 workspace view 也不可越權。
- [ ] **5.** 重跑 slow-response scope切換及已知 Q03 分頁。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q14` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-job-scope.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** revert query/UI；server 授權契約不變。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

