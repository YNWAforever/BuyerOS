# Provider 授權差異：本機交付與驗證

日期：2026-10-17（Asia/Hong_Kong）。
使用者授權限本機實作／合成隔離測試；不是正式政策、支出、寄信或發布批准。

## 版本與範圍

- Worktree：`C:/Users/laich/.codex/worktrees/policy-activation-native-20261017/BuyerOS`
- Branch：`codex/controlled-policy-activation-20261017`
- HEAD/base：`51532f19c19dd10ab3aa6c4a5fac87bc039856bb`，全部實作仍未提交。
- 沿用原有 dirty Native 工作；備份／未追蹤資料保留，沒有修改 `.gitignore`。
- 沒有 commit/push、正式 migration/grant、credential/security change、部署、
  公司帳戶 UAT、24/57 提交、真實付費呼叫或外部發送。

設計見同目錄 `2026-10-17-provider-policy-delta.md`。

## 最小授權差異

`manual-native.v1` 保持原有 wire/hash 與人工範圍。新增 opt-in
`provider-native.v1`，仍使用 Native authority → request → resolution → audit，
沒有 raw-permitted 繞過、fixture-only production flag 或新的自授權 endpoint。

| 動作 | 伺服器核對 |
|---|---|
| `contact.enrich` | exact workspace/project/source、provider、account、reviewed contract hash |
| `contact.read` | 明確列出的 retained、checked contact IDs；enrichment不隱含可讀新渠道 |
| `draft.generate` | exact reviewed sender；指定recipient，或明確准許不指定recipient的內部草稿 |
| `delivery.review` | exact sender／recipient；只屬內部用途權限 |
| `delivery.send` | exact provider/account/contract/sender/recipient，加原有內容approval、budget、runtime、flags、suppression及fence |

owner designation必須明列新動作，原人工authority不會自動擴權。
同purpose沿用最新head；若要保留人工動作，必須明列並重新批准。
sender/contact在申請及批准時均經canonical tenant/project關係驗證。
公司、人物或渠道存在，不構成同意接收推廣的證據。

worker只新增下列 proof 欄位SELECT，仍有FORCE RLS、無新表DML或整表SELECT：

| public表 | buyeros_worker可讀欄位 |
|---|---|
| policy_controller_authorities | id, workspace_id, project_id, approver_user_id, membership_version, version, status, purposes, allowed_actions, valid_from, expires_at, execution_receipt |
| policy_activation_requests | id, workspace_id, project_id, authority_id, authority_version, terms, terms_hash |
| policy_activation_resolutions | id, workspace_id, project_id, request_id, actor_id, outcome, decision_id, terms_hash |

`terms`仍是批准內容（含來源／批准證據reference和hash），沒有provider credential。
loader以`load_only(..., raiseload=True)`避免意外讀取其他欄位。
schema差異在尚未發布的0056；沒有修改已合併0055、建立新migration head或套用正式ACL。

## 實際驗證結果

所有DB client前先驗Docker transport、exact receipt/container/image/loopback port、
fixture DB與Auth issuer；本輪使用cached PG18.6（180006），沒有production URL fallback。
API/worker使用真實runtime角色和RLS。provider transport、identity與資料均為合成fixture。
dispatch正向測試只在測試process內暫設flags及mock selection；正常設定及production
selection維持關閉／未安裝，沒有真實provider或寄信啟用。

| 證據 | 結果 |
|---|---|
| provider contract與原manual contract | 37通過 |
| provider核心API／DB | 270通過、1項測試fixture舊If-Match失敗；已修正並在下列補測通過 |
| 審查補修＋Native policy use/races/HTTP/migration | 41通過 |
| 上述三組按case ID去重、以補測取代同一失敗case | 346個不同API／DB／契約案例通過；原XML不改寫 |
| frozen worker routing與GET-only schedule | 21通過 |
| policy client recovery | 11通過 |
| release／runtime bundle控制 | 183通過 |
| CI registration consumer | 4通過；仍12 jobs |
| TypeScript／受影響UI lint／生成契約及routes／diff whitespace | 通過；124 operations |
| 全API inventory | 2,967已collection及consumer核對；不是全量執行通過 |

有一次fresh只讀source review，兩項Important均重現RED再修正：
CSV export缺少outreach context；usage缺少contact.read context。
修正保留獨立export permissions，加入精確recipient/sender及retention檢查。
補測包含不同recipient不可借用scope、owner失效阻止已建立export取回、
渠道過期不計入contactable且不改已結算金額。

