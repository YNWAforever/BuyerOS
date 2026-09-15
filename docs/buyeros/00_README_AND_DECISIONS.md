# FIMMICK BuyerOS implementation planning package

Plan revision: v1 · Audit date: 2026-09-14 UTC / 2026-09-15 Hong Kong · Mode: PLAN ONLY.

## Executive decision

Build a **live research, optional business-contact lookup and reviewed-draft pilot**, incrementally through the existing BuyerOS interface. Delivery remains a separately approved phase. No implementation is authorized or completed by this package. The primary architecture is decided as a proposal; vendor tenancy, commercial terms and deployment activation remain explicit gates.

The exact project is **verified**. The owner-confirmed canonical repository is [YNWAforever/BuyerOS](https://github.com/YNWAforever/BuyerOS), which now holds this planning pack at commit `1512d4c17d4f792e14598d524fdac3c9c37d27e7`; the audited content baseline [YNWAforever/buyerosgpt](https://github.com/YNWAforever/buyerosgpt) commit `b804ba8d1514a1049b7202c861278dd72c473a75` is imported at tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1` and merged into `main` via `72fef7da785624a35bb6701f1451ebcf0184a089`. Its Git tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1` exactly matches the available Sites checkout at commit `76892126c86031bfe8e7ab517adba7f306040313`. Sites version 1 names that same source commit. `.openai/hosting.json` identifies `appgprj_6aa82285e5108191aac9c44c840c5efe`. Current Sites metadata identifies title **FIMMICK BuyerOS — Review Workspace**, slug `fimmick-buyeros`, live URL `https://fimmick-buyeros.laichiwillyjp.chatgpt.site`. Current access is **public**, active, revision 2; the audit did not change access. Exact commit links: [GitHub import](https://github.com/YNWAforever/buyerosgpt/commit/b804ba8d1514a1049b7202c861278dd72c473a75).

Verified stack: **Vinext 1.0.0-beta.5 / Vite 8.0.13 with Next App Router APIs, React 19.2.6, TypeScript 5.9.3, Tailwind 4.2.1, pnpm 11.25.0**. The existing build targets a Cloudflare Worker through Sites. This is not an assumed standard Next.js/Vercel app. Empty Drizzle/SQLite scaffolding and unused ChatGPT identity helpers exist; no BuyerOS domain backend, database binding, worker, queue or provider integration is present in inspected source.

## Input inventory and completeness

| Requested input | Actual access and reading | Evidence status |
|---|---|---|
| `01_CODEX_PLANNING_MASTER_INSTRUCTION.md` | That exact filename/unpacked pack was not supplied. Uploaded `FIMMICK_BuyerOS_Codex_Astra6_OpenCode_Planning_Instruction_v1(1).md` and `(3).md` contain the planning master, read completely using local text reads. Their bytes are identical. | PROVIDED_EQUIVALENT_FILENAME |
| Master upload hash | SHA-256 `3cc6f3ffdc2cfa1887ba55611cdd5e58e56aa72f73ef5c2f9ef992ee5ee651d1` for both copies | VERIFIED |
| `references/BUYEROS_FRONTEND_MASTER_INSTRUCTION_v1.md` | Exact references directory absent. Earlier local upload `FIMMICK_BuyerOS_ChatGPT_Sites_Frontend_Master_Instruction_v1(2).md` found at `/workspace/scratch/4686e5eec5a1/upload/`, read as the earlier frontend specification. Equivalence to missing renamed reference is not byte-proven. | EARLIER_SPEC_READ |
| `references/BUYEROS_RESEARCH_SOURCE.md` | Not in supplied uploads or discovered local files. | NOT PROVIDED / NOT READ |
| `references/SITE_PROJECTION.txt` | Not supplied; master describes its limited content, but projection itself was not read. Fresh Site and source evidence replace no missing source silently. | NOT PROVIDED / NOT READ |
| `references/SOURCE_REGISTER.md` | Not supplied; original research SHA cannot be independently checked. | NOT PROVIDED / NOT READ |
| Original research uploads (1)/(2) | User/master say identical; original bytes absent. Treat as one reported source, not independent corroboration. | OWNER-REPORTED, NOT REHASHED |
| Current source | Read exact available checkout, manifests, routes, adapters, fixtures, deployment, schema, instructions and tests. | SOURCE_VERIFIED |
| Current Site | Authorized browser inspection, 1348×936 desktop CSS viewport; synthetic controls only. See browser ledger in 01. | OBSERVED_UI / LOCAL_DEMO_VERIFIED |
| OpenCode installation | No `opencode` executable on this environment PATH. No installation performed. | VERSION UNVERIFIED; version command NOT RUN |

The supplied bytes are retained for handoff as [planning master](inputs/PLANNING_MASTER.supplied.md) and [earlier frontend specification](inputs/FRONTEND_SPEC.earlier-upload.md). These planning snapshots do not reconstruct the absent references directory. No Library reads were used for the uploaded attachments. Missing pack paths are relative to the input pack, not presumed repository files. Input reconciliation is incomplete and remains B-INPUTS; this package does not claim all absent references were read.

## Decisions and source conflicts

| Topic | Report/master position | Frontend specification/current source | Proposed resolution and rationale | Approval / blocker | Evidence |
|---|---|---|---|---|---|
| Source identity | Earlier planning master had no confirmed repo | Owner confirms canonical repo YNWAforever/BuyerOS with audited baseline buyerosgpt imported (commit b804ba8d, tree b4c6b538) and merged via 72fef7d; tree parity verified | Use this repository and preserve current files; no replacement app | Owner-specified, identity verified | 01 identity ledger |
| Frontend foundation | Report is described as recommending AI_Find_Customer web foundation | BuyerOS already has a coherent Vinext workspace | Preserve BuyerOS; selectively adapt upstream backend capabilities | Proposed architecture review BO-001/002 | Source audit; upstream matrix |
| FIMMICK acronym | Master reports Keycloak/Kubernetes/Terraform/Helm acronym | No such infrastructure in source | Not corporate infrastructure evidence; exclude unnecessary infrastructure | No architecture permission implied by acronym | Original report absent; explicit provenance caveat |
| Runtime | Generic React/TS preference | Vinext + Next App Router APIs + Cloudflare plugin | Keep runtime/router/lock; no Next migration. Vercel portability is optional later spike | BO-001 | package.json, vite.config.ts |
| Domain schema | Report favors PostgreSQL | Empty SQLite Drizzle scaffolding, null D1 | New domain tables owned only by Python SQLAlchemy/Alembic; retain scaffold unused | BO-003/005 approval | db/schema.ts; migration journal |
| Sending | Report described as including sending/reply sync | Frontend disables delivery; source no transport | MVP-A research/contact/draft; P7 separate sender decision | B-DELIVERY | User requirement and source |
| Fit/contact | Demo uses Company fit/review plus overwritten contact suppression label | User requires fully separate dimensions | Tenant-local company plus project buyer, immutable fit, reviews, validity, suppression and purpose policy | BO-003/005/009 | services/contracts.ts; Workspace suppression handler |
| Quote lifecycle | Demo reserves at dialog open; expired holds no longer counted | Live unknown provider result may still be charged | Quote itself not a hold; confirm atomically reserves. Submitted/unknown holds never age out as unused quotes | BO-010/017–020 | services/mock-client.ts; 03 invariants |
| Search upstream | README describes multiple search channels | Pinned AI_Find_Customer active search node is Maps-only; evaluate means continuation | Reuse specific insight/query ideas; independent bounded public-web search adapter | B-PROVIDERS | UPSTREAM_AUDIT |
| OpenOut licensing | Master described OpenOutreach/OpenOutFind GPL | Pinned orchestrator/finder GPL, sender MIT, ranking dependency GPL | Component-level notices and obligations; optional GPL path excluded from primary pilot | B-LICENSE optional | UPSTREAM_AUDIT |
| Prices/timing/retention | Report examples and estimates unavailable for full inspection | Demo USD6.60/0.30 are fictional | No price/effort promise; pricing capability record and configurable retention required | B-PROVIDERS/B-POLICY | 03/04/05 |
| Site visibility | Saved master says custom | Current Sites response public | Record current public state; do not change it | No change requested | Live metadata read |
| Instructions | README says npm installation | Manifest/wrappers/lock say pnpm11.25.0 | Follow executable pnpm conventions; propose README correction later | BO-000 | Source files |

## Binding invariants

I-01 Exact BuyerOS identity and existing account-first journey stay intact. I-02 Server verifies actor and tenant for every record, file, event and background action. I-03 Fit is tied to immutable profile/evidence; human acceptance is separate. I-04 Contact validity never implies purpose permission. I-05 Research-contact, draft preparation, export and outreach policy are separate, versioned, fail-closed decisions. I-06 All paid operations reserve a bounded upper amount atomically across applicable budgets. I-07 Unknown provider acceptance retains its hold and cannot blindly retry. I-08 Exact revision/recipient/evidence/policy approval becomes stale after material change. I-09 Demo and live stores/providers never silently mix. I-10 Copy/export/manual outcome never equals delivery. I-11 No sender exists in enabled MVP-A capabilities. I-12 Schema, queue and financial ledger each have one authority.

## Blockers and approval register

| ID | Missing decision/evidence | Owner / resolving task | Scope blocked |
|---|---|---|---|
| B-INPUTS | Original references directory/report/projection/register or explicit acceptance of this reduced provenance | Owner + architect / BO-000 | Final source-conflict sign-off; no claim of complete source-pack review |
| B-OPENCODE | Version/help and effective rules in actual executor environment | Platform / BO-000 | Version-specific config and automation; none emitted active |
| B-HOST | Render API/worker (Singapore), Neon PostgreSQL (`ap-southeast-1`), Cloudflare R2 (APAC), staging on default provider hostnames are **selected**; remaining: account provisioning, service-size/runtime-limit sign-off and privacy/data-locality review | Owner + platform / BO-001 | Resource creation and live deployment; local design can be reviewed |
| B-IDENTITY | Auth0 OIDC selected and tenant `dev-oaug20cdxqqgn1s8.us.auth0.com` supplied; remaining: reconfigure the app from `regular_web`/`client_secret_post` to a public Authorization Code + PKCE client and register the Site callback/logout origin, and name the membership owner | Security + owner / BO-001/004 | Live authentication and all live tenant API access |
| B-PROVIDERS | Named search/LLM/contact provider account rights, versioned price bounds, timeout/idempotency/status/webhook semantics | Provider owner / BO-002 | Each respective live paid adapter; fixture development can follow approved contracts |
| B-POLICY | Market/entity/purpose decisions, retention/deletion, client/controller scope, export and contact-research permission | Data owner + qualified reviewer / BO-009 | Live personal-data lookup/exposure/export and outreach preparation where policy unknown |
| B-LICENSE | Exact copied file notices, resolved dependency licenses; optional GPL strategy; parser dependency review | Architect/commercial reviewer / BO-002 | Unreviewed copies, GPL optional integration, problematic PDF parser |
| B-APPROVAL | Explicit approval of selected task with current commit, files and tests | Owner / each task | Build actions; plan approval does not authorize all tasks |
| B-PILOT | Concrete release evidence, capped provider spend, selected real-company evaluation set, approved infrastructure | Owner / BO-028/029 | Any live pilot activation or paid smoke check |
| B-DELIVERY | Separate P7 sender, mailbox/domain, policy, bounce/reply/opt-out and exact send authorization | Owner / BO-030 | All real delivery; never automatically unlocked by P6 |
| B-MOBILE | Current 390/768/1280/1440 E2E and full keyboard/locale audit not run in this session | QA / BO-025 | Responsive release sign-off, not source identity |

## Package and reading order

1. [01_SOURCE_AND_UI_AUDIT.md](01_SOURCE_AND_UI_AUDIT.md) — identity, browser ledger and exact source matrix.
2. [02_ARCHITECTURE_AND_REUSE.md](02_ARCHITECTURE_AND_REUSE.md) — primary design and component-level upstream reuse.
3. [03_DATA_API_AND_STATE_CONTRACTS.md](03_DATA_API_AND_STATE_CONTRACTS.md) and [proposed OpenAPI](contracts/openapi.proposed.yaml).
4. [04_PHASED_IMPLEMENTATION_PLAN.md](04_PHASED_IMPLEMENTATION_PLAN.md) and [dependency manifest](tasks/index.json).
5. [05_TEST_SECURITY_AND_RELEASE.md](05_TEST_SECURITY_AND_RELEASE.md).
6. [06_OPENCODE_EXECUTION_GUIDE.md](06_OPENCODE_EXECUTION_GUIDE.md), [starter prompt](handoff/OPENCODE_START_PROMPT.md), proposed AGENTS addendum and progress template.
7. Evidence appendices: [source audit](research/SOURCE_AUDIT.md), [upstream audit](research/UPSTREAM_AUDIT.md), [planning verification](PLANNING_VERIFICATION.md).

Critical path: BO-000 provenance → decisions/contracts → identity/schema/demo boundary → persisted profile/buyer review → budget/durable execution → safe bounded search/evidence/fit/progress → quote/confirmation/dispatch/reconciliation → grounded drafts/approval/export/outcomes → security/recovery/evaluation → separately approved live pilot. Policy, baseline UI and provider/license analysis can proceed independently, but shared contracts, migrations and budget transaction ownership must be serialized.

Effort and assumptions are computed from the task manifest in 04; elapsed timing is not the report's historical estimate. First action is **BO-000 in OpenCode Plan**, not Build. Current implementation statuses are deliberately not DONE. This planning session changed documentation only.
