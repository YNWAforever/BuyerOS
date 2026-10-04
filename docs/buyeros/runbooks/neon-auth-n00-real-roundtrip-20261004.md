# N00 fresh isolated real Auth roundtrip — proposal requiring approval

Status: NOT AUTHORIZED / NOT STARTED. Source2fd84ef49d289ea313a5abb21ec6e30bc2659a9d. Fixture-only work completed; full five-case suites retain synthetic302 failure. This proposal does not treat fixtures as live evidence.

## Verified owner and proposed target

Read-only Neon describe_project for user-supplied nameless-bar-15324691 confirms BuyerOS, organization org-soft-sunset-25251479, aws-ap-southeast-1, free_v3. CLI4.13.0 projects list with that explicit org succeeded. Proposed name buyeros-neon-auth-n00-20261004 is absent. Existing BuyerOS and BuyerOS-CF-preview-20261001 are outside mutation scope. Do not clone any existing project/branch/database or reuse cleared/expired approvals. Only relevant project metadata is retained in N00_CALLBACK/REAL_TARGET_READ_ONLY.json.

Create one **new empty** Neon project buyeros-neon-auth-n00-20261004 in org-soft-sunset-25251479 / aws-ap-southeast-1, with its own default empty branch and minimum free-tier compute. Project/branch/auth IDs are NULL until actual creation/readback. Provision Managed Better Auth only there. No subscription upgrade or billed resources; total additional spend US$0, stop if free-only cannot be established or quota is exhausted. Before creation read back plan/quota/region support and minimum compute/suspend settings; unsupported region or required charges block this proposal instead of silently choosing another.

## One bounded execution scope

- Up to200 **actual auth HTTP checks total**, counting setup/readback/negative/error/retry requests; no automatic retries or repeated build loop. Reserve cleanup requests; stop new checks before exhausting budget.
- Up to two clean local Linux builds, each20minute maximum (existing local-only builder keeps tighter300s bound unless separately reviewed). Actual portable/workerd and Nitro/Vercel output, not dev-server proof.
- Two-hour TTL from first new resource creation: delete only the new account/Auth integration/project and owned local runtime data, retain sanitized evidence. Record IDs as soon as returned; unknown outcomes reconcile by exact project name/operation ID before retry. If auth or runtime is blocked, clean up within the TTL.
- One isolated **test Neon identity** via development Google OAuth using human-operated laichiwillyjp@gmail.com sign-in. No password handling or login to another person's account. This may create one account in the new Auth directory only; requires explicit approval. Read back enabled Google method/shared development credentials; do not create/update a production OAuth app or use its credentials. No signup/verification/welcome email/SMTP, no email/password registration, no BuyerOS user/membership/mapping/role writes, no automatic linking by email.
- Allow only http://localhost:44890 in the new Auth trusted-domain/local-development settings, and the provider redirect URI returned by that new integration. No wildcard production/Vercel domains. Browser test traffic restricted to the approved new Auth host, Google login/consent hosts needed for the human step, and localhost. No outreach/provider activation.
- No Vercel project/deployment, production environment mutation, Auth0 changes, Cloudflare activation, BuyerOS business DB DSN, RLS fixture bypass, database migration or paid provider call.

## Required readback and separate real harness

Before actual sign-in, inspect the new Auth config for no email/SMTP hooks and exact configured methods. Stop if a no-email Google development flow cannot be established. Configure a separate real-only harness from **observed explicit** Auth base URL, issuer, audience, JWKS URL and allowed EdDSA/Ed25519 algorithm/key types. The current fictional SDK overlay/diagnostic remains immutable evidence and cannot be relabeled real. Do not place a new Neon DSN in existing destructive pytest fixtures. Do not point production Auth0 RSA adapter at a Neon URL.

| Value | Source | Allowed use |
|---|---|---|
| project/branch/auth IDs | New resource API readback | exact owned-target checks and cleanup |
| NEON_AUTH_BASE_URL | New Auth config readback | approved server runtime only; exact HTTPS host/path |
| NEON_AUTH_COOKIE_SECRET | fresh random runtime-only secret | server signing, never build/log/browser storage |
| issuer / audience / JWKS | observed new integration/token/JWKS, reviewed explicitly | separate local FastAPI diagnostic allowlist; no auto trust inference |
| Google provider method | new integration readback | human-operated test only |
| actor subject | approved new Auth identity/JWT | canonical identity unchanged; hash in public evidence where appropriate |

Prepare/review the real-only environment allowlist and hostname/cleanup/200-request guards before using actual credentials. Service bindings resolve only in functions, not builds or routing middleware. The SDK callback middleware runs inside the built server runtime and may read its server-only cookie configuration; the cookie secret must never be baked into build/client output. Verify that runtime configuration on both outputs before real use. No production variable values are inferred, copied or printed.

## Acceptance evidence and stop conditions

Record source SHA, exact target/config identifiers (without secrets), UTC times, real vs fixture case counts, raw failures, built input/output hashes, actual callback302 on Neon -> app307 verifier exchange -> clean same-origin return, cookie security, getSession/server hard reload, in-memory token -> FastAPI signature/issuer/audience/key validation, logout/reload anonymous. Preserve challenge/replay/negative checks and existing synthetic failure separately; do not suppress a required skip or convert failure to pass. Platform/Vercel ingress and workspace/RLS/staff flow remain unverified because no deployment or canonical DB grant occurs.

Do not promise OAuth/state/CSRF/rotation/refresh/platform acceptance from the current fixture. Real protocol differences get a new failing case and smallest reversible local fix. Do not merge auth cutover. Rollback is removal of only the newly owned resources and reverting real-harness changes; existing Auth0, canonical IDs, roles, audit/job actors and DB data remain.

## Approval required

The latest execution request authorizes local repairs, but real external configuration/accounts require specific authorization. Earlier hosted preview resources were cleaned and their time/build limits expired. Approve this fresh empty-project/Auth setup, one human-operated Google test identity, the200-check/two-hour/US$0 limits and cleanup before any mutation. No owner approval record is prefilled or fabricated.
