# Authenticated conversation QA (real account, dedicated workspace)

This is the only path that proves the conversation studio end to end with a real
account. Ordinary CI is fixture-based and cannot reach a real Neon account.

## One-time setup (owner)

1. Create the protected environment `buyeros-conversation-qa` in
   **Settings → Environments**. Add yourself as a required reviewer (recommended)
   so no run starts without an explicit approval. The same reviewers gate any live
   model-recall run; do not remove them to speed up a dispatch.
2. Add these **environment** secrets (not repository secrets):

   | Secret | Purpose |
   | --- | --- |
   | `BUYEROS_NEON_REAL_EMAIL` | Dedicated production-QA account email (nonbillable journey) |
   | `BUYEROS_NEON_REAL_PASSWORD` | Dedicated production-QA account password (nonbillable journey) |
   | `BUYEROS_MODEL_QA_EMAIL` | Isolated model-QA account email (manual rehearsal and paid recall) |
   | `BUYEROS_MODEL_QA_PASSWORD` | Isolated model-QA account password (manual rehearsal and paid recall) |
   | `BUYEROS_QA_PROTECTION_BYPASS` | Optional: only if the candidate is a protected preview |

   The model-QA account is used against the isolated Neon QA database/auth
   provisioned for paid acceptance and for the manual nonbillable rehearsal. Both
   isolated modes map `BUYEROS_MODEL_QA_*` to the Playwright standard names. They
   have no fallback to the production QA account, and the standard nonbillable step
   cannot use the model account. Never commit or paste these values anywhere in
   the repository or a chat. Account credentials are only exposed to the test step
   for the current mode; checkout, dependency installation and artifact upload
   never receive them.

3. Add these protected **environment variables** to the same environment. They
   are the authority for isolated modes; dispatch inputs must equal them or the
   workflow fails before any isolated credential is exposed:

   | Variable | Value |
   | --- | --- |
   | `BUYEROS_MODEL_QA_WORKSPACE_ID` | `064d5168-709b-57e7-a7c3-871c2f16c814` |
   | `BUYEROS_MODEL_QA_PROJECT_ID` | `bd632836-3298-58de-aa85-59213cb28ab2` |
   | `BUYEROS_MODEL_QA_SOURCE_LABEL` | `product approved` (approved profile fact source) |

   The approved QA source checkbox text is exactly `product approved`; it is independent
   of the synthetic buyer names. Do not substitute a provider, approval or
   production source.
4. Confirm membership in the isolated model-QA workspace/project as well as the
   standard QA tenant. Set `NEXT_PUBLIC_CONVERSATION_HOME=true` for both the
   frontend build and the API runtime. The journey reads the QA project's sales
   capability, verifies the corresponding workspace home, and then opens the
   discussion directly. A disabled QA workspace exercises the same path as the
   reported issue. The database-backed browser suite also tests direct entry with
   sales disabled.

## Deployment protection on previews

Vercel preview deployments are protected by Vercel Authentication by default; an
anonymous `GET` answers **401** before the app loads. Choose one of:

- **Unprotected candidate** — target the immutable URL of an unprotected deployment
  (the journey then needs no extra secret). Mutable aliases are refused.
- **Bypass token** — in the Vercel project: *Settings → Deployment Protection →
  Protection Bypass for Automation*, create a token, and store it as the
  environment secret `BUYEROS_QA_PROTECTION_BYPASS`. The Playwright fixture
  (`tests/e2e/qa-protection.fixture.ts`) makes **one** candidate-origin request
  carrying `x-vercel-protection-bypass` with `x-vercel-set-bypass-cookie: true`
  (no redirect following); that response sets the bypass cookie in the browser
  context's shared cookie jar. Browser requests then carry only the cookie — the
  raw token is never a context-wide header, is not attached to cross-origin
  redirects/assets, and is never echoed into the app. With the env var absent the
  fixture is a no-op and the run targets an unprotected candidate as before.

If a protected candidate is targeted without a bypass, the journey fails in
seconds with
`BLOCKED: the QA candidate is protected by Vercel Authentication; set BUYEROS_QA_PROTECTION_BYPASS …`
instead of a locator timeout.

## QA preview origin configuration

The QA auth callback and browser must run on the **exact immutable Vercel
deployment host**, which is only known after the deployment exists. Do not set
`BUYEROS_PUBLIC_ORIGIN` to a guessed hostname. Instead, deploy the QA candidate
with this narrow preview-only opt-in and let `lib/auth/neon-config.ts` derive the
extra allowlist entry from the platform-injected `VERCEL_URL`:

| Deployment environment variable | Value |
| --- | --- |
| `BUYEROS_NEON_ENVIRONMENT` | `preview` |
| `BUYEROS_NEON_QA_PREVIEW_ORIGIN_ENABLED` | `1` |
| `BUYEROS_QA_PREVIEW_PROJECT_ID` | Expected Vercel project id (`prj_…`) |
| `BUYEROS_QA_PREVIEW_REPO` | `YNWAforever/BuyerOS` |
| `BUYEROS_QA_PREVIEW_REPO_ID` | Exact GitHub repository id (numeric) |
| `BUYEROS_QA_PREVIEW_BRANCH` | Exact PR/commit branch, equal to `VERCEL_GIT_COMMIT_REF` |
| `BUYEROS_RUNTIME_SOURCE_SHA` | Full reviewed 40-character source SHA |
| `BUYEROS_QA_PREVIEW_EXPECTED_ORIGIN` | Optional; if set, must equal `https://$VERCEL_URL` |
| `BUYEROS_QA_PREVIEW_TEAM_ID` | Optional; if set, must equal platform `VERCEL_TEAM_ID` |

`VERCEL_URL`, `VERCEL_ENV`, `VERCEL_PROJECT_ID`, `VERCEL_TEAM_ID` and the
`VERCEL_GIT_*` metadata are injected by Vercel; never copy them from a request
`Host` or forwarded header, and do not set them manually. The app refuses the
opt-in unless `VERCEL_ENV=preview`, `NODE_ENV=production`, the environment is
`preview`, both the preview and production staging flags are not enabled together,
and the platform project/repo/branch/source metadata exactly matches the expected
values above. `BUYEROS_PUBLIC_ORIGIN` and `BUYEROS_NEON_EXPECTED_PUBLIC_ORIGIN`
remain the independently bound canonical origin; the candidate host is only an
additional allowlisted origin. Production staging with
`BUYEROS_NEON_STAGED_ORIGIN_ENABLED` is unchanged and remains production-only.

The isolated Neon Auth branch must also list the exact `https://<candidate>.vercel.app`
origin as a trusted domain for the QA run, in addition to its canonical origin.
Add it from the deployment metadata, never by guessing the next SHA's host before
the build. Remove it after acceptance.

Deployment-specific values can be supplied through the deployment request (for
example `vercel deploy --prebuilt --target preview --env KEY=value …`) so a new
reviewed SHA does not require editing project-wide environment variables. The QA
workflow rejects any candidate whose platform metadata does not match the reviewed
source SHA and repository binding.

## Run

Dispatch the reviewed workflow from `main` with the immutable deployment origin,
the QA workspace/project ids and the full commit SHA the deployment was built from.
The separate metadata job uses `buyeros-runtime-readonly` and checks out trusted
`main` before it receives the server-side Vercel token. Its branch restrictions and
review requirements still apply. Only after metadata verification succeeds can the
QA job receive the account credentials from `buyeros-conversation-qa`:

```bash
gh workflow run buyeros-conversation-qa.yml \
  --ref main \
  -f origin=https://<immutable-candidate>.vercel.app \
  -f workspace_id=<qa-workspace-uuid> \
  -f project_id=<qa-project-uuid> \
  -f expected_source_sha=<reviewed-full-source-sha>
```

The QA job checks out exactly `expected_source_sha` (or the PR head SHA for the
label path), fails if `git rev-parse HEAD` differs, and only then installs
dependencies. `persist-credentials: false` is set on both checkouts. The workflow
refuses non-HTTPS origins, non-Vercel hosts, a non-bare origin, malformed UUIDs, a
short SHA and a malformed bypass token. Before the login job, management API
readback must prove a READY immutable deployment belonging to the protected
project/team, with the expected repository binding and full commit SHA. Redirects
are refused, and the management token is never sent to the candidate. These are
deployment-metadata checks; protected runtime/database binding, attestation and
actual candidate-bound acceptance remain separate release gates.

Verify the bypass offline before dispatching (the token stays in the environment,
never on the command line):

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -H "x-vercel-protection-bypass: $BUYEROS_QA_PROTECTION_BYPASS" \
  "https://<candidate>.vercel.app/"
