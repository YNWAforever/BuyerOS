# BuyerOS Cloudflare Job Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in the current session. The user selected that execution method and did not authorize agents. Steps use checkboxes for tracking; every checkbox is currently incomplete.

**Goal:** Replace continuous Celery/Valkey/Render job hosting with Cloudflare Queues/Workflows and resumable Python steps, preserving BuyerOS domain and financial behavior.

**Architecture:** One TypeScript Worker controls scheduling and durable handoff; the existing FastAPI service owns bounded Python execution and all PostgreSQL transactions. Cloudflare persists opaque orchestration metadata; outbox, step receipts, membership, policy, provider operations, money and checkpoints remain authoritative in Neon. Native Python computation remains on Vercel and requires hosted feasibility proof.

**Tech Stack:** Existing Vinext/React/TypeScript/pnpm; FastAPI/SQLAlchemy/Alembic/Python>=3.12; Neon/Auth0/R2; proposed Cloudflare Queues/Workflows using the repository's pinned Wrangler toolchain.

**Spec:** [2026-10-01-cloudflare-job-migration-design.md](../specs/2026-10-01-cloudflare-job-migration-design.md).

**Status:** Local implementation approved by direct user reply, 2026-10-01 HK. CF00 local, CF01 and CF02 completed; hosted/paid/production activation is not approved. Initial planning snapshot: Source `aed7a7eb2b7370c10cd7a41306eecf09d378ad42`, initial diff clean. Implementation/architecture change and external activation are not approved by requesting this plan. All future tests and commands below are **NOT RUN**; expected results describe acceptance, not evidence.

## Global constraints

- Preserve one FastAPI domain API and one SQLAlchemy/Alembic migration owner. Proposed exception to the earlier Celery/Valkey/Render job requirement needs explicit approval.
- In-memory browser access tokens; server-verified identity and current memberships/RLS; actor-bound snapshots and exact-context approval.
- Money remains `NUMERIC(20,6)` / Decimal; HTTP money is a six-decimal string. Unknown provider acceptance retains holds and reconciles; retry/lease expiry cannot release or resubmit it.
- Research: target<=100, rounds<=3, cumulative queries<=12, raw results<=300, page attempts<=200, decoded page<=2097152 bytes, wall<=1800 seconds, model tokens<=100000, provider concurrency<=4. Restart does not reset counters/deadline.
- Bulk: synchronous<=100; asynchronous101..1000, chunk50. One active execution step globally initially; per-provider concurrency1.
- Public API pagination limit1..100/default20; snapshots<=1000 IDs/900-second expiry; authorization is rechecked on consumption.
- Mailbox/CRM/sending stay disabled; delivery returns `403 DELIVERY_DISABLED` even for approved drafts.
- No production/shared DB fixtures, synthetic live rows, hidden skips, weakened regression tests, paid providers, resource creation, migrations or deployment without the applicable specific authorization.
- No baseline reset, unrelated edits, automatic merge or delegation. Suggested commits are recorded after each task; follow current repository/user commit authority and explicitly stage files.
- Before schema changes, rerun `alembic heads` and allocate the actual next revision. `0034` is only the current candidate after `0033_api_rate_windows`; never overwrite a numbered revision.

## Review focus

1. Same-generation duplicate step requests must not submit one provider operation twice — CF02/CF04/CF06.
2. Worker/API restarts, queue expiry and Workflow retention cannot erase accepted jobs or money holds — CF05/CF06.
3. Removed membership, changed offer/ICP/policy or late scope results cannot authorize/expose old work — CF03/CF04/CF07.
4. Queue concurrency1 does not limit Workflow execution; DB permits must enforce the pilot bound — CF02/CF05/CF07.
5. Python packaging, PDF isolation and both Vercel hops must fit actual limits; low Cloudflare base cost must include Neon/Vercel effects — CF00/CF07/CF08.

## File structure and ownership

