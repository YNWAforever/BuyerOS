# Guided sales — final-candidate local verification

**Live acceptance BLOCKED; phase incomplete.** Local implementation and review follow-up are complete. Independent scoped review accepted I1–I6/M1; the controller corrected its two additional CI findings with 45 passing runner/resource checks. Those final CI corrections have controller verification, not another independent review. See `.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/controller-completion.md` and `controller-candidate-final.json` for final identity and review limits. No provider activation, production migration, flag change, deployment or Git mutation is authorized by this document. Historical evidence below remains tied to its original candidate.

Candidate identity includes uncommitted path/content SHA-256 hashes, not just baseline HEAD `da49de0f70077db14c15219338133b59fcecd822`. Each fixture case has PASS/FAIL/BLOCKED/NOT_RUN, classification and candidate hash in `cases.json`. The final-fix candidate and lineage are in `.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/final-fix-evidence/candidate-final.json` and `final-cases.json`. Task15/fix1 manifests are inherited historical evidence, not fresh runs. Use the final report's lineage for affected reruns; do not sum overlapping runs or treat collected/skipped cases as passes.

## All 17 actual producer paths

**INHERITED PASS — prior owned synthetic producer/save/readback evidence for all 17 rows.** Fix1 replaces the invalid snapshot15 prospect-composition association with the actual passing `composition-final` owned run after repairing its direct fixture caller. No broad suite was rerun. The final receipt lineage contains 780 unique passing Python cases, with no unresolved local failures; this is not one 780-case run. Contacts additionally ran explicit en/zh-HK producer cases. Live acceptance remains BLOCKED.

The following are executable API/owned-PostgreSQL save/readback assertions, not the browser's 17 intake-only checks. Canonical readback enforces current provenance, source authority and revision. Fixture proofs do not establish live model or provider quality. Final pass status is the referenced case's latest receipt, with unresolved failures stated in the report.

| Skill | Saved output | Actual producer/persistence evidence (API tests) |
|---|---|---|
| sales-prospect | research_report | `test_sales_composition_db::test_three_real_prospect_children_are_saved_and_recursively_revoked`; fix1 `composition-final/pytest.xml` freshly verifies actual enrichment/competitive/outreach children and recursive revocation; missing-child partial state remains inherited from the drafting matrix |
| sales-research | research_report | `test_sales_drafting_db::test_material_draft_edit_invalidates_approval` matrix; actual worker completion/reconciliation/expiry in `test_sales_native_lifecycle_db` |
| sales-quick | research_report | same drafting matrix en/zh-HK plus bounded alias tests in `test_sales_research` |
| sales-qualify | qualification_assessment | drafting matrix en/zh-HK; actual native picker/preparation in owned browser; advisory unknowns retained |
| sales-contacts | enrichment_proposal | `test_xverum_enrichment_db::test_native_save_canonical_output_and_exact_retry`; selected identity/fields, native revision and canonical revision 2, no implicit human review |
| sales-outreach | outreach_preparation | drafting matrix en/zh-HK; actual eligible native draft, grounding review/approval then material-edit invalidation |
| sales-followup | followup_preparation | drafting matrix en/zh-HK plus `test_sales_composition_db::test_positive_formal_followup_current_parent_exact_content_and_material_edit`; zero delivery |
| sales-prep | meeting_brief | `test_sales_reporting_db::test_remaining_documents_and_pipeline_saved` en/zh-HK, exact version/history |
| sales-proposal | sales_proposal | `test_sales_reporting_db::test_proposal_competitive_child_and_report_export` en/zh-HK, verified commercial/case evidence; missing proof stays Needs input |
| sales-objections | objection_playbook | remaining-documents matrix en/zh-HK, grounded proof and unknowns |
| sales-icp | profile_proposal | drafting matrix en/zh-HK; separate native profile approval |
| sales-competitors | competitive_document | proposal/competitive test en/zh-HK, exact selected child revision and matching native basis |
| sales-report | pipeline_report | remaining-documents/report-export tests en/zh-HK; actual native as-of/filter read, unavailable metrics null |
| sales-report-pdf | report_export | proposal/report-export test en/zh-HK plus `test_pdf_exports_the_selected_revision`; native authorized exact-revision PDF, bundled CJK font, current download permission |
| first-project | project_setup | drafting matrix en/zh-HK and `test_configured_setup_and_current_invalidation`; native setup authority |
| understand-documents | document_understanding | `test_sales_reporting_db::test_native_upload_understanding_and_image_unknown` en/zh-HK; real upload/extraction/partial status, canonical history and deletion |
| review-buyers | buyer_review | drafting matrix en/zh-HK; saved proposal, separate native shortlist review |

