# Controlled Policy Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **本案執行方法：Native。** 沿用使用者選擇，由同一執行者按 `superpowers:executing-plans` 逐項實作；本計畫沒有授權dispatch subagents。**今輪只編寫計畫，所有實作步驟尚未開始。**

**Goal:** 讓已指定資料擁有人／delegate以正常Auth批准不可變政策申請，由伺服器原子啟用可撤回的人工Native用途權限，保持付費research、contact enrichment及寄信停用。

**Architecture:** 保留既有client `permitted` 403及policy evaluator，新增authority、request、resolution三個tenant關聯表與受控Native routes。重用membership、FORCE RLS、workspace transaction lock、idempotency、audit及approval invalidation；將批准的action/source/retention約束接到既有Native讀取和提交邊界。

**Tech Stack:** 現有FastAPI／Pydantic 2／SQLAlchemy 2／Alembic／psycopg、React／TypeScript、OpenAPI產生器、pytest及Playwright；沿用lockfiles，不新增服務或依賴。正式PG18.6的本機隔離migration演練與現有CI PG16覆蓋分開記錄。

**Spec:** [使用者已核准的Native設計](<C:/Users/laich/.codex/worktrees/pr21-golden-resources/BuyerOS/.superpowers/sdd/policy-activation-design-20261017/controlled-policy-activation-design.zh-HK.md>)，SHA256 `3afaae7ed67b97e6586042055442ddb9390eb402a10b95889507df452d82bfce`。

**Approval:** 2026-10-17使用者明確「核准這份 Native 受控政策啟用設計，請繼續編寫實作計畫供我審閱」。此為**設計＋計畫編寫**授權，不是產品實作、正式政策內容或發布授權。歷史spec的「待批准」標籤以此最新指示為準；本計畫仍待審閱。

## Global Constraints

- 本輪只寫文件；以下checkbox全部未開始。**計畫批准前不改產品、不啟動fixture或跑會寫入的測試。**
- 本計畫相對路徑以 `C:/Users/laich/.codex/worktrees/pr21-golden-resources/BuyerOS` 為根；執行時另建／重用核准的專用checkout，不覆寫原工作。保留 `codex/native-save-readback-recovery-20261016`、備份、未追蹤內容及兩個checkout的 `.gitignore`；不reset、不force-push。
- source歷史基準：main `51532f19c19dd10ab3aa6c4a5fac87bc039856bb`，tree `122ba57759cdbc51023d3c36350faafeaaed8d1a`；專用checkout HEAD `047db2f24d2d2afd1f4b2c20bda9647648c839e1` 同tree。本輪不重新做正式發布核對；開工時如main／spec變動，先核差異，不能套用舊CI。
- 第一版只對exact workspace/controller/project、一個purpose一份申請；purpose只有 `account_research`、`contact_research`、`draft_preparation`。沒有whole-workspace wildcard grant，沒有owner資料便保持空authority／blocked。
- 不新增policy_admin，不把普通workspace_admin自動當owner；真正獲指定owner可以申請兼批准，沒有新加requester≠approver規則。release獨立reviewer仍是另一個閘門。
- authority、request、resolution append-only；撤回以新restrictive decision／authority revoke版本表達，expiry在server gate即時生效。歷史approved不等於現在permitted，更不等於consent。
- `0056_policy_activation` 是暫名，依賴 `0055_lead_workflow`；不得改0055。執行時先核最新migration head；號碼已佔用就停下審閱新號碼，不能建立第二個head。
- exact ACL：api對policy/audit只SELECT+INSERT；worker對policy只SELECT、audit只SELECT+INSERT。新authority api只SELECT；新request/resolution api只SELECT+INSERT，worker無權。不得為測試加廣權、fixture bypass或production test flag。
- USD10/月只是cap，不是支出授權。新policy suite及UAT configuration的paid、enrichment、delivery保持disabled；真實external transport calls必須0。既有mock provider contract測試的mock次數與真實外呼次數分開。
- 不重做PR25 intent保存／429恢復；不修改 `features/live/lead-workflow/intent-client.mjs` 或 `tests/lead-intents.test.mjs` 的業務行為／斷言。必要policy context plumbing只限本案邊界。
- 所有DB／Auth測試先驗owned-disposable identity再建client/import會啟動stack的module；缺顯式fixture URL或target receipt即abort，不能fallback正式DATABASE_URL。
- 25項P01–P25必測條件沿用設計附件；它們是驗收群組，**不是預設剛好25個pytest cases**。參數化後的實際數量由collection與execution逐一對照。
- commit/push/PR/merge、正式migration/ACL/authority bootstrap、憑證或安全設定、stage/promotion、公司UAT寫入、24/57提交及外發，全部不包含在本機實作範圍。各task只做diff checkpoint；有另行commit授權才建立commit。
- 不再讀取完整Vercel project metadata或env values；安全管理員透過安全UI處理原敏感metadata事件。

## Review Focus

