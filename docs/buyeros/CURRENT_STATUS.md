# BuyerOS C61 execution status

Execution date: 2026-10-07 Asia/Hong_Kong. Original audit date: 2026-10-06.
Draft PR #12: https://github.com/YNWAforever/BuyerOS/pull/12 . Published head is
22f11ab; later local commits are reviewable follow-ups awaiting PR synchronization.
The original audit, 114 outcomes and task columns remain preserved. New outcomes
use execution fields; fixture evidence does not close a production finding.

C61-01: input hashes, HEAD/worktrees and Q drift comparison verified locally.
C61-02: selective Q integration retained; required Q PG suite 64/64, 45 Node
cases and full built 96/96 at 53bb6cf pass. Initial PR CI exposed a cold JWKS
race and document preference observer issue. Focused RED then 51 auth/DB cases,
4 observer units and the fresh full 96-case built suite pass. Earlier interrupted,
stale, empty and ENOSPC runs remain unsuccessful. JWT trust was not widened.
Latest hosted CI and integrated complete browser run remain pending.

C61-03: bounded staff reconciliation CLI defaults to read-only, supports existing
canonical users only and requires current DB admin authority and exact versions.
36 focused required cases pass. Actual staff accounts and role readback are pending.
C61-04: sanitized diagnostics and Alembic logging compatibility pass 22 focused
cases. The historical Oct2 OperationalError root is unconfirmed; C61-05 remains
blocked on historical evidence. No pool/cold-start explanation is inferred.
C61-06: migration 0038 restricted directory, canonical resolver and rollback
payload pass 39 required cases and actual runtime-role warm benchmark. SQL stays
4 per sample across W=1/10/100/1000. Production migration-owner eligibility,
index/lock review, deployment and directory performance readback are pending.
The complete follow-up API suite is 863/863 with fresh JUnit and zero fail/error/
skip at 92d19d0. Git API/migration tree equality connects it to the integrated
source; this does not certify later C61-21 edits or the entire repository tree.

C61-07: current public Neon SDK/production contract ADR prepared; six offline
peer SDK cases reviewed. Target Neon project/branch, real email/Google login,
JWT trust and portable runtime acceptance are pending. C61-08/09 can start locally.
C61-15: closed provider registry and immutable activation contract are implemented.
40 API registry cases and 5 durable worker safety cases pass. No provider selected,
verified account contract or credential configured; activation/spend stay zero.
C61-16: existing 33 search/fetch/ingestion safety cases verified; live adapters
and market/language account acceptance still need implementation/evidence.

C61-21: typed project work-queue summary and filtered lists are being implemented
in the second owned worktree. Initial 7 DB RED then 12 focused cases pass; 5
frontend cases pass and 3 new browser cases are positively discovered. Added
cross-project/concurrent receipt/contract regression and built execution are pending.
C61-22: readable source cards, exact read-only keyboard selection and workflow
are integrated. Native Chromium readonly caret failure was reproduced independently;
grapheme keyboard movement fixes actual [1,3] DOM selection -> [1,2] server emoji
citation. 22 core + 15 fresh built draft/dirty/retry/Unicode/approval/export cases
pass, zero fail/error/skip, with source hashes and exact export artifacts. Human
screen reader/zoom and real-source semantic/readback acceptance are pending.

Research admission still returns honest 503. Native delivery stays protected 403.
Real provider, built preview with real auth/provider, production readback and human
UAT have separate gates. Unowned dirty Neon worktree and user branches are untouched.

Release A (research + approved export): NOT ACCEPTED.
Neon-only: NOT ACCEPTED.
Native send (C61-20/30): NOT ACCEPTED.

Next local work: complete C61-21 built/contract acceptance, then C61-23; C61-08/09
and live adapter source remain independent ready tasks. C61-05 depends on actual
historical root evidence. Production/auth/provider spend/send need their specific
authority and same-version verified payloads. Rollback remains per task source
commit; 0038 rollback removes only directory function/index after route rollback,
preserving canonical IDs, FKs, existing memberships, audit, revisions and holds.
