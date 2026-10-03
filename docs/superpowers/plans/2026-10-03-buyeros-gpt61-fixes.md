# BuyerOS 修復及 Neon Auth 遷移 — Codex GPT-6.1 Sol Implementation Plan

> **For agentic workers:** 使用 `superpowers:executing-plans`（如環境提供）逐項執行；每次完成一個可驗收任務，步驟以 checkbox 追蹤。此交接預設單一 Codex GPT-6.1 Sol 執行，不要求或授權額外 sub-agents。

**Goal：** 修復證據包的21項問題，完成日常研究至已批准匯出流程、可維護批量操作及Auth0→Neon Auth遷移，按證據驗收後才啟用相應正式能力。

**Architecture：** 保留 React／Vinext／Vite＋Nitro 前端、FastAPI domain API、Postgres及既有Cloudflare jobs架構。先修現有錯誤，再以additive identity mapping切入Neon Auth；業務RBAC、RLS、版本審批、idempotency、outbox與經濟帳本仍由現有domain層負責。

**Tech Stack：** 證據基線 Node≥22.13、React19.2.6、Vinext1.0.0-beta.5、Nitro3.0.260903-beta、TypeScript5.9.3、pnpm11.25.0；Python3.12／FastAPI／SQLAlchemy／Alembic／pytest；Playwright。按目前repo lockfile安裝，不能用本文舊版本強制降級。

**Spec：** `BuyerOS_Audit_2026-10-03_Evidence.zip` 內的稽核MD、98-case CSV、44-operation CSV、25-task CSV及E01–E09。ZIP SHA-256：`19369591a175edad7dd2e9f3ddb5bfdebc6cdc5130a2770243b1e9de2a42d35a`。本次已核對ZIP CRC和全部31個manifest hashes。

日期：2026-10-03（Asia/Hong_Kong）。目標執行者由舊計劃的 GPT-6 Sol 更新為 **GPT-6.1 Sol**；不因型號名稱變更而假設產品已修好。所有步驟是待執行計劃，本次沒有修改產品、部署、DB或會員。

## 1. 基線與不可誤讀的結果

| 項目 | 證據包內容 | 執行時處理 |
|---|---|---|
| 程式基線 | a78859fe474f5722be3755b10e2586436b53bf97 | 先讀AGENTS.md及最新HEAD；逐F-ID重查drift，不盲套舊行號 |
| 部署基線 | dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp，與source一致 | 本計劃沒有再次live稽核；重新唯讀確認目前deployment |
| 正式流程 | 首次workspace500；重試後無membership／404 | 是兩個獨立問題；Neon遷移不會自動修membership |
| 正式覆蓋 | 7/44代表操作執行；八模組業務內容0/8完成 | blocked不是pass；不能以source trace當live驗收 |
| 原自動檢查 | Python61pass＋1DBskip；JS103pass | 歷史基線，並非本計劃執行結果；缺DB不能把skip改pass |
| 效能 | fake connection量到2+2W execute calls；W1000=2002 | 不是SQL時間／正式p95；新測試需owned PG與網路分層 |
| 能力 | 真provider allowlist空、delivery403、Neon尚未遷移 | 保留fail-closed；「外展完成」只驗收到批准匯出及人工outcome |

## 2. Global Constraints

- 保留 canonical `users.id`、memberships、owner、approval及歷史actor；禁止依email自動link或提升權限。
- Neon登入身份不等於workspace角色；roles只由BuyerOS DB membership決定。worker HMAC不改成user JWT。
- 版本更新保留If-Match、Idempotency-Key、逐列outcome、tenant／actor限制；不以UI顯示成功代替durable commit證據。
- 未明provider結果保留hold並reconcile；不為重試而換新key、不盲重發可能已commit的write。
- 修改採局部、小PR；不順手換框架、重寫全站、換jobs平台、接付費模型或開寄送功能。
- 所有DB mutation tests只使用既有guard接受的disposable loopback `buyeros_test_*` DB或Docker。**不能把production或Neon branch DSN直接塞入現有destructive pytest fixture，更不能移除guard。** 隔離Neon Auth測試另用明確harness。
- 本次要求是寫計劃。後續明確開始實作時可做local code、tests、read-only核對及可審閱PR；正式membership／帳戶link、DB migration、deployment／auth cutover、provider支出、發信等按當時已有授權執行，缺授權只阻擋相關外部動作。
- 不可變更原證據包。新增結果另記source SHA、命令、環境、case ID、pass/fail/skip/blocked及artifact。

## 3. Review Focus

| 容易漏掉的條件 | 必須得到的結果 | 負責任務 |
|---|---|---|
| token更新或硬刷新發生在研究回應遺失後 | 保留同意圖，未知狀態不再建新run | Q04、N04：B05/B06/NA19 |
| A→B→A scope＋慢回應／同kid跨issuer | 舊response不能覆蓋新scope；不同issuer不能共用key | Q03、Q06、N03：B16/NA16 |
| 保存衝突與背景job回來時仍有dirty稿 | 不丟文字；只有成功save或明確discard能離開 | Q15：D02 |
| 繁中／emoji人工稿的來源段落覆核 | Unicode位置正確、全篇覆核、同revision來源有效 | Q12：D01/D03 |
| cutover之後新Neon帳戶與新業務寫入 | rollback仍有登入恢復路徑且不還原/丟失業務資料 | N06/N07：NA29 |

## 4. 執行分組及PR順序

保持原N00–N07／Q01–Q17共25個ID。PR-xx是建議交付編號，不是GitHub已建立的PR；有外部blocker時可按依賴調整先後。每個PR只有一個主要可驗收成果；首輪四PR替代舊計劃的單一大PR，便於獨立回退。

| 波次 | 先後順序 | 何時可交付 |
|---|---|---|
| 起點 | Q11的PR-00 current baseline；Q16唯讀調查 | 記錄完成不等於所有release gates完成 |
| A：可立即修 | Q01 → Q03 → Q04 → Q15 | 4個獨立PR；必要fixture/DB測試通過即可review |
| B：早期認證決策 | N00 → N01/N02 → N03 → N04 → N05 | 在隔離fixture完成；Auth0正式路徑仍可用 |
| C：核心日常流程 | Q02 → Q05；Q03 → Q06；Q15 → Q07/Q12；Q03 → Q14；N02 → Q13 | 可依資源交錯做，不必等Neon正式切換 |
| D：效率及驗收 | Q05/Q06 → Q08；Q01/Q02/Q05/Q14/Q15 → Q09；再Q10 | 10k維護、8模組journey、perf/accuracy證據 |
| E：認證切換 | Q12/Q15＋N05 → N06；N06＋Q11-Auth → N07 | 具體readback、rollback及授權後才正式切換 |
| 事故修復 | Q16有根因 → Q17 | 無根因則受阻，其餘繼續 |
| 收尾 | Q11按能力關閉各gate | 可用Auth不等於真provider/完整外展已上線 |

依賴修訂：Q02解除舊N02依賴，因現有User.display_name及分頁不需換身份；Q13仍依N02共用resolver。N06新增Q12/Q15，避免以存在草稿斷點的流程驗收遷移。N07只依Q11-Auth gate，不要求未啟用provider先完成；全產品可用性另外受Q10／WF03約束。

## 5. 共用檔案與驗證規則

| 邊界 | 檔案 | 規則 |
|---|---|---|
| contract真源 | docs/buyeros/contracts/openapi.proposed.yaml | 新endpoint先定schema、operationId、roles、error和pagination |
| 生成型別 | services/generated/buyeros-api.ts | 執行generator，禁止手改；generated routes及operation ledger同步 |
| live client | services/live/operations.ts、client.ts、session.ts | 沿用scope generation、abort、typed response和token supplier |
| auth | features/providers/workspace-session.tsx、services/live/auth.ts、api/auth.py、api/jwks.py | Q01先改狀態；N04再換adapter，避免重做 |
| migrations | services/api/alembic/versions/ | 每PR由目前head產生唯一revision；expand→backfill→verify→切讀；不硬編下一序號 |
| 新UI regression config | playwright.audit-fixes.config.ts | Q01建立；所有audit-*.spec.ts使用隔離HTTP/DB，不指向live |
| Neon harness | playwright.neon-auth.config.ts | N00建立；mock JWT契約與真Neon roundtrip分開標示 |
| 狀態文件 | docs/buyeros/CURRENT_STATUS.md | 每PR更新自己的F-ID／case證據，歷史資料不覆寫 |