## Spec requirement evidence map

| Requirement | Owned/pure/browser evidence and boundary |
|---|---|
| typed request/card equivalence and missing input | `sales-typed-aliases.test.mjs` all17 en/zh-HK; browser intake; `test_sales_tasks_api`, `test_sales_context` |
| complete persisted catalogue or honest state | producer matrix above; current task/output history and state assertions |
| native reopen/reload/private audience | owned `test_sales_ui_access_db` sources/retry/capability phases; sales output ACL and native links tests; synthetic full-shell history separately |
| cross-tenant/project/member/share/worker authority | `test_sales_tasks_db`, `test_sales_outputs_db`, `test_sales_privacy_db`, Xverum boundaries, current-role readiness |
| stale writes/material approval invalidation | enrichment stale-apply tests, native draft edit/approval, export policy tests |
| duplicate/reconnect/restart | execution concurrency/outbox tests; owned uncertain-start replay; native lifecycle worker recovery; unknown dispatch holds |
| ambiguous identity/employer/null/freshness | Xverum enrichment/boundary tests; explicit candidate/field review browser |
| bounded credits/currency/reservations/quotes | Xverum quote/credit/dispatch tests and actual registered accounting owner; no inferred token bill |
| revoked OAuth/schema drift/outages/partial | synthetic connection/transport tests; live SaaS lifecycle remains BLOCKED |
| deletion/retention/export denial | Task14 finalfix paging fence, deadline purge, API/worker TEMP-shadow protection; native document/source/export regressions |
| factual outreach/commercial evidence | drafting/model/document schema and producer tests; no sending/scheduling |
| accessibility/locales/history/native preservation | browser 390/768/1440, keyboard, CSS and real Chromium 200% zoom, injection; full-shell en/zh-HK; owned native recovery |
| fixture/live separation | every case receipt classifies synthetic scope; live prerequisites below remain independent |
| migration and rollback | 0059→0065 empty roundtrip, populated transactional refusal, FORCE RLS/grants/readiness; server-off/workspace-off authorized recovery |
| font/artifact delivery | rebuilt wheel SHA/font/license/source hashes, current downloaded PDF and extracted zh-HK text; rendering evidence in Task15 |
| telemetry | identifiers/status/counts/durations only in receipts; unmeasured product rates/cost/latency null; no improvement threshold invented |

## Live gate

Missing verified SaaS OAuth ownership/refresh/revocation, durable multiprocess secret storage, reviewed model registration, exact policy/tariff, approved prospect/recipient/tool scope and maximum credits/currency are **BLOCKED**. See `runbooks/guided-sales-release.md` for the required receipt and bounded journey. Default registrations stay unselected. Completed local review and controller follow-up do not establish release readiness.

---

## Historical baseline (Task1; superseded environment/schema status)

# Guided sales acceptance — Task 1 baseline

Date: 2026-11-05 (Asia/Singapore). **Baseline recorded; integration acceptance BLOCKED.**
This is preservation evidence, not implementation or release acceptance for Tasks 2–15.
No product code, schema, provider registration or default flag was changed.

## Revision and environment