| Path | Responsibility / proposed change |
|---|---|
| `services/api/buyeros_api/execution/` (new) | Celery-independent engine, dispatcher, domain runners, graph/checkpoints and bounded step orchestrator. API owns these; worker package imports/reexports them. |
| `services/api/buyeros_api/db/worker_execution.py` (new) | Runtime selector, step receipts and nonce ORM models; existing outbox/lease/provider/money models reused. |
| `services/api/buyeros_api/services/worker_execution.py` (new) | Transactional claims, DB execution permits, fencing, receipts, recovery and status. |
| `services/api/buyeros_api/api/worker_auth.py`, `worker_schemas.py`, `routes/worker_internal.py` (new) | Machine auth, strict internal protocol and the five internal routes; no staff authorization bypass. |
| `services/api/buyeros_api/api/app.py`, `settings.py`, `db/outbox.py` | Registration, server-only settings and backend/epoch claim metadata. |
| `app/v1/[...path]/route.ts` | Transport-only signed header allowlist for exact internal paths. |
| `services/api/pyproject.toml`, `uv.lock` | Sole dependency installation for extracted native Python execution. No circular dependency on `buyeros-worker`. |
| `services/worker/buyeros_worker/*.py`, `handlers/*.py` | Existing import-compatible Celery adapters and selector guards; no copied second implementation. |
| `services/cloudflare-jobs/wrangler.jsonc`, `tsconfig.json`, `src/{index,protocol,api-client,dispatcher,queue,workflow}.ts` (new) | Isolated strict runtime types, bindings, scheduled publication, Queue→Workflow handoff, signed API calls and safe orchestration. |
| `services/cloudflare-jobs/src/worker-api.generated.ts`, `worker-configuration.d.ts` (new) | Strict generated internal OpenAPI and Wrangler binding types. |
| `scripts/generate-worker-api-types.mjs`, `services/api/tools/export_worker_openapi.py` (new) | Reproducible internal contract generation, with check mode. |
| `services/api/tests/test_cloudflare_*.py`, `services/worker/tests/test_transport_independence.py`, `services/cloudflare-jobs/tests/` (new) | Meaningful bounded-execution, security, queue, concurrency and recovery regressions. |
| `playwright.cloudflare.config.ts`, `tests/e2e/cloudflare-journey.spec.ts`, local harness files (new) | Real locally owned DB/Worker/API path with fictional identity/providers; no seeded replacement for staff-created journey. |
| `vercel.json`, `.github/workflows/buyeros-ci.yml`, `package.json`, `pnpm-lock.yaml`, root `tsconfig.json`, `eslint.config.mjs` | Runtime/package proof, separate Worker typecheck/lint, additional required gates and pinned local tooling; retain existing public routing and tests. |
| `docs/buyeros/runbooks/cloudflare-worker-setup.md`, `remaining/TASKS.json`, `REMAINING_DEVELOPMENT_STATUS.md`, T30 handoff (proposed updates) | Exact setup/cutover/rollback and evidence ledger. Preserve historical deployment/test/approval facts. |

### Extraction map

Keep basenames and move ownership, retaining thin legacy import wrappers. CF01 owns `engine.py`, `leases.py`, `registry.py`, `run_emitter.py`, `run_lifecycle.py`, `dispatcher.py`, `handlers/bulk_mutate.py`, `handlers/fetch_evidence.py`, `handlers/capability_blocked.py` and new `domain_executor.py`/`config.py`. CF03 owns `document_runner.py`, `fetch_runner.py`, `pdf_parser.py`, `pdf_parser_child.py`, `handlers/retention.py`, `handlers/draft_generate.py`. CF04 owns `external_runner.py`, `discovery_runner.py`, `fit_execution.py`, `fit_runner.py`, `research_graph.py`, `checkpoints.py`, `handlers/contact_submit.py`, `handlers/reconcile.py`. Source paths are currently under `services/worker/buyeros_worker/`; targets are under `services/api/buyeros_api/execution/`. Keep Celery `app.py`, signals, broker publisher, CLI and transport wrappers in the legacy worker package. Update parser child module invocation to the extracted API package; do not remove subprocess isolation.

## Execution conventions

Commands are proposed for Linux CI from repo root unless `cwd` is given. Windows equivalents use the selected project's `.venv/Scripts/python.exe`, `pnpm.cmd`, and existing owned test setup. `uv run --frozen --project services/api ...` requires that task's reviewed lock updates first. Before any destructive fixture setup, inspect its script and prove loopback/owned disposable DB names; unset production credentials and retain strict integration mode. Hosted probes require an explicitly approved, protected preview with a disposable DB; never reuse the production Neon branch.