以下命令都是**給執行者的驗證指令，本次未執行**。標示「新增」的檔案由所屬任務建立，執行前應存在；讀最新版config確認testMatch，不能在只匹配daily-workbench的舊config下誤跑新test而得到0 tests。

**CONTRACT**（repo root）：

```bash
node scripts/generate-api-types.mjs --write
uv run --frozen --project services/api python scripts/generate-operation-routes.py
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
pnpm exec tsc --noEmit
```

上述 routes generator 在基線預設寫入，`--check`作比對，PyYAML使用services/api鎖定依賴。所有新operation還須在app註冊router，更新deps.OPERATION_ROLES及API_OPERATION_STATUS.csv。

**API-TEST**（下文縮寫；cwd=`services/api`）：

```bash
BUYEROS_STRICT_INTEGRATION=1 uv run --frozen pytest -q <任務列出的測試檔> --junitxml=artifacts/audit-task.xml
```

`<…>`是明確替換位置，不是可直接貼上字串。需要DB的case要零skip；無Docker/loopback測試DB時記blocked，不能降低STRICT或改安全guard。frontend fixture亦可能需要services/worker的鎖定依賴，跟現有CI/harness準備。

每PR先跑針對缺陷的紅測試，再實作、綠測試；低風險純文件任務用內容核對，不製造形式化測試。共用auth/client/contract改動需跑現有相關check，migration需owned PG與role/RLS；改controller才跑對應Cloudflare gates。最後release跑CI必需suites及完整journey，避免每個文案改動都重跑無關全套。

## 6. 逐項實作

### Q01 · 修復auth狀態、空存取與語言

**交付：** PR-01｜**問題：** F01;F02;F15｜**優先：** P1｜**前置：** 無

**證據／驗收案例：** E01;E03;E07；U01;U02;U03;U13。責任角色：Frontend＋Admin。

**檔案邊界：**

- 修改／核對：`features/providers/workspace-session.tsx`、`app/auth/callback/page.tsx`、`features/live/workspace-picker.tsx`、`features/live/locale.ts`、`locales/index.ts`。
- 新增：`playwright.audit-fixes.config.ts`、`tests/e2e/audit-auth-entry.spec.ts`。
- 測試：`tests/e2e/audit-auth-entry.spec.ts`、`tests/live-auth-checks.mjs`。

**Interfaces／設計決定：** 在 SessionValue 新增判別狀態 `AuthBootstrap = {kind:'initializing'} | {kind:'disabled'} | {kind:'ready'; auth:AuthAdapter} | {kind:'configuration_error'; message:string}`；沿用 AuthAdapter、SessionScope。只有配置缺漏或不合法才是 configuration_error，callback 失敗另列 callback_error。顯示語言獨立於 membership；只把非敏感 locale 存入瀏覽器偏好，會員偏好載入後只在本次尚未手動切語言時套用；若本次已手動選擇則保留，登入前不寫會員API。

- [ ] **1.** 新增 `U13_initialization_has_no_false_config_alert`：延遲 hydration，assert 初始化只有 status；配置正確的整段 callback 不出現未配置 alert。新增 U02/U03：無會員及 500 時仍可切 en／zh-HK，Retry 只重讀存取。
- [ ] **2.** 建立 playwright.audit-fixes.config.ts，繼承 workbench fixture 的隔離 HTTP／Postgres 啟動與 teardown，testMatch 僅 audit-*.spec.ts；禁止 reuseExistingServer、正式 URL 及 production fixture。先執行上述案例，保留針對現有缺陷的失敗。
- [ ] **3.** 實作初始化狀態與空權限頁；提供重新檢查、切換帳戶及複製診斷資料（request ID、時間、scope、登入方式），不包含 token、callback code。沒有設定支援地址時顯示聯絡工作區管理員，不發明聯絡人。
- [ ] **4.** 重跑 U02/U03/U13；驗證 401、403、404、500 文案各自正確。無會員不得自動建立 workspace 或 admin。
- [ ] **5.** 將 U01 的正式存取核對獨立記錄：管理員比對 verified issuer＋subject、canonical user、active membership。UI PR 可完成；U01 未有證據仍 blocked。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q01` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** node tests/live-auth-checks.mjs；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-auth-entry.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** revert UI commit；保持既有後端 fail-closed，不撤銷或新建 membership。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### Q03 · Operations契約與結果分頁

**交付：** PR-02｜**問題：** F05｜**優先：** P1｜**前置：** Q01

**證據／驗收案例：** E03；B10;B11。責任角色：Frontend。

**檔案邊界：**

- 修改／核對：`features/live/operations.tsx`、`services/live/operations.ts`、`services/generated/buyeros-api.ts`。
- 新增：`tests/e2e/audit-operations.spec.ts`。
- 測試：`tests/e2e/audit-operations.spec.ts`、`tests/operation-input.types.ts`。

**Interfaces／設計決定：** consumer 使用 `components['schemas']['AsyncJob']`／`BulkItemResult`，結果 ID 為 `item.id`。維持 `getAsyncJob` 的 offset／limit／total 契約；每頁 20，換 workspace、job、filter 時 offset 歸零並取消舊 request。不得手改 generated types。

- [ ] **1.** 新增 B10/B11：使用 server producer 的真實 schema payload，21／101 筆資料；assert 無 undefined ID／key，所有頁完整且無重複；0 筆顯示 0，不顯示 1–0。
- [ ] **2.** 先跑 audit-operations.spec.ts，確認失敗來自 consumer 的 buyer_id 及只讀第一頁。
- [ ] **3.** 移除手寫 Job，改用 typed operation client；增加 job 結果 Previous／Next／總數；完整 ID 可複製，名稱未知時不冒充買家名稱。
- [ ] **4.** 測試慢回應下換 job／workspace／page，舊資料不得覆蓋目前頁；其他 actor／tenant 的 job 仍由 server 拒絕。
- [ ] **5.** 執行 generated contract check 及 UI 測試，保存 payload 與畫面證據。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q03` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** node scripts/generate-api-types.mjs --check；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-operations.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** revert consumer；server contract 不改。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

**補充：** Q01 只提供共用 E2E config；不是產品邏輯依賴。

### Q04 · 研究建立保留操作意圖

**交付：** PR-03｜**問題：** F08｜**優先：** P1｜**前置：** Q01

**證據／驗收案例：** E03;E05；B05;B06。責任角色：Frontend＋Backend。

**檔案邊界：**

- 修改／核對：`features/live/run-progress.tsx`、`services/live/action-intent.ts`、`services/live/runs.ts`、`services/api/buyeros_api/services/run_admission.py`。
- 新增：`tests/e2e/audit-research-intent.spec.ts`。
- 測試：`tests/e2e/audit-research-intent.spec.ts`、`tests/live-adapter-checks.mjs`、`services/api/tests/test_run_admission_db.py`。

**Interfaces／設計決定：** 復用 `ActionIntent<Run>.run(fingerprint, work)`。fingerprint 由 actor/session scope（排除只因token更新變動的generation）、workspace、project、icp_version_id 及正規化完整 request body 組成；金額固定六位小數。unknown／lost-response 保留 key；成功取得 run 才結束意圖。新增「開始全新研究」必須明確重設意圖。UI generation token 只用於拒絕過期回應，不可因 token refresh 改變同一操作的 durable idempotency identity。

