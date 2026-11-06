# Guided Sales Skills and Xverum Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete sales tasks through guided chat with versioned native outputs and bounded, reviewed Xverum buyer enrichment.

**Architecture:** Extend the existing conversation home, server threads, sharing, model admission and native domain services. Add a versioned skill registry, durable task/event/output layer and Xverum connection/credit boundary; models propose typed actions while the server authorises and executes them. Preserve existing canonical buyers, profiles, runs and drafts.

**Tech Stack:** Existing React/TypeScript/Vinext frontend; Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy and Alembic/PostgreSQL backend; existing durable execution infrastructure; HTTP MCP adapter and existing OpenCode Go model transport. Retain the selected revision's lockfiles and framework runner.

**Spec:** `docs/superpowers/specs/2026-11-05-guided-sales-skills-xverum-design.md`, approved 2026-11-05, plus its referenced October preservation map.

## Global Constraints

- “A complete task has a persisted output with canonical readback, provenance, and an accurate execution state.”
- “Canonical buyers, lists, profiles, runs and drafts remain authoritative.”
- “New conversations read only selected, authorised project facts, documents and outputs, not sibling transcripts automatically.”
- “No arbitrary shell execution or dynamic skill installation.”
- “No initial search approval authorises unspecified downstream enrichment.”
- “A lost response creates Outcome unknown and retains the reservation.”
- “Do not store credits in a USD amount.”
- “Phone lookup, reverse lookup, and job-change prediction stay disabled by default.”
- “Raw responses are not retained by default.”
- “Without an authorised live model and Xverum account, the UI shows configuration requirements and live acceptance stays BLOCKED.”
- Complete the entire mapped catalogue; partial delivery is not whole-phase completion. No automatic sending, scheduling, autonomous approvals, or replacement of existing screens.
- Preserve private-by-default discussion ACLs, project-assigned administrator connections, en/zh-HK, keyboard/mobile/zoom, source deletion and permission revocation.
- Preserve Drive's existing zero-content-retention and `paid_eligible=False` boundaries. This plan authorises no new use of Drive bodies in durable outputs/model receipts.
- Current root AGENTS.md: “Avoid unnecessary secondary labels and descriptions. Let the layout do the explaining.” Use status text only where it communicates a meaningful state or decision.
- Implementation preparation must preserve all dirty worktrees and evidence. No blanket add/reset/clean. Commit checkpoints below require task-specific Git authorisation; otherwise leave reviewed changes uncommitted. No push/merge/deploy, shared DB migration, OAuth provisioning or paid call follows merely from plan/design approval.

## Review Focus

1. A share is revoked after a task starts: the former editor cannot read its events/results or cause further dispatch (Tasks 3, 5, 14).
2. Discovery returns two subsidiaries with the same name: neither detail calls nor field writes occur until explicit identity selection (Tasks 9, 10).
3. Provider receives a request but its response is lost: hold remains, reconnect does not dispatch twice, operator evidence is required (Tasks 8, 9).
4. A restricted Drive excerpt enters a mixed context selection: it never reaches persistent skill receipts or outputs (Tasks 4, 14).
5. A user edits a buyer or draft while chat prepares a save: reject the stale write and retain the proposed result for review (Tasks 6, 10, 11).

---

## Verified starting point and scope

Plan status: complete for review; execution has not started. All task checkboxes remain open. This is one coordinated plan because task identity, quotes, output authority and recovery are shared interfaces; skill groups are separately testable delivery increments.

Selected implementation base: **YNWAforever/BuyerOS main `da49de0f70077db14c15219338133b59fcecd822`**, verified with read-only `git ls-remote` and GitHub commit/compare APIs on 2026-11-05. It contains retained `3c79793b` and is 28 commits ahead. The primary local checkout is still `3f10f419`; do not implement here by assumption. The selected commit is not present in its local object database. Fetching/creating an isolated checkout belongs to execution, not this planning turn. Never switch or reset a retained checkout. If remote main changes, compare the new SHA and revise this baseline before execution.

Current source inspected at the selected SHA:

| Existing owner | Reuse / required extension |
|---|---|
| `features/live/conversation-home.ts` | Six templates plus custom, existing `/app/discussions/s/:uuid` routes and scope-aware navigation. Extend IDs; retain old links and history behaviour. |
| `features/live/discussion-server.tsx`, `services/live/conversation-threads.ts` | Server thread ACL/version handling; accepted AI answers are presently memory-only. Introduce durable task/output readback. |
| `api/routes/conversation_threads.py`, `db/conversation_threads.py` under `services/api/buyeros_api/` | Notes and references, owner/editor/viewer ACLs, idempotency, limits. Reuse thread IDs; add separate typed task/answer data without weakening legacy import allowlists. |
| `services/conversation_reply.py`, `services/conversation_admission.py` | Approved source grounding and bounded model admission. `REGISTRATION=None`, route unselected; no active model inferred from credentials. |
| `providers/conversation_model.py`, `providers/opencode_model.py` | Strict cited answer schema and OpenCode Go transport (`DEFAULT_MODEL_ID='kimi-k3'` in source). Add sales schemas with separate reviewed registration; no vendor switch or automatic activation. |
| `db/conversation_connections.py`, `services/drive_mcp.py` | Drive metadata and transport hardening patterns. Xverum gets its own connection/account semantics, not Drive folder-grant impersonation. |
| `0058_conversation_threads`, `0059_conversation_connections` | Existing schema authorities and receipt fences. New migrations are additive and update readiness/fences coherently. |