| Evidence | Observed value / scope |
| --- | --- |
| Checkout | `C:/Users/laich/.codex/worktrees/guided-sales-skills-xverum/BuyerOS` |
| Branch | `codex/guided-sales-skills-xverum` |
| HEAD and remote main | `da49de0f70077db14c15219338133b59fcecd822`; fresh `git ls-remote origin refs/heads/main` matched |
| Remote | `https://github.com/YNWAforever/BuyerOS.git` |
| Graph | Existing `BuyerOS_Sales`; search_graph first, then get_code_snippet; no checkout/index recreation |
| Initial status | No tracked changes; three retained untracked approved design/plan files in `docs/superpowers/` |
| Runtime | Windows; Node 26.13.0; uv 0.11.27; owned API venv CPython 3.12.13 |
| Toolchain difference | CI documents Node 24 and pnpm 11.25.0; pnpm/Corepack not resolved by Get-Command; system Python 3.14.6 was not used for pytest |
| Dependencies | `uv sync --project services/api --frozen --python 3.12` succeeded; API-only setup, lockfiles retained |
| Resources | Controller observed 5.55 GiB free RAM; this session observed 4.43 GiB. Docker Linux engine pipe unavailable |
| Environment identity | Local synthetic non-DB tests only; no database, provider account, live model or OAuth grant used |
| Permissions | Restricted Git checks failed; elevated checks succeeded. Managed-access limitation, not metadata corruption |

Read root `AGENTS.md`, `ARCHITECTURE.md`, `docs/DEVELOPMENT.md`,
`docs/buyeros/CONVERSATION_THREADS_STAGE3.md`,
`docs/buyeros/CONVERSATION_CONNECTIONS_STAGE4.md`, the November approved design and
October preservation map, and Task 1 brief/constraints/progress rulings.
Controller-owned scratch/upstream/review tooling and `progress.md` were not modified.

## Ownership and preservation

Paths below are relative to `services/api/buyeros_api/` unless explicitly repository-root paths.
Exact signatures appear below. Graph snippets for research, buyer review, draft admission,
dispatch and retention resolved to this worktree. No incompatible interface drift was found
in this bounded inspection; later-task interfaces are not thereby implemented or accepted.

| Surface | Current owner | Preserve |
| --- | --- | --- |
| Navigation | `features/live/conversation-home.ts`, `features/live/discussion-server.tsx`, `services/live/conversation-threads.ts` (root paths) | Six templates plus custom; `/app/discussions/s/:uuid`, local/legacy links, history |
| Research | `api/routes/runs.py:start_run` → `services/run_admission.py:admit_run` | Current member/profile, capability/budget/policy, transactional run/event/outbox, idempotency |
| Profile | `api/routes/icp.py:save_icp_version, approve_icp_version, list_icp_versions`; `services/icp_service.py:approve_icp` | Immutable version, explicit approval, offer revision/content hash |
| Buyer review | `api/routes/reviews.py:review_buyers` → `services/buyer_review.py:apply` | Native versions, current assessment, human review, approval invalidation |
| Lists | `api/routes/buyer_management.py:create_buyer_list, change_list_memberships` | Canonical lists, membership/project checks, idempotency/version |
| Drafts | `api/routes/drafts.py:generate_draft, get_draft, edit_draft`; `services/draft_service.py:admit_grounded_template, edit_draft` | Zero-cost grounded preparation, approved facts/accepted buyer, revisions; no implicit approval/send |
| Export | `api/routes/exports.py:export_draft`; `services/export_service.py:create_buyer_export, create_draft_export` | Native authorization, exact revision/approval and download eligibility |
| Dispatch | `execution/dispatcher.py:dispatch_cycle` | Bounded tenant rotation, durable outbox, selected transport |
| Retention | `services/retention.py:expire_subject_data`; `services/receipt_retention.py:expire_provider_receipts` | Derived-content erasure, approval invalidation, export revocation, delete intents |
| Threads/Drive | `api/routes/conversation_threads.py`, `db/conversation_threads.py`, `services/conversation_connections.py`, `services/drive_mcp.py` | Private owner/editor/viewer ACLs, current revocation, generic references, zero Drive content retention |