- [ ] **1.** 新增 B05/B06：server 已 commit run／outbox／reservation 後丟棄 202；同頁 Retry 及雙擊 assert 使用同 key，資料庫只有一個 run、一個 admission outbox 及一個經濟意圖。
- [ ] **2.** 先執行紅測試；另外覆蓋只改 target、cap、ICP、workspace 時才建立新意圖。
- [ ] **3.** 把 start 的 UUID 改為 ActionIntent；不可改 worker retry／hold 語意。uncertain 時顯示「查詢／重試同一次研究」，列出已知 run 或恢復線索。
- [ ] **4.** 保留現有 ActionIntent 的共用 promise 及失敗留 key 行為。若需要跨路由恢復，只保存非敏感 intent handle／key＋fingerprint，不保存 token；沒有可信恢復資料的硬刷新顯示檢查現有研究，不自動再發 POST。
- [ ] **5.** 在隔離 DB 驗證 durable 數量；token renew 及 A→B→A scope 回應不得產生新 side effect 或錯置 UI。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q04` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** node tests/live-adapter-checks.mjs；API-TEST tests/test_run_admission_db.py；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-research-intent.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 停用新研究建立入口或 revert consumer；保留已提交 run／outbox／hold，不重播未知操作。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

**補充：** 不因本地 busyRef 通過就把 B05 標完成；必須有 commit 後丟回應的持久化證據。

### Q15 · 草稿dirty guard與明確保存選擇

**交付：** PR-04｜**問題：** F19｜**優先：** P1｜**前置：** Q01

**證據／驗收案例：** E03；D02。責任角色：Frontend。

**檔案邊界：**

- 修改／核對：`features/live/drafts.tsx`、`services/live/drafts.ts`。
- 新增：`features/live/draft-dirty-guard.tsx`、`tests/e2e/audit-draft-dirty.spec.ts`。
- 測試：`tests/e2e/audit-draft-dirty.spec.ts`。

**Interfaces／設計決定：** `DirtyDecision = 'save'|'discard'|'cancel'`；`guardDraftTransition({dirty,choose,save,proceed}):Promise<boolean>`，choose 回傳 DirtyDecision，save 與 proceed 均為 `Promise<void>`。只有 dirty=false、明確 discard 或 save 成功可 proceed；save 拋錯／412 不得 proceed。所有 refresh、open draft、job materialization 走同一個 guard。

- [ ] **1.** 新增 D02 三分支測試：Cancel 保留 subject／body／language；Save 先等成功再換；Discard 只在明確選擇後捨棄。再加入 412、503 及背景 job 完成情境。
- [ ] **2.** 先證明現版 Refresh draft 會覆蓋本地草稿，再實作 guard dialog。
- [ ] **3.** 把未保存 baseline 綁 revision ID／version，API response 不得直接覆蓋 dirty buffer；衝突畫面並列本地與新版本，提供複製內容，不把 conflict 當成功保存。
- [ ] **4.** 保留焦點、Escape=Cancel、單一進行中 transition；背景更新只提示有新版。
- [ ] **5.** 重跑 D02；確認 token 過期、scope 切換後不把舊草稿寫入新 workspace。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q15` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-draft-dirty.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 回退 UI 前保留可複製的未保存內容；不清除 revision／approval。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### N00 · Neon框架相容及精確契約spike

**交付：** PR-05｜**問題：** F20｜**優先：** P1｜**前置：** 無

**證據／驗收案例：** E03;E09；NA01。責任角色：Identity＋Frontend。

**檔案邊界：**

- 修改／核對：`package.json`、`pnpm-lock.yaml`、`scripts/run-framework.mjs`、`scripts/run-vercel.mjs`。
- 新增：`docs/buyeros/decisions/2026-10-03-neon-auth-contract.md`、`tests/e2e/audit-neon-compat.spec.ts`、`playwright.neon-auth.config.ts`。
- 測試：`tests/e2e/audit-neon-compat.spec.ts`。

**Interfaces／設計決定：** 決策產物 `NeonAuthContract` 記錄 SDK 精確版本、Auth base URL、issuer、audience、JWKS URL、handler prefix、cookie domain／SameSite／TTL、provider methods、兩種 build 輸出與結果。首選官方同源 handler；只在 Vinext／Nitro 實測通過才採用。N03 消費 issuer/audience/JWKS，N04 消費 session／token adapter contract。

- [ ] **1.** 在獨立 spike branch 讀最新官方文件及目前 lockfile，確認現在是 Vinext／Vite＋Nitro，而不是把 package.json 中 next 視為標準 Next runtime。
- [ ] **2.** 建立最小登入→getSession→token→FastAPI 驗簽→logout fixture；NA01 先暴露不相容點。缺真 Neon fixture 時，mock 部分可做，但 NA01 不得標實際相容。
- [ ] **3.** 鎖定驗證過的 @neondatabase/auth 版本；分別執行 portable build 和 Vercel build，於建置後輸出測 cookie、callback、reload。
- [ ] **4.** 首選 app/api/auth/[...path]/route.ts＋server-only auth module；若不相容，先形成具體 ADR，比較受支持同源代理與局部 adapter，不自行換全站框架或以第三方 cookie 依賴作為通過。
- [ ] **5.** 保存精確契約與阻擋原因。未通過不合併 auth 切換，但 Q 系列獨立修復繼續。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N00` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** pnpm build（clean portable checkout）；node scripts/run-vercel.mjs build；pnpm exec playwright test --config playwright.neon-auth.config.ts tests/e2e/audit-neon-compat.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 刪除 spike／revert 試驗依賴；現有 Auth0 未切換。

**執行界線：** 本地 build 可先做；真登入 roundtrip 需要隔離 Neon Auth 及核准測試帳戶。

### N01 · 隔離Auth設定與production差異

**交付：** PR-06｜**問題：** F20｜**優先：** P1｜**前置：** N00

**證據／驗收案例：** E09；NA02;NA03。責任角色：Platform。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/settings.py`、`app/layout.tsx`。
- 新增：`docs/buyeros/runbooks/neon-auth-environments.md`、`services/live/auth-config.ts`、`tests/neon-config-checks.mjs`。
- 測試：`tests/neon-config-checks.mjs`。

**Interfaces／設計決定：** 新增設定分層：client provider mode 與 API accepted issuer set 分開；`BUYEROS_AUTH_MODE=auth0|dual|neon` 是本計劃新增設計。`NEON_AUTH_BASE_URL`、`NEON_AUTH_COOKIE_SECRET` 僅 server；API 的 Neon issuer／audience／JWKS 由 N00 契約明列，不用使用者輸入拼 URL。dual 必須有明確 UTC 截止時間，逾期拒絕 Auth0；缺配置不回落 production。

- [ ] **1.** NA02/NA03：缺任一必填配置、preview 指向 production、過期 dual deadline，assert 啟動拒絕或 fail-closed；build/log 不含 secret。
- [ ] **2.** 先提交 config parser 測試，之後實作型別化 env 驗證與 server/client 邊界。
- [ ] **3.** 整理 development／preview／production 差異、trusted domains、cookie secret、OAuth callback 與 email provider；只配置已採用方法。
- [ ] **4.** 建立可審閱設定 diff 與 rollback；隔離環境的實際服務變更按已有授權執行，未獲授權時只完成文件和程式。
- [ ] **5.** 記錄精確環境識別與核實時間，不輸出 secret 值。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N01` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** node tests/neon-config-checks.mjs；node scripts/run-vercel.mjs build。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 回復前版 config；保留 identity mapping 與稽核紀錄。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### N02 · 身份映射保持User與membership

**交付：** PR-07｜**問題：** F01;F20｜**優先：** P1｜**前置：** N00

**證據／驗收案例：** E03;E09；NA07;NA08;NA09;NA10。責任角色：Backend／Identity。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/db/models.py`、`services/api/buyeros_api/api/deps.py`、`services/api/buyeros_api/api/routes/workspaces.py`。
- 新增：`services/api/buyeros_api/services/identity_service.py`、`services/api/tests/test_identity_mapping_db.py`。
- 測試：`services/api/tests/test_identity_mapping_db.py`、`services/api/tests/test_auth_routes_db.py`。

**Interfaces／設計決定：** 新增 additive `auth_identities(issuer,subject,user_id,active,verified_at,proof_ref)`，唯一鍵 (issuer,subject)，FK 指向原 users.id。`resolve_canonical_user_id(session, *, principal:Principal) -> UUID|None` 僅接受已驗簽 Principal；disabled mapping 不回落舊 users 表。migration 將既有 users issuer/sub 一對一 backfill，重跑可對帳；verified proof_ref 是不可含憑證的稽核引用。

- [ ] **1.** NA07–NA10：同 user 兩 issuer 仍是同一 UUID；同 email 不同 sub 無 proof 不 link；mapping collision 原子拒絕；disabled／unmapped 沒有 membership。
- [ ] **2.** 新增 migration（由當前 Alembic head 產生唯一 revision，不能硬寫 0037）；保留原 users 欄與所有業務 FK。
- [ ] **3.** 實作唯一 canonical resolver，替換 workspace discovery／load_membership 的直接 issuer/sub 查詢，搜尋全 repo 補齊同類入口。
- [ ] **4.** mapping 管理只供受控管理程序，普通 runtime 不可自行 INSERT／UPDATE 身份連結；新增／撤回均有 proof、actor、時間和理由。email 只作比對提示。
- [ ] **5.** 以 migration 前後 UUID／membership／owner／approval／job actor 對帳及並發 link 測試證明一致。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N02` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_identity_mapping_db.py tests/test_auth_routes_db.py。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 停止新 issuer 接入，保留 additive schema 與已核實 mapping；不還原整個業務 DB。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### N03 · Neon JWT驗證及有限雙issuer

**交付：** PR-08｜**問題：** F20｜**優先：** P1｜**前置：** N01、N02

**證據／驗收案例：** E03;E09；NA11;NA12;NA13;NA14;NA15;NA16。責任角色：Backend／Security。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/api/auth.py`、`services/api/buyeros_api/api/jwks.py`、`services/api/buyeros_api/settings.py`。
- 新增：`services/api/tests/test_neon_jwt.py`。
- 測試：`services/api/tests/test_neon_jwt.py`、`services/api/tests/test_jwks_cache.py`、`services/api/tests/test_auth_cache_lifecycle.py`。

