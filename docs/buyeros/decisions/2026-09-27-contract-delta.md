# Contract delta for the 2026-09-27 execution

This record reconciles the external implementation pack with current source at `f43a9d88b334c2c4029fa06fa71624ed52efe4a2`. It does not approve provider activation or change historical BO decision records.

## Current source and ownership

- FastAPI routes live under `services/api/buyeros_api/api/routes`; P13 already added buyer snapshot, update, review, and evidence handlers. Keep these routes and the existing `idempotency_records` ledger as the single domain API/write path.
- Alembic has one head, `0011_project_buyer_version`. Reserve the next revision when a task actually needs schema change. Do not reuse the plan's numbered filenames.
- SQLAlchemy models and Alembic own the domain schema. The Vinext/React client consumes generated OpenAPI types; its demo fixtures are not live API results.

## T00 checked-in delta

- The Project response schema allows `website` to be a URL or null because an unconfigured project currently has no website. The Project serializer explicitly emits `sender_identity: null` until configured. A real serializer payload is validated with Draft 2020-12 and negative required-field, enum, and type mutations.
- `services/generated/buyeros-api.ts` is generated from `contracts/openapi.proposed.yaml` with `scripts/generate-api-types.mjs --write`; `--check` detects drift. It is a contract type artifact, not proof that every route response currently conforms.
- ICP, buyer, evidence, and future operation responses still need task-owned strict response tests and truthful serializers. Do not add synthetic fields just to satisfy a schema.
- `remaining/API_OPERATION_STATUS.csv` distinguishes present handlers, live integration, contract verification, UI verification, and deployed proof for the 70 baseline operations plus three extensions.

## Deliberate limits

The T00 browser fixture uses a fake principal and a disposable PostgreSQL database under a non-owner API role. It proves only the isolated HTTP/database path. The current browser remains demo mode; actual Auth0 sign-in and the full staff journey are separate later tasks and external activation checks.

## T01 idempotency delta

Project mutation keys now bind operation, workspace/project target, the validated strong `If-Match` precondition, and body under serializer version 1. The existing ledger stores lifecycle status, resource ID, and JSONB `{http_status, version, data}` so retries return the first result. Body-only historical project records conflict rather than guessing their target. P13 buyer caller migration remains with its later task. No new table or migration was introduced.

## T02 ICP basis and validation delta

`0012_offer_basis_revision` is the next Alembic revision after one verified 0011 head. Project `offer_revision` starts at 1; historical ICP rows retain unknown NULL basis and cannot be approved without a newly saved successor. Save requires a current `basis_offer_revision`, allocates a number while locking the Project, validates nested schema, normalizes caller fact approval flags to false, and records a frozen idempotent response. The ICP content hash uses the existing `sha256:` prefix, now reflected in the OpenAPI pattern. Approval adds a required `expected_project_version`; T03 owns complete approval race and audit acceptance. No historical approval or content row is rewritten by the migration.

## T03 approval and read-status delta

ICPVersion adds derived `basis_status` (`current`, `stale`, `unknown`) and `is_current`; the immutable content/hash stays unchanged. Both Project and ICP version collections honor the contract's shared offset 0/limit 20 defaults and 1–100 limit, with stable SQL ordering. Approval writes one redacted audit event alongside pointer/version changes. The 0012 migration remains the single schema change through T03.

## T04 project-link and JWKS delta

Alembic 0013 adds same-project constraints after a read-only violation preflight; no legacy relationship is guessed or deleted. `list_memberships`, `fit_assessments`, and `buyer_snapshot_items` gain owner `project_id` columns backfilled from their existing parent rows. The API runtime role remains non-owner and NOBYPASSRLS. JWKS cache behavior gains a configurable hard stale limit of 3600 seconds; it never authorizes an unknown key during outage. Real Auth0 and any persisted-database migration remain separate activation evidence.

## T05 browser identity and scope delta

The frontend uses public Auth0 Authorization Code + PKCE and signed ID-token verification; the API remains the current-membership authority. `BUYEROS_API_BASE_URL` and public Auth0 issuer/client ID/audience are explicitly inlined by Vinext at build time because the Cloudflare RSC dev runtime did not inherit Node environment variables. No secret is inlined. The test-only issuer/API interception stays in Playwright, never in the application build. Access tokens remain in memory; one-use PKCE transaction state is stored only in sessionStorage. The observed Auth0 confidential client needs an approved public SPA configuration and real round trip before activation. Browser fixture verified 12 scope/auth paths; it does not verify real CORS or Auth0.

## T08 snapshot and read-model delta

