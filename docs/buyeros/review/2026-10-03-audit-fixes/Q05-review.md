# Q05 / PR-12 author review

Base: 6e7a78c6994664cb47c5325d8c0eecd8cfdde573. Source commit: 4cd0f484814be7d4333ca265c9637de940d398fa.

Author review only; no independent reviewer was dispatched because the user prohibits sub-agents. Independent review/merge approval remains pending.

## Findings and disposition

- F06 UI remains open at base: confirmation stays checked after selection change; no colleague picker. Reproduced B02 with the actual isolated UI before edits.
- Server eligibility/version/tenant boundaries already exist: retain synchronous inactive-owner 422 and post-enqueue per-row blocked outcomes. Three added strict persistence tests verify rejection, 100 mixed outcomes/reason digest, and 101 terminal blocked rows across recreated sessions.
- Confirmation binds canonical actor/workspace/project/operation, IDs+versions or snapshot+exclusions, target membership and trimmed reason. Keyed confirmation remounts on material change; page-only changes preserve it. Frozen payload copies and freezes arrays/objects; no token in fingerprint/storage.
- Generated listEligibleAssignees projection is used for current operator/admin callers. Paging/search keys include the scope generation, and stale reads/writes are cancelled. Eligibility is rechecked by the existing domain API.
- Unknown write retains its frozen payload and ActionIntent across route/scope round trips; explicit same-intent retry uses the same key, without accepting changed fields. UI shows the actual frozen target/count/reason on return. Known 4xx releases the local uncertain state; no success is fabricated.
- Individual blocked/conflict IDs/reason codes/current versions stay visible after partial synchronous results. Successful rows are preserved, not automatically undone.
- Review refinements: fix reproduced mobile picker overflow, preserve frozen target in the disabled picker after remount, and check current in-memory session before starting a write. Types/lint pass without rule suppression.
- Fixture correction: required project version and database subject_id naming errors are execution/test errors, not product RED. Repeated seed/ownership CLI calls were reduced to one unchanged owner_dsn proof per bounded process. Fixture cleanup removes only the extra B operator membership so Q02's original other-workspace assertions remain valid.
- Combined suite detected a real fixture-isolation defect: Q05 mobile saved operator zh-HK preference, making following English D02 selectors fail. Restore the fictional preference through its real API at mobile-case end; do not force English in product or weaken D02.

## Considered and deferred

- Hard browser/process restart for an unresolved assignment: this task uses memory-only recovery. Q06 addresses bounded job summary polling and refresh; hard-browser assignment recovery remains unverified, not promised by that polling task.
- True staff/Neon/provider/production journey, external auth cutover, deployment and paid activation: not authorized in this repair scope and not executed. Auth0 and Cloudflare HMAC remain separate and unchanged.
- Full release performance/200-percent zoom/screen-reader acceptance and the other F-IDs: separate Q09/Q10/Q11 gates; test elapsed times are not production p95.
- Q16/Q17: only OperationalError evidence exists; no SQLSTATE/pool/driver root cause was obtained. No speculative infrastructure fix.

## Review outcome

Local Q05 acceptance passes on this source: strict DB13, combined UI37 and related unit18, zero failures/errors/skips; generated79-operation/type/lint gates pass. Completion-tool ESLint timeout is preserved separately; bounded wrapper rerun passed. See the Q05 RESULTS.md for exact evidence. No new schema, domain API owner, migration owner, paid provider, membership grant, identity link, delivery activation or deployment introduced.
