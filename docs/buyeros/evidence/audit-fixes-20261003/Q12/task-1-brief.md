### Task 1: Q12 · 人工改稿的来源覆核與重新審批

**交付：** PR-15｜**問題：** F16｜**優先：** P1｜**前置：** Q15

**證據／驗收案例：** E03;E06；D01;D03;U09。責任角色：Backend＋Frontend＋Reviewer。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/api/routes/drafts.py`、`services/api/buyeros_api/api/schemas.py`、`services/api/buyeros_api/db/drafts.py`、`services/api/buyeros_api/services/draft_service.py`、`services/api/buyeros_api/services/approval_service.py`、`services/live/drafts.ts`、`features/live/drafts.tsx`、`docs/buyeros/contracts/openapi.proposed.yaml`。
- 新增：`services/api/buyeros_api/services/draft_grounding.py`、`services/api/tests/test_manual_grounding_db.py`、`tests/e2e/audit-draft-reground.spec.ts`。
- 測試：`services/api/tests/test_manual_grounding_db.py`、`tests/e2e/audit-draft-reground.spec.ts`、`services/api/tests/test_draft_approval_context_db.py`。

**Interfaces／設計決定：** 新增 `POST /v1/workspaces/{workspace_id}/drafts/{draft_id}/grounding-reviews`，operation reviewDraftGrounding；If-Match＋Idempotency-Key。輸入 revision_id、content_hash、句段清單（field=subject/body、Unicode code-point start/end、exact_text、classification=factual/non_factual、versioned evidence/fact refs）、reason；只 reviewer/admin 可提交。輸出 generated Draft 的後繼 immutable revision；正文保持原樣，新增 claims／review metadata，再走原 exact-review／approve。不能在原 revision 原地改 content。

- [ ] **1.** D01/D03：保存人工修改→逐段來源覆核→exact review→approve→export；assert 正文保留、新 revision、旧 approval invalidated；無引用、跨公司、過期來源及 stale hash 不能批准。
- [ ] **2.** 增加完整 coverage 驗證：subject/body 每個非空文字段都被 reviewer 分類，factual 段必須有有效來源；offset 按 Unicode code points，測繁中／emoji／換行，不能用 JS UTF-16 offset 直接傳。非事實標記保留 reviewer 理由，UI 強制整篇核讀。
- [ ] **3.** 實作 transaction：鎖 draft、檢查 expected version／hash、重讀 company/tenant/source version/retention/offer facts/policy，保存人工作證及 successor revision，清舊 review context。系統只驗可檢查結構與來源資格，不能宣稱算法已證明句意正確。
- [ ] **4.** UI 顯示逐句與來源片段，讓 reviewer 明確覆核；一般 operator 可編輯／準備但不能自行讓 needs_review 變成 grounded。既有 approve 仍再驗 recipient、sender、policy、revision。
- [ ] **5.** 添加 actor/time/proof audit；取消或失敗不建立半個 grounded revision；重試同 key 只一 successor。資料模型變動採 additive migration。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q12` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_manual_grounding_db.py tests/test_draft_approval_context_db.py；CONTRACT；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-draft-reground.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 關閉新增覆核入口；保留 needs_review、所有 revisions 和 audit；不能直接改 grounded=true 讓舊稿通過。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

**補充：** PR 可再按同一 Q12 拆成 contract/domain 與 UI commits；兩者一同完成才關閉 F16。