The existing `buyer_selection` service remains the sole snapshot owner. It filters, sorts, and clips in SQL; the API pages frozen versioned IDs with actor/project/expiry checks and bounded related-data reads. `filters_hash` uses the already persisted `sha256:` prefix, reflected in OpenAPI. Unknown Buyer market/type/fit/review and Evidence source classification/title/requirement are optional until sourced; the API never invents them. Buyer notes normalize an absent database value to an empty string, and empty contact/policy collections are explicit. This change is verified by real disposable-PostgreSQL responses for all five T08 operations against their JSON Schema. No migration was added, and no live provider/source proof is implied.

## T09 list, review and preset delta

The single API now implements the seven list/preset operations formerly owned by the 501 registry. `BuyerList.version` is a strong precondition for rename and membership changes; `list_id` moves from deferred to supported snapshot and saved-filter inputs. Presets are unique per workspace/project/actor/name and same-name saves atomically advance `version`. Existing `project_buyers.note` is widened to the OpenAPI 20,000-character limit; `buyer_lists.name` is limited to 160 after preflight. The runtime API remains under tenant FORCE RLS, and `0014_buyer_management` is the sole Alembic revision for this slice.

Review acceptance now requires a current active ICP fit assessment, and a material review invalidates related draft approvals synchronously. `listWorkspaces` additionally exposes the current authorized `membership_id` so “Assign to me” uses an actual membership. The browser tests use fake identity/disposable PostgreSQL; none of these changes grants real policy permission or activates delivery.

## T10 purpose policy and suppression delta

`0015_policy_lifecycle` is the single next Alembic revision after verified head `0014_buyer_management`. It widens the old policy/suppression rows to explicit workspace/controller/subject/purpose/provenance/country/expiry/retention/actor fields and indexes. Upgrade aborts when legacy rows exist because their legal meaning cannot be inferred. Downgrade aborts when new policy or suppression history exists because dropping those fields would lose evidence. A disposable empty-database downgrade/re-upgrade passed; no persisted environment was migrated.

The API implements `listPolicyDecisions`, `recordPolicyDecision`, `listSuppressions`, `createSuppression`, and `removeSuppression` under current workspace membership and FORCE RLS. A client request for `permitted` always returns 403 `POLICY_APPROVAL_REQUIRED`; the test-only permitted rows exercise the evaluator and are not an owner approval or activation record. Restrictive decisions and suppressions retain actor, source, reason and versioned history. Adding a suppression synchronously invalidates matching draft approvals and quarantines existing contact points; removing it never restores either.

`evaluate_current_policy` serializes with policy mutations through one transaction-scoped workspace advisory lock. It chooses the latest decision at each applicable subject scope, applies the most restrictive current status, treats expiry/absence as unknown, derives a company domain from tenant-scoped persistence, and overlays active suppressions. Consuming route/worker code in T18/T21/T22/T24/T25/T26 must call this gate inside its own committing transaction before an intent, result display or export; it must use server-resolved IDs and preserve lock order. Late provider results, dispatch and export do not exist yet and are not verified by T10 tests. Real controller, jurisdiction, retention, data-owner and qualified-reviewer decisions remain external B-POLICY activation requirements.


## T11 durable bulk mutation delta

`0016_bulk_jobs` follows the verified single `0015_policy_lifecycle` head. Durable actor-bound `async_jobs` and immutable selected buyer/version `async_job_items` live under FORCE RLS. The existing transactional outbox and worker are the only dispatch path; one intent commits each at-most-50-row chunk and its successor intent atomically. The test-only browser pump invokes the real `run_intent` transaction directly and does not prove Valkey/Celery dispatch or a deployed worker.

The existing `reviewBuyers` and `changeListMemberships` 200 responses remain for selections of at most 100 buyers; 101–1000 freeze into a 202 `AsyncJobResponse`. `assignBuyerOwners` is a new BO-008 operation with the same 200/202 split. `getAsyncJob` now has an actor/admin-scoped bounded result page, and `retryFailedAsyncJob` is an added operation that creates a new command for only blocked/conflicted rows using current persisted versions. `cancelAsyncJob` is an added actor-bound operation that stops pending rows, records them as cancelled, and leaves committed rows untouched; it never claims a whole-batch rollback. New action and job history remain separate; same-key replay preserves the original response status and body. Strict `BulkResult` counts include `unchanged` so updated + unchanged + blocked + conflicts accounts for each completed row. No contact data is in the early failure report; cancelled rows are not eligible for failure-only retry.

The UI stores only the opaque job ID in its URL. A page reload requires fresh sign-in because bearer tokens stay in memory, after which the actor can read the durable job and its failure reasons. Owner membership must be active when a job is queued and is checked again per chunk. Revoked actors or later-inactive owners produce blocked rows rather than silent success. No policy permit, provider call, live identity, delivery or deployment is inferred from fixture completion.


## T12 settings and operations delta

