# Cloudflare operating conditions and cost worksheet

2026-10-01. Local results; no hosted latency or account bill was measured.

## Measured conditions

The two real local Queue/Workflow/HMAC/API/PostgreSQL repetitions each inject ten
non-provider jobs together, with native bodies bounded to one second. Durable
receipts and observed native intervals prove maximum concurrency one. Production
Cron is one minute; the benchmark invokes claims immediately. First-step age
includes fixture setup and runtime startup, measured from durable outbox creation.

| Metric | Repeat 1 | Repeat 2 |
| --- | ---: | ---: |
| First-step P50 / P95 seconds | 7.20 / 9.85 | 8.61 / 14.07 |
| Peak native bodies | 1 | 1 |
| Cold engines: workspaces / ticks | 100 / 10 | 100 / 10 |
| Cold claim-tick P95 ms | 115.17 | 173.65 |
| API fixture CPU seconds | 2.66 | 3.58 |
| API fixture peak RSS bytes | 165421056 | 172158976 |
| Actual probe receipt age seconds | 6.00 | 6.58 |

Memory is the entire Python fixture process peak, excluding Node/workerd/Docker
children. Database connection and queue/fairness ages are in
`artifacts/cloudflare/CF07-operating-benchmark-final-repeat{1,2}.json`.
Both first-step P95s meet the specified local 120-second target. Native network
operations (45 seconds), API steps (60), HTTP (75), and Workflow steps (90) keep
their production limits. Provider latency and hosted cold starts remain untested.

The independent actual SQL read benchmark uses 10,000 fictional buyers across
100 workspaces, a bounded 1,000-item actor snapshot, and a real offset900/limit100
page. Thirty sequential reads yield P50/P95 42.42/58.60ms; ten concurrent reads
yield P95 262.44ms (one actor) and 258.65ms (distinct actors), 11 queries/request,
50,721 bytes/page, ten connections afterward. ASGI transport has no external
network. This measures one actual late page, not fetching all 10,000 rows.

## Monthly scenario, not a quote

A 30-day month has 43,200 minute ticks. While enabled, even an empty system
sends one probe through Queue/Workflow and makes one claim plus one maintenance
API call per tick. With the app proxy and native API, that is approximately
86,400 signed HTTP requests and 172,800 Vercel function invocations before any
customer job. It also means about 129,600 Queue operations and 43,200 probe
Workflow steps, before retries. Disabled execution returns before network I/O.

Illustration: 10,000 jobs/month, four successful native units/job, ten durable
Workflow actions/job including waits, messages under64KB, no retries or paid
providers. Queue operations are about159,600; Workflow steps143,200. Forty
thousand native calls plus10,000 publication calls add about100,000 two-hop
Vercel invocations. Every status/retry adds work. The global one-step bound is
not a spend cap; CPU, storage, logs, retention and other account workloads count.

The proposed Workers Paid base is US$5/month. Under this illustration, Queue
operations and Workflow steps fit their published included amounts; account-wide
CPU/request/storage overages, tax, Neon, Vercel and provider charges are additional.
Use these rates only after verifying the selected account plan and current bill.
[Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[Queue pricing](https://developers.cloudflare.com/queues/platform/pricing/),
[Workflow pricing](https://developers.cloudflare.com/workflows/reference/pricing/).

One-minute database queries prevent the usual five-minute Neon inactivity window.
Inference: an enabled all-day dispatcher can keep compute active for720 hours/month;
at0.25CU that is180CU-hours. Read-only account metadata now confirms production project `nameless-bar-15324691`,
PG18 in Singapore, `free_v3`, autoscale0.25..2CU. Its endpoint was actually
suspended/idle; no database queries were made. The current published Free allowance
is100CU-hours per project per month. Therefore the180CU-hour minimum all-day
scenario exceeds Free; an increased compute size costs more. No total dollar saving
or implicit Neon upgrade is claimed. Remaining allowance and actual billing
were not read. [Neon current Free quota](https://github.com/neondatabase/website/blob/main/content/faqs/free-plan-limits-and-quotas.md).
[Neon scale-to-zero source](https://github.com/neondatabase/website/blob/main/content/docs/introduction/scale-to-zero.md).
Approved working-hour scheduling could reduce cost but would change readiness and
queue latency; it is a separate design decision, not silently implemented here.

## Bounded feasibility preview proposal

Use a fresh empty PG18 project `BuyerOS-CF-preview-20261001`, Singapore,
Free, min=max0.25CU, subject to actual account quota/configuration readback.
A two-hour test window implies0.5CU-hours at that size, plus startup and
scale-to-zero tail; it is not a hard bill cap. Do not copy production data,
roles, connection strings or fixtures. Disable the preview Cron/selector at
completion or two hours, whichever occurs first. No scheduled automation exists.
The separate Cloudflare account's current billing plan remains unverified;
US$5/month is the proposed Paid base if not already active, before account-wide
metered overages. No Neon/Vercel paid-plan change is included in preview approval.
Stop and report any additional paid requirement before proceeding.

## Activation measurements still required

Protected hosted package/PDF/checkpoint and both-hop90-second proofs; selected
Cloudflare account/plan and locality/privacy review; Vercel plan/compute billing;
Neon actual size/rate/autosuspend; real probe/backlog alerts; authenticated staff
continuity. Monitor hourly usage initially. Retain paid admission/dispatch, R2,
mailbox/CRM/sending off. Delivery remains403 `DELIVERY_DISABLED`.