Every implemented task ends with its focused red/green cycle, existing affected integration tests, generated-contract checks, diff inspection, and a checkpoint listing exact commands/exit codes/pass-fail-error-skip counts, environment, migrations/rollback, risks and next eligible task. An external skip is not an integration pass; required local gates must have zero skips. Future commit messages below are suggestions, not execution evidence.

### Common check commands (proposed, NOT RUN for this migration)

After the owned disposable DB setup, retain `BUYEROS_STRICT_INTEGRATION=1` and that harness's `BUYEROS_TEST_DATABASE_URL`. Never copy a production DSN into these commands. Create the owned `artifacts/cloudflare` output directory before JUnit writes.

```text
uv run --frozen --project services/api pytest services/api/tests -q --junitxml=artifacts/cloudflare/api-tests.xml
uv run --frozen --project services/api python scripts/check-required-tests.py --junit artifacts/cloudflare/api-tests.xml
uv run --frozen --project services/worker pytest services/worker/tests -q --junitxml=artifacts/cloudflare/worker-tests.xml
uv run --frozen --project services/api python scripts/check-required-tests.py --junit artifacts/cloudflare/worker-tests.xml
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
node scripts/generate-worker-api-types.mjs --check
node --test tests/api-types-generation.test.mjs tests/vercel-services.test.mjs tests/worker-gateway.test.mjs
node tests/domain-checks.mjs
node tests/live-adapter-checks.mjs
node tests/live-auth-checks.mjs
pnpm exec tsc --noEmit
pnpm exec tsc --noEmit --project services/cloudflare-jobs/tsconfig.json
pnpm lint
pnpm build
node scripts/run-vercel.mjs build
node --test tests/vercel-render.test.mjs
pnpm exec vitest run --config services/cloudflare-jobs/vitest.config.ts
pnpm exec playwright test --config playwright.cloudflare.config.ts --reporter=line,junit
git diff --check
```

Additional existing browser commands are retained verbatim from `.github/workflows/buyeros-ci.yml`: `playwright.mvp-research.config.ts`, `playwright.workbench.config.ts`, `playwright.buyer.config.ts`, `playwright.buyer-management.config.ts`, `playwright.mvp.config.ts` and `playwright.live-zoom.config.ts` with their existing named specs and required count gates. New test/type/harness paths in this catalog are introduced by the owning CF task, not assumed to exist now. Expected acceptance: all selected tests pass, zero required failures/errors/skips, generated files current, no weakened public78-operation check. Record actual counts rather than copying baseline577/174 into new evidence.

---

### CF00: Prove native execution feasibility and prepare the protected preview probe

**Predecessor:** reviewed architecture/implementation scope. **Files:** create `services/api/tools/probe_worker_runtime.py`, `services/api/tests/test_cloudflare_runtime_probe.py`, `tests/deployment/cloudflare-python-runtime.test.mjs`, `artifacts/cloudflare/CF00-runtime-matrix.json`; inspect API/worker pyproject locks, `vercel.json`, parser and checkpoints.

**Interfaces:** produces `probe_runtime(output: Path) -> RuntimeProbeReport` with package/import results, child-parser isolation/timeout, PG checkpoint/role results, package size, cold/warm CPU/memory/duration and both-hop deadlines. Each record includes `environment: local|preview`, source SHA and `verified|failed|not_run`. No probe is a customer/job executor.

- [x] Add `test_probe_rejects_shared_or_production_database` and `test_probe_requires_native_parser_and_checkpoint_proof`; assert owned disposable identity, no inherited parser secrets, existing 8-second parser limit and explicit hosted `not_run`.
- [x] Run the tests against missing probe; observe the actual failure. Command: `uv run --frozen --project services/api pytest services/api/tests/test_cloudflare_runtime_probe.py -q`. Create that named test file in this step; do not fabricate a pre-run result.
- [x] Implement the disposable Linux/native package probe and prepare a protected preview script with reviewed sample PDFs/checkpoint inputs. Inspect bundle/import behavior under frozen no-dev builds. Record account-specific duration/region/billing/deployment-protection evidence as missing until inspected.
- [x] Run focused tests, `node --test tests/deployment/cloudflare-python-runtime.test.mjs`, and `uv run --frozen --project services/worker python services/api/tools/probe_worker_runtime.py --output artifacts/cloudflare/CF00-runtime-matrix.json` against the owned fixture DSN supplied through `BUYEROS_TEST_DATABASE_URL`. The existing worker environment provides native packages for this local probe; it is not proof of the later API deployment bundle. Hosted package/parser/DB/90-second-both-hop check remains gated by preview authorization and must pass before CF08 activation. A known native incompatibility requires a revised design; independent local tasks can continue while hosted access is missing.
- [x] Checkpoint actual evidence and proposed `test: probe bounded native Python worker execution` commit. No production probe, paid API or schema change.

