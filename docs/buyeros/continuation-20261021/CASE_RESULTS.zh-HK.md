# N21 全部72項案例對照

原 audit 不改寫。PASS_LOCAL 只表示此表列明的本機 fixture 斷言通過；不表示正式部署、正常公司 Google、真人 UAT 或原始72項人工案例全部已執行。
PARTIAL 保留未完成的必要條件；BLOCKED 不計作通過。舊 audit 結果完整保存在每筆 audit_snapshot。

更新：2026-10-21T22:55:38.653317+00:00；狀態統計：`{"PASS_LOCAL": 49, "BLOCKED": 7, "PARTIAL": 16}`。

| Case | 本輪狀態 | 本機證據 | 剩餘限制 |
|---|---|---|---|
| N21-AUTH-01 | PASS_LOCAL | 私人入口、單一登入 CTA、未登入不展示業務資料 | 仍未部署／未做正常公司 UAT |
| N21-AUTH-02 | PASS_LOCAL | 1440/768 首屏表單、單一 main/h1、主控制項 44px | 仍未部署／未做正常公司 UAT |
| N21-AUTH-03 | PASS_LOCAL | 390/320 及窄畫面 reflow／首屏登入控制 | 仍未部署／未做正常公司 UAT |
| N21-AUTH-04 | PASS_LOCAL | 中英標籤／錯誤一致；切換語言保留 email | 仍未部署／未做正常公司 UAT |
| N21-AUTH-05 | BLOCKED | 合成 social-init 正向、取消、外 branch 拒絕、重複點擊 | 真實 Google chooser／公司帳戶登入未執行；合成協定不能代替 |
| N21-AUTH-06 | PASS_LOCAL | 空白欄位原生驗證與焦點 | 仍未部署／未做正常公司 UAT |
| N21-AUTH-07 | PASS_LOCAL | 無效 email 的可操作驗證 | 仍未部署／未做正常公司 UAT |
| N21-AUTH-08 | PASS_LOCAL | 滑鼠 Start again 導航至 /app 並移除舊 form | 仍未部署／未做正常公司 UAT |
| N21-AUTH-09 | PASS_LOCAL | Enter 恢復、主要內容焦點、新 transaction | 仍未部署／未做正常公司 UAT |
| N21-AUTH-10 | PASS_LOCAL | 直接 /app 是唯一私人入口，可重新登入 | 仍未部署／未做正常公司 UAT |
| N21-AUTH-11 | BLOCKED | 合成 SDK email/token/API/reload/deep-link | 真實公司 Google session／branch JWT／membership 尚未驗收 |
| N21-AUTH-12 | PARTIAL | 合成跨 tab 登出、私密 buffer 恢復及明確 Discard 清除；expiry unit | 正常公司身份與實際 expiry/relogin 尚未驗收 |
| N21-WORK-01 | PASS_LOCAL | 零 membership 與 503／未核實狀態分開；可重試 | 仍未部署／未做正常公司 UAT |
| N21-WORK-02 | PASS_LOCAL | scope 切換／晚到回應守衛；未存 preparation 保留原作用域 | 仍未部署／未做正常公司 UAT |
| N21-WORK-03 | PASS_LOCAL | 深連結、同專案 reload、Back/Forward 與導航完成；三引擎旅程及關鍵 history 回歸 | 正常公司層級仍未驗收；引擎自動化不等同實體裝置 |
| N21-WORK-04 | PASS_LOCAL | 每日卡片與 filtered total／rows 按不同公司一致 | 仍未部署／未做正常公司 UAT |
| N21-WORK-05 | PASS_LOCAL | 同名成員、姓名查詢、Mine／Unassigned；目錄 503／denied 可離開篩選 | 仍未部署／未做正常公司 UAT |
| N21-WORK-06 | PASS_LOCAL | UI-created project 保存 v1/v2、reviewer 批准並進入下一步 | 仍未部署／未做正常公司 UAT |
| N21-WORK-07 | PASS_LOCAL | 角色導航／直接 API 與權限撤回一致 | 仍未部署／未做正常公司 UAT |
| N21-WORK-08 | PASS_LOCAL | 診斷 clipboard resolve 後才成功；失敗可選取且不洩漏敏感錯誤 | 仍未部署／未做正常公司 UAT |
| N21-OFFER-01 | PASS_LOCAL | 同一 UI-created project 四步輸入、保存、修改及 exact ICP approval | 仍未部署／未做正常公司 UAT |
| N21-OFFER-02 | PARTIAL | 既有 offer intake／profile input 及驗證 contracts | 未逐項重跑原矩陣全部 wizard 無效欄位的 browser 組合 |
| N21-OFFER-03 | PARTIAL | 原生附件／PPTX backend、transport、extraction caveat 及私有權限回歸 | 新候選未做正常公司帳戶的 binary upload/download/hash 全流程 |
| N21-OFFER-04 | PARTIAL | profile save transport、分步恢復及 idempotency contracts | 未將全部 offer partial-save 組合接進此輪同專案 browser journey |
| N21-OFFER-05 | PARTIAL | 既有 stale/version contracts 與 scope dirty 守衛保持 | 完整 Offer P01 雙 tab 比較／替換不是本次已完成的產品變更 |
| N21-OFFER-06 | PARTIAL | 版本化產品、material-change／caveat 令 content review 失效 | 未在公司 UAT 串起研究／已批准匯出後再次修改產品的完整旅程 |
| N21-RESEARCH-01 | PASS_LOCAL | readiness／disabled admission、mock 費用 cap 與拒絕規則 | 仍未部署／未做正常公司 UAT |
| N21-RESEARCH-02 | PASS_LOCAL | 實際 UI/API/owned DB/test Celery，fixture search 到候選／買家覆核 | 仍未部署／未做正常公司 UAT |
| N21-RESEARCH-03 | PASS_LOCAL | 相同研究 intent key 重試／lost response，避免重複工作 | 仍未部署／未做正常公司 UAT |
| N21-RESEARCH-04 | PASS_LOCAL | 既有 native progress／polling／斷線回復與作用域隔離 | 仍未部署／未做正常公司 UAT |
| N21-RESEARCH-05 | PARTIAL | cancel／partial／unknown hold backend 與原結果恢復 contracts | 並非所有取消時點及部分結果組合均有此輪單一路徑 browser 證據 |
| N21-RESEARCH-06 | BLOCKED | 固定 fictional provider 只證明 plumbing／來源契約 | 缺少獨立人工標註 goldset；不能由一個 fixture 推算準確率或真實採購意欲 |
| N21-RESEARCH-07 | PARTIAL | 惡意來源／URL／provider failure／policy refusal 的離線 contracts | 沒有真實 provider integration 或人工 prompt-injection goldset；未授權付費呼叫 |
| N21-BUYER-01 | PASS_LOCAL | 公司 domain、Unknown market、fit 理由、來源數與 fit freshness | 仍未部署／未做正常公司 UAT |
| N21-BUYER-02 | PASS_LOCAL | 實際 query／sort／頁面／total 與舊回應不覆蓋新查詢 | 仍未部署／未做正常公司 UAT |
| N21-BUYER-03 | PASS_LOCAL | 本頁／全部選取、凍結 preview／manifest 與明確 bulk 確認 | 仍未部署／未做正常公司 UAT |
| N21-BUYER-04 | PARTIAL | 既有 bulk conflict／idempotency／safe recovery contracts | 未重跑所有大批 manifest 邊界及10000項業務寫入的 browser 情境 |
| N21-BUYER-05 | PARTIAL | 既有 Excel/CSV preview／duplicate import／provenance contracts | 本輪未匯入真實24家／57來源，亦未用公司帳戶重做 import UI |
| N21-BUYER-06 | PARTIAL | contact quote/provider authorization 以合成 fixture 驗證 | 真實 contact enrichment 未授權且維持停用 |
| N21-BUYER-07 | PASS_LOCAL | review-and-next identity、排序後焦點／可辨認公司資訊 | 真人任務時間／錯誤率不由此自動化結果推算 |
| N21-PREP-01 | PASS_LOCAL | 引用產品／公司／人物 evidence、可覆核但不可視作 sending approval | 仍未部署／未做正常公司 UAT |
| N21-PREP-02 | PASS_LOCAL | 公司切換 Cancel／Discard／Save 保留精確文字及原 scope | 仍未部署／未做正常公司 UAT |
| N21-PREP-03 | PASS_LOCAL | 版本／分頁／Save→Archive；缺頁直接讀原 ID，另一筆完整 row 不變 | 仍未部署／未做正常公司 UAT |
| N21-PREP-04 | PASS_LOCAL | Refresh 必須明確處理 dirty 文字 | 仍未部署／未做正常公司 UAT |
| N21-PREP-05 | PASS_LOCAL | sidebar、logout、native reload、Back/Forward、慢 RSC 舊 editor 卸載；三引擎關鍵 history 回歸；強制 expiry 清除內容並明示原提交可能已完成 | 實體瀏覽器及正常公司身份結果不能由引擎自動化替代 |
| N21-PREP-06 | PASS_LOCAL | loading／no match／503 retry 保留 query，selected company 不丟失 | 仍未部署／未做正常公司 UAT |
| N21-PREP-07 | PASS_LOCAL | deep-link 直接讀公司、分頁有界，superseded search 不覆蓋 | 仍未部署／未做正常公司 UAT |
| N21-PREP-08 | PASS_LOCAL | committed readback 429、lost stage receipt、initial history failure 沿原 intent read/ACK | 仍未部署／未做正常公司 UAT |
| N21-PREP-09 | PASS_LOCAL | material product change／expired channel 使 content review 失效 | 仍未部署／未做正常公司 UAT |
| N21-DRAFT-01 | PASS_LOCAL | 模板／grounded generation 可用性及 delivery disabled 的能力說明 | 仍未部署／未做正常公司 UAT |
| N21-DRAFT-02 | PASS_LOCAL | 人工改文須重新 grounding 及 exact revision review | 仍未部署／未做正常公司 UAT |
| N21-DRAFT-03 | PASS_LOCAL | DraftEditor dirty guard／412 conflict／明確 Discard／logout recovery | 仍未部署／未做正常公司 UAT |
| N21-DRAFT-04 | PASS_LOCAL | 實際授權匯出對應 exact approved revision，保留 approval／revision／export chain | 仍未部署／未做正常公司 UAT |
| N21-DRAFT-05 | PASS_LOCAL | content review 不授權送出；真實寄送0，disabled/refusal 邊界 | 仍未部署／未做正常公司 UAT |
| N21-OPS-01 | PASS_LOCAL | 受限成員目錄顯示姓名、同名區分、Mine／Unassigned 與可復原篩選 | 仍未部署／未做正常公司 UAT |
| N21-OPS-02 | PASS_LOCAL | failed／unknown 區分，原 handle readback；無假成功或重複 revision | 仍未部署／未做正常公司 UAT |
| N21-OPS-03 | PARTIAL | frozen manifest scope／expiry／original key contracts 保留 | 完整大型 segmented-maintenance browser sweep 尚非本輪全部執行範圍 |
| N21-OPS-04 | PASS_LOCAL | 權限改動後受限畫面／API 立即拒絕 | 仍未部署／未做正常公司 UAT |
| N21-OPS-05 | PARTIAL | 來源、dirty candidate、artifact／CI／runtime 矩陣及拒絕規則分開 | 正式 alias source/API/worker/schema 仍未知；新 diff CI 未 push／未執行 |
| N21-ACCESS-01 | PASS_LOCAL | test Principal／owned DB 的 foreign object／search／count／scope 拒絕 | 這不是正常公司 Neon 身分／正式 RLS UAT |
| N21-ACCESS-02 | PASS_LOCAL | operator／reviewer／viewer／admin 伺服器與 UI 分工 | 仍未部署／未做正常公司 UAT |
| N21-ACCESS-03 | PARTIAL | suppression、私有附件及 retained source contracts | 真實儲存與公司帳戶 private-byte 流程未接觸；正式權限不變 |
| N21-ACCESS-04 | PASS_LOCAL | canonical business summary 與 exact hash／authority／revision 一致；細節預設折疊 | 仍未部署／未做正常公司 UAT |
| N21-ACCESS-05 | PASS_LOCAL | unknown decision／duplicate click／readback recovery 不重複決定 | 仍未部署／未做正常公司 UAT |
| N21-PERF-01 | PARTIAL | viewport 功能／bounded selection 的 controlled fixture baseline | 沒有 production field LCP／INP／CLS 或部署版 performance acceptance |
| N21-PERF-02 | PASS_LOCAL | 記憶體實際建立100／1000／10000個不同公司ID，搜尋／分頁；各 n=10、100ms 延遲、初始公司清單請求≤2、p95≤2s | 只限 UI/transport；不是 DB capacity 或真實網絡量測 |
| N21-PERF-03 | PASS_LOCAL | 舊 query／scope response 取消及 late-result fencing；目錄 page24/cap1000 | 仍未部署／未做正常公司 UAT |
| N21-PERF-04 | PARTIAL | backend bulk bounds／恢復 contracts，單一 heavy job 資源紀錄 | 沒有真實10000項任務的端到端容量或成本驗收 |
| N21-UAT-01 | BLOCKED | 同專案合成旅程已有 durable chain | 未有真實 FIMMICK 員工／主管的正常身份任務成功率與完成時間 |
| N21-UAT-02 | BLOCKED | 自動化語意／焦點／鍵盤恢復與 reflow | screen reader／人工 zoom／完整真人鍵盤驗收未執行；不得宣稱 WCAG AA 全部通過 |
| N21-UAT-03 | BLOCKED | Chromium／Firefox／WebKit 公開端、同專案旅程及關鍵 history 引擎自動化 | 不等同真實 Safari、實體 iOS／Android 或觸控／virtual keyboard UAT |
| N21-UAT-04 | BLOCKED | 可讀來源與政策摘要由 canonical data 派生 | 沒有真實業務用戶對文案／政策／unknown 狀態理解的觀察證據 |
