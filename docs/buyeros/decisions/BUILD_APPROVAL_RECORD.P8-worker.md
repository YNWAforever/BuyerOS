# Build approval record — P8 worker/dispatcher (dependency waiver)

**Status: APPROVED (owner-authorized this session).** Plan revision v1. Recorded 2026-09-15 (Hong Kong).

## Approval fields

| Field | Value |
|---|---|
| Phase/task | **P8 worker + dispatcher** (covers the pending BO-011 execution layer) |
| Scope | Outbox dispatcher, Celery/Valkey worker, DB leases + fencing, sweeper/recovery, `worker_leases` migration, handler registry, `fetch.evidence` (validation), fail-closed handlers for `run.discover`/`contact.submit`/`draft.generate`, run/event lifecycle, tests |
| Spec | `docs/buyeros/specs/2026-09-15-p8-worker-dispatcher-design.md` |
| Plan | `docs/buyeros/plans/2026-09-15-p8-worker-dispatcher-implementation.md` |
| Source baseline | `YNWAforever/BuyerOS` `main`; audited source `b804ba8d1514a1049b7202c861278dd72c473a75` (tree `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`) |
| Current HEAD at approval | recorded in `docs/buyeros/PROGRESS.md` at execution time |
| Allowed files | create `services/worker/**`; modify `services/api/buyeros_api/db/{outbox,worker}.py`; create `services/api/alembic/versions/0006_worker_leases.py`; add `services/api/tests/**` and `services/worker/tests/**` |
| Dependencies with evidence | **BO-003/BO-004/BO-011 NOT complete** — see waiver |
| Approver | Owner (session authorization, execution mode = subagent-driven) |
| Environment/spend | none. Local disposable PostgreSQL and (optionally) a local `valkey/valkey:8` container only |
| Explicitly excluded | remote commits/pushes, deployment, cloud resources, real-data migrations, paid provider calls, contact purchase, mailbox connections, sends, AGENTS.md/OpenCode config changes |

## Dependency waiver (explicit)

The owner authorized P8 Build with an explicit waiver of `depends_on` prerequisites (BO-003 contract freeze, BO-004 bearer identity, BO-011 outbox/task completion). Rationale: the dispatch/execution layer is independent of auth and the HTTP contract, and it builds directly on the P2–P5 tables already implemented and tested. Consequences accepted: later auth/contract changes may require rework; no provider is verified, so discover/contact/draft handlers remain fail-closed.

This waiver does **not** mark BO-003, BO-004, or BO-011 complete, and does not authorize any other phase.

## Sign-off (owner)

> I approve implementation of the P8 worker/dispatcher phase against the imported source baseline, under the dependency waiver and exclusions above, executed subagent-by-task with review between tasks, and with no remote commits/pushes, deployment, real-data migration, provider, or delivery authorization.