### CF01: Extract one transport-independent Python execution owner

**Predecessor:** CF00 local feasibility. **Files:** CF01 extraction map, create `services/api/buyeros_api/api/worker_schemas.py` with strict `JobEnvelope`/`ClaimBatch`; modify API/worker dependencies and locks, `services/worker/buyeros_worker/tasks.py` and CLI imports. Tests: `services/worker/tests/test_transport_independence.py`, existing `test_tasks.py`, `test_dispatcher.py`, bulk tests.

**Interfaces:** `async run_domain_intent(engine, workspace_id: UUID, outbox_id: UUID, generation: int) -> str`; `async claim_cycle(engine, *, backend: str, epoch: int, max_total: int=10, time_budget_seconds: float=10) -> ClaimBatch` (selector enforcement added CF02). `ClaimBatch` is a strict model `{items: list[JobEnvelope], next_cursor: UUID|None, runtime_epoch: int}`; return IDs only. API execution imports no Celery, Redis or `buyeros_worker`. Existing `execute_intent_sync(...)` becomes a compatibility wrapper; async FastAPI never nests `asyncio.run`.

- [x] Add tests asserting a clean API-process import creates no Celery app/broker connection; run a real disposable bulk intent through the extracted async function and legacy Celery wrapper and compare durable rows/terminal state. Assert stale/terminal/missing-tenant paths perform no write.
- [x] Run `uv run --frozen --project services/worker pytest services/worker/tests/test_transport_independence.py -q` and observe the new API import/async entrypoint failures.
- [x] Extract the mapped modules, install shared dependencies from API only, preserve transaction ownership and old import paths as thin wrappers. Keep unextracted document/provider branches in the legacy adapter until CF03/CF04; API must report unsupported paths without pretending execution succeeded.
- [x] Run focused tests plus `test_tasks.py`, `test_dispatcher.py`, `test_bulk_mutate_handler.py`; frozen no-dev API import and legacy Celery help must pass. Inspect any changed monkeypatch targets to prove assertions still test the authoritative implementation.
- [x] Checkpoint ownership/package evidence and proposed `refactor: share async BuyerOS execution behind Celery adapters` commit. No migration/public operation changes.

### CF02: Add fenced step ownership and the authenticated internal bridge

**Predecessor:** CF01. **Files:** new ORM/service/auth/schema/internal-route files in the ownership map; modify `db/outbox.py`, `api/app.py`, `settings.py`, both claimers and app gateway; allocate next Alembic revision. Tests: `services/api/tests/test_cloudflare_bridge_db.py`, `test_cloudflare_runtime_control_db.py`, `tests/worker-gateway.test.mjs`. Create generated internal OpenAPI/type scripts/artifacts here.

**Interfaces:** strict `JobEnvelope`/`StepOutcome` from spec; `async claim_execution_step(session, envelope: JobEnvelope, step_key: str, now: datetime) -> StepClaim`; `async execute_step(engine, envelope: JobEnvelope, step_key: str) -> StepOutcome`; `async read_step_status(engine, envelope, step_key) -> StepOutcome`. `StepClaim` has `state: claimed|busy|cached|stale`, `owner: UUID|None`, `expires_at: datetime|None`, `outcome: StepOutcome|None`. `verify_worker_request(method, path, raw_body, headers, now) -> MachinePrincipal` returns verified `key_id`/`nonce`, no customer roles. One DB permit globally; never a tenant query without SET LOCAL.

Extend CF01's existing `worker_schemas.py`; do not recreate it. Export the internal schema to `services/api/contracts/worker.openapi.json` and generate `services/cloudflare-jobs/src/worker-api.generated.ts`. `InternalOperation`, `InternalRequest<K>` and `InternalResponse<K>` in later tasks are aliases of those generated five operations, not hand-maintained duplicate types.

