# N00 counted native IPC and isolated fixed worker — local checkpoint

Date: 2026-10-05 HKT. Base `a06e134d807850c6fe8f4324a877d187e1ed5387`; author-reviewed/tested source `779138aa5335eb829a97a80bbc80430a32201c1a`; branch `codex/n00-native-ipc-isolation`. Source: five files, 136 insertions. Independent review pending. **Full N00 / NA01 / F20 is OPEN; release is NOT READY.**

## Facts by verification boundary

| Fact | Evidence |
| --- | --- |
| Code implemented | Private counted IPC, fixed Linux worker, owned Docker lifecycle, three regression cases and local plan |
| Fixture verified | All307 JUnit root leaves /308 Node reported tests pass; Chromium5 and EdDSA8 pass, zero failures/errors/skips |
| Integration verified | Actual local Docker IPC/HTTP/native socket/subprocess and existing loopback budget/intent journal. Positive control3physical HTTP+TCP; isolated fixed child0directHTTP and four refused probes. Unknown write hold survives a new container and reconstructed journal despite renewed token |
| Externally blocked / unverified | No true Neon/Google/Admincleanup or original302 acceptance; fresh exact target/account/cleanup authorization absent. Parent/broker/browser/APIRequestContext/arbitrary provider CLI/control-plane OS confinement unimplemented/unverified. Independent review pending |
| Deployed | None in this slice; deployedSHA null/unproven. Auth0/application remain current |

The positive-control sink receives only local diagnostic paths, never auth/provider data. Those diagnostic requests and Docker management operations are separate from counted fictional `/fixture/auth/` requests. This slice does not establish complete real-run request accounting.

## Smallest slice and interfaces

- `scripts/neon-native-ipc.mjs`: existing `assertFixtureExecutionBoundary` owns the exact `execution/journal` pair; fixed cli requests dispatch through the original budget/intent owner. No second domain API, journal or migration owner. Pair index and full caller request tuple checked; target fingerprint rechecked before dispatch.
- `scripts/neon-native-worker.mjs`: fixed source only, no arbitrary binary/URL/provider adapter. Private stdout request lines and stdin receipts. At most8requests, 32768 serialized request JavaScript string code units; 65536 code units per line, 1MiB total stdout bytes; 15second pipe deadline. Native HTTP/fetch/TCP probes300ms, subprocess2s, Docker operations20s; bounds not enlarged to obtain green.
- `scripts/neon-native-ipc.d.mts`: strict typed report identifies fixture-only scope and expressly false parent/browser/arbitraryCLI containment.
- `tests/neon-native-ipc.test.mjs`: persistent unknown/renewed-token restart case, injected/foreign owner rejection before resource creation, and real native bypass negative with working positive control. No test skip on missing Docker; unavailable local Docker fails.
- `docs/superpowers/plans/2026-10-05-n00-native-ipc-isolation.md`: bounded task interfaces, constraints, review focus and rollback. The original master-plan N00 Task2 is still open.

Runtime uses an explicitly checked local `desktop-linux` Docker Desktop named pipe and actual immutable cached `node:22-bookworm-slim` imageID. `--pull=never`; no build/pull. Owned `--internal` bridge hosts sink and positive control; actual worker uses `--network none`. Actual inspected worker: nonroot node, read-only, cap-drop ALL, pids64, memory128MiB, CPU1, no mounts/published ports. Image entrypoint adds benign HOME/HOSTNAME/PWD; strict allowlist accepts only known benign metadata and BUYEROS_STRICT_INTEGRATION, never inherited provider/DB/proxy/credential keys. Container environment names and actual probe/cleanup readback are in `reports/final-native-observations.json` and `reports/image-environment.json`.

Docker's network-none driver supplies only loopback to the container. This is the chosen child-only mechanism; actual network and native probes are checked separately. [Docker network-none documentation](https://docs.docker.com/engine/network/drivers/none/).

## RED, GREEN and retained failures

| Producer/report | Pass | Fail | Error | Skip | Meaning |
| --- | ---: | ---: | ---: | ---: | --- |
| `red-ipc.xml` | 0 | 2 | 0 | 0 | Missing counted IPC export; meaningful feature RED |
| `red-isolation-behavior.xml` | 2 | 1 | 0 | 0 | IPC works but native paths reach owned sink: actual3 vs expected0; meaningful isolation RED |
| `root-first.xml` | 306 | 1 | 0 | 0 | All307 leaf cases execute; isolated egress case passes, one IPC cleanup readback times out |
| `root-green.xml` | 307 | 0 | 0 | 0 | Final30root MJS files, all307 leaves; Node separately reports308 including one nested parent; 466803.7974ms |
| `browser.xml` | 5 | 0 | 0 | 0 | Actual Chromium accounting/WS/SW fixture, 0globalerrors, 13.736473s |
| `crypto.xml` | 8 | 0 | 0 | 0 | Strict EdDSA API trust fixture, 3.12s, one existing asyncio deprecation warning |

The three new native cases are included in the whole-root green count. Earlier startup failures are retained as `green-ipc*`, `red-isolation.xml` and `red-isolation-stage.xml`; they are failed attempts, not successful verification or meaningful isolation RED. `reports/all-attempt-counts.json` enumerates every retained XML producer. No0-test result or skip is counted as pass. No expected-failure conversion or assertion weakening.

