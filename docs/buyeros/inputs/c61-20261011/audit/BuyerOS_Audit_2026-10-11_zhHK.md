# BuyerOS 網站與程式碼稽核

**稽核日期：2026-10-11（UTC；香港時間 UTC+8）**  
**結論：目前用戶不能完成研究至外展流程。登入可以成功，但正式 API 在載入工作區時失敗。**

本次依「網站稽核執行」重審 GitHub、正式網站及後台，重點是更新後的登入，以及同一筆資料由 Offer 到 research、buyer、draft、approval、export／send 的完整流程。這是稽核與修復交接，沒有修改產品程式、正式資料庫、身份設定或供應商，也沒有寄出訊息。

## 1. 最重要的結果

| 優先 | 發現 | 用戶影響 | 下一步 |
|---|---|---|---|
| P0 · F23 新增 | 正式 API 查詢 `user_identities` 時得到 PostgreSQL `42P01`／relation 不存在 | 已成功登入的用戶仍看不到工作區；其餘七個功能入口停用 | 先查明實際 DB target、schema head、search_path 和 runtime grants，再作相容修復 |
| P1 · F24 新增 | 這次正式推廣未攔截 schema／應用不相容 | Vercel 顯示 READY、CI 最終全綠，網站仍不可工作 | 把必要 schema、身份映射及真實工作區讀取接到 promotion gate |
| P1 · F20 延續 | 正式登入仍使用 Auth0；Neon 尚未切換 | 新 Neon 實作沒有成為用戶目前使用的登入流程；reload 後需再按 Sign in | 完成同版本 Neon canary、identity mapping、有限期雙信任及退役驗收 |
| P1 · F10 延續 | 真實 research／contact／model 供應商未選定，send 授權仍關閉 | 修復工作區後，仍不能直接宣稱完整 research + outreach 可用 | 依獨立供應商、成本、來源、寄送驗收逐項啟用 |
| P1 · F13 延續 | 開發狀態及 release manifest 過時 | 實作者可能重做已有功能，或誤把部署當作交付完成 | 更新單一狀態記錄，分開 implementation、test、activation、live acceptance |

成功登入只證明 authentication。它不證明工作區 membership、API authorization、資料庫相容性或研究功能可用。本次沒有讀到 membership，不能把錯誤解釋成「用戶沒有工作區」。

## 2. 版本及證據基準

| 項目 | 本次核對 |
|---|---|
| GitHub | https://github.com/YNWAforever/BuyerOS |
| 正式網站 | https://buyer-os-nu.vercel.app/ |
| 後台 | https://buyer-os-nu.vercel.app/app |
| main／正式 deployment SHA | `cbbe0e93b0132ae07ff0d87f6cc57f871f13200e` |
| tree SHA | `127970f6538dd257523c49fa84b82dae011cc39f` |
| PR12 | 已合併；2026-10-11 06:10:03 UTC，即香港 14:10:03 |
| 正式 deployment | `dpl_DWwUAPyLxDR6pLU95BgcUxgseAFZ`；READY；約 06:11:12 UTC |
| main CI | run `38117173377`；11 jobs success；約 06:46:17 UTC 完成 |
| 正式 API 版本 | 本次錯誤診斷 `source_sha` 同為 `cbbe0e93…` |
| schema head／實際 runtime role | 未取得 DB readback；診斷值為 null，不能據此猜版本 |

因此，10 月 6 日 F22「修復仍不在 main／正式部署」的版本差距已消除。**F22 可就這個具體版本差距結案；整體產品驗收仍未完成。** [E01、E03、E04]

本次沿用原來 114 個稽核案例，加上 C61 計劃 16 個案例，保留 130 個既有 ID；新增 N11-01 至 N11-18，共 148 筆案例記錄。舊欄位以 `baseline_` 保留，不能把歷史 pass 當成本次 pass。原 30 項 C61 任務保留，新增 C61-31／32／33。共 24 個 findings、33 個任務。

## 3. 更新後登入：實際重現