1. **R1：相同內容的Unicode／欄位順序／時區表示。** server canonical terms hash穩定，UI批准server回傳的hash；非空白內容不得被默默改寫。T01測 `test_canonical_terms_are_stable_without_rewriting_evidence`。
2. **R2：官方domain的suffix／userinfo／port／文件ID偽裝。** `allowed.example.test.evil.test`、跨project文件及claim「official」不能通過來源範圍。T06測 `test_source_allowlist_is_exact_and_server_resolved`。
3. **R3：政策有效但source／內容保留期限較短。** 取最嚴deadline，不能重載後延長或重新顯示過期private內容。T06測 `test_shorter_source_deadline_wins_after_reload`。
4. **R4：logout／workspace切換後舊429或成功回應晚到。** 不污染新scope，不丟失原operation locator、不顯示假成功。T08測 `late_policy_response_cannot_update_another_scope`。
5. **R5：獨立read-only receipt查詢嵌在持鎖的父交易內。** 保留現有read-only snapshot邊界，不能自我deadlock，也不能以snapshot批准mutation。T06測 `test_policy_receipt_read_does_not_wait_on_parent_and_cannot_authorize_write`。

---

## 開工／指令約定

以下是**未執行的未來命令**，不是本輪通過結果。`<run>`、`<owned-target-receipt>` 是執行時產生的非秘密fixture識別，不可換成正式目標。

純schema/unit命令（repo中的 `services/api` 目錄）：

```text
uv run --frozen pytest tests/test_policy_activation_contract.py -q
```

DB/API命令統一經T02新增的test-only runner；runner先核receipt／Docker metadata，再以同一process啟動pytest：

```text
# cwd: services/api
uv run --frozen python tools/run_policy_activation_tests.py --target-receipt <owned-target-receipt> --suite api -- tests/test_policy_activation_migration_db.py -q
```

Browser命令只在同一identity gate已通過的process啟動，禁止reuse未知localhost server：

```text
# cwd: services/api
uv run --frozen python tools/run_policy_activation_tests.py --target-receipt <owned-target-receipt> --suite browser
```

`--suite api` consumes pytest args after `--`；`--suite worker`在worker root執行pytest；`--suite browser`只執行新policy config，或用固定allowlist selector執行既有Native config。runner不接受任意shell命令／任意baseURL、不連Neon或讀production env。詳細介面在T02。

全task RED須是預期行為／缺介面失敗，不能把DB未就緒、零collection或skip當RED；GREEN須failure/error/skip=0並含DB canonical readback，不能只看HTTP200。

## 檔案結構與責任

| 單元 | 新增／修改路徑 | 決定 |
|---|---|---|
| Typed契約 | 新 `services/api/buyeros_api/api/policy_activation_schemas.py`；新 `services/api/buyeros_api/services/policy_activation_terms.py` | 前者strict輸入／輸出；後者封閉manual模板、canonical terms／hash及source範圍驗證，純函式、無DB／網絡 |
| Persistence | 新 `services/api/buyeros_api/db/policy_activation.py`；改 `db/models.py`；新 `alembic/versions/0056_policy_activation.py` | 三模型與frozen revision分離，不擴大舊policy.py；完整複合FK、RLS、uniques及精確ACL |
| Authority管理 | 新 `services/api/buyeros_api/services/policy_activation_bootstrap.py`；新 `scripts/policy-authority.py` | reviewed-manifest dry-run／apply／reconcile／revoke；不能直接寫permitted；API沒有自授authority endpoint |
| Native交易 | 新 `services/api/buyeros_api/services/policy_activation_service.py` | submit/lookup/decide/withdraw、CAS、同交易policy/audit/receipt |
| Current gate | 新 `services/api/buyeros_api/services/policy_activation_read.py`；改 `policy_service.py`、既有lead_evidence/review/preparation_service.py；必要lead_intent_service.py `_view` | read helper只依賴models／T01型別，不import交易service，避免循環；current proof／context與version排序，不重寫intent狀態機 |
| HTTP／生成契約 | 改 `api/routes/policy.py`、`api/deps.py`、`docs/buyeros/contracts/openapi.proposed.yaml`；生成 `services/generated/buyeros-api.ts`、`operation-routes.ts` | admin-only新operation IDs，保留舊403；generation不手改 |
| 管理UI | 改 `features/live/policy-settings.tsx`、`locale.ts`；新 `policy-activation-panel.tsx`、`policy-activation-client.ts` | 原restrictive表單保留；新panel只做申請／指定owner決定及effective狀態，client只負責policy locator／重試 |
| Owned測試 | 新 `services/api/tests/policy_activation_fixtures.py`、`tests/policy_activation_target.py`、`tools/run_policy_activation_tests.py`；必要改既有lead及18個raw policy seed fixtures | helper只存在tests/tools；不把fixture authority混入runtime code／真實FIMMICK |
| Browser／CI | 新 `playwright.policy-activation.config.ts`、`vitest.policy-activation.config.ts`、`tests/e2e/policy-activation.spec.ts`；必要改 `tools/serve_e2e_fixture.py`、`.github/workflows/buyeros-ci.yml` | 新seed只給owned fixture；TS client用獨立Vitest config，沿既有frontend/browser-continuity jobs，仍12 jobs，不取代Native19/client6 |

沒有計畫修改共用idempotency.py、audit_service.py或db/session.py；若實作證明必需，先交最小差異，不能順手重構。所有新增檔案名稱在下列介面固定；不另建通用審批引擎。

## Task T01：固定typed terms與manual模板

