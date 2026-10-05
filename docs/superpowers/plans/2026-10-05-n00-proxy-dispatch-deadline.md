# N00 proxy dispatch deadline — local follow-up

Spec: docs/superpowers/plans/2026-10-03-buyeros-gpt61-fixes.md (N00/F20/NA01).
Base: 233848b263cfdefc49d6dc5f53df2d534afdba16.
Global Constraints: existing isolated worktree; no agents/push/deploy/external calls/accounts/email/roles/schema/auth cutover. Auth0 and delivery403 retained. Original302 assertions unchanged. Owned loopback HTTP/filesystem fixtures only; no DB required by this protocol-only change.

## Task 1: Bound ingress and recheck before physical dispatch

Interfaces/predecessors: N00 Task1 owned backend/journal guard, RealRunJournal 200-total/20-cleanup reserve and two-hour TTL, existing counted proxy manual redirects and unknown holds. Runtime body may arrive after reservation. No new authorization inferred from a reserved request.

Ruling: Fix the demonstrated local counted transport deadline independently; original302/real Neon/native all-channel containment/independent review remain open. A fixture guard cannot authorize real execution.

1. Add native Node HTTP streamed-body tests: TTL crosses after durable reservation -> zero upstream hops and rejected receipt; continuous trickle exceeds body deadline -> zero upstream hops; timely body still relays original bytes/headers and records one hop; a physical write exceeding remaining TTL stays unknown and cannot replay after restart. Observe RED before implementation.
2. Replace resettable ingress idle timeout with bounded body collection; recheck TTL immediately before physical dispatch. Preserve pre-dispatch rejected vs post-dispatch unknown and manual redirects/hold semantics. Keep body/response/budget bounds unchanged.
3. Run new and existing related Node suites, whole root suites, types/scoped lint/generated84 contracts, strict EdDSA. Inspect source diff/rollback applicability. Reuse actual historical built runtime-flow artifacts only after verifying their hashes, label original built source separately; no current-source build claim from reuse.
4. Local source commit and byte-exact evidence checkpoint; update only N00/NA01/current source pointers, preserve other tasks/cases/artifacts. N00 Task2 stays OPEN.

Expected: meaningful nonempty RED/GREEN, zero final fail/skip for applicable suites; no external/provider/production mutation. No domain DB suite applicable; no DB skip suppressed. Rollback source plus following metadata; retain existing admitted request/unknown holds; no DB undo. Original302 and real auth gates stay OPEN.
