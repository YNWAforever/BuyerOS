# Xverum dispatch and reconciliation

New work requires an explicitly assigned, current connection, approved purpose,
unsuppressed buyer, current quote, separate USD and integer-credit holds, enabled
native runtime, and a provisioned durable credential adapter. Defaults remain
disabled. This implementation does not authorize live activation or spending.

## Admission and execution

Quote confirmation commits the reservation, stage, bounded per-tool receipts and
`xverum.step` outbox together. `StepReceipt.id` is the admitted stage receipt ID.
Standalone `task_id=null` grants no private-task authority. Linked admission uses
`POST /xverum/tasks/{task_id}/quotes/{quote_id}/approve` with native Idempotency-Key
and task If-Match; the server checks thread access, skill allowlist, buyer and
context. Linking an already standalone receipt is refused.

The native worker commits a per-tool claim before calling Task7 `call_xverum`.
That boundary retains all credential/generation checks and additionally rechecks
dispatch authority immediately before tools/call. There is no transaction over
credential or network IO. Each stage has at most six tools, each with at most two
attempts. The second attempt is allowed only after typed proof that tools/call
never started, with bounded backoff and the original quote deadline. Search is
never approval for future detail/email selection.

Linked declarations count against the same 16-step/8-model-call/2-concurrent
invocation, under the task lock. Unknown work continues to occupy a slot. Provider
USD reservations and integer credits are independent of the single model parent.
Cancellation stops undispatched tools. It does not undo accepted calls.

## Outcome unknown

A committed claim with no durable response, a timeout after tools/call begins,
invalid/over-ceiling billing, or a failed projection transaction retains both
holds. Recovery/readback never calls the provider. No retry endpoint exists.
Empty results with authoritative zero usage are successful results, not failures.

1. Use current workspace-admin authority to GET
   `/xverum/receipts/{receipt_id}/liability`. It returns the original connection,
   generation/account reference, current receipt ETag and content-free per-tool
   identities/states/request IDs. It does not grant private-thread result access.
2. Independently obtain authoritative account/provider evidence through the
   organization's existing controlled operational process. Match original account,
   connection/generation, exact tool claim and request, and billing units. Do not
   infer non-dispatch from a timeout, empty result, HTTP error or missing billing.
3. Retain the evidence in an access-controlled operational record. Supply its
   opaque UUID as `evidence_ref`; never supply a token, raw response, public URL,
   signed URL, personal profile/background, or transcript. The operator attests
   to this evidence; the API does not perform provider verification or fetch URLs.
4. POST `/xverum/receipts/{receipt_id}/reconcile` with Idempotency-Key, current
   receipt If-Match, and `ReconciliationEvidence`. `expected_version` must match
   the header. Multi-tool stages require the exact `tool_receipt_id`.
   - `usage`: exact provider request ID and authoritative integer tool credits.
   - `non_dispatch`: authoritative proof that this tool was never dispatched;
     conflicting retained acceptance or usage is rejected.
   - `unknown`: preserves uncertainty and both holds.
5. Re-read the liability and balances. Reconciliation stops remaining unclaimed
   tools; it cannot resume the stage. A separate reviewed quote is new work.

Repairs remain available when new-sales admission is disabled or the connection
is disconnected. Current operational membership is rechecked even on replay.
Evidence identity, original account/connection and payload are permanently
deduplicated in `xverum_reconciliations`; key expiry cannot double-charge. CAS
conflicts require fresh readback, not automatic resubmission with a new version.

## Balance reconciliation

Unknown member calls retain the entire stage credit and USD reservation. Only
when all member outcomes are known does the owner sum accepted tool credits,
settle the original tariff-derived Decimal USD amount through `settle_operation`,
append one credit settlement and release the remaining holds atomically. Known
non-dispatch for every tool releases unused holds without a charge. Zero accepted
usage creates one native zero-cost event. Provider credits are never USD amounts.

Inspect the stage reservation's native operation ID, native USD reservation,
original tariff version, credit account and per-tool observations together.
Conflicting or above-ceiling evidence requires investigation; this API does not
invent capacity, alter tariffs, top up balances, or compensate an existing charge.
Model-parent billing remains the separate model accounting owner's obligation.

## Retained result evidence and next owner

`xverum_tool_receipts` stores only the Task7 typed professional projection,
digest, request/usage metadata and a 24-hour expiry. No raw response is stored.
`read_evidence(session, scope, receipt_id)` rechecks current actor/project/private
thread/context, current connection generation, purpose/suppression, settlement
and expiry. Call it with policy/USD gates acquired before any thread/task lock;
the function acquires those gates itself for a top-level call. Financial operator
repair cannot manufacture projected contact data.