**Files:** Create `api/policy_activation_schemas.py`、`services/policy_activation_terms.py`、`tests/test_policy_activation_contract.py`（均位於services/api）。

**Interfaces:**

- Produces `PolicyTerms`：workspace/controller/project、purpose、template_version、allowed_data_categories、allowed_sources（exact domains／project document IDs）、allowed_actions、valid_from/expires_at、retention_days、deletion_plan、countries、policy_version、basis_reference/provenance及owner evidence reference/hash。
- Produces `ActivationSubmit`（client_request_id、authority_id/version、expected_policy_id/version、terms、request_deadline）；`ActivationDecision`（approve/reject、terms_hash、expected request/head、reason）；`ActivationWithdrawal`。
- Produces `PolicyUseContext(action: str, project_id: UUID, source_ids: tuple[UUID,...], source_domains: tuple[str,...], data_categories: frozenset[str])`；不是caller可任意傳入就信任的授權物件，由domain service解析canonical資料建立。
- `canonicalize_terms(terms: PolicyTerms) -> tuple[PolicyTerms,str]` 重用 `db.icp.canonical_hash`；`validate_manual_scope(terms: PolicyTerms) -> None`；`match_policy_use(terms: PolicyTerms,use: PolicyUseContext,now: datetime) -> bool`。
- 輸出分開 `ActivationReceipt`（immutable request/resolution/decision IDs、terms hash、original outcome／versions）與 `ActivationView`（receipt＋目前computed request/effective狀態）。不把動態permitted狀態凍結入idempotency response。
- Produces `AuthoritySummary`（id/version、project/purposes、可審批資格與期限，不回designation原文）、`AuthorityPage`及`ActivationPage`；page欄位沿現有policy contract：items/offset/limit/total，limit 1..100、default20。

- [ ] **1—RED tests：** `test_rejects_actor_fields_unknown_purpose_and_unenforceable_scope` 斷言client actor/time/status、非三用途、未知template／未實作更窄限制均拒絕；`test_canonical_terms_are_stable_without_rewriting_evidence`（R1）斷言JSON key次序不影響hash、server UTC序列化一致、Unicode evidence原文保留、terms改一字則hash改變。
- [ ] **2—跑RED：** 使用上方pure unit command；預期新schema／validator缺失或明確assertion失敗，沒有DB connection。
- [ ] **3—最小實作：** 封閉template version設為 `manual-native.v1`；purpose依三用途，action只允許既有Native的 `observation.append`、`lead.review`、`lead.evidence.read`、`preparation.create/revise/request_review/review/read`。模板明列現有strict字段集合，owner須整體批准，任意較窄而無法執行的字段要求回 `UNSUPPORTED_POLICY_SCOPE`。保留每purpose獨立許可；讀寫仍需現行所有purpose，不合併為一張全用途許可。
- [ ] **4—跑GREEN：** 同command，全部通過；額外驗boundary `now == expires_at` 不允許、時區缺失或valid_from≥expires_at拒絕。實際authority及source deadline從DB解析後的上限驗證分別由T05、T06負責，pure terms不捏造這些metadata。
- [ ] **5—Checkpoint：** 留typed輸入／輸出樣例（只合成）、test names與hash；不commit，交付T02–T08可共用的穩定型別。

## Task T02：三表、精確ACL及owned target gate

**Files:** Create `db/policy_activation.py`、`alembic/versions/0056_policy_activation.py`、`tests/test_policy_activation_migration_db.py`、`tests/policy_activation_target.py`、`tools/run_policy_activation_tests.py`；Modify `db/models.py`。

**Interfaces:**

- Consumes T01；produces `PolicyControllerAuthority`、`PolicyActivationRequest`、`PolicyActivationResolution`。
- Authority自然key固定為workspace/project/approver，append version＋supersedes；request對workspace/requester/client_request_id唯一；resolution對workspace/request_id唯一，approved才有decision_id，同decision至多一個approval。
- `assert_owned_target(receipt: dict,container_metadata: dict,env_endpoints: dict) -> OwnedTarget` 只做純比對；`run_owned_suite(target: OwnedTarget,suite: Literal["api","worker","browser"],args: list[str]) -> int` 只執行固定命令。receipt記container/image digest、run label、host/port/db、Auth issuer、owned child DB清單；不存DSN或token。

- [ ] **1—RED tests：** `test_target_gate_precedes_any_database_client` 用spy斷言receipt缺失／port或container／Auth不符時沒有connect；`test_0055_upgrade_adds_three_tables_with_forced_rls_and_exact_privileges` 驗三表／FK／uniques及權限；`test_cross_tenant_links_and_runtime_rewrites_are_denied`、`test_populated_downgrade_refuses_to_destroy_policy_history`。
- [ ] **2—跑RED：** 先pure target validator；再在明確獲准的owned PG18.6建立run-labelled container，驗metadata後才用runner跑migration檔。不存在owned target則報BLOCKED，不改用正式或skip冒充。
- [ ] **3—最小實作：** Frozen migration依0055，初始authority/request/resolution均空，無business backfill。new authority api SELECT；request/resolution api SELECT+INSERT；worker無new-table權。對public.policy_decisions/public.audit_events撤api+worker UPDATE/DELETE，再撤worker policy INSERT；檢查effective privileges，保留正常audit INSERT。不改public.alembic_version grant、不改0055／舊migration。
- [ ] **4—跑GREEN：** 完整0054→0055→新revision、FORCE RLS／composite FK／ACL、唯一鍵競態、transaction中途失敗rollback；empty-only downgrade先實測，有任何新history則拒絕。保留source／DDL／role／row counts證據。PG16 CI相容與PG18.6結果分開。
- [ ] **5—Checkpoint：** schema/ACL清單及migration fingerprint；owned cleanup僅本run精確container/child DB。既有備份不清理，無正式grant／migration執行。

