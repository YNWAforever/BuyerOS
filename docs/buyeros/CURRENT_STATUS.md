# BuyerOS current status — T21 local candidate

Updated: 2026-10-21T22:55:38.922028+00:00. 本文件描述此專用 worktree；新候選仍未提交／推送／部署。

## 版本與證據層

| 層級 | 已核實狀態 |
|---|---|
| Audit / GitHub main | `c529dc8523a1d82da91243aaf33ea680a574277f`；GitHub ref 與原 main CI run 已唯讀重新核對 |
| 原 checkout | `3f10f419`；保留其既有檔案、未追蹤資料、備份及 .gitignore |
| 本機候選 | `codex/t21-workflow-20261022`，base 加未提交 diff；完整指紋見 version-matrix.json |
| 現有 main CI | Run 39111507046 / c529 main 成功；不是新 diff 的 CI |
| 新候選 CI | NOT_RUN：尚未 commit／push |
| 正式 alias | dpl_DcRxZFpfV6zHYbQyP6rmkxWQvJbc / CLI / READY；未返回 gitSource，正式 source/API/worker/schema 仍 unknown |
| 公司 Google / human UAT | NOT_RUN；fixture／CI 不替代正常身份與人工驗收 |

## 本機變更

- 單一雙語 auth surface；exact trusted social-init contract；native recovery 與去敏 support correlation。
- Preparation/Draft 多 editor transition guards、原 intent recovery、history/unload 保護；queued action 固定原 preparation ID。
- 研究轉頁修正 render snapshot／history commit 的次序；慢轉頁時先移除舊 editor。
- 公司搜尋有界分頁／獨立 retry；買家 domain／fit／來源摘要明示 Unknown；受限成員目錄姓名與 Mine／Unassigned。
- Canonical policy business summary，exact JSON/hash 折疊；原 authority／version/hash refusal 不變。
- 強制 expiry 清除保護資料並明示未提交 preparation 不保留；只新增一般 in-memory boolean，沒有文字儲存。

## 本機測試

| Proof | 狀態 |
|---|---|
| N | PASS — `.superpowers\t21-20261022\evidence\native-final-46-r2.json` |
| P | PASS — `.superpowers\t21-20261022\evidence\public-final-chromium-r2.json` |
| A | PASS — `.superpowers\t21-20261022\evidence\auth-final-5-r2.json` |
| S | PASS — `.superpowers\t21-20261022\evidence\sdk-final-9-r2.xml` |
| POL | PASS — `.superpowers\t21-20261022\evidence\policy-final-9-r2.json` |
| L | PASS — `.superpowers\t21-20261022\evidence\thin-final-chromium-r2.json` |
| R | PASS — `.superpowers\t21-20261022\evidence\audit-risk-final-r3.json` |
| PF | PASS — `.superpowers\t21-20261022\evidence\public-final-firefox-r2.json` |
| PW | PASS — `.superpowers\t21-20261022\evidence\public-final-webkit-r2.json` |
| LF | PASS — `.superpowers\t21-20261022\evidence\thin-final-firefox-r2.json` |
| LW | PASS — `.superpowers\t21-20261022\evidence\thin-final-webkit-r2.json` |
| HF | PASS — `.superpowers\t21-20261022\evidence\history-final-firefox-r2.json` |
| HW | PASS — `.superpowers\t21-20261022\evidence\history-final-webkit-r2.json` |
| API | PASS — `.superpowers\t21-20261022\evidence\api-final-1-api-full.xml` |
| W | PASS — `.superpowers\t21-20261022\evidence\worker-final-1-worker-full.xml` |
| FE | PASS — `.superpowers\t21-20261022\evidence\verification-commands-frontend-final-5.json` |
| CTRL | PASS — `.superpowers\t21-20261022\evidence\verification-commands-controls-final-5.json` |

完整命令／計數及原始證據見 [local-proof-summary.json](continuation-20261021/local-proof-summary.json)。
原先 frontend251、thin-journey-4及第一輪final的成功／失敗保留為歷史；最終結果以 frontend-final-5／Native46-r2／journey-r2／risk-r3 為準。R2以後只改risk fixture config，完整frontend/controls及risk92已重跑；產品runtime及artifact相同。跨引擎自動化不代替實體 Safari／正常公司身份驗收。

## 驗收缺口與發布邊界

- [全部72個 N21 案例](continuation-20261021/CASE_RESULTS.zh-HK.md) 分清 PASS_LOCAL、PARTIAL、BLOCKED；不代表72個人工案例全部執行。
- [Task ledger](continuation-20261021/task-ledger.json)／[Finding ledger](continuation-20261021/finding-ledger.json) 保留歷史 F01–F24 及原 F13/F25–F34。
- 真實 Google／branch JWT／FIMMICK membership、同版受控 hosted 環境、正式 provenance 仍需獨立確認；不沿用 admin/mock 代替。
- 人工 goldset、真人 usability、screen reader／zoom、實體 Safari/mobile、field LCP/INP/CLS 尚缺，不能宣稱 world-class／完整 WCAG 或正式就緒。
- 本輪沒有 migration/grant/Auth/Secret/安全設定變更，沒有提交24/57；付費 provider、enrichment、真實寄送及正式/rehearsal worker 維持停用。
- 後續 commit／push／PR、部署／正式前置、公司 UAT 寫入須各按明確授權處理；保留 Native worktree 與所有證據。

歷史 CURRENT_STATUS 原文已保存於此 worktree evidence/CURRENT_STATUS.before-T21.md，Git parent 亦保留原版本。
