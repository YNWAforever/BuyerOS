# Increment 2.7 review — "Why this proposal" explainer and read-time decision decoration

Reviewer: `reliability` (independent of the implementation streams)
Date: 2026-11-09 (Asia/Singapore)
Worktree: `C:\Users\laich\Documents\BuyerOS\.worktrees\conv-studio`, branch `feat/conversation-proposal-why`, head `a3e724859` (stacked PR #59 on `feat/conversation-streaming`).
Contract: `docs/superpowers/specs/2026-11-09-proposal-explainer.md` (Increment 2.7) plus the Increment A/B/C contracts.
Scope: backend read-time decision decoration, thread/turn response paths, frontend decision reader + explainer projection/component, and regression risk to the shipped gate. **No implementation file was modified by this review; the only file written is this document.**

Verification legend:
- **[READ]** verified by reading source at the cited `file:line`.
- **[TEST]** verified by a test executed in this sandbox (frontend `node:test`, tsc, lint only — see §5).
- **[BLOCKED]** PostgreSQL and browser execution are unavailable here (Docker named pipe denied; uv cache read-only so no Python env; Playwright `spawn EPERM`). CI run 42597516460 is the authority; no DB/browser result is claimed by this review.
- **[ROUTED]** reported to the Lead.

## 1. Findings summary

| Id | Severity | Finding | Evidence | Status |
| --- | --- | --- | --- | --- |
| MAJOR-1 | Major (hardening/acceptance) | The decoration lookup is scoped by `workspace_id + project_id + proposal_id` only, not by `thread_id`/`turn_id`. The acceptance criterion asks for "same workspace/project/thread/proposal"; a decision row whose `proposal_id`/`thread_id` pair is inconsistent (possible only by direct DB write — the API always writes a consistent pair) would still decorate the thread that contains that proposal part. No user-reachable mismatch was found: proposal ids are `uuid5(thread_id, client_message_id, capability)` and `conversation_turn_decisions` is `UNIQUE(workspace_id, proposal_id)` with both FKs enforced. | `services/api/buyeros_api/services/conversation_proposal_read.py:52-55`; proposal-id derivation `services/conversation_turns.py` (`_proposal`); decision schema `db/conversation_turns.py:78-103`; no negative test for a foreign/mismatched decision | [READ] |
| MINOR-1 | Minor (strictness) | The frontend decision reader accepts wider objects (extra keys are ignored, not rejected): `readProposalDecision` and `persistedDecision` destructure `choice/decided_at/decided_by` and drop everything else. No internal value is ever rendered, but the task explicitly asks to reject wider/malformed shapes. | `features/live/conversation/types.ts:94-101`; `features/live/conversation/explainer.ts:76-84` | [READ] |
| MINOR-2 | Minor (defence in depth) | Argument projection filters internal **keys** (`id/hash/fingerprint/token/locator/protocol/schema/...`), not id/hash-shaped **values**, and the key regex misses camelCase internal keys. Current server previews are safe (only `document_ids`/`buyer_id`/`company_id`/`source_ids` are filtered; the remaining values are user text/language), so no current leak; a future preview field with an id under a benign key would render. | `features/live/conversation/explainer.ts:36-41,57-66`; server previews `services/conversation_turns.py` (`_proposal` call sites) | [READ] |
| MINOR-3 | Minor (defence in depth) | `decision_payload` passes `row.decision` through without a server-side allowlist check. The DB CHECK restricts it to `approve|reject` and the frontend drops anything else, so a corrupt row degrades to absent, not a leak or 500. | `services/conversation_proposal_read.py:34-40`; DB CHECK `alembic/versions/0066_conversation_turns.py` (decision CHECK) | [READ] |
| MINOR-4 | Minor (coverage) | No viewer-specific decoration test (the new API test covers a teammate editor; the viewer path is identical but unasserted), and no negative test proves a foreign/mismatched decision never decorates. | `services/api/tests/test_conversation_turns_api.py` decoration tests; `tests/conversation-home-responsive.test.mjs` explainer row | [READ] |
| MINOR-5 | Minor (copy) | The explainer "Decision" row renders the action words `Approve`/`Reject` rather than past-tense `Approved`/`Rejected`. Cosmetic only; no privacy/authority impact. | `features/live/conversation/proposal-explainer.tsx:45-47` | [READ] |
| OBS-1 | Observation | The pre-existing tool-activity "Details" disclosure still renders `capability` names (e.g. `xverum.enrich_company`); that is Increment A behaviour and is outside the explainer's ordinary path, but it means protocol names remain visible in a nested disclosure elsewhere in the transcript. | `features/live/conversation/inline-parts.tsx` (`ToolActivity`) | [READ] |

**No blocker was found.** No user id, email, membership id, correlation id or other internal reference can cross through the decoration payload, and there is no re-fetch or write on expand.

## 2. Backend: privacy of the decoration [READ]

- Payload shape is exactly three fields: `choice` (`row.decision`), `decided_at` (`row.created_at` ISO-8601, naive timestamps coerced to UTC) and `decided_by` (`you` / `a workspace member`). `decision_payload` is the only constructor (`services/conversation_proposal_read.py:34-40`).
- `coarse_actor_label` compares the requesting actor (resolved server-side from membership by `access()`) with `row.actor_id` and returns only the two coarse labels; missing actor ids degrade to `a workspace member` (`:23-31`). Unit test asserts neither UUID appears in the payload (`tests/test_conversation_proposal_read_unit.py:38-45`).
- The decorator is the only path that reads `conversation_turn_decisions` for a response: a repository-wide grep finds the table referenced only by the decision service (write/read for replay) and this decorator; no endpoint serializes the raw row. `decided_at` exposes decision timing (explicitly allowed by the contract), not identity.
- Viewer/teammate: every decorated path receives `viewer=actor` from `access()`; a teammate or viewer therefore gets `a workspace member`, while the decision actor gets `you`. API test asserts the teammate editor label and the absence of the operator UUID (`test_conversation_turns_api.py`, new decoration tests).
- Reconcile continuation: the continuation turn has no proposal part, but the response thread includes the source proposal and is decorated; the new assertion in `test_reconcile_unknown_then_new_evidence_and_idempotent_replays` proves `choice`/`decided_by='you'` there.
- Tenant/ACL: lookup filters `workspace_id` + `project_id` (RLS is also forced on the table); proposal ids are derived per thread, and the decision table is `UNIQUE(workspace_id, proposal_id)` with FKs to the proposal and turn. No cross-workspace/cross-project path exists. MAJOR-1 is the missing explicit thread/turn predicate and negative test (defence in depth, no user-reachable exploit found).

## 3. Backend: read-only, no schema change, failure mode [READ]

- **No writes**: `conversation_proposal_read.py` performs only `select`; `_part_dicts` copies each part dict and `decorate_parts` returns new dicts. `decorate_thread_payload`/`decorate_turn_payload` mutate only the freshly built response dict, never ORM rows. API test compares `conversation_turns.parts` and `conversation_thread_messages.parts` JSONB byte-for-byte before and after a decorated read (`test_proposal_decision_absent_before_decision_and_stored_parts_unchanged`).
- **Stored parts cannot even contain a decision**: the persisted-part DB validator requires an exact key set per part kind (`alembic/versions/0066_conversation_turns.py`, `buyeros_turn_parts_valid`), and the pydantic part models are `extra="forbid"` — so `decision` is necessarily read-time only.
- **No schema change**: the diff contains no Alembic revision; the decoration is derived from existing `conversation_turn_decisions` columns.
- **Missing/malformed decision degrades to absent, never 500**: absent row → no field added; `created_at is None` → empty `decided_at` (frontend drops it and shows Unknown); malformed `actor_id` falls back to string comparison; the DB CHECK makes a malformed `choice` unreachable through the API. No new exception path is introduced in the route.
- All thread response paths are decorated consistently: create/get/rename/append/sources/runs/grant/revoke in `api/routes/conversation_threads.py` and create/decide/cancel/reconcile in `api/routes/conversation_turns.py` pass `viewer=actor`; list responses are `full=False` and contain no parts (nothing to decorate). No route was missed.

## 4. Frontend: reader, projection, component [READ]

- **Strict-ish decision reader**: `readProposalDecision` allowlists `choice` and `decided_by`, bounds/parses `decided_at` (`types.ts:94-101`); `persistedDecision` repeats the validation for the explainer (`explainer.ts:76-84`). Malformed shapes become absent and the explainer renders explicit Unknown rows. MINOR-1: extra keys are ignored rather than rejected.
- **No internal values rendered**: `proposalExplain` projects only rationale (bounded), arguments (keys filtered, primitives only, ≤12 items/200 chars), evidence (citation labels + already-allowlisted `/app` hrefs), cost state, filtered policy notices, approval state and the validated decision. It never includes `proposal_id`, `capability`, hashes or raw argument objects; the core test asserts none of those strings appear in the view model (`tests/core-conversation-explainer.test.mjs:52-60`). The old collapsed-card "Details" disclosure that rendered `capability` and `proposal_id` was removed.
- **Unknown rows only for absent data**: absent rationale/arguments/evidence/decision each render `Unknown`; a present decision renders choice/actor/time (browser row asserts zero Unknown rows for the decided terminal card and exactly three for the undecided card).
- **Cost wording preserved**: `readCost` keeps the shipped `known:false` rule — a provider-credit cost with `known:false` (or any `known:false`) maps to `review_required`, which renders "Cost review required before any paid request." and never a number; the collapsed `ProposalCostLine` is unchanged and still shows the same wording. Core test asserts no `0` from the unknown tariff; browser row asserts the shipped sentence.
- **No re-fetch / no mutation on expand**: the explainer is a native `<details>` over `useMemo` projection of already-loaded parts; the browser row asserts the request count is unchanged when expanding/collapsing.
- **Approval behaviour unchanged**: inline-parts still renders the same Approve/Reject buttons and the same `proposalUiState`/terminal-inert gating; the explainer adds no actions. Browser row asserts Approve remains on the awaiting card and is absent (with Reject) on the inert terminal card; the pre-existing viewer row still asserts a viewer has no actions.
- **a11y**: native `<summary>` disclosure (keyboard operable, focusable) with visible text; evidence links are real buttons; decision values are rendered as text. No custom key handling is needed.
- **EN/zh-HK**: 9 new keys in `features/live/locale.ts` and 12 in `locales/index.ts`; a reviewer scan of `explainer.ts`, `proposal-explainer.tsx` and `inline-parts.tsx` finds 0 missing keys, and the browser row checks zh-HK labels for the disclosure, rationale and actor.

## 5. Verification executed / BLOCKED

Executed here (bundled Node v24; `--experimental-test-isolation=none` because the sandbox blocks child spawn):
- Core client suite `tests/core-*.test.mjs` + `tests/audit-research-intent.test.mjs` → **141 tests, 141 pass, 0 fail** (matches CI count gate 141; includes the 6 new explainer tests).
- `tsc --noEmit -p tsconfig.json` → exit 0.
- Targeted eslint on `features/live/conversation`, `tests/core-conversation-explainer.test.mjs`, `tests/conversation-home-responsive.test.mjs` → exit 0.
- Static consistency: pytest inventory 3999→4005 matches the 6 added backend tests (4 unit + 2 API); browser gate 22→23 cases (one appended test) with the same six screenshot paths as the base branch and no pre-existing assertion changed (the diff is a single appended test block); i18n scan 0 missing.

**BLOCKED locally (CI is authoritative):** all PostgreSQL pytest (the new `test_conversation_proposal_read_unit.py`, the two new decoration API tests, the reconcile decoration assertion, tenant/RLS/stored-parts assertions), and the Playwright browser gate (the new explainer row plus the 22 pre-existing rows). Real provider/paid behaviour is not involved in this increment.

## 6. CI artifacts that prove acceptance

| Criterion | Proof | Artifact |
| --- | --- | --- |
| Payload privacy (only choice/decided_at/decided_by; no ids) | `test_conversation_proposal_read_unit.py` (coarse label, no UUID in payload), new API decoration tests (operator UUID absent from response text), teammate label test | job `api`: `services/api/artifacts/tests.xml` (artifact `buyeros-neon-cutover-local-rehearsal`), inventory 4005 |
| Decoration on turn responses, thread GET/PATCH, reconcile continuation | New decoration API tests + reconcile-response assertion; all response paths wired with `viewer=actor` | same `tests.xml` |
| Stored parts untouched / no schema change | `test_proposal_decision_absent_before_decision_and_stored_parts_unchanged` (JSONB before/after) | same `tests.xml` |
| Missing/malformed decision degrades to absent | unit tests (malformed/absent), source validation | same `tests.xml` |
| Frontend strict reader / projection (no ids, cost wording, unknown rows) | `tests/core-conversation-explainer.test.mjs` (6 cases) | job `frontend`: `test-results/core-client.xml` (artifact `buyeros-core-client`), count 141 |
| Browser explainer (expand/collapse, evidence link, cost wording, approval state, terminal inertness, zh-HK, no fetch) | new browser row + the 22 pre-existing rows | job `frontend`: `test-results/conversation-studio.xml` + `test-results/conversation-studio/*.png` (artifact `buyeros-conversation-studio`), 23 cases |
| Regression: pre-existing rows/screenshots unchanged | diff is additive; six screenshot paths unchanged; 22→23 cases | same browser artifact |
| No schema/migration | diff has no Alembic revision; `tests.xml` migration tests unchanged | `tests.xml` |

Unproven by any artifact: a negative test for a foreign/mismatched decision row (MINOR-4), a viewer-specific decoration assertion, and value-pattern filtering for future argument previews (MINOR-2). None blocks acceptance; they are the residual hardening list.

## 7. Recommendations (owner: owning streams)

1. Add `thread_id` (and ideally `turn_id`) to the decision lookup and a negative test that a decision row from another thread/project/workspace never decorates (MAJOR-1/MINOR-4).
2. Reject wider decision shapes explicitly (exact key set) in `readProposalDecision`/`persistedDecision` (MINOR-1).
3. Consider value-level UUID/hash filtering in `readArguments` and camelCase coverage in `INTERNAL_KEY` (MINOR-2), and an allowlist check on `row.decision` server-side (MINOR-3).
4. Optional copy fix: render past-tense decision choice (MINOR-5).

## 8. Not reviewed / out of scope

- No production deployment/promotion/Vercel changes; no implementation edits (only this document).
- Real provider/paid dispatch, production data and browser runtime were not exercised here; the CI artifacts above are the substitute.