provider核心失敗是新測試重用hardcoded `If-Match: "2"` helper；
正式CAS沒有放寬，測試改用server回傳的當前review version。
原始core失敗XML及補測XML均保留，沒有將失敗報告改成綠燈。

證據目錄：`.superpowers/sdd/2026-10-17-provider-policy-delta/`。
包含RED/GREEN logs、原始JUnit、Docker receipts、`evidence-summary.json`、
final source manifest及`reviewable-native-provider.patch`。
patch相對main，明確包含此前尚未提交的Native相依檔案，不冒稱純本輪增量。

## 實際指令

以下`$e`是本機證據目錄，`$receipt`是該目錄的`owned-target.json`。
runner只接受顯式owned fixture DSN；測試命令從`services/api`執行。
可用public fixture常數`tests.conftest.DB_USER/DB_PASSWORD`及receipt.port建立DSN，
不可讀production env替代。若本輪容器已清理，應用
`tools/create_policy_test_target.py --receipt <new-local-receipt>`重新建立並驗身分，
不能沿用已失效port或覆寫舊receipt。

```powershell
# API核心：本輪原始271案例，保留一項fixture失敗，見補測
.venv/Scripts/python.exe tools/run_policy_activation_tests.py --target-receipt $receipt --suite api --fresh-target -- tests/test_provider_policy_db.py tests/test_provider_delivery_policy_db.py tests/test_contact_registry_scope_db.py tests/test_lookup_quotes_db.py tests/test_contact_confirm_atomicity_db.py tests/test_draft_persistence_db.py tests/test_delivery_admission_db.py tests/test_delivery_budget_db.py tests/test_delivery_submission_db.py tests/test_delivery_post_db.py tests/test_delivery_reconciliation_db.py -q --tb=short --maxfail=3 --junitxml="$e/provider-core-final.xml"

# 最終補測41案例，包括已修正If-Match及審查兩項缺口
.venv/Scripts/python.exe tools/run_policy_activation_tests.py --target-receipt $receipt --suite api --fresh-target -- tests/test_exports_authorization_db.py tests/test_usage_outcomes_db.py tests/test_provider_delivery_policy_db.py tests/test_policy_activation_use_db.py tests/test_policy_activation_races_db.py tests/test_policy_activation_http_db.py tests/test_policy_activation_migration_db.py -q --tb=short --maxfail=3 --junitxml="$e/review-policy-final.xml"

# Worker21案例，使用worker自己的frozen interpreter及獨立owned cluster
.venv/Scripts/python.exe tools/run_policy_activation_tests.py --target-receipt $receipt --suite worker -- tests/test_delivery_routing_db.py tests/test_delivery_schedule.py -q --tb=short --junitxml="$e/worker-final.xml"
```

repo root另執行：

```powershell
services/api/.venv/Scripts/python.exe -m pytest -q services/api/tests/test_provider_policy_contract.py services/api/tests/test_policy_activation_contract.py
node node_modules/vitest/vitest.mjs run --config vitest.policy-activation.config.ts
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js features/live/policy-activation-panel.tsx --max-warnings=0
node scripts/generate-api-types.mjs --check
services/api/.venv/Scripts/python.exe scripts/generate-operation-routes.py --check
services/api/.venv/Scripts/python.exe -m unittest discover -s tests -p test_policy_activation_ci_registration.py -q
services/api/.venv/Scripts/python.exe -m pytest -q tests/test_release_readiness.py tests/test_candidate_promotion.py tests/test_promotion_transport.py tests/test_runtime_bundle_workflow.py tests/test_runtime_bundle.py tests/test_runtime_observation_packet.py tests/test_runtime_observation_workflow.py tests/test_workspace_runtime_observations.py
git diff --check
```

## 驗收限制與下一步

本輪沒有執行全量2,967 API、全量469 worker、Native/browser、遠端CI或公司帳戶UAT；
不以本機去重結果宣稱整branch CI全綠。provider申請／批准API可用合成資料測試，
畫面建立表單仍限manual scope，沒有新增啟用真實provider的UI或預設選擇。

如之後要發布，仍須另行批准commit/push/PR/merge、正式0055/0056及最小grant、
真實authority/用途內容、受保護contracts/簽署、部署與公司帳戶UAT資料範圍。
任何真實enrichment或寄信仍需具體provider/account/contract、成本與收件人／內容
批准；本文件不代表已取得同意、法律依據或真實支出權限。
