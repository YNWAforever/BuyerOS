# N00 counted native IPC and fixed worker isolation — local proposal

## Scope

Base `a06e134d807850c6fe8f4324a877d187e1ed5387`; source `779138aa5335eb829a97a80bbc80430a32201c1a`. Existing isolated `codex/n00-native-ipc-isolation`, five source/plan files, 136 added lines. No remote PR/push/deployment. Metadata/evidence is a following local commit.

- Fixed fixture Linux worker sends bounded request tuples over private pipes; existing execution boundary and RealRunJournal own budget/intent/unknown holds.
- Explicit local Docker endpoint and immutable cached image, pull never. Own internal positive-control sink; actual worker network none, read-only/nonroot/cap-drop/no mounts or public ports.
- Exact owned label/ID cleanup and absence; single bounded readonly inspect retry after observed blank-stderr killed timeout. Writes are not retried.
- Three meaningful new tests, RED observed, final root308 reported/307leaves pass; Chromium5/crypto8 pass; types/lint/contracts84/routes exit0. Original assertion/DB guards preserved.

## Open release gates

Full N00/NA01/F20 remain OPEN. Fixed child only; parent/broker/browser/APIRequestContext/arbitrary provider CLI/control-plane containment and true Neon/Google/admincleanup/original302/independent review remain open. Auth0 remains current. No accounts/email/identity links/membership grants/production changes/provider activation/migrations/deployments.

## Review focus

Single budget owner, canonical tuple+fingerprint, stream/request limits, local context/image only, environment allowlist, exact resource ownership and absence on failures, unknown accepted writes held across restart. Author self-review recorded; independent review pending. Fresh raw failed attempts and final reports retained. Reviewer must not interpret fixture routes/screenshot as live/staff acceptance.

## Rollback

Revert following metadata commit then `779138aa5335eb829a97a80bbc80430a32201c1a`. Source reverse patch applicability checked only, not a runtime rollback rehearsal. No schema/data rollback. Preserve admitted/unknown journal entries and reconcile accepted outcomes before any retry. See RESULTS.md for commands, environment, pass/fail/error/skip and cleanup evidence.
