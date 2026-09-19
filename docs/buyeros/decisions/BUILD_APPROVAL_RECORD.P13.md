# Build approval record — P13 durable buyer review (BO-008, Slice 1)

**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-19 (Hong Kong).

| Field | Value |
|---|---|
| Task | **BO-008** — persist buyer evidence views, reviews, stable selections and lists (**Slice 1** of the task) |
| Phase | **P13 durable buyer review** (the first buyer read/review workflow over the P12 write surface) |
| Scope | `createBuyerSnapshot`, wider `listBuyers`/`getBuyer`, `updateBuyer` (notes/owner under `If-Match`), append-only `reviewBuyers` with per-item conflicts, `listBuyerEvidence`/`getEvidence`, migration `0011`, and live buyer table/detail UI |
| Spec | `docs/buyeros/specs/2026-09-19-p13-buyer-review-design.md` |
| Plan | `docs/buyeros/plans/2026-09-19-p13-buyer-review-implementation.md` |
| Base | branch `p13-buyer-review` from `p12-project-profile-writes` @ `91ba848` (which contains `p11-demo-live-adapter` @ `cf20b1a` and `main` @ `d159ae9`) |
| Allowed files | create `services/api/alembic/versions/0011_project_buyer_version.py`, `services/api/buyeros_api/services/{buyer_view,buyer_selection,buyer_read,buyer_review}.py`, `services/api/buyeros_api/api/routes/reviews.py`, `services/api/tests/test_buyer_review_db.py`, `services/live/buyer-selection.ts`, `features/live/{buyers,buyer-detail}.tsx`; modify `services/api/buyeros_api/{db/buyers.py,db/contact.py,api/schemas.py,api/idempotency.py,api/deps.py,api/routes/buyers.py,api/app.py,api/unimplemented.py}`, `services/api/tests/{conftest,test_api_buyers,test_api_deps,test_api_routes_contract,test_buyer_review_db}.py`, `services/live/mapping.ts`, `tests/live-adapter-checks.mjs`, `features/{workspace.tsx,live/buyers.tsx,live/buyer-detail.tsx}`; docs under `docs/buyeros/**` |
| Dependencies with evidence | BO-007 (P12) is complete for the write surface; the P2 tables already exist in `0003_p2_tables.py`. The B-IDENTITY blocker (no live Auth0) is accepted below |
| Approver | Owner (execution mode = subagent-driven) |
| Environment/spend | none; no network, no identity provider, no credentials, no provider calls. Backend tests use the disposable `postgres:16` fixture; frontend checks use a stubbed fetch |
| Excluded | buyer lists and filter presets (Slice 2), discovery/runs/fit generation, `contacts`/`policies` fields, suppression, draft-approval invalidation (P5), real Auth0 activation, CORS/CSRF, audit hooks, browser tests, live workspace selection, UI redesign |

## Dependency waiver (explicit)

B-IDENTITY is unresolved, so no configured identity provider can issue a token the API would verify. The owner waived that prerequisite: P13 proves the **buyer read/review surface and its seam** — bounded snapshot materialization, a wider contract-shaped buyer read, idempotent note/owner updates under a strong `If-Match`, append-only review with per-item version conflicts and a stored bulk replay, scoped evidence reads, and the live mapping/UI — against the disposable database and a stubbed fetch, with no network and no live mode. Consequences accepted: `filters.markets`/`source_types` and the `contacts`/`policies`/`market`/`buyer_type` response fields have no source yet; live mode stays gated off with no workspace selection, so the authenticated round trip is not exercised. This waiver does not mark BO-008 complete in the task index and authorizes no other phase.

## Recorded deviations from the BO-008 task text

1. **Slice 1 only.** Lists (`createBuyerList`/`listBuyerLists`/`getBuyerList`/`renameBuyerList`/`changeListMemberships`) and filter presets (`listFilterPresets`/`saveFilterPreset`) are Slice 2; acceptance test **TEST-BO-008-02** (list membership) is deferred with them.
2. **No Playwright.** The task specifies `pnpm exec playwright test`. The repository's zero-dependency node check convention is extended instead, so **no new dependency** is added; the live UI is verified by `tsc`, `eslint` and `pnpm build`.
3. **Evidence reads pulled forward from BO-014.** `listBuyerEvidence`/`getEvidence` are tagged BO-014 in the contract; they are read-only and add no table, so they are implemented here so the live drawer's evidence view is real.
4. **`source_types` deferred.** Neither `evidence` nor `source_documents` carries a source-type column until P3/BO-014 ingestion, so a non-empty `source_types` filter is rejected (`422`) rather than silently ignored; the spec §D was amended in lockstep.
5. **Owner mapping.** The contract's `owner_membership_id` is stored as the membership's `user_id` in the existing `project_buyers.owner_user_id` and resolved back on read; no new column.
6. **Stale task paths and migration impact.** The task lists `main.py`/`models/core.py` and `migration_impact: none`; the repository uses `api/app.py` + `db/`, and this phase needs migration `0011`.
7. **Recorded limitation.** `listBuyers`/`getBuyer` load fit/review/owner/evidence-count with one query per row; acceptable for a page of at most 100 in a pilot and recorded rather than batched.
8. **Review `reason` column widened.** Migration `0011` also widens `human_reviews.reason` to `varchar(2000)` so the contract's 3..2000 reason is storable; the downgrade truncates with `USING left(reason, 400)` so it stays reversible on a populated database.
9. **Review emission gated on a known assessment.** A `Buyer.review` is emitted only when `fit` is present and the review's `assessment_id` is set, so every emitted `review` carries its contract-required `assessment_id`/`icp_version_id`; a review on a buyer without a fit assessment is stored but not emitted until an assessment exists.
10. **Owner UI deferred.** The live drawer implements the note editor (calling `updateBuyer` with `If-Match`); the owner control is deferred because live mode has no membership picker. The spec §E and its file map were corrected.
11. **Project-scoped idempotency.** `createBuyerSnapshot`/`reviewBuyers` use `operation_id="<op>:<project_id>"` so the same key cannot replay across projects.

## Sign-off (owner)

Recorded from the owner's in-session direction on 2026-09-19: the owner approved the P13 spec, selected Slice 1, chose subagent-driven execution, and authorized that execution under the dependency waiver above. This record captures that authorization; it is not a verbatim quotation and no remote push, deploy or activation is authorized by it.
