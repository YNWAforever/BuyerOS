# BuyerOS — Codex GPT-6 Sol 執行計劃（2026-10-03 更新）

本計劃依本次八模組稽核與之前Neon Auth計劃重寫。基線 main／production為 `a78859fe474f5722be3755b10e2586436b53bf97`。完整結論及證據在同包稽核報告；21 findings、25 tasks。

**產品修復尚未開始。** 本次稽核沒有產品commit、正式membership變更、Neon配置、provider啟用、寄信或部署。

## 第一批
先做Q01的UI、Q03、Q04、Q15；可先在本地／隔離fixture完成。N00先做相容性spike，Q12獨立實作來源覆核。Q16以唯讀資料調查workspace500；未有根因前不猜測Q17修法。

## 不可破壞的條件
保留canonical users.id、membership、歷史actor及RLS；不依email自動link；Neon provider role不代表workspace角色；寫入保持If-Match與idempotency；unknown provider結果保留hold並reconcile；delivery維持403。
Auth0→Neon須按N00–N07分步。先驗證Vinext／Nitro相容，再加入身份映射與EdDSA verifier、session恢復及有限雙issuer切換。不可只改issuer環境變數。
舊N00–N07及Q01–Q11 ID維持；新增Q12–Q17。估算為人日，不是Codex執行時間承諾。

## 任務

### N00 · Neon框架相容及精確契約spike
- 問題／優先：F20；P1。狀態：待開始。
- 修改範圍：Vinext/Nitro兩種輸出；auth session／JWT／same-origin proxy；pin SDK。
- 依賴：無。責任：Identity＋Frontend。估算：1–2人日（粗估，非承諾）。
- 驗收：登入→session→token→FastAPI→logout在兩種build實測；明列issuer/audience/JWKS與cookie；失敗不能只改env。
- 案例：NA01。證據：E03;E09。
- 回退：刪隔離spike分支；舊auth不變。
- 受阻：沒有已知阻擋；按repo與環境核對。

### N01 · 隔離Auth設定與production差異
- 問題／優先：F20；P1。狀態：待開始。
- 修改範圍：Neon Auth環境、trusted domains、cookie secret、OAuth／email。
- 依賴：N00。責任：Platform。估算：1人日（粗估，非承諾）。
- 驗收：preview與production分離；secret不在client/log；只設定已選登入方法；用戶資料不跨branch洩漏。
- 案例：NA02;NA03。證據：E09。
- 回退：回復設定版本；保留migration evidence。
- 受阻：實際建立服務／發驗證信／付費需對應授權。

### N02 · 身份映射保持User與membership
- 問題／優先：F01;F20；P1。狀態：待開始。
- 修改範圍：新增auth identity關聯；workspace discovery及load_membership用shared canonical resolver。
- 依賴：N00。責任：Backend／Identity。估算：2–3人日（粗估，非承諾）。
- 驗收：同一已核實使用者保留users.id；roles、ownership、approvals、audit actor均不重建；同email不自動link；唯一鍵與對帳可追查。
- 案例：NA07;NA08;NA09;NA10。證據：E03;E09。
- 回退：保留additive mapping；關閉新provider，不還原整個DB。
- 受阻：沒有已知阻擋；按repo與環境核對。

### N03 · Neon JWT驗證及有限雙issuer
- 問題／優先：F20；P1。狀態：待開始。
- 修改範圍：verifier／JWKS cache：RSA Auth0與Ed25519 Neon分開allowlist。
- 依賴：N00;N02。責任：Backend／Security。估算：2人日（粗估，非承諾）。
- 驗收：錯alg／iss／aud／kid／過期拒絕；rotation與cache outage測試；不使用Neon role決定workspace權限。
- 案例：NA11;NA12;NA13;NA14;NA15;NA16。證據：E03;E09。
- 回退：provider flag切回已授權舊路徑；撤回新issuer接受。
- 受阻：沒有已知阻擋；按repo與環境核對。

### N04 · Neon UI及session恢復
- 問題／優先：F02;F15;F20；P1。狀態：待開始。
- 修改範圍：登入／callback／session provider／token renewal／zh-HK。
- 依賴：N01;N03;Q01。責任：Frontend。估算：2–3人日（粗估，非承諾）。
- 驗收：刷新／新分頁／deep link／15分鐘JWT換取／logout撤回／disabled member皆有清楚結果；無token localStorage。
- 案例：NA04;NA05;NA17;NA18;NA19;NA20;NA23;U14。證據：E03;E09。
- 回退：旗標回復前一UI；不丟membership／歷史資料。
- 受阻：沒有已知阻擋；按repo與環境核對。

