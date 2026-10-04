# BuyerOS local verification gates follow-up

Spec: 2026-10-03 repair handoff/Q11 release-evidence discipline and the 2026-10-04 continue request. The selected recommendation is the two inherited root Node failures after U05; no additional product feature or cutover is selected.
Base: cbb67ddbb907b8b989b175588ba73ed205e2c2d8.

## Global Constraints
Use the existing isolated repair branch. No agents, remote PR, push, deploy, auth/Cloudflare cutover, production data/membership/identity mutation, mail or paid providers. Preserve frozen evidence, historical case fields and all destructive fixture guards. Only newly owned Docker sentinels/build container and ignored local output may be mutated; verify ownership before fallback cleanup. Do not skip or synthesize a built Vercel function.

## Review Focus
The teardown check must detect missing delegation through observed marker/container effects, accepting valid wrappers. Failure cleanup must only touch this run's labelled resources. Vercel verification must import the actual emitted vercel preset function; a node-server build is insufficient. Report build prerequisites, test failures and source hashes separately; no live acceptance follows.

## Task 1: Close inherited local Node gates
Interfaces: Playwright globalTeardown -> base DB cleanup / audit owned UI cleanup; run-vercel.mjs -> Nitro vercel output -> vercel-render.test.mjs. Predecessor: U05 complete. No product/API/schema interface changes.

- [x] Reproduce current two failures and retain exact output; evaluate the configured teardown through real owned container/marker effects. Mutation-check removal of audit's database delegation.
  Expected: original baseline fails two checks; behavior check detects missing cleanup, valid direct and delegated cleanup pass; no skip.
- [x] Run a bounded local Linux build from a safe source inventory with frozen cached dependencies; import the actual emitted Vercel handler for /, /app and /auth/callback. Supply the genuine artifact to the normal whole-root Node command.
  Expected: real vercel output, three SSR200/content assertions and whole-root Node zero failures/skips; missing build artifacts continue to fail.
- [x] Run types/lint/generated contract checks, inspect the diff and author review. Record exact commands, counts, artifact hashes, ownership cleanup and rollback applicability; local commit source/tests then checkpoint evidence.
  Expected: no migration or product runtime changes, existing evidence untouched, clean reviewable commits; independent review/human UAT/live gates stay open.