**Interfaces／設計決定：** `IssuerPolicy(issuer,audience,jwks_url,algorithms,provider)`，Auth0=RS256/RSA，Neon=EdDSA/OKP/Ed25519。cache 依 issuer＋JWKS URL＋algorithm policy 隔離；unverified iss 只可選預設 allowlist，不授權也不觸發任意 URL fetch。驗簽及 iss/aud/exp/nbf/sub 型別通過後才建立 Principal。

- [ ] **1.** NA11–NA16 加上 existing S01：正確 Ed25519 通過；none／HS256／錯 kty／跨 branch audience／過期／壞 sub 拒絕；同 kid 不同 issuer 不混用。
- [ ] **2.** 先用固定測試 key 與 fake clock 產生紅測試，保留原 Auth0 suites。
- [ ] **3.** 擴充 verifier，固定 allowlist，不採用 token 內 jku/x5u；保留 single-flight JWKS refresh、TTL、unknown-kid rate limit 及 hard-stale fail-closed。
- [ ] **4.** 測 bounded dual acceptance 及截止後 Auth0 被拒絕；Neon role=admin 不能繞過 DB membership。
- [ ] **5.** 將 JWT policy、cache key 和錯誤類型寫入 ADR；日誌不得包含原 token。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N03` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_neon_jwt.py tests/test_jwks_cache.py tests/test_auth_cache_lifecycle.py tests/test_api_auth.py。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 在已核准窗口回復 Auth0 trust；停用 Neon acceptance；不刪已 link 帳戶。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### N04 · Neon UI及session恢復

**交付：** PR-09｜**問題：** F02;F15;F20｜**優先：** P1｜**前置：** N01、N03、Q01、Q04

**證據／驗收案例：** E03;E09；NA04;NA05;NA17;NA18;NA19;NA20;NA23;U14。責任角色：Frontend。

**檔案邊界：**

- 修改／核對：`services/live/auth.ts`、`services/live/session.ts`、`services/live/client.ts`、`services/live/operations.ts`、`features/providers/workspace-session.tsx`、`app/auth/callback/page.tsx`、`features/live/workspace-picker.tsx`、`app/layout.tsx`。
- 新增：`services/live/neon-auth.ts`、`lib/auth/server.ts`、`app/api/auth/[...path]/route.ts`、`tests/e2e/audit-neon-session.spec.ts`。
- 測試：`tests/e2e/audit-neon-session.spec.ts`、`tests/live-auth-checks.mjs`、`tests/live-adapter-checks.mjs`。

**Interfaces／設計決定：** 依 N00 通過的 SDK 路徑實作 `createNeonAuthAdapter(...):AuthAdapter & {restoreSession():Promise<boolean>}`。瀏覽器登入由 HttpOnly session cookie 維持；`getAccessToken()` 經同源受控路徑取得短期 JWT，快過期 30 秒內 single-flight 換取，JWT 僅記憶體。身份變更用 issuer＋subject，不能只用跨 issuer 可能重複的 sub。

- [ ] **1.** NA04/05/17–20/23、U14：reload／新 tab／deep link 恢復同一授權 scope；10 個 API 同時到期只換 token 一次；惡意 returnTo 回 /app。
- [ ] **2.** 先跑新 session tests，之後實作 server handler、adapter、初始化恢復與登入／登出 UI。保留 Auth0 adapter 直到 N07。
- [ ] **3.** 讓 read client 與 typed operation client 均接 token supplier；401 最多換取一次。寫入重試只容許原 payload＋原 idempotency key；網路失敗／5xx 不自行新建意圖重送。
- [ ] **4.** 跨 tab logout 廣播只傳登出事件，清 token／scope／cache／poll；不傳 token。已發出的 JWT 可有餘下有效期，不能宣称瀏覽器 logout 即令所有 bearer 立即失效。
- [ ] **5.** 重跑 Q04 lost202、role 撤回與 A→B→A；session 尚在恢復時不顯示無會員。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N04` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** node tests/live-auth-checks.mjs；node tests/live-adapter-checks.mjs；pnpm exec playwright test --config playwright.neon-auth.config.ts tests/e2e/audit-neon-session.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 回復舊登入 UI／adapter，保留業務資料；Neon-only 新戶依 N07 恢復策略處理。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### N05 · 身份及八模組回歸

**交付：** PR-10｜**問題：** F20｜**優先：** P1｜**前置：** N02、N03、N04

**證據／驗收案例：** E09；NA21;NA22;NA24;NA25;NA26。責任角色：QA＋Security。

**檔案邊界：**

- 修改／核對：`tests/e2e/fixtures/workbench-auth.ts`、`tests/vercel-services.test.mjs`、`tests/worker-gateway.test.mjs`。
- 新增：`services/api/tests/test_neon_authorization_db.py`、`tests/e2e/audit-neon-security.spec.ts`。
- 測試：`services/api/tests/test_neon_authorization_db.py`、`tests/e2e/audit-neon-security.spec.ts`、`tests/vercel-services.test.mjs`、`tests/worker-gateway.test.mjs`。

**Interfaces／設計決定：** 身份認證、workspace RBAC、service HMAC 三者分離。撤回 mapping／membership 後，下次 API 和需重新授權的 domain step 必須拒絕；純 JWT cryptographic validity 不代表業務權限仍有效。fixture 可簽測試 JWT，但 production 不接受測試 principal bypass。

- [ ] **1.** NA21/22/24–26 以及 S02/S05/S06：跨 tenant、非 admin、disabled mapping/member、惡意 Origin、callback replay；assert 拒絕且無業務寫入。
- [ ] **2.** 加入 WebKit runner 及人工 Safari 測試記錄；第三方 cookie 被禁時同源登入／reload／logout 仍可行。runner 不等同實機 Safari。
- [ ] **3.** 驗證業務 /v1 proxy 不轉送 auth cookie／secret；Neon handler 的合法 cookie 路徑獨立，worker internal 仍只信原 HMAC。
- [ ] **4.** 以必要 owned-Postgres suites 零 skip、既有 gateway suites 通過作 gate；不得為了測試通過弱化 RLS／CSRF。
- [ ] **5.** 保存 UI 與 API 一致的 viewer／operator／reviewer／workspace_admin 角色矩陣。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N05` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_neon_authorization_db.py tests/test_auth_tenant.py tests/test_safe_fetch.py；node --experimental-strip-types tests/vercel-services.test.mjs；node --experimental-strip-types tests/worker-gateway.test.mjs；pnpm exec playwright test --config playwright.neon-auth.config.ts tests/e2e/audit-neon-security.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 阻止 cutover；保留既有 provider，不降低驗收斷言。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### Q02 · 成員分頁與可辨識身份

**交付：** PR-11｜**問題：** F03;F04｜**優先：** P1｜**前置：** Q01

**證據／驗收案例：** E03；U06;U07;U08;S06。責任角色：Frontend＋Backend。

**檔案邊界：**

- 修改／核對：`features/live/settings.tsx`、`services/api/buyeros_api/api/routes/memberships.py`、`services/api/buyeros_api/api/schemas.py`、`docs/buyeros/contracts/openapi.proposed.yaml`。
- 新增：`tests/e2e/audit-memberships.spec.ts`、`services/api/tests/test_membership_directory_db.py`、`docs/buyeros/runbooks/member-onboarding.md`。
- 測試：`tests/e2e/audit-memberships.spec.ts`、`services/api/tests/test_membership_directory_db.py`。

**Interfaces／設計決定：** 延伸 memberships GET 加 `q`，server offset／limit≤100／total，同一 filter 計數。增加安全 display_name，fallback 完整 ID；不顯示未授權 email。新增 `GET /v1/workspaces/{workspace_id}/eligible-assignees?q=&offset=&limit=`，`EligibleAssignee={membership_id,display_name,user_id,version}`，僅 assignBuyerOwners 可用角色可讀，server eligibility 與提交時同一規則。

- [ ] **1.** U06/U07/U08/S06：250 成員、同名、相同 ID 尾碼，assert 第 101 位可搜尋／可達、total 正確；last-admin 併發拒絕失去最後管理員。
- [ ] **2.** 加入 API search／projection 與 typed contract tests；先證明現版 UI 缺頁。
- [ ] **3.** 實作 server 搜尋與分頁，不在前端一次下載全名單；身份名稱由既有 users.display_name，Neon 遷移之後再由核實資料更新，不等待 N02。
- [ ] **4.** 加入最小 eligible-assignee lookup 供 Q05；角色更改仍逐人 If-Match、reason、idempotency，不開一般 bulk role edit。
- [ ] **5.** 提供 admin onboarding checklist：已核實身份、明確 workspace/roles、現有受控建立程序及驗收。完整邀請寄信／接受／撤回系統是後續產品項目，不以此 PR 宣稱已有 invitation。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q02` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_membership_directory_db.py；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-memberships.spec.ts；CONTRACT。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** revert UI／新增 projection；已審計的角色變更不自動撤銷。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