## Task T03：受控authority bootstrap與合法合成fixture

**Files:** Create `services/policy_activation_bootstrap.py`、`scripts/policy-authority.py`（repo root）、`tests/policy_activation_fixtures.py`、`tests/test_policy_activation_bootstrap_db.py`；必要修改既有raw-permit fixture setup。

**Interfaces:**

- Consumes T01/T02；produces `AuthorityManifest`（exact target fingerprint、workspace/project/approver、membership版本、purposes、期限、owner designation ref/hash、expected prior authority、authorization reference）。
- `inspect_authority_manifest(session,manifest: AuthorityManifest,now: datetime) -> AuthorityPlan`（dry-run只SELECT）；`apply_authority_manifest(session,manifest,execution: VerifiedBootstrapExecution,now) -> AuthorityReceipt`；`reconcile_authority_manifest(session,manifest_hash: str) -> AuthorityReceipt|None`；`revoke_authority(session,authority_id: UUID,expected_version: int,reason: str,execution: VerifiedBootstrapExecution,now) -> AuthorityReceipt`。
- `VerifiedBootstrapExecution`只由CLI已核實管理身分／target及已獲准manifest構成，HTTP body不能建立；字串approved_by不算批准。CLI default dry-run，apply/revoke必須明確模式，且工具沒有permit-write功能。
- Test helper `provision_fixture_authority(owner,scope,approver,purposes,now)` 只在tests package，檢查owned receipt；service及真實API使用同一套authority驗證。

- [ ] **1—RED tests：** `test_api_role_cannot_self_designate_authority`、`test_dry_run_has_no_mutation`、`test_wrong_target_or_unapproved_manifest_never_applies`、`test_same_manifest_reconciles_without_duplicate_authority_or_audit`、`test_revoke_keeps_history_and_invalidates_dependent_approval`。assert真人FIMMICK UUID不在fixture。
- [ ] **2—跑RED：** runner `--suite api -- tests/test_policy_activation_bootstrap_db.py -q`，全程owned fake designation evidence、真實external calls=0。
- [ ] **3—最小實作：** 沿staff onboarding的validated-manifest／receipt模式，不重用其membership寫權或建立新admin。authority apply/revoke先取既有 `membership_admin.lock_membership_admin`，核target membership版本後取policy workspace lock，同交易寫audit（service identity/hash，不記原文）。Apply需active指定admin；revoke不能因目標帳戶已停用而無法撤權，只核既有authority版本與受控執行授權。缺approval或unknown outcome先reconcile，不能新manifest hash盲重試。
- [ ] **4—跑GREEN及compatibility gate：** 更新Native shared seed為有authority／批准證據的合成前置。對18個raw policy seed檔逐一分類，保留原角色／用途／provider contract斷言；不得把provider-positive案例改成manual permission、注入production fixture flag或改成mock gate來假裝原整合通過。若manual-only規格無法表達某既有positive fixture的合法權限，先留下具體RED與最小設計差異，**暫停該依賴，不擅自新增provider授權模板**。
- [ ] **5—Checkpoint：** 提交fixture遷移清單及每項原斷言是否保留；沒有兼容證據不得把T06/T09標綠。正式authority仍空，沒有實際owner被指派。

## Task T04：申請／歷史lookup與重複提交

**Files:** Create `services/policy_activation_service.py`、`tests/test_policy_activation_requests_db.py`。

**Interfaces:**

- Consumes T01–T03。`PolicyActor(workspace_id: UUID,user_id: UUID,roles: frozenset[str],membership_version: int)`由server current membership建立，不能從request JSON讀取。`refresh_actor_membership(session,actor: PolicyActor) -> PolicyActor` 在mutation取得membership admin lock後，以server已驗明的user/workspace重新讀active/roles/version；不能信任進鎖前snapshot。
- `submit_activation(session,*,actor: PolicyActor,data: ActivationSubmit,key: str,now: datetime) -> ActivationView`。
- `get_activation(session,*,actor: PolicyActor,request_id: UUID,now: datetime) -> ActivationView`。
- `find_activation(session,*,actor: PolicyActor,project_id: UUID,client_request_id: UUID,now: datetime) -> ActivationView|None`；`list_activations(session,*,actor,project_id,offset,limit,now) -> ActivationPage`。

