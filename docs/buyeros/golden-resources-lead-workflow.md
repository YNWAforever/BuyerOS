# Golden Resources Native lead workflow

Implementation date: 2026-10-16, Asia/Hong_Kong.

Authority: the approved specification and implementation plan in `docs/superpowers/`.
Execution checkout: `codex/golden-resources-lead-workflow-20261016`.
Application predecessor: `c42c9f40f5f99c5810980bb72885548335d1f1bb`.

## Scope and operating limits

The workflow separates company source checks, purchasing-person evidence, channel ownership,
content review and formal sending eligibility. Employment and procurement evidence have a
30-day review lifetime; channel ownership has a 7-day lifetime. Future observations are
rejected and exact expiry boundaries do not qualify.

The first-month targets are 24 company evidence cards, 8 priority companies, 6 companies
with a reviewed purchasing person, 4 with a source-verified direct channel, and 4 with
reviewed preparation content. These are distinct-company targets, not promises about
public data availability. Generic departmental mailboxes, forms, homonyms and technical
verification alone do not satisfy the named direct-channel criterion.

Paid research, all contact enrichment (including free tiers), and sending remain disabled.
Preparing content does not create a formal draft, recipient, provider operation, model
receipt, background job or delivery event. A saved USD10 policy does not activate a
provider or increase a native executable budget account.

No migration, deployment, production data write, provider lookup, enrichment, message,
role change or personal-account link is part of this delivery. Migration 0055 is local
and unpublished. Migration 0054, protected release workflows, formal draft eligibility
and signed-runtime publication requirements retain their existing semantics.

## Six-page workflow

| Page | Native behavior |
| --- | --- |
| Overview | Uses the backend distinct-company metrics; each number links to the same qualification criterion. An unavailable read is not zero. |
| Offer | Retains the original upload, download, extraction and ICP approval workflow. Preparations reference an approved ICP hash, offer revision and fact IDs. |
| Buyers | Separate manual observations and purchasing/channel review panels coexist with the original research Evidence, fit and company source checks. |
| Operations | Server-filtered manual queue by stage, owner and due date; dates are reminders and start no job. Canonical source changes refresh the contact panel without replacing unsaved text. |
| Drafts | Independent cited preparations support revisions, exact-content review, history and archive. A content review is not a formal send approval. |
| Settings | Combined monthly USD policy, native holds, external cost evidence, corrections, reconciliation and credits. Unknown history leaves remaining funds unknown. |

Original company source dates preserve their precision. A missing publication date stays
unknown. Where the existing product-fact contract has an attachment and excerpt but no
page, the UI explicitly says the page is unknown; it does not invent a slide number.
Image-only or incomplete extraction is visible and unsupported facts are not added to
templates.

## Save, scope and recovery

Every new write is prepared and applied through server-held, actor-scoped intents. The
original target, payload, action, submission key and precondition survive an uncertain
response. Reload recovery requires the existing normal sign-in again; no browser storage
is added for tokens or personal contact payloads.

A confirmed canonical readback precedes acknowledgement. Reading an already-applied
intent does not submit it again. Prepared operations require an explicit continuation or
cancellation. A stale edit preserves local text and shows the stored result separately.
Role and purpose checks run again on recovery and replay. Privacy expiry clears retained
copies rather than returning an old successful PII response.

The new schema forces tenant RLS and binds composite workspace/project/buyer/company and
person/channel references. Journals are append-only. Workers can read the non-private
pilot policy row to distinguish legacy projects, but a configured disabled pilot refuses
worker admission before private accounting reads. Workers do not receive SELECT on
private lead payloads. The existing retention sweeper receives only EXECUTE on the
tenant/deadline-checked erasure function. Normal maintenance discovers person-only
records and unapplied private intents through bounded tenant-scoped erasure; workers
receive no SELECT on private payload contents.

Purchasing reviews are scoped to their person/channel. A company qualifies when any
current subject qualifies, while a later rejection of that same person's role prevents
older channels from preserving a false qualification. A preparation follows its own
reviewed subject rather than another person's newer review. Its target changes only
through an explicit editor selection. The complete review journal has its own bounded
pagination. Human preparation reasons remain in erasable, subject/document-linked
original intent payloads; permanent audit records contain fixed reason codes.

## Monthly USD10 accounting

One policy covers all new third-party costs for this project. Amounts remain decimal
strings; the warning calculation uses integer microdollars. Native settlement and
external copies of the same operation are not counted twice. A settlement replaces its
commitment, corrections retain the original economic identity, and prepaid credit
consumption does not add the purchase cost again.

USD spending and provider credit units have independent periods and provenance. Fees,
minimum purchase and conversion evidence can remain incomplete, but that blocks a known
remaining amount. Shared external usage requires explicit reconciliation against the
current ledger version/hash. Actual overspend and old unresolved holds remain visible.
Billing periods use UTC, with a separate Hong Kong display.