1. `/` 和 `/app` 顯示 Sign in 及 Language。
2. Sign in 導向 Auth0 hosted login，並非 Neon。使用者透過安全登入流程選擇 email，沒有向稽核記錄提供密碼。
3. Callback 返回 `/app`，出現 **Sign out** 及 **Live workspace**。登入成功。
4. 工作區載入顯示「Service temporarily unavailable…」，request ID `0c64e2f6-0da5-4309-a34a-224c1c9dcf52`。
5. 按一次 Retry loading workspaces，仍失敗，request ID `b7aea690-a1a4-4c58-b85e-27dc02a7e7c8`。
6. 重新整理後回到 Sign in。再按按鈕，既有 Auth0 SSO 不用再次輸入密碼便完成 callback，但工作區仍失敗。本次第三個 request ID 為 `6c8f86f0-9e64-4d43-b02a-4f38bc3a0361`；保留的 runtime correlation 是前兩個 ID。
7. 在錯誤狀態選繁體中文，導航、錯誤及請求編號 label 有翻譯；完成後恢復 English。登出後回到 Sign in。

Auth0 adapter 將 access token 放在記憶體，沒有 Neon adapter 的初始化流程；這與 reload 後需要重新按 Sign in 的觀察一致。修復應使用已設計的 session 恢復流程，不應為了避開重新登入而把 bearer token 改存 localStorage。[E02、E05]

**Copy diagnostics：**按下後沒有可見成功／失敗回饋，cloud clipboard 讀回空白。這只足以判定結果不明；不能單凭雲端 clipboard 把網站寫入功能判成壞掉。原始碼也沒有 await／catch／status feedback，應補上成功提示及失敗時的可選取文字。[E02、E05；F01]

本次没有測試新用戶註冊、忘記密碼、Google OAuth、真實 Neon session 或完整跨 tab revocation。可見登出不等於證明所有 token 即時失效。

## 4. F23：工作區阻塞的直接根因

兩個本次 request ID 的 Vercel 診斷均為：

```text
error_class: ProgrammingError
classification: missing_relation
sqlstate: 42P01
relation: user_identities
source_sha: cbbe0e93b0132ae07ff0d87f6cc57f871f13200e
schema_head: null
runtime_role: null
```

對應原始碼：

- `services/api/buyeros_api/api/routes/workspaces.py:22` 呼叫 `resolve_user_id`。
- `services/api/buyeros_api/services/identity_resolver.py:10` 查詢 active `UserIdentity`，Auth0 登入亦會經過此處。
- `services/api/alembic/versions/0039_c61_user_identities.py` 建立 `public.user_identities`，回填既有 canonical user UUID、設立 trigger、immutable association 規則及有限欄位 SELECT grants。

**已證實：**這個執行中的 API 看不到它所需的 relation，阻斷正常工作區查詢。  
**尚未證實：**實際 migration head、是否漏跑 migration、連錯 branch／database、search_path 或部署的連線目標。`42P01` 不應直接等同「只要跑一次 migration 就好」。

第一步必須由有權限的工程人員，以實際 runtime role／預期 DB target 做只讀核對，包含 `to_regclass('public.user_identities')`、Alembic head、0038 directory function、grants 及既有身份 exact mapping。不要只建一張空表；那會讓舊用戶的 canonical mapping 缺失。也不要用 email 自動合併用戶、重建 UUID 或放寬租戶權限。

目前來源的 migrations 已延伸至 0050；是否及如何升級整段 schema，必須由當前 API／worker 相容矩陣與 DB 實際 head 決定。稽核沒有執行正式 migration。[E03、E05]

**歷史區分：**F21 是 10 月 2 日的 `OperationalError`，舊根因仍未確認。本次 `ProgrammingError/42P01` 是新的、有直接證據的 F23，不能據此把 F21 填成已修復。

## 5. 全部研究與外展流程

