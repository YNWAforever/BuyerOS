# 原生 PowerPoint 私有附件

日期：2026-10-14。設計基準為已部署的 `fcfa5a6e044df21bb26968c051a6aa0ee999bb92`。本文件待使用者審閱；尚未新增產品程式、依賴或資料庫結構。

## 目的與驗收

使用者選擇優先支援原生 PowerPoint 附件。成功條件是：兩份原始 `.pptx` 都能在現有專案上傳、保存原始 bytes、查閱逐頁來源，並與產品輪廓的完整保存流程一起使用。現有買家、已保存輪廓、附件及操作回執必須保留。

本次接受上限 20 MiB 的 `.pptx`。PDF、TXT、MD 仍以 5 MiB 為檔案上限。分段傳輸解決 Functions 的 4.5 MB 請求限制，而不是調高單次請求上限。原生格式支援不包含 `.ppt` 或 `.pptm`。

一份來源簡報沒有可編輯文字，另一份有逐頁文字。前者成功保存後顯示「圖片簡報，未抽取可編輯文字」，保留既有 Markdown 文字來源；後者提供按投影片順序排列的原文。抽取不使用 OCR、LLM 或研究供應商。候選事實仍須人工批准。付費研究、草稿生成及寄信保持未啟動。

來源細節、檔名、檔案 hash、客戶內容及正式環境 ID 留在既有私人驗收包，不提交 Git。

## 使用者操作

1. 在現有「產品資料 → 產品文件」選擇 PowerPoint。選檔時顯示檔案上限及大小；驗證不合格時在傳輸前指出原因。
2. 點擊上傳後顯示已完成的分段數與進度。PowerPoint 每段最多 2 MiB；20 MiB 最多十段。大型既有格式也走此流程，小於等於 4 MiB 的 PDF/TXT/MD 保留既有單次上傳。
3. 中斷後先讀回原上傳狀態。頁面重開後要求重新選擇同一個檔案，比對完整 hash，繼續缺少的分段；不把原文存入瀏覽器持久儲存。
4. 完成時顯示 ready、投影片數、含文字的投影片數與解析說明。提供逐頁原文查閱及「下載原檔」，並可選為輪廓來源文件。下載完成前核對整份 hash，圖片簡報可透過原檔查閱。
5. 實際採用的產品候選事實保留來源文件及投影片位置。沒有抽出文字不等於資料已核實；頁面不宣稱圖片內容已解析。
6. 既有輪廓只在使用者明確儲存時建立新版本。上傳不會自動批准輪廓或啟動研究。

## 模組與資料流

| 部分 | 責任 |
| --- | --- |
| 附件前端及獨立上傳 client | 選檔、hash、原操作身分、分段進度、讀回與恢復；只保存有限的上傳識別 metadata |
| 上傳 session service | 工作區／建立者授權、固定 manifest、不可變分段、限額、到期及完成回執 |
| PowerPoint parser child | 有資源上限的 ZIP/XML 解析；只回傳排序後的文字及有限 metadata |
| 現有私有儲存及文件 service | 原子保存原始 bytes、OfferDocument、逐頁文字、候選事實、回執及已完成 outbox |
| 文件來源查閱 | 以現有讀取權限分頁提供逐頁文字，不暴露 object key 或公共檔案網址 |

第一版沿用已設定的 PostgreSQL 私有文件儲存。開始分段前明確檢查此能力；缺少設定時顯示可行的管理員提示，不切換到另一個供應商。舊的單次上傳及 R2 路徑保留既有行為。

## 上傳 API 與恢復

新增 API 使用現有同工作區的附件上傳權限，且每一步都重新檢查目前成員資格；session metadata 只供建立者操作。查閱完成的來源頁則使用現有文件讀取權限。