- [ ] **1—RED tests：** `test_submit_never_creates_permitted_policy`、`test_same_key_replays_and_changed_body_conflicts`、`test_new_key_with_same_client_reference_does_not_duplicate_request`、`test_unknown_first_response_is_resolved_by_client_reference`、`test_foreign_request_and_source_lookup_does_not_enumerate`。
- [ ] **2—跑RED：** runner `--suite api -- tests/test_policy_activation_requests_db.py -q`；預期缺service／行為assertion失敗。
- [ ] **3—最小實作：** submit先取membership admin lock並刷新current actor；驗project/controller/source ownership及authority snapshot，再按現有begin/complete_idempotency及唯一client reference返回原resource。Canonical terms immutable，同reference不同body409；submitted不改任何effective policy。GET只讀、computed stale/expired、offset/limit bounded；不因GET搶admin寫鎖，owner evidence只回reference/digest，不回原文或秘密。
- [ ] **4—跑GREEN：** 每個POST結果對canonical GET和row/audit counts，模擬server保存但回應遺失；不以新key作「恢復」。
- [ ] **5—Checkpoint：** 1 request的完整synthetic readback與original locator；無permit／cost／provider/outreach副作用。

## Task T05：批准／拒絕／撤回的原子交易

**Files:** Modify `services/policy_activation_service.py`、`services/policy_service.py`、`api/routes/policy.py` 的舊restrictive head排序；Create `tests/test_policy_activation_decisions_db.py`、`tests/test_policy_activation_races_db.py`。

**Interfaces:**

- Consumes request／actor／receipt型別及T03 authority；produces `decide_activation(session,*,actor: PolicyActor,request_id: UUID,data: ActivationDecision,key: str,now: datetime) -> ActivationView`、`withdraw_activation(session,*,actor,request_id,data: ActivationWithdrawal,key,now) -> ActivationView`。
- `policy_service.latest_policy_head(session,*,workspace_id,project_id,purpose) -> PolicyDecision|None`：version主序，歷史version相同時created_at/id僅作明確tie-break，不回填假version。
- `build_activation_view(session,request,now) -> ActivationView`：immutable receipt與current effective status分開；approval replay不延長validity。

- [ ] **1—RED tests：** `test_designated_owner_approves_one_exact_request`；`test_real_owner_can_request_and_approve_without_fabricated_second_person`；`test_nondesignated_admin_cannot_approve`；`test_approve_reject_withdraw_race_has_one_resolution`；`test_membership_revocation_serializes_before_approval_commit`；`test_audit_or_invalidation_failure_rolls_back_everything`；`test_earlier_transaction_timestamp_cannot_hide_later_blocked_version`。
- [ ] **2—跑RED：** runner依序跑decisions/races兩檔；用barrier與兩條owned連線控制競態，不靠增加sleep/timeout令結果碰巧通過。
- [ ] **3—最小實作：** 先取既有 `membership_admin.lock_membership_admin`，刷新actor/authority membership，再begin_idempotency→policy_workspace_lock→request／head；與現有membership PATCH的admin鎖相容，不另造鎖系統，不讓舊roles snapshot在撤權後批准。重核指定authority、exact terms hash、expected head/version及期限。依FK順序插入PolicyDecision與唯一resolution，invalidate_approvals_for_subject、append_audit、complete_idempotency同交易flush/commit。pending withdrawal只容原requester active admin，不製造blocked decision；生效後撤權沿新blocked／authority revoke，不覆寫approved history。
- [ ] **4—跑GREEN：** 第二key同request只回canonical terminal或409/412；audit INSERT故障不留permit、resolution、completed idempotency或假成功；commit回應遺失時以原reference查明。舊 `test_unapproved_permitted_policy_is_denied_even_for_workspace_admin` 仍403、零row。
- [ ] **5—Checkpoint：** 保留並發timelines、version鏈及歷史／effective差異；不要自行提升requester或審批role。

## Task T06：current policy-use與Native內容邊界

**Files:** Create `services/policy_activation_read.py`；Modify `services/policy_service.py`、`lead_evidence_service.py`、`lead_review_service.py`、`lead_preparation_service.py`；只在policy-read context需要時改 `lead_intent_service.py` `_view`；Create `tests/test_policy_activation_use_db.py`。既有readonly receipt相關測試保留。

**Interfaces:**

- Consumes T01/T05。現有 `evaluate_current_policy(session,subject,purpose,now,*,use_context: PolicyUseContext|None=None) -> dict` 及readonly版本加keyword-only context，保留原status/reason contract；對受控啟用用途的permitted核對resolution／authority／terms及context。缺proof／context不默認grant。
- `policy_activation_read.resolve_approved_policy_terms(session,decision: PolicyDecision,now: datetime) -> PolicyTerms|None` 僅SELECT；該module不import policy_service／activation_service。`lead_evidence_service.authorize_native_policy_use(session,scope,*,action: str,source_ids: tuple[UUID,...],now) -> PolicyUseReceipt` 解析actual tenant/source/domain與欄位模板後調共用gate。
- `PolicyUseReceipt`綁decision IDs、terms hashes、authority versions、最嚴expiry；Native review/preparation context hash帶這些版本，不能以舊review跨政策繼續。

