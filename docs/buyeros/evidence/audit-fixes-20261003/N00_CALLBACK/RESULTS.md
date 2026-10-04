# N00 / F20 / NA01 — managed callback fixture follow-up

Source `2fd84ef49d289ea313a5abb21ec6e30bc2659a9d`; base `2606ed53da983dc3b8aa9b793cb32fb882cf1829`; branch codex/neon-auth-compatibility-local-20261004. **Full N00/NA01 NOT PASSED. Real Neon NOT RUN. No deployment/push/remote PR.**

## What changed

Official SDK middleware in disposable proxy.ts + dynamic /compat/return page; fictional random one-use managed state/challenge/verifier upstream; two meaningful built callback regressions. Original three cases/assertions unchanged. Official [OAuth setup](https://neon.com/docs/auth/guides/setup-oauth) places provider callback on Neon, then app callbackURL session-verifier exchange. No private SDK/global-fetch patch or production auth change.

## Exact final results

| Check | Pass | Fail | Error | Skip | Output |
|---|---:|---:|---:|---:|---|
| Current Node guards/discovery/typed/Auth0 render/services |32|0|0|0|exit0;13.1972273s|
| Actual portable output whole5 |4|1|0|0|exit1;57.528115s|
| Actual Nitro/Vercel output whole5 |4|1|0|0|exit1;19.821048s|
| Added callback cases, per target (subset above) |2|0|0|0|RED observed, GREEN both|
| Final strict types / focused lint |—|—|—|—|both exit0|
| Clean Linux portable / Vercel builds |—|—|—|—|both exit0|

Auth0 API34pass/0fail/0skip is **carried from prior source2f14645**, not re-executed by this fixture-only follow-up. No required DB suite for this slice; no DB suite skipped, no DSN passed. Alembic heads exit0, sole0037_bulk_manifests;0 migrations.

Added positives actually exercise official built handler -> challenge host cookie -> fictional Neon callback302 -> official app middleware307 -> exact resolved clean URL/query, session/cache cookies, challenge cleared, server session/reload/token/FastAPI/logout, consumed verifier rejected in a new context, and actual-browser redirect navigation. Missing/mismatched challenge is denied with no session; the owner's fresh verifier remains usable. Fixture5minute expiry is implemented but not waited; no actual provider/account/state/CSRF/refresh/revocation/key rotation/Safari/Firefox claim.

**Retained synthetic302 API-proxy case FAILS:** portable500 and Vercel200 vs302. Original test not weakened/removed/skipped/expected-failure. Later assertions unexecuted, not pass. This arbitrary proxy redirect is not the documented provider callback path and does not prove real Neon OAuth or a production SDK defect. Whole suites remain red. Signed-in demo-shell screenshots are protocol fixture evidence, not staff/workspace/UAT.

## RED and setup records

Initial new2cases200vs500 because social upstream unimplemented404 fell through Nitro SSR; unchanged login baseline1pass. With upstream but old output, both new cases307vs200: missing built middleware. New portable first5 run2pass3fail0skip36.2s: valid relative Location/test URL setup; next2pass3fail0skip27.8s: Chromium manual Secure http-cookie setter rejected. Exact browser URL resolution and cloning actual minted secure/domain/path/expiry cookie metadata fixed setup without relaxing status/destination/attributes. Logs/XML/traces retained with flattening/source map. Initial RED traces were replaced by a later producer run before freezing; retained traces belong to missing-middleware RED, not initial500. No invented trace claim.

Evidence freezer default cp950 failed reading legacy Unicode JSON after only N00/NA01 tracker writes. Resumed with explicit UTF-8 and reverified preservation. No test result changed or counted as pass. The source comparison byte-prefix check also exposed Git LF versus worktree CRLF; normalized original cases are identical.

## Environment / provenance / limits

SDK0.5.0-beta exact, framework pins unchanged. Node22.23.2-bookworm-slim image sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9;4CPU/6GiB;pnpm11.25.0 frozen install44.5s with supply-chain checks. Owned build e47117940ec860437126e2cb cleaned, seed052d6a686de9 read-only. Clean outputs between targets. Build input base2606ed5 plus source/staged hashes; compiled overlay hashes match source. Final test/runner hashes recorded separately; test setup corrections are not build dependencies. Local Vercel bridge runs genuine emitted outputs, not Vercel ingress/protection/binding/deployment proof. HostNode24.18.0/APIvenvPython3.14.6/Chromium1120x800. No live SLA/performance/staff claim.

## Preservation / rollback / next gate

31 frozen input payloads/150 prior N00_LOCAL payloads match bytes/hash;24other tasks/97other cases/98historical fields/84operations/4destructive guards/other worktrees preserved. Production Auth0/framework/config/routes/domain API/canonical IDs/memberships/roles/owner/approval/audit/job actor/Cloudflare HMAC/delivery unchanged. No automatic email linking or role grant. Author review only; independent pending per no-agents.

Reverse source.patch check exit0 (not applied); revert2fd84ef and metadata checkpoint to return to previous spike. No DB/data/role undo. Auth0 remains release path; deployed SHA null. Next specifically approved fresh isolated actual Neon Auth target/account/method roundtrip; old cleaned/expired approvals not reused. Q13 waitsN02; Q16/Q17 root proof remains blocked. No eight-module/live acceptance.

[Commands](COMMANDS.md), [capture map](CAPTURE_MAP.json), [decisions](RULINGS.md), [contract/ADR](../../../decisions/2026-10-03-neon-auth-contract.md).

## Exact next external decision prepared

Read-only target inspection confirms free_v3 org-soft-sunset-25251479 and proposed fresh name absent; no mutation. [Fresh real-roundtrip proposal](../../../runbooks/neon-auth-n00-real-roundtrip-20261004.md) specifies one new empty Auth project, one human-operated Google test identity, US$0/no upgrade,200checks/two-hour cleanup, local built outputs only/no Vercel deployment. Approval not inferred or recorded as granted.
