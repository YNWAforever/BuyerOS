# Build approval record — BO-005 (persistence spike, dependency waiver)

**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-15 (Hong Kong).

## Approval fields

| Field | Value |
|---|---|
| Task ID | `BO-005` (tenant-safe domain persistence and one migration owner) |
| Scope | **Scope-limited spike**: SQLAlchemy tenant models, hand-written Alembic migrations (already-imported tables + RLS/roles), transaction-local tenant session, and unit tests under `services/api/**` |
| Plan revision | `v1` |
| Spec | `docs/buyeros/specs/2026-09-15-p1-boundary-design.md` |
| Implementation plan | `docs/buyeros/plans/2026-09-15-p1-boundary-implementation.md` (Tasks 1–4; Task 8 partial) |
| Source baseline | `YNWAforever/BuyerOS` `main`, source import commit `b804ba8d1514a1049b7202c861278dd72c473a75` (tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`) |
| Current HEAD at approval | recorded in `docs/buyeros/PROGRESS.md` at execution time |
| Allowed files/actions | create `services/api/**`; create this record; run `uv sync`/`uv run pytest` locally; optional local disposable PostgreSQL container for DB-backed tests |
| Dependencies with evidence | **BO-003 and BO-004 are NOT complete** — see waiver below |
| Approver | Owner (session authorization) |
| Date/time | 2026-09-15 (Hong Kong) |
| Environment/provider spend | **none** |
| Explicitly excluded | commits to remote, pushes, deployments, cloud resources, real-data migrations, paid provider calls, contact purchase, mailbox connections, sends, Active agent/AGENTS.md config changes |

## Dependency waiver (explicit)

The owner authorized a scope-limited BO-005 **persistence spike** with an explicit waiver of the `depends_on: ["BO-003","BO-004"]` prerequisite. Rationale: the persistence/RLS/migration work is independent of the contract freeze (BO-003) and bearer identity (BO-004), and BO-004 is additionally blocked by unresolved B-IDENTITY. Consequences accepted: later contract/auth decisions may require rework; no auth, no API routes, no providers are implemented here.

This waiver does **not** mark BO-003 or BO-004 complete, and does not authorize any other task.

## Sign-off (owner)

> I approve implementation of a scope-limited BO-005 persistence spike under `services/api/**` against the imported source baseline, with the dependency waiver and exclusions recorded above, and with no remote commits/pushes, deployment, migration-on-real-data, provider, or delivery authorization.
