# BO-001 — Runtime, identity, deployment and migration decision record

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Task: BO-001. Owner approval: disposition approved in the Plan review session; this document is a decision-record input, not implementation approval.

No application code, lockfile, dependency install, database migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, commit or push is authorized or performed by this record. It does not activate Auth0 or any provider.

Base content commit (import baseline): `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. Sites source commit: `76892126c86031bfe8e7ab517adba7f306040313`. Site: `appgprj_6aa82285e5108191aac9c44c840c5efe`, `https://fimmick-buyeros.laichiwillyjp.chatgpt.site`.

Read with [00 decisions](../00_README_AND_DECISIONS.md), [02 architecture](../02_ARCHITECTURE_AND_REUSE.md), [03 contracts](../03_DATA_API_AND_STATE_CONTRACTS.md) and [05 test/security/release](../05_TEST_SECURITY_AND_RELEASE.md).

## Decisions

| ID | Decision | Status | Provenance |
|---|---|---|---|
| D1 | Canonical repository is `YNWAforever/BuyerOS`. Currently empty; an exact import of the audited source is expected, producing the same tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`. The content baseline remains `b804ba8d1514a1049b7202c861278dd72c473a75` until re-verified. | Owner-supplied; import NOT RUN | Owner; GitHub API |
| D2 | Preserve the Vinext 1.0.0-beta.5 / React 19.2.6 / Vite / TypeScript / pnpm 11.25.0 frontend. No Vercel or standard Next.js migration. Frontend stays on Sites/Cloudflare. | Verified source baseline; UNCHANGED | 01, 02 ADR-01 |
| D3 | Identity provider: managed Auth0 OIDC. Issuer `https://dev-oaug20cdxqqgn1s8.us.auth0.com/`; client ID `iVnUZbP4JsjRAJAHob1qmTSlZ0rgZU1R`. Browser Authorization Code + PKCE (public client), short-lived access token in memory, bearer to FastAPI; server verifies signature/issuer/audience/expiry/algorithm and looks up current Postgres membership. | Provider pinned; **app reconfiguration required** | Owner; ADR-07; 03 §4 |
| D3a | **Correction required:** the current Auth0 application is a `regular_web` confidential client using `client_secret_post`, with callback `http://localhost:3000/auth/callback` and logout `http://localhost:3000/`. Reconfigure to a **public SPA client** with **Authorization Code + PKCE**, register callback/logout for the Site origin `https://fimmick-buyeros.laichiwillyjp.chatgpt.site` (plus a dev origin if needed), and keep no client secret in the browser. Until reconfigured, live authentication stays disabled. | PENDING owner action | Owner report |
| D3b | Membership authority is the Postgres `memberships` table; roles operator / reviewer / viewer / admin. The **membership owner is not yet named** (only open identity item). | PENDING | 03 §3.2 |
| D4 | API + worker host: Render, region **Singapore**. One built Python image, one web service and one background worker; one **Valkey** broker on a persistent, non-evicting plan. The plan's proposed limits are carried as **defaults pending owner sign-off**: API non-streaming ≤15s, stream heartbeat 15s, run ≤30 min wall clock, fetch 15s, LLM step 45s, contact submit 20s, 4 concurrent provider operations per run with an initial per-provider semaphore of 1. | Owner-supplied (host/region); limits + service size PENDING | Owner; ADR-02/ADR-06; 02 |
| D5 | Database: Neon managed PostgreSQL, region `ap-southeast-1` (Singapore). Proposed default: a paid plan with backups, a pooling DSN for runtime and a direct DSN for migrations (final plan/size PENDING owner sign-off). SQLAlchemy/Alembic is the sole BuyerOS domain-schema migration owner. The empty Drizzle/SQLite scaffold remains unused for domain tables. | Owner-supplied (host/region); plan size PENDING | Owner; ADR-04/ADR-05 |
| D6 | Object storage: **Cloudflare R2**, private bucket, **APAC jurisdiction** to align with Singapore. Worker accesses it server-side over the S3-compatible API; downloads use short-lived, tenant-authorized signed URLs. The existing Sites R2 binding remains null and unused. This **revises ADR-08** from AWS S3. | Owner-supplied; provisioning NOT RUN | Owner; ADR-08 revised |
| D7 | Staging uses default provider hostnames (`*.onrender.com`); no custom domain or DNS. Site access is unchanged (public, active, revision 2); this record does not alter it. | Owner-supplied | Owner; 00 |
| D8 | Data locality: Singapore compute + Neon SG + R2 APAC processes operator and EU candidate/contact data in APAC. This is **flagged for the B-POLICY controller/processor review**; no legal sufficiency is claimed. | Open policy item | 05 §5 |