- [x] Add named tests: `test_user_token_cannot_call_internal_worker`, `test_signature_binds_raw_body_path_timestamp_and_nonce`, `test_same_generation_has_one_execution_owner`, `test_selector_rejects_other_backend_and_old_epoch`, `test_internal_headers_forward_only_on_allowlisted_paths`. Assert nonce replay409, invalid machine auth401, unknown fields422, body>8192 rejected, no customer reads before authentication, and one durable bulk mutation under 20 simultaneous same-step requests.
- [x] Observe red with `uv run --frozen --project services/api pytest services/api/tests/test_cloudflare_bridge_db.py services/api/tests/test_cloudflare_runtime_control_db.py -q` and `node --test tests/worker-gateway.test.mjs`.
- [x] Inspect heads, allocate additive revision, implement control/receipts/nonces, default disabled and consistent Celery/CF guards. Register the five POST operations. Implement raw signed gateway forwarding and closed status-code enums. Generate internal schemas/types; keep all 78 public operations distinct from these five internal operations.
- [x] Run focused security/concurrency tests on owned PostgreSQL; empty upgrade/downgrade/re-upgrade, populated downgrade refusal, non-owner/NOBYPASSRLS and cross-project/tenant negatives. Run `node scripts/generate-worker-api-types.mjs --check`, existing route/public type checks and gateway tests. Record actual revision, grants and rollback output; no production migration.
- [x] Checkpoint and proposed `feat: fence machine-authenticated BuyerOS execution steps` commit.

### CF03: Complete bounded bulk, document, draft and retention slices

**Predecessor:** CF02. **Files:** CF03 extraction map, `execution/step_runner.py`, `execution/domain_executor.py`, API dependency locks; existing worker wrappers. Tests: `services/api/tests/test_cloudflare_local_steps_db.py`; existing PDF/document/fetch/bulk/draft/retention tests.

**Interfaces:** `async execute_local_step(engine, envelope: JobEnvelope, step_key: str, *, deadline: datetime) -> StepOutcome`. Stable server-selected step keys: bulk chunk (50 rows), document parse/delete, one permitted fetch, one grounded draft revision or retention page (<=50 items). Progress/outcome and successor step commit together; arbitrary event/body/URL instructions are never accepted from Cloudflare.

- [ ] Add `test_bulk_restart_resumes_next_chunk_without_repeat`, `test_pdf_child_keeps_sanitized_env_and_eight_second_timeout`, `test_document_delete_during_parse_blocks_exposure`, `test_member_removal_blocks_draft_after_enqueue`, `test_retention_runtime_role_membership_is_verified`. Assert 101/1000-row partial results survive restarts and no synthetic text/contacts appear on live failure.
- [ ] Observe red with `uv run --frozen --project services/api pytest services/api/tests/test_cloudflare_local_steps_db.py -q` under strict disposable integration.
- [ ] Extract native runners/handlers into API ownership and implement one bounded unit per call; preserve SSRF, parser subprocess and R2 capability checks. Replace the retention helper's login-name assumption with actual verified worker-role membership and tenant transactions. No fixture provider factory outside explicit test mode.
- [ ] Run focused tests plus existing document/parser/retention/bulk/draft regressions and API packaging import. Assert <=60-second units, safe expired/incomplete step state, exact receipts and current authorization; object mocks are fixture proof only.
- [ ] Checkpoint and proposed `feat: execute bounded BuyerOS local jobs through the shared engine` commit. Paid/R2 gates stay disabled.

### CF04: Make research, fit, contact and reconciliation resumable without duplicate spend

**Predecessor:** CF03. **Files:** CF04 extraction map, shared `step_runner.py`, existing provider and budget services as necessary, API locks. Tests: `services/api/tests/test_cloudflare_provider_steps_db.py`; existing `services/worker/tests/test_external_runner_db.py`, `test_discovery_limits.py`, `test_discovery_runner_db.py`, crash matrix and contact/fit tests.

**Interfaces:** `async execute_provider_step(engine, envelope, step_key, *, deadline: datetime) -> StepOutcome`. Unit: one search query, permitted page attempt, canonicalization batch<=50, one fit buyer (split into graph nodes when needed), one contact operation or one read-only reconciliation action. The backend supplies stable provider intent identity; no fresh identity from a retry/Workflow ID. Existing PG graph thread/buyer/attempt keys remain compatible.