## Verification and evidence boundaries

The execution ledger and retained discovery, JUnit and failure logs are in:

`.superpowers/sdd/2026-10-16-golden-resources-contact-workflow/`

The following are the exact required local inventories and receipt locations. Use the
final execution ledger and the actual reports for pass/fail status, rather than treating
this source document or a successful build as a verification receipt.

| Layer | Required evidence |
| --- | --- |
| API native inventory | 2,737 original cases plus 94 additions = 2,831; native discovery and `final-candidate-api.xml` must match exactly. |
| Worker | 469 original cases; native discovery and `final-candidate-worker.xml`. |
| Node clients / frontend guards | Full general Node report, separate server SDK and emitted-auth reports, plus six distinct lead client cases; empty file wrappers are rejected. |
| Root Python guards | 332 cases, including rejection of empty/missing/skipped reports. |
| TypeScript / generated contracts | TypeScript and both generation checks; 118 operations. |
| Builds | Default build and local Vercel build. Neither command deploys. |
| Browser | Fixed local Vercel bundle: lead 17, original source checks 5, import 4, native attachments 4, formal draft 1. `browser-final-matrix.json` binds each exact discovery/JUnit pair without skips. |
| Lint | Full lint report; three existing Hook warnings in `features/live/drafts.tsx` are separate from any new errors. |
| Remote CI / hosted company account / production | Not run or claimed in this implementation round. |

Browser fixtures are expressly fictional: `Fixture Rice Buyer 01` through `24`,
`Fixture Purchaser` and `.example.test` channels. Their 24/8/6/4 counts and prepared
content are not real Golden Resources purchasing contacts or business outcomes.

Earlier failures remain retained, including missing UI RED runs, a definitive-validation
client-cache regression, development-server startup/IPC failures, an unacknowledged
fixture setup intent, a built-link navigation failure and a sibling-panel stale-state
failure. They are not relabeled as passing.
The original 2,815-case full API attempt had two cold-cutover failures and is retained as
failed evidence even though its intended filename contained `green`. The final corrected
inventory is 2,831. Cold fixture setup explicitly permits read-only schema metadata for
the new exact-head compatibility check, retains every original positive/rollback/unknown
hold assertion, and adds the eight new empty actor-FK histories to the original six.
Only the reviewed 0039 and 0054 heads may omit the not-yet-installed lead policy; a missing
current or unknown-future feature schema is refused.

The original 10 untracked files, two backups (51,460 bytes), `.gitignore`, and PR23's
`codex/ci-pg16-image-preload-20261015` reference passed the preservation hash check in
`preservation.after.json`. No cleanup should delete this evidence workspace.

## Acceptance mapping

| Criteria | Local evidence |
| --- | --- |
| GR-01, GR-02, GR-03, GR-11 | `test_lead_intents_db.py`, `test_lead_evidence_db.py`, `lead-evidence.spec.ts`: exact recovery, partial independence, unchanged source-check/fit fields and revoked writes. |
| GR-04, GR-05, GR-06, GR-07 | `test_lead_progress_db.py`, `test_lead_quality.py`: distinct priority-company counts, purchasing duties, generic-channel exclusion and separate technical status. |
| GR-08, GR-09 | Quality boundary/conflict tests and preparation context tests; browser material-change and sibling-source tests. |
| GR-10 | Preparation API tests and browser read/review/history flows; zero provider, model, contact/search receipt, job, formal draft and send-event counters. |
| GR-12 | Existing disabled admission/delivery regressions plus the new worker-policy refusal and zero-side-effect preparation assertions. No live provider activation. |
| GR-13, GR-14, GR-15, GR-16 | `test_pilot_budget_db.py` and `pilot-budget.spec.ts`: atomic cap, economic identity, credit separation, reconciliation and UTC carry. |
| GR-17 | Predecessor-to-0055 source-check preservation test, unchanged original files and retained private fixture data. |
| GR-18 | Viewer/revoked tests, explicit unavailable reads, bounded pagination and bilingual status labels. |
| GR-19 | Original native attachment and buyer import browser suites; current approved product facts only. |
| GR-20 | This report labels source, local fixture, remote CI, hosted and production evidence separately. |
| RF-1–RF-5 | Original named API tests cover freshness, homonyms/shared ownership, revoked intent replay, retention copies and economic deduplication; final branch review must inspect these boundaries independently. |

## Release handoff

Keep this branch local until the separately authorized publishing/release process is
requested. Pushing may create a preview deployment, so local completion does not imply
push authorization here. A future release requires the exact candidate's required CI,
the protected signed-runtime workflow and fresh company-account/hosted acceptance.
Real lead enrichment or outreach needs its own authorization; this implementation
provides no activation shortcut.