| 模組 | 日常工作與應有結果 | 目前來源／測試狀態 | 本次正式 UI |
|---|---|---|---|
| Overview | 選 workspace/project，待辦卡進入同範圍資料 | 六張 scoped work queue 卡、pending approval／receipt 列表已實作 | 入口可見，但只看到工作區錯誤；沒有業務數據 |
| Offer | 建立／修改產品資料，來源文件，ICP 版本與核准 | wizard、documents、version guards 已存在 | 停用，未建立或修改資料 |
| Buyers | Research admission、候選企業覆核、去重、負責人 | search adapter、candidate review、bulk manifest 已增加 | 停用；供應商 default registry 仍空 |
| Results | 檢查符合度、來源、contact quote／結果與匯出 | fit、source、quote、receipt／export 路徑存在 | 停用；真實精確度及聯絡結果未验收 |
| Research runs | 進度、需要人工覆核、取消、安全重試、unknown reconciliation | durable intent、scope／epoch guards、receipt recovery 有測試 | 停用；未啟動真實 run |
| Drafts | 來源支持的草稿、修改、重新 grounding、核准及 exact revision 匯出 | dirty guard、Unicode selection、grounding、history 已實作；send 另有 candidate | 停用；未驗收一份真實 approved export 或寄送 |
| Settings | 成員／角色、政策、budget、provider readiness | member paging、capability blockers、恢復介面已有 fixture | 停用；管理員無法從該畫面診斷本次阻塞 |
| Operations | Jobs、失敗原因、批量結果、只重試失敗項、receipt history | 分頁、scope、持久結果及批量流程有測試 | 停用；沒有正式維護操作驗收 |

**本次沒有完成一條業務端到端資料鏈。**八個模組都未完成正式業務驗收：Overview 停在 workspace error，其餘七個入口停用。這不表示每個子功能原始碼都壞掉，而是前置條件使實際業務流程無法開始。

修復後，必須用同一個 test project 串起：產品來源 → ICP revision → research run → company candidate → reviewer decision → buyer／contact receipt → draft revision → source support → approval → export。站內寄送再另接 sender／recipient／delivery intent／callback／suppression。每一步保留相同 tenant、project、actor、版本及 trace ID，不能用互不相關的成功畫面湊成全流程。

## 6. 新功能的真實完成狀態

| 新增／改善項目 | 已有實作證據 | 還欠甚麼 |
|---|---|---|
| Neon auth server、public config、JWT trust、session refresh | runtime dependency `@neondatabase/auth 0.5.0-beta`；server/session/verifier tests | 真實 target branch、provider session、canonical linking、角色讀回及正式切換 |
| Identity migration 0039 | additive table、legacy backfill、exact issuer/subject、撤銷及immutable association | 正式 runtime 對 relation 的可見性和相容 schema；F23 |
| Search／model／contact adapters | `live_search.py`、`live_model.py`、`live_contact.py` 及 mock transport 測試 | account-specific contract、市場／語言、價目與有界 sandbox receipts |
| Candidate review／來源選取 | review context、審核 handoff、read-only Unicode selection | 真實來源語義正確及人員操作驗收 |
| Overview、批量維護與 Operations | scoped counts、manifest、expiry、10,000 筆 crash recovery fixture | 正式資料量、維護工作所需時間、角色與錯誤恢复驗收 |
| Delivery ledger／admission／callback／reconciliation／Resend candidate | 0048–0050、native runner、獨立 status reader、signed callback、history | 選定的 sender/account/price/authority，真實 single-send receipts 及完整 UX |

`DEFAULT_REGISTRY = ProviderRegistry()` 仍沒有 registrations。`selected_run_capability()` 由這個 registry 取得 search capability。這是未啟用的明確程式證據，不應將 credential 存在當成已啟用。

Delivery 的 `selected_delivery_authorization()` 仍直接回 `None`；`delivery_admission_enabled` 預設 false。即使只翻 feature flag，也不會自動產生合法的 server-owned authority。舊 `/deliver` 保持 disabled 邊界；新的 delivery-intents route 與其不同，兩者不能混為一談。

因此應承認已完成的工程工作，同時保留 **Release A、Neon-only、native send 均未完成正式驗收**。安全拒絕未授權成本／發送是正確保護，但用戶要的功能仍未交付。[E05、E07–E09]

API contract 從前次 84 增至 **93 個 operation**，本次 generated route check 相符。新增九項：delivery callback、delivery reconciliation、draft delivery admission、work queue、provider operations、candidate review context、candidate review、candidate list、draft delivery history。這是靜態 operation inventory，不代表 93 個操作都在正式站實測。另保留 48 項代表性 UI actions，並非每個 DOM button 的清單。[E06]

## 7. 測試結果與覆蓋界線