### N05 · 身份及八模組回歸
- 問題／優先：F20；P1。狀態：待開始。
- 修改範圍：CSRF／cross-tenant／revocation／role change／full staff flow。
- 依賴：N02;N03;N04。責任：QA＋Security。估算：2人日（粗估，非承諾）。
- 驗收：必要owned DB／UI cases零skip；所有角色與8模組完整journey；worker HMAC未受影響。
- 案例：NA21;NA22;NA24;NA25;NA26。證據：E09。
- 回退：阻止cutover；不減斷言來通過。
- 受阻：沒有已知阻擋；按repo與環境核對。

### N06 · 帳戶轉移演練與對帳
- 問題／優先：F01;F20；P1。狀態：待開始。
- 修改範圍：身份prove-and-link；受控OAuth reauth／password reset；異常清單。
- 依賴：N05。責任：Identity＋Admin。估算：1–2人日（粗估，非承諾）。
- 驗收：mapping數／membership數／角色／owner／歷史actor逐項一致；duplicate／unmapped拒絕自動提權；無密碼可匯出假設。
- 案例：NA06;NA27。證據：E09。
- 回退：關閉新mapping使用；保留可審計舊identity。
- 受阻：沒有已知阻擋；按repo與環境核對。

### N07 · 受控Neon切換及Auth0退役
- 問題／優先：F20；P1。狀態：待開始。
- 修改範圍：有限雙auth→Neon only→舊secret／callback清理。
- 依賴：N06;Q11。責任：Release owner。估算：1–2人日（粗估，非承諾）。
- 驗收：切換前後8模組驗收及觀察；未知寫入不重播；rollback不restore業務DB；到期後Auth0 token拒絕。
- 案例：NA28;NA29;NA30。證據：E02;E09。
- 回退：有期限回舊auth；新Neon會員須明確恢復策略。
- 受阻：production授權、可用會員、rollback rehearsal。

### Q01 · 修復auth狀態、空存取與語言
- 問題／優先：F01;F02;F15；P1。狀態：待開始。
- 修改範圍：workspace-picker／callback／provider；UI初始化與config錯誤分離。
- 依賴：無。責任：Frontend＋Admin。估算：1–2人日（粗估，非承諾）。
- 驗收：無membership能切繁中及重新核對；配置正確無false alert；精確issuer/sub由admin核對，無email自動升權。
- 案例：U01;U02;U03;U13。證據：E01;E03;E07。
- 回退：revert UI；保留授權fail-closed。
- 受阻：正式會員核對需管理員；UI可先做。