The graph used for initial discovery was BuyerOS_T21 and does not contain these newer modules. Exact-SHA GitHub source reads resolved that insufficiency. Re-index the execution checkout before discovery. No product tests, schema changes, live calls or rollout checks were run while writing this plan.

## File map and ownership

All paths below are relative to the chosen implementation checkout. New files are proposals, not claims of existing implementation. Python package prefix **API** means `services/api/buyeros_api/`; test prefix **PT** means `services/api/tests/`. These aliases are expanded mechanically and must not be mistaken for directories named API/PT.

| Unit | Files / responsibility |
|---|---|
| Skill definitions | New `API/sales/contracts.py`, `registry.py`, `catalogue.json`, `playbooks/*.md`, `provenance.json`, `THIRD_PARTY_NOTICES.md`; code-owned definitions, schemas and attribution. |
| Thread/task persistence | Modify `API/db/conversation_threads.py`; new `API/db/sales_tasks.py`, `API/services/sales_tasks.py`, `API/api/routes/sales_tasks.py`; extract reusable ACL helpers into `API/services/conversation_access.py`. |
| Context/model | New `API/sales/context.py`, `model.py`, `planning.py`; extend `API/providers/opencode_model.py`, `live_model.py`, `model_receipts.py` by schema dispatch only; retain legacy validation. |
| Durable execution | New `API/execution/sales_tasks.py`, `API/sales/actions.py`; reuse native outbox, worker admission and recovery through existing execution routing. |
| Outputs | New `API/db/sales_outputs.py`, `API/services/sales_outputs.py`, `API/api/routes/sales_outputs.py`; native references, authored versions and dependency graph. |
| Xverum | New `API/db/xverum.py`, `API/providers/xverum_mcp.py`, `API/services/xverum_connections.py`, `xverum_quotes.py`, `xverum_credits.py`, `xverum_enrichment.py`, `API/api/routes/xverum.py`. |
| Skill runners | New `API/sales/research.py`, `drafting.py`, `documents.py`, `reporting.py`; small domain-specific adapters. |
| Browser | New `services/live/sales-tasks.ts`, `sales-outputs.ts`, `xverum.ts`; new `features/live/sales-skills/{task-cards,task-progress,output-panel,enrichment-review,connections,documents}.tsx`. Extend current discussion/navigation rather than adding a parallel app shell. |
| Contracts | New `docs/buyeros/contracts/sales.openapi.yaml`, `scripts/generate-sales-api.mjs`, `services/generated/sales-api.ts`; a generated extension contract, leaving the retained proposed contract and legacy hand-written adapters intact. |
| Schema | New `0060_sales_tasks.py`, `0061_sales_outputs.py`, `0062_xverum_credits.py` in `services/api/alembic/versions/`; renumber only if the execution base has advanced, updating every reference. |
| Evidence | New `docs/buyeros/GUIDED_SALES_ACCEPTANCE.md`, `docs/buyeros/runbooks/xverum.md`, `playwright.sales-skills.config.ts`, focused Python/Node/browser tests listed below. |

## Shared contracts and testing conventions

Task 2 owns Pydantic contracts and generated TypeScript names. Use UUIDs for internal identity, Decimal for currency and integer provider credits. `Scope(workspace_id, project_id, actor_id)` is server-derived. `SourceRef(id, version, kind, locator, retention_class)` references currently authorised evidence. `ContextSnapshot(refs, digest, profile_version, connection_generations)` contains immutable references; authorised text is materialised only for the call. `SkillDefinition(id, version, inputs_schema, output_kind, allowed_actions, languages, budget_class, upstream_hash)` is immutable.

`TaskInput(thread_id, skill_id, skill_version, user_message, source_refs, arguments)` feeds `TaskRecord(id, state, revision, context_digest, output_ids, pending_review)`. `TaskEvent(task_id, sequence, kind, payload)` contains bounded typed data; no tokens/raw provider bodies. `ActionProposal(id, capability, arguments, source_versions)` is an untrusted model suggestion. `OutputCandidate(kind, content, citations, dependencies, native_refs)` becomes `OutputVersion(id, revision, visibility, native_refs)` only after validation and save. `NativeRef(surface, id, revision)` supports profile/buyer/list/run/draft/document; no arbitrary URLs.

`XverumQuote(id, stage, actor_id, connection_generation, query, provider_ids, tool_plan, max_credits, tariff_version, expires_at, fingerprint)` distinguishes `search` and `detail` stages. `XverumReceipt(id, dispatch_state, request_id, credits_used, held_credits, projection_digest)` has no raw response field. `EnrichmentProposal(id, buyer_id, buyer_version, identity_match, fields, source_refs)` carries field choices without applying them.

Task 2 also owns `SalesModelRequest(task_id, step_id, skill_id, skill_version, context, model_id, route, arguments)` and `SalesModelResult(candidate, usage, provider_ref, model_id, prompt_version)`. Extend the output read representation with `content`, `citations`, `dependencies` and `availability`; unavailable content is never returned just because its metadata is visible. Define `CONTACT_ALLOWLIST` as the five enabled Xverum tool names in the approved spec; person/company details and email still require their separate quoted stages.

Builder execution bounds: a single invocation has at most 16 steps and 8 model calls, at most 2 concurrent steps, and no automatic model repair. Admit the aggregate maximum liability from the selected registration before executing its model steps; each child consumes part of that reservation rather than acquiring an extra unbounded budget. A larger request becomes a separately reviewed follow-on task. These are implementation defaults within the design's bounded-execution requirement, not newly authorised live spending.

