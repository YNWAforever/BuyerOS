# C61-25 polling source budget

This budget covers the existing Operations and BulkJobPanel summary poller.
It is a source regression contract, frozen before the local workload. Fleet
quota, sustained backend capacity, WAN latency, field metrics and release
acceptance require separate evidence and owner adoption.

| Condition | Required local behavior |
|---|---|
| Visible, online, nonterminal | One request in flight per poller; next request starts at least 2 seconds after settlement |
| Fast successful summary | At most 30 starts in a half-open 60-second steady window, without availability transitions |
| 2.5-second fixture RTT | 14 starts per poller in a half-open 60-second steady window; 10 views/jobs total 140 |
| Hidden or browser offline | Abort current summary; no new requests or retry timers until available |
| Reconnect or show | At most one immediate request if the prior deadline allows; repeated events do not overlap requests |
| Transient error or 429 | Keep existing 2/4/8/16/30-second backoff and Retry-After deadline across availability changes |
| Timeout | Abort at 10 seconds and await settlement before retrying |
| Scope change, disposal, terminal or 401/403/404 | Old lifetime stops; ignore late values/errors; no reconnect restart |
| Payload | Summary only; result pages remain explicit bounded reads |

Each visible tab has its own poller. There is no cross-tab leader election or
SSE transport in this path; do not describe this as an SSE fallback test or
multiply the per-poller budget into permission to raise API quotas. An
offline browser hint is advisory: online requests can still fail and use the
existing error/backoff path. An aborted read does not cancel a durable job,
resubmit an intent, spend money or release any hold.

`tests/job-poller-checks.mjs` uses logical time and synthetic summaries to
exercise 10 views/jobs, hidden/offline pauses, A-B-A scope lifetimes, terminal
and denied accounts, timeout and Retry-After. It is not wall-clock capacity.
`playwright.job-poller.config.ts` discovers all 3 source-module Chromium cases
for native `navigator.onLine`, offline/online events and disposal. These cases
use local timers; they do not run the built application, real auth, API or DB.
Required CI checks positive native JUnit and exact browser discovery with zero
failure/error/skip. All existing audit specs remain required separately.

Run from repository root after frozen dependency installation:

```sh
node --test tests/job-poller-checks.mjs
pnpm exec playwright test --config playwright.job-poller.config.ts
```

Rollback the poller change to the preceding compatible frontend artifact.
API, canonical identities, migrations, durable job state, accepted/unknown
intents and holds are unaffected. Keep both the failed baseline and the new
source-bound local artifacts; C61-25 remains open for adopted budgets, real
bulk/restart/backend capacity and same-chain/field acceptance.