### Q02 · 成員分頁與可辨識身份
- 問題／優先：F03;F04；P1。狀態：待開始。
- 修改範圍：settings／memberships API；另提供operator可用的最小eligible-assignee lookup。
- 依賴：N02。責任：Frontend＋Backend。估算：2–3人日（粗估，非承諾）。
- 驗收：250成員全部可達；搜尋第101位；同名／尾碼碰撞可辨；last-admin競態與逐人原因通過。
- 案例：U06;U07;U08;S06。證據：E03。
- 回退：revert分頁UI／投影欄；不rollback已審計角色變更。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q03 · Operations契約與結果分頁
- 問題／優先：F05；P1。狀態：待開始。
- 修改範圍：generated AsyncJob／BulkItemResult.id；remove handwritten Job；detail paging。
- 依賴：無。責任：Frontend。估算：1人日（粗估，非承諾）。
- 驗收：21及101結果均可讀完整ID；真實payload render無undefined key；cross-workspace job拒絕。
- 案例：B10;B11。證據：E03。
- 回退：revert consumer；server contract不變。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q04 · 研究建立保留操作意圖
- 問題／優先：F08；P1。狀態：待開始。
- 修改範圍：run-progress／ActionIntent；建立與查詢recovery。
- 依賴：無。責任：Frontend＋Backend。估算：1–2人日（粗估，非承諾）。
- 驗收：commit後丟202再按Retry：只一run／outbox／economic intent；body或scope改變才新key；doubleclick共享pending。
- 案例：B05;B06。證據：E03;E05。
- 回退：暫停新research建立；保留已有run／holds／outbox。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q05 · 分派同事與精確批量確認
- 問題／優先：F06；P1。狀態：待開始。
- 修改範圍：eligible owner picker；scope/selection/owner/reason fingerprint。
- 依賴：Q02。責任：Frontend＋Backend。估算：1–2人日（粗估，非承諾）。
- 驗收：選5後加1清confirm；可指定同事／自己／無owner；preview後owner失效由server拒絕；逐列版本正確。
- 案例：B02;B03;B04;B07;B16。證據：E03。
- 回退：關閉新版bulk入口；不自動撤銷已完成分派。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q06 · 有界job summary輪詢
- 問題／優先：F07；P1。狀態：待開始。
- 修改範圍：summary／paged results分離；abort／single-flight／visibility／backoff。
- 依賴：Q03。責任：Frontend＋Backend。估算：1–2人日（粗估，非承諾）。
- 驗收：running1000results/RTT2.5s下每view最多一個progress request；hidden停止；未開結果不遍歷歷史頁；429尊重Retry-After。
- 案例：B12;B13;P04。證據：E03。
- 回退：回退到手動Refresh，不恢復高頻全結果輪詢。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q07 · 草稿控制項與模板承諾一致
- 問題／優先：F09；P2。狀態：待開始。
- 修改範圍：移除無效tone/objective或實作有引用約束的免費style/CTA。
- 依賴：無。責任：Frontend＋Backend。估算：1人日（粗估，非承諾）。
- 驗收：兩組purpose/tone的行為與UI說明一致；zh-HK引用原語言有說明；不新增付費模型。
- 案例：A02;A07。證據：E06。
- 回退：恢復固定模板並明確標示限制。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q08 · 10k分段維護manifest
- 問題／優先：F11；P2。狀態：待開始。
- 修改範圍：server frozen IDs/versions；chunks／結果／failed-only retry。
- 依賴：Q05;Q06。責任：Backend＋Frontend。估算：3–5人日（粗估，非承諾）。
- 驗收：1000/1001限制不誤選；10k逐段總數一致，50衝突不改寫；重試不重做已成功列；中斷可恢復。
- 案例：B01;B08;B09;B14;B15。證據：E03。
- 回退：停止新manifest；已commit結果保留並可查；不盲目Undo。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q09 · 日常任務優先的八模組UX
- 問題／優先：F14;F04；P2。狀態：待開始。
- 修改範圍：compact scope；buyer主區與sticky bulk bar；human labels；shared dictionaries。
- 依賴：Q01;Q02;Q14。責任：Product designer＋Frontend。估算：3–5人日（粗估，非承諾）。
- 驗收：3–5員工完成五項任務≥90%；錯scope0；390px／200%／鍵盤／screen reader；記前後時間與失誤。
- 案例：U09;U10;U11;U12。證據：E03。
- 回退：按模組feature flag回退；資料契約不變。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q10 · 效能與真實準確率驗收
- 問題／優先：F12；P1。狀態：待開始。
- 修改範圍：隔離load／goldset／provider canary／可重跑結果。
- 依賴：Q06;Q08;Q12;Q13。責任：QA／Data／SRE。估算：3–5人日（粗估，非承諾）。
- 驗收：按報告先定門檻；分層200公司holdout及3次重跑；輸出p95/p99與CI；不把fixture當liveaccuracy。
- 案例：A03;A04;A05;A06;A08;P01;P02;P03;P04;P05;P06;P07;P08;P10。證據：E04;E06;E08。
- 回退：停壓測／canary；保留證據與holds。
- 受阻：真provider、隔離資料及成本上限未就緒。

### Q11 · 單一現況與分能力release gate
- 問題／優先：F10;F13；P1。狀態：待開始。
- 修改範圍：CURRENT_STATUS／operation ledger／readiness／owner與時間；記code/deployment/DB/jobs/provider/UAT。
- 依賴：無。責任：Release owner＋SRE。估算：1–2人日（粗估，非承諾）。
- 驗收：main/live明確；每個deployed驗收附case；schema/role/selector讀回；restore及告警有責任人；未驗不得markcomplete。
- 案例：R01;R02;R03;R04;R05;R06。證據：E02;E03。
- 回退：只回復文件與UI；activation rollback依實際service runbook。
- 受阻：正式DB／worker readback與外部recovery證據仍缺。

