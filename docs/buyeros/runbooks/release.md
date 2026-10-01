# BuyerOS staged release procedure (draft, not executed)

This procedure is a review artifact. It authorizes no cloud creation, deploy, secret entry, paid request, production migration or delivery. Replace placeholders only after the named owner approves an exact target and reviewed source SHA. Keep the single FastAPI domain API, SQLAlchemy/Alembic migration owner, Celery worker/dispatcher and one Valkey broker.

## Configuration to review before any external action

| Component | Exact inputs | Required evidence |
| --- | --- | --- |
| Vercel app/Vinext | Public same-origin `/v1/*`; Auth0 issuer, public client ID and API audience; runtime `BUYEROS_INTERNAL_API_URL` injected by the app service binding | Auth0 application is a public SPA using authorization code + PKCE; allowed callback/logout origin matches the chosen Site; token remains in memory. |
| Vercel internal FastAPI service | `BUYEROS_DATABASE_URL` (Neon pooled restricted runtime), Auth0 issuer/audience, exact CORS origins and environment; direct migration credential stays outside Vercel builds | Dedicated non-owner runtime role, current memberships/RLS, exact HTTPS Site origin, no secret values in build/client bundle. |
| API switches | `BUYEROS_LIVE_READ_ENABLED`, `BUYEROS_PAID_ADMISSION_ENABLED`, `BUYEROS_RECONCILIATION_ENABLED`; read/write/expensive per-minute bounds | Start with paid admission false, read/reconciliation true. Any enabling is a separately recorded pilot decision. |
| Celery worker and dispatcher/Render Singapore | `BUYEROS_DATABASE_URL`, `BUYEROS_BROKER_URL`, `BUYEROS_PAID_DISPATCH_ENABLED`, `BUYEROS_RECONCILIATION_ENABLED`, `BUYEROS_RETENTION_POLICY_VERSION` | Same authorized Neon tenant data, one persistent non-evicting Valkey broker, separate worker DB role, paid dispatch false until vendor/finance gate. |
| R2 private object store | `BUYEROS_R2_ENABLED`, `BUYEROS_R2_ACCOUNT_ID`, `BUYEROS_R2_BUCKET`, `BUYEROS_R2_ACCESS_KEY_ID`, `BUYEROS_R2_SECRET_ACCESS_KEY`, `BUYEROS_R2_JURISDICTION` | Private APAC bucket, server-only credentials, minimum permissions, tested deletion/restore journal and no public object link. |

Never place a secret, DSN, full callback URL with credentials, contact value or provider reference in this document or task output. The current repository does not contain a verified Render/Neon/R2 deployment manifest; create an exact reviewed config diff for the selected account only after target and account ownership are established.

## Staged order and checks

1. Record `git rev-parse HEAD`, `git status --short`, `git diff --check`, reviewed artifact hashes and the exact release SHA. Review the current strict API577/worker174 zero-skip gates, the source-qualified T29 representative performance artifacts and the four-case T30 fixture staff journey; close remaining external recovery/accessibility gates. Run required no-skip JUnit gates; distinguish fixtures from live verification.
2. Record the named staging target, backup/export access, direct migration DSN and pooled runtime DSN without printing values. Confirm a private restore target, sole Alembic head and a compatible prior app version. Run migration and restore rehearsals only on an isolated disposable or explicitly approved staging database. A production migration needs its own authorization.
3. Configure Auth0 public SPA callback and Site origin, current membership owner, API CORS, Vercel app/internal API, external Render worker/dispatcher, Neon roles, one Valkey broker and private R2. Keep paid switches false, mailbox/CRM disconnected and delivery 403.
4. On an approved staging target, check unauthenticated `/health/live`, authenticated per-workspace `/readiness` and `/capabilities`, wrong audience/tenant/revoked role denials, broker heartbeat, RLS tenant switch and explicit 503 for unselected providers. Record target URL, UTC time and deployed SHA; a decorative Connected label is insufficient.
5. Run the real staff journey with approved fake/staging identities and no paid adapter first. Exercise en/zh-HK at desktop/mobile, pagination, stale basis/approval, partial errors, restart recovery and export authorization. Report each gate with exact pass/fail/skip counts and screenshots.
6. Only after separate written pilot approval, bind the exact workspace/users/markets/purposes/time window/provider/version/max spend and stop thresholds. Compare configured cap/price to approved values, verify provider acceptance/status/reconciliation and then enable only the approved paid switches. Optional contact remains off if its separate evidence is absent. There is no delivery activation in MVP-A.

## Stop and recovery

On tenant leakage, unauthorized contact access, lost budget lock, unexplained charge, missing provider status or accidental delivery, disable new admission and paid dispatch; preserve read access and reconciliation when safe. Retain unknown-operation holds, outbox and ledger history. Do not flush Valkey, reset schema or assume a timeout means rejection. Use `recovery.md` for lease, deletion and restore steps. Roll back only to an application compatible with the migrated schema; otherwise roll forward additively. Revalidate deletion tombstones before exposing restored data.

## Evidence still needed

The specifically authorized app/API deployment4181062 is READY on the existing production Vercel project, with source/alias readback and actual anonymous HTTP/public-bootstrap acceptance4/4. The earlier Neon/Auth0/FIMMICK setup has exact four-row readback and prior human UI visibility. Current deployment evidence is in T30_RELEASE_CANDIDATE_HANDOFF_20261001.md and artifacts/t30-production-*-4181062-20261001.*. All nine saved production variable records are unchanged; paid admission and R2 remain false. This deployment approval does not authorize provider spend, worker/R2 provisioning, database writes/migration or a pilot. Authenticated API/full live continuity, compatible external worker/Valkey, private R2, policy/provider evidence, external restore custody and a bounded pilot decision remain required. Do not overwrite the nine saved production values or set the injected binding variable yourself.
## Current compatible worker requirement

Reviewed source4181062 binds recipient_context in queued zero-cost template commands. Use that source or a proven compatible newer worker before dispatching them. Freeze admission/dispatch before a worker rollback and preserve the queued bound commands; an older62d40bc worker does not enforce the new recipient binding. Reverting the API/frontend alone does not authorize replay through that older worker.
