# Protected Workspace Release Operations

The runtime bundle workflow stages a reviewed build. A stage is not production acceptance. Paid research, contact enrichment, workers, CRM delivery, and email must remain disabled.

## Required Remote Controls

Before dispatch, read back the controls rather than relying on this file:

- `main` is protected, strict required checks contain all 15 BuyerOS CI jobs, and administrators are covered. Pull-request approvals are optional under the owner's explicit policy; neither an approving PR review nor approval of the last push is required. This PR policy does not waive actual protected runtime signoff or production promotion approval.
- `buyeros-runtime-readonly` and `buyeros-production-promote` exist. Restrict them to protected branches. The latter disallows administrator bypass. Under the explicitly approved `BUYEROS_RELEASE_REVIEW_POLICY=solo-owner-v1`, its sole required reviewer is YNWAforever (GitHub user ID `201698560`) and `prevent_self_review` is false. This records owner review, not independent review. The default `independent-v1` policy instead requires a reviewer other than the initiator and prevents self-review; an unknown policy fails closed.
- The Vercel project and team match the linked BuyerOS GitHub repository, production branch is `main`, and `autoAssignCustomDomains` is `false`.
- The reviewed production runtime has `BUYEROS_PAID_ADMISSION_ENABLED=false`, `BUYEROS_DELIVERY_ADMISSION_ENABLED=false`, and `BUYEROS_CLOUDFLARE_EXECUTION_ENABLED=false`.
- The API runtime login can select only `version_num` from `public.alembic_version` for schema metadata and `enabled` from `public.worker_runtime_control` for activation proof. This is a prerequisite to the release probe, not a reason to grant owner or migration credentials to the API. The workflows never change database grants or apply migrations.

## Protected Configuration

Enter secret values directly into the protected GitHub environments. Do not put secrets in workflow inputs, repository files, comments, logs, or artifacts.

Both protected environments need `BUYEROS_PROMOTION_METADATA_TOKEN` (a repository-scoped credential with only the read permissions needed for branch/environment/workflow metadata) and `VERCEL_TOKEN` scoped to the intended team. The pinned CLI also reads team metadata during `pull`; a token restricted to one project can pass project API reads yet fail that step with HTTP 403. Use the intended team's All Projects scope for this CLI workflow; release controls still enforce the exact BuyerOS project and team. Set `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` as environment variables. Do not copy a broadly scoped local GitHub credential into CI.

The pinned Vercel CLI checks saved credentials before loading `VERCEL_TOKEN` on a fresh runner. Release commands therefore write that token to an isolated temporary CLI auth file, select it with `--global-config`, and remove it after the command, including failures. The token never enters command arguments, and a developer's saved login is not copied or modified.

Stage, signoff, promotion, and release-readiness CI pin Vercel CLI `54.17.2`. This version supports the existing Services configuration and service-targeted rewrite while retaining the collector's stdin-based curl configuration. CI uses the actual pinned CLI validator against `vercel.json` and checks its dotenv parsing with synthetic values. Do not upgrade the CLI without checking Services build/prebuilt output, environment semantics, and protected curl transport together; newer versions may reject the stdin configuration mechanism.

Release-readiness also builds a synthetic frontend and FastAPI service outside the checkout on Linux, with an isolated CLI configuration and no inherited application credentials. It checks production build metadata, both service outputs, runtimes, routing, and the private binding. This validates the build tooling only; the protected stage still independently verifies the real candidate's service artifacts and runtime behavior.

Production environment exports use the pinned CLI's dotenv format, not JSON string escaping. The release reader preserves embedded quotes (including JSON CORS arrays), matches the pinned build reader's newline handling, and never expands variables or executes values. Invalid names, duplicate keys, and malformed records remain blocking errors. Sensitive exports may be blank; the existing protected database/probe bindings and independent runtime checks remain required.

Both environments also need `BUYEROS_RELEASE_PROBE_TOKEN` so stage, signoff, and promotion can read the exact candidate configuration without activating a provider. The promotion job uses its narrowly scoped workflow token with `deployments: write` to persist intent in the dedicated `buyeros-production-intents` ledger; the metadata credential remains read-only.

The stage environment also needs:

