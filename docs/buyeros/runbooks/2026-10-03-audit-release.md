# First-round audit repair release boundary

PR-00: frozen baseline only; Q11 release gates remain open.
PR-01 Q01 F01/F02/F15; PR-02 Q03 F05; PR-03 Q04 F08; PR-04 Q15 F19. Each range must include RED/GREEN commands and counts, case evidence and rollback.

No production deployment, database migration, membership or identity linking, external email, paid provider or delivery activation is authorized by this request.

Q16: request `1d123054-2633-40b7-8e07-b6aed83dad98`, `2026-10-02T19:40:34Z`. Supplied E07 proves only OperationalError and JWKS 200. Driver/SQLSTATE/database/pool/connection evidence is absent; root cause and Q17 remain blocked. No guessed cold-start/pool fix.

DB tests: existing fixture guard accepts only loopback buyeros_test_* or owned Docker. BUYEROS_STRICT_INTEGRATION=1; no required DB skips. No Neon or production DSN.

Rollback: revert the respective UI commit. Q04 preserves already admitted runs/outbox/holds and never replays an unknown operation with a new key. Q15 retain/copy dirty buffers before reverting. No data rollback.

Final handoff: ../review/2026-10-03-audit-fixes/HANDOFF.md. Four task commits 8251027/f5936ce/fc8fae7/3efd1f3; tested tree ae62fa34c8601a826e0056c5e66de9cac2e48d57. UI22/0/0 and strict backend75/0/0; no deployed repair SHA. Independent review/live capabilities remain open.
