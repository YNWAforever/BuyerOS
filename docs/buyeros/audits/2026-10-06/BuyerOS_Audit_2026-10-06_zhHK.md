# BuyerOS 網站、後台及研究至外展流程稽核

日期：2026-10-06（UTC；香港 UTC+08:00）。證據整理時間：2026-10-06T15:54:37.850299+00:00。範圍：[GitHub](https://github.com/YNWAforever/BuyerOS)、[正式網站](https://buyer-os-nu.vercel.app/) 及指定工作區 `900cd19b-4e03-4446-bdd6-7cb199d96060`。

## 判斷

**目前不能確認整個研究及外展流程可正式使用；根據正式來源，真實研究與站內發送仍未完成接駁。** 開發分支已有大量業務修復及隔離測試證據，但正式站仍部署10月3日稽核時的版本。需要先交付已做修復、完成真實整合及帳戶驗收，才可宣稱整段流程可用。

本次正式後台登入被網站以「Wrong email or password」拒絕，故八個登入後模組 **0/8 完成正式端到端操作**。這是本次存取限制，不能推斷八個模組均故障，也不能把上次無會員問題當成這次再次觀察到的結果。沒有修改產品程式、會員、正式資料、schema或部署，也沒有真實研究消費或寄信。

主要結論：

1. **研究不能只靠填API key解鎖。** `selected_run_capability()`仍回傳`None, production`，`admit_run()`回503 `PROVIDER_UNAVAILABLE`；provider allowlist為空。執行層亦有blocked handler。需完成adapter、選擇器、報價／capability及worker接駁。此結論為程式證據，未在正式帳戶重現POST。[E07]
2. **站內發送未實作成可用交付。** `/drafts/{id}/deliver`固定403 `DELIVERY_DISABLED`。已有隔離流程可驗到審批、授權下載及手動記錄結果；沒有證據支持「已自動送出、送達或回覆同步」。停用邊界是正確防護，不能直接刪掉403來完成需求。[E03,E07]
3. **Auth0→Neon Auth未切換。** live仍實際跳Auth0；開發分支的Neon SDK與harness屬兼容spike，production auth檔案仍使用Auth0。N00完整真實兼容及N01–N07遷移仍未完成。[E02,E06,E07]
4. **業務修復有進展但未上線。** 最新CI8個job成功，本次44項重點unit全過；研究重試、成員分頁、批量結果、草稿防遺失、重新來源覆核及10k manifest均已有程式／fixture證據。正式來源未包含這些修復。[E01,E03,E04,E07]
5. **工作區查詢效能問題仍在。** reviewed branch與main的`workspaces.py`相同，每次列舉所有工作區再逐一查membership，最後才切頁。既有實際PG16測量SQL隨W=1/10/100/1000增至4/22/202/2002，沒有通過<=6及不隨無關W增長的門檻。這不是本次正式站latency測量。[E06,E07]

## 版本與證據層次

| 層次 | 本次確認 | 含義 |
|---|---|---|
| main | `a78859fe474f5722be3755b10e2586436b53bf97` | 仍為上次正式來源 |
| production | `dpl_7A95afQdDSUsaPRw2RnPFouQ1hEp`，READY，alias buyer-os-nu.vercel.app，來源main/a78859f | READY只證明部署完成，不等於業務ready |
| reviewed開發head | `bbaf8ecd1f7ef755b89cdc29c8e01c505ad96442` | 稽核其業務修復、測試及未完成Neon spike |
| PR #11 | 2026-10-06 15:20:55Z merged到`codex/n00-native-ipc-isolation`，merge `05d8a4a` | **沒有合併main**；內文仍寫Draft屬過時敘述，採平台實際metadata |
| CI37403378632 | 8/8 jobs success；checkout `767f13e` | git核對其tree、bbaf8ec tree及05d8a4a tree完全一致：`7c06894c7664aa15661b1a1249e85338c16ac2e9` |
| contract | main78；開發84 operation IDs | 84是來源清單分母，不是84項正式實測通過 |
| schema | 開發有新增`0037_bulk_manifests` | 正式DB migration head／runtime role／worker selector與epoch本次未讀回 |

開發的原25任務仍保留：Q01–Q08、Q12、Q14、Q15共11項標fixture或integration-fixture verified；Q09/Q10/Q11及N00仍部分完成；Q16根因受阻；N01–N07、Q13、Q17在本checkpoint標outside-current-scope。這是分支狀態聲明，不能轉成正式完成率。另有peer Q13紀錄，**沒有在本次reviewed樹整合**，未獨立驗證其分支。

證據用語：`verified`只適用實際取得的metadata／測試結果；`code-only`為程式可推導行為；`live-only`為當次頁面觀察；`blocked`為缺帳戶／外部驗收條件；`not-tested`不等於通過。歷史圖片、基準與原98案另標，原始actual/result未覆寫。

## 八模組與業務資料鏈

| 模組 | 路由 | 員工目的 | 開發狀態／剩餘工作 | 關聯 |
|---|---|---|---|---|
| Overview | `/app` | 工作優先次序、失敗工作及用量 | Q14正確project範圍已有；其餘卡片仍有通用Operations入口／缺數量，需真人任務驗收 | F14;F17;F18 |
| Offer | `/app/discover/new；/app/discover/edit` | offer→facts→ICP核准→research intent | 研究防重複已有；實際provider resolver仍None，不能完成真實研究 | F08;F10 |
| Buyers | `/app/discover` | 找公司、證據、人工審核、分派、清單、聯絡資料 | 同事搜尋／分頁／10k manifest有fixture證據；contact provider未核實啟用 | F06;F10;F11 |
| Results | `/app/results` | 結果篩選、成本、manual outcomes／更正、匯出 | 有hosted workbench fixture；真實結果與成本來源尚未驗收 | F12;F14 |
| Research runs | `/app/runs` | 進度、事件、取消、失敗恢復、重開讀回 | run subscriber／intent檢查通過；生產search/fit path仍blocked capability | F07;F08;F10 |
| Drafts | `/app/outreach` | 生成→編輯→來源重核→精確審批→授權匯出 | 固定模板如實標示；dirty/re-ground已有；delivery仍403；長審批表單待簡化 | F09;F14;F16;F19 |
| Settings | `/app/settings` | 成員、角色、語言、budget/policy／sender設定 | Q01/Q02改善已有；只改現有會員，不等於邀請／Neon身份遷移完成 | F01;F02;F03;F04;F20 |
| Operations | `/app/operations` | 能力／readiness、工作及每筆結果、失敗重試、audit | Q03/Q06摘要輪詢與正確分頁已有；provider仍unconfigured/disabled；production schema/worker未讀回 | F05;F07;F10;F13;F21 |

以上路由依來源核對；本次未登入後逐頁開啟。正式公開`/`與指定`/app`均只顯示登入入口。[E02]

完整驗收必須追同一組資料：operator建立offer與可用事實 → reviewer核准ICP → operator設定預算並啟動研究 → DB／outbox／worker／provider對帳 → 公司與證據／fit落庫 → 人工審核買家及聯絡人合法用途 → 生成固定模板或已核准model草稿 → 編輯後重新來源覆核 → reviewer審批精確revision、recipient、sender及policy → 授權匯出 → operator追加手動結果／修正；admin在Operations查工作、每筆結果、audit及能力狀態。不能停在按鈕顯示成功。

「完成外展」需分清交付邊界：現有候選支援的是**準備、審批、匯出及手動成果紀錄**。若需求包含站內寄信、bounce／unsubscribe／reply同步，A26-12是新增整合工作，不能以目前fixture journey視為完成。

## F01–F22追蹤

所有原F01–F21保留；新增F22交付缺口。没有任何原問題在本次被標為「正式已驗證完成」。這不否定開發分支的有效修復。

| ID | 優先 | 問題 | reviewed開發狀態 | 後續 |
|---|---|---|---|---|
| F01 | P1 | 工作區存取與恢復 | 恢復 UI 已寫；真實會員／工作區驗收仍受阻 | Q01;A26-02 |
| F02 | P2 | 無工作區時不能切換語言 | Q01 已提供本地語言偏好及延後持久化；待部署驗收 | Q01;A26-03 |
| F03 | P1 | 成員清單只取首100筆 | 20筆分頁、total及搜尋已加入；既有250成員 fixture證據 | Q02;A26-03 |
| F04 | P2 | 成員辨識／入職支援不足 | 姓名／完整ID／role編輯已有；只管理現有會員，完整邀請入職流程仍未交付 | Q02;A26-02;A26-09 |
| F05 | P1 | Operations錯用buyer_id及只顯示首20結果 | 改用生成型別id、20筆分頁及舊請求取消；待正式驗收 | Q03;A26-03 |
| F06 | P2 | 批量分派／確認容易出錯 | 同事搜尋、精確確認及未知結果保留已有；真人可用性待驗 | Q05;A26-03;A26-09 |
| F07 | P1 | 輪詢重抓全部結果及重疊請求 | 摘要輪詢、單一請求、取消、隱藏暫停及退避已有；本次11項poller unit通過 | Q06;A26-03;A26-10 |
| F08 | P1 | 研究未知回應重試可能建立新意圖 | 穩定fingerprint/key及同意圖retry已有；本次3項intent unit通過 | Q04;A26-03 |
| F09 | P2 | tone/objective看似控制文案但不改輸出 | 改為如實標明免費固定模板，語言只改框架；未新增真實LLM文案能力 | Q07;A26-03;A26-09 |
| F10 | P1 | 真實研究／聯絡整合及寄送未啟用 | 同樣未啟用；ready提示／責任角色較清晰。不是填API key即可完成 | Q11;A26-05;A26-12 |
| F11 | P2 | 一般snapshot只容納1000筆 | 新增上限10000的凍結manifest；10001拒絕、不截斷；0037未確認正式應用 | Q08;A26-03 |
| F12 | P1 | 真實準確度／現場效能未量測 | 離線評估工具已有；假資料分數不代表真實準確度 | Q10;A26-10 |
| F13 | P2 | 狀態文件與實際交付不一致 | CURRENT_STATUS累積多個Current；PR內文Draft已過時但平台已merged至非main | Q11;A26-01 |
| F14 | P2 | 每日工作台／手機／審核效率不足 | 已有中英／鍵盤／手機fixture證據，但長表單、UUID、source段落offset仍增加員工負擔 | Q09;A26-09 |
| F15 | P2 | 初始化短暫顯示登入未設定 | 新增initializing狀態及明確錯誤；待部署驗收 | Q01;A26-03 |
| F16 | P1 | 手改草稿後不能完成來源覆核／審批 | 新增不可變人工來源覆核、Unicode段落及精確revision/hash；不等於機器核實語義真偽 | Q12;A26-03 |
| F17 | P2 | Overview顯示project但failed jobs用workspace範圍 | count、清單、deep link共用JobScope；本次3項query unit通過 | Q14;A26-03 |
| F18 | P1 | workspace discovery隨全部工作區線性查詢 | reviewed branch也未改；歷史PG16 SQL gate失敗；另有peer Q13聲明但未在本樹 | Q13;A26-04 |
| F19 | P2 | 刷新草稿覆蓋未儲存內容 | Save/Discard/Cancel守衛已有；本次7項guard unit通過 | Q15;A26-03 |
| F20 | P1 | Auth0→Neon Auth仍未完成 | Neon SDK只供spike；N00尚未完整驗收，N01–N07未在此分支交付 | N00–N07;A26-06 |
| F21 | P1 | 曾發生workspace API 500，根因未明 | Q16仍待SQLSTATE等診斷；不得猜是cold-start或pool | Q16;Q17;A26-07;A26-08 |
| F22 | P1 | 已做修復仍未交付到正式使用者 | PR11已合併到codex/n00-native-ipc-isolation；相同樹不在main；部署缺口確認 | Q11;A26-01;A26-03;A26-13 |

完整來源路徑、GitHub固定commit連結、正式／開發分欄見 Findings CSV；相關程式快照及hash見E07。P1表示影響核心任務或重要資料／交付，並不代表已證實資安入侵。本次未識別新P0；稽核範圍有限，不能解讀為全面安全保證。

## UI／UX與維護建議

1. **今日待辦要直接帶到待辦資料。** Overview的failed jobs已修範圍，但Pending approvals與Unknown provider acceptance仍通往通用Operations，部分卡片没有數量。改用同一server predicate的數量及篩選deep link；清楚顯示範圍和真正資料更新時間，回到工作台保留工作上下文。[F14/F17]
2. **將「設定」與「今日執行」分開。** 既有手機草稿fixture顯示sender表單、草稿清單、正文、UUID／hash及審批／匯出一路堆疊。已驗證sender應摺疊，預設直接進入待審草稿；修改sender仍建立新版本並使舊審批失效。[E06圖片；F14]
3. **來源覆核使用商業語言。** 新功能要求輸入code-point split position、逐段reason及UUID引用，員工成本高。用選取文字拆段、來源標題／網址／日期／摘錄、清楚的事實／非事實分類；服務端仍校驗Unicode範圍、revision/hash、source版本及完整覆蓋。人工勾選不等於AI已驗證語義真偽。[F16/F14]
4. **批量工具應顯示「對哪些人做甚麼」。** 保留freeze/digest/version，但主要確認畫面顯示買家數、負責同事姓名、操作、篩選、排除數、原因及到期倒數；原始JSON／digest置於技術詳情。提供全筆結果分頁、可下載失敗清單、失敗項重新預覽，而不是重跑全部。[F06/F11]
5. **後台維護減少手動UUID輸入。** 成員姓名搜尋已改善，但邀請／入職仍未形成完整產品流程。當前應提供明確管理員入職runbook／存取申請渠道。後續邀請需綁定不可變identity、workspace及角色，不把email相同當身份相同。[F04/F20]
6. **能力及錯誤狀態要給可執行下一步。** 保留readiness與provider capability的區別；告訴員工「研究未啟用，請聯絡release owner」「可先匯出，站內寄送停用」。錯誤顯示安全request ID、是否可重試及如何保留未儲存內容。[F10/F13/F21]

這些UX問題來自source及明確標示的既有fixture圖片，**未聲稱本次真人可用性或正式手機實测**。建議3位代表員工各跑5項日常任務，記錄完成率、時間、求助次數及資料遺失；90%無協助完成可作提議門檻，須由產品負責人事前確認。實際screen reader與200%完整五任務仍待驗。

## 效能與準確度

### 可核對的既有數據

| 測試 | 條件／來源 | 結果 | 可得結論／限制 |
|---|---|---|---|
| Q06輪詢重播 | 邏輯60秒、10個view、1000筆持久化結果、模擬RTT2500ms，owned PG16／真實HTTP計數 | HTTP1250→140；body bytes9293390→69440；DB executes10000→840；result queries2500→0；每view最大in-flight13→1；全200 | 開發摘要輪詢減少工作量；不是正式wall-clock latency改善百分比；本次僅核對歷史檔案及重跑poller units |
| Q10工作區清單 | owned PG16、runtime非owner/NOBYPASSRLS、1 actor有1會員；每W暖30樣本 | W1/10/100/1000：SQL4/22/202/2002；p95=8.772/35.749/270.364/2822.957ms | 歷史本地門檻失敗，source仍相同；不是production p95；n30 p99不穩定 |
| Q10準確度工具 | 8家fictional公司、holdout6、3次fixture predictions | 有precision/recall/coverage/abstention、Wilson95%及零分母处理 | 只驗算術和結構，不能推斷真實市場準確度 |

### 可直接執行的下一輪測試

- **列表／API**：隔離preview以1k/10k/50k buyer資料測搜尋、篩選、offset/limit與total、CSV內容一致；1/10/50並發，冷啟動另記，穩態10分鐘。至少30暖請求僅作診斷；要談尾延遲應收集足夠樣本並交代環境。提議正常列表p95≤1秒、低錯誤率的實際門檻，由團隊按部署資源事前凍結，不能事後改門檻過關。
- **workspace discovery**：沿用既有<=6SQL且不隨無關W增長的明確門檻；檢查多會員分頁、0會員、inactive會員、撤權、租戶context重用及EXPLAIN。UI的allPages不能掩蓋每頁全租戶掃描。
- **輪詢／恢復**：RTT2.5秒、429含Retry-After、503、timeout、hidden/visible、unmount、A→B→A；每view最多一個在途請求、終態停輪詢、舊資料不回寫。這部分本次已有11項unit通過。
- **批量**：100/101同步異步界線；1000普通snapshot；1001/10000 manifest；10001拒絕且不截斷；50筆chunk中斷及恢復、取消後已提交保留、只重試衝突／失敗項；preview/execute lost-response穩定key且一job/outbox。
- **準確度**：建議至少50家按市場／語言／公司類型分層的雙人標註參考集，holdout與調參分離，3次固定預算重跑；逐公司核對名稱／域名去重、引用是否支持判斷、時效／來源撤銷、wrong-company rate及unknown。報numerator/denominator及區間，不只總分。50只是建議起點，不保證統計效力。
- **成本及結果**：UI usage＝ledger的reserved/settled/released；成功、拒絕、unknown、timeout及取消分列；匯出採相同filter／snapshot／revision，不混用未核准聯絡或草稿。provider receipt與成本日誌要能以operation ID對帳。

本次沒有做正式負載測試、Core Web Vitals/RUM/Lighthouse評分、production p95/p99、真實goldset或paid provider測量；不得把本地／CI數字代入。

## Neon Auth 特別處理

保留用Neon取代Auth0的目標。此repo實際是Vinext/Vite加Nitro Vercel輸出，不能因使用Next API就假設官方Next範例已兼容。分支pin `@neondatabase/auth` 0.5.0-beta作開發依賴；這是repository事實，不是「目前最新版」的聲明。

N00已有SDK／cookie／session／diagnostic JWT及受限transport的fixture進展。文件保留原始302轉送診斷失敗；後續也明確區分Neon provider callback與app callbackURL。因此不能把該診斷單獨當成「真實Google登入必然失敗」，也不能刪去失敗測試而宣稱遷移完成。先以目前官方契約及實際部署runtime確認產品必要路徑，給每項診斷清楚適用性，再做獲授權的隔離Neon驗收。

N01–N07應保留BuyerOS canonical users.id、現有membership/RLS、歷史owner/approval/audit/job actor、Cloudflare HMAC及停用delivery邊界；另建可審阅identity mapping。issuer/audience/JWKS/algorithm取實際授權目標的明確配置，不能套用fictional值或只按email連結。完成migration dry-run、雙身份／角色撤銷負測及回退演練後才切換。

官方背景來源：Neon [新Auth架構說明](https://neon.com/blog/neon-auth-branchable-identity-in-your-database)指出每branch有自己的Auth endpoint及配置／資料，可支援隔離驗證。本次搜尋曾混入legacy Stack Auth內容，未用舊Stack範例作新SDK實作依據；兩個API reference在搜尋工具因text/markdown解析失敗，本報告沒有冒稱已重新讀到其全文。具體SDK契約目前以固定版本repo證據及後續官方原文核對為準。

## 本次測試及覆蓋分母

| 類別 | 實際結果 | 範圍 |
|---|---|---|
| 本次main checks | domain11、live adapter74、auth8、run subscription4，4命令exit0 | 來源a78859f；不等於真實provider或UI驗收 |
| 本次開發重點unit | **44 pass、0 fail、0 error、0 skip** | 10檔：access-denial、bulk-confirmation、manifest、grounding、dirty-guard、job-query、member-contract、profile-read、research-intent、job-poller |
| 初次本地執行 | 37個case pass＋1檔因缺react/jsx-runtime不能載入 | 補repo相同版本React後重跑整組；原tap/XML保留；不是產品失敗或紅綠修復證據 |
| Hosted CI API | **812 pass、101 warnings、263.57s，0fail/error/skip** | 從job112075371676原始log核對；checkout tree等同reviewed head；不是本次本地重新跑API |
| Hosted workflow | **8/8 jobs success** | frontend/api/worker/browser-smoke/browser-zoom/browser-continuity/cloudflare-controller/cloudflare-staff-acceptance；job名staff不等於真人UAT |
| 下載continuity JUnit | research4、workbench8、buyers1、buyer-management3、mvp1，均0fail/error/skip | 5個distinct套件；zip有重複XML副本，不重複累加；不同套件可能重疊情境，不與812或44相加 |
| 正式站 | 公開入口及指定後台登入入口；Auth0錯誤訊息 | 八模組登入後完整驗收0/8；0次真實研究或寄送；沒有正式API操作全覆蓋 |
| 操作清單 | 開發84，main78 | 全數列於inventory；屬source inventory，未作84個production API calls |
| 案例追蹤 | 原98＋本次16＝**114案例** | 原欄保留；新增Oct6觀察欄及O26-01–16。不是114項皆已執行／通過 |

本機沒有可用pytest／已設置隔離PostgreSQL，因此不把本次本地unit說成完整API/DB重跑；hosted證據及歷史PG結果各自標版本和來源。未在稽核中降低任何斷言／增加skip以取得綠燈。

## 優先修復／交付順序

詳細13項任務的修改位置、依賴、角色、估時不確定性、驗收及回退見 Remediation Tasks CSV。估時為供排程討論的工程日範圍，不是交付承諾。

1. **先恢復可驗收狀態**：A26-01鎖版本與分支；A26-02由持權者完成正確帳戶登入／membership核對。已有Q修復進A26-03 review與preview，避免重新開發同一功能。
2. **並行推進互不依賴的核心缺口**：A26-04處理workspace查詢；A26-05真實provider接駁；A26-06 Neon migration。Neon spike未完成不應無限阻塞能独立驗收的業務修復；各lane保留其release gates。
3. **先查明500再修**：A26-07診斷證據 → A26-08針對已證實根因修復。現在不能聲稱F21已解決。
4. **員工可用性與真實品質**：A26-09工作台／審核簡化；A26-10效能／準確度；A26-11同一dataset完成八模組讀回。
5. **站內發送及發布分開驗收**：需要自動寄送時執行A26-12；A26-13以同SHA的CI、preview、schema、Auth/provider/worker及staff UAT為發布證據。沒有可審阅結果前不要求使用者批准模糊部署。

### 交給實作者的執行提示

> 先讀本報告、Findings／Tasks／114案例CSV、原98案、repo AGENTS.md（本次兩checkout未找到）及TASKS.json。重新核對main／candidate／production SHA是否已漂移。保留F與Q/N IDs及所有歷史證據；不把PR內文或CI綠燈當正式完成。先逐項review/reuse已有業務修復，針對核心行為補足驗證；不整批重写。變更session/identity/bulk/approval時必須保留tenant、canonical actor、If-Match、stable intent、unknown hold與exact revision約束。每項回報code、CI、deployed、live/UAT四種狀態，附同版本證據、未解限制及回退。Neon、provider與真實外部發信各按其目標和授權執行；稽核本身不是正式資料修改或寄信授權。

## 證據索引與限制

- E01：GitHub PR/CI metadata及Vercel正式deployment讀回。
- E02：本次公開入口截圖及脫敏登入／runtime觀察；不保存密碼、token或OAuth state。
- E03：最新hosted API log摘錄與下載continuity XML；下載artifact SHA256及XML去重摘要在validation.json。
- E04：本次44 unit的final及首輪環境失敗原始TAP/JUnit。
- E05：本次main四組checks及exit／耗時。
- E06：開發分支既有Q06/Q08/Q09/Q10/N00/Q16證據及來源hash。手機圖僅fixture，不是本次正式操作。
- E07：32個reviewed source檔案快照、hash、CI／合併／head tree一致證明及84 operations inventory。

原10月3日ZIP是追蹤基準，不將其截圖／500／會員狀態重新標成10月6日觀察。本次沒有全repo逐行安全review、所有分支／未提交worktree盤點或正式data/schema巡檢。正式完整流程仍需有效登入帳戶與既有工作區權限；目前可交付的是有證據的部分網站操作＋來源／開發進度稽核及具體後續驗收計劃。

另附 BuyerOS_UI_Actions_2026-10-06.csv：原44項代表性UI操作＋4項新控制，共48項；角色、前置條件、期望、歷史結果及本次受阻欄分開。只有公開入口完成live觀察，其餘不能稱為通過。