- `BUYEROS_G0_TARGET_JSON`, `BUYEROS_SCHEMA_CONTRACT_JSON`, and their reviewed SHA-256 environment variables `BUYEROS_G0_CONTRACT_SHA256` / `BUYEROS_SCHEMA_CONTRACT_SHA256`.
- `BUYEROS_RUNTIME_READ_SCOPE_SHA256` matching the target packet's authorization reference.
- Four distinct current test-account credentials in `BUYEROS_G0_OWNED_TOKEN`, `BUYEROS_G0_FOREIGN_TOKEN`, `BUYEROS_G0_EMPTY_TOKEN`, and `BUYEROS_G0_REVOKED_TOKEN`. Negative controls must be real independently scoped accounts, not reused credentials or expired tokens.
- `BUYEROS_RELEASE_PROBE_TOKEN`, matching the production runtime setting with the same name. It grants access only to the fixed release-binding response.
- `BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY`, a random 32-byte key encoded as 64 hex characters, shared only with the signoff environment.
- `BUYEROS_RUNTIME_DIAGNOSTIC_ENCRYPTION_KEY`, a separate random 32-byte key encoded as 64 hex characters, held only in the stage environment and the operator's private diagnostic session. It encrypts bounded subprocess failure details; it cannot authorize staging, signing, or promotion.
- `BUYEROS_ROLLBACK_DEPLOYMENT_ID` as an environment variable identifying the current production deployment with compatible frontend/API artifacts.
- `BUYEROS_SCHEMA_CHECK_DATABASE_URL`, the restricted runtime-role credential used when the Vercel export omits the database secret. The reviewed endpoint and live candidate binding must still match.

For `dual` or `neon` auth, only the promotion/signoff environment (`buyeros-production-promote`) receives `BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON`. Collect and separately accept it against the actual staged candidate, then save it before approving the waiting signing job. Stage neither reads this secret nor includes a Neon receipt in its encrypted observation packet. Signing consumes the protected secret and the existing complete gate verifies its exact source, tree, deployment, configuration, database binding, freshness, acceptance, and Neon-only rollback evidence. A workspace read is not auth acceptance.

Only the promotion/signoff environment gets `BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY`, a separate random 32-byte key encoded as 64 hex characters. Keep the observation and final-bundle keys distinct. Source-specific private contracts must be refreshed after a reviewed main commit changes; old contracts fail closed.

### Staged Neon Origin

The protected stage command sets `BUYEROS_NEON_STAGED_ORIGIN_ENABLED=1` and `BUYEROS_RUNTIME_SOURCE_SHA` on the candidate deployment. The auth boundary accepts its additional origin only with a lowercase 40-hex source SHA, `BUYEROS_NEON_ENVIRONMENT=production`, `NODE_ENV=production`, and `VERCEL_ENV=production`. The hostname must be the validated Vercel-injected `VERCEL_URL`; do not set it from a request Host or forwarded header. Only `https://<VERCEL_URL>` is added. The independently bound canonical `BUYEROS_PUBLIC_ORIGIN` remains accepted for eventual promotion. An Origin header must match the request target exactly; POST requests require it even when both origins are approved. The staging security flag is included in both the expected and observed release configuration fingerprint; a mismatch blocks acceptance.

After the candidate exists and its exact deployment identity has been verified, add only its exact HTTPS origin to the intended Neon Auth branch's trusted domains and read back that setting. Do this before candidate browser acceptance and before approving `bundle-signoff`. The application flag does not configure Neon trust, and successful staging does not prove it exists. Do not use a wildcard, a sibling deployment, or disable Vercel deployment protection. Keep canonical-origin trust in place.

For rollback browser evidence, verify that the live canonical alias still points to the recorded rollback deployment before checking login, the exact QA workspace/project, secure session cookies, reload, and logout across two tabs. Keep these browser observations separate from the immutable rollback API checks. Historical rollback success cannot replace fresh candidate acceptance or relax the 900-second receipt limit.

## Candidate And Human Signoff

