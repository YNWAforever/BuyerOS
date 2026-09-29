# BuyerOS release candidate readiness (T30 preparation)

Status: **NOT READY FOR RELEASE OR LIVE PILOT**. This is a reviewable local candidate record, not an approval or deployment record. Candidate base: `f43a9d88b334c2c4029fa06fa71624ed52efe4a2` plus the T00–T30 review diff. The eventual PR head SHA is recorded in the PR and handoff; merged and deployed SHAs are **not established**.

## Evidence boundary

| Fact | Current disposition |
| --- | --- |
| Code | T00–T28 implemented locally; T28 strict API/worker gates passed; T29 partly implemented with fresh bilingual workbench and disposable performance evidence; T30 partial same-project seeded approval/export/outcome UI walkthrough and one same-dataset UI offer edit→exact ICP approval→research→fit→review/list/assign→grounded-draft browser/worker journey passed; the complete addressed approval journey and release gates remain open. |
| Contract | 70 original operations plus 8 extensions have route handlers; per-operation integrated/tested/deployed status remains in `remaining/API_OPERATION_STATUS.csv`. A handler does not prove live provider readiness. |
| Fixture | Disposable PostgreSQL/fake OIDC/fixture provider tests passed in preceding task checkpoints. Earlier strict API 569/569 and worker 169/169 had zero skips; the 2026-09-29 current-tree API rerun failed at disposable Docker startup and is not a passing current gate; T29 demo responsive 21/21 after bounded component extraction, fresh API-backed workbench 8/8 and T30 partial journeys 1/1 each. |
| Integration | Earlier disposable PostgreSQL/Valkey and fake identity/provider runs verified T29 post-rate-pool 10k/100-workspace in-process read, mutation/admission and broker-publish benchmarks against proposed local P95 targets, plus T30 same-dataset edited/approved offer→browser→dispatcher→broker→worker research and grounded-draft handoff. The earlier strict API 569/569 result had zero skips; the current-tree 2026-09-29 rerun stopped at Docker fixture startup, so there is no current green strict API/worker or API-backed browser gate. Addressed approval remains a separate seeded UI fixture. |
| Live | Auth0 public SPA reconfiguration, membership ownership, Render/Neon/R2/Valkey targets, policy and named provider semantics not verified here. |
| Deployment | Not authorized or performed. No deployment SHA or staging URL is claimed. |

## Required gates before staging or a pilot

| Gate | Owner/evidence needed | Current result | Failure action |
| --- | --- | --- | --- |
| Source and contracts | Repository owner: review candidate diff, 78-operation ledger, final PR head SHA | Pending | Keep candidate local; revise diff. |
| Strict tests and migration | QA/backend: full API/worker no-fail/no-skip gates, sole Alembic head, isolated restore/rollback evidence | Earlier API 569/569 and worker 169/169 passed with zero skips; current strict API finishing rerun failed at disposable Docker startup, and worker was not rerun; local older-backup fixture replay passed; external journal custody/completeness, physical deletion, screen-reader review and unmeasured non-text elements remain unverified | Keep live switches off; repair and rerun. |
| Security/policy | Identity owner and data-policy owner: public Auth0 SPA PKCE callback, named membership owner, CORS, EU/APAC purpose/retention/export review | Pending external decisions | Disable live identity/provider access. |
| Infrastructure | Platform owner: Render Singapore API/worker/dispatcher, persistent non-evicting Valkey, Neon Singapore pooled runtime/direct migration DSNs, private R2 APAC with restore/deletion controls | Not provisioned/verified here | No staging deployment or migration. |
| Provider economics | Provider/finance owners: named search/model/contact adapter, terms, bounded liability and current prices, acceptance/status/reconciliation proof | No live provider selected | Paid admission/dispatch remain off; fixture rows never presented as live. |
| Complete staff journey | QA: fake-identity HTTP+DB+worker+broker end-to-end at en/zh-HK and mobile/desktop; negative roles, races, failures, refresh | T30 seeded addressed exact approval/export/outcome UI 1/1 and same-dataset UI offer edit/ICP approval→browser/worker research/fit→review/list/assign→grounded unaddressed draft 1/1; project creation and addressed approval remain separate fixtures | Keep candidate local. |
| Performance | QA/platform: 1k/10k buyers, 100 workspaces/projects/ICP revisions, P95/query count/bytes/EXPLAIN, broker queue fairness | T29 10k/100, ten distinct fixture staff, 20+20 persisted mutations/admissions, 100-workspace broker publish measured locally; deployed latency and worker-consume age not measured | No latency or capacity claim. |
| Pilot activation | Named budget and policy owners: exact workspace/users/markets/purposes/dates/providers/caps/stop triggers and maximum external spend | No approval record | Zero live paid requests; no production migration/deployment. |
| Delivery | Separate later approval and implementation | Disabled by design | `/deliver` stays 403 `DELIVERY_DISABLED`; mailbox/CRM/sending disconnected. |

## Candidate scope for human review

The candidate can support internal review of scoped offers, ICP approval, bounded research, buyer review/lists/assignment, optional quote/lookup, grounded drafts, exact-context approval, authorized export, manual outcomes and refresh when the relevant **fixture** gates pass. It does not establish real-company precision, provider acceptance, contact validity, live identity, deployment, or a sender of record. User-facing live APIs must fail closed when a selected capability is absent; no synthetic demo row may appear as a live result.

Pilot values are intentionally unfilled: authorized workspace and users, markets, dates, lawful purpose, retention version, total/category/run caps, maximum paid operations, provider IDs/prices, stop thresholds and signatories. Filling those fields requires a concrete owner decision. No illustrative dollar amount is an authorization.

## Supporting local evidence

See `remaining/CHANGED_FILES.md` for the exact 410-path pre-commit review inventory, `REMAINING_DEVELOPMENT_STATUS.md` for exact task commands and counts, `performance-baseline.md` for benchmark conditions, `provider-capabilities.md` for unselected live adapters, `runbooks/recovery.md` for uncertain holds and kill switches, and `runbooks/release.md` for a future staged procedure. Do not promote this candidate until every relevant gate has dated evidence bound to a reviewed release SHA.

## Latest local candidate checks (2026-09-30)

On HEAD `f43a9d88b334c2c4029fa06fa71624ed52efe4a2` plus the 410-path candidate diff: 11/11 domain checks, 73/73 live-adapter fail-closed checks and 3/3 Node contract/cleanup tests passed; TypeScript, lint, Vinext build, generated types, 78-operation route map and whitespace checks exited 0. The build retains a nonfatal >500 kB chunk advisory. The supplied 70 original operation IDs are all present in the 78-row ledger, with eight extensions and zero deployed dispositions. Alembic has sole head `0033_api_rate_windows`; no schema change was made in this reconciliation. A separate actual Chromium 200% zoom regression passed 2/2 across six fictional demo routes in en/zh-HK. These checks do not replace the failed current strict API fixture gate or prove staging, live providers, screen-reader use or a deployed SHA.

The user authorized a Docker Desktop maintenance restart on 2026-09-30 to recover the isolated PostgreSQL 16 test fixture. The normal `docker desktop restart` failed during stop with `context deadline exceeded`; the engine became unavailable. A subsequent bounded detached start returned `Starting Docker Desktop`, but engine readiness and the current strict gate were not established at this checkpoint. No Docker/WSL processes were force-killed and no unrelated container was removed. The next verification prerequisite is restored Docker Desktop health or an equivalent isolated PostgreSQL 16 host. Named provider/policy and exact pilot scope remain separate owner activation decisions recorded in `PILOT_EXECUTION_RECORD.md`; this document supplies none.
