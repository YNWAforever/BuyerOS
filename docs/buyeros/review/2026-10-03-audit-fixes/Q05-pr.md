# PR-12 / Q05 — Exact bulk confirmation and eligible owner assignment

Base: `6e7a78c6994664cb47c5325d8c0eecd8cfdde573`. Source commit: `4cd0f484814be7d4333ca265c9637de940d398fa`. Local PR preparation only; no GitHub PR, push or deployment performed. Suggested title: `fix(Q05): bind bulk confirmation and reconcile frozen owner assignments`.

## Changes

- Use generated eligible-member projection for current colleague search/pages, full IDs, self and no-owner choices; guard stale scope reads.
- Canonical confirmation binds actor/workspace/project/operation, explicit IDs+versions or snapshot+exclusions, target membership and trimmed reason. Material changes invalidate; page-only changes preserve confirmation.
- Freeze the generated owner body before ActionIntent submission. Unknown response locks edits and preserves exact key/body/preview across route and scope remounts; only explicit same-assignment Retry can reconcile. Obsolete results cannot update another scope.
- Show conflict/blocked IDs, reasons and current versions; fix mobile picker overflow and preserve en/zh-HK preference ownership.
- Add five unit checks, eight browser cases and three strict DB tests using unchanged disposable-only ownership guards. Fix fixture locale isolation without changing existing D02 assertions.

## Acceptance and review

F06 local repair: B02/B03/B04/B07/B16. Final strict DB13, combined UI37 and related unit18 pass, zero failures/errors/skips. Generated79-operation/type/lint gates pass. See [exact commands, failed/green runs, artifacts and limits](../../evidence/audit-fixes-20261003/Q05/RESULTS.md), [complete seven-file patch](../../evidence/audit-fixes-20261003/Q05/Q05.patch), and [author review](Q05-review.md).

Server domain handlers/schema/contracts are retained; inactive-target synchronous422 and queued per-row blocked semantics already existed and have new proof. No schema migration, identity link, membership grant, provider activation, delivery change or deployment. Fake identities/test-controlled processing are not live verification. Author review performed; independent reviewer approval pending.

## Rollback and remaining scope

Revert source commit as one unit; reverse applicability passed. Preserve successful assignments/versions/audits and unknown-operation details; compensating changes require current versions and authority, never automatic Undo or a new-key blind replay. Memory recovery covers route/scope/token renewal, not hard-browser restart. Q06 bounded summary polling is next; real account/provider/Neon/production and release performance gates remain separate.
