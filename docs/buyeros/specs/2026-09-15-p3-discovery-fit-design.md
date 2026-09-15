# P3 design — bounded discovery, canonicalization, evidence-first fit, run progress

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Design covers tasks **BO-013, BO-014, BO-015, BO-016** (phase P3). Approved in the Plan review session; this is a design input, not Build approval.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, commit or push is authorized or performed by this document. No provider is activated and no paid step is enabled.

Related records: [P1 boundary design](2026-09-15-p1-boundary-design.md), [P2 foundation design](2026-09-15-p2-persistence-foundation-design.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md), [03 data/API contracts](../03_DATA_API_AND_STATE_CONTRACTS.md), [research/UPSTREAM_AUDIT.md](../research/UPSTREAM_AUDIT.md), [contracts/openapi.proposed.yaml](../contracts/openapi.proposed.yaml).

Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Canonical repository: `YNWAforever/BuyerOS` (planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; a source import is still expected to produce tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`).

## Scope

Deliver bounded, budgeted, multilingual company discovery; canonicalization with linked evidence; an evidence-first fit assessment that stops for human review; and durable run progress/cancel/retry in the preserved UI.

In scope: BO-013, BO-014, BO-015, BO-016. Out of scope: contact lookup (BO-017+), drafting (BO-021+), provider adapters selection (BO-002), delivery. Depends on the P1 boundary and P2 foundations.

## J. Bounded multilingual discovery (BO-013)

- Run creation binds the **approved ICP version** and must pass tenant + policy + atomic budget admission. No run without an approved profile.
- **Query plan:** versioned `query-plan.v1` prompt producing a structured `QueryPlan{queries[{query,market,language,requirement_ids}], rationale_summary}`. Languages and markets come from the saved profile, not fixture equality. Strategy: German for DE, Dutch for NL, Dutch/French + English for BE, English industrial vocabulary as approved fallback.
- **Limits (authoritative, 03 §8.1):** ≤3 adaptive rounds; **≤12 query dispatches total per logical run including safe retries**; ≤300 raw results; 30-minute wall clock from first external dispatch; limits accumulate across retries/restart and a retry cannot reset the deadline.
- **Search adapter:** a **single provider-agnostic adapter** behind a verified capability manifest with deterministic fixtures. The concrete provider, endpoints, pricing and rights are pinned later in BO-002. **No waterfall and no second provider.** Search can be billable, so each dispatch takes its own bounded reservation and idempotent intent.
- **Model route:** one approved model route per task; versioned prompts; cumulative ≤100k tokens across calls/repairs/retries; at most one schema-repair attempt inside the already-approved budget. No invented model identifiers or prices.
- Discovery **stops at human review**: there is no graph edge into contact lookup, drafting, or sending.

## K. Canonicalization and linked evidence (BO-014)

- URL normalization uses a real parser: lowercase/IDNA host, drop default ports and tracking fragments, record redirect/alias provenance. A registrable domain is an **identity hint**, not proof of legal identity.
- Merge only **proven identical registry identifiers** or a **reviewed exact alias** with compatible legal entity and market. Shared brand domains, subsidiaries and similarly named distributors remain **separate**. Ambiguity produces a **review item**, never an automatic merge. Raw→canonical lineage is reversible and preserved; no irreversible fuzzy merge.
- Evidence: versioned `source_documents` (canonical URL, digest, retrieval/observation time, original language, storage mode) and `evidence` rows marked supports/contradicts/qualifies and observation/inference, with translation kept distinct from the source excerpt.
- Every important claim links an exact evidence ID/hash. Inaccessible, changed or deleted sources are labelled unavailable/unknown and **fail closed** for approval; a deleted source's hash alone does not substantiate its old claim.

## L. Evidence-first fit (BO-015)

- LangGraph checkpoints preserve **workflow progress only**, in a **separate schema** via a pinned saver under the single Alembic migration owner. State references IDs/hashes/counters and bounded query plans; it stores no raw pages, prompts, or private reasoning.
- Node sequence: validate request/limits → load approved ICP → generate query plan → discover candidates → normalize/deduplicate → fetch permitted evidence → deterministic hard exclusions → structured fit → verify linkage → persist immutable assessment and run events → **await human review**.
- Fit output: `match` / `needs_review` / `not_a_match`, plus supported/contradicted/unknown requirement sets, evidence IDs, a terse rationale and a next review action. The output schema **forbids invented evidence IDs**; there is at most one bounded repair, and a validator confirms every cited ID belongs to the same tenant/run/company scope and is permitted/current.
- Assessments are **immutable**; human acceptance (BO-008) is a separate decision. A LangGraph checkpoint may never authorize a paid call or bypass a newer policy decision.
- **Prompt-injection posture:** fetched text is untrusted data. The allowed tool set contains no path to contact lookup, spend, or send; page instructions cannot add tools or authorize a network call.

## M. Durable run progress, cancellation and retry (BO-016)

- `run_events` carry a **monotonic per-run sequence** with unique `(workspace, run, sequence)`, committed **atomically** with the corresponding state transition. Progress derives from committed events, never timer animation; a completed run may yield fewer companies than the target and still be complete.
- **Transport:** authenticated **fetch-streaming SSE** using an `Authorization` header (never a query-string token), `after_sequence`/`Last-Event-ID` resume, comments as heartbeats. **Polling** on the same JSON endpoint is the fallback. Reconnect replays after the last applied sequence; duplicates are ignored; gaps trigger a replay/snapshot refresh; tenant switch aborts the stream and clears scoped selections/quotes/editor caches.
- **Cancellation:** `running → cancel_requested → cancelled`; **in-flight paid holds remain** and the UI never claims the provider was cancelled. `cancel_requested` is independent of pending/unknown provider states.
- **Retry:** explicit immutable attempt IDs; only safe/idempotent stages; requires remaining budget; **never blind-retries an unknown submission**. Partial results and committed costs are retained; the UI shows the existing run screen with real error/empty states instead of sample data.

## Cross-cutting

RLS + composite tenant FKs and the single Alembic migration owner apply to every new table. Mutations carry an `Idempotency-Key` (except provider callbacks) and version preconditions where relevant. Live responses use `{data, request_id, data_mode:"live"}`; demo and live never mix.

## Data flow

Approved ICP → run admission (tenant/policy/budget) → committed intent + outbox → worker: query plan → provider search (reserved, idempotent) → canonicalize + link evidence → fit assessment → persist + emit run events → SSE/polling to the UI → human review. Retry/cancel operate on committed run state only.

## Interfaces

Provider-neutral public API per the proposed OpenAPI (`startRun`, `getRun`, `getRunEvents`, `cancelRun`, `retryRun`, `listBuyers`, `getEvidence`, `getAsyncJob`). No new endpoint may be invented; disagreement is a reviewed contract revision. Error codes/envelopes follow 03 §4.

## Testing (all PROPOSED_AFTER_TASK / NOT RUN)

| Test | Expectation |
|---|---|
| TEST-BO-013-01 | DE/NL/BE query fixtures; unsupported country rejected; token/round/spend caps enforced; honest partial/empty results with no sample substitution and no enrichment edge |
| TEST-BO-014-01 | distinct legal entities sharing a domain stay separate; evidence-ID tamper rejected; contradictions/unknowns preserved; stale/deleted source marks evidence unavailable |
| TEST-BO-015-01 | claims cite allowed evidence; unsupported claims rejected or marked review; injection cannot trigger contact/spend/send; stale profile/evidence fails closed |
| TEST-BO-016-01 | reconnect/duplicate/gap handling, polling fallback, scoped stream; cancel/retry produce no duplicate cost; terminal event durable |

Supporting: OpenAPI parse (70 ops / 139 schemas / 0 unresolved — verified in planning), deterministic provider fixtures, `node tests/domain-checks.mjs`, `pnpm exec tsc --noEmit` — NOT RUN.

## Assumptions, blockers and non-goals

- **Blocked by:** B-PROVIDERS (search + LLM route categories), B-POLICY, B-LICENSE (AI_Find_Customer MIT adaptation scope, parser/PDF deferral), B-HOST. Dependencies: BO-013 needs BO-002/010/011/012; BO-014 needs BO-008/012/013; BO-015 needs BO-014; BO-016 needs BO-006/007/011/015.
- **Non-goals:** live paid discovery execution, provider selection, contact lookup, drafting, delivery, migrations executed, provisioning, and any Build action.

## Completion criteria

No task is completed by this document. BO-013…BO-016 may be marked DONE only when their own acceptance tests and approval obligations have recorded evidence.

## Rollback / roll-forward

Supersede this design with a dated successor for design changes. Prefer forward-compatible migrations and additive repair; never discard committed research results or release unknown holds to satisfy a limit.