- [ ] **1—RED tests：** `test_manual_permit_cannot_admit_provider_enrichment_formal_draft_or_send`、`test_expired_or_revoked_authority_blocks_next_read_and_write`、R2 `test_source_allowlist_is_exact_and_server_resolved`、R3 `test_shorter_source_deadline_wins_after_reload`、R5 `test_policy_receipt_read_does_not_wait_on_parent_and_cannot_authorize_write`。
- [ ] **2—跑RED：** runner `--suite api -- tests/test_policy_activation_use_db.py tests/test_receipt_read_current_scope_db.py tests/test_provider_receipt_retention_db.py -q`。
- [ ] **3—最小實作：** 版本主序、most restrictive/suppression及expiry保留；exact HTTPS domain／同project source IDs由server解析；expiry比較用timezone-aware now，取authority/policy/source retention最嚴期限。Native讀／commit都檢查，不能只在建立intent時驗一次。readonly gate維持實際READ ONLY要求，不搶父transaction advisory lock。
- [ ] **4—跑GREEN與caller coverage：** graph inbound已定位draft_service、buyer_read、providers/live_search、execution/handlers/draft_generate及Native callers；把actual call sites記入manifest並測manual permit在非Native路徑被拒。只做必要context plumbing；若需超出檔案清單的大幅provider改動，連同T03 fixture compatibility RED先交最小差異，不暗中擴scope。policy操作不得release unknown cost holds／啟動scheduler。
- [ ] **5—Checkpoint：** evidence→person/channel review→preparation保存／取回的synthetic鏈與context hashes；既有Native保存／4296client測試斷言不變。

## Task T07：HTTP權限、OpenAPI及generated routes

**Files:** Modify `api/routes/policy.py`、`api/deps.py`、`docs/buyeros/contracts/openapi.proposed.yaml`；Regenerate `services/generated/buyeros-api.ts`、`operation-routes.ts`；Create `tests/test_policy_activation_http_db.py`。

**Interfaces:** 新operation IDs固定為：

- `listPolicyControllerAuthorities`：GET /policy-controller-authorities?project_id=...
- `submitPolicyActivationRequest`：POST /policy-activation-requests
- `listPolicyActivationRequests`／`getPolicyActivationRequest`：GET list／{id}，list支援project_id及client_request_id lookup
- `decidePolicyActivationRequest`：POST /{id}/decisions
- `withdrawPolicyActivationRequest`：POST /{id}/withdrawals

以上均在 `/v1/workspaces/{workspace_id}`，`x-permitted-roles`只有workspace_admin；controller／subject為server-resolved，不新增HTTP authority寫入。表單及approve payload不接受actor/time/status=permitted。

- [ ] **1—RED tests：** `test_http_roles_and_foreign_scope_are_denied_before_write`、`test_http_actor_is_derived_from_current_membership`、`test_contract_rejects_missing_fields_and_exposes_canonical_locator`、`test_old_permitted_route_stays_closed`；各case驗response schema及DB row counts。
- [ ] **2—跑RED：** runner `--suite api -- tests/test_policy_activation_http_db.py tests/test_policy_lifecycle_db.py -q`。
- [ ] **3—最小實作：** routes薄封裝T04–T06；reuse tenant_scoped/load_membership/rate limits/envelope。回403/404／409/412／422清楚對應權限、unknown/stale、validation；不把audit失敗轉成200。current存取先驗才可replay，沒有scope權的人不可用locator讀history。
- [ ] **4—跑GREEN及生成檢查：**

```text
# repo root
node scripts/generate-api-types.mjs --write
# services/api
uv run --frozen python ../../scripts/generate-operation-routes.py
# checks
node scripts/generate-api-types.mjs --check
uv run --frozen python ../../scripts/generate-operation-routes.py --check
```

第一／第三命令cwd是repo；第二／第四cwd是services/api。生成後跑HTTP套件、`node --test tests/api-types-generation.test.mjs`及`pnpm exec tsc --noEmit`；不得手改generated內容。

- [ ] **5—Checkpoint：** 保存OpenAPI diff、operation角色表、generated diff及exact request/response synthetic samples；全部operation受現有server角色檢查。

## Task T08：管理設定UI、policy recovery及browser/CI接入

**Files:** Create `features/live/policy-activation-panel.tsx`、`policy-activation-client.ts`、`playwright.policy-activation.config.ts`、`vitest.policy-activation.config.ts`、`tests/e2e/policy-activation.spec.ts`、`tests/policy-activation-client.test.ts`；Modify `features/live/policy-settings.tsx`、`locale.ts`；必要新增owned seed到 `services/api/tools/serve_e2e_fixture.py`；Modify `.github/workflows/buyeros-ci.yml`。

**Interfaces:**

- `PolicyActivationPanel({roles,t}: existing policy-settings props)`只掛入現有管理設定；保留restrictive表單。
- `createPolicyActivationClient(transport: PolicyTransport)` 回傳 `submitPolicyActivation(scope,data)`、`decidePolicyActivation(scope,requestId,data)`、`withdrawPolicyActivation(scope,requestId,data)`、`recoverPolicyActivation(scope,locator)`；transport由panel以T07 generated operation client注入，pure client測試不用app initializer或真實網絡。`PolicyActivationLocator`只含actor/workspace/project、client_request_id、original operation key、request_id（若已知）、terms_hash；不存token、owner證據原文或人物內容。
- `PolicyClientScope`固定actor_id/workspace_id/project_id及`isCurrent(): boolean`（沿captured session generation）。`PolicyTransport`提供typed async `submit(scope,data,key): Promise<ActivationView>`、`decide(scope,id,data,key): Promise<ActivationView>`、`withdraw(scope,id,data,key): Promise<ActivationView>`、`get(scope,id): Promise<ActivationView>`、`find(scope,client_request_id): Promise<ActivationView|null>`；data型別對應T01/T07生成契約。Panel的authority／history list直接用generated GET operations，不讓pure client建立Auth或保存token。
- panel從server authority摘要選人；approve顯示server完整canonical terms＋hash及scope，另按一次明確批准；沒有authority就blocked，不提供「設為permitted」checkbox。