**補充：** 修正舊計劃的不必要 N02 依賴：分頁與 existing User.display_name 可先完成；不改 canonical identity。

### Q05 · 分派同事與精確批量確認

**交付：** PR-12｜**問題：** F06｜**優先：** P1｜**前置：** Q02

**證據／驗收案例：** E03；B02;B03;B04;B07;B16。責任角色：Frontend＋Backend。

**檔案邊界：**

- 修改／核對：`features/live/bulk-actions.tsx`、`features/live/buyer-results.tsx`、`services/api/buyeros_api/services/buyer_management.py`。
- 新增：`services/live/bulk-confirmation.ts`、`tests/e2e/audit-bulk-confirmation.spec.ts`。
- 測試：`tests/e2e/audit-bulk-confirmation.spec.ts`、`services/api/tests/test_bulk_jobs_db.py`。

**Interfaces／設計決定：** `bulkConfirmationFingerprint(input):string` 包含 actor、workspace、project、operation、selection ID+versions 或 snapshot+excluded IDs、owner membership ID、trimmed reason。穩定序列化 selection；任何實質變化清 confirm。owner selector 提供自己／有資格同事／無 owner；server 再驗 eligibility。

- [ ] **1.** B02–B04/B07/B16：選 5 確認後加 1、改 reason／owner／scope assert confirmation=false；10 同事可搜尋選擇。
- [ ] **2.** 先跑 UI 紅測試，再接 Q02 directory 與 fingerprint；頁碼變動但選取集合不變不應誤清。
- [ ] **3.** 預覽顯示 scope、數量、owner、原因及可能衝突；submit 用當時凍結 payload 與 ActionIntent。
- [ ] **4.** 模擬預覽後 owner 停用、buyer version 變動；逐列 blocked／conflict，不能繞過 server。
- [ ] **5.** 重跑 mixed 100 列計數：requested = updated＋unchanged＋blocked＋conflicts（終態依既有契約），audit reason 可追查。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q05` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_bulk_jobs_db.py；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-bulk-confirmation.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 關閉新版分派入口；保留已成功結果，不自動反向分派。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### Q06 · 有界job summary輪詢

**交付：** PR-13｜**問題：** F07｜**優先：** P1｜**前置：** Q03

**證據／驗收案例：** E03；B12;B13;P04。責任角色：Frontend＋Backend。

**檔案邊界：**

- 修改／核對：`features/live/bulk-actions.tsx`、`features/live/operations.tsx`、`services/api/buyeros_api/api/routes/jobs.py`、`services/api/buyeros_api/services/bulk_service.py`、`docs/buyeros/contracts/openapi.proposed.yaml`。
- 新增：`services/live/job-poller.ts`、`tests/job-poller-checks.mjs`、`services/api/tests/test_job_summary_db.py`。
- 測試：`tests/job-poller-checks.mjs`、`services/api/tests/test_job_summary_db.py`、`tests/e2e/audit-operations.spec.ts`。

**Interfaces／設計決定：** 新增 `GET /v1/workspaces/{workspace_id}/jobs/{job_id}/summary`／operation getAsyncJobSummary，回 typed `AsyncJobSummary`（狀態及 counters，無 result_page），保留原 result endpoint。`startJobPoller({fetchSummary,onValue,onError,signal,isVisible}):()=>void`；每 view／job 一個 in-flight，完成後 2s 再排，失敗 2/4/8/16/30s 上限；429 遵守 Retry-After；hidden 暫停、unmount/scope abort、terminal 停止。

- [ ] **1.** B12/B13/P04：RTT 2.5s＋1000 results、fake clock，assert maxInFlight=1；沒打開結果頁 result requests=0；hidden=0，新 visible 只更新一次。
- [ ] **2.** 先寫 poller 與 summary contract 紅測試；summary 的 actor/tenant guard 必須與 detail 一樣。
- [ ] **3.** 實作有界 summary poller，結果頁只在使用者選頁時讀；terminal 最多 refresh 當前可見頁一次，completion callback 只一次。
- [ ] **4.** 測 429 seconds/date、503、timeout、取消及 A→B→A；Abort 不顯示可怕錯誤，不繼續整段 pagination。
- [ ] **5.** 記錄前後 60 秒、10 views 的 requests／bytes／DB execute count；只把實測改善寫入結果。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q06` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** node tests/job-poller-checks.mjs；API-TEST tests/test_job_summary_db.py；CONTRACT；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-operations.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 回退至手動 Refresh；不重新啟用每兩秒全結果抓取。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### Q07 · 草稿控制項與模板承諾一致

**交付：** PR-14｜**問題：** F09｜**優先：** P2｜**前置：** Q15

**證據／驗收案例：** E06；A02;A07。責任角色：Frontend＋Backend。

**檔案邊界：**

- 修改／核對：`features/live/drafts.tsx`、`services/api/buyeros_api/execution/handlers/draft_generate.py`。
- 新增：`tests/e2e/audit-template-copy.spec.ts`。
- 測試：`services/api/tests/test_draft.py`、`tests/e2e/audit-template-copy.spec.ts`。

**Interfaces／設計決定：** 採最小明確方案：保留現有免費固定模板，tone 不再作可影響正文的選項；objective 如保留，只標示「內部工作目的，不改變模板正文」。API 為相容性保留欄位，UI 提交明確固定 tone。language 控制只承諾模板支援範圍，來源引用維持原語言。

- [ ] **1.** A02/A07：兩組 tone/objective 保持同正文時，UI 不得聲稱可調語氣／CTA；zh-HK 明示引用未自動翻譯。
- [ ] **2.** 先建立 UI 文案與實際 output 對照測試。
- [ ] **3.** 移除無作用的 tone control，objective 改為內部備註或隱藏；顯示免費固定模板及下一步人工改稿。
- [ ] **4.** 保留 deterministic template 的來源約束及零成本 admission；不順手接收費 LLM。
- [ ] **5.** 測修改後經 Q15 保留內容並可轉 Q12 來源覆核。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q07` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_draft.py；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-template-copy.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 恢復固定模板 UI 並保持限制文案；不啟用收費生成。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

### Q12 · 人工改稿的来源覆核與重新審批

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

### Q13 · Workspace membership discovery去全域掃描

**交付：** PR-16｜**問題：** F18｜**優先：** P1｜**前置：** N02

**證據／驗收案例：** E03;E06；P09;P10;S06。責任角色：Backend／DB。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/api/routes/workspaces.py`、`services/api/buyeros_api/api/deps.py`、`services/api/buyeros_api/db/session.py`。
- 新增：`services/api/buyeros_api/services/workspace_directory.py`、`services/api/tests/test_workspace_directory_query_count.py`。
- 測試：`services/api/tests/test_workspace_directory_query_count.py`、`services/api/tests/test_workspace_listing_db.py`、`services/api/tests/test_auth_tenant.py`。

**Interfaces／設計決定：** `list_visible_workspaces(session, *, user_id:UUID, offset:int, limit:int)->dict` 使用 N02 resolver。新增僅 SELECT 的 self-membership discovery policy：同一 transaction 由 server 驗簽後設定 app.user_id；只能 active 且 user_id=self。保留既有 workspace-scoped 策略及全部 write WITH CHECK；其他 tenant tables 不擴權。查 membership join workspace，server count＋stable order＋pagination，actor與workspace context 不跨 pool request 留存。