| 層級 | 結果 | 可以證明 | 不可以證明 |
|---|---|---|---|
| 本次本地 Node focused | 81 pass、0 fail／skip | session、auth boundary/config/proxy、research intent、bulk manifest、grounding、job query 等選定檔案 | 真實 Neon OAuth／正式 DB／實際供應商 |
| 本次本地 API focused A | 105 pass、0 fail／skip | registry、delivery protocol、workspace benchmark tools | 正式 schema、正式吞吐或信件已送達 |
| 本次本地 API focused B | 139 pass、0 fail／skip | Neon verifier 與 search/model/contact adapters 的隔離測試 | account-specific filter support、真實品質和費用 |
| 同 SHA hosted API CI | 2,525 pass，0 fail/error/skip | CI owned DB fixtures 及整個當前 API suite | 正式 migration 已執行或 live tenant 可用 |
| 同 SHA hosted worker CI | 246 pass，0 fail/error/skip | hosted worker suite | 真實 worker 已在正式環境有健康 heartbeat |
| 同 SHA hosted built UI | 三組 124／17／4 pass | fixture 下 browser 操作及 discovery/execution 一致 | 真實 auth/provider journey；不同組可能重疊，不相加當 unique cases |
| Live focused N11-01…09 | 5 pass、3 fail、1 inconclusive | 此次實際入口、登入、重試、reload、語言、登出與診斷結果 | 完整 research／outreach 或所有角色 |

本次本地三組合共 **325 個測試**，檔案集合分開。hosted 數字不加到本地數字；hosted API／worker focused 子組也不另外加總。新 18 個稽核案例中另有 metadata 檢查及被阻擋／未執行的驗收，不能用 325 個 unit/integration test 代替 148 個 user-case 完成率。[E04、E07–E09]

本地没有 Docker／disposable PostgreSQL，因此未重跑 DB suites；使用同 SHA hosted run 的真實 job logs，清楚標示來源。沒有為了取得漂亮數字對目前失敗的正式站做壓測。

## 8. 效能及準確度：可執行的驗收案例

以下是修復後的測試計劃與建議門檻，**不是本次正式環境量測結果**。先由產品／技術負責人採用預算及 SLA，再固定資料集、環境和版本。

| Case | 方法與資料量 | 驗收及保留資料 | 目前結果 |
|---|---|---|---|
| P01 工作區目錄 | owned PG16、runtime 非 superuser／NOBYPASSRLS；W=1/10/100/1000，並發 1/10/25；每actor每stage 30–100 warm samples，cold另記 | 既有 harness ceiling：warm p95≤800ms、p99≤1500ms、5xx≤1%、SQL≤6、tenant錯誤0；保存逐request raw observations、query count、bytes、pool／role／head；樣本不足不報穩定p99 | 本次 tools tests 通過；正式成功 latency 未量測 |
| P02 批量 10k | 50／500／10,000 buyers；跨頁全選，固定query/version/expiry，50個已變更版本衝突；worker中途停止後恢復 | 每buyer只處理一次；完整10k結果；僅失敗子manifest重試；預覽／確認／結果分頁有界；量測記憶體、queue age及耗時 | hosted fixture 有 9,950更新／50衝突斷言；不等於正式耗時 |
| P03 背景輪詢 | 多tabs、多jobs，前景／背景／斷線／resume／scope switch | 保存request rate、重複請求、SSE fallback、abort；不讓舊tenant response覆蓋新scope；後台無無限輪詢；數值預算先定 | 未量測正式網絡負載 |
| P04 端到端 latency | 同一project成功流程；分拆 auth、DB、provider等待、queue等待、UI render | 各段p50/p95，失敗與成功分開；不用固定sleep算API latency；不得把tool round-trip當站點速度 | 被 F23 阻擋 |
| P05 前端可用性性能 | 桌面及390px、限制網絡／CPU；登入／列表／大批預覽 | 建議 LCP≤2.5s、INP≤200ms、CLS≤0.1；分開lab與field percentile，列樣本量；追蹤route bundle與long task | 建議目標，沒有本次Lighthouse／field測值 |
| A01 公司對應 | 60個人工gold案例，HK/en/zh-HK各類含同名企業、子公司、錯domain、過期來源；兩人覆核 | 建議precision≥95%；不確定保持needs_review；分層列分子／分母及分歧，不能以小樣本保證整體表現 | 沒有真實provider結果 |
| A02 Claim／citation | 至少100條事實claim，驗URL、來源段落、時間、Unicode範圍及原文支持；含惡意來源指令 | 未支持claim不得核准；人審100%已核准事實有支持；保留錯誤類型而非只平均分 | fixture能測mechanics，語義未驗收 |
| A03 Contact／成本 | 已核准sandbox test allowance；區分verified／unverified；同intent重放、timeout/unknown、pricing change | 不捏造email；max liability有界；unknown不重複扣款／重查；actual charge與ledger逐筆對帳 | 未用付費provider |
| A04 Export／send一致性 | 同一approved revision與sender/recipient，UTF-16/emoji、中英混合、修改後重核准、callback重送 | export text與approved revision完全一致；accepted≠delivered；unknown禁止重寄；bounce／complaint／unsubscribe不倒退 | export／send正式資料鏈未測 |

