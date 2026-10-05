# N00 counted APIRequestContext adapter — local only

Spec: 2026-10-03-buyeros-gpt61-fixes.md N00/F20/NA01, current Neon contract and predecessor native IPC checkpoint. BASE ad1a54510f6a0fb2485392c878e7e867e9def6be. Reuse isolated worktree, branch codex/n00-api-request-context.

## Global Constraints

No agents, external provider/Neon/Auth0/account/mail/identity/membership/paid/production DB/migration/Cloudflare/push/deploy actions. Preserve canonical actors/RLS, Auth0 and delivery403. Original302, tests and DB guards stay unchanged. Fixed fixture adapter does not contain arbitrary raw APIRequestContext or parent/browser OS egress. Original evidence and other worktrees preserved.

## Review Focus

One existing boundary/journal owns reservations and holds; never use a second budget/intent serializer. Fixed gateway URL must be branded and paired with execution/journal/nonce. No caller URLs/contexts/storage/proxy/retry settings; standalone in-memory context only. Explicit zero automatic redirects/retries, bounded deadline, no secret-bearing transport errors. Unknown/accepted writes remain held across fresh contexts/journals and renewed headers. Dispose actual APIResponse/context resources; stale/closed/rebound gateway cannot be adopted. Do not claim live Neon/full N00 or general OS containment.

## Task 1: Adapter plus actual Chromium consumer

Interfaces/predecessors: assertFixtureExecutionBoundary, ownedFixtureSdkUrl, FixtureExecutionBoundary.holds/dispatch, existing gateway /dispatch JSON envelope and RealRunJournal; predecessor source779138a fixture native IPC. FixtureApiRequest input omits channel and allows GET/HEAD/POST only; dispatch returns existing ExecutionReceipt; dispose owns only its standalone context. Channel fixed browser. Domain API/migration/identity contracts unchanged.

- [x] Write meaningful actual Playwright APIRequestContext regressions: counted/manual hops and pre-dispatch persistence, backend unknown across restart, committed-but-lost gateway response/no autoretry, unexpected wire redirect/no sink leak, ownership/injected context refusal, invalid/oversized paths and body before wire, 180budget stop, rebound/disposed context refusal plus separate owner-change-during-body/disposal cases (10new Node cases total). Expected RED: missing adapter export; nonzero tests, no skip.
- [x] Add one actual Chromium fixture consumer with browser cookie isolation and two counted manual auth hops. Expected RED: old5pass/new1fail, zero globalerrors, no import-only 0test failure.
- [x] Implement minimal fixture-only adapter into original journal owner. Explicit maxRedirects0/maxRetries0, timeout20..3000ms, owner/target checks before and after await; no raw context exposed. Unknown errors sanitized; accepted/unknown ledger retained. Reuse validation through holds; do not reserve twice. Expected focused new cases GREEN.
- [x] Run whole root MJS suite serially, dedicated whole Chromium suite, strict EdDSA crypto, types/scopedlint/generated84/routes and read-only Alembic heads. No new build for host-only harness; retained app SSR scope disclosed. Expected nonzero GREEN/0skip; record every failure and keep raw attempts.
- [x] Author review actual source/diff and preservation preflight:3659 artifacts and three unrelated worktrees unchanged. Independent review pending under user no-agents instruction. Full N00 stays OPEN.

Checkpoint handoff: prepare source then metadata local commits; check manifest/index/commit bytes and reverse patch applicability; record final preservation after tracker update. This is a bounded local fixture slice, not full N00 completion.

## Rollback and next

Revert following metadata then source; no schema/data undo; never erase admitted/unknown journal holds. Next local: parent/browser/control-plane OS isolation feasibility and exact composition; genuine fresh Neon/human account/cleanup scope remains separately authorized. No fresh real approval inferred from continue.
