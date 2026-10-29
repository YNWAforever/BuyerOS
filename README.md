# BuyerOS

BuyerOS supports buyer requirements, evidence-backed research, buyer review and lists,
contact-lookup quotes, and reviewed outreach drafts. The browser has separate **demo**
and **live API** adapters. Fixture tests do not establish provider or production readiness.

- [Architecture, risk map and next engineering investments](ARCHITECTURE.md)
- [Run locally, test and update contracts](docs/DEVELOPMENT.md)
- [Build, stage, promote and roll back](docs/DEPLOYMENT.md)

## Quick start: local demo

Use Node 24 (minimum 22.13.0), pnpm **11.25.0** and the committed lockfile.
Run from the repository root:

```sh
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open `http://localhost:5173/app`; `/` is the bilingual marketing site. Leave
`BUYEROS_API_BASE_URL` unset for the demo. A configured API with invalid auth fails
closed rather than substituting demo buyers. On a clean clone the execution profile
is portable. Sites-managed checkouts use the plugin's preview lifecycle; see
[execution profiles](docs/DEVELOPMENT.md#execution-profiles).

## Fast checks: no external services

```sh
corepack pnpm test:core
node tests/domain-checks.mjs
node tests/live-adapter-checks.mjs
corepack pnpm exec tsc --noEmit
corepack pnpm lint
```

`test:core` executes named Node tests for research admission/retry, streamed progress,
scope changes and private draft recovery. It needs installed JavaScript dependencies,
not a database, browser, login or provider credentials. The broader
[verification ladder](docs/DEVELOPMENT.md#verification-ladder) covers API, worker,
controller and browser integration; CI is in
[buyeros-ci.yml](.github/workflows/buyeros-ci.yml).

## Runtime boundaries

| Area | Source / authority |
| --- | --- |
| Marketing and workspace UI | `app/`, `features/`, `locales/` |
| Browser API/auth/scope boundary | `services/live/`, `lib/auth/` |
| Domain API, policy, budgets and persistence | `services/api/buyeros_api/` |
| Domain migrations | `services/api/alembic/` — Alembic is the sole owner |
| Background execution | `services/worker/` (Celery/Valkey); `services/cloudflare-jobs/` is the alternative controller |
| Public contracts and generated browser types | `docs/buyeros/contracts/`, `services/generated/` |
| Release controls | `.github/workflows/buyeros-{runtime-bundle,promote}.yml`, `scripts/protected-runtime.py` |

The Vercel target builds the app and internal FastAPI service; the default Vinext
build emits a Cloudflare Worker for the frontend. These are different artifacts.
Root D1/Drizzle files are optional starter examples, not the BuyerOS domain database.

Paid research, contact lookup and delivery require their own runtime, policy,
provider and budget gates. Building or opening a PR does not enable them.
Deployment instructions describe the checked-in controls, not a claim that a given
release is live.

## Live API request recovery

The shared browser API client bounds GET/HEAD/OPTIONS requests and text exports to
30 seconds, and mutations to 120 seconds to accommodate the API's 90-second
execution budget. One deadline covers transport, the existing single 401
refresh/replay, and reading the response body. A deadline aborts the request and
surfaces `REQUEST_TIMEOUT`; scope changes or unmount cancellation remain silent.
Timers and caller-signal listeners are released when the request settles.

A timeout does not confirm whether a write committed. The client never
automatically replays a timed-out write: use the flow's status/readback action or
retry its retained command with the same idempotency key and payload. No schema
migration, new environment variable, or caller API change is required.

`node tests/audit-request-lifetime.test.mjs` verifies stalled fetches, response
bodies and token refresh, cancellation, late responses, cleanup and retained
write intents with virtual time. The existing frontend CI audit glob includes it.

## Existing records

[BuyerOS handoff index](docs/buyeros/HANDOFF_INDEX.md) and
[remaining-development status](docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md) preserve
historical evidence and open activation decisions. Dated status tables,
[DEVELOPER_HANDOFF.md](DEVELOPER_HANDOFF.md), and the original architecture proposals
refer to their recorded commits; use the guides above and current source for commands.

## Conversation home — Stage 4 Connections (Google Drive) Preview

Stage 4 adds admin-managed, read-only Google Drive Connections through a
Fimmick-owned OAuth/MCP gateway. Admins approve folder IDs; members select only
approved item IDs with generic labels. Current access is rechecked on selection
and Ask; disconnect and approval changes invalidate previous Drive references.
HK residency is preferred and content cache retention is zero. No Drive bodies,
filenames or tokens are persisted. Drive grounding stays in request memory and
cannot enter existing paid model receipts; AI admission remains unavailable by
default. Gateway credentials/Google consent are provisioned separately; missing
configuration is honestly unavailable. No environment or secret changes are made.

[Stage 4 route, schema, gateway contract and proof details](docs/buyeros/CONVERSATION_CONNECTIONS_STAGE4.md).
Alembic head is **0059_conversation_connections**; Stage 3's 0058 history below is retained.

`NEXT_PUBLIC_CONVERSATION_HOME === 'true'` opts the **live** workspace into
Conversation home. Unset (default), `false`, or any other value retains the
#41 OFF Overview, navigation, guards and reads. Preview is already enabled;
this change requires no Vercel environment edits. Production remains unset/OFF.

`/app` and `/app/discussions/new` offer six BuyerOS guided templates and a local
composer. `/app/discussions/<localId>` restores messages and selected source
references after refresh. Continue working lists device discussions plus owned and explicitly shared workspace
discussions for the current actor, workspace and project, newest first. The two Stage 0 example
bookmarks remain template entry pages. All destination buttons use the existing
guarded navigation with workspace/project and any selected record IDs.

New discussions still default to **saved on this device only, not shared**. A versioned, strictly
validated `buyeros.discussions.v1:<actor>:<workspace>:<project>` key uses encoded
scope components. Limits: 256 KiB UTF-8 per scope, 30 threads, 100 messages and
100 selected sources per thread, 4,000 characters per message. Invalid, foreign,
old-version or oversized payloads are ignored with a notice. A full limit refuses
additions and keeps existing data; unavailable storage keeps changes in the tab
with an honest notice. Sign-out clears session-owned memory caches.
Browser writes use a per-scope local lock. A stale tab refuses to overwrite
another tab's saved changes and asks you to copy unsaved work before reloading.
Browsers without local lock support keep edits in the tab instead of persisting.
Source selections persist only IDs and generic labels; filenames, document contents,
fact values, buyer records and draft bodies are never copied into the store.
Do not enter private buyer details, draft bodies or document text into messages.

**Save to workspace** opens an explicit per-thread confirmation. It imports only
user notes, title, template ID, source IDs/generic labels and run IDs/labels/status;
AI replies and citations are excluded. No existing device thread is auto-uploaded.
The device copy stays until you explicitly remove it after a successful save.
Uncertain saves retain the same request key and import snapshot for retry in this
session. Workspace threads reopen at `/app/discussions/s/<uuid>` after refresh or
in another signed-in browser. Device and workspace storage are clearly badged.

Workspace threads are private until their owner shares them with named active
members of the same workspace with project-view permission. `viewer` can read;
`editor` can append notes and references. Only the owner can rename, share, change
roles, revoke or hard delete. Workspace admins cannot override a private thread.
Membership, project access and current shares are rechecked on every request and
before replay; revoked/deactivated access returns 404 without exposing existence.
Viewers cannot Ask/research into shared threads. Editor Ask and research retain
the existing Offer/startRun gates; only notes and run references are persisted.

Server limits: 200 owned threads per actor/project, 25 shares per thread, title
80 characters, 100 notes/sources/run references, 4,000 characters per note.
`Idempotency-Key` fences imports, appends and grants. `If-Match` fences mutations;
stale writes ask you to copy unsaved text and reload, and unavailable writes keep
the composer text. Thread caches/intents are scope-bound and cleared on sign-out
or scope change. The new API returns 404 when the flag is not exactly `true`.

Alembic **0058_conversation_threads**, after historical 0057, adds three FORCE RLS
tables with tenant/project composite FKs and API-only least-privilege grants.
Source/run refs use bounded, DB-validated JSONB so reference replacement is atomic
with the thread version; notes and shares have separate relational rows. All three
receipt-writable fences now point to 0058. Empty downgrade restores 0057; populated
downgrade refuses to erase user data. No seeded data, worker grants or admission
changes. [Stage 3 API and schema details](docs/buyeros/CONVERSATION_THREADS_STAGE3.md).

Documents & outputs reads existing project records with current permissions:
offer documents/extraction state, candidate and approved facts, recent runs with
authoritative statuses, and the current UTC month's Results counts. Reads are
bounded and cached for the active session scope; Refresh project context explicitly
re-reads them. Missing permissions, partial lists, empty and unavailable services
are reported without blocking local discussion work. A fact is shown as approved
only with the authoritative active reviewer-approved current profile. Document
candidates always need reviewer approval. Offer context follows the existing
active-project/operator Offer gate; other retained surfaces keep their own gates.

For device threads, templates and Send retain deterministic **Guided step · no AI** copy in English
and zh-HK. These actions, source selection and thread navigation make no network
calls. Project context uses existing GETs only; refreshing the page
or changing validated scope may reload context. Offer document links focus the
existing document row, run links open the existing run, Drafts and Saved results
remain links to existing work. Overview stays at `/app/overview`, with Offer,
Research runs, Buyers, Drafts, Results, Settings and Operations retained.

Stage 2 follows roadmap #38: **Ask BuyerOS** is a separate explicit action for
1–20 selected sources. It sends only the current question, source IDs and language
through SessionScope. The flag-gated API re-resolves membership, active project,
approved active/current profile and document retention/provenance under tenant RLS.
Only selected approved facts or a selected document's reviewer-approved excerpts
qualify; extraction candidates, model inferences, runs/results, missing/foreign or
partially unavailable selections fail closed. No source bodies or history travel
from the browser. Source checks never create a research, quote or enrichment job.

**Research from a discussion requires an explicit confirmation.** Propose research
loads the current approved profile, ledger budget remaining, and any configured
shared pilot cap. The confirmation sheet shows maximum USD cost, target companies
and every run limit. Confirm calls the existing `startResearch` / `startRun`
endpoint with an Idempotency-Key; `admit_run` still checks permission, capability,
provider, approved ICP, current policy and budget. Known refusals are localized in
en/zh-HK and cannot imply success. An uncertain request retains its original key;
check Research runs before retrying. Only run IDs, generic labels and statuses
are saved in local threads (at most 100 references). Refresh run status reads the
existing snapshot; run links retain existing partial results, timeouts, cancel and
safe retry controls. Templates, Send and AI outputs never start research.

**Live conversation admission remains OFF by default.** `ROUTE.route_id=None`
and the separate code-owned conversation `REGISTRATION=None` return
`CONVERSATION_MODEL_UNAVAILABLE` (503), even if a fit provider is selected. There
is no environment/request fixture or conversation route selector. Activation
requires a separately reviewed conversation registration/account/contract, paid
admission and dispatch switches, current membership, approved selected sources,
exact `research.model` policy with selected document IDs, and approved budgets.
Facts without an approved document policy scope remain blocked.

Alembic **0057_conversation_model** adds a tenant-fenced API-only receipt
transition function and conversation document/profile retention dependencies;
it does not seed approvals, accounts, prices, selection or work. The new
`conversation` budget category starts at zero through existing account creation
and is exposed only with the feature flag. Maximum liability is code-owned
**USD 0.100000**. Preparation atomically reserves through `reserve_operation`
(including shared pilot accounting), inserts a ProviderOperation, a terminal
`conversation.model` outbox fence that workers cannot claim, and a model receipt.
The new `conversation-basis.v1` has no run/buyer/company requirement. A second
short transaction rechecks authority and commits one claim before any external
await. No DB transaction/lock spans model HTTP. The route has no tools, 6,000 input
and 1,000 output tokens, a 30-second deadline and no repair/retry loop. Output must
be `needs_review`, with citations strictly within the selected source IDs.

Unknown, timeout, cancelled and received operations all retain their original
hold until authoritative billing reconciliation; token counts never settle
money. Concurrent reservations cannot exceed workspace/project/category or pilot
limits; same-key replays cannot submit twice. Conversation receipts use the
existing private retention/erasure boundary, capped at one day and the shortest
selected document retention. Populated 0057 downgrade refuses to erase liability;
empty downgrade restores the 0056 fences and dependency function.

Live reply text stays in memory only and is not saved in localStorage. Only test
fixture replies may restore bounded text and generic citation locators. Unknown
fields, URLs, unselected citations, tools/refusals and malformed output are
rejected. Citation buttons use guarded navigation. Scope, route, source or
permission changes discard in-flight replies. Error states keep the question.
Preview stays true, Production stays unset, and this change edits no environments.

Out of scope: enrichment/contact quotes, approval, exports or sending from chat;
SME/GSC/Firecrawl/DataForSEO,
connectors/OAuth beyond the approved Google Drive adapter; paid live Preview/Production smoke or any
environment edits; Production enablement, deployment/promotion or merging;
auth/Neon/delivery eligibility changes or removal of retained work surfaces.

Checks: `node --test tests/audit-conversation-home.test.mjs`,
`node --test tests/conversation-home-responsive.test.mjs` (compiled Vercel CSS +
local Chromium), `pnpm test:core`, `pnpm exec tsc --noEmit`, `pnpm lint`,
`pnpm build`, and
`NEXT_PUBLIC_CONVERSATION_HOME=true node scripts/run-vercel.mjs build`.
API/DB checks: `cd services/api && uv run --frozen pytest tests/test_conversation_threads_db.py tests/test_conversation_threads_api.py tests/test_conversation_reply.py tests/test_conversation_reply_db.py tests/test_conversation_model.py tests/test_conversation_admission_db.py tests/test_conversation_research_db.py`
(database cases require the existing disposable PostgreSQL fixture).