性能第一優先是恢復成功且有界的 workspace read。其後才做索引／query plan／pool tuning；沒有 pool-wait 或 SQL latency 證據前，不把本次 `42P01` 說成 cold start 或連線池不足。

## 9. 後台 UI／UX 與大量維護規格

| 範圍 | 目前阻礙／待驗收 | 建議行為及欄位 | 正常、空白、錯誤、權限、批量驗收 |
|---|---|---|---|
| 登入／Workspace | generic unavailable；使用者無法分辨帳戶與服務故障 | 顯示登入成功、服務暫時不可用、最後檢查時間、request ID、可用重試；admin有安全診斷入口；不要把SQL／schema曝露给一般用戶 | empty membership與500分開；重試loading禁止重複點；copy成功／失敗回饋；無admin權限不顯示敏感診斷 |
| Overview | 正式六卡尚未驗收 | 每卡顯示範圍、total、更新時間及下一動作；卡與列表共享filters | 0是確實空資料；error顯示不可用，不當0；換project不見舊數據 |
| Offer／Research | 啟用前缺可理解的下一步 | 開始前列產品版本、ICP核准、provider availability、預算及估算；一個明確主操作 | 缺前置條件說明誰可完成；operator／reviewer能力分開；submit後保留intent並可恢復進度 |
| Results／Drafts | 真實來源與人工覆核仍待驗收 | 顯示公司domain、source段落、更新日期、confidence／needs_review；draft版本、未儲存提示、事實支持與approval history同屏可查 | 修改使舊approval失效；無支持內容阻止approve；保存／權限拒絕不得丟dirty text |
| Bulk | 跨頁scope容易被誤解；正式10k未驗收 | 清楚區分本頁X筆／全部符合Y筆；preview含query、workspace、project、action、owner、revision、expiry、將跳過原因；確認後有job連結 | expired重預覽；scope改變清selection；成功／conflict／denied逐項計數；只重試失敗子集合；不重送成功項 |
| Operations | 失敗原因及unknown需要不同恢復方法 | 顯示job用途、建立者、範圍、進度、耗時、更新時間、safe retry／reconcile條件及錯誤分組 | unknown只status reconciliation；永久拒絕不自動重試；匯出失敗清單有權限限制；bulk action有可讀confirm |
| Settings | F23使admin不能進入 | 將成員、角色、budget、provider contract與readiness整理成明確卡；每blocker列具體負責角色和下一步 | ordinary member只看授權資訊；保存衝突保留輸入；read失敗可單獨重試；避免一個全局綠燈掩蓋未配置provider |
| Mobile／keyboard | 只有hosted fixture，不等於人員UAT | 390px與200%zoom可完成核心操作；合理focus順序、可讀labels、錯誤announcement、批量toolbar與table可操作 | 用真實operator／reviewer各做5項daily jobs；記錄完成時間、錯誤及求助次數；screen reader人工覆核 |

目前 observed workspace error DOM 已有 alert role、語言切換及停用業務入口，這些是可保留的正確行為。停用入口應有可理解的原因；不可為了「讓按鈕可點」跳過 authorization 或前置資料檢查。