1. Confirm the current-main BuyerOS CI run succeeded with all 15 required jobs. Dispatch `BuyerOS protected runtime bundle` on main using that run ID and explicitly select staging; staging defaults to off.
2. The workflow reads protected controls and production configuration, tests rollback API compatibility, builds the reviewed source, and stages it with `--prebuilt --prod --skip-domain`. It verifies the exact deployment identity, service build inventory, schema, seven API account controls, and the candidate runtime's effective settings fingerprint and disabled activation controls. The separate protected configuration endpoint also reads the actual worker-control row and passive contact-provider readiness; a pulled environment file cannot substitute for this runtime proof.
3. The `bundle-signoff` job waits at the protected environment. Configure and verify the exact candidate Neon trusted domain as described above, then follow its candidate URL using the authorized company account. Check workspace roles and project, reload the page, and verify the retry/recovery behavior without starting research, enrichment, drafts, or email.
4. For `dual` or `neon` auth, complete actual candidate browser auth acceptance and Neon-only rollback verification, and install the separately accepted candidate-bound receipt in `buyeros-production-promote` while the signing job is waiting. Do not fabricate a receipt from a READY deployment or successful API read. Environment secrets are consumed when the protected job starts, so install the receipt before manual approval. Approve only after these acceptance checks and the workspace browser checks pass, with the exact approval comment:

   `workspace-canary-pass:<full-source-sha>:<deployment-id>:roles-project-reload-retry`

   The workflow reads the actual GitHub approval history; a supplied reviewer name or an arbitrary comment is insufficient. Under `solo-owner-v1`, the approver must be the pinned owner YNWAforever and may also be the initiator. Under the default `independent-v1`, the approver must differ from the initiator. Neither policy permits automatic approval or administrator bypass. This comment is a human browser receipt, not an automated browser-test claim.
5. Receipts older than 900 seconds are rejected. If staging or human review takes longer, preserve the failed run and start a new reviewed workflow; do not change receipt timestamps or replay approvals. Workflow reruns are rejected.
6. The complete signed artifact is named `buyeros-attested-runtime`; it contains only encrypted `runtime-bundle.json`. The intermediate artifact is encrypted under a different key and cannot be promoted.

## Promotion And Readback

Dispatch `BuyerOS guarded promotion` once with the successful runtime run ID. A separate actual environment approval under the configured review policy is required: pinned owner approval for `solo-owner-v1`, or non-self approval for `independent-v1`. The promoter verifies the exact ciphertext attestation, signer workflow, main source digest, full workspace gate, fresh remote controls, current rollback identity, and both approval histories.

The promoter first creates a project/candidate/bundle-scoped GitHub deployment intent, then fsyncs `promotion_unknown` before its single no-redirect, no-retry Vercel promotion HTTP request. It does not use the retrying Vercel CLI for the mutation. Any unresolved intent blocks every fresh workflow dispatch for that project; a runner-local file and run-attempt check are additional controls. It never retries an uncertain result. `promotion_submitted_readback_required` is not proof that production serves the candidate. Preserve the artifact and read the production alias, deployment source, migration head, runtime binding, and disabled settings independently. Vercel promotion may affect automatic assignment settings; read them back and keep the release held if any protection changes. Do not issue a second promotion to reconcile an unknown result. After separately authorized read-only reconciliation establishes the outcome, an owner can record `success`, `failure`, or `inactive` on the original intent with the exact description `read-only-reconciled:<source-sha>:<deployment-id>`. Preserve that original identity and evidence; do not create a replacement key. The same candidate or bundle cannot be resubmitted automatically even after reconciliation.

Only after the exact production alias and all release controls are verified may the separately authorized Golden Resources source checks be saved. Preserve each original note, observed date, grade, rationale, limitations, and official-source links. Use the authenticated BuyerOS append-only API as the company user; read back exactly 24 records and 57 links and compare original notes unchanged. Do not create provider operations, cost reservations, research/enrichment jobs, or delivery attempts.

## Verification Boundaries

If protected staging fails, use its allowlisted diagnostic phase and failure category to locate the failing check. Raw command output, arguments, exception messages, credentials, and private contracts remain in the runner's private log and are not published. A diagnostic does not satisfy any release check. Verify whether a deployment was created before starting another staging run; never retry an uncertain deployment or promotion result.

When the separate diagnostic key is configured, a failed stage also preserves up to 64 KiB of subprocess stderr in `buyeros-private-stage-failure-encrypted`, retained for one day. Only AES-GCM ciphertext is uploaded; source and workflow-run identity are authenticated with it. Decrypt privately, verify the expected source and run, and report only the relevant nonsecret error. This distinct diagnostic format is never accepted as release evidence. Missing diagnostic keys or failed diagnostic writes preserve the original failure and do not permit progress.

Unit, disposable-database, CI, stage, human-browser, and production evidence are distinct. A green CI run, READY deployment, ciphertext artifact, or HTTP 200 cannot replace the missing stage or production acceptance checks. Keep historical failures, source-audit backups, and untracked fixture evidence; do not alter `.gitignore` to hide them.