- **開始：** `POST /projects/{project_id}/offer-document-uploads`，帶原始 Idempotency-Key。manifest 固定 filename、media type、完整 SHA-256、byte length、2 MiB chunk size 及 chunk count。相同建立者、專案、manifest 的仍有效 session 可讀回重用。
- **狀態：** `GET /offer-document-uploads/{upload_id}`，只回傳 manifest、已收到的 chunk index/hash、expires_at、終態及完成的 document ID，不回傳 bytes。這也是完成回應遺失時的恢復路徑。
- **分段：** `PUT /offer-document-uploads/{upload_id}/chunks/{index}`，原始 bytes 加分段 hash。位置及長度由 manifest 決定。相同位置／內容可重送；不同內容回覆 conflict。服務端不覆寫已提交 bytes。
- **完成：** `POST /offer-document-uploads/{upload_id}/complete`，沿用原操作識別。先取得完整且已校驗的 immutable 分段，關閉資料庫交易後解析。最後重新授權並依既有 Project 鎖順序鎖定專案及 session，原子提交結果。
- **逐頁來源：** `GET /offer-documents/{document_id}/slides`，標準 offset/limit 分頁，最多每頁 20 張，回傳 slide number、原文及 text/image-only 標記。
- **原檔查閱：** `GET /offer-documents/{document_id}/content-chunks/{index}`，每次最多 2 MiB bytes 的 base64 envelope，包含 index、長度及 chunk/full-file hash。沿用同工作區文件讀取權限，拒絕 deleted/expired 文件。PostgreSQL 使用有界 bytea slice，不為每段讀回整份檔案；瀏覽器組合並核對完整 hash 後才下載，取消、換 scope 或任何錯誤均不產生部分檔案。原文不提供公開或把 bearer token 放在網址的下載連結。

完成不需要把整份檔案再從瀏覽器傳送一次。並行完成可重複計算有限解析，但只有一個結果可提交；另一個請求讀回同一回執。已完成且未到期的相同檔案在同專案重用同一份文件，避免不同 session 產生重複附件。

回應未知時先查狀態，保留原 manifest/key，不能換新 key 盲目重送。失去權限、專案封存、版本衝突及不同檔案均停止該寫入。已完成的回執仍可在目前授權下讀取，以釐清原操作結果。

## 資料庫與限制

新增一個 additive migration，保留現有資料並同步既有 schema receipt guards；不修改身分、角色、預算或 paid admission。

- **Upload session：** UUID、workspace/project/actor 複合關聯、immutable manifest、status、expires_at、完成的 document ID 及錯誤碼。狀態為 uploading/completed/failed/expired。
- **Upload chunks：** workspace、upload ID、index、body、byte length、SHA-256；唯一鍵 `(workspace_id, upload_id, index)`，複合 FK 固定 tenant。DB 驗證 hash 與長度，無一般 UPDATE bytes 權限。
- **Document slide text：** workspace/project/document 複合 FK、slide number、literal text、text classification。唯一 slide number；只讀取 ready 且未刪除／到期的同工作區文件。
- **OfferDocument：** 新增有界 extraction metadata，例如 format、slide count、text slide count、說明碼。原始 bytes 繼續放在 private_document_objects；其上限由 5 MiB 擴至 20 MiB，既有 hash／30 日保留約束不變。
- **索引／RLS：** 新表均 ENABLE/FORCE RLS，使用既有 `app.workspace_id`；應用角色只能透過指定操作存取。tenant/actor/project/status/expiry 查詢與所有複合 FK 有適當索引。

未完成上傳的可存取期限為一小時；同一建立者最多兩個 active session、同工作區最多八個，總 bytes 不超過各 manifest 宣告且每份最多 20 MiB。建立及限額判斷使用短交易中的穩定工作區鎖，避免並行繞過限額。

完成時在同一交易移除 staged chunk bytes。確定失敗時保留有限結果 metadata 並移除 staged bytes，不建立 ready 文件。到期後不可存取；一般授權附件活動做有界清理。沒有啟用維護 runner 時，不宣稱完全閒置期間的準時實體刪除。

