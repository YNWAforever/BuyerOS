# Q10 local quality tools

These commands create only fictional, owned local PostgreSQL fixtures or read
supplied local label files. They do not approve providers, deployment, auth or
Cloudflare cutover. Full Q10 remains dependent on Q13/N02 and actual external
quality/load/UAT evidence.

## Directory baseline

Use the API's frozen virtual environment (`uv sync --frozen` in services/api)
and an available Docker daemon. Unset all four inherited database variables:
`BUYEROS_TEST_DATABASE_URL`, `BUYEROS_DATABASE_URL`, `DATABASE_URL`, and
`BUYEROS_WORKER_DATABASE_URL`. Do not replace the shared fixture guard or supply
production/Neon DSNs.

```powershell
services/api/.venv/Scripts/python.exe scripts/benchmark-workspace-directory.py --samples 30 --actors 1 --output test-results/q10-my-run.json
```

The opt-in case uses the existing owned PostgreSQL16 startup/guard helpers and
current Alembic head. W1/10/100/1000 each has exactly one visible membership per
actor. It verifies fixture RSA JWTs using the actual verifier, then serves the
real ASGI app against the real non-owner NOBYPASSRLS database role. No live Auth0
or Neon session is tested. `--actors 10/25` are supported, not measured in the
first baseline. Work is bounded to30–100 batches and15minutes. On timeout the
wrapper terminates pytest and removes only the recorded matching container ID.
The session teardown normally removes it first. The owner marker is retained
as evidence, without a DSN/password. An ownership mismatch fails closed.

Output and sibling XML/owner marker must be new. Warm metrics include all
requests, including errors; first-after-seed and three primers are reported
separately and are not process-cold proof. Actual runtime-role EXPLAIN plans
and pool member/nonmember/revocation probes are recorded. Directory query
count must be independent of unrelated W and <=6; CLIexit1 means this frozen
gate failed even when the capture test passed. This is in-process/local
loopback evidence, not geographic API load,10-minute stairs, browser/RUM,
worker throughput or product release acceptance. SQL time totals successful
cursor completions; failed SQL execution time is not independently observed.

Percentiles use linear interpolation over every request. `p99_stable` is a
conservative sample-size flag (n>=1000), not a statistical guarantee. Raw
samples remain available for a reviewer; the30-sample baseline flags it false.
Provenance records HEAD, dirty state and exact tool/route bytes. The archived
first-baseline source overlay preserves the earlier pre-review byte hashes.

## Research labels

```powershell
services/api/.venv/Scripts/python.exe services/api/tools/evaluate_research_goldset.py --goldset path/to/gold.json --predictions path/to/predictions.json --output test-results/q10-quality-new.json
```

See the archived fictional inputs in `Q10_LOCAL/reports/`. Goldset schema is
`buyeros.research-goldset.v1`; prediction schema is
`buyeros.research-predictions.v1`. Companies are unique across train/holdout;
all three distinct runs must cover exactly the frozen holdout. Each company
needs two distinct declared annotators, and disagreements require a separate
adjudicator/reason matching the reference. `declared_human_labels` requires
at least200 unique companies; the tool does not authenticate independence,
source truth/currentness, prompt-injection resistance or actual provider calls.
Fixture data is never a real goldset or accuracy result.

Precision=TP/(TP+FP); recall=TP/all reference positives (positive abstentions
are FN); coverage=decided/holdout; needs_review=abstained/holdout. Wilson95%
intervals accompany each proportion; zero denominator is null. Three runs
reuse companies and retain separate intervals, never a pooled3n claim.
[NIST method](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
The proposed plan threshold is precision point estimate>=95%, not a CI lower
bound promise. Safety violations (wrong company/workspace or unsupported
source IDs/current/inference declarations) prevent the offline gate passing.
Contact provider-marked-valid and actual employment/company relationship are
not measured by this research-only tool.

Output cannot overwrite inputs or existing evidence. Exit2 is invalid input;
exit1 is a safety violation or failed declared-label offline threshold; valid
fixture tool verification exits0 even if its hypothetical quality is poor.
Every report remains `live_verified=false`, `provider_calls=0` and
`release_accepted=false`, including perfect fixture/declaration scores.

The existing T29 wrapper retains legacy keys, adds schema/byte provenance and
refuses inherited DSNs/existing API or dispatcher output. Its actual1k/10k
load was not rerun for this local tools slice.

## Rollback

Revert only the two Q10 source commits plus their documentation metadata after
review. No application endpoint, schema, identity, membership, approval, actor,
hold, delivery or broker change requires runtime/data rollback. Reverse patch
applicability is verified separately; no production rollback rehearsal occurs.