Named regression anchors (implement in the corresponding task's test files; surrounding red steps add their related cases):

| Task | Test function and decisive assertion |
|---|---|
| 2 | `test_contacts_registry_is_allowlisted`: `assert skill.allowed_actions == CONTACT_ALLOWLIST` |
| 3 | `test_task_replay_after_share_revocation`: `assert replay.status_code == 404` and `assert task_count == 1` |
| 4 | `test_mixed_drive_context_cannot_enter_sales_receipt`: `assert model.calls == 0` and `assert receipt_count == 0` |
| 5 | `test_stream_reconnect_does_not_execute_again`: `assert dispatched_step_count == 1` |
| 6 | `test_output_regeneration_keeps_old_revision`: `assert new.revision == old.revision + 1` and `assert get(old.id, old.revision).content == original` |
| 7 | `test_disconnect_wins_over_late_refresh`: `assert connection.status == 'disconnected'` and `assert transport.calls == 0` for the next attempted data call |
| 8 | `test_competing_credit_reservations_are_atomic`: `assert admitted == 1` and `assert held_credits == 5` |
| 9 | `test_lost_response_keeps_hold_without_redispatch`: `assert transport.calls == 1` and `assert held_credits == quoted_max` |
| 10 | `test_stale_enrichment_apply_preserves_native_buyer`: `assert response.status_code == 409` and `assert buyer.fields == before.fields` |
| 11 | `test_material_draft_edit_invalidates_approval`: `assert draft.approval_is_current is False` using the native equivalent readback field |
| 12 | `test_pdf_exports_the_selected_revision`: `assert export.output_revision == requested_revision` |
| 13 | Browser test `saved output survives reload`: `expect(outputHeading).toBeVisible()` after reload and native-record navigation |
| 14 | `test_deleted_source_is_unreadable_from_all_outputs`: `assert readable_derived_outputs == []` and `assert exported_body_count == 0` |
| 15 | `test_sales_runner_rejects_shared_database`: `assert exit_code != 0` and `assert database_writes == 0` |

Task 15 creates `PT/test_sales_runner.py` for its guard assertion and runs it before launching any database fixture.

All DB/API tests run from `services/api`: `uv run pytest tests/<file>.py -q`. Only use a proven disposable DB and synthetic provider/model adapters; inherited/shared DSNs are forbidden. Unit red tests must fail on the named missing behaviour, not environment setup. DB red/green tests require role/RLS-capable isolated PostgreSQL; if resources are insufficient mark BLOCKED, not skipped PASS. Existing isolated runner `services/api/tools/run_core_isolated.py` is the starting point for fixture orchestration.

Frontend commands run at checkout root. Test examples below use fixtures/helpers defined in their test files or shared `PT/sales_fixtures.py`; they are assertions to implement, not existing test results. Each implementation task has its own red/green check and scoped review checkpoint. No test runner should call a live provider by default.

Dependency sequence: **1 → 2 → 3 → 4 → 5 → 6**. Connection/ledger work **7 → 8 → 9** can proceed after contracts; integration **10** joins outputs and provider work. **11–12** finish skill groups; **13** completes UI; **14** tests lifecycle boundaries; **15** records acceptance and release readiness.

### Task 1: Establish the isolated baseline and preservation evidence

**Files:** Read current `AGENTS.md`, `ARCHITECTURE.md`, `docs/DEVELOPMENT.md`, `docs/buyeros/CONVERSATION_THREADS_STAGE3.md`, `CONVERSATION_CONNECTIONS_STAGE4.md`; create `docs/buyeros/GUIDED_SALES_ACCEPTANCE.md`.

**Interfaces:** Consumes approved spec and selected SHA. Produces an evidence table of exact checkout SHA, toolchain, schema head, existing route/native-action owners, default flags, test commands and environment identity.

- [ ] Verify remote identity and compare current main against the pinned SHA; create an isolated `codex/guided-sales-skills-xverum` checkout using the worktree skill only when execution begins. Preserve primary/untracked/retained trees.
- [ ] Index that checkout; resolve current native research, profile, buyer-review/list, draft, export, job-dispatch and retention owners. Record exact paths and signatures in the evidence file; stop on incompatible interface drift instead of porting from the older graph.
- [ ] Run existing conversation/model/thread/connection tests and the isolated core journey. Record actual PASS/FAIL/BLOCKED/NOT_RUN by SHA; capture pre-existing failures before editing.
- [ ] Verify 0059 is the single migration head and document schema-fence/readiness references. Record a zero-shared-mutation test setup and an isolated rollback rehearsal target.
- [ ] Review this baseline and retain a scoped checkpoint; do not claim implementation progress from source presence alone.

### Task 2: Add versioned skill definitions and extension contracts

**Files:** Create `API/sales/{__init__,contracts,registry}.py`, `catalogue.json`, `provenance.json`, `THIRD_PARTY_NOTICES.md`; create the 13 upstream-named `playbooks/sales-*.md` files plus `first-project.md`, `understand-documents.md`, `review-buyers.md`; create extension OpenAPI/generator/generated TS files from the file map. Test `PT/test_sales_registry.py`, `tests/sales-contracts.test.mjs`.

**Interfaces:** `load_skill(skill_id: str, version: str) -> SkillDefinition`; `validate_arguments(skill: SkillDefinition, arguments: dict) -> dict`; types in Shared contracts. Existing seven template IDs map to canonical skill IDs without rewriting old threads. `sales-prospect` orchestrates, `sales-quick` is a bounded alias of research, `sales-report-pdf` exports the same report revision.

- [ ] Write red tests: `assert load_skill('sales-contacts','1').allowed_actions == CONTACT_ALLOWLIST`; `assert all(s.languages == ('en','zh-HK') for s in catalogue)`; reject unknown skill/version, unknown input keys and disabled capabilities. Verify all upstream groups plus native templates have schemas and output validators.
- [ ] Run `uv run pytest tests/test_sales_registry.py -q`; require failure on absent registry.
- [ ] Pin an exact upstream commit, inspect every imported playbook/script/template, preserve MIT attribution, and adapt text only. Remove installer/shell/file execution assumptions. Make each playbook consume typed selected context and return its specified output kind. Define schemas for all shared contracts and API operations used below.
- [ ] Implement `generate-sales-api.mjs --write|--check` using the existing OpenAPI generator pattern. Run registry tests, `node scripts/generate-sales-api.mjs --check`, and `node --test tests/sales-contracts.test.mjs`; require complete catalogue coverage and no legacy-contract drift.
- [ ] Review/checkpoint only these files; record upstream SHA/hash and compatibility mapping.

### Task 3: Extend durable threads with task identity and events

**Files:** Create `API/db/sales_tasks.py`, `API/services/sales_tasks.py`, `API/services/conversation_access.py`, `API/api/routes/sales_tasks.py`, migration `0060_sales_tasks.py`; modify existing thread routes/models, `API/db/__init__.py`, `API/api/app.py` and exact schema fences from Task 1. Tests `PT/test_sales_tasks_db.py`, `test_sales_tasks_api.py`.

**Interfaces:** `create_task(session, scope: Scope, data: TaskInput, key: str, expected_thread_version: int) -> TaskRecord`; `get_task(session, scope, task_id: UUID) -> TaskRecord`; `append_event(session, task_id: UUID, kind: str, payload: dict) -> TaskEvent`; `read_events(session, scope, task_id: UUID, after: int) -> list[TaskEvent]`. New project-root `/sales-tasks` POST/GET-detail, GET `/{id}/events?after=`, POST `/{id}/cancel`; native live envelope/no-store/idempotency/If-Match conventions.

- [ ] Red tests: `assert replay.id == first.id`; `assert event_sequences == sorted(set(event_sequences))`; same key/different payload conflicts; revoked editor gets no task/event data; old import still rejects AI bodies. Test simultaneous append and thread deletion with a running task.
- [ ] Run both task test files and confirm intended failures.
- [ ] Extract thread ACL checks without changing legacy authority. Add tasks, monotonic events, dependency references and client-message deduplication. Add per-actor pin/archive preference and ACL-filtered title/note search; do not expose private titles. Keep existing note limits (4000 characters, 100 notes) with actionable limit errors, not silent truncation. New assistant/task records are separate from legacy note imports. FORCE RLS, composite tenant/project/thread FKs, minimal role grants; no worker blanket access to notes.
- [ ] Require active work to be cancelled/reconciled before hard deletion; remove private content under retention rules while keeping only permitted content-free receipt evidence. Test populated downgrade refusal and empty isolated downgrade/upgrade. Run tests plus existing `test_conversation_threads_db.py` and `test_conversation_threads_api.py`; require unchanged legacy behaviour.
- [ ] Review/checkpoint schema, route contract and ACL diff together.

### Task 4: Build context resolution and the sales model boundary

**Files:** Create `API/sales/{context,model,planning}.py`; modify `API/providers/{opencode_model,live_model,model_receipts}.py` via explicit schema branches. Tests `PT/test_sales_context.py`, `test_sales_model.py`.

**Interfaces:** `resolve_context(session, scope: Scope, refs: list[SourceRef]) -> ContextSnapshot`; `plan_task(skill: SkillDefinition, arguments: dict, context: ContextSnapshot) -> TaskPlan`; `validate_sales_proposal(payload: dict, context: ContextSnapshot, skill: SkillDefinition) -> OutputCandidate | ActionProposal`; `SalesModelClient.complete(request: SalesModelRequest) -> SalesModelResult`. Define `TaskPlan(steps, missing_inputs, output_kind)` and model request/result types in Task 2 contracts.

- [ ] Red tests: selected facts only; no sibling transcripts; `assert model.calls == 0` for a Drive/mixed nonpersistent source entering a durable skill; reject invented citation, authority fields, tool calls, invalid JSON and oversized output. Missing offer facts must produce `missing_inputs`, not invented product claims.
- [ ] Run both focused tests for expected failures.
- [ ] Reuse source-authorisation services. Materialise only allowed text in request memory; pin references/digests and code-owned prompt versions. Add `sales-basis.v1` schema dispatch while preserving fit/conversation validators. Model tools remain disabled: typed proposals are executed later by the server. Retain OpenCode Go transport and explicit model ID selection; add a separate unselected sales registration. Set initial per-call bounds to 6000 input tokens, 1000 output tokens, 30 seconds, zero automatic repair; split long outputs into bounded sections under a parent budget.
- [ ] Keep useful progress streaming as durable events, not partial unvalidated prose. No token-streaming dependency is required. Add model usage receipts but do not equate token counts to final supplier billing. Run tests and existing `test_conversation_model.py`, `test_conversation_reply.py`; require default `CONVERSATION_MODEL_UNAVAILABLE` unchanged.
- [ ] Review/checkpoint context leakage and schema dispatch before native actions consume them.

### Task 5: Execute validated task steps durably

**Files:** Create `API/execution/sales_tasks.py`, `API/sales/actions.py`; modify `API/services/sales_tasks.py`, existing native dispatch selector and `API/services/worker_recovery.py` at Task 1's resolved owner. Tests `PT/test_sales_execution_db.py`.

**Interfaces:** `admit_step(session, scope, task_id: UUID, proposal: ActionProposal, review_id: UUID | None) -> StepReceipt`; `execute_step(engine, step_id: UUID) -> StepReceipt`; `cancel_task(session, scope, task_id: UUID, expected_version: int) -> TaskRecord`. `StepReceipt(id, task_id, dispatch_state, native_operation_id, reservation_ids)` references existing jobs rather than replicating them.

- [ ] Red tests: two workers claim once; stream reconnect starts zero work; revoked actor before dispatch causes no external call; cancellation after dispatch preserves liability; one failed branch produces partial completion; `assert task.state != 'Completed'` until output readback.
- [ ] Run `uv run pytest tests/test_sales_execution_db.py -q` and verify intended failures.
- [ ] Add explicit action registry and transactional admission/outbox linkage. Dispatch independent prospect substeps with bounded concurrency (initial maximum 2) under one parent context/cost ceiling. Each action checks actor/project/source policy at dispatch. Expose Needs input/Ready for review/Queued/Running/Partially completed/Completed/Failed/Cancel requested/Cancelled/Outcome unknown. Never execute arbitrary model instructions or trust provider progress text.
- [ ] Test restart at each commit/external-await boundary, including an uncertain native save; read back before retrying. Run focused tests and existing recovery/admission suites selected in Task 1.
- [ ] Review/checkpoint worker grants, lock order, dispatch claims and cancellation.

### Task 6: Persist versioned outputs and native links

**Files:** Create `API/db/sales_outputs.py`, `API/services/sales_outputs.py`, `API/api/routes/sales_outputs.py`, migration `0061_sales_outputs.py`; update registry imports/readiness/fences. Tests `PT/test_sales_outputs_db.py`.

**Interfaces:** `save_output(session, scope, task_id: UUID, candidate: OutputCandidate, key: str, visibility: Literal['thread','project']) -> OutputVersion`; `get_output(session, scope, output_id: UUID, revision: int | None) -> OutputVersion`; `apply_native_action(session, scope, proposal: ActionProposal, expected_revision: int, key: str) -> NativeRef`. Routes `/sales-outputs` POST/list, GET `/{id}`, GET `/{id}/versions`.

- [ ] Red tests: `assert regenerated.revision == previous.revision + 1`; same save key creates one revision; no shared output backlink reveals a private thread; native write rejects stale revision; task completion requires saved output readback. Reject saving source bodies with nonpersistent retention class.
- [ ] Run `uv run pytest tests/test_sales_outputs_db.py -q` for expected failures.
- [ ] Persist authored content separately from canonical records; store dependency graph and source revisions. Default authored output visibility to thread; show destination/audience before explicit project save. Native buyer/list/draft writes use existing services and permissions. Add list queries by native record ID so full screens show related outputs. Render Markdown safely without raw HTML or executable links.
- [ ] Test direct reopen without transcript access, inaccessible-source redaction, FORCE RLS, empty rollback and populated downgrade refusal. Require tests PASS and unchanged native record version/approval semantics.
- [ ] Review/checkpoint visibility and source-lifecycle graph.

### Task 7: Add project-assigned Xverum connections and bounded MCP transport

**Files:** Create `API/providers/xverum_mcp.py`, `API/services/xverum_connections.py`, `API/api/routes/xverum.py`, `API/db/xverum.py`; connection schema joins migration 0062 in Task 8. Tests `PT/test_xverum_mcp.py`, `test_xverum_connections.py`.

**Interfaces:** `XverumTransport.call(tool: XverumTool, arguments: dict, credential: SecretHandle) -> XverumResult`; `require_xverum_connection(session, scope: Scope) -> ConnectionBinding`; `disconnect_xverum(session, scope, expected_version: int, key: str) -> ConnectionBinding`. Define `SecretHandle`, `ConnectionBinding(id, generation, account_ref, project_ids, status, tariff_version)` and allowlisted response projections in contracts; opaque secret references only in application DB.

- [ ] Red tests: reject wrong endpoint, redirect, tool, oversized response, malformed structured payload, foreign connection generation and cross-project access; `assert raw_token not in logs_or_response`; disconnect remains possible during provider outage. Token refresh is single-flight and revocation cannot be undone by a late refresh.
- [ ] Run both transport/connection tests using an owned HTTP fixture only.
- [ ] Implement server-only OAuth credential-provider interface `resolve(binding) -> SecretHandle`, `refresh(binding) -> SecretHandle`, `revoke_local(binding) -> None`; use existing secret-service adapter if compatible. Keep live implementation disabled until OAuth client registration/refresh and SaaS account delegation are verified. Do not borrow Drive gateway credentials or developer OAuth. Admin-only connection assignment/rotation; current generation checked every call.
- [ ] Implement MCP initialise/session handling and JSON/bounded SSE responses using existing Drive transport hardening as reference. Fixed HTTPS Xverum endpoint; redirects and environment proxy inheritance off; one 12-second deadline and 64-KiB decoded-response cap per call. Allow only company/people search/detail and business email. Revalidate actual advertised schemas at activation; unknown required-field drift fails closed. Run tests, including prompt-injection text treated solely as data.
- [ ] Review/checkpoint protocol and credential boundary. OAuth deployment remains BLOCKED until separately provisioned; fixtures are not live proof.

### Task 8: Add staged quotes and an atomic credit ledger

**Files:** Create `API/services/xverum_{quotes,credits}.py`, migration `0062_xverum_credits.py`; extend `API/db/xverum.py`, routes, readiness/fences; reuse monetary budget service. Tests `PT/test_xverum_quotes_db.py`, `test_xverum_credits_db.py`.

**Interfaces:** `quote_search(session, scope, connection_id: UUID, query: str, target: Literal['company','people'], buyer_id: UUID) -> XverumQuote`; `quote_details(session, scope, search_receipt_id: UUID, selected_ids: list[str], include_email: bool) -> XverumQuote`; `confirm_quote(session, scope, quote_id: UUID, fingerprint: str, key: str) -> StepReceipt`; `settle_credits(session, receipt_id: UUID, credits_used: int) -> None`.

- [ ] Red tests: search ceiling 5; company detail 4; people search 5; at most three people details (12); optional email only selected people (at most 6). `assert unknown_receipt.held_credits == original_hold`; two simultaneous 5-credit reservations with 5 available admit exactly one. Missing required USD tariff blocks before dispatch. Altered IDs/generation/query/expiry invalidate confirmation.
- [ ] Run both tests against isolated PostgreSQL and verify failures.
- [ ] Add provider-account credit account/reservation/settlement/receipt tables with tenant FKs, unique operation keys and integer CHECKs. Workspace cap and project limits share a consistent lock order with USD budget locks. Use a versioned tariff supplied by an administrator; no conversion guessed. Set quote lifetime to five minutes as a builder default, retaining native actor/version/expiry controls.
- [ ] Bind search quote to exact query/limits, not unknown identities. Pause after results; detail quote binds selected returned IDs and exact tools. One approved quote cannot authorise future selection. Store minimum request identity, digest and usage; do not retain raw payload. Test idempotent settlement, genuine zero-result usage, malformed/over-ceiling usage held for reconciliation and shared-account concurrency. Run legacy `test_budget_atomicity_db.py` too.
- [ ] Review/checkpoint credit/money separation and schema downgrade protections.

### Task 9: Add provider dispatch receipts and uncertain-outcome recovery

**Files:** Extend `API/execution/sales_tasks.py`, `API/services/xverum_credits.py`; create `API/services/xverum_dispatch.py`, `docs/buyeros/runbooks/xverum.md`. Tests `PT/test_xverum_dispatch_db.py`.

**Interfaces:** `dispatch_xverum(engine, step_id: UUID) -> XverumReceipt`; `reconcile_xverum(session, scope, receipt_id: UUID, evidence: ReconciliationEvidence) -> XverumReceipt`. `ReconciliationEvidence(provider_request_id, authoritative_usage, evidence_ref, resolution, expected_version)` is operator-supplied through existing operational permissions; evidence references must not be public access-bearing URLs.

- [ ] Red tests cover crash before/after durable claim, timeout after provider acceptance, duplicate callbacks/readback, generation revocation, out-of-credit denial and a result whose projection save fails. `assert transport.calls == 1` after uncertain retry/reconnect. No-results is not a transport failure.
- [ ] Run `uv run pytest tests/test_xverum_dispatch_db.py -q` for intended failures.
- [ ] Commit dispatch claim before await; persist validated projected result/receipt atomically when possible. Keep usage hold when acceptance or billing is unknown; never trust assumed provider deduplication. Operator reconciliation can settle known usage or confirm non-dispatch from authoritative evidence; absent evidence leaves hold/Outcome unknown. No blind retry endpoint. Cancel prevents future undispatched steps, not already accepted calls.
- [ ] Implement bounded backoff only for positively known nonaccepted calls within quote/deadline; otherwise stop. Run crash-injection tests and check no secrets/personal payloads in logs. Document a redacted operator runbook and balance-reconciliation procedure.
- [ ] Review/checkpoint recovery and external-call count evidence.

### Task 10: Enrich company/person fields through reviewed native saves

**Files:** Create `API/services/xverum_enrichment.py`, extend `API/api/routes/xverum.py`, skill actions and native buyer/evidence service owners recorded in Task 1. Tests `PT/test_xverum_enrichment_db.py`.

**Interfaces:** `propose_enrichment(session, scope, buyer_id: UUID, receipt_ids: list[UUID]) -> EnrichmentProposal`; `apply_enrichment(session, scope, proposal_id: UUID, fields: list[str], expected_buyer_version: int, key: str) -> NativeRef`. Add POST `/xverum/enrichment-proposals`, POST `/{id}/apply` under the project root, requiring native permissions plus task/thread authority when linked.

- [ ] Red tests: same-name subsidiary requires selection; conflicting domain is not auto-merged; person with uncertain employer stays unresolved; null end date does not prove current employment. `assert buyer.review_status == before.review_status`; stale buyer revision returns conflict with no field writes; suppressed contact cannot be retrieved/exposed.
- [ ] Run `uv run pytest tests/test_xverum_enrichment_db.py -q` for expected failures.
- [ ] Map provider identity to canonical buyer with corroborating domain/name/location. Present field-level before/after/source/time/conflict. Persist only selected business-relevant fields and citations, never education/personal background. Recheck company/person match, current permission, provider generation, suppression and source revision before native save. Keep provider verification labels attributed, not upgraded to BuyerOS verification.
- [ ] Save proposal/result output through Task 6 and verify canonical readback. Test repeated apply returns one native revision and no duplicate person records; record provenance without accepting buyer/approving profile/unsuppressing contact. Run buyer review/source regressions from Task 1.
- [ ] Review/checkpoint the full search → select → detail → field review → native-save path.

### Task 11: Complete profile, research, shortlist and drafting skills

**Files:** Create `API/sales/research.py`, `drafting.py`; extend native action registry and catalogue playbooks. Tests `PT/test_sales_research.py`, `test_sales_drafting_db.py`, `test_sales_core_journey_db.py`.

**Interfaces:** `run_research_skill(scope, task_id: UUID, context: ContextSnapshot) -> OutputCandidate`; `prepare_draft(scope, task_id: UUID, context: ContextSnapshot) -> OutputCandidate`; `save_formal_draft(session, scope, output_id: UUID, recipient_id: UUID, expected_revision: int | None, key: str) -> NativeRef`. Reuse native `startRun`/quote/list/profile/draft commands resolved in Task 1.

- [ ] Red tests for ICP proposal without auto-approval; research linked to one existing run; missing provider/profile yields explicit Needs input/unavailable; advisory qualification preserves unknown budget/authority/timing; shortlist changes require review. Outreach/follow-up must reject fabricated citations, introductions and commercial proof points. Preparation can exist without an eligible recipient, formal draft cannot.
- [ ] Run the three tests for expected failures.
- [ ] Implement all core skills and native setup/document/shortlist guidance through Task 5 actions. Prospect branches reuse discovery once and share context/budget. Document extraction reuses existing uploader/extraction statuses; image-only content remains unknown. Draft sequence steps are authored preparations, never scheduled messages; formal creation uses native recipient/policy/suppression and revision controls.
- [ ] Exercise one isolated end-to-end fixture journey through saved buyer evidence, research report, draft preparation, eligible formal draft, approval, then material edit invalidation. Verify no send endpoint is introduced and no duplicate research execution after failed link save.
- [ ] Review/checkpoint native-domain semantics and evidence grounding.

### Task 12: Finish meeting, proposal, objections, competition and reports

**Files:** Create `API/sales/documents.py`, `reporting.py`; extend output kinds/catalogue and existing export-service owner from Task 1. Tests `PT/test_sales_documents.py`, `test_sales_reporting_db.py`.

**Interfaces:** `compose_sales_document(skill_id: str, context: ContextSnapshot, inputs: dict) -> OutputCandidate`; `build_pipeline_report(session, scope, as_of: datetime, filters: dict) -> OutputCandidate`; `export_output(session, scope, output_id: UUID, revision: int, format: Literal['markdown','pdf']) -> NativeRef`.

- [ ] Red tests require a saved output for each remaining skill; missing pricing/case-study facts require input; competitor claims cite evidence. Unavailable pipeline metric must not equal zero. `assert exported.revision == requested.revision`; revoked source blocks export; Chinese text must remain readable in PDF.
- [ ] Run both focused tests for intended failures.
- [ ] Implement grounded meeting briefs, proposals, objection playbooks and competitor reports. Reports reference actual project records with fixed as-of/filter scope. Use native export approval/audit; generate PDF from the exact authorised saved revision, with a bundled licensed CJK-capable font and pinned dependency only if the chosen checkout lacks a suitable renderer. Do not execute upstream PDF scripts unreviewed.
- [ ] Verify catalogue coverage includes report Markdown/PDF, no unresolved placeholder templates, and regeneration history. Run focused tests and native export regressions.
- [ ] Review/checkpoint catalogue-to-output coverage matrix.

### Task 13: Complete the guided chat UI and native output access

**Files:** Create frontend files in the file map; modify `features/live/{conversation-home.ts,discussion-server.tsx,discussion.tsx,discussion-workspace.tsx,navigation.tsx,workspace-picker.tsx,locale.ts,discussion.css}` and `services/live/conversation-threads.ts`; integrate buyer/research/draft native link panels at Task 1's owners. Create `tests/sales-skills-client.test.mjs`, `tests/e2e/sales-skills.spec.ts`, `playwright.sales-skills.config.ts`.

**Interfaces:** `SalesTasks.start(input: TaskInput, threadVersion: number): Promise<TaskRecord>`; `get(id)`, `events(id, after)`, `cancel(id, version)`; `SalesOutputs.get(id, revision?)`; `XverumClient.quoteSearch`, `quoteDetails`, `confirm`, `propose`, `apply` use generated contract types. All clients share existing `SessionScope` cancellation and `LiveClient` auth/version carriers.

- [ ] Red browser tests: template and equivalent typed request reach same skill; thread A/B drafts remain separate; save+reload reopens output; uncertain send retries stable key; project switch aborts old requests; viewer cannot edit/confirm. Follow enrichment approvals and apply only checked fields. Assert native full-screen links preserve project scope and Back/Forward do not bypass dirty-draft guards.
- [ ] Run `node --test tests/sales-skills-client.test.mjs` and `pnpm exec playwright test --config playwright.sales-skills.config.ts` against isolated fixtures, confirming intended failures.
- [ ] Extend existing route parser, not a second shell. Keep `/app/discussions/s/:id`, `/app/overview` and old template routes; add `/app/documents` and output revision view under it. Show template catalogue, missing-input prompts, chosen skill, action/cost review, task progress and Results/Sources/Decisions. Persist unsent text/selection in scoped memory across route navigation; acknowledge server-saved messages explicitly. No sensitive browser local storage. Offer explicit import for old device-only threads, never auto-upload them.
- [ ] Add rename/pin/archive/search/resume and linked new-discussion actions. Saving shared records from private discussions shows audience. Integrate project-assigned connection status and field-level enrichment review. Keep inaccessible providers disabled with meaningful recovery. Reuse attachments and approved source selection.
- [ ] Run browser checks at 390/768/1440 widths and 200% zoom, keyboard/focus/error announcements, en/zh-HK and dangerous Markdown payloads. Verify workspace feature disable restores prior navigation while authorised outputs remain recoverable. Run `pnpm exec tsc --noEmit`, `pnpm lint`, `pnpm build`; build checks do not count as browser/live acceptance.
- [ ] Review/checkpoint the approved mockup direction with simplified labels per current AGENTS.md.

### Task 14: Enforce retention, revocation and cross-surface recovery

**Files:** Create `API/services/sales_retention.py`; modify task/output/connection services and exact existing retention owner from Task 1; extend `tests/e2e/sales-skills.spec.ts`. Tests `PT/test_sales_retention_db.py`, `test_sales_privacy_db.py`.

**Interfaces:** `invalidate_source(session, scope, source_id: str, reason: str) -> int`; `purge_sales_content(session, scope, target_id: UUID) -> PurgeReceipt`; `revalidate_task_access(session, scope, task_id: UUID) -> TaskRecord`. Define content-free `PurgeReceipt(affected_ids, completed_at)` in contracts.

- [ ] Red tests delete a source used by two tasks and an exported output; all derived retrieval/search/export paths reject it. Revoke thread share between step claim/result read; revoke connection during queued work; stale cache cannot revive access. Confirm no source bodies survive in summaries, receipts, logs, full-text indexes or report exports under system control.
- [ ] Run both Python tests for expected failures.
- [ ] Implement dependency invalidation before content reads and dispatch, then bounded purge jobs with tombstones/audit metadata only. Persist user notes/output content only under the existing workspace retention policy; project source restrictions take precedence. Existing downloaded files outside BuyerOS cannot be remotely erased and are not counted as system-controlled purge. Drive remains excluded from durable skill context throughout.
- [ ] Run privacy/retention tests and browser sign-out/scope-change/reload cases. Assert previous approved revisions become stale after material context changes, with no silent re-execution.
- [ ] Review/checkpoint all data surfaces, including caches and shared backlinks.

### Task 15: Verify complete delivery and prepare bounded activation

**Files:** Update `docs/buyeros/GUIDED_SALES_ACCEPTANCE.md`, `docs/buyeros/runbooks/xverum.md`, `.github/workflows/buyeros-ci.yml`; create `services/api/tools/run_sales_isolated.py` and `docs/buyeros/runbooks/guided-sales-release.md`.

**Interfaces:** Runner accepts only explicit disposable-resource identity and owned fixture endpoints, emits per-case PASS/FAIL/BLOCKED/NOT_RUN with SHA and fixture/live classification. Release receipt records source/artifact identity, account/connection references without secrets, policy/tariff versions, permitted tool scope, maximum spend, rollback and outstanding blockers.

- [ ] Extend the existing isolated runner to apply migrations, seed two tenants/roles and run core plus Xverum fixture journeys. Refuse inherited production DSNs or live provider credentials. Wire CI to isolated nonbillable suites and generated-contract checks; no provider activation in CI.
- [ ] Run all focused tests once, existing affected native regressions, TypeScript/lint/build, and the browser suite on the final candidate. Test upgrade from 0059, populated downgrade refusal and non-destructive feature rollback. Fix failures and rerun only affected checks until clean; preserve receipts.
- [ ] Record acceptance for every skill and each spec requirement. Output count/latency/correction/unresolved-failure/cost telemetry contains identifiers and aggregates, not conversation text or personal payloads. No invented success thresholds.
- [ ] Prepare, but do not execute, a separately authorised live acceptance: verified SaaS OAuth ownership/refresh/revocation, permitted data handling, real model registration/policy/tariff, approved prospect/recipient scope and exact maximum credits/currency. Live test must prove search → identity selection → detail enrichment → reviewed native save → saved research/draft output and reconnect recovery. If any prerequisite is absent mark live acceptance BLOCKED and phase incomplete.
- [ ] Keep `NEXT_PUBLIC_CONVERSATION_HOME` behaviour intact. Add `BUYEROS_SALES_SKILLS_ENABLED=false` server capability plus per-workspace opt-in, returned to the UI by capability reads; no new public environment flag is needed. Default provider/model registrations stay unselected. Prepare release/rollback instructions; disabling dispatch must not remove authorised output recovery routes. Production flags, credentials, migrations and deploy require their own exact-target approval.
- [ ] Whole-branch review after all task reviews. Provide final change summary, verified environments, remaining blockers and scoped Git/release approval request only if those actions are requested. No release-ready claim while mandatory live checks are BLOCKED or NOT_RUN.

## Plan self-review and execution handoff

Self-review completed against the approved spec: source baseline corrected to current main; existing thread/Drive implementations reused; all catalogue groups map to Tasks 2/11/12; paid discovery ambiguity maps to Task 8; durable saves/recovery/privacy map to Tasks 3–6/9/14; native UI/preservation maps to Task 13; source pinning, exact review checkpoints and isolated/live evidence map to Tasks 1/15. Five Review Focus cases have named owning tests. Contract/type names above are shared rather than independently redefined by tasks.

The accepted design's broad persistence permission does not remove source-specific restrictions. This plan deliberately preserves the current Drive exclusion. Xverum live OAuth/account compatibility and model registration are operational activation prerequisites, not reasons to fabricate a working integration or silently widen access.

Recommended execution: **Subagent-driven**, because task, credit-ledger, ACL and model boundaries deserve independent review before dependent tasks proceed. Native execution in this chat is the lower-overhead alternative with whole-branch review at the end. User reviews this plan and selects the method before implementation. Design/plan documents remain uncommitted under the user's Git boundary.