### Source defaults, not deployed configuration

- `NEXT_PUBLIC_CONVERSATION_HOME` requires exact string `true`; unset is OFF.
  `api/app.py` gates registration and requests. Historical Stage 3/4 Preview/Production
  statements were not reverified as hosted evidence.
- `services/conversation_admission.py:REGISTRATION=None`;
  `services/conversation_reply.py:ROUTE` is unselected (`route_id=None`), no permitted tools, repair limit zero.
- `settings.py`: paid admission, delivery admission, Cloudflare execution and R2 default OFF;
  live read and reconciliation default ON. No flag was changed.
- Drive grounding is `paid_eligible=False`; text cannot enter persistent model receipts.
  No credentials were provisioned. MCP tests use synthetic credentials and HTTP mocks.
- No sales/Xverum capability was introduced or activated. Proposed phone/reverse/job-change
  lookup remains outside enabled scope. Source presence is not live acceptance.

## Schema, readiness and rollback

**PASS (source only):** from `services/api`,
`uv run --frozen --no-sync alembic heads` returned exactly
`0059_conversation_connections (head)`, exit 0. No database connection or migration ran.

- `services/api/alembic/versions/0059_conversation_connections.py` has
  `down_revision='0058_conversation_threads'`. Its `_fences(head)` updates all three
  search/model/contact receipt writable functions to the exact revision.
- Migration source enables/FORCEs tenant RLS, grants API-only CRUD, and stores no content/credentials.
- `services/api/buyeros_api/services/schema_readiness.py:inspect_schema(connection: AsyncConnection, expected: SchemaContract) -> SchemaReadiness`
  checks target receipts, real runtime role, single compatible head, required revisions,
  relations/functions/grants/RLS in a read-only transaction. CLI:
  `services/api/tools/check_schema_readiness.py`. Inspected, not executed against a DB.
- `services/api/buyeros_api/services/worker_recovery.py` includes 0059 in its reviewed
  schema allowlist. `api/routes/health.py:readiness` checks current membership and
  runtime/heartbeat state; liveness alone is not readiness.
- `services/api/tests/test_conversation_connections_db.py` pins 0059; DB schema/RLS tests are BLOCKED.

**Rollback target: planned, unallocated.** A fresh disposable `postgres:16` container
with immutable container ID, image/ownership label and independently verified fixture receipt
before first SQL; separate migration owner and nonprivileged API runtime.
Rehearse 0059 → 0058 → 0059 on empty synthetic state, then verify populated Drive
connections/references refuse downgrade transactionally, retaining data/FORCE RLS/fences.
Do not erase populated state to make downgrade succeed. The migration source has this refusal.
**Rehearsal BLOCKED:** no target allocated and no downgrade/upgrade executed.

## Baseline results

All checks refer to the pinned SHA and Windows worktree. Retained evidence directory:
`.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-1-evidence/`.

| Check | Status | Evidence |
| --- | --- | --- |
| Frozen API setup | PASS | exit 0; `uv-sync.log`; owned `services/api/.venv` |
| Conversation/model/Drive plus thread/connection flag-off tests | PASS | 70 passed, 0 failed/skipped; one Starlette/AnyIO deprecation warning; `python-pure.log`, `python-pure.xml` |
| Source migration head | PASS | exit 0; 0059 only; `alembic-heads.log` |
| Core client runner, including discussions/context | BLOCKED; command FAIL | `node scripts/test-core.mjs` exit 1, six file-load failures, no assertions: missing `typescript`; exact `node-core.log` |
| Remaining conversation/thread/connection/admission/research DB cases | BLOCKED | Docker unavailable; not invoked; no skipped case counted as PASS |
| Isolated core browser journey | BLOCKED | Docker unavailable; not invoked; worker venv/frontend/pnpm/Corepack/Chromium not prepared or verified |
| DB readback, RLS/fences and rollback | BLOCKED | No proven isolated DB |
| Render/responsive, lint/typecheck/build and full worker suite | NOT_RUN | Bounded baseline, no full frontend install |
| Live model/Xverum and hosted acceptance | BLOCKED | No authorized account/activation; no live acceptance |
| Device/accessibility/localization end-to-end | NOT_RUN | No browser acceptance |