```

## What the journey proves

Only non-billable, read-only behaviour plus the QA workspace's own discussions:

- real sign-in and scope landing on the QA workspace/project
- direct discussion entry with the QA project selected
- three durable turn responses with distinct turn IDs and the same thread ID
- sending after reload and opening the saved URL in a second tab, with all three user messages and assistant responses present in order
- unsent composer text survives reload (protection of unsent messages)
- an unconfigured model/action is shown honestly and never faked; any proposal
  card is **not** approved (no provider spend, no paid admission)
- no uncaught console errors during the journey
- EN and zh-HK rendering of the same surface

Screenshots and JUnit are uploaded as the `buyeros-conversation-qa` artifact.

## Model recall acceptance

The PostgreSQL integration test `services/api/tests/test_discussion_context_recall.py` submits identical follow-ups to two saved discussions. An offline adapter derives its answer from the history it receives. This covers thread isolation and durable model-reply handling. Live model quality is verified separately on a candidate.

Live recall is the only billable part of this workflow. It is opt-in, manual and
capped at **one US dollar** for this acceptance; it must never run automatically
from a label, repository variable, push or schedule.

Manual dispatch gates, all required together:

1. `live_model_recall=true` (workflow_dispatch boolean input; false by default and
   impossible to set on a `pull_request` label event).
2. `authorized_spend_usd=1` (any other value fails target validation).
3. `model_source_label="product approved"` exactly equals protected environment variable
   `BUYEROS_MODEL_QA_SOURCE_LABEL`; it is independent of the synthetic buyer names
   and is not a secret.
4. `isolated_workspace_id` and `isolated_project_id` exactly equal the protected
   environment variables `BUYEROS_MODEL_QA_WORKSPACE_ID` and
   `BUYEROS_MODEL_QA_PROJECT_ID`. The workflow rejects UUID-shape-only dispatch
   values before exposing isolated credentials.
5. Protected environment `buyeros-conversation-qa` approval by its required
   reviewer.

After the nonbillable journey has passed for the reviewed SHA, rehearse the same
isolated credential without paying: this dispatch uses the isolated model-QA
account and isolated tenant, runs only the nonbillable journey, and never sets
`live_model_recall`:

```bash
gh workflow run buyeros-conversation-qa.yml \
  --ref main \
  -f origin=https://<immutable-candidate>.vercel.app \
  -f workspace_id=064d5168-709b-57e7-a7c3-871c2f16c814 \
  -f project_id=bd632836-3298-58de-aa85-59213cb28ab2 \
  -f expected_source_sha=<reviewed-full-source-sha> \
  -f isolated_workspace_id=064d5168-709b-57e7-a7c3-871c2f16c814 \
  -f isolated_project_id=bd632836-3298-58de-aa85-59213cb28ab2 \
  -f qa_isolated_rehearsal=true
```

The rehearsal inputs and the paid-recall inputs must equal the protected
environment variables `BUYEROS_MODEL_QA_WORKSPACE_ID`,
`BUYEROS_MODEL_QA_PROJECT_ID` and (for recall) `BUYEROS_MODEL_QA_SOURCE_LABEL`.
The workflow checks that equality before exposing isolated credentials. The
dispatch form still has its existing required `workspace_id`/`project_id` fields;
for isolated modes pass the same isolated UUIDs there too (the workflow selects
the isolated inputs and validates both against the protected environment).

Then dispatch the paid recall separately (never by adding a label). It uses the
same isolated model-QA issuer/account and tenant, and runs only the two-thread
recall test:

```bash
gh workflow run buyeros-conversation-qa.yml \
  --ref main \
  -f origin=https://<immutable-candidate>.vercel.app \
  -f workspace_id=064d5168-709b-57e7-a7c3-871c2f16c814 \
  -f project_id=bd632836-3298-58de-aa85-59213cb28ab2 \
  -f expected_source_sha=<reviewed-full-source-sha> \
  -f isolated_workspace_id=064d5168-709b-57e7-a7c3-871c2f16c814 \
  -f isolated_project_id=bd632836-3298-58de-aa85-59213cb28ab2 \
  -f live_model_recall=true \
  -f authorized_spend_usd=1 \
  -f model_source_label="product approved"