- [ ] **1.** P09/P10/S06：總 workspace=1/10/100/1000、同 actor 可見數固定，assert query count 不随無關 W 增長；有頁數邊界、revoked、兩 tenant 及池重用。
- [ ] **2.** 先重現包內 2+2W probe，新增 owned-PG runtime-role 測試；EXPLAIN 保存前後 plans。
- [ ] **3.** 新增 index 以 active membership 的 user_id／workspace_id 查詢；新 migration 對 RLS policy 的 missing/empty setting 用 fail-closed 表達式，僅放行已核實 actor 自己的 membership 讀取。
- [ ] **4.** 禁止 BYPASSRLS、table-owner runtime、全域 membership 快取及任意 user_id API 參數；清楚列明這是受限 SELECT policy 擴充，需安全 review。
- [ ] **5.** 建議預算：熱路徑包含 resolver/context/count/page ≤6 次 SQL execute、与 W 無關；若合理額外驗證超出，先在 PR 說明，不為數字略過安全查詢。所有必要 DB suites 零 skip。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q13` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_workspace_directory_query_count.py tests/test_workspace_listing_db.py tests/test_auth_tenant.py。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 切回舊 read strategy；保持 additive index/schema，確認 rollback 的舊程式仍可用；不改會員資料。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

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

### Q08 · 10k分段維護manifest

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

### Q09 · 日常任務優先的八模組UX

**交付：** PR-19｜**問題：** F14;F04｜**優先：** P2｜**前置：** Q01、Q02、Q05、Q14、Q15

**證據／驗收案例：** E03；U09;U10;U11;U12。責任角色：Product designer＋Frontend。

**檔案邊界：**

- 修改／核對：`features/live/overview.tsx`、`features/live/offer-wizard.tsx`、`features/live/buyer-results.tsx`、`features/live/results.tsx`、`features/live/run-progress.tsx`、`features/live/drafts.tsx`、`features/live/settings.tsx`、`features/live/operations.tsx`、`features/live/locale.ts`、`locales/index.ts`。
- 新增：`docs/buyeros/specs/2026-10-03-daily-workbench-ux.md`、`tests/e2e/audit-daily-ux.spec.ts`。
- 測試：`tests/e2e/audit-daily-ux.spec.ts`、`tests/e2e/responsive-accessibility.spec.ts`。

**Interfaces／設計決定：** 保持既有路由與業務操作；精簡 scope selector、主表＋buyer drawer、選取時才顯示 sticky bulk bar、debug ID 收於 details。Overview 的 CTA 帶正確 project/filter；Results 聚焦漏斗、成本與人工 outcome。共用 copy keys／錯誤映射，避免每元件另造翻譯。

- [ ] **1.** 先寫五項任務驗收：建/改Offer並交review、研究後review買家、跨頁分派與failed-only處理、人工改稿至批准匯出、管理成員與追查失敗job。以既有baseline錄時間、失誤、完成率。
- [ ] **2.** 在 spec 明列八模組 layout／empty/loading/error/permission states、390px／200% zoom／keyboard焦點；採既有design system，分模組小 commit。
- [ ] **3.** 消除重複清單與表單堆疊；Offer partial-save 不丟輸入、ICP舊版本不能批准；latest metadata 使用既有1筆分頁查詢，不先下載所有versions。
- [ ] **4.** 驗證 outcome=人工輸入、空分母=—、UTC範圍及 append-only correction；所有後台可見身份為人可辨名稱，內部ID仍可在details查閱。
- [ ] **5.** U09–U12/WF01/WF02：3–5員工×5任務，完成率≥90%、錯scope寫入0；缺實際人員時先交可測preview，人工UAT保持blocked。無整頁橫捲、focus可見、不讓aria-live輪詢洗版。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q09` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-daily-ux.spec.ts；使用既有 responsive/zoom config 執行 U10/U11；人工 U12 記分母及觀察。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 按模組回退 UI；保留共用契約、原始資料及安全控制。

**執行界線：** 本地及隔離 fixture 可開始；正式環境另按 release gate。

**補充：** 首次 source-based UX 建議不是現場受權視覺驗收；新的 preview 截圖與員工測試才可升級證據。

### Q10 · 效能與真實準確率驗收

**交付：** PR-20／Release-Quality｜**問題：** F12｜**優先：** P1｜**前置：** Q06、Q08、Q12、Q13、Q09

**證據／驗收案例：** E04;E06;E08；A03;A04;A05;A06;A08;P01;P02;P03;P04;P05;P06;P07;P08;P10。責任角色：QA／Data／SRE。

**檔案邊界：**

- 修改／核對：`scripts/benchmark-buyeros.py`、`docs/buyeros/performance-baseline.md`、`docs/buyeros/pilot/evaluation-protocol.md`。
- 新增：`scripts/benchmark-workspace-directory.py`、`services/api/tools/evaluate_research_goldset.py`、`tests/e2e/audit-full-handoff.spec.ts`。
- 測試：`tests/e2e/audit-full-handoff.spec.ts`、`services/api/tests/test_fit_eval.py`、`services/api/tests/test_settlement.py`。

**Interfaces／設計決定：** 版本化 benchmark result JSON：SHA、environment、dataset、region、actors、cold/warm、samples、p50/p95/p99、error denominator、requests/bytes/queries、cost。goldset row：company_id、market/language/type、source/date、雙人標記、reference verdict、split；metrics 同報 precision/recall/coverage/needs_review/CI，按company隔離holdout。

- [ ] **1.** 先跑 deterministic fixture／6-case fit／hold與settlement回歸（A01/S03/S04）；不能以這些數字代替 real accuracy。
- [ ] **2.** 執行固定負載方法與門檻（下節）；記錄 baseline→after，超標時定位到 request/SQL/render，再修相關任務並重測受影響項。
- [ ] **3.** 建立至少200家公司金標，兩位標註者獨立評核並處理分歧；holdout 固定，3次重跑；真provider未可用時交工具／fixture但A03–A08保留not-tested/blocked。
- [ ] **4.** WF03 以operator/reviewer/admin完成全部8模組持久化journey；mutation不可用response mock冒充server成功，跑出approve/export/outcome資料後重載核對。
- [ ] **5.** 每能力記錄成本上限、停止條件、owner和環境；先隔離負載，正式站/真provider只按已核准有界canary。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q10` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_fit_eval.py tests/test_settlement.py；pnpm exec playwright test --config playwright.audit-fixes.config.ts tests/e2e/audit-full-handoff.spec.ts；執行已記錄負載腳本與goldset protocol。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 停止負載／canary，保留所有結果及未知holds；失敗gate阻止對應能力上線。

**執行界線：** 本地工具可做；真人UAT、真provider goldset、正式RUM依資料/帳戶/成本授權分別受阻。

### N06 · 帳戶轉移演練與對帳

**交付：** PR-21｜**問題：** F01;F20｜**優先：** P1｜**前置：** N05、Q12、Q15

**證據／驗收案例：** E09；NA06;NA27。責任角色：Identity＋Admin。

**檔案邊界：**

- 修改／核對：`tests/e2e/fixtures/staff-journey.ts`。
- 新增：`services/api/tools/reconcile_auth_identities.py`、`docs/buyeros/runbooks/neon-auth-migration.md`、`tests/e2e/audit-neon-handoff.spec.ts`。
- 測試：`services/api/tests/test_identity_mapping_db.py`、`tests/e2e/audit-neon-handoff.spec.ts`。

**Interfaces／設計決定：** 遷移工具預設 dry-run，input 每列 canonical_user_id、舊 issuer/sub、新 issuer/sub、核實 proof_ref；output 是 linked／unmapped／collision／disabled 及前後對帳數。apply 必須明確指定目標與受控權限。OAuth 重新登入／password reset 只建立身份證明，不按 email 自動合併。

- [ ] **1.** NA06/NA27：密碼舊戶、新 OAuth、同 email 異人、已停用會員、多 workspace 角色；assert 保留每個 user／membership／owner／歷史 actor。
- [ ] **2.** 實作 dry-run 與 idempotent link rehearsal；重跑不增加重複 mapping，衝突不部分提權。不得假設可匯出 Auth0 密碼。
- [ ] **3.** 使用虛構 24 公司及 operator／reviewer／admin，完成 Offer→ICP→Research→Buyers→Contact fixture→Draft edit→Grounding→Approval→Export→人工 Outcome，刷新後核對資料。
- [ ] **4.** 只向已核准測試帳戶做 email／OAuth 演練；未有寄信授權時輸出待辦與收件人名單，不自動發送。
- [ ] **5.** 產生異常帳戶清單、support 步驟與回退演練證據。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N06` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_identity_mapping_db.py；pnpm exec playwright test --config playwright.neon-auth.config.ts tests/e2e/audit-neon-handoff.spec.ts。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 關閉新身份使用；不重建 user、不撤回業務寫入；保留 proof 與對帳記錄。

