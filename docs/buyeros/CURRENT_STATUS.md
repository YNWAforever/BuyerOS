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

C61-21: typed scoped six-card summary, pending-approval draft filtering and
private durable receipt pages are integrated. 54 API/contract, 5 frontend units
and 24 fresh built cases pass with zero fail/error/skip; all six A/B en/zh-HK390
cards equal actual filtered API totals. Current membership/project/actor
predicates and read-only repeatable snapshots isolate receipt pages. Dirty
drafts and exact Unicode approval/export still pass. Errors remain unavailable.
The first built 22-pass/2-unsuccessful run is retained; both locator defects
were corrected without weakening counts or increasing timeouts. Same-version
real account/provider, production readback and human acceptance remain pending.
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

Next local work: finish C61-23 maintenance/expiry acceptance; C61-08/09
and live adapter source remain independent ready tasks. C61-05 depends on actual
historical root evidence. Production/auth/provider spend/send need their specific
authority and same-version verified payloads. Rollback remains per task source
commit; 0038 rollback removes only directory function/index after route rollback,
preserving canonical IDs, FKs, existing memberships, audit, revisions and holds.
