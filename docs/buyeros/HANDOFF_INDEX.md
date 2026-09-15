# BuyerOS plan index, decisions and current state

**Status: PROPOSED / PLAN ONLY.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). This is a handoff index, not Build approval.

No application code, lockfile, install, migration, cloud resource, deployment, Site access change, paid provider call, mailbox connection, message, or send is authorized by this document. The audited application source is imported at `b804ba8d1514a1049b7202c861278dd72c473a75` (tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`) and merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`.

- Canonical repository: `YNWAforever/BuyerOS`
- Planning pack committed at `1512d4c17d4f792e14598d524fdac3c9c37d27e7` (docs only)
- Base content commit: `b804ba8d1514a1049b7202c861278dd72c473a75`, tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`
- Sites source commit: `76892126c86031bfe8e7ab517adba7f306040313`; Site `appgprj_6aa82285e5108191aac9c44c840c5efe`
- Live Site: `https://fimmick-buyeros.laichiwillyjp.chatgpt.site` (public, active, revision 2; unchanged)

The import commit `b804ba8d…` carries tree `b4c6b538…`; `main` HEAD is the merge commit `72fef7d…`, whose tree combines source and docs.

## Task → design → plan map

| Tasks | Phase | Design spec | Implementation plan |
|---|---|---|---|
| BO-000…BO-003 | P0 decisions/contract | `decisions/BO-001-runtime-identity.md`; reviews recorded in `tasks/` | `plans/2026-09-15-p1-boundary-implementation.md` (contract work in BO-003) |
| BO-004…BO-006 | P1 boundary | `specs/2026-09-15-p1-boundary-design.md` | `plans/2026-09-15-p1-boundary-implementation.md` |
| BO-007…BO-012 | P2 foundation | `specs/2026-09-15-p2-persistence-foundation-design.md` | `plans/2026-09-15-p2-persistence-foundation-implementation.md` |
| BO-013…BO-016 | P3 discovery/fit | `specs/2026-09-15-p3-discovery-fit-design.md` | `plans/2026-09-15-p3-discovery-fit-implementation.md` |
| BO-017…BO-020 | P4 contact | `specs/2026-09-15-p4-contact-guardrails-design.md` | `plans/2026-09-15-p4-contact-guardrails-implementation.md` |
| BO-021…BO-025 | P5 draft/approval/export | `specs/2026-09-15-p5-draft-approval-export-design.md` | `plans/2026-09-15-p5-draft-approval-export-implementation.md` |
| BO-026…BO-029 | P6 hardening/pilot | `specs/2026-09-15-p6-hardening-pilot-design.md` | `plans/2026-09-15-p6-hardening-pilot-implementation.md` |
| BO-030 | P7 delivery (design only) | `specs/2026-09-15-p7-delivery-design.md` | `plans/2026-09-15-p7-delivery-design-implementation.md` |

Task manifest and dependency graph: `tasks/index.json`. Reading order and rules: `00_README_AND_DECISIONS.md`, `06_OPENCODE_EXECUTION_GUIDE.md`.

## Decisions recorded

| Decision | Value | Source |
|---|---|---|
| Runtime | Vinext 1.0.0-beta.5 / React 19.2.6 / TS / pnpm 11.25.0; frontend stays on Sites | ADR-01 |
| Identity | Auth0 OIDC, issuer `https://dev-oaug20cdxqqgn1s8.us.auth0.com/`, client `iVnUZbP4JsjRAJAHob1qmTSlZ0rgZU1R`; **must be reconfigured** to a public PKCE SPA client with the Site origin registered | BO-001 D3/D3a |
| Roles | viewer / operator / reviewer / admin with an explicit fail-closed matrix | P1 design |
| Tenant isolation | RLS + composite FKs + non-owner roles + transaction-local context | BO-005 |
| API/worker host | Render, Singapore; one image (web + worker); one Valkey | D4 |
| Database | Neon PostgreSQL `ap-southeast-1`; Alembic sole domain migration owner | D5 |
| Object store | Cloudflare R2, private, APAC jurisdiction (**revises ADR-08** from AWS S3) | D6 |
| Staging | default provider hostnames; no custom domain | D7 |
| Demo/live | `BUYEROS_MODE=demo|live`, profile-driven; live failure never returns fixtures | P1 design |
| Offer parsing | UTF-8 text/Markdown first; **PDF deferred** (no AGPL parser) | P2 design |
| Search | single provider-agnostic adapter behind a verified capability manifest; no waterfall | P3 design |
| Approval fingerprint | versioned canonical JSON with shared golden vectors | P5 design |
| Delivery channel | transactional ESP API (design only, never activated) | P7 design |

### Defaults recorded where a question was left unanswered

- **Contact provider:** single, capability-gated (bounded charge + status + idempotency-or-safe-unknown); contact path stays disabled until verified.
- **Approval fingerprint:** canonical JSON (alternative: raw-text hashing).
- **Delivery channel:** transactional ESP API (alternative: SMTP/IMAP or no decision yet).

These are defaults, not owner confirmations; change any of them and the affected spec/plan must be revised.

## Open blockers

| ID | Remaining | Resolving task |
|---|---|---|
| B-INPUTS | Missing `references/` pack contents (research source, Site projection, source register); no owner waiver | BO-000 / owner |
| B-OPENCODE | CLI not on PATH; desktop app v1.18.30 located; CLI version/effective permissions unverified | BO-000 / platform |
| B-IDENTITY | Auth0 app reconfigure (public PKCE + Site origin) and membership owner | BO-001/004 |
| B-HOST | Render/Neon/R2 accounts, service sizes, limits, staging hostnames | BO-001 |
| B-PROVIDERS | Search/LLM/contact account rights, bounded prices, status/idempotency/webhook semantics | BO-002 |
| B-POLICY | Market/entity/purpose, retention, controller scope, export/contact-research permission | BO-009 |
| B-LICENSE | Copied-file notices, dependency licenses, GPL deferral, parser review | BO-002 |
| B-APPROVAL | Explicit selected-task Build approval | every task |
| B-PILOT | Release evidence, capped spend, evaluation set, approved infrastructure | BO-028/029 |
| B-DELIVERY | Separate P7 sender/mailbox/policy and exact send authorization | BO-030 |
| B-MOBILE | Current E2E and keyboard/locale audit | BO-025 |

## Exact next action

1. (DONE) Audited source imported at `b804ba8d1514a1049b7202c861278dd72c473a75` and merged; BO-000 identity re-verifies against tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`.
2. Resolve B-IDENTITY (Auth0 reconfigure + membership owner) and B-HOST (accounts/sizes).
3. Approve **one** task (recommended: BO-005 or BO-004) with commit, allowed files/actions, approver and timestamp; then Build only that scope via `superpowers:subagent-driven-development` or `superpowers:executing-plans`.

## Status

No task is DONE. No acceptance test has been executed. Application implementation has not started. The plans are execution-ready only after the source import, the named blockers above are resolved, and a selected task is approved.
