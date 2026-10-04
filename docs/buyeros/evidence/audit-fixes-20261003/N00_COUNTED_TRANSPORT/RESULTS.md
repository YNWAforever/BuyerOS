# N00 / F20 / NA01 — counted fixture transport checkpoint

Reviewed source `261a9e51d9d038c68be1d0d67002fcbe6e1eff6c`; base `a94bdf4951a1fcf418df828fee15ac01baae9ba6`; branch codex/neon-auth-compatibility-local-20261004. Source8files287insertions/12deletions. Author review only, independent review pending. No remote PR/push/deploy; deployed SHA null.

## Implemented and verified

Owned loopback backend only; durable reservation before body/dispatch; manual redirects, no automatic retry; unknown/lost POST results retain consumed budget and block replay after restart; concurrent identical-write barrier; body/response/time bounds; auth/session/challenge/JWT headers preserved without raw values in journal; nonce-bound stop plus OS child-absence and owned journal cleanup proof. Official SDK calls use this governor in both actual previously built outputs. Production Auth0/identity/membership/RLS/approval/actor/HMAC/delivery403 remain unchanged.

| Gate | Fresh result |
|---|---|
| Related Node | 80pass/0fail/0cancelled/0skip/0todo;9064.3264ms;exit0 |
| New loopback HTTP regressions | 11pass, includes actual lost-response/restart/concurrent/cap/timeout cases |
| Portable full fixture | 7cases/6pass/1fail/0error/0skip;23.084738s;exit1 |
| Vercel full fixture | 7cases/6pass/1fail/0error/0skip;12.189678s;exit1 |
| New SDK counted cases | 2pass per target, negative401 counted as a real fixture response |
| Final types / focused lint / generated API | exit0/0/0 |
| Alembic | single0037_bulk_manifests head,0migrations/no DB connection |
| Final fixture budgets | each44reserved/44forwarded/41accepted/3rejected/0pending/0unknown;external0 |
| Cleanup | final child PIDs absent/journals removed;5earlier owned abandoned roots recovered/removed |
| Rollback applicability | reverse source patch checkexit0; not applied |

## Gates still open

Original strict synthetic callback test remains unchanged and fails302vs500/200. Both managed-verifier/challenge added cases pass, but neither fixture result proves real Neon OAuth or a production SDK defect. **Full N00/NA01 is not complete.** Real Neon base/issuer/audience/JWKS/method readback, real-only runtime secrets/build configuration, actual approved Google account roundtrip, complete real SDK/browser/CLI budget coverage, Firefox/Safari/rotation/expiry/account recovery and independent review remain unverified. Existing real-target template IDs/trust are NULL; fresh specific approval is pending. Expired previous resource approvals were not reused.

No paid provider, account/email/link/role/production DB/Auth0/Cloudflare mutation; no staff8-module live acceptance/performance/deployment claim. API DB34from source2f14645 is carried evidence only, not a fresh DB run. This slice requires no destructive DB suite and skips none; guards unchanged. Current84operation ledger (70original+14extensions) is retained rather than counted as live coverage.

## Evidence and preservation

[Exact commands](COMMANDS.md), [machine counts](SUMMARY.json), [captures and SHA mapping](CAPTURE_MAP.json), [source hashes](SOURCE_HASHES.json), [rollback](rollback.json), [preservation](PRESERVATION.json). Frozen prior270payloads (31inputs+150local+66callback+23preflight), four DB guards, nine compiled overlay hashes and all89/2214reused emitted archive members verified unchanged. Other24task records/97case rows/98historic columns preserved. Root/audit-parent clean and dirty historical193paths/diffSHA preserved.

## Rollback / next eligible

Revert source `261a9e51d9d038c68be1d0d67002fcbe6e1eff6c` and this evidence/status checkpoint in reverse order if this local harness is rejected. Auth0 is retained; no DB downgrade/data/resource undo. Applicability was checked only; runtime rollback not rehearsed. Keep original immutable evidence even if reverting source. N00 remains first eligible; N01/N02 and then N03/N04/N05 stay gated; Q13 waits N02; Q16 root cause remains blocked and Q17 has no guessed fix. Next independent local scope is real-only configuration/accounting preparation; actual new empty Auth/one human Google test identity requires the exact fresh runbook approval.