- [ ] Add `test_accepted_then_lost_response_keeps_hold_and_uses_status_only`, `test_new_generation_cannot_resubmit_unknown_operation`, `test_restart_shares_twelve_query_two_hundred_page_and_original_deadline_limits`, `test_changed_icp_membership_or_policy_blocks_next_provider_step`, `test_fit_checkpoint_resumes_one_buyer_and_stops_for_review`. Use Decimal ledger assertions and actual owned DB receipts; fictional provider counters distinguish submit/status calls.
- [ ] Observe red with `uv run --frozen --project services/api pytest services/api/tests/test_cloudflare_provider_steps_db.py -q`; record failure before implementation.
- [ ] Split loops at persisted boundaries, keep the prepare→external I/O→finalize transaction separation and stable intent keys. Mark potentially accepted operations before egress; on uncertainty return `reconcile` without release. Preserve current unconfigured production adapters and independent paid-admission/dispatch gates.
- [ ] Run new tests plus all existing provider/discovery/fit/contact/money/limit regressions. Exercise n and n+1 for every cumulative ceiling, stale generation, changed price, cancellation, duplicate callback and zero network while a tenant row lock is held. Show one reservation/settlement and no duplicate external submit under restart/concurrency.
- [ ] Checkpoint and proposed `feat: checkpoint bounded research and provider execution without blind retries` commit. No live provider acceptance or price proof is inferred.

### CF05: Add the real Cloudflare scheduling, Queue and Workflow controller

**Predecessor:** CF04 (protocol can be developed locally after CF02). **Files:** create Cloudflare service source/config/binding types; modify root tooling/lock to reuse pinned Wrangler; tests `services/cloudflare-jobs/tests/{protocol,dispatcher,queue,workflow}.test.ts` and `vitest.config.ts`. Do not deploy or create queues during local development.

**Interfaces:** `scheduled(event, env, ctx)`, `queue(batch: MessageBatch<JobEnvelope|ProbeEnvelope>, env, ctx)`, `BuyerOSJobWorkflow.run(event, step)`; `callWorkerApi<K extends InternalOperation>(env, operation: K, body: InternalRequest<K>) -> Promise<InternalResponse<K>>`. Strict validation occurs at runtime despite generated TS. `dispatchTick(env) -> {claimed:number,published:number}` persists fairness via API; no in-memory tenant cursor authority.

- [ ] Add tests rejecting extra payload fields/URLs, proving 10-ID/10-second claim bounds, recovery after publish-before-receipt crash, deterministic Workflow identity, duplicate instance inspection without restart, and HTTP timeout followed by committed-status read before any repeat step. Assert Queue ACK only after Workflow creation/existence is verified and no ACK-as-business-completion.
- [ ] Observe red using `pnpm exec vitest run --config services/cloudflare-jobs/vitest.config.ts` with the Cloudflare Workers Vitest integration; choose/pin a compatible test-pool release from official package metadata without unrelated upgrades. The test harness must exercise actual local queue/Workflow behavior as well as unit stubs.
- [ ] Implement scheduled/Queue/Workflow handlers and HMAC client; default disabled, no public fetch route. Bind one active Queue and one Workflow; DLQ quarantine. Configure batch1/concurrency1/retries5 and spec budgets. App/API/DB permits enforce execution concurrency; Queue settings cannot substitute for them. Define `ProbeEnvelope` as `{v:1, kind:'probe', probe_id:UUID, runtime_epoch:number}`; the probe writes an operational receipt, not a customer intent. Validate it as a distinct union branch. Treat busy permits as safe bounded waits, independently from transport retry exhaustion.
- [ ] Generate Worker binding types with the pinned Wrangler into `worker-configuration.d.ts`, add an isolated strict `services/cloudflare-jobs/tsconfig.json`, exclude that service from the frontend TS compilation and add its own mandatory TS/lint gate. Scope any ESLint environment changes to the Worker service; retain frontend strictness.
- [ ] Run Worker unit and actual local Queue→Workflow→API→owned PG tests, generated binding/types and `pnpm exec wrangler deploy --dry-run --config services/cloudflare-jobs/wrangler.jsonc --outdir .sites-runtime/cloudflare-dry-run`. Verify no production secrets/network activation, compatible pinned schema, worker source size, machine origin allowlist and failure-safe dispatch-off behavior. If local platform features are unsupported, record the exact limitation; mocks are not platform proof.
- [ ] Checkpoint and proposed `feat: orchestrate BuyerOS jobs with Cloudflare Queues and Workflows` commit.

