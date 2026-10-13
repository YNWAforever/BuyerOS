# Exa + OpenCode Go research go-live

Status 2026-10-13: code ready on `claude/live-ui-exa-research` (PR #19). Nothing below
has been applied to production. Steps marked **OWNER** handle secrets or irreversible
production changes and must be done by the account owner.

Research runs end to end only when **all** of these hold: providers registered
(keys present), production schema current, Cloudflare worker executing, paid
admission and dispatch on, an approved account research policy, an approved
budget, and an approved buyer profile in the project.

## 1. Production database (OWNER, irreversible)

Production was last inspected at Alembic `0033`; code head is `0050`.

1. In Neon (`nameless-bar-15324691`, branch `br-autumn-block-b3exsqii`), create a
   recovery branch from the current production branch.
2. From `services/api`, with the owner/migration connection string in your own shell
   only (never committed or shared):

   ```bash
   BUYEROS_DATABASE_MIGRATION_URL='<owner DSN>' uv run --frozen alembic upgrade head
   ```

3. Confirm `SELECT version_num FROM alembic_version` returns `0050`.
4. Create the restricted runtime login per
   [cloudflare-production-setup-proposal-20261002.md](cloudflare-production-setup-proposal-20261002.md)
   (`buyeros_cf_runtime`, INHERIT member of `buyeros_worker`, NOBYPASSRLS, nonowner).

## 2. Secrets (OWNER)

Generate one machine secret locally, for example `openssl rand -base64 48`, and store it in both places:

| Where | Name | Value |
| --- | --- | --- |
| Vercel `buyer-os` production (sensitive) | `BUYEROS_WORKER_CURRENT_KEY_ID` | `cf-prod-20261013` |
| Vercel (sensitive) | `BUYEROS_WORKER_CURRENT_SECRET` | the generated secret |
| Cloudflare `buyeros-jobs` secret | `WORKER_CURRENT_SECRET` | the same secret: `npx wrangler secret put WORKER_CURRENT_SECRET --config services/cloudflare-jobs/wrangler.jsonc` |
| Vercel (sensitive) | `BUYEROS_EXECUTION_DATABASE_URL`, `BUYEROS_CHECKPOINT_DATABASE_URL` | `buyeros_cf_runtime` DSN |
| Vercel (sensitive) | `BUYEROS_EXA_API_KEY` | from dashboard.exa.ai |
| Vercel (sensitive) | `BUYEROS_OPENCODE_API_KEY` | OpenCode Go key from opencode.ai/auth |

## 3. Non-secret configuration

| Where | Name | Value |
| --- | --- | --- |
| Vercel | `BUYEROS_RESEARCH_MARKETS` | optional; comma list of ISO country codes (default in `providers/activation.py`) |
| Vercel | `BUYEROS_OPENCODE_MODEL` | optional; default `kimi-k3` (list: `curl https://opencode.ai/zen/go/v1/models`) |
| Vercel | `BUYEROS_RETENTION_POLICY_VERSION` | your reviewed policy id (max 64 chars) |
| Worker `wrangler.jsonc` vars | `WORKER_API_ORIGIN` | `https://buyer-os-nu.vercel.app` |
| Worker | `WORKER_API_ALLOWED_ORIGINS` | `["https://buyer-os-nu.vercel.app"]` |
| Worker | `WORKER_CURRENT_KEY_ID` | `cf-prod-20261013` |
| Worker | `RUNTIME_EPOCH` | read back from `worker_runtime_control` after step 5 |

## 4. Cloudflare resources

```bash
npx wrangler queues create buyeros-jobs
npx wrangler queues create buyeros-jobs-dlq
npx wrangler deploy --config services/cloudflare-jobs/wrangler.jsonc
```

Deploy with `EXECUTION_ENABLED=false` first. The Workflow `buyeros-job` is created by the deploy.

## 5. Select Cloudflare execution (OWNER: needs the admin DSN)

From `services/api`, with `BUYEROS_RUNTIME_ADMIN_DATABASE_URL` set in your own
shell, dry run first, then rerun with `--apply`:

```bash
uv run --frozen python tools/set_execution_runtime.py --expected-epoch <current> --backend cloudflare --enabled true --reason "Exa+OpenCode go-live"
```

Then set Vercel `BUYEROS_CLOUDFLARE_EXECUTION_ENABLED=true` and Worker
`EXECUTION_ENABLED=true` and `RUNTIME_EPOCH=<new epoch>`, and redeploy both. Confirm
Operations → Readiness shows a fresh probe receipt.

## 6. Switch on paid research

Set Vercel `BUYEROS_PAID_ADMISSION_ENABLED=true` and
`BUYEROS_PAID_DISPATCH_ENABLED=true`, then redeploy. In the app as a workspace admin:

1. Settings → approve the **account research** policy.
2. Settings → set a budget. Each Exa search holds up to $0.04 and each OpenCode Go
   fit proposal up to $0.10. OpenCode Go also has its own subscription caps
   ($12 per 5 hours, $30 per week, $60 per month); past them, calls fail until the
   window resets or Zen balance is topped up.
3. Offer → create a project and approve the buyer profile, using markets from the
   allowed list and language `en`.
4. Research runs → Start research. Watch Operations for failed jobs.

## Rollback

Set `BUYEROS_PAID_DISPATCH_ENABLED=false` and Worker `EXECUTION_ENABLED=false`
first. Then run the pause step in [cloudflare-worker-setup.md](cloudflare-worker-setup.md).
Removing the Exa or OpenCode key unregisters that provider on the next deploy.
Never release unknown holds just to empty a queue.
