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

   Never commit or paste these values anywhere in the repository or a chat.
3. Confirm the QA account is a member of the dedicated QA workspace and that the
   workspace is opted into sales/conversation features for the candidate under
   test (`BUYEROS_SALES_WORKSPACE_IDS` / `BUYEROS_SALES_SKILLS_ENABLED` on the
   deployment, and `NEXT_PUBLIC_CONVERSATION_HOME=true`).

## Run

Dispatch the workflow against the branch (or, after merge, against `main`) with
the deployment origin, the QA workspace/project ids and the full commit SHA the
deployment was built from:

```bash
gh workflow run buyeros-conversation-qa.yml \
  --ref feat/conversation-studio \
  -f origin=https://buyer-jclj9q3y0-ynwaforevers-projects.vercel.app \
  -f workspace_id=<qa-workspace-uuid> \
  -f project_id=<qa-project-uuid> \
  -f expected_source_sha=9823f3192bbb73d37d1d4c29584b378f7ee0bd82
```

The workflow refuses: non-HTTPS origins, non-Vercel hosts, a non-bare origin,
malformed UUIDs, a short SHA, and (where `/healthz` is available) a deployment
whose reported source does not match.

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
