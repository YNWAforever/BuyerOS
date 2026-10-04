# Exact commands and environment

Cwd C:/Users/laich/.codex/worktrees/neon-auth-compatibility-local-20261004/BuyerOS; Windows PowerShell / Node24.18.0; existing API Python venv for Alembic heads only. No real target, account, cookie secret, bearer, DSN or provider credentials loaded. Synthetic local metadata and OS-temporary journals only. No external HTTP executor exists in the new component.

- node --test tests/neon-real-preflight.test.mjs: feature skeleton RED33tests19pass14fail0skip, exit1 (feature missing, no import/path failure). First implementation32pass1fail0skip, exit1; test teardown rmSync(empty dir) produced Windows EISDIR, corrected to rmdirSync. Both raw logs preserved.
- node --test tests/neon-real-preflight.test.mjs after review tests: meaningful RED35tests33pass2fail0skip, exit1; no expected exception for settled outcome without evidence and forged build sequence. Repair ->35pass0fail0skip20.5532656s, exit0.
- node --test tests/neon-real-preflight.test.mjs tests/neon-compatibility-harness.test.mjs tests/neon-compatibility-discovery.test.mjs tests/api-types-generation.test.mjs tests/audit-auth-render.test.mjs tests/vercel-services.test.mjs:68tests68pass0fail0cancelled0skip0todo10.0034381s, exit0; includes36new cases and actual terminated/restarted Node processes. Other32 related contracts rerun.
- node node_modules/typescript/bin/tsc --noEmit: exit0, types.log.
- node node_modules/eslint/bin/eslint.js scripts/neon-real-preflight.mjs tests/neon-real-preflight.test.mjs --max-warnings=0: exit0; lint-final.log.
- Sanitized OS/tool-only environment plus PYTHONUTF8/PYTHONIOENCODING: services/api/.venv/Scripts/python.exe -m alembic heads, cwd services/api: exit0 /0037_bulk_manifests(head). No database connection, migration or required DB suite for this metadata/FS-only slice; no DB skip.
- node scripts/neon-real-preflight.mjs check docs/buyeros/runbooks/neon-auth-n00-real-target.template.json: expected exit1 /N00_REAL_TARGET_REQUIRED, no HTTP.
- git diff --cached --check: source staging exit0 (4files351insertions). git apply --reverse --check --binary test-results/neon-real-preflight/source.patch: exit0; check only, not applied. Compressed patch retains exact uncompressed SHA.
- Manifest verification:247prior payloads (66callback+150local+31input) exact bytes/SHA256; four DB guards unchanged. No prior payload/report overwritten; actual built UI/APIs not rerun this turn.
