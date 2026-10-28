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

## Conversation home — Stage 1 Preview

`NEXT_PUBLIC_CONVERSATION_HOME === 'true'` opts the **live** workspace into
Conversation home. Unset (default), `false`, or any other value retains the
#35/#37 OFF Overview, navigation, guards and reads. Preview is already enabled;
this change requires no Vercel environment edits. Production remains unset/OFF.

`/app` and `/app/discussions/new` offer six BuyerOS guided templates and a local
composer. `/app/discussions/<localId>` restores messages and selected source
references after refresh. Continue working lists only the current actor,
workspace and project's discussions, newest first. The two Stage 0 example
bookmarks remain template entry pages. All destination buttons use the existing
guarded navigation with workspace/project and any selected record IDs.

Messages are **saved on this device only, not shared**. A versioned, strictly
validated `buyeros.discussions.v1:<actor>:<workspace>:<project>` key uses encoded
scope components. Limits: 256 KiB UTF-8 per scope, 30 threads, 100 messages and
100 selected sources per thread, 4,000 characters per message. Invalid, foreign,
old-version or oversized payloads are ignored with a notice. A full limit refuses
additions and keeps existing data; unavailable storage keeps changes in the tab
with an honest notice. Sign-out clears session-owned memory caches. Source
selections persist only IDs and generic labels; filenames, document contents,
fact values, buyer records and draft bodies are never copied into the store.
Do not enter private buyer details, draft bodies or document text into messages.

Documents & outputs reads existing project records with current permissions:
offer documents/extraction state, candidate and approved facts, recent runs with
authoritative statuses, and the current UTC month's Results counts. Reads are
bounded and cached for the active session scope; Refresh project context explicitly
re-reads them. Missing permissions, partial lists, empty and unavailable services
are reported without blocking local discussion work. A fact is shown as approved
only with the authoritative active reviewer-approved current profile. Document
candidates always need reviewer approval. Offer context follows the existing
active-project/operator Offer gate; other retained surfaces keep their own gates.

Every BuyerOS reply is deterministic static **Guided step · no AI** copy in
English and zh-HK. Templates, Send, source selection and thread navigation make
no network calls. Project context uses existing GETs only; refreshing the page
or changing validated scope may reload context. Offer document links focus the
existing document row, run links open the existing run, Drafts and Saved results
remain links to existing work. Overview stays at `/app/overview`, with Offer,
Research runs, Buyers, Drafts, Results, Settings and Operations retained.

Out of scope: AI/LLM replies or citations; research starts, providers or paid
calls from chat; enrichment/contact quotes, approval, exports or sending; backend
or schema changes; server-side discussions, sharing/ACL; SME/GSC/Firecrawl/
DataForSEO, CRM/shared-library connectors or OAuth; Production enablement,
deployment/promotion, merging, or removal/restyling of retained work surfaces.

Checks: `node --test tests/audit-conversation-home.test.mjs`,
`node --test tests/conversation-home-responsive.test.mjs` (compiled Vercel CSS +
local Chromium), `pnpm test:core`, `pnpm exec tsc --noEmit`, `pnpm lint`,
`pnpm build`, and
`NEXT_PUBLIC_CONVERSATION_HOME=true node scripts/run-vercel.mjs build`.