Exact selected command, from `services/api`:

```text
uv run --frozen --no-sync pytest tests/test_conversation_reply.py tests/test_conversation_model.py tests/test_drive_mcp.py tests/test_conversation_threads_api.py::test_flag_off_is_404_without_database_access tests/test_conversation_connections_api.py::test_flag_off_all_paths_fail_closed_before_auth_or_validation -q --junitxml=<worktree>/.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-1-evidence/python-pure.xml
```

Child-process setup removed inherited `BUYEROS_*` and `NEXT_PUBLIC_CONVERSATION_HOME`,
set `BUYEROS_STRICT_INTEGRATION=1`, and used the owned venv/worktree-local uv cache.
Only named non-DB cases were selected from DB-containing files. No app/server/worker started;
no database/broker/provider was contacted. Do not run seeded/destructive fixtures with inherited DSNs.

Future Windows core entrypoint:
`services/api/.venv/Scripts/python.exe services/api/tools/run_core_isolated.py`.
First review its Linux-specific `/workspace/.cache`, `/proc` and browser setup;
preserve its owned allocator and receipt checks. Shared/inherited DSNs are forbidden.
Do not start Docker Desktop or change machine settings to unblock this task.

## Scoped checkpoint

Artifacts remain uncommitted. Full report:
`.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-1-report.md`.
Source/lockfile and artifact hashes accompany retained evidence. No push/merge/deploy,
paid call, activation, shared mutation, secret change or controller-ledger edit.
Baseline capture is complete; integration and whole-phase acceptance remain blocked.
No task-completion/time/cost improvement metric is established by these tests.

## Exact native owner signatures

Resolved through the existing graph at the pinned checkout. These are current native
interfaces, not proposed sales-task interfaces.

### `services/api/buyeros_api/services/icp_service.py:approve_icp`

```python
approve_icp(
    session: AsyncSession,
    project_id: uuid.UUID,
    icp_id: uuid.UUID,
    expected_project_version: int,
    content_hash: str,
    actor_id: uuid.UUID,
    *,
    workspace_id: uuid.UUID,
    expected_number: int,
) -> dict
```

### `services/api/buyeros_api/api/routes/icp.py:approve_icp_version`

```python
approve_icp_version(
    workspace_id: uuid.UUID,
    icp_version_id: uuid.UUID,
    payload: ICPApproveRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> dict
```

### `services/api/buyeros_api/api/routes/buyer_management.py:change_list_memberships`

```python
change_list_memberships(
    workspace_id: uuid.UUID, list_id: uuid.UUID, payload: ListMembershipRequest, request: Request,
    response: Response, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    if_match: str | None = Header(default=None, alias="If-Match"),
)
```

### `services/api/buyeros_api/services/export_service.py:create_buyer_export`

```python
create_buyer_export(session, *, workspace_id, project_id, actor_id, request)
```

### `services/api/buyeros_api/api/routes/buyer_management.py:create_buyer_list`

```python
create_buyer_list(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: ListWrite, request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
)
```

### `services/api/buyeros_api/services/export_service.py:create_draft_export`

```python
create_draft_export(session, *, workspace_id, draft_id, actor_id,
                              request, expected_version)
```

### `services/api/buyeros_api/execution/dispatcher.py:dispatch_cycle`

```python
dispatch_cycle(
    engine, publish: Callable, owner: str, now: datetime, *,
    max_total: int, time_budget_seconds: float, cursor: int = 0,
    lease_seconds: int = 120, expired_only: bool = False,
) -> dict
```