### CF06: Prove restart recovery, honest readiness, deletion and rollback

**Predecessor:** CF05. **Files:** `services/api/buyeros_api/services/worker_execution.py`, existing `api/routes/health.py`, `db/worker.py`, `execution/handlers/retention.py`, controller recovery/probe logic; new `services/api/tests/test_cloudflare_recovery_db.py`, `tests/integration/cloudflare-recovery.test.ts`; create `docs/buyeros/runbooks/cloudflare-worker-setup.md`.

**Interfaces:** `async recover_execution(engine, *, now: datetime, limit: int=10) -> RecoveryReport`; real Queue→Workflow→API probe receipt updates readiness only after durable receipt. `set_execution_runtime(expected_epoch: int, backend: str, enabled: bool, reason: str) -> RuntimeControl` is a reviewed operational tool, not a staff route; epoch only increases.

- [ ] Add failure-injection tests at customer commit/publish, queue accept/receipt, Workflow create/ACK, DB step claim/egress/finalize and provider accept/response. Add `test_queue_or_workflow_retention_does_not_reexecute_terminal_step`, `test_environment_flag_cannot_make_readiness_ready`, `test_celery_cloudflare_overlap_has_one_owner`, `test_populated_rollback_preserves_unknown_holds`, `test_restore_then_deletion_replay_keeps_reads_closed`.
- [ ] Observe red with strict DB recovery tests and `pnpm exec vitest run --config services/cloudflare-jobs/vitest.config.ts tests/integration/cloudflare-recovery.test.ts` after adding that path to the explicit config include.
- [ ] Implement bounded orphan/reconcile/deletion scheduling and global probe receipts; DB-backed alerts at 180-second missing receipt/300-second oldest work. Preserve minimal IDs only in Workflow state. Write exact pause/drain/fence/roll-forward instructions with no queue purge and no promise of an already provisioned Celery fallback.
- [ ] Run process kill/restart with actual local components and DB/ledger conservation checks. Simulate expired platform state, stale epoch, duplicate same-generation requests, removed membership, key rotation, retention and backup restore. Exercise disabled→CF→paused and compatible CF→Celery **only in disposable tests**; prove unsupported old builds are excluded.
- [ ] Checkpoint and proposed `test: prove Cloudflare job recovery readiness and guarded rollback` commit.

### CF07: Verify the staff journey, pagination and measured operating conditions

**Predecessor:** CF06. **Files:** new `playwright.cloudflare.config.ts`, `tests/e2e/cloudflare-journey.spec.ts`, `tests/e2e/fixtures/cloudflare-stack.ts`; existing CI fixture startup/teardown and `.github/workflows/buyeros-ci.yml`; create `scripts/run-cloudflare-acceptance.mjs`, scoped evidence/screenshots. Reuse existing UI code and fix only proven migration regressions.

**Interfaces:** harness starts owned PostgreSQL, local real Cloudflare runtime, API and existing UI; fake OIDC/provider seams are explicit. `runCloudflareAcceptance(options: {mode:'local'|'preview', baseUrl:string, evidenceDir:string}) -> AcceptanceReport` rejects shared DB/prod mutation targets. It writes source/environment/command/count metadata and never fabricates a hosted pass.

