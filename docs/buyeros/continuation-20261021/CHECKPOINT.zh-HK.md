# T21 本機候選驗證與接續點

更新：2026-10-21T22:55:39.159178+00:00。本文件是本機工程交付；沒有 commit、push、merge 或部署。

## 可核對版本

- 專用 branch：`codex/t21-workflow-20261022`；HEAD/base：`c529dc8523a1d82da91243aaf33ea680a574277f` 加未提交修改。
- 修改／新增 source+test 輸入共 77 檔，SHA-256：`b4d2d92053314fd712cc655e116fedd22496a959b3669b6f590a59345cbceb33`。
- 完整 emitted artifact：2243 個實體檔案、24 個內部 links；每個 link target 均在 output 內並已納入 hash。
- Artifact tree SHA-256：`e4595d50f291ce3e9ada3d9ee890718bbd27d7ae07d64695634677264b8553af`。不是只用不變的 entry glue hash。
- 最後risk回歸前後code/test輸入完全一致；R2以後只改playwright.t21-risk.config.ts，完整frontend5／controls5及risk92已重跑。所有產品runtime source及emitted artifact files／links相等；文件整理不屬於執行輸入指紋。
- 完整 API 開始前的保留 snapshot 與最後候選的 backend/generated 六個變更檔逐一 hash 相等；其餘 backend/worker 沿用相同 base，後續 frontend 修正沒有冒充重新執行 backend。
- GitHub main 及 run39111507046 重新唯讀核對：仍為 c529dc85，12/12 jobs 成功；不屬於新 diff CI。
- 正式 alias 仍回傳 dpl_DcRxZFpfV6zHYbQyP6rmkxWQvJbc、CLI／READY；withGitRepoInfo 未返回 gitSource。正式 UI/API/worker SHA、schema 仍 unknown。
- 原 checkout main 3f10f419 保留。沒有把原 checkout 或 b65823aa 的局部分支當成新候選版本。

## 實作與修正

- T21-01/02：持續的 /app layout 與 auth surface 分離；單一雙語首屏表單、native recovery／焦點、重複提交保護、去敏 diagnostics；exact trusted branch social-init contract。
- T21-03：Preparation/Draft 多 editor 守衛；公司／版本／分頁／sidebar／scope／logout／reload／Back-Forward／refresh 明確 Save/Discard/Cancel；unknown 沿原 intent/readback，queued action 固定原 preparation ID。
- 強制 expiry 清除保護資料；只保留一般 in-memory 提示旗標，不儲存 preparation 文字。提示明確說明 submitted save 可能已完成，重新登入先查原 operation。
- Chromium／Firefox 保留精確 early replay guard；WebKit 沿用既有 guarded restore-before-decision，避免 canceled traversal cursor/key 不一致；不把引擎識別用於權限。
- /app 與直接 auth 頁的語言選擇等待 client hydration／bootstrap readiness；原 public12 的繁中跨頁斷言保留。三項實際SSR RED 明確捕捉舊控制項沒有disabled。
- T21-04：公司查詢 page24／query200／snapshot cap1000、deep-link direct read、保留 query 的獨立 retry、abort/sequence fence。
- T21-05：公司 domain／fit／來源數與 freshness，缺少市場資料明示 Unknown；受限成員姓名及 Mine/Unassigned，沒有擴大目錄權限；owner_unassigned API/types/schema 無 migration。
- T21-06：摘要直接衍生 canonical policy terms；exact JSON/hash 預設折疊；authority、revision、hash、expiry/refusal 不變。沒有真實 policy activation。
- T21-08：同一 UI-created project 串起 offer v1/v2 → reviewer → fixture research/owned Celery → buyer/evidence → draft → exact approval/export → outcome/reload，附 durable IDs 及實際下載 hash。

## 實際最終測試

| 套件 | 結果 |
|---|---|
| 完整 API | 3,005 PASS；0 failure/error/skip |
| 完整 worker | 469 PASS；0 failure/error/skip |
| 完整前端 | Node265、serverSDK3、policy client11、六個 bare scripts 全通過；typecheck/lint/portable build exit0 |
| 發布／CI 契約 | release183、C61 foundation163、其他 discovery/registration/types/routes 全通過；controls9 commands exit0；新 navigation/protocol14 個 JUnit cases 全通過 |
| Native | 46/46；含原19 mandatory subset、準備內容21、daily9、evidence5、workflow4、budget4、scale3 |
| 其他 Chromium | policy9、原包 public12、合成Auth5、SDK9 均通過；risk92分四個獨立target，各完整family執行並核對ID集合完全等於原92項 |
| 跨引擎 | Chromium/Firefox/WebKit 每個原包 public12＋同專案旅程1 通過；Firefox/WebKit 各額外 history3 通過 |

完整 cwd/argv/exit code/elapsed/raw log 在 test-commands.json；JUnit／Playwright JSON／browser traces 在 worktree evidence。樣本重疊，不相加作不重複測試總數。
API 原始報告保留1,182項 warnings、worker14項 warnings（主要 Python asyncio/deprecation）；build／fixture warnings 亦保留，沒有把 warnings 改成跳過。
本機 Node24.18.0／Python3.14.6／已鎖定依賴；與 hosted runtime 不等同。

## 固定延遲選擇量測