### Q12 · 人工改稿的来源覆核與重新審批
- 問題／優先：F16；P1。狀態：待開始。
- 修改範圍：revision-bound claims mapping／human grounding review endpoint與UI；current facts/policy再驗。
- 依賴：無。責任：Backend＋Frontend＋Reviewer。估算：2–4人日（粗估，非承諾）。
- 驗收：改正文→保存→逐句來源覆核→exact review→approve→export完成；新revision撤舊approval；無引用／跨company／stale evidence拒絕；不直接設grounded。
- 案例：D01;D03;U09。證據：E03;E06。
- 回退：關閉新覆核入口，保留needs_review與修訂；不自動批准。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q13 · Workspace membership discovery去全域掃描
- 問題／優先：F18；P1。狀態：待開始。
- 修改範圍：canonical identity lookup；受限制的DB端membership discovery＋pagination。
- 依賴：N02。責任：Backend／DB。估算：2–3人日（粗估，非承諾）。
- 驗收：ownedPG證明querycount不隨無關workspace線性增长；頁面完整；RLS／active／revocation不退化；禁止BYPASSRLS捷徑。
- 案例：P09;P10;S06。證據：E03;E06。
- 回退：切回舊read策略；保留新schema兼容；不撤銷member資料。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q14 · 工作數與列表使用相同scope
- 問題／優先：F17；P2。狀態：待開始。
- 修改範圍：overview／operations query builder；project_id與workspace視圖切換。
- 依賴：無。責任：Frontend。估算：1人日（粗估，非承諾）。
- 驗收：A0/B5 fixture統計與點入列表一致；admin全workspace明確標籤；非admin仍actor-bound。
- 案例：U15。證據：E03。
- 回退：回復UI；server授權不改。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q15 · 草稿dirty guard與明確保存選擇
- 問題／優先：F19；P1。狀態：待開始。
- 修改範圍：Refresh draft／job／open共用Save/Discard/Cancel。
- 依賴：無。責任：Frontend。估算：1人日（粗估，非承諾）。
- 驗收：Cancel不改local subject/body/language；Save成功再換；Discard明確；412保留local供比較。
- 案例：D02。證據：E03。
- 回退：revert guard UI但保留local暫存；不得清除未保存內容。
- 受阻：沒有已知阻擋；按repo與環境核對。

### Q16 · 調查workspace500根因
- 問題／優先：F21；P1。狀態：受阻。
- 修改範圍：精確requestID／時間的DB、pool、schema/role、timeout資訊；唯讀。
- 依賴：無。責任：SRE／Backend。估算：0.5–1人日（粗估，非承諾）。
- 驗收：以同時間診斷確定或明確排除原因；保留最小重現與錯誤分類；不能只寫Neon冷啟動。
- 案例：U16。證據：E07。
- 回退：純調查無產品rollback。
- 受阻：目前日志只有OperationalError，缺底層診斷。

### Q17 · 按已確認原因修復workspace500
- 問題／優先：F21；P1。狀態：受阻。
- 修改範圍：Q16結論所指最小連線／查詢／環境修復；有上限GET retry。
- 依賴：Q16。責任：Backend／SRE。估算：待Q16後估人日（粗估，非承諾）。
- 驗收：原觸發條件下讀取成功；失效role/schema仍清楚報錯；不加無限retry；無盲目重播write。
- 案例：U16;P01;P02。證據：E07。
- 回退：依具體變更revert設定／程式；不restore業務DB。
- 受阻：依賴Q16根因；不預設加pool。

## 執行提示


```text
你正在 BuyerOS 工作。先讀 repo 的 AGENTS.md（如有）、本報告、Operation Inventory、Test Cases、Implementation Tasks及 evidence/E02、E03、E06、E07。
重新取得目前 main／工作分支／production source SHA；本報告基線為 a78859fe474f5722be3755b10e2586436b53bf97。若已變更，逐項重查F-ID，不重做已完成工作。

這次先實作Q01的初始化／空狀態／語言UI、Q03、Q04和Q15。分小PR、使用既有generated contract與ActionIntent，不重寫整個產品。Q16同步只讀調查500；無根因則記blocker。
Q01：auth initializing不能當config_error；無membership也可讀繁中，提供可重試access與安全support資訊；不自動新增會員或依email升權。
Q03：Operations改讀BulkItemResult.id，使用generated type，補結果分頁；21／101 rows和actual payload render測試。
Q04：Start research同意圖跨lost202重試用同key，body／scope／ICP改變才新intent；隔離DB驗證只有一run／outbox／經濟意圖。
Q15：Draft refresh／open／job materialization統一dirty guard，按鈕語意與真正Save／Discard／Cancel一致；取消不改任何本地內容。

另以N00開始Neon Auth相容性spike，按N00–N07計劃遷移；保留canonical users.id、memberships與歷史actor；禁止email自動link、禁止把Neon role當workspace role。不要只替換AUTH0_ISSUER。
Q12必須補人工引用覆核流程，不能用設grounded=true繞過審批。

執行相關unit／contract／UI及必要owned-Postgres測試。記錄SHA、命令、pass/fail/skip、artifact；缺DB不得將skip當pass。以同case ID更新矩陣，產品修改只有驗收成功才標「已驗證完成」。
不啟用real provider／delivery，不發外展訊息，不改正式會員，不自動部署或migrate production。完成可review的變更、測試及rollback後交接；只有另有明確授權才做正式切換。
```



## 完成定義
每個任務須有commit SHA、相關測試命令、pass/fail/skip、案例結果及artifact。程式碼存在或CI success不等於正式UAT；缺DB／角色／provider時記受阻，其他獨立工作繼續。所有正式切換需具體授權與可review的readback／rollback方案。