# BuyerOS current C61 execution status

Execution: 2026-10-07 Asia/Hong_Kong; input audit date: 2026-10-06.

C61-01 is locally verified. C61-02 selective Q source is integrated on
`d90431dd4a5a448b54fcb29b4920f6d07982e4d9`: 45 fresh Node cases pass,
typecheck passes, 96 browser cases are discovered. The required PG16 suite
passed 64/64 with zero fail/error/skip at 35226658; unchanged product subtree
hashes connect that result to d90431d. The isolation correction passed 23/23.
Complete built-browser acceptance remains blocked after local ENOSPC and
Docker fixture startup failure. Zero-case/stale reports do not pass.

The draft PR is a reviewable source checkpoint. CI, real provider, production
API/schema/worker/selector/epoch and human UAT each need separate evidence.
Production is not updated. Historical 44/812 counts are not current results.

C61-04 sanitized diagnostics and historical-root evidence, C61-07 public SDK
contract review, C61-15 provider gates, C61-06 directory payload and C61-22
Unicode helper are prepared in the second attached worktree; integrate their
independent commits deliberately. Historical F21 root remains unconfirmed,
so C61-05 is blocked. No pool/cold-start cause is inferred.

Research admission remains503; native delivery403 remains protected.
Release A (research plus approved export): not accepted.
Neon-only: not accepted. Native send: not accepted.

All original audit fields/114 outcomes and task fields are preserved.
Current run results occupy execution fields and the TASKS c61 namespace.
The dirty original Neon migration checkout and other user branches are intact.

C61-02 CI follow-up: PR #12 at 22f11ab failed API concurrent cold JWT
verification and mobile keyboard preference observation. A held-fetch focused
RED reproduced the real JWKS race; 51 auth/required cases then pass without
changing JWT trust. Current-document preference observation has 4 unit cases
and 3 fresh built-browser cases passing, including both U05 locales and T30
keyboard mobile. The original full UI run was deliberately interrupted and is
not accepted. Full fresh built/CI acceptance remains pending. C61-02 fixture
diagnostics now retain bounded subprocess exit/signal metadata on failure;
the two prior reset failures have no confirmed cause and their timeout is unchanged.