## 10. 修復及交付順序

### 第一批：恢復正式工作區

1. **C61-31（P0，0.25–0.5人日估算）**：取得當前 DB target／head／role／relation／grants 的只讀證據，核對此 SHA 需要的 schema。
2. **C61-32（P0，0.5–1.5人日估算）**：在隔離副本排練相容修復，保留所有 canonical UUID、FK、revoked identities、歷史及unknown holds。依證據選 additive migration 或已驗證的相容 application rollback。正式執行須有該具體變更授權。
3. 重測 N11-02／03／04／11：合法員工 workspace 200、正確roles；零會員正常empty；不同租戶不得互見；不得用暫時放寬auth/RLS解決。

### 第二批：避免同類故障再上線

4. **C61-33（P1，1–2人日估算）** 與 C61-28／29：將 release manifest 固定到 source、API、worker、schema、configuration digest；已知必要relation／grants／mapping缺失、錯target、stale manifest、CI未完成時禁止promotion。
5. `/health/live` 只證明程序回應，不當作登入或資料庫相容性檢查。candidate 需要實際 runtime role 的相容性驗證及已授權known-account workspace read。不要在一般 build hook 直接用DB owner自動執行未審核migration。
6. 修復 copy feedback、可操作錯誤與admin診斷；把 `CURRENT_STATUS.md`、`release-candidate.json`、TASKS 的当前摘要與歷史紀錄分開。

### 第三批：完成 Neon 登入

7. 沿 C61-07…14 驗收已有實作，避免重寫已通過測試的 session／verifier。確認 server `BUYEROS_AUTH_PROVIDER`、API `BUYEROS_AUTH_MODE`、route gate、issuer/audience/JWKS、callback origin、cookie設定同屬預期環境。
8. 用真實 email／Google／Neon-only及已遷移帳戶驗收：callback return path、reload恢復、20個同時401只一次refresh、跨tab logout、撤銷後下一request拒絕、四種角色及兩個tenant。
9. Exact issuer＋subject 映射到既有 canonical UUID；不依email自動連結，不匯出密碼。保留Neon-only帳戶可用的相容frontend/API回退版本。雙信任期限明確，canary通過才退役Auth0。

### 第四批：讓完整研究與外展可工作

10. C61-15…19 選定並驗證 search/model/contact contract、市場／語言、每次成本上限及真正回執。先在隔離且已有支出授權的sandbox驗收，處理timeout/unknown與status-only recovery。
11. C61-21…27 用同一資料鏈完成八模組、批量10k、準確度、性能、真實員工daily workflow。研究與核准匯出先形成可驗收版本（C61-29）。
12. C61-20／30 獨立完成 sender／recipient／policy／suppression／cost authority／單次POST／signed callback／delivery history後，才驗收站內寄送。修復研究不自動授權寄信或付費。

人日是工程估算，不包含帳戶設定、授權等候、真實資料gold set及使用者UAT。30項既有任務的驗收標準和回退條件保留於tracker；新增3項針對本次正式故障。

## 11. 開發文件與維護性

`docs/buyeros/CURRENT_STATUS.md` 仍記載 PR12 是 draft、published head `22f11ab`、部分Neon／adapter工作「可以開始」，但現時PR已合併，source包含更多auth、provider及delivery實作。`release-candidate.json` 仍指 `a78859fe…`、CI／deployment為null及所有acceptance false。[E05]

建議維持一個機械可讀 current manifest，分別記錄 **implemented_at_sha、tested_at_sha、deployed_at_sha、activated、live_accepted_at**。歷史runbook可以保留，但頁首標示「historical」及最新替代版本。CI應驗證manifest的宣告與實際commit／required evidence一致；不要單憑文檔字串false／true控制真實外部side effect。

維護操作應保留 immutable intent、approval revision、provider receipt、budget hold及trace ID；用bulk manifest固定範圍，出錯只處理失敗集合。UI從同一API取得capability blockers，避免前端硬編碼綠燈。對外資料取得、研究品質、寄送及資料庫migration分開驗收，能降低一次排錯牽涉過多系統的成本。

## 12. 證據索引與限制

