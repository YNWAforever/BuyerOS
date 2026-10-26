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

## Existing records

[BuyerOS handoff index](docs/buyeros/HANDOFF_INDEX.md) and
[remaining-development status](docs/buyeros/REMAINING_DEVELOPMENT_STATUS.md) preserve
historical evidence and open activation decisions. Dated status tables,
[DEVELOPER_HANDOFF.md](DEVELOPER_HANDOFF.md), and the original architecture proposals
refer to their recorded commits; use the guides above and current source for commands.