- [ ] **1—RED tests：** browser `admin_submits_and_designated_owner_decides_exact_terms`、`same_owner_can_confirm_in_two_audited_actions`、`requester_withdrawal_does_not_revoke_another_active_policy`、`approved_history_and_expired_policy_are_not_confused`、`duplicate_click_and_unknown_response_recover_one_resource`、R4 `late_policy_response_cannot_update_another_scope`（含同帳戶重新登入generation已變）、`relogin_reads_same_request_and_current_effective_state`、`viewer_and_foreign_workspace_cannot_activate`。
- [ ] **2—跑RED：** pure TS client用 `pnpm exec vitest run --config vitest.policy-activation.config.ts`；獨立config只include新client test、environment=node、passWithNoTests=false，不載入Cloudflare或app Vite config。Browser再透過owned runner；新config沿 `playwright.policy.config.ts` fixture方式，但 `reuseExistingServer=false`、先驗target receipt、明確paid/delivery/Cloudflare execution false。不得因未知localhost已在listen就接管。
- [ ] **3—最小實作：** policy client復用現有ActionIntent/captureWriteContext模式但有自己的locator，保存失敗保留form input；未知先GET原reference；ack後history429不另造grant。reload/relogin先從server取canonical結果；若原body未存且不能查明，不顯示成功或自動重送。t()字串沿既有locale規則，避免重複key。
- [ ] **4—跑GREEN：** browser discovery與execution逐一對照；新policy browser獨立report，不塞入Native19冒充同一套。CI加步驟至既有browser-continuity/frontend/api jobs，保持12項required jobs。跑`pnpm exec tsc --noEmit`、lint、new client Vitest及JUnit；原lead client6仍用Node，禁止降低原Native19、lead client6、release183 inventory。
- [ ] **5—Checkpoint：** UI/API/DB同ID／hash／版本、跨scope失敗及relogin讀回證據；真實normal company Auth未測，不能標公司UAT完成。

## Task T09：完整回歸、migration相容性及可審閱交付

**Files:** Modify CI的exact API/worker inventory（僅按實際新增case更新）、新增 `tests/test_policy_activation_ci_registration.py`（repo root）；按需要更新 `docs/buyeros/05_TEST_SECURITY_AND_RELEASE.md`、retention runbook及原發布包G6差異附件。沒有部署或正式bootstrap命令執行。

**Interfaces:** Produces `policy-activation-verification.json`：candidate source/dirty fingerprints、target receipts、case IDs與XML hashes、mock vs real calls、cleanup、migration/ACL before-after、known legacy incompatibility／NOT RUN，以及新release依賴。不產生假owner approval或正式runtime acceptance receipt。

- [ ] **1—RED registration tests：** `test_policy_cases_are_discovered_and_executed_without_replacing_native_baselines` 驗new test modules與CI step必須存在、discovery不可空／重複；`test_legacy_runtime_is_not_accepted_as_compatible_after_scoped_grants` 驗missing/incompatible rollback證據拒絕放行。不得把所有舊source一概宣稱不相容或一概相容。
- [ ] **2—跑RED：** `python -m unittest discover -s tests -p test_policy_activation_ci_registration.py -v`；registry缺失應明確失敗。舊runtime實際兼容fixture只在owned DB運行、network全mock。
- [ ] **3—最小接入：** 三表／ACL變動同步schema/compatibility fixtures與release材料，但**不配置正式contract values**。所有新code的0056 head依賴逐項分類，不能全域把0055字串換成0056或放寬unknown-future-head拒絕。舊permitted seed兼容、worker audit INSERT及retention依賴必須有實際證據。
- [ ] **4—跑GREEN／完整驗證：** identity gate後依CI實際命令跑full API／worker `pytest tests --collect-only`、execution及JUnit join；新case inventory取真實collection，不硬套舊2852/469或手動抬數。原測試身份集合必須保留，任何rename附mapping。保留Native19、lead client6及release183完整結果；另跑新policy browser與pure/client套件。TypeScript、lint及build用fixture-only config，不 `vercel pull`、不deploy、不讀production env。資源不足列BLOCKED，不skip、放寬assertion或增加timeout掩蓋。
- [ ] **5—Checkpoint／交付：** fresh reviewable diff、源碼SHA／所有dirty差異、實際測試命令與結果、精確cleanup及未完成項目。停止於本機成果；commit/push/PR和exact-commit CI要另批，不能在未commit狀態宣稱「新commit CI12/12」。

### T09完整命令基準（未執行）

