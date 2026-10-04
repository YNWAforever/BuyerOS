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


## Local preflight preparation (no external execution)

The separate module scripts/neon-real-preflight.mjs and tests/neon-real-preflight.test.mjs validate this proposal's exact scope. The null-valued neon-auth-n00-real-target.template.json is deliberately unusable until new resources exist and authenticated provider readbacks have been inspected. It contains no approval record, credentials or guessed issuer/audience/JWKS. The preflight does not verify the authenticity of supplied metadata; synthetic unit metadata is never provider readback evidence.

Run the inert config check with:

~~~text
node scripts/neon-real-preflight.mjs check docs/buyeros/runbooks/neon-auth-n00-real-target.template.json
~~~

Expected now: exit1 / N00_REAL_TARGET_REQUIRED. A populated valid config check still reports external_authorized:false, external_started:false, built_runtime_verified:false and N00_complete:false. It performs no HTTP, resource/account creation, linking, builds or deletion.

After specific human authorization, initialize one RealRunJournal in a newly owned buyeros-n00-real-* directory under the OS temporary directory or test-results/neon-real-preflight, with the actual authorization reference/time. A string in this journal is provenance, not a grant of permission. Initialize before the first counted setup/readback check. Each outgoing request needs its own reserveRequest call **before** submission; setup, negative/error responses, each redirect hop, retry and reconciliation all consume budget. The owned fictional SDK runner now uses a synthetic journal and a loopback-only counted proxy; it cannot be repointed to Neon. The shared target validator and request-lazy typed server-only runtime overlay are prepared separately. Actual real SDK/browser/CLI interception, real-harness UI/diagnostic, new built runtime configuration proof and external cleanup executor remain unimplemented/unverified; do not begin real execution until every traffic path is counted. These prepared components do not assert real traffic is already bounded.

The journal uses exclusive creation, an exclusive writer lock, fsync and atomic replacement. Never reset/recreate it to regain budget. Up to180 setup/auth checks, with20 reserved for cleanup/reconciliation, total200; pending/unknown/resolved operations retain their reservations across process restart. The same operation ID cannot be blindly resubmitted; use a separately counted readback with a new reconciliation ID. There are two build reservations, each bounded to20minutes and remaining resource TTL. A crash during a writer lock fails closed as BUSY; inspect exact process/ownership and preserve the journal before manual lock recovery. It is not a tamper-proof ledger against a malicious local administrator.

Bind only the observed new-empty project/branch/auth IDs and configured auth trust to the journal. Two-hour TTL derives from its recorded resource creation time. The current plan rejects an unexpected JWKS origin: inspect and review any genuine different-origin provider contract before changing that guard. It never substitutes issuer/audience from a URL or token. Runtime environment construction takes an explicitly supplied fresh random cookie secret (use32cryptographic random bytes encoded base64url), removes inherited DB/Auth0/provider variables, and supplies only the observed auth values. Build environment construction drops all runtime auth values. **The separate real-only overlay now compiles and its configuration/constructor kernel executes on actual portable/workerd and Nitro/Vercel outputs with fictional metadata.** Six kernel cases per output pass, including runtime-only secret/trust and node:crypto; this does not verify SDK session/token/handler/middleware, real Neon or human Google. See ../evidence/audit-fixes-20261003/N00_RUNTIME_BUILT/RESULTS.md. A later separately compiled real-only UI/diagnostic and fully counted SDK/browser/CLI harness must exercise them before that gate can pass.

cleanupTargets returns IDs only after fresh matching readback (at most5minutes old), includes at most one bound new-directory test identity, and stays available after TTL. It does not delete anything. The executor must confirm ownership and absent/unknown outcomes using counted provider readbacks, implement deletion in the new-target scope only, and produce cleanup evidence. No real journal/target/account/secret has been created by these local tests.


## 2026-10-05 N00 built session/token checkpoint (c756596)

Reviewed source c756596406f41884f61a3b64c8549f569e34cfa4;27files518insertions/1deletion. Official pinned SDK login/session/token/handler/managed callback/logout and independent owned EdDSA FastAPI execute on both actual built outputs with fictional target/transport:each5pass0fail0skip0globalerror.144serialNode/8crypto pass;types/lint/contracts0;fourcleanbuildcommands0. Receipt binds server session subject/fingerprint;bearer stays in memory. Both30fixtureAuthHTTP/0pending0unknown;owned roots/journals/children removed. Body timeout,two0-test startups,parallel40ms regression and initial type/lint failures retained;original status/body/deadline assertions unchanged. No DB/migration/external action. True Neon/Google/full SDK-browser-CLI accounting/external cleanup/independent review and original strict302 gate remain open;N00/NA01/Task2 OPEN. Evidence: docs/buyeros/evidence/audit-fixes-20261003/N00_RUNTIME_FLOW/RESULTS.md. Reverse applicability0only;revert source plus following metadata;no DB/resource undo. NexteligibleN00accounting/cleanup preparation;fresh real-target/account approval pending;Auth0 retained/deployednull.

The real-only UI is prepared and exercised only when composed with a separate fictional transport overlay/owned loopback verifier. Real targets remain unavailable until SDK/browser/CLI accounting and external cleanup are implemented/reviewed and the exact isolated target/Google scope authorized. No real IDs/identity/cookie secret/readback/approval record has been filled.

## 2026-10-05 N00 local execution-boundary checkpoint (b8a1084)

Reviewed source b8a10848b62090ff19544918961e54df3ebfa921;10files277insertions/0deletions. Owned loopback gateway durably counts SDK/browser/fixed Node fixture CLI/control HTTP; cross-channel write holds/manual redirects/limits/TTL; exact-resource cleanup model uses fresh matching readback and confirmed absence. Real provider/CLI/human Google containment and external cleanup API adapters remain unimplemented/unverified. Final related165pass0fail0skip(new21included),Chromium3pass0skip0globalerror/3ownedcleanup receipts,crypto8pass1existingwarning;types/lint/contracts0;0037singlehead/no migrations/DBconnections/skips. Attempted full30-fileNode234tests229pass5fail0skip: two missing mainVerceloutput gates,admin/mvp Docker30stimeouts and parent failure; unchanged tests/no weakened assertions. Full suite RED disclosed. Prior c756596 actual builtUI historicalcarried,not rerun.1401priorN00payloads+31inputs/84operations(70+14)/guards/24other tasks/97other cases/all98historicfields/legacyT registry/unrelated worktrees preserved. Reverse applicability0only;revert following metadata then source;no DB/resource undo. Evidence: docs/buyeros/evidence/audit-fixes-20261003/N00_EXECUTION_BOUNDARY/RESULTS.md. N00/NA01/Task2 OPEN;original302/realNeon/humanGoogle/fresh approval/independent review gates open. Auth0 retained/deployednull;no agents/external mutation/push/deploy. Nexteligible N00 transport coverage/provider cleanup adapters.
