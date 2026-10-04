# Exact N00 commands / environment

Run from the isolated worktree. Pnpm11.25.0, hostNode24.18.0, APIvenvPython3.14.6, DockerNode22.23.2-bookworm-slim, Chromium/Playwright1.63.0. No provider/DB/auth credentials passed to builds/fixture children. No agents. SDK exactly0.5.0-beta; core-js build denied. Original framework pins retained.

1. `pnpm install --frozen-lockfile` (exit0; host setup).
2. `uv sync --frozen --project services/api` (exit0; no DB).
3. Optional actual read-only seed: `BUYEROS_N00_SEED_VOLUME=buyeros-audit-ui-deps-052d6a686de9`, `BUYEROS_N00_SEED_OWNER=052d6a686de9`; owner label must match. Omit if unavailable, use a fresh frozen install. Do not mount any shared/production working database.
4. `node scripts/neon-compatibility-harness.mjs`: ownedDocker4CPU6GiB; actual inside commands `corepack pnpm install --frozen-lockfile`, `corepack pnpm build`, `node scripts/run-vercel.mjs build`, clean outputs between targets. Both final builds exit0. Refuses overwrite of existing build proof; use fresh checkout/proof area or preserve old attempt before rerun. Do not run root type scan concurrently with source staging.
5. `node --test tests/neon-compatibility-harness.test.mjs tests/neon-compatibility-discovery.test.mjs tests/api-types-generation.test.mjs tests/audit-auth-render.test.mjs tests/vercel-services.test.mjs`:32pass0fail/skip.
6. `pnpm exec tsc --noEmit`:exit0.
7. `pnpm exec eslint scripts/neon-compatibility-harness.mjs scripts/serve-neon-compatibility.mjs tests/neon-compatibility-harness.test.mjs tests/neon-compatibility-discovery.test.mjs tests/e2e/audit-neon-compat.spec.ts playwright.neon-auth.config.ts playwright.audit-fixes.config.ts tests/fixtures/neon-compatibility/overlay --max-warnings=0`:exit0.
8. API command: resolved `services/api/.venv/Scripts/python.exe -m pytest tests/test_api_auth.py tests/test_auth_tenant.py -q --junitxml=<absolute-area>/auth0-api.xml`, cwdservices/api, env from exported fixtureChildEnvironment (OS/tool allowlist + BUYEROS_STRICT_INTEGRATION=1, no DSNs/auth/provider env):34pass0fail/error/skip,5.68s. Same sanitized interpreter `-m alembic heads`:0037_bulk_manifests only, no DB connection.
9. Set `BUYEROS_N00_TARGET=portable`, then `pnpm exec playwright test --config playwright.neon-auth.config.ts tests/e2e/audit-neon-compat.spec.ts`:whole3,2pass1fail0error/skip,exit1,25.9s fresh reverify.
10. After teardown set targetvercel, same command:whole3,2pass1fail0error/skip,exit1,23.8s. Never run targets simultaneously (same owned loopback ports44890/91/92).
11. Discovery uses `pnpm exec playwright test --config playwright.neon-auth.config.ts --list --reporter=list` (exact3, not execution). Default configured JUnit on --list overwrites actual report with listed/skipped entries; retained portable-discovery-only.xml is explicitly not acceptance evidence. Node discovery uses --reporter=json and verifies existing Q01 remains selected while N00 stays outside DB workbench/regression configs.
12. `git apply --reverse --check --binary docs/buyeros/evidence/audit-fixes-20261003/N00_LOCAL/source.patch`:exit0 applicability only. No actual runtime/production revert. Revert source2f14645 thenb2e4d38 and separate checkpoint metadata if abandoning the spike.

Final fixtures use actual emitted archives; not dev server. Ephemeral fictional account/key/secret/session; no live Neon account, OAuth/session-verifier, email, provider, canonical membership/role or platform proof. Both strict callback assertions remain failing. Do not mark full N00/NA01 complete or deploy these fixture routes.