## PowerPoint 解析

延伸現有 isolated PDF parser 的程序模式。子程序不取得 bearer token、object key、資料庫／供應商 credentials 或應用設定；停用網路，父程序八秒期限，Linux 使用既有 512 MiB 記憶體及六秒 CPU 上限。

明確限制：壓縮檔 20 MiB、最多 1,000 entries、總宣告及實際展開內容 64 MiB、最多 100 張投影片、單一 XML 2 MiB、全部抽取文字 100,000 UTF-8 bytes；有限 JSON 輸出最多 256 KiB。

使用 hardened XML parser，拒絕 DTD/entity、加密、巨量解壓、重複或越界路徑、宏及無效 package。依 presentation 的 slide relationship 順序讀取内部 slide XML，不以檔名排序代替實際順序。外部 relationships 只記錄「未讀取」，embedded workbook/物件不解析或執行，不因這些正常來源特徵宣稱已核實其內容。

只讀 slide literal text，不渲染 HTML、不跟隨超連結或外部資源。來源畫面使用 React 的文字轉義。`Product:` / `Value proposition:` 等現有固定標籤可產生有限、未批准候選。來源投影片位置納入既有 excerpt；候選完整 excerpt 在輪廓保存時依現有規則核對，不能由 client 偽造頁碼。保留原檔 SHA-256 作整份來源校驗。

解析失敗／逾時會產生可讀回的確定失敗結果，不產生 ready 文件、候選事實或排程。image-only 是成功保存的明確類型，不是解析成功內容的宣稱。

## 驗證及發佈

1. RED→GREEN：原生格式不支援、大檔傳输、缺段／亂序、hash 錯誤、重複分段、manifest 衝突、開始／完成回應遺失、重新選檔恢復、並行完成及權限中途撤銷。
2. 真實 PostgreSQL：跨 tenant/actor、FK/RLS、限額競態、immutable bytes、原子回執／document／outbox、到期／刪除、archive 競態及 populated downgrade guard。
3. Parser：實際投影片順序、中文與 Unicode、page provenance、全圖片、external relationships/embedded part 不被存取、宏、DTD/entity、path traversal、重複 entries、壓縮炸彈及程序期限。供應商／網路呼叫為零。
4. Browser：真實編譯畫面＋可丟棄資料庫，包含進度／重開／同檔恢復／不同檔拒絕、未批准事實、完整輪廓保存及重複附件；原檔下載的 bytes/hash、越權／到期、傳輸中斷、scope 取消及損壞 chunk 阻止下載。保留現有 133 browser cases 及完整 native discovery/JUnit gates，依真正新增 case 更新精確數量。
5. 私人來源驗證：兩份原始檔 hash 保持一致；15 張無文字簡報與 20 張文字簡報都可保存。檢查逐頁字數與頁碼，既有三份 MD 及 24 家買家仍完整。實際檔案不放入 Git/CI artifacts。
6. 完整 CI 通過後，才用精確 source SHA 建立正式候選。migration 先在可丟棄 DB 及隔離 Neon 分支演練，再準備 production backup、原子升級／讀回及候選檢查。正式上傳及新版本保存依已確認流程執行；付費供應商與寄信維持停用。
7. 正式驗收保留原檔 digest、兩份文件回執、逐頁來源、重新開啟保存結果、來源關聯及零研究／草稿／費用讀回；各類證據與 CI 分開。

rollback 保留目前正式部署。必須演練舊 source 對新 schema 的既有讀取相容性；有新資料或超過 5 MiB 原文時禁止直接 downgrade／縮小約束。無法安全回到舊 source 時，採用關閉新上傳入口及修復前進，保留已提交文件與回執。

## 使用者審閱狀態

使用者已選擇原生 PowerPoint 優先項目。本規格完成 source/schema 核對及範圍自查；待使用者審閱後進入實作。正式網站目前仍為已驗收的 fcfa5a6e。