| ID | 檔案／來源 | 範圍 |
|---|---|---|
| E01 | `evidence/E01-source-deployment.json` | GitHub main／PR／CI與Vercel alias metadata |
| E02 | `evidence/E02-live-browser-notes.json` | 本次正式登入、reload、workspace error、語言及登出觀察 |
| E03 | `evidence/E03-runtime-diagnostics-redacted.json` | 兩個本次request ID、42P01、source SHA；已排除SQL參數及身份值 |
| E04 | `evidence/E04-main-ci-summary.json` | 同SHA hosted job log 摘要；非本地／live測試 |
| E05 | `evidence/E05-source-excerpts.txt` | 帶行號及commit連結的auth、migration、provider、delivery、UI、release excerpts |
| E06 | `evidence/E06-inventory-summary.json` | 93個declared operation、9項新增、148cases／33tasks分母 |
| E07 | `evidence/E07-focused-node-tests.log` | 本次81個Node focused結果 |
| E08 | `evidence/E08-focused-api-tests.log` 及 XML | 本次105個API focused結果 |
| E09 | `evidence/E09-auth-provider-tests.log` 及 XML | 本次139個auth/provider結果 |
| E11 | `evidence/baseline-0…5.csv` | 前次案例／findings／C61 tracker／inventory的可讀內容；經內容擷取正規化，不宣稱等同原ZIP bytes |

