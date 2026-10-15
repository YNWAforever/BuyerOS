# Protected Workspace Release Operations

The runtime bundle workflow stages a reviewed build. A stage is not production acceptance. Paid research, contact enrichment, workers, CRM delivery, and email must remain disabled.

## Required Remote Controls

Before dispatch, read back the controls rather than relying on this file:

- `main` is protected, strict required checks contain all 12 BuyerOS CI jobs, administrators are covered, and stale pull-request approvals are dismissed with at least one approving reviewer.
- `buyeros-runtime-readonly` and `buyeros-production-promote` exist. Restrict them to protected branches. The latter requires a reviewer other than the workflow initiator and disallows administrator bypass.
- The Vercel project and team match the linked BuyerOS GitHub repository, production branch is `main`, and `autoAssignCustomDomains` is `false`.
- The reviewed production runtime has `BUYEROS_PAID_ADMISSION_ENABLED=false`, `BUYEROS_DELIVERY_ADMISSION_ENABLED=false`, and `BUYEROS_CLOUDFLARE_EXECUTION_ENABLED=false`.
- The API runtime login can select only `version_num` from `public.alembic_version` for schema metadata and `enabled` from `public.worker_runtime_control` for activation proof. This is a prerequisite to the release probe, not a reason to grant owner or migration credentials to the API. The workflows never change database grants or apply migrations.

## Protected Configuration

Enter secret values directly into the protected GitHub environments. Do not put secrets in workflow inputs, repository files, comments, logs, or artifacts.

Both protected environments need `BUYEROS_PROMOTION_METADATA_TOKEN` (a repository-scoped credential with only the read permissions needed for branch/environment/workflow metadata) and `VERCEL_TOKEN` scoped to the intended team/project. Set `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` as environment variables. Do not copy a broadly scoped local GitHub credential into CI.

Both environments also need `BUYEROS_RELEASE_PROBE_TOKEN` so stage, signoff, and promotion can read the exact candidate configuration without activating a provider. The promotion job uses its narrowly scoped workflow token with `deployments: write` to persist intent in the dedicated `buyeros-production-intents` ledger; the metadata credential remains read-only.

The stage environment also needs:

- `BUYEROS_G0_TARGET_JSON`, `BUYEROS_SCHEMA_CONTRACT_JSON`, and their reviewed SHA-256 environment variables `BUYEROS_G0_CONTRACT_SHA256` / `BUYEROS_SCHEMA_CONTRACT_SHA256`.
- `BUYEROS_RUNTIME_READ_SCOPE_SHA256` matching the target packet's authorization reference.
- Four distinct current test-account credentials in `BUYEROS_G0_OWNED_TOKEN`, `BUYEROS_G0_FOREIGN_TOKEN`, `BUYEROS_G0_EMPTY_TOKEN`, and `BUYEROS_G0_REVOKED_TOKEN`. Negative controls must be real independently scoped accounts, not reused credentials or expired tokens.
- `BUYEROS_RELEASE_PROBE_TOKEN`, matching the production runtime setting with the same name. It grants access only to the fixed release-binding response.
- `BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY`, a random 32-byte key encoded as 64 hex characters, shared only with the signoff environment.
- `BUYEROS_ROLLBACK_DEPLOYMENT_ID` as an environment variable identifying the current production deployment with compatible frontend/API artifacts.
- If the candidate's auth mode is `dual` or `neon`, a separately accepted `BUYEROS_NEON_ACCEPTANCE_RECEIPT_JSON` bound to that candidate. The workflow does not infer auth acceptance from a successful workspace read.

Only the promotion/signoff environment gets `BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY`, a separate random 32-byte key encoded as 64 hex characters. Keep the observation and final-bundle keys distinct. Source-specific private contracts must be refreshed after a reviewed main commit changes; old contracts fail closed.

## Candidate And Human Signoff

1. Confirm the current-main BuyerOS CI run succeeded with all 12 required jobs. Dispatch `BuyerOS protected runtime bundle` on main using that run ID and explicitly select staging; staging defaults to off.
2. The workflow reads protected controls and production configuration, tests rollback API compatibility, builds the reviewed source, and stages it with `--prebuilt --prod --skip-domain`. It verifies the exact deployment identity, service build inventory, schema, seven API account controls, and the candidate runtime's effective settings fingerprint and disabled activation controls. The separate protected configuration endpoint also reads the actual worker-control row and passive contact-provider readiness; a pulled environment file cannot substitute for this runtime proof.
3. The `bundle-signoff` job waits at the protected environment. Follow its candidate URL using the authorized company account. Check workspace roles and project, reload the page, and verify the retry/recovery behavior without starting research, enrichment, drafts, or email.
4. Approve only after those checks pass, with the exact approval comment:

   `workspace-canary-pass:<full-source-sha>:<deployment-id>:roles-project-reload-retry`

   The workflow reads the actual GitHub approval history; a supplied reviewer name or an arbitrary comment is insufficient. The approver must differ from the initiator. This comment is a human browser receipt, not an automated browser-test claim.
5. Receipts older than 900 seconds are rejected. If staging or human review takes longer, preserve the failed run and start a new reviewed workflow; do not change receipt timestamps or replay approvals. Workflow reruns are rejected.
6. The complete signed artifact is named `buyeros-attested-runtime`; it contains only encrypted `runtime-bundle.json`. The intermediate artifact is encrypted under a different key and cannot be promoted.

## Promotion And Readback

Dispatch `BuyerOS guarded promotion` once with the successful runtime run ID. A separate non-self environment approval is required. The promoter verifies the exact ciphertext attestation, signer workflow, main source digest, full workspace gate, fresh remote controls, current rollback identity, and both approval histories.

The promoter first creates a project/candidate/bundle-scoped GitHub deployment intent, then fsyncs `promotion_unknown` before its single no-redirect, no-retry Vercel promotion HTTP request. It does not use the retrying Vercel CLI for the mutation. Any unresolved intent blocks every fresh workflow dispatch for that project; a runner-local file and run-attempt check are additional controls. It never retries an uncertain result. `promotion_submitted_readback_required` is not proof that production serves the candidate. Preserve the artifact and read the production alias, deployment source, migration head, runtime binding, and disabled settings independently. Vercel promotion may affect automatic assignment settings; read them back and keep the release held if any protection changes. Do not issue a second promotion to reconcile an unknown result. After separately authorized read-only reconciliation establishes the outcome, an owner can record `success`, `failure`, or `inactive` on the original intent with the exact description `read-only-reconciled:<source-sha>:<deployment-id>`. Preserve that original identity and evidence; do not create a replacement key. The same candidate or bundle cannot be resubmitted automatically even after reconciliation.

Only after the exact production alias and all release controls are verified may the separately authorized Golden Resources source checks be saved. Preserve each original note, observed date, grade, rationale, limitations, and official-source links. Use the authenticated BuyerOS append-only API as the company user; read back exactly 24 records and 57 links and compare original notes unchanged. Do not create provider operations, cost reservations, research/enrichment jobs, or delivery attempts.

## Verification Boundaries

Unit, disposable-database, CI, stage, human-browser, and production evidence are distinct. A green CI run, READY deployment, ciphertext artifact, or HTTP 200 cannot replace the missing stage or production acceptance checks. Keep historical failures, source-audit backups, and untracked fixture evidence; do not alter `.gitignore` to hide them.
