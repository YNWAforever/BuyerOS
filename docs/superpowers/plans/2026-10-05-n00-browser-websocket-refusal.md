# N00 browser WebSocket refusal and transport gap audit

Spec: docs/superpowers/plans/2026-10-03-buyeros-gpt61-fixes.md N00 / F20 / NA01; BASE ebe830e16f15d432ad326e7f298d629c8ca59a6f.

## Global Constraints
Owned loopback/browser fixtures only; no external target, account, provider, email, DB/schema, roles, auth cutover, deployment, push or agents. Keep original302, unknown-write holds, budget, timeout and destructive DB guards unchanged. Source and metadata commits local only.

## Task 1: Refuse browser WebSockets before physical connection
Interfaces/predecessors: existing audit-neon-execution.spec.ts actual Chromium/pinned SDK/fixed Node CLI, owned gateway/journal and serviceWorkers:block dedicated config. HTTP routing cannot establish WebSocket containment. No port/string is authority to call a real target.
1. Extract the existing HTTP-only route into one shared local spec helper without changing behavior. Add actual native WebSocket probes toward owned gateway and a separate owned sink; no backend upgrades permitted. A positive control in a separate unrestricted fixture context must prove the sink observes a real native upgrade. Observe meaningful RED (actual upgrades vs zero); keep original three cases unchanged in meaning.
2. Add context-wide WebSocket refusal before any native socket is created. Verify same-origin and foreign-loopback WebSockets both blocked; normal counted browser/SDK/CLI still pass. Verify service worker registration does not make a physical script request. Include fresh-page/refresh coverage.
3. Run dedicated browser cases and exact discovery, related/full Node, types/scoped lint/contracts84. No fresh build or full staff/Neon acceptance claim; this is a spec-side local guard, not production runtime. Review source diff, byte evidence, preservation, rollback applicability, then source and metadata commits.
Expected: RED reflects observed owned upgrades, GREEN nonempty zero fail/error/skip, original three browser flows retained. No DB suite applicable to browser transport-only slice; no required DB skip. Unknown journals preserved.

## Review Focus and limits
Context HTTP/WS/service-worker cases cover only this dedicated fixture. Arbitrary Node HTTP/https/net/TLS/undici workers, provider CLI, browser APIRequestContext/WebRTC/DNS/background egress, true Google and actual provider cleanup remain OPEN. HTTP refusals and WS attempts are local refused transport attempts, not actual upstream auth hops; do not fabricate journal reservations for zero-hop attempts. Author review only; independent review pending. Full N00 Task2 and N01/N02 prerequisites remain open.

## Rollback
Revert following metadata and this source commit; no DB/data rollback. Retain admitted/unknown journal holds and all historical evidence. Next local eligibility: audit and prepare remaining native transports; real target/account execution separately requires fresh bounded authorization.
