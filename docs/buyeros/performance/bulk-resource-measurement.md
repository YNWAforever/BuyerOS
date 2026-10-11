# C61-25 owned bulk resource capture

From the repository root, with the existing frozen API environment and Docker
available, unset inherited `DATABASE_VARIABLES` in the child environment and run:

```powershell
services/api/.venv/Scripts/python.exe scripts/benchmark-bulk-capacity.py --output-dir artifacts/repair/bulk-new-run
```

Linux uses `services/api/.venv/bin/python`. The runner rejects every inherited DB
target and any existing output directory. Native discovery must contain exactly
three registered cases (50, 500, 10,000); execution must match those identities
with zero failure/error/skip. Partial raw captures remain available on failure.
The ordinary required API suite includes the refusal controls. The existing
owned-worker CI job also executes this separate opt-in workload and retains its
native discovery, JUnit, raw captures and source provenance.

The workloads reuse canonical bulk manifests, runtime `buyeros_api` with neither
superuser nor BYPASSRLS, same-intent replay, bounded 50-row chunks and 100-row result
pages. The two async sizes retain 50 initial conflicts, a before-commit rollback,
an actual separate-process resume, a refused blind retry and a reviewed 50-row
child. Native SQL/result assertions establish complete, unique results and
exact versions; resource sampling does not replace those assertions.

RSS comes from the actual API interpreter and the owned resume interpreter. On
Windows the existing bounded worker utility also samples its Popen launcher and
descendants; the executing PID must appear. Linux uses `/proc` VmRSS. Samples
start after data seeding and include preview, execution, chunks and result reads.
API RSS includes pytest, fixtures and allocations retained from prior dataset
cases. Reported sample maxima are not true peaks, PSS or cgroup memory; summing
process RSS can double-count shared pages. This is an in-process API workload,
not a deployed HTTP service or a remote worker/backend capacity measurement.

For async workloads, SQL snapshots record pending rows, committed processed
rows, status and age since `async_jobs.created_at`. That age includes execution
and is not broker dequeue latency. The sync 50-row path explicitly has no queue.
Duration includes observation overhead and one workload per dataset; it provides
no percentile, sustained-load result or adopted performance budget.

The runner refuses missing datasets, invalid units, incomplete memory/process or
queue denominators and any claim of live/release/budget acceptance. C61-25,
P05/P08, numerical memory/duration budgets, actual broker inflight recovery,
provider capacity, HK network, RUM and human UAT remain separate acceptance work.
Rollback removes these measurement files/CI steps and restores the prior native
API inventory guard; application/schema/auth/provider behavior is unchanged.