**執行界線：** 工具與 fixture 可先做；實際帳戶 link／驗證信須有對應授權。

### Q11 · 單一現況與分能力release gate

**交付：** PR-00／PR-22／Release-Gates｜**問題：** F10;F13｜**優先：** P1｜**前置：** 無

**證據／驗收案例：** E02;E03；R01;R02;R03;R04;R05;R06。責任角色：Release owner＋SRE。

**檔案邊界：**

- 修改／核對：`docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md`、`docs/buyeros/remaining/API_OPERATION_STATUS.csv`、`docs/buyeros/RELEASE_READINESS.md`、`docs/buyeros/provider-capabilities.md`、`services/api/buyeros_api/api/routes/health.py`、`services/api/buyeros_api/providers/base.py`、`services/api/buyeros_api/providers/search.py`、`services/api/buyeros_api/providers/contact.py`、`services/api/buyeros_api/providers/model.py`、`features/live/operations.tsx`。
- 新增：`docs/buyeros/CURRENT_STATUS.md`、`docs/buyeros/runbooks/2026-10-03-audit-release.md`。
- 測試：`services/api/tests/test_api_routes_contract.py`、`tests/e2e/audit-operations.spec.ts`。

**Interfaces／設計決定：** 單一 current-status 表：source_sha、deployment_sha、schema_revision、runtime_role、worker selector/epoch、provider能力、case結果、checked_at、owner、evidence。capability 顯示 status/reason/checked_at/owner_role/next_action；unknown 絕不顯示 ready。F10只有在所選provider adapter、價格/配額、worker啟用和有界canary全有證據時才可關閉；尚未選定供應商則維持blocked，不能只做readiness UI就宣稱真研究/contact可用。新增 API 要更新 contract、generated routes、role mapping 和 ledger 分母。

- [ ] **1.** PR-00 先建立凍結baseline與任務記錄，舊Current標historical；保留原21F/98cases、verified/code-only/blocked/not-tested，不修改原證據包。
- [ ] **2.** capability/Readiness UI 顯示具體阻擋原因及下一步，沒有負責人名字時用責任角色，不捏造聯絡人。
- [ ] **3.** R01–R06：唯讀核對deployment/schema/role/selector/epoch/outbox；0036存在於repo不代表已migrate；78 public operation逐項維持驗收狀態，不批量設verified。
- [ ] **4.** 分別完成 Auth gate（N05/N06/回退）、Daily-work gate（功能/RLS/UX）、Provider gate（真能力與quota/cost）、Recovery gate（restore/retention/epoch/unknown hold/alerts）。各gate只依自己的證據，避免把可用auth部署綁到尚未啟用付費provider。
- [ ] **5.** 選定且已授權的provider若尚無實作，按既有providers/search.py、contact.py、model.py介面逐一補adapter及contract tests，不同provider分PR，沿用Q11子項；unknown結果reconcile、價目/配額/成本上限通過前不入live allowlist。每個release附readback/rollback/剩餘blockers；全產品可用性只在完整WF03及必要P1通過才宣稱。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q11` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** CONTRACT；API-TEST tests/test_api_routes_contract.py；按 R01–R06 runbook 保存對照與演練證據。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 回退新增文件/UI；啟用能力按各service runbook回復，不自動切換執行引擎。

**執行界線：** PR-00記錄可立即做；正式 DB/worker/readback與recovery未有證據時其gate維持blocked。

**補充：** 此任務先開始、最後分能力收尾；N07依Q11-Auth gate，Q11本身不設N07前置，無依賴循環。

### N07 · 受控Neon切換及Auth0退役

**交付：** PR-23／Release-Auth｜**問題：** F20｜**優先：** P1｜**前置：** N06、Q11

**證據／驗收案例：** E02;E09；NA28;NA29;NA30。責任角色：Release owner。

**檔案邊界：**

- 修改／核對：`docs/buyeros/runbooks/release.md`、`services/api/buyeros_api/settings.py`。
- 新增：`docs/buyeros/runbooks/neon-auth-cutover.md`。
- 測試：`tests/e2e/audit-neon-session.spec.ts`、`services/api/tests/test_neon_jwt.py`。

**Interfaces／設計決定：** 四狀態：R0 Auth0 only → R1 有截止期 dual trust／測試 cohort → R2 Neon default＋有限 Auth0 rollback → R3 Neon only。每一步記錄 source/deployment、branch/schema、mapping 摘要、UTC deadline、owner、觀察與回復條件。新 Neon-only user 先納入恢復名單；沒有恢復方法前不得退役舊入口。

- [ ] **1.** 在隔離環境跑 NA28/29/30：R3 未過期 Auth0 token 仍拒絕；rollback 後既有新業務寫入不丟失，新 Neon-only 帳戶有可用恢復路徑。
- [ ] **2.** 準備完整 diff、測試、mapping 對帳與實際可執行回退 runbook；取得 production 切換授權是最後一步。
- [ ] **3.** 已獲授權時按 cohort 切換，每步驗證 roles、scope、研究去重、draft approval、export。建議觀察 24 小時；樣本不足時明列，不能以零流量宣稱成功。
- [ ] **4.** 可驗證身份錯配、權限擴張、重複經濟意圖或關鍵登入失敗立即中止 rollout；依 runbook 回退。
- [ ] **5.** R3 後測 Auth0 拒絕，再清理舊 callback／secret／依賴。刪 secret 是退役動作，不能在 R1 預先做。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `N07` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** 重跑 NA28–NA30 的指定 tests；將 canary request IDs、登入分母／成功數／錯誤分類及 readback 寫入 release record。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 以配置／部署回退，絕不整庫 restore；有限度恢復 Auth0 信任需新期限，不默認永久 dual。

**執行界線：** 需 N05/N06 全通過、Q11-Auth gate、production 授權、可用帳戶及回退演練；不能以 code merge 當正式切換完成。

### Q16 · 調查workspace500根因

**交付：** INV-01｜**問題：** F21｜**優先：** P1｜**前置：** 無

**證據／驗收案例：** E07；U16。責任角色：SRE／Backend。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/api/deps.py`、`services/api/buyeros_api/api/app.py`、`services/api/buyeros_api/api/errors.py`。
- 新增：`docs/buyeros/incidents/2026-10-03-workspace-500.md`。
- 測試：`services/api/tests/test_api_app.py`。

**Interfaces／設計決定：** 調查鍵：request ID `1d123054-2633-40b7-8e07-b6aed83dad98`，UTC `2026-10-02T19:40:34Z`，deployment `dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp`。已知只有 OperationalError；同期JWKS200，無證據把根因指向Auth0、Neon冷啟動或pool耗盡。

