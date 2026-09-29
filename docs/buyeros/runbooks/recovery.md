# BuyerOS recovery and capability switches (T28)

This is a local operations guide. It does not authorize a deployment, provider request or production migration.

## Independent switches

| Switch | Default | Effect |
| --- | --- | --- |
| `BUYEROS_LIVE_READ_ENABLED` | true | False returns correlated 503 `READ_DISABLED` for `/v1/` GETs; health remains readable. |
| `BUYEROS_PAID_ADMISSION_ENABLED` | false | False rejects production paid run admission before run/outbox creation. |
| `BUYEROS_PAID_DISPATCH_ENABLED` | false | False prevents new paid provider/run/contact claims and blocks already published selected-adapter work. |
| `BUYEROS_RECONCILIATION_ENABLED` | true | False pauses reconciliation claims. Use only when reconciliation itself is unsafe; unknown holds remain reserved. |

Changing a switch requires restarting the affected API/dispatcher/worker processes and verifying the effective value without logging secrets. Enabling a paid switch still requires separately approved capability, price, policy and credential evidence. No switch activates mailbox, CRM, sending or delivery; `/deliver` remains 403 `DELIVERY_DISABLED`.

## Local request and queue controls

API rate windows are stored per verified actor, workspace, request class and minute under tenant RLS. Defaults are 600 reads, 300 writes, 120 expensive reads and 60 expensive writes per minute; an exceeded class returns 429 `RATE_LIMITED` with `Retry-After: 60`. These are local protective bounds, not measured production capacity or an approved tenant tariff. `GET` live reads can be paused independently through the switch above. The `0033_api_rate_windows` rollback refuses to discard retained windows; on a disposable target, let them expire and clear them under an authorized migration procedure before downgrading.

From the worker environment, `buyeros-worker metrics --workspace-id <workspace UUID>` prints aggregate ready/failed intents, oldest ready age, expired leases, pending jobs and held USD on unsettled provider operations. It emits no payload, address, token or provider reference. Scrape each authorized workspace separately; the command is a read and is not an alerting service. Review sustained ready age, expired leases and held amount against the approved pilot bounds before activating paid dispatch. Representative production thresholds have not been measured.

## Failure response

1. Freeze new admission and paid dispatch. Keep secure reads and reconciliation available when safe. Record request/job/intent IDs, lease generation, queue age and unknown-held amount; do not record personal content.
2. If the broker fails after the outbox commit or before publish, restore the single Valkey broker and dispatcher. Lease expiry/reclaim republishes the existing intent; the worker checks fencing and terminal state before execution.
3. If a paid provider may have accepted an operation, keep its hold. Reconcile by the original verified provider reference; never blindly resubmit or infer rejection from timeout. A callback is an accounting hint only after authentication and ownership checks.
4. If object or checkpoint cleanup fails, keep `source.delete` nonterminal and repair the storage/worker credential. Do not restore readable source data to make cleanup pass.
5. For a disposable restore rehearsal, restore into a separate local database, verify migration head, RLS and ledger balance, replay the separately controlled deletion journal, and only then enable reads. A local two-container fixture now proves that a pre-tombstone dump restores readable source text and that a separately held fixture journal can drive tenant-scoped tombstone replay before reads resume. It verifies migration head, RLS, fixed-point ledger balance, one queued delete intent and idempotent replay. External journal custody/authenticity/completeness, physical object/checkpoint deletion, approved staging recovery and representative alert thresholds remain release gates.

Do not flush the broker, drop outbox rows, release unknown reservations or weaken RLS to restore apparent availability. Observe the metrics and rate-limit gates in the release checklist before activation; those production thresholds are not yet verified.
