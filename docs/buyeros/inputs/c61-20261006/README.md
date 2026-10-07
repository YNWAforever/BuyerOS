# BuyerOS GPT‑6.1 Sol 修復交接包

先讀 `BuyerOS_Codex_GPT61_Implementation_Plan_2026-10-06_zhHK.html` 或同名Markdown；直接交給Codex時使用 `BuyerOS_Codex_GPT61_Start_Prompt_2026-10-06_zhHK.md`。

- `docs/superpowers/plans/`：總計劃與四份子計劃，複製到repo相同路徑後可持續更新。
- Task Tracker：30項任務、原A26/Q/N對應、依賴、估工、owner、驗收與回退。
- Case Traceability：114原始case的所有欄位保留，追加本次execution欄位。
- New Test Cases：16個新增高風險case，全部not-run。
- `docs/buyeros/audits/2026-10-06/`：隨行spec；`evidence/`為原輸入ZIP，不是重新稽核。
- `validation.json`：本計劃完整性、coverage、DAG、路徑檢查與SHA256。

檔案路徑均相對repo root。子計劃的全域環境規則見總計劃；技術接口標示為計劃新增的，並非現況。未修改BuyerOS程式、登入、外寄或部署。
