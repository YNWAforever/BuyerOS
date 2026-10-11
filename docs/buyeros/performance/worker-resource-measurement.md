# Owned worker resource capture (C61-25; partial P05/P08)

Reuse `scripts/benchmark-worker-capacity.py` with distinct new output/JUnit paths.
The runner rejects inherited database variables and starts its own disposable
PG16 fixture, Valkey broker and two Celery solo processes. Paid dispatch remains
disabled; the workload deletes expired fixture source metadata without provider
or private-object IO. The original 25/3/1 tenant backlog, first-cycle fairness,
29 distinct generation-1 intents and restart between committed work are retained.

The capture adds RSS samples at startup and each 200 ms readback. Windows venv
launchers spawn a separate interpreter, so samples include the owned launcher's
process tree with explicit owner, PID, parent and depth (maximum 16 PIDs/depth 4).
Linux Celery solo runs in the owned PID. Windows uses `GetProcessMemoryInfo.WorkingSetSize`; Linux uses
`/proc/<pid>/status` `VmRSS` converted from KiB to bytes. Report the sample count,
observation window, method and sampled maximum for each PID; any tree RSS sum may
double-count shared pages. This does not measure
the all-time peak, PSS, cgroup memory, broker/DB memory or per-request allocations.
Unsupported or missing process measurements fail the new capture; Windows launcher-only samples are refused.

SQL snapshots retain the oldest `created_at` age per workspace/state, including
ready, dispatched and done rows. Every snapshot accounts for all 29 owned intents;
the initial state is ready and final state done. The additional SQL observation
query is part of the measured duration. These are backlog ages at observation,
not actual dequeue latency or a queue wait percentile. The raw denominators are
retained, and empty, nonfinite, negative or incomplete observations are refused.

No memory, queue-age or fleet SLO is adopted by this change. Historical captures
without these new observations remain historical functional evidence. Neither
their success nor the new local samples establish production provider capacity,
in-flight crash/redelivery, sustained HK latency, cost acceptance or P05/P08 pass.
The existing strict lease-expiry, stale-generation/epoch and unknown-hold controls
are run separately and identified by their native names; they do not turn the
between-commits restart into an in-flight worker-kill measurement.

The required worker suite collects and executes all 256 tests, including the
ten new resource controls, with zero skips. The opt-in real Celery capture remains
one explicitly discovered case in its separate CI job. Rollback is the preceding
`e885e99e` benchmark tools/workflow; no application, schema, identity, provider,
delivery or retained hold is changed.