`0017_settings_audit` follows the verified single `0016_bulk_jobs` head. It versions existing membership rows, adds actor/workspace preferences under FORCE RLS, permits UUID request correlation on audit events, and adds a service-only worker-heartbeat table. A disposable empty rollback to 0016 and re-upgrade passed; no shared or production schema was migrated. Membership updates remain limited to existing verified users and require an administrator, current If-Match, idempotency key and reason. The last active administrator cannot be removed. Every read rechecks current membership, so role changes take effect on existing bearer sessions.

The original contract gains `listMemberships`, `updateMembership`, and `listAsyncJobs` as separate T12 extensions, making 76 generated operations: 70 original and six cumulative extensions. The job page is actor-bound except for current workspace administrators, with bounded status/project filters and SQL pagination. Audit responses expose only UUID subjects and request IDs, normalized short reason codes, and no contact body/token. Existing T01–T11 idempotent writes now append a redacted first-write audit summary at the same transaction boundary where missing; domain-specific events remain. Replays do not append another summary.

Public liveness now returns a valid UUID request ID without disclosing dependencies; invalid inbound request IDs are replaced with a canonical UUID before response and audit correlation. Authorized readiness uses a live tenant database read plus the latest persisted worker heartbeat; absent/stale heartbeats fail closed, and only a real non-eager broker-delivered sweep records one. Capabilities remain unconfigured or disabled until verified provider activation, regardless of environment variables. Settings and operations reads retry after actor/project scope changes, so an early cancelled membership fetch cannot strand the member list. The operations UI shows persisted failed job count and selected-project profile approval state. It directs staff to the live buyer list for review status without inventing a review count; T27 remains the complete metrics owner. All browser identity proof in T12 is fixture-only until real Auth0 activation.


## T13 atomic budget and rollover delta

`0018_budget_ledger` follows the verified single `0017_settings_audit` Alembic head. Existing budget tables gain typed scope identity, UTC monthly boundaries, optimistic version, one operation reservation across constrained workspace/project/run/category accounts, an allocation projection table under FORCE RLS, and unique external economic-event identity. Existing projects receive zero-limit workspace, project and category accounts. New projects provision the same accounts in their creation transaction. Migration preflight refuses legacy nonzero budget, reservation or cost-event rows because the old schema lacks enough scope/period identity to map live liabilities safely; such rows require a reviewed mapping before any persisted upgrade. Disposable empty downgrade/re-upgrade and nonzero preflight were tested; no production database was migrated.

`listBudgets` and `updateBudget` now have domain handlers. The contract's provisional `budget_admin` role was removed from these operations because current membership roles are exactly viewer/operator/reviewer/workspace_admin; workspace_admin is the budget-limit editor. Update requires a strong If-Match, idempotency key and reason, rejects a reduction below settled plus effective held cost, and appends a redacted audit event. Operators/reviewers may read budgets; viewers receive 403. Money stays six-place USD strings in the API and UI; the UI shows zero remaining with a frozen state instead of a negative progress indicator.

`reserve_operation` holds a workspace transaction advisory lock and deterministic account row locks. It reserves only at the confirmed operation boundary, leaving quote creation unchanged; callers must create their job/outbox in that same transaction. Every new monthly account starts at zero, earlier unresolved holds count toward admission, and settlement/refund append one event to the original period. Empty cost evidence cannot release a hold. No provider price version was verified or paid call made in T13; T14 must supply bounded verified provider evidence before any live admission.

## T16 R2 data-location evidence (2026-09-28)

The recorded Cloudflare R2 “APAC” selection is a location **hint**. Cloudflare's current [data-location documentation](https://developers.cloudflare.com/r2/reference/data-location/) says hints are best effort, not a storage guarantee; jurisdiction restrictions are listed for EU, US and FedRAMP, with no APAC jurisdiction. We retain R2 as the selected object-store direction, but do not claim APAC data residency or provision a bucket from this note. If the controller requires guaranteed APAC residency, the storage decision needs explicit review before activation. Cloudflare's [presigned URL documentation](https://developers.cloudflare.com/r2/api/s3/presigned-urls/) also states that a bearer URL remains reusable until expiry, so sensitive document reads should pass through current API authorization rather than expose a revocation-bypassing direct link.

## T16 pending URL document digest and schema delta

A queued URL fetch has no retrieved bytes to hash. The proposed `OfferDocument.sha256` response had required a digest even in queued status, which would force a synthetic value. The contract now permits null until retrieval; uploads still require a caller-declared SHA-256 verified against the actual bytes. The current repository had no `offer_documents` table despite the historical BO-012 “no migration” estimate. Alembic `0019_offer_documents` follows the single verified 0018 head and adds tenant RLS, project linkage, document lifecycle metadata and nullable source-object retention fields. Its downgrade refuses nonempty new document/source data.
