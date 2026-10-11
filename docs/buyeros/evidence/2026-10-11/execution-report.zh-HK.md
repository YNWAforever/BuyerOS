# 2026-10-11 BuyerOS 實作批次

此批交付 source 修復和隔離驗證；G0、GN、GA、GS 全部仍未接受。主計劃原文在 `docs/superpowers/plans/2026-10-11-buyeros-gpt61-fixes.md`。原 ZIP、28 項 manifest hashes、F01–F24、33 個 C61 task 和 148 個 case 均保留；原本 current 欄位另存 retained audit 欄，新的 current tracker 不覆蓋 baseline。148 是 inventory，並非 148 個本輪 pass。

## 已實作

| 範圍 | 改動及本地證據 | 正式狀態 |
|---|---|---|
| C61-01 | fresh fetch 確認 main 仍是稽核 cbbe0e9；production source 一致。reuse/modify/activation-only/acceptance-only/blocked 選擇已逐 task 記錄 | 截圖 JPG 未隨包提供；API/worker 精確 runtime metadata 未證實 |
| C61-31 | 只讀 bounded runtime probe：target/head/lineage/role/visibility/column/function/grants/FORCE RLS；拒絕繼承 privileged role，綁定完整contract digest。RED→GREEN，16 strict DB controls | named Neon production branch 為0033、缺 identity/directory；runtime 缺 version SELECT。仍不能把 sensitive Vercel DSN 綁到該 branch |
| C61-32 | 在隔離0033確實重現42P01，沿既有0034–0050明確 chain 恢復；保留UUID/FK/membership/preference/policies、revoked replay。1新 rehearsal + 101既有 focused auth/rollback controls | 無正式 migration；review packet/offline SQL 已備，但 exact target／PG18副本／restorepoint／canary／scope authorization 未齊 |
| C61-33a/28a | typed evaluator、required CI全集、artifact/config/DB/schema/canary/rollback receipt joins，guarded workflow 實際 alias entry point；40拒絕/正常 transport controls，防止activation越gate與跨project/team/repository | remote auto-assignment仍true、main未protected；trusted runtime producer與protected environment未採用，33 parent及28b open |
| C61-02/03/06 | clipboard await/catch，成功或可選取 fallback；zhHK aria-live；pending retry disabled、last checked。4新增RED→GREEN + 17既有auth/revocation，共21 built pass | candidate功能；尚未部署、員工與screen-reader驗收未完成 |
| C61-15 | capabilities使用當前registry狀態，保留未配置/blocked/ready之差；沒有factory或外部call。42 focused pass | DEFAULT_REGISTRY仍空；provider帳戶/contract/tariff/budget/activation未接受 |
| C61-07/11/13 | 真Neon spec獨立native discovery 2，無identity/JWKS/session mock；登入/恢復/two-tab及獨立Neon-only rollback驗收準備 | 只收錄，真實執行0；Google/enrollment/reset/兩tenant四roles/相容artifact IDs仍blocked |

其他已存在的研究、覆核、草稿、approved export、bulk、delivery、retention/cold restore 功能沿用，未重寫。81 Node focused controls及既有strict auth controls是fixture/source回歸，不能冒充live acceptance。F21仍是歷史unknown；F23是本次42P01另案；F22只關稽核版本差距。

## 可操作的 blocked 項

1. G0：提供原截圖；從實際部署runtime取得same-target/head/search_path/role/grants/mapping讀回；known-account canary；可用frontend+API rollback及restorepoint。formal packet是reviewable但尚不具備正式執行条件，不能盲升head/stamp/建空表/email-link/放寬RLS。
2. Promotion：owner採用reviewed remote staging/main required checks/environment reviewers、短效repo-scoped metadata token及真正runtime receipt producer。source gate不是live promotion驗收。
3. GN：明確隔離Neon/email/Google帳戶、enrollment/reset郵件授權；真session、UUID/FK與revoked/foreign控制；independent Neon-only rollback及cold restore讀回。
4. GA：reviewed provider account/model/filter/pricing/liability與零外推的支出上限；同一chain worker/provider/API八模組；60-company/100-claim真人goldset；同環境performance樣本與operator/reviewer UAT。worker只讀查詢回10007，不推論所有accounts都不存在。
5. GS：GA/C61-29後才處理C61-14 Auth0退役。再核對server-owned delivery authority、sender/recipient/成本上限、一次submission及callback/suppression delivered證據。unknown/accepted不重送，hold不釋放。

本輪production/schema/auth/provider/spend/send mutation均為0。未使用舊325、93 operations定義、READY或health/live替代workspace驗收。一般source和isolated tests已持續執行；外部條件欠缺逐gate保留，不宣稱完整研究或站內外展可用。

## 證據入口

- `current.json`：各task source/test/deploy/activation/live acceptance獨立欄位及blocked。
- `current-tasks.csv`、`current-cases.csv`：本輪current與retained audit current並存。
- `batch-local.json`：各focused suite實際JUnit SHA256，0 fail/error/skip，測試環境限定。
- `db-readback.redacted.json`：named production branch runtime只讀結果，same-deployment match仍null。
- `schema-change-set.json`／offline SQL與兩份runbook：範圍、雜湊、stop conditions、相容rollback及promotion adoption缺口。

required final CI及whole-branch review結果由draft PR相同candidate的checks讀回；本文件不把pending寫成pass。
