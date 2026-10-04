## Task 1: Close inherited local Node gates
Interfaces: Playwright globalTeardown -> base DB cleanup / audit owned UI cleanup; run-vercel.mjs -> Nitro vercel output -> vercel-render.test.mjs. Predecessor: U05 complete. No product/API/schema interface changes.

- [ ] Reproduce current two failures and retain exact output; evaluate the configured teardown through real owned container/marker effects. Mutation-check removal of audit's database delegation.
  Expected: original baseline fails two checks; behavior check detects missing cleanup, valid direct and delegated cleanup pass; no skip.
- [ ] Run a bounded local Linux build from a safe source inventory with frozen cached dependencies; import the actual emitted Vercel handler for /, /app and /auth/callback. Supply the genuine artifact to the normal whole-root Node command.
  Expected: real vercel output, three SSR200/content assertions and whole-root Node zero failures/skips; missing build artifacts continue to fail.
- [ ] Run types/lint/generated contract checks, inspect the diff and author review. Record exact commands, counts, artifact hashes, ownership cleanup and rollback applicability; local commit source/tests then checkpoint evidence.
  Expected: no migration or product runtime changes, existing evidence untouched, clean reviewable commits; independent review/human UAT/live gates stay open.