```text
# services/api，已核實owned target
uv run --frozen python tools/run_policy_activation_tests.py --target-receipt <owned-target-receipt> --suite api -- tests --collect-only -q
uv run --frozen python tools/run_policy_activation_tests.py --target-receipt <owned-target-receipt> --suite api -- tests -q --junitxml=artifacts/policy-activation/<run>/api.xml
uv run --frozen python tools/run_policy_activation_tests.py --target-receipt <owned-target-receipt> --suite worker -- tests -q --junitxml=artifacts/policy-activation/<run>/worker.xml
# repo，pure/client checks
node --test tests/lead-intents.test.mjs
pnpm exec vitest run --config vitest.policy-activation.config.ts
pnpm exec tsc --noEmit
pnpm lint
pnpm build
```

以上full suite必須保留執行時discovery到execution identity join，不只看總數。release183及Native19沿 `.github/workflows/buyeros-ci.yml` 原有完整命令執行，不摘取子集當full PASS。新增tests後API／worker數量可增加；此計畫不預告新的測試總數或通過結果。

## P01–P25完成條件對照

| 設計案例 | 實作／驗收任務 |
|---|---|
| P01 合法批准 | T03 authority＋T05 decisions＋T07 HTTP |
| P02 未授權角色 | T03 authority限制、T07 current membership HTTP、T08 UI負面 |
| P03 同一真正owner兩步確認 | T05 server、T08 UI |
| P04 跨workspace/project/source | T02 RLS/FK、T04/T06 lookup／source、T07 HTTP |
| P05 必要欄／unsupported scope | T01 strict契約、T07 HTTP |
| P06 用途/action/source及外部拒絕 | T01模板、T06 current use、T09 provider/refusal回歸 |
| P07 future／expired policy/authority | T01邊界、T05批准時、T06每次使用 |
| P08 pending撤回／拒絕 | T05 unique resolution、T08顯示 |
| P09 已生效撤回／authority revoke | T03 revoke、T06即時拒絕＋舊history |
| P10 同key replay／body衝突 | T04/T05 |
| P11 跨key雙擊／同client reference | T04/T05、T08 |
| P12 approve/reject/withdraw並發 | T05 races |
| P13 stale policy/authority/membership | T05 CAS、T07 roles |
| P14 older transaction timestamp | T05 version排序；不假稱現況已重現FAIL |
| P15 restricted operation vs revoke | T05/T06 workspace lock |
| P16 audit／invalidation故障rollback | T05，T07不顯假成功 |
| P17 unknown response／429 | T04 lookup、T05 receipt、T08 client |
| P18 self-designation／wrong target／manifest | T02 identity gate、T03 bootstrap |
| P19 evidence／source context變更 | T06，T08 stale顯示 |
| P20 append-only ACL及正常INSERT | T02/T03、T09 worker回歸 |
| P21 歷史approved與effective不同 | T01 view、T05 replay、T08 UI |
| P22 reload/relogin／workspace切換 | T08 |
| P23 migration／populated downgrade refusal | T02 |
| P24 舊runtime安全／rollback | T09 owned兼容／refusal證據；**正式舊endpoint處置仍BLOCKED，需另批驗收** |
| P25 完整政策／Native／財務回歸 | T09；不將本機結果當CI或公司UAT |

## 明確停止／恢復規則

- T03合法fixture或T06 current caller context無法維持原用途覆蓋：保留RED／原斷言，提交最小設計差異；不加provider模板／test bypass去求綠燈。
- DB/API mutation結果未知：保留原key／manifest／client_request_id，先canonical lookup；不放新key、不release holds、不把timeout當未保存。
- owned cleanup僅本run manifest的精確IDs；失敗保留證據、停止後續清理，不刪別人container／資料。
- audit/ACL不符：保持功能blocked，不能restore廣UPDATE/DELETE當作預設修復。正常worker真的需要舊權限時先交根因。
- 不相容舊runtime：標記該artifact不能作rollback，不「修正」receipt令其compatible。正式old endpoint保護／退役由管理員另批；alias切換不等於舊URL失效。

## 本機完成後仍需分開批准

1. source發布：commit/push/PR／merge及新SHA完整12 CI；保留原分支。
2. 正式DB：fresh pre-migration restore point及隔離恢復演練，再批准0055、最小version_num SELECT，以及新revision／ACL。Neon6小時窗口是前次核實值；執行前重新查，不能依賴舊或過期備份。
3. 正式恢復：有authority／request／policy及其他tenant新資料後，populated downgrade拒絕；forward fix／compatible service或另批restore與post-backup資料損失評估，不能保證無損。
4. release：獨立reviewer、protected credentials/contracts、signed runtime bundle、實際artifact/runtime/schema/DB binding、舊endpoint安全及promotion，仍各有批准。
5. owner內容及啟用：指定真實owner/delegate、project、sources/data/actions、basis/countries、期限／保留刪除，批准exact authority manifest及policy terms；技術測試不代替這些決定。
6. 公司UAT：批准公司正常Auth及synthetic project／fault injection／cleanup範圍後才驗收；24/57來源提交、任何收件人／內容及外發繼續另批。

## 計畫審閱與下一步

本計畫為待審閱文件，採Native執行方法。確認計畫後的第一個執行步驟是隔離checkout／source與test target identity gate；不是直接啟用FIMMICK政策。
所有task checkpoint沒有預設commit授權。沒有owner資料可先用合成fixture完成技術驗證，正式authority保持空。若計畫須修改，只改本地文件，不能因設計已核准而跳過計畫審閱。