| 記憶體公司數 | n | p50 ms | p95 ms | 初始清單請求 |
|---|---|---|---|---|
| 100 | 10 | 829.26 | 873.90 | 2 |
| 1000 | 10 | 847.92 | 863.52 | 2 |
| 10000 | 10 | 843.36 | 861.38 | 2 |

每個transport request額外100ms；每頁24／snapshot cap1000。原始30個樣本與attachment對照見performance-fixtures.json。這不是field Web Vitals或DB容量。

## 原始案例與未完成驗收

- 72個原 N21 IDs 全保留：49 PASS_LOCAL、16 PARTIAL、7 BLOCKED。原 audit_snapshot 沒有改寫。
- PASS_LOCAL 僅限逐案列出的合成／隔離斷言；不是72個原人工案例全部已執行。16個 PARTIAL 明確保留未涵蓋組合。
- F01–F24、F13/F25–F34 原資料保留；F35–F38 是新增本機發現；D21 是開發過程回歸。F26 只完成 contract 修正，真實 Google／部署端原因仍未關閉。
- 尚缺正常公司 Google/branch JWT/FIMMICK membership、同一新候選 hosted 身分、公司帳戶 UAT。
- 尚缺真人 usability、人工 screen reader/zoom、實體 Safari/iOS/Android、60公司/100claims雙人 goldset 及 field LCP/INP/CLS；不能宣稱 world-class／完整 WCAG AA／正式就緒。
- 100/1000/10000各n10及100ms latency的選擇測試，均在測試記憶體實際建立對應數量的不同公司ID並作搜尋／分頁；不是正式 DB capacity 或實際10000筆DB寫入。

## 證據限制及保留

- RED、失敗及 setup logs 全保留；`history-replay-webkit-green` 名稱雖含 green，實際2 PASS/1 FAIL，已由最終新 run取代，沒有改寫舊結果。
- 早期 thin-journey-2 trace ZIP 因重名未完成封存；raw log保留，後續新run有獨立zip。不能稱全部早期 trace 均已封存。
- 第一輪policy9中兩項失敗：政策模式誤載lead fixture令合成requester降為operator，以及舊測試沒有展開canonical details。修正僅在test config／spec；不修改產品權限或現實角色。
- 第一輪risk92：84 PASS/8 FAIL；七項不同family共用保留recipient資料造成natural-key衝突，改以獨立DB執行完整family，沒有刪除／改寫原contact來遷就測試。N11故障注入改為在初始驗權完成後，只hold一次手動recheck，保留精確重複請求斷言。
- risk-r2彙整曾在啟動fixture前拒絕較早79項discovery；舊檔及失敗保留。新全量discovery92與第一輪實際執行92 IDs完全相等；最終risk-r3四target的union再次核對相同92 IDs，沒有減分母。
- 早期legacy risk/journey的allocator將CID receipt寫在臨時目錄，未搬入主evidence；不重構歷史receipt。新run另保留經實際Docker metadata觀察的精確CID與移除結果；pre-client gate本身不變。
- 錯 cwd、缺 fictional compile Auth、空 bootstrap DSN、archive collision、CRLF patch syntax 等 setup 問題與真正產品 RED 分開。
- 本輪只建立/清理自己 metadata-gated 的 disposable Docker DB及旅程服務；沒有連正式 DB或讀取真實 secrets。
- 清理核對限明列容器IDs、marker及UI/API ports；沒有另作volume/cache prune，不宣稱舊匿名volume全部已刪除。
- 原 checkout、既有206個未追蹤檔案、Native branches、backup及24/57 packet保留；.gitignore/lockfiles 無修改；最終 preservation receipt另記核對範圍。

## 下一個明確 checkpoint

1. 審閱 reviewable.patch 與 source-file-manifest.json；若批准，只 commit/push 指定 source/test/docs 到此專用分支並建PR，核對同一 head全部12 jobs。今輪未執行。
2. 要做正常公司 UAT，另批准固定候選 SHA 的隔離 hosted/本機入口、精確 DB/Auth branch/issuer/audience/workspace 及有限讀寫範圍；不可混用舊 b658 build或管理員/test Principal替代。
   本輪 artifact 採用明確 fictional compile Auth，不能直接拿去部署；正常 UAT 必須按核實設定另建 artifact 並核對同 source/provenance。
3. 首先唯讀核實 willylai@fimmick.com 的正常登入、JWT 與 FIMMICK membership；若 identity bootstrap仍需apply，保留獨立dry-run receipt核驗與apply批准門檻，不能用此候選繞過。
4. 身份通過後才另批合成業務UAT：建議上限1 project、2 offer/ICP版本、2公司、4來源、2 preparation版本、1 draft/2修訂及1 approval/export；實際workspace、用途政策、角色及run ID先確定。只清理/封存本run明列資料並保留immutable audit，不涉及原24/57；付費provider及真實寄送仍為0。
5. 正式 migration/grant、受保護contracts/簽署、fresh restore point與部署各另行批准；正式 schema本輪未讀，不把歷史0054當作當前。還原會捨棄還原點後新寫入。

不 commit/push/merge/deploy、不修改正式 DB/Auth/grant/Secret，不提交24/57，不啟用付費research/enrichment/寄信/自動outreach。保留 worktree，等下一個具體授權；沒有背景持續工作。