### `services/api/buyeros_api/services/draft_service.py:edit_draft`

```python
edit_draft(session, *, workspace_id, draft, expected_version: int, changes: dict)
```

### `services/api/buyeros_api/api/routes/drafts.py:edit_draft`

```python
edit_draft(workspace_id: uuid.UUID, draft_id: uuid.UUID, payload: DraftUpdate,
                     request: Request, response: Response,
                     principal: Principal = Depends(get_principal),
                     idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                     if_match: str | None = Header(default=None, alias="If-Match")) -> dict
```

### `services/api/buyeros_api/services/receipt_retention.py:expire_provider_receipts`

```python
expire_provider_receipts(session,*,now,policy_version,limit=50,source_id=None)
```

### `services/api/buyeros_api/services/retention.py:expire_subject_data`

```python
expire_subject_data(
    session, subject_id: uuid.UUID, policy_version: str, now: datetime,
    *, subject_type: str,
) -> dict
```

### `services/api/buyeros_api/api/routes/exports.py:export_draft`

```python
export_draft(workspace_id: uuid.UUID, draft_id: uuid.UUID,
                       payload: DraftExportRequest, request: Request,
                       principal: Principal = Depends(get_principal),
                       idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                       if_match: str | None = Header(default=None, alias="If-Match")) -> dict
```

### `services/api/buyeros_api/api/routes/drafts.py:generate_draft`

```python
generate_draft(workspace_id: uuid.UUID, project_id: uuid.UUID,
                         payload: DraftGenerateRequest, request: Request,
                         principal: Principal = Depends(get_principal),
                         idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict
```

### `services/api/buyeros_api/api/routes/drafts.py:get_draft`

```python
get_draft(workspace_id: uuid.UUID, draft_id: uuid.UUID, request: Request,
                    response: Response, principal: Principal = Depends(get_principal)) -> dict
```

### `services/api/buyeros_api/api/routes/icp.py:list_icp_versions`

```python
list_icp_versions(
    workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict
```

### `services/api/buyeros_api/api/routes/reviews.py:review_buyers`

```python
review_buyers(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ReviewRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict
```

### `services/api/buyeros_api/api/routes/icp.py:save_icp_version`

```python
save_icp_version(
    workspace_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ICPSaveRequest,
    request: Request,
    principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict
```

### `services/api/buyeros_api/api/routes/runs.py:start_run`

```python
start_run(
    workspace_id: uuid.UUID, project_id: uuid.UUID, payload: RunCreate,
    request: Request, principal: Principal = Depends(get_principal),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    selection: tuple[dict | None, str] = Depends(selected_run_capability),
) -> dict
```

### `services/api/buyeros_api/services/draft_service.py:admit_grounded_template`

```python
admit_grounded_template(session, *, workspace_id, project_id, actor_id, request)
```

### `services/api/buyeros_api/services/run_admission.py:admit_run`

```python
admit_run(session, actor_id: uuid.UUID, project_id: uuid.UUID, request: RunCreate,
                    *, workspace_id: uuid.UUID, capabilities: dict | None,
                    environment: str = "production") -> dict
```

### `services/api/buyeros_api/services/buyer_review.py:apply`

```python
apply(session, *, workspace_id, project_id, actor_user_id, active_icp_version_id, selection: dict, status: str, reason: str) -> dict
```

## Subsequent baseline evidence (controller, 2026-11-05)

Frozen pnpm 11.25.0 dependency installation completed. Package manifest and lockfile diff was empty (exit 0). Re-ran `node scripts/test-core.mjs`: exit 0, 86 passed, zero failures/skips. Receipt: `.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/task-1-evidence/node-core-after-install.log`. This supersedes only the earlier client-runner BLOCKED status; original failure output remains retained. Database/browser/rollback and live acceptance remain BLOCKED. The independent Task 1 reviewer inspected the new log and approved the bounded baseline evidence.