- [ ] Add four initial journey cases (en/zh-HK ×390px/1280px) that create/edit offers, approve ICP, research, review/list/assign/bulk, optional fixture lookup, grounded draft, exact approval, export, manual outcome and refresh through the UI. Add scope races, viewer/reviewer negatives, partial provider failure, restart during execution and a real second buyer/result page. Assert approved delivery remains403.
- [ ] Run `pnpm exec playwright test --config playwright.cloudflare.config.ts --reporter=line,junit` and observe the missing transport/harness or journey failure before wiring it. Inspect fixture reproduction scripts and owned DB checks before running.
- [ ] Integrate the real local stack and required no-skip gates without replacing existing Celery acceptance. Add a repeated-concurrency condition (10 queued jobs, one active step), 100-workspace fairness across cold starts and 10k-row read pagination; measure P50/P95, CPU/memory, connections, queue age and receipt age. Include idle minute polling and Neon-autosuspend implications in the cost worksheet.
- [ ] Run all required API/worker suites, existing browser continuity/zoom/pagination suites, public78/internal5 contract/type checks, TS/lint/both builds, Worker platform tests and dry-run. Worker TS command: `pnpm exec tsc --noEmit --project services/cloudflare-jobs/tsconfig.json`. Zero required DB/transport skips; inspect screenshots at both widths/locales. Actual Auth0/preview/paid-provider results are separate, authorization-gated evidence. P95<=120 seconds for first step is an acceptance target under the named ten-job fixture condition with <=1-second non-provider work per step; record provider latency separately, not as the same benchmark.
- [ ] Checkpoint exact outputs/counts, UI screenshot paths, fixture/live distinctions and proposed `test: verify Cloudflare BuyerOS staff continuity and operating bounds` commit.

### CF08: Prepare the release candidate and present the exact activation decision

**Predecessor:** CF07 for local RC; CF00 protected hosted proof also required for activation. **Files:** prepared Wrangler/Vercel configs (both app/API budget mechanism validated against their actual schemas), setup runbook, internal/public operation coverage, audit closure, existing T30 handoff/status/TASKS, sanitized source-bound test/configuration/rollback artifacts.

**Interfaces:** `ActivationProposal` names reviewed source SHA, account/plan, resources, origin/budgets, DB migration/role, secrets source map, initial allowed capability scope, expected usage, locality/privacy review and rollback. It records requested approvals separately from received approvals.

- [ ] Validate config/schema with execution disabled, public routes/binding unchanged and no customer/provider secrets in bundles. Prepare exact migration/role/config diffs and protected preview probes; do not publish them to obtain approval.
- [ ] Inspect all changed source and retained test evidence; update A01–A18 with current proof, public70+8/internal5 coverage and remaining source/activation blockers. Migration head/upgrade/populated refusal and paused-runtime rollback evidence must be source-bound. No deployment SHA is emitted without platform proof.
- [ ] Present the architecture change for review if not already approved. Once local work is complete, present the **single exact activation change** with account/plan, monthly usage estimate, private resource names, verified Vercel budgets, approved migration/role/secret placement, enabled job scope and rollback. Missing provider/policy/R2/pilot approval remains independent; do not include it implicitly.
- [ ] Only after that specific activation authorization: deploy compatible API off, migrate the approved target, configure secrets/bindings, deploy Worker off, prove protected hosted fixture boundaries, stop legacy claimers, inspect in-flight operations, change epoch/selector and enable the approved non-delivery scope. Resource creation/preview tests may need a separate earlier exact authorization; do not count elapsed time as approval.
- [ ] Verify deployed source, real Queue/Workflow probe, disabled gates, authenticated staff continuity and cost/latency on the approved scope; report code implemented, fixture verified, hosted integration verified, externally blocked and deployed as separate facts. Prepare/push reviewable changes only under existing Git authority; no merge. Suggested commit: `docs: hand off guarded Cloudflare BuyerOS release evidence`.

## Plan self-review and current handoff

Reviewed against the design: runtime ownership, auth, schema, package direction, step state, duplicates/uncertainty, actor/policy races, counters, deletion, platform expiry, concurrency, costs, UI, contracts, rollback and external gates each map to CF00–CF08. Exact signatures/types are shared above. Review-focus tests map to their owning tasks; all commands for future files are marked NOT RUN.

Planning checks only: source/origin/diff inspected; native dependency/handler/proxy sources read through graph then targeted fallback; current Alembic head inspected offline. New migration/tests/runtime are not implemented, no cloud account configuration was inspected, and no resource was created. The execution registry links this proposal without changing completed T00–T30 results or historical owner approvals.

**Next eligible decision:** review this plan and its design, particularly bounded Python execution on Vercel, the Celery/Valkey exception, internal routes and one-minute queueing. After approval, start CF00 in this session; do not restart T00 or assume agent permission. The writing-plans skill requires review before implementation for this newly requested migration plan. Approval of the plan does not activate paid resources or production jobs.
