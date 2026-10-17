# Native provider policy 最小差異

使用者授權：2026-10-17，本機設計、實作及合成隔離測試；不 commit/push、
部署、改正式 DB/權限、提交24/57、啟用付費 research/enrichment 或寄信。

基準：`codex/controlled-policy-activation-20261017`，HEAD `51532f19`；
沿用未提交 Native 實作及備份，不改 `.gitignore`。

## 原因與範圍

`manual-native.v1` 刻意沒有 provider 動作。raw `permitted` fixture 不具有
authority/request/resolution 證據；不能拿人工 grant 當付費或傳送授權。

新增 opt-in `provider-native.v1`，沿用三張 append-only 表及相同 owner approval、
CAS、withdrawal、expiry、audit、idempotency。authority 必須明確包含新動作，
現有 manual designation 不會自動擴權。沒有新增 admin/self-designation route。

| purpose | 封閉 action | 必要範圍 |
|---|---|---|
| contact_research | contact.enrich | provider、account、reviewed contract SHA256、exact project/source |
| contact_research | contact.read | 指定已保留、已核查 contact IDs；enrichment grant不隱含可讀全部渠道 |
| draft_preparation | draft.generate | exact sender；已列 recipient 或明確准許不指定 recipient 的草稿 |
| outreach | delivery.review、delivery.send | exact sender/recipient；send 額外精確匹配 provider/account/contract |

terms 保留既有期限、用途、來源、資料類型、retention/deletion、owner 批准證據。
同一purpose沿用最新head；需要同時保留人工動作時，owner必須在provider terms內
明列該人工動作，authority亦須覆蓋；不自動繼承舊grant、不回退尋找較舊permitted。
provider fields 並非秘密或 credential。review 只授權內部審閱，
不能單憑 review 動作提交；send 仍需要原有具體內容 approval、sender verification、
selected delivery authority、recipient scope、suppression、budget、runtime 及 dispatch flags。
本案不新增 consent 聲明或推廣法律依據；真實內容仍待資料擁有人確認。

## 任務與驗收

1. 先寫 provider terms 正反測試，確認缺少契約的 RED；新增嚴格契約和 matching。
   manual wire/hash 不變；不接受 wildcard、actor/time/status 偽造。
2. 原有 Native bootstrap/action 驗證只增加封閉新 action；API 仍拒絕 raw permitted。
3. API/worker 在 canonical quote/receipt/draft/delivery 邊界建立 use context。
   contact quote/confirm/claim 每次綁定 current reviewed account/contract；
   send 在 reserve/claim/post 前重查，retained GET/reconciliation 不依賴新授權。
4. 在尚未發布的 0056 中增補 outreach purpose；worker 僅獲 proof 必需欄位 SELECT，
   load_only + raiseload 防止意外讀取其他欄位；保留 FORCE RLS 及全部 DML 拒絕。
   不改已合併0055，不連正式DB。
5. 合成 fixture 走真正 bootstrap + submit + decide；拒絕錯誤 scope、失效/revoke、
   跨 tenant、預算不足；並驗證回應遺失/unknown 不重新 submit、不釋放 hold。
6. 執行 focused API/worker、既有 policy 回歸、契約生成/typecheck；
   所有真實外呼為0，正常設定paid/delivery仍false、未安裝provider selection。

審查補修：usage以`contact.read`判斷指定渠道；contact CSV export沿用現有
`export_accounts`/`export_contacts`獨立權限，再傳入exact sender/recipient的
`delivery.review`用途context，不能拿此內部review動作當send grant。兩者均檢查
contact retained/checked期限；合成fixture不再用raw outreach permit通過受控閘門。

只修本差異影響的已存在流程。完整API/worker、browser、CI、正式UAT若未跑，
須明確列為未驗證，不借用歷史綠燈。所有 logs/receipts 保留。
