# Build approval record — template (not an approval)

**Status: TEMPLATE / NOT AN APPROVAL.** Plan revision v1. Recorded 2026-09-15 (Hong Kong). Completing this file does not authorize Build until the owner signs it with the exact values below.

Copy to `docs/buyeros/decisions/BUILD_APPROVAL_RECORD.<task>.md`, fill every field, and have the owner confirm. An approval covers only the named task and scope; planning approval does not approve all tasks, any live pilot, or delivery.

## Required fields

| Field | Value (owner to complete) |
|---|---|
| Task ID | e.g. `BO-005` (one task only) |
| Plan revision | `v1` |
| Spec | `specs/2026-09-15-<phase>-design.md` |
| Implementation plan | `plans/2026-09-15-<phase>-implementation.md` |
| Reviewed source baseline | canonical repo `YNWAforever/BuyerOS`; the **source-import commit** and its tree (expected `b4c6b5384ccfd6d0bdd5b4b92440427db83de7c1`) |
| Current HEAD at approval | `<sha>` (captured with `git rev-parse HEAD`) |
| Working-tree state at approval | `git status --short` output; unrelated changes preserved |
| Allowed files/actions | exact `existing_files_to_modify` + `proposed_files_to_create` from the task YAML |
| Dependencies with evidence | predecessor task IDs and their recorded completion evidence |
| Approver | `<name>` |
| Date/time (with zone) | `<ISO timestamp>` |
| Constraints | preserve frontend/routes/lockfile; no second backend/queue/migration owner; no silent demo fallback |
| Environment/provider spend | `none` by default; if approved, exact provider, purpose, environment, cap, currency, time window |
| Modes/tools permitted | Plan-only vs Build; which commands may run; no commits/pushes/deploy/migrations unless separately named |
| Evidence to return | changed files/symbols, commands with output/exit code, migrations proposed vs executed, NOT RUN list, rollback status |

## Explicitly not covered by any single approval

- Commits, pushes, deploys, Site access changes, cloud provisioning, database migrations on real data.
- Paid provider calls, contact purchase, mailbox connections, or any send.
- Delivery (P7) and BO-029 live activation require their own separate approvals.
- Any file outside the task's declared scope.

## Recommended first candidates

| Task | Why first | Preconditions still open |
|---|---|---|
| **BO-005** tenant-safe persistence + one migration owner | Local, disposable PostgreSQL; no provider or live data; exercises RLS + composite FKs | source import; B-HOST (for deployed DB) not needed for local |
| **BO-004** verified bearer identity + tenant membership | Establishes the auth boundary | B-IDENTITY (Auth0 reconfigure + membership owner); contract freeze (BO-003) |

## Sign-off sentence (owner to write verbatim)

> I approve implementation of task `<ID>` against commit `<SHA>` with the scope, files, actions, and limits recorded above, and with no provider, deployment, migration-on-real-data, or delivery authorization.

## After approval

1. Run only the approved task's Build steps within scope.
2. Record exact results in `PROGRESS.md`; mark every unexecuted check **NOT RUN**.
3. Stop and replan on any material source/contract/license/provider/identity difference.