Detail evidence also depends on its original search. The immutable quote's
`source_receipt_id` / `source_digest` retain that dependency; the source stage
retains its task/thread/context/intake binding. `source_search_evidence` permits
exactly one terminal search with one received, unexpired, digest-consistent
projection. It rejects detail chains and cycles before traversing them. Creating
or approving a detail quote, every pre-call authorization, post-response
retention, quote readback and evidence resolution recheck the source's current
private authority, context, connection, policy and expiry. Standalone approval or
linking to a different task cannot remove this dependency. A detail's own expiry
does not extend its source's lifetime. Source revocation after a call preserves
financial usage but denies result retention; revocation after settlement hides
the derived evidence. Operator liability readback and reconciliation remain
available under their independent current financial authority.

HTTP receipt cancellation acquires policy/USD gates before its first linked
ownership check, including idempotent replay. All callers composing these owners
must acquire those gates before any thread/task lock, including source threads.

`resolve_evidence(session, scope, SourceRef(...))` accepts the immutable tool
receipt ID, version 1, and `provider_evidence:{id}` locator. Task10 must consume
this owner when adding provider sources to canonical enrichment/output assembly;
generic model/context admission is deliberately not broadened by this task.
Returned evidence includes buyer ID/version, selected/returned provider IDs,
connection generation, digest and typed projection. Never treat a model-generated
ID as provider provenance. No-results produces an empty, valid projection.

Task10 owns identity selection, proposed field validation and canonical output
save/readback. Task14 owns coordinated expiry/deletion/redaction across derived
outputs, backups and retained financial proof. Reads already hide expired or
revoked evidence; the linked stage FK preserves proof against task deletion.
No task is marked completed merely because provider dispatch settled.

Task10 integration also owns Task9 review M1: give earlier successful members
nonzero usage in the multi-tool recovery test, then assert aggregate credits,
tariff-derived Decimal USD, released holds and exactly one native cost event
across repeated repair/readback. This is separate from the closed Task8 M1.

## Local validation boundary

Use only the identity-gated disposable PostgreSQL allocator. Clear inherited
`BUYEROS_*` and `NEXT_PUBLIC_CONVERSATION_HOME`, set `BUYEROS_STRICT_INTEGRATION=1`
and retain `BUYEROS_POLICY_FIXTURE_EVIDENCE`. Verify the prior exact runner exited
before another starts; inspect only exact allocator container IDs for cleanup.
Synthetic transport/credentials prove local wiring, not live OAuth, provider
billing, durable external credential-service acceptance or production readiness.

## Task15 bounded release preparation

Current local schema: `0065_sales_lifecycle`. Task15's acceptance report supersedes historical collected-only claims. Run `tools/run_sales_isolated.py --allocate-owned --evidence <new-directory>` with the installed API Python from repository root after the guard tests. No external DSN or provider endpoint is accepted. CI is nonbillable and never activates a provider. See [guided-sales-release.md](guided-sales-release.md) for exact-target approval fields, maximum tool scope/spend and non-destructive rollback.

The five permitted tool IDs are `search_company_xverum`, `search_people_xverum`, `enrich_company_xverum`, `enrich_person_xverum`, `get_email_xverum`. Search and selected-ID detail/email have distinct reviewed quotes. Disabled extra tools remain disabled. No live receipt exists: SaaS OAuth/ownership/refresh/revocation, durable multiprocess credential service, model registration, policy/tariff and prospect/recipient/spend scope are BLOCKED.

Task14's actual registered accounting owner settles authoritative evidence only. Preserve unknown credit/USD holds, current operational membership, exact account/claim identity and reconciliation replay. Legacy missing account hashes fail closed. Content purge does not delete financial evidence. Native source deletion/export denial, bounded tombstone continuation and deadline-driven standalone provider purge remain required; root read fences apply before physical pages finish. API/worker purge routines require exact `pg_catalog,public,pg_temp` paths and qualified persistent relations; never broaden mutation grants to bypass them.

Disabling new sales dispatch preserves current-authority reads, cancellation and reconciliation. No flags, credentials, shared migrations, deployment or sending are performed by these preparation instructions. Use aggregate counts, statuses and authoritative cost totals only; exclude raw responses, person data and conversation text from telemetry.


Final-fix evidence lineage: `.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/final-fix-report.md`
and `final-fix-evidence/candidate-final.json` / `final-cases.json` in that SDD directory.
Task15 broad passes remain inherited. Scoped review accepted the original seven findings; controller follow-up corrected the two CI findings with 45 passing checks, without another independent review. Final identity and limits are in `controller-completion.md` and `controller-candidate-final.json` in that SDD directory;
live acceptance remains BLOCKED, phase incomplete, and hosted CI NOT_RUN.
