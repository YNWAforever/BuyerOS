# SDD ledger — plan: docs/superpowers/plans/2026-10-04-buyeros-n00-local-compatibility.md
Pre-flight: Task1 source inventory/build produces exact overlay consumed by Task2; current portable is Cloudflare/workerd, Vercel is Vinext/Nitro. Both must run actual outputs.
Ruling: Use a new independent spike from27f141 per N00 despite existing isolated audit worktree — avoids mixing experiment with completed repairs — cost if wrong: separate branch integration review.
Ruling: Official SDK0.5.0-beta pinned as devDependency; diagnostic routes live under tests/fixtures only and overlay into disposable build copy — retains Auth0 release path — cost if wrong: N04 must later integrate production imports.
Ruling: local fake upstream + dedicated FastAPI EdDSA diagnostic, no domain verifier edit — local protocol proof cannot close real Neon NA01 or N03 — cost if wrong: real preview may expose provider differences.
Ruling: no agents per human instructions; author review only — independent review remains open — cost if wrong: same-author blind spots.
Baseline attempt used two nonexistent test paths, exit1/zero tests; setup error, not pass. Correct baseline pending.
Task 1: complete (commits 27f1412..b2e4d38, tests: node --test tests/neon-compatibility-harness.test.mjs → ℹ duration_ms 1103.068)

Task2: official SDK built both targets exit0; first browser Vercel2fail/1pass, portable startup failed/zero tests. Not compatibility pass.
Ruling: overlay-only Nitro server.ts uses public fetchViteEnv to dispatch API/Flight — default SSR emits callback200HTML instead302 — cost: real provider/platform routing still unverified.
Ruling: clean owned Linux output dirs between targets — isolates build output — cost: build time.
Ruling: optional verified read-only Linux cache seed — npm tarball timeouts blocked fresh install — cost: new environment needs own cache or successful fresh install.

Ruling: Nitro services require a default fetch object; Vinext RSC virtual default is a function. Register its public app-router-entry as rsc service in the disposable staged Vite config, dispatch all app requests through it. Marker must match exactly once; record both source and transformed hashes. Production Vite/SDK code unchanged. Cost: Nitro experimental service interface may change and real Vercel remains unverified.
Docker unavailable attempt produced no builds. Move its source-stage/logs into a separate failed-attempt archive before retry; no zero-test pass. Seed preflight now runs before copying source to avoid duplicate TS inputs.

Verification: Node28pass0fail/skip; first concurrent root types scanned the ephemeral source stage then failed TS6053 after its cleanup. Fresh typecheck after staging completed exit0. Keep both logs; stage-copy and root-typecheck are dependent operations and must be sequential.

Owned build44ba873a retained RED: exited before install/build during bounded180s cache copy; container label verified and removed. Ruling: use a tar stream for the same read-only seed into owned writable container, bounded360s; show actual spawn error rather than empty stderr. Cost: longer local setup, not an increase to build timeout/paid resources.

Adapter run3cases:2fail1pass. Trace proves login/session/token200 JSON; first verifier callconnectionrefused before FastAPI ready. Add bounded actual401 readiness before app listening; no synthetic readiness. Callback still200HTML: exact SDK server-b0OzGjXl handleAuthRequest1129 fetch has no redirect:manual and follows upstream302. Keep assertion302 failing; do not mark NA01 compatible or monkeypatch global fetch/SDK internals. Local cache-image snapshot failed because build container already Dead; no image/resource created. Lint1error1warning preserved, fixed via useSyncExternalStore hydration and named dispatcher export.

Portable actual output3cases:2fail1pass; first flow button blocked by existing SiteCreator fixed sidebar (trace proves pointer interception, not SDK failure). Ruling: offset the fixture main320px; retain ordinary visible click and production plugin, no force click/hiding. Cost: protocol fixture has diagnostic layout, not BuyerOS staff UI acceptance. Callback500 after upstreamredirect remains failing; do not infer specific self-fetch/network cause. Lint final exit0. Rebuild exact final fixture source after hydration/lint/layout repair.

Author-review fix: apply the same environment allowlist to the Vercel bridge process itself before importing built output, not only its FastAPI/Wrangler children. This runner-only change is not imported by either build; retain its exact final hash with UI evidence. No secret names/values printed.

Portable final initial:login/session/cache/reload/token/FastAPI200 passed; original all-storage-empty assertion rejected existing buyeros-prefs-v1. Ruling: exact canonical locale-only JSON is allowed (writePrefs18–21 graph source); token/session/unknown fields/duplicate JSON must still fail. Add Node RED then GREEN negative cases. Cost: permit existing locale persistence; credential persistence remains forbidden. Preserve1pass2fail report and rerun both whole3-case suites after test-only correction. Callback302 assertion unchanged.

Author-review discovery: audit-* selected N00 in workbench DB config and inherited regression config. First test used wrong Q01 filename (setup1pass2fail); corrected filename then meaningfulRED1pass2fail confirms3N00cases leaking. Ruling: exclude only this spec from workbench config; dedicated N00 config actually executes3cases, no skip/expectedfailure; Q01 stays selected. Cost: separate N00 CI/runtime job must be added when gate turns green.

Evidence packaging initialCopyFile2 failed on deeply nested Windows trace path. Ruling: flatten archived trace paths with original-source mapping and identical content hashes; cost: reviewers follow the map for historical paths. Remove only this turn's incomplete N00_LOCAL copy after resolved-path/reparse-point check; original producer reports untouched.

Task2 checkpoint: source2f14645f34ba61ea032c1e826debff1c1defcec6; Node32pass0fail/skip, Auth0 API34pass0fail/error/skip, clean builds2exit0, each actual UI3cases2pass1fail0skip. Callback302 gates fail; N00/NA01 stays open, no task-done2/full completion. Author review only/independent pending. Keep plan workspace because acceptance/review are not clean.

Evidence guard rejected discovery-only portable XML: --list with default JUnit reporter replaced actual report with3unexecuted/skipped cases. Preserve as portable-discovery-only.xml, do not count as executed skip/pass; fresh whole portable suite required. Use --reporter=json/list for future discovery to avoid report collisions. No producer outcome fabricated.

Fresh portable reverify2pass1fail0skip25.9s; Vercel2pass1fail0skip23.8s. XML parsed and callback gates remain FAIL. Synthetic302 callback does not establish real Neon OAuth/session-verifier protocol or productionSDK defect. Freeze guard rejects incomplete/discovery reports; actual result matches summaries.