## One architecture, one migration owner

- Single domain API: FastAPI (proposed). Single worker runtime: Celery with one Valkey broker plus transactional outbox and DB leases. Single durable identity: Postgres.
- Single domain-schema migration owner: SQLAlchemy/Alembic. Drizzle stays a non-domain scaffold; no second Node domain backend, queue, or migration authority.
- No Kubernetes, Keycloak, Kafka, GPU host, vector service, or secondary queue is introduced. The FIMMICK acronym does not imply that infrastructure.

## Blocker disposition effect

| Blocker | Before | After this disposition |
|---|---|---|
| B-IDENTITY | Open | Mostly resolved: provider/tenant pinned. Remaining: Auth0 app reconfigure (D3a) and membership owner named (D3b). |
| B-HOST | Open | Mostly resolved: Render/Neon/R2/Singapore/hostnames chosen. Remaining: account provisioning (not authorized) and final service-size/limit sign-off. |
| B-POLICY | Open | Still open; D8 adds the data-locality item. |
| B-INPUTS, B-OPENCODE, B-PROVIDERS, B-LICENSE, B-APPROVAL, B-PILOT, B-DELIVERY | Open | Unchanged by this record. |

## Required follow-up documentation corrections (proposed; NOT applied)

1. ADR-08: change the proposed object store from AWS S3 to Cloudflare R2 (APAC jurisdiction).
2. ADR-07: state that the Auth0 application must be a public SPA client with Authorization Code + PKCE; record the tenant/issuer; add the reconfigure action D3a.
3. 02 architecture: record Singapore region, R2 private store, and default provider hostnames for staging.
4. BO-000 identity: record canonical repository `YNWAforever/BuyerOS` and the expected exact-import/tree re-verification.
5. 00 blocker register: update B-IDENTITY and B-HOST rows with the above and the D8 policy item.

## Verification evidence

| Check | Result | Status |
|---|---|---|
| Auth0 tenant discovery `https://dev-oaug20cdxqqgn1s8.us.auth0.com/.well-known/openid-configuration` | issuer matches; `authorization_code` and PKCE `S256` supported | VERIFIED (live, read-only) |
| GitHub `YNWAforever/BuyerOS` | public, default branch `main`; planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7` (docs only, root tree `66c5e1f8b4e4059fc666b09bffe296b7cc712b3c`); source still not imported | VERIFIED (read-only) |
| GitHub `YNWAforever/buyerosgpt` | public; HEAD `b804ba8d…`, tree `b4c6b538…` | VERIFIED (read-only) |
| Source checkout `git rev-parse HEAD` / `git status --short` | no checkout available in the review environment | **NOT RUN** |
| Render/Neon/R2 provisioning, Auth0 app reconfiguration, Site callback registration, membership owner | not performed | **NOT RUN / pending owner** |

No secrets (client secret, keys, DSNs) are recorded here; none should be added. This is a public-client PKCE design.

## Rollback / roll-forward

Supersede this ADR with a dated successor; no runtime or cloud rollback is required because nothing was provisioned or changed. If a later decision changes the app/host/store, revise the affected ADR and dependent tasks rather than layering a second scheme.

## Remaining NOT RUN / uncompleted

- Open items: Auth0 app reconfigure (D3a), membership owner (D3b), B-POLICY data-locality review (D8), all account provisioning and service-size sign-off.
- Product/application checks for BO-001: **NOT RUN**. BO-001 remains uncompleted; no task is DONE.
- This document is a new planning artifact and is not listed in the pack `SHA256SUMS.txt`; the pack manifest was not modified.
