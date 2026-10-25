# Public demo intake

Intake is disabled by default and has no dependency on product Auth, tenant
credentials, product rate limits, outreach, email providers or paid models.
The Node routes are `/api/marketing/leads/challenge` and `/api/marketing/leads`;
they call only the independent API routes `/marketing/leads/challenge` and
`/marketing/leads`. The production API registers the same router. A separate
minimal API app is available for isolated synthetic acceptance.

## Local synthetic fixture

From the repository root:

```sh
services/api/.venv/bin/python services/api/tools/run_marketing_intake.py
services/api/.venv/bin/python services/api/tools/run_marketing_intake.py --serve
```

The first command allocates/proves a unique PostgreSQL16 container, migrates only
its `marketing_intake` schema, creates a restricted login, runs the API contracts,
then checks the exact receipt/container/owner label before cleanup. It uses the
already installed image with `--pull=never`. It does not inspect `.env` files or
inherit application settings. Platform proxy and CA configuration is retained.

The second command keeps the owned fixture and API on `127.0.0.1:8013` alive for
browser acceptance at `http://127.0.0.1:5195`. It prints a private mode0600 file
under `/tmp/buyeros-marketing-*.json`. Read **only its `node` dictionary** into
the isolated frontend child environment; never print or commit this dictionary.
No frontend process or build is created by this runner. Stop with Ctrl-C after
acceptance to perform ownership-checked cleanup and remove the private handoff.

To independently verify persisted browser receipts while the fixture is alive:

```sh
services/api/.venv/bin/python services/api/tools/run_marketing_intake.py \
  --readback /tmp/buyeros-marketing-REPLACE.json --receipt-id REPLACE_UUID
```

Readback revalidates the current container/port/database before opening SQL and
returns only receipt ID, locale, synthetic flag and timestamp. Omit
`--receipt-id` to list the synthetic fixture's receipts. The runner stores target,
role, source fingerprints, test and cleanup receipts under
`outputs/marketing-full/intake/run-*`. Those receipts contain no gateway token
or runtime password.

## Server configuration

| Node server only | Independent API | Meaning |
| --- | --- | --- |
| `MARKETING_ENABLED=1` | `BUYEROS_MARKETING_ENABLED=1` | Explicit enable switch; absent means503 without SQL initialization |
| `MARKETING_SYNTHETIC_MODE=1` | `BUYEROS_MARKETING_SYNTHETIC_MODE=1` | Local synthetic mode; API accepts only email domains ending `.test` |
| `MARKETING_REAL_INTAKE_APPROVED=1` | `BUYEROS_MARKETING_REAL_INTAKE_APPROVED=1` | Additional required gate when synthetic mode is off; currently unapproved |
| `MARKETING_PUBLIC_ORIGIN` | `BUYEROS_MARKETING_PUBLIC_ORIGIN` | One exact serialized HTTPS origin, or explicit loopback HTTP origin for local acceptance |
| `MARKETING_API_ORIGIN` | — | Exact HTTPS/loopback HTTP API origin without path/credentials |
| `MARKETING_GATEWAY_KEY` | `BUYEROS_MARKETING_GATEWAY_KEY` | Same cryptographically generated secret, minimum32 ASCII characters; never browser/public env |
| — | `BUYEROS_MARKETING_DATABASE_URL` | Explicit dedicated PostgreSQL database and restricted intake login; no fallback to tenant DSN |
| — | `BUYEROS_MARKETING_RETENTION_DAYS` | Required explicit1–365days; local synthetic fixture sets1 |
| — | `BUYEROS_MARKETING_GLOBAL_PER_HOUR` | Durable rolling global successful-submission budget; default20 |
| — | `BUYEROS_MARKETING_EMAIL_PER_DAY` | Durable rolling per-email successful-submission budget; default3 |
| — | `BUYEROS_MARKETING_CHALLENGES_PER_MINUTE` | Durable global challenge-issuance budget; default100 |

Only the enabled/synthetic booleans may be serialized by the public page. A
boolean does not prove availability: the challenge endpoint is the availability
probe and returns503 when required server configuration/storage is unavailable.

POST requires an exact Origin. The challenge GET accepts an exact Origin, or a
missing Origin together with `Sec-Fetch-Site: same-origin` and a request URL
whose origin exactly matches configuration (browsers omit Origin on same-origin
GET fetches). All supplied foreign/null/combined origins fail403. The Node proxy
forwards only the configured Origin, dedicated gateway key, JSON Content-Type
and UUID Idempotency-Key; it never forwards cookies, Authorization or IP claims.
The API requires the exact Origin and gateway key on every request. Neither
boundary trusts forwarding/IP headers or exposes tenant routes/data.

## Storage and retry semantics

Apply `buyeros_api.marketing.migrate.migrate(connection)` only using an explicitly
approved **dedicated intake database migration connection**. This migration is
separate from tenant Alembic history and is never run by HTTP. Provision a
non-owner runtime role with NOSUPERUSER/NOBYPASSRLS and only USAGE on
`marketing_intake` plus SELECT/INSERT/UPDATE/DELETE on its tables. Runtime
connections reject superuser/BYPASSRLS roles. The local runner performs and
records this provisioning only after target identity proof.

Challenges are database-issued random UUIDs with a2second minimum age,15minute
expiry and single use. Submission size is capped at8192bytes on both streaming
boundaries. The honeypot must be empty. The API validates all fields and rejects
unknown keys. Global/email budgets, challenge consumption and receipt insertion
share one database transaction and transaction lock across API instances.

The API returns201 only after commit; deferred commit failures return503 and
roll back the lead/challenge. An unchanged request with the same UUID key
returns200 with the committed receipt even after challenge expiry or response
loss. The business payload fingerprint excludes the challenge, allowing refresh
on retry. A changed payload with the same key returns409. A consumed challenge
with another key returns422. Idempotency lasts for the configured lead retention
period. Only synthetic receipts may appear in local acceptance.

Expired challenges and leads are purged transactionally on successful intake
activity. There is no background scheduler in this subsystem; an independently
approved scheduled retention job is required for a strict wall-clock deletion
guarantee during inactivity. Real enablement remains gated on owner-approved
data handling/publication details, an explicit retention decision, restricted
database provisioning, secure gateway configuration and operational retention.
No real intake, provider integration, deployment or sending was performed.
