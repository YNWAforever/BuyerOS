# N00 local counted IPC and isolated native worker

Spec: docs/superpowers/plans/2026-10-03-buyeros-gpt61-fixes.md N00/F20/NA01. BASE a06e134d807850c6fe8f4324a877d187e1ed5387.

## Global Constraints
Existing isolated worktree/branch; no agents, external request, account, provider, email, production DB/schema/roles/auth cutover/push/deploy. Cached local image only, explicit local Docker endpoint; no pulls/builds. Owned internal network/containers, no published ports/host sockets/credential mounts. Canonical actors/RLS/HMAC and delivery403 retained. Original302 and DB guards unchanged.

## Task 1: Private counted IPC into the existing journal owner
Interfaces: existing fixture-only createFixtureExecutionBoundary.dispatch and assertFixtureExecutionBoundary; fixed cli channel; RealRunJournal canonical intent/hold/200budget/20cleanup/TTL. Single parent dispatch owner; child returns requests on stdout and receives receipts on stdin. No domain operation/migration added.
Write nonempty failing contract tests for durable receipt, unknown/restart/channel-stable intent and invalid injected boundary; implement fixed owned Docker worker/control with bounded private pipes, read-only nonroot/cap-drop/no-new-privileges/resource limits and exact ownership/absence cleanup. Initially use only owned --internal network to exercise positive control and IPC. Assert original user/credential environment never reaches child. Observe RED before implementation and GREEN.

## Task 2: Deny isolated child's direct native egress
Add regression that raw Node HTTP/fetch/TCP/subprocess cannot reach an owned sink. Existing internal control must demonstrably reach it (three HTTP plus raw TCP), then worker must have zero direct requests. Observe behavioral RED against Task1 internal network, then select --network none for the worker; keep positive control on its own owned internal network. Inspect actual container network/user/readOnly/caps/ports/mount/env fields; validate native outcomes, IPC request persists before owned auth receives it, holds survive restart, all owned IDs absent after cleanup. No skip when Docker unavailable; fail and disclose.

## Verification and review
Meaningful RED/GREEN; full root suites, original5Chromium accounting/WS/SW, strictcrypto/types/scopedlint/contracts84 and read-only Alembic heads. No current build needed (host harness/worker only), no true Neon/provider/full staff UI claim. Parent/broker and Chromium/APIRequestContext/Google/control-plane traffic remain outside this child's OS boundary. Full N00 Task2 remains OPEN; never promote fixed worker to arbitrary provider CLI containment. Inspect payload/pipe bounds, no shell interpolation, exact label/ID cleanup on all paths, local context/image only and original evidence/worktrees preserved. Author review only, independent pending.

## Rollback and next
Revert source plus following metadata; no DB/data undo. Preserve admitted/unknown journal holds. Next local work: compose browser/parent/control-plane into an end-to-end counted isolation design, APIRequestContext explicit adapter; real scope still requires fresh target/account/cleanup authorization after harness review.