```

The recall test creates exactly two independent saved discussions containing two
different ordered buyer pairs (`Alder`/`Birch` and `Cedar`/`Willow`) in the
isolated Neon QA database. In each saved thread it selects the configured approved
source, reloads, asks which buyer was second, then asks which buyer was first in a
second tab. Each answer must name only the requested buyer and must not name the
other buyer in the pair or either buyer from the other saved thread. After both
threads exist, each is reopened and read back independently; its three user
messages and three assistant replies must match the first read, and no stored
reply may name a buyer from the other thread.

The billable scope is fixed at **6 turns** (2 threads × 3 turns) plus 2 source
selections. The paid dispatch runs only this test, against the isolated model-QA
account/database; the standard nonbillable step is skipped rather than running the
production QA account against the isolated database. Run the manual
`qa_isolated_rehearsal=true` dispatch first to prove the same isolated credential
and tenant on the same candidate without paying. The test fails if any decision,
approval, dispatch, quote, cancel, native-action or send mutation occurs, and it
does not approve or click those controls. Worker count is 1 and retries are 0. If
the run fails, do not rerun the paid test automatically; inspect the
`results-recall.xml` JUnit result and explicitly re-authorize a new manual
dispatch.

The default nonbillable run reports durable messaging separately and skips live
recall. Screenshots and JUnit are uploaded; Playwright traces are deliberately not
uploaded because they can contain session/login request data. Only results.xml and
the deliberate PNG screenshots are retained.

## Enabling generated replies for the isolated QA project

The browser login identifies the QA user. The backend uses the BuyerOS service account through OpenCode Console. DeepSeek V4.1 Flash (`deepseek-v4.1-flash`) is the default model for generated discussion replies in approved projects. Store the service-account key as the sensitive `BUYEROS_CONVERSATION_MODEL_API_KEY` variable on the candidate branch. The key needs Models Request permission. [OpenCode service-account documentation](https://opencode.ai/docs/console/api/#service-accounts)

The published token rates are US$0.30 per million input tokens and US$1.20 per million output tokens. The route caps each call at 6,000 input and 1,000 output tokens, which costs at most US$0.003 at those rates. BuyerOS reserves US$0.10 per call. The QA policy authorizes only the synthetic offer source. [OpenCode Console pricing and privacy](https://opencode.ai/docs/console/models/#pricing)

Add the reviewed model, tariff ceiling, retention terms, evidence dates and account reference to `REVIEWED_ROUTES` in the conversation provider registration. Bind its contract hash to the approved policy for the exact QA workspace and project. Set `BUYEROS_CONVERSATION_MODEL_WORKSPACE_ID`, `BUYEROS_CONVERSATION_MODEL_PROJECT_ID` and `BUYEROS_CONVERSATION_MODEL_ENABLED=true` for that preview. The existing `NEXT_PUBLIC_CONVERSATION_HOME`, `BUYEROS_PAID_ADMISSION_ENABLED` and `BUYEROS_PAID_DISPATCH_ENABLED` flags must also be `true`. Check the remaining workspace, project and conversation allowances before dispatch. All three apply to each call.

The repository's protected QA environment requires a reviewer. When its branch policy allows only `main`, dispatch from a reviewed workflow on `main` with the immutable candidate URL and SHA. The production release also requires an account binding and an existing approved budget for its own project.

## Other release gates

- The separately authorized live model recall (`live_model_recall=true`, max US$1)
  is the only paid acceptance in this workflow; it is never implied by a label
  or by a repository variable.
- Real provider dispatch (Xverum) outside the recall source, worker/queue
  execution, delivery and exports remain separate authorised acceptance and keep
  their own release gates. The journeys here never approve or dispatch them.

## Pre-merge run (label-gated)

`workflow_dispatch` is only available once this file is on the default branch, so
a pull request can run it earlier by adding the `qa:real` label. Fork PRs are
refused explicitly, and the protected environment still requires its reviewers.

One-time setup for the label path — repository **variables** (not secrets):

| Variable | Value |
| --- | --- |
| `BUYEROS_QA_ORIGIN` | The Vercel deployment origin under test |
| `BUYEROS_QA_WORKSPACE_ID` | Dedicated QA workspace UUID |
| `BUYEROS_QA_PROJECT_ID` | Dedicated QA project UUID |

Then add the `qa:real` label to the PR. Label runs execute only the nonbillable
journey: the live-recall environment gate is hard-wired false for
`pull_request` events, so the paid test is skipped even if the label is added.
The workflow uses the PR head SHA as the expected source, pins the QA checkout to
that SHA, uses the environment secrets for the account, and uploads
`buyeros-conversation-qa` (JUnit + screenshots only). Live recall still requires a
separate manual dispatch and protected-environment approval as described above.

## Release evidence

A release candidate is accepted only when the nonbillable journey and the
separately authorized live-recall run both pass for the same reviewed SHA and
immutable Vercel candidate. Keep `results-nonbillable.xml`, `results-recall.xml`,
the isolated-rehearsal dispatch URL/result, the pinned source SHA, the candidate
origin/deployment id, the manual dispatch URL and the recall run's
`live-recall-budget-usd=1` annotation. Do not release from a label run alone, from
a failed recall run, or by widening the paid scope; fix and re-authorize instead.