可追查來源：[PR12](https://github.com/YNWAforever/BuyerOS/pull/12)、[main CI](https://github.com/YNWAforever/BuyerOS/actions/runs/38117173377)、[本次原始碼](https://github.com/YNWAforever/BuyerOS/tree/cbbe0e93b0132ae07ff0d87f6cc57f871f13200e)。

全部結論有區分 live verified、source verified、local test、hosted fixture、historical、blocked、unknown。沒有保留密碼、cookie、access token、OAuth code/state、完整SQL參數或正式資料庫匯出。瀏覽器截图只供內部核對，持久證據包以去識別文字紀錄提供。

## 13. 第一批 Codex 執行提示

```text
先讀 BuyerOS_Audit_2026-10-11_zhHK.md、Findings、Cases、Tasks 和 evidence E01/E03/E05。
核對當前 main、部署和 repo 規則；本稽核基準是 cbbe0e93，不假定之後未變。
優先 C61-31 → C61-32 → C61-33。先證明實際DB target/head/role/relation，不能盲目upgrade head。
保留F21舊案unknown，F23是本次新42P01。沿用所有既有F/C61/case IDs及歷史欄位。
先在隔離環境完成可review的migration或兼容rollback、negative tests及實際runtime role驗證。
保留canonical UUID/FK、revoked identity、原intent/key、approval、receipt及unknown holds；不能email自動link。
不以CI綠燈、Vercel READY、fixture或操作定義數當live acceptance。
不重寫已有Neon/provider/delivery實作；先核對其未完成的activation與live acceptance。
只有取得具體授權才改production schema/auth/provider activation、支出或寄送。
每批更新current source/test/deploy/acceptance證據；受阻時列出確切條件，繼續完成獨立工作。
修復後以同一資料鏈重測完整8模組；native send另保留獨立啟用與回退門檻。
```


## 14. 全部 findings 最新處置

以下涵蓋F01–F24。只有所列的具體觀察可視為本次驗證，其餘仍須正式驗收。

| ID | 優先 | 問題 | 最新處置及證據 |
|---|---|---|---|
| F01 | P1 | 登入成功後工作區載入失敗，不能進入業務流程 | 恢復與診斷 UI 已存在；本次根因見 F23。未讀到會員資料，不能判定無 membership。 [E02;E03;E05] |
| F02 | P2 | 無可用工作區時的語言切換 | 在本次工作區錯誤畫面切換繁中成功；零會員／跨裝置偏好另未重測。 [E02] |
| F03 | P2 | 成員目錄分頁 | 新版來源及 hosted fixture 有對應覆蓋；正式 Settings 受 F23 阻擋。 [E04;E05] |
| F04 | P1 | 員工身份與工作區入職 | identity reconciliation 工具已存在；實際員工 canonical UUID／角色尚未讀回。 [E05] |
| F05 | P2 | Operations 分頁及工作辨識 | 目前有 scope/filter/receipt/result paging；正式工作台無法進入。 [E04;E05] |
| F06 | P1 | 批量選取、責任人與確認 | 新版 manifest／confirmation 已有測試，未驗收正式跨頁批量。 [E04;E07] |
| F07 | P2 | 輪詢與頁面背景負載 | session scope 與取消機制有程式測試；正式流量、SSE／polling fallback 未量測。 [E04] |
| F08 | P1 | Research 接受後回應遺失可能重複提交 | intent/idempotency 有本次 focused 測試；真實供應商 unknown receipt 未驗收。 [E07] |
| F09 | P2 | 語氣／目的與實際產出一致性 | 不能以 fixture 取代真實 model output 的人工品質評核。 [E04] |
| F10 | P1 | 研究、聯絡人及完整站內外展仍未啟用 | live_search/model/contact 與 Resend candidate 已實作；DEFAULT_REGISTRY 空，selected_delivery_authorization 回 None。 [E05;E09] |
| F11 | P1 | 大量維護與結果可重試性 | 現有 10,000 筆 crash recovery 測試在 hosted API suite 內；不是正式容量或操作驗收。 [E04;E05;E07] |
| F12 | P1 | 真實效能、準確度與成本證據不足 | 正式 workspace fail；沒有成功請求 p95/p99、真實搜尋 precision 或真實單位成本。 [E02;E04] |
| F13 | P1 | 開發與發布文件過時 | CURRENT_STATUS 仍稱 PR12 draft / Neon 可開始；release-candidate 仍 a788、predeploy_ready=false。 [E01;E05] |
| F14 | P2 | 每日工作 UI、mobile 與可達性 | hosted keyboard／zh-HK mobile case 通過；本次正式 UI 只驗登入／工作區错误。 [E02;E04] |
| F15 | P1 | 登入初始化與設定錯誤呈現 | 新 Neon bootstrap 有測試；本次 Auth0 callback 成功，reload 仍回 Sign in。 [E02;E07] |
| F16 | P1 | 編輯後重新核對來源及核准 | grounding 與 Unicode／dirty draft fixture 增加；真實来源至匯出的資料鏈未驗收。 [E04;E07] |
| F17 | P1 | Overview／列表篩選範圍及數量 | 六卡與 scope 查詢已有 hosted fixture；正式 workspace 受阻。 [E04;E07] |
| F18 | P1 | workspace discovery 查詢規模 | 0038 restricted function 與有界查詢已存在；本次首先於 0039 identity relation 缺失失敗。 [E03;E05] |
| F19 | P1 | 草稿未儲存內容保護 | 跨 tab／dirty buffer／navigation 測試存在；本次未開啟正式草稿。 [E04;E07] |
| F20 | P1 | Auth0 轉 Neon 仍未完成正式切換 | 目前 live 仍導向 Auth0；Neon SDK、server、JWT verifier、session、identity migration 已有實作與離線測試。reload 需再按 Sign in。 [E02;E05;E07;E09] |
| F21 | P1 | 2026-10-02 舊 workspace OperationalError | 保留舊案；不能用本次 42P01 代替舊錯誤根因或將它標為已修復。 [E11;E03] |
| F22 | P1 | 舊修復未在 main／正式別名部署 | PR12 已 merge，main／正式 alias／錯誤 API source_sha 同為 cbbe0e93；不代表八模組已驗收。 [E01;E03] |
| F23 | P0 | 正式 API 必需的 user_identities relation 不存在 | 兩個本次 request ID 均為 missing_relation / 42P01；工作區 route 無條件查 identity。0039 含 backfill、trigger 及 restricted grants。尚未取得實際 DB target/schema head/search_path，不能斷言只是漏跑某一 migration。 [E02;E03;E05] |
| F24 | P1 | 正式推廣沒有攔截已知未就緒的資料庫／發布狀態 | Vercel READY 約 06:11 UTC，完整 main CI 約 06:46 才完成；release-candidate 仍 predeploy_ready=false。source build 只執行 Vite，/health/live 只回 ok。確定此次未攔截不相容發布；未讀取全部遠端 deployment protection 設定，不能宣稱一概沒有門檻。 [E01;E03;E05] |
