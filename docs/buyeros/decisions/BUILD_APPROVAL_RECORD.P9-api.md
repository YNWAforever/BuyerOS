# Build approval record — P9 API surface (dependency waiver)

**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-15 (Hong Kong).

| Field | Value |
|---|---|
| Phase | **P9 API surface (auth-agnostic, contract-first)** |
| Scope | FastAPI app factory + error envelope; fail-closed auth/tenant dependencies; health/readiness; workspaces/projects/ICP routes (hash-bound approval); buyer read routes; explicit 501 registry; contract-conformance + DB-backed isolation tests; generated TS client |
| Spec | `docs/buyeros/specs/2026-09-15-p9-api-surface-design.md` |
| Plan | `docs/buyeros/plans/2026-09-15-p9-api-surface-implementation.md` |
| Base | `main` @ `4cd159a` (PR #1 merged); branch `p9-api-surface` |
| Allowed files | create `services/api/buyeros_api/api/**`, `services/api/tools/**`, `services/api/tests/**`, `services/api/package.json`; modify `services/api/pyproject.toml` (deps), `services/generated/**`; docs under `docs/buyeros/**` |
| Dependencies with evidence | **BO-004 NOT complete** — see waiver. Real Auth0 activation blocked by B-IDENTITY |
| Approver | Owner (execution mode = subagent-driven) |
| Environment/spend | none; local disposable PostgreSQL only |
| Excluded | real Auth0 activation, provider calls, deployments, cloud resources, real-data migrations, mailboxes, sends, frontend wiring |

## Dependency waiver (explicit)

The owner authorized P9 Build with an explicit waiver of `depends_on` prerequisites (BO-003 contract freeze, BO-004 bearer identity). Rationale: the API surface, contract conformance and tenant-isolation tests are independent of live Auth0 configuration, and the auth dependency is intentionally fail-closed until B-IDENTITY is resolved. Consequences accepted: full JWKS/RS256 verification and live login are deferred to BO-004; `If-Match`/idempotency coverage is partial in this phase.

This waiver does **not** mark BO-003 or BO-004 complete and does not authorize any other phase.

## Sign-off (owner)

> I approve implementation of the P9 API surface against `p9-api-surface`, under the dependency waiver and exclusions above, executed subagent-by-task with review between tasks, with no real Auth0 activation, deployment, provider call, or delivery authorization.
