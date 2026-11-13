# Authenticated conversation QA (real account, dedicated workspace)

This is the only path that proves the conversation studio end to end with a real
account. Ordinary CI is fixture-based and cannot reach a real Neon account.

## One-time setup (owner)

1. Create the protected environment `buyeros-conversation-qa` in
   **Settings → Environments**. Add yourself as a required reviewer (recommended)
   so no run starts without an explicit approval.
2. Add these **environment** secrets (not repository secrets):

   | Secret | Purpose |
   | --- | --- |
   | `BUYEROS_NEON_REAL_EMAIL` | Dedicated QA account email |
   | `BUYEROS_NEON_REAL_PASSWORD` | Dedicated QA account password |
   | `BUYEROS_QA_PROTECTION_BYPASS` | Optional: only if the candidate is a protected preview |

   Never commit or paste these values anywhere in the repository or a chat.
3. Confirm the QA account is a member of the dedicated QA workspace and that the
   workspace is opted into sales/conversation features for the candidate under
   test (`BUYEROS_SALES_WORKSPACE_IDS` / `BUYEROS_SALES_SKILLS_ENABLED` on the
   deployment, and `NEXT_PUBLIC_CONVERSATION_HOME=true`).

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

The workflow refuses non-HTTPS origins, non-Vercel hosts, a non-bare origin,
malformed UUIDs, a short SHA and a malformed bypass token. Before the login job,
management API readback must prove a READY immutable deployment belonging to the
protected project/team, with the expected repository binding and full commit SHA.
Redirects are refused, and the management token is never sent to the candidate.
These are deployment-metadata checks; protected runtime/database binding,
attestation and actual candidate-bound acceptance remain separate release gates.

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
- conversation-first home (composer, thread list, project identity)
- first turn creates exactly one discussion and one user message
- a second turn keeps both messages ordered with no duplicate
- reload restores the same thread and messages (durable conversation)
- unsent composer text survives reload (protection of unsent messages)
- an unconfigured model/action is shown honestly and never faked; any proposal
  card is **not** approved (no provider spend, no paid admission)
- no uncaught console errors during the journey
- EN and zh-HK rendering of the same surface

Screenshots and JUnit are uploaded as the `buyeros-conversation-qa` artifact.

## What this does not prove

- Real provider dispatch (model/Xverum) remains a separate authorised acceptance
  with paid admission enabled; this journey explicitly does not approve it.
- Worker/queue execution, delivery and exports keep their own release gates.

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

Then add the `qa:real` label to the PR. The workflow uses the PR head SHA as the
expected source and the environment secrets for the account, and uploads
`buyeros-conversation-qa` (screenshots + JUnit).
