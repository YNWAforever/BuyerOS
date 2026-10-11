# C61-25／19 owned broker recovery

This opt-in fixture uses disposable PG16, Valkey8 and two actual Celery solo
processes. It reuses the production registered task, late ACK configuration,
executor, leases, generation/epoch fences and contact hold/settlement rules.
Fault barriers and synthetic IO live exclusively in test utilities. No real
provider transport, credentials, charge or delivery is used.

From the repository root, with all four `DATABASE_VARIABLES` unset:

```bash
services/worker/.venv/bin/python scripts/benchmark-broker-recovery.py --output-dir artifacts/repair/broker-recovery-new
```

The runner refuses inherited DB targets or an existing output directory. It
requires four positively discovered native cases, exact matching JUnit names
and zero failures/errors/skips before validating the raw capture denominators.
The original twelve required CI jobs include this runner in
`owned-worker-capacity`; the default worker suite includes the refusal/capture
controls. Failed attempts remain evidence and never earn a report PASS.
The 45 default controls require recovery completion to match the started task,
intent, generation and replacement PID. Accepted reconciliation must retain
both its settlement and matching duplicate execution/snapshot, with one cost
and the same settled reservation; omitted or unrelated evidence is refused.

| Case | Required observations |
| --- | --- |
| redelivery | Hard loss while private-object fixture IO is inflight, an actual unacked broker task, natural redelivery of the same task ID/generation to a different owned PID, one final outbox |
| lease | Actual DB clock reaches the lease expiry, sweeper claims generation2, second worker completes, original still-running generation1 finalizer is stale |
| unknown | Fixture acceptance followed by hard loss before finalization, natural broker redelivery, exactly one submit, same operation/key/reservation, unknown result and retained USD0.30 synthetic hold |
| accepted | Accepted result committed before hard loss/ACK, duplicate broker delivery makes no submit, original epoch1 status retains hold; selector2 rejects the old epoch, compatible owned rollback advances to3; authoritative synthetic USD0.10 settles once via status only, duplicate causes no second cost |

Each case records owned launcher/interpreter identities, broker unacked IDs,
actual Redis clock/visibility expiry, native consumer visibility/restore
observations, per-process RSS samples, SQL snapshots, task start/return and
fixture submit/status events. Accepted inflight, committed, pending and settled
snapshots preserve the actual states separately. A new producer app owns each
disposable broker pool; these opaque-ID messages use the registered production
consumer task. Owner seeding of a ready reconciliation intent and selector
epochs is limited to disposable fixture data; it does not exercise API admission
or real runtime promotion/rollback. Fixture rollback respects the production
monotonic epoch constraint; no teardown restores an older epoch.

Crash cases compress the owned broker visibility to2s; lease uses120s to isolate
the DB lease race from broker visibility. The broker's native restore scanning
is unchanged and may take longer than its visibility timeout. Windows and Linux
results are separate: a Windows consumer that does not restore within the
bounded180s observation is a failed platform run, never a skip or an assumed
Linux pass. Actual deployment backend/role/DB binding, production visibility,
representative sustained/mixed load, adopted numerical budgets and real provider
receipts remain separate prerequisites. This closes no P05/P08 live acceptance,
does not establish a queue SLO and cannot enable G0/GN/GA/GS.