- [ ] **1.** 先取同時段 redacted DB/driver error code、timeout class、連線初始化、schema/role、pool與request timing；只讀，不列出DSN/secret/原始參數。
- [ ] **2.** 建立 hypotheses 表：證據、可反駁条件、最小重現、結論；區分首次500與之後無membership兩個問題。
- [ ] **3.** 日誌保留期已過時，明列無法取回，準備有上限的新增診斷 patch供審閱；不宣稱已找到歷史根因。
- [ ] **4.** 完成可確認根因或明確blocker；只在得到重現/足夠原因證據後解鎖Q17。
- [ ] **5.** 如果只做診斷文件，不製造無意義紅測試；新增logging時測redaction與request ID關聯。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q16` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** 唯讀比對原請求與有界重現；如修改診斷logging則 API-TEST tests/test_api_app.py。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 純只讀無產品回退；診斷patch可revert，不刪原錯誤證據。

**執行界線：** 目前受阻：缺 OperationalError 底層診斷；此阻擋不能阻止其他獨立修復。

### Q17 · 按已確認原因修復workspace500

**交付：** PR-24（條件式）｜**問題：** F21｜**優先：** P1｜**前置：** Q16

**證據／驗收案例：** E07；U16;P01;P02。責任角色：Backend／SRE。

**檔案邊界：**

- 修改／核對：`services/api/buyeros_api/api/deps.py`、`services/api/buyeros_api/api/routes/workspaces.py`、`services/api/buyeros_api/settings.py`。
- 新增：`services/api/tests/test_workspace_error_recovery.py`。
- 測試：`services/api/tests/test_workspace_error_recovery.py`、`services/api/tests/test_workspace_listing_db.py`。

**Interfaces／設計決定：** 實際修改檔案由 Q16 已確認原因選擇；上列是候選邊界，不能全部預先重構。連線、查詢、schema/role或timeout修法只做對應最小變更。安全GET重試至多一次且有總timeout；結構性schema/permission錯誤不重試；POST/PATCH不盲重播。

- [ ] **1.** 把Q16觸發條件變成可重現的 `U16_workspace_read_recovers_from_confirmed_failure`，先記紅測試；無根因時保持blocked。
- [ ] **2.** 實作最小修正，區分可重試transport錯誤與永久設定錯誤；不預設增加pool。
- [ ] **3.** 測原始failure成功恢復、永久錯誤有明確分類／request ID、retry有上限；無membership仍顯示真實空權限。
- [ ] **4.** 在有代表性的冷暖read重跑U16/P01/P02，報分母與環境；一次成功不是可用率證明。
- [ ] **5.** 保存精確config/code diff及rollback；移除不再需要的敏感/高量診斷。
- [ ] **6. 提交及交接：** 以上驗收通過後提交一個可review的commit／PR，標 `Q17` 及F-ID，附red/green log、case結果、未測限制及rollback。缺外部證據只標相應gate受阻，不報已上線。

**驗證：** API-TEST tests/test_workspace_error_recovery.py tests/test_workspace_listing_db.py；按P01/P02有界重測。成功＝測試 assertions 通過、必要DB零skip、無0-tests假通過；具體live/rehearsal另有artifact。

**回退：** 回退根因所對應config/code；不還原DB、不新增會員、不擴大JWT信任。

**執行界線：** Q16根因及重現未完成前不得開寫猜測修法。

## 7. 八模組與完整日常流程驗收

| 模組 | 預期交付／主要任務 | 不能省略的驗收 |
|---|---|---|
| Overview | Q14 scope統計；Q09今日待辦入口 | A專案0／B5，卡與列表一致，權限不足清楚 |
| Offer | Q09保留partial-save與version提示 | WF01失敗重試不多建project；WF02舊ICP不得沿用 |
| Buyers | Q05同事分派；Q06有界poll；Q08 manifest；Q09主表/drawer | 100/101、1000/1001、10k；跨頁選取/排除清楚；逐列結果可追 |
| Results | Q09用途與人工outcome清楚 | 分母0、UTC邊界、修正鏈、buyer/owner/time filter |
| Research runs | Q04同意圖重試；Q11能力前置 | lost202只有1run；ICP/budget/provider未ready不提交 |
| Drafts | Q15 dirty；Q07模板文案；Q12人工來源覆核 | 保存→覆核→exact review→approve→export，同revision與policy |
| Settings | Q02分頁/身份/受控onboarding | 250會員、最後admin競態、revocation、無普通bulk提權 |
| Operations | Q03結果ID及分頁；Q06 summary；Q14 scope；Q11 readiness | 真payload、21/101結果、actor/tenant guard、可操作原因 |

WF03／NA27使用虛構24公司、example.invalid及隔離operator/reviewer/admin，透過UI建立Offer、批准ICP、研究fixture、review買家、建list/分派、contact quote/confirm fixture、人工改draft、來源覆核、批准匯出、手動outcome。重載與跨角色交接後資料一致。delivery仍403。真provider canary、實際員工UAT、production smoke各自記錄，不能用mock outcome代替。

## 8. 性能與準確率門檻

以下沿用稽核的**建議驗收目標，並非既有SLA或已量到的值**；執行前凍結環境／資料／門檻，不在測完後調低來製造通過。

| 檢查 | 方法 | 建議通過條件 |
|---|---|---|
| P01/P06 UI | HK測點、桌面/390px、冷暖各30次；登入另算 | 暖ready p95≤2s、冷≤4s；LCP≤2.5s、INP≤200ms、CLS≤0.1；同報p99/錯誤/n；小樣本p99標不穩定，lab≠RUM |
| P02/P03 API | 1k/10k buyers；1/10/100 workspaces；1/10/25 actors，10分鐘階梯 | 暖read p95≤800ms、p99≤1.5s、5xx<1%、tenant錯配0；SQL/bytes/pool分層 |
| P09/P10 directory | W1/10/100/1000，可見membership數固定 | SQL次數與無關W無關；建議熱路徑≤6；EXPLAIN、role、pool-reuse安全測試 |
| P04 bulk | 1000 results、RTT2.5s、10 views、60秒＋hidden/429 | 每view≤1個progress request；未開results不抓歷史頁；hidden停止 |
| P05/P08 worker | 10 workspaces長短jobs，30分鐘有界負載＋30分鐘idle | 無starvation、無無意義idle loop；queue wait/oldest age/hold/cost皆有數據，支出不超已准額 |
| A03–A08 research/contact | ≥200公司雙人goldset，company-level holdout，3次重跑 | 暫定match precision≥95%，同報recall/coverage/needs_review/CI；錯公司/跨tenant/unsupported引用在測試集中0 |
| U12 usability | 3–5員工，各5項固定任務 | 完成≥90%、錯scope寫入0；比較前後時間/失誤，不能只報主觀喜好 |

goldset缺真provider時保留not-tested。聯絡email格式合法、provider_marked_valid、實際任職／公司關係三種指標分開；不以發真信測準確度。真資料來源可能過期或含prompt injection，A04–A06須拒絕錯實體、無效引用及來源指令。

## 9. Neon Auth的精確邊界與官方參考

2026-10-03重新查閱官方文件：Neon Managed Better Auth瀏覽器採session cookie；外部API用`authClient.token()`取得JWT。目前文件記EdDSA/Ed25519、15分鐘有效期、issuer/audience為Auth URL的origin，JWKS位於完整Auth base URL下。這些值仍須N00用目標環境核對；不能把base URL與origin混為一談，也不能只改AUTH0_ISSUER。

官方Next.js SDK提供server handler與cookie整合；**文件支援標準Next.js不等於已證明本repo的Vinext/Nitro可用**。N00必須跑built output。Neon JWT role不表示BuyerOS權限；本計劃的canonical mapping是BuyerOS自己的遷移設計。

- [JWT官方文件](https://neon.com/docs/auth/guides/plugins/jwt)
- [Next.js Server SDK](https://neon.com/docs/auth/reference/nextjs-server)
- [Production checklist](https://neon.com/docs/auth/production-checklist)

立即權限撤回依active mapping/membership及domain授權；已發JWT的密碼學有效期與session logout分開。若產品要求所有token即時失效，須另加明確server revocation/introspection設計與測試，不宣称logout天然做到。

## 10. 完成定義、恢復與維護

每個PR附：目的與F-ID、實際changed files、source SHA、命令與環境、pass/fail/skip、case及artifact、schema/API相容性、回退方法、未測範圍。tracker分開 `code_status`、`verification_status`、`release_status`；code merged不能填production verified。

任務受阻時先完成可做的code/fixtures/docs，列出具體缺項、owner角色、解除條件，继续無依賴工作。Q16沒有底層錯誤時不執行Q17猜測修復；N00不相容時不硬切Neon；缺DB時不把純mock升格為RLS驗收。

DB採expand/backfill/read-switch，身份及bulk/draft資料都是additive；回退程式時保持舊版讀相容。禁止用整庫restore撤回auth，避免丟失切換後業務寫入。provider未知副作用、hold與outbox不可在rollback时盲重播/釋放。

維護交付包括：共享型別／query builder／poller／intent／dirty guard、單一current status、可操作錯誤碼、分能力readiness、原case ID可重跑證據。不要以大量抽象或全站重構替代這些具體結果。

## 11. 建議首輪執行指令

把本計劃、原證據ZIP及同包的 `BuyerOS_GPT6.1Sol_Start_Prompt_2026-10-03_zhHK.md` 一併交給Codex GPT-6.1 Sol。第一輪範圍固定為Q11-baseline＋Q01/Q03/Q04/Q15；完成四個可review PR後報告驗收，再按波次續做。首輪不得把Neon切換、正式migration或provider activation夾入同PR。

本交付完成的是實作計劃及覆蓋核對，沒有執行上述產品修復或再次聲稱網站驗收通過。