First whole-root failure: exact owned sink inspect was killed after20s with empty stderr, leaving an active endpoint; network removal correctly refused. Exact owner/IDs were reconciled and removed (see `reports/manual-cleanup.json`). The implementation now permits only a single readonly inspect retry for that narrow killed/empty-stderr case, keeps20s per call, reports its count, and never retries writes. Final probe receipt reports0such retries. Unknown create outcomes reconcile pre-reserved names/labels before cleanup. All owned IDs are checked again before removal and absence confirmed; independent owned cleanup proceeds even if another resource fails. No shared prune/restart/removal.

An earlier failed create also left a labelled empty internal network `1af3c6b4e4d0b9f6895827cffd5d23bb908b8f3f0ed1f358a27e4c8139c1f68c`, owner2321b2bbb153. Exact name/label/internal/empty readback was observed before removal during this execution; its raw observer output was not archived. Final owner-label inventory confirms zero remaining resources (`reports/owned-absence-final.json`).

## Exact final commands and environment

Run from the isolated BuyerOS worktree, PowerShell:

```powershell
$env:PYTHONUTF8='1'
$env:BUYEROS_STRICT_INTEGRATION='1'
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:BUYEROS_TEST_DATABASE_URL -ErrorAction SilentlyContinue
$taskTests=@(Get-ChildItem tests -Filter '*.test.mjs' -File | Sort-Object Name | ForEach-Object { 'tests/'+$_.Name })
node --test --test-concurrency=1 --test-reporter=spec --test-reporter-destination=test-results/n00-native-ipc-isolation/root-green.log --test-reporter=junit --test-reporter-destination=test-results/n00-native-ipc-isolation/root-green.xml @taskTests
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js scripts/neon-native-ipc.mjs scripts/neon-native-worker.mjs tests/neon-native-ipc.test.mjs --max-warnings=0
node node_modules/@playwright/test/cli.js test --config playwright.neon-execution.config.ts
services/api/.venv/Scripts/python.exe -m pytest -q tests/fixtures/neon-runtime-flow/test_verify.py --junitxml=test-results/n00-native-ipc-isolation/crypto.xml
node scripts/generate-api-types.mjs --check
uv run --frozen --project services/api python scripts/generate-operation-routes.py --check
```

Every final command above exited0. Exact expanded30-file root argv and return codes are in `reports/commands.json`. Head was inspected read-only from services/api with `uv run --frozen --project . alembic heads`: `0037_bulk_manifests`; migrations0. No allocation/DB rollback needed. New protocol-only cases need no canonical DB test; destructive DB guards are unchanged, no remote DSN was substituted, and no required DB suite was skipped. Root runners retain their own disposable Docker/loopback safeguards.

Host/runtime metadata: `reports/environment.json`. Node24.18.0 host / cached Linux image metadata NODE_VERSION=22.23.1, Python3.14.6, Docker Desktop29.8.1, Windows PowerShell; explicit local desktop Linux daemon, cached image digest recorded. Full suite time includes local Docker startup/readback/cleanup and existing guarded tests. This is not an application/provider latency, capacity, availability or production SLA measurement.

No current-source build was run: changed source is only the local harness/worker. Existing root SSR gates use retained application source5aaf649 output; prior clean portable/Vercel SDK builds retain their historical scope, not a fresh build claim. Current application/API/UI5aaf649, proxy9e1ef78, browser362b60d unchanged.

## Case, contract, preservation and UI evidence

| ID / scope | Current result |
| --- | --- |
| F20 / NA01 | Still open; this local worker slice passes, full Neon/session/runtime/platform/account/containment gate incomplete |
| Original strict302 | Unchanged and not rerun here; earlier synthetic500/200 failure remains historical OPEN |
| Domain API | Generated types and84route mappings exit0;70original+14extensions; ledger bytes unchanged, no operation added |
| Schema | Existing0037, zero migrations; separate peer0038 unmerged |
| Other findings/cases | Existing task/case statuses preserved; no new closure or live claim |

`reports/preservation-final.json` checks3599prior input/evidence artifacts byte-for-byte,24other audit tasks,31legacy T task objects, all98original fifteen case columns and97other case rows,84operation ledger bytes,3foreign worktrees and193unrelated dirty paths. `reports/source-proof.json` binds all five tested working files and commit blobs; source reverse patch applicability exit0 only. These checks are evidence preservation, not independent source review.

Fresh screenshot `screenshots/accounting-fixture.png` was visually inspected: “N00 accounting fixture”, “Browser hops:2; fixture only:true”. It is a diagnostic page, not staff login/workspace/provider acceptance. Fresh Chromium5cases run the owned accounting/WS/SW harness; no current full staff/en/zh journey is claimed. Earlier actual built/UI/staff fixtures retain their original evidence and scope.

## Rollback and remaining next task

Revert the following local metadata commit first, then source `779138aa5335eb829a97a80bbc80430a32201c1a`. `source.patch` passes `git apply --reverse --check` against the reviewed source; applicability checked only, rollback not executed. No DB/schema/identity/membership/resource data migration occurred. Preserve admitted/unknown durable journal holds and reconcile accepted outcomes before retry; rollback must not erase those entries.

Next eligible local N00 work: explicit counted APIRequestContext adapter and composition of parent/browser/control-plane OS isolation. Arbitrary provider CLI and actual Managed Auth cleanup are separate boundaries, not covered by this fixed worker. Real Neon/Google/session/token/platform/account rehearsal requires a fresh exact target/account/cleanup/budget configuration and specific authorization after harness review. N01/N02/Q13/Q16/Q17 and external live/provider/staff/independent review gates remain open; Cloudflare cutover separate. No push, remote PR, account, email, linking/grant, paid provider, production migration/auth/Cloudflare change or deployment.
