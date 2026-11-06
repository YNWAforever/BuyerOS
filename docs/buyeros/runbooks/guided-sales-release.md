# Bounded guided-sales release preparation

Status: **LIVE BLOCKED; phase incomplete; no activation authorized.** Local fixture verification is recorded in `GUIDED_SALES_ACCEPTANCE.md` and the Task15 report. It does not authorize Git mutation, production flags, credentials, migrations, paid calls, push or deployment.

## Candidate and approval receipt

Use the exact `source.json` candidate SHA-256 (sorted path/content hashes including uncommitted source), Git HEAD, build/wheel hashes, command receipts and per-case results. HEAD alone is insufficient. After any source change attach a new manifest and identify affected verification. Independent Task15 review and final whole-branch review are controller-owned prerequisites.

A future approver must fill every field; an empty/null field is BLOCKED, never zero spend or approval:

| Field | Required value before live work | Current status |
|---|---|---|
| source/artifacts | candidate hash, review verdicts, UI/API/worker artifact hashes | local review/follow-up recorded; exact release artifact approval outstanding |
| target | exact environment, workspace/project IDs, current initiating/admin actor references | BLOCKED |
| SaaS account | provider account and project-assigned connection references; ownership and allowed processing evidence | BLOCKED |
| OAuth | SaaS registration, refresh/rotation and revocation proof, account compatibility | BLOCKED |
| credential storage | durable multiprocess secret-provider reference and recovery/rotation proof; no secret values | BLOCKED |
| model | reviewed selected model/route/account registration, prompt/schema versions | BLOCKED |
| policy/tariff | approved purpose/retention, source permission, exact policy and credit-to-currency tariff versions | BLOCKED |
| subjects | exact approved prospect IDs/domains, selected identities and permitted recipient scope | BLOCKED |
| provider ceiling | maximum integer credits, page/results and tool-specific caps | BLOCKED |
| money ceiling | exact Decimal maximum and currency; separate model and provider liabilities | BLOCKED |
| authority | approver identity, timestamp, expiry and exact action receipt | BLOCKED |
| rollback | named operator, dispatch-disable target, read/reconcile recovery checks | BLOCKED |

Never place tokens, personal records, provider bodies or conversation text in this receipt. References and content digests are sufficient. Missing commercial terms cannot be replaced by estimated token bills.

## Exact prospective scope

Only `search_company_xverum`, `search_people_xverum`, `enrich_company_xverum`, `enrich_person_xverum` and `get_email_xverum` may be proposed. Copy the exact five allowed tool IDs from the candidate registry into the approved receipt. Phone, reverse lookup and job-change tools remain disabled. Limit company search to one page/five results and one selected company detail; people search to one page/five results; at most three explicitly selected person details. Email requires an explicit selected-person quote. These are maximum design bounds, not an authorization to spend them.

Search approval binds query, actor/project/connection generation, policy/tariff, page/result limit, expiry and maximum credits/currency. It does not authorize unknown downstream IDs. Select identity after seeing candidates; obtain a distinct exact detail/email quote. Any scope expansion requires a new review. Do not infer employment or decision authority from title/name alone.

The separately authorized live journey must demonstrate search → ambiguous identity selection → approved detail → field review → native CAS save → canonical reload/provenance → saved research and authored outreach/native eligible draft. Verify reconnect/event replay without redispatch, lost-response held liability and evidence-based reconciliation, current-account OAuth refresh and revocation, and access revocation after saving. No sending, scheduling or autonomous approval belongs to this scope.

## Feature enablement and non-destructive rollback

Keep `BUYEROS_SALES_SKILLS_ENABLED=false` and workspace opt-in empty until exact-target activation approval. Preserve `NEXT_PUBLIC_CONVERSATION_HOME`; introduce no public sales flag. The current authenticated capability read combines server enablement and workspace opt-in. Registrations remain unselected by default; credentials alone never select a model/provider.

After an independently authorized release, rollback new admission/dispatch by disabling the server sales flag or removing only the approved workspace opt-in. Verify new work is rejected and saved outputs/native records remain accessible to currently authorized users, with cancellation, reconciliation and operational recovery available. Do not delete outputs, clear unknown holds, revoke read grants, remove recovery routes or downgrade populated financial/content tables. Preserve native payer, suppression, approval, source-retention and lifecycle authority.

The current undeployed schema head is `0065_sales_lifecycle`. Owned verification covers 0059→0065, empty round trips, current API/worker role readiness and populated downgrade refusal. Production migration requires its own exact-target approval, backup/recovery receipt and runtime readiness evidence. A fixture migration is not production permission.

## Nonbillable reproduction and telemetry

Run guard tests first, then `python services/api/tools/run_sales_isolated.py --allocate-owned --evidence <new-directory>` from the repository root with the installed API environment. Clear inherited `BUYEROS_*` and `NEXT_PUBLIC_CONVERSATION_HOME` before invocation. Before creating even an evidence directory, the runner validates the explicit mandatory 28 sales/Xverum and 11 native test files, rejects inherited database/provider credentials, and resolves the effective explicit/default Docker context to a local engine. The verified context is pinned through allocation; context drift aborts mutation. Successful Docker creation IDs are recorded immediately in `allocations.json`, before readiness. Failed-create/collision names never authorize removal; timeout cleanup requires the recorded exact ID and matching image/name/ownership label. `--case` is a bounded affected mode and is never reported as full-suite execution; do not weaken the guard or pass a shared DSN. Use local Docker only and run PostgreSQL suites sequentially. `SALES_PNPM_CJS` may identify the pinned cached pnpm entry on Windows; CI uses Corepack. Retain every allocator receipt and exact-ID removal verification.

Per-case reports contain identifiers, candidate hashes, classification, PASS/FAIL/BLOCKED/NOT_RUN and durations. Fixture wall time is not user time-to-output. Production metrics require a separately approved aggregate pipeline: task count, saved-output count, corrections, unresolved failures, latency aggregates and authoritative settled cost totals separated by currency/provider credits. Leave unmeasured metrics null; establish a baseline before claiming improvement. Never record user text, recipient identity or raw payloads in telemetry.




Before a local cold-cache invocation, clear inherited application target/credential variables and run
`services/api/.venv/Scripts/python.exe services/api/tools/run_sales_isolated.py --prepare-local-image`
(Unix: `.venv/bin/python`). This explicit preparation verifies the effective local Docker context,
pulls only `postgres:16` when absent, and verifies its immutable image ID. Then invoke the strict
`--allocate-owned --evidence <absolute-fresh-directory>` runner separately. Allocation still refuses
an unverified image and checks full container ID, labels and mounts; preparation does not authorize
shared databases or remote engines. Hosted CI remains NOT_RUN. The browser bridge uses pnpm on PATH by default; `SALES_PNPM_CJS` is an explicit optional script override.


Final-fix evidence lineage: `.superpowers/sdd/2026-11-05-guided-sales-skills-xverum/final-fix-report.md`
and `final-fix-evidence/candidate-final.json` / `final-cases.json` in that SDD directory.
Task15 broad passes remain inherited. Scoped review accepted the original seven findings; controller follow-up corrected the two CI findings with 45 passing checks, without another independent review. Final identity and limits are in `controller-completion.md` and `controller-candidate-final.json` in that SDD directory;
live acceptance remains BLOCKED, phase incomplete, and hosted CI NOT_RUN.
