# BuyerOS Protected Workspace Release and Runtime Bundle

## Status

Approved by the user on 2026-10-15 together with the implementation plan. Production promotion and the source-record write remain conditional on the protected release gates and exact production readback.

## Goal

Enable a reviewed workspace-only BuyerOS release to stage an exact main-branch build, collect fresh runtime evidence for that exact deployment and database, encrypt and attest a complete release bundle, pass a non-self-approved promotion gate, and only then expose the app and save the 24 existing Golden Resources source checks. Research providers, contact enrichment, workers, delivery, CRM, and email remain disabled throughout.

## Current evidence and gap

PR #21 commit `a9b7f38a0193fce4be6f467e84473f037086dd2c` passed all 12 CI jobs. Production Neon reports migration `0054_buyer_source_checks`; the new table exists with zero records. The Vercel production alias still serves an older deployment. `buyeros-runtime-acceptance.yml` currently collects bounded API reads and schema readiness and emits a redacted summary with `promotable: false`; it does not create the encrypted `buyeros-attested-runtime` artifact expected by `buyeros-promote.yml`. Current remote controls also show main unprotected, no `buyeros-production-promote` environment, and Vercel `autoAssignCustomDomains` enabled. Only the repository owner is currently listed as collaborator, so a distinct environment reviewer must be available before any production alias change.

## Approaches

1. **Same-run protected runtime probes (recommended).** Stage an exact, green main commit without assigning aliases. A protected job probes the staged deployment and its runtime database binding, runs the owned/empty/revoked/foreign API controls, records a browser canary, and verifies rollback compatibility. It joins those observations with the exact CI and build records, encrypts the complete bundle, and attests only the ciphertext. The promoter verifies the signature and re-reads all remote controls before one alias promotion. This gives the strongest source-to-runtime chain and avoids accepting hand-entered booleans.
2. **Protected operator-supplied receipts.** A reviewer enters full source-bound runtime, browser, database-binding, and rollback receipts into protected environment secrets; a protected workflow checks freshness and signatures, encrypts the bundle, and attests it. This is faster to build, but depends on correct manual evidence preparation for every candidate and can become stale.
3. **Keep release blocked.** Preserve the current partial observer and do not produce a promotion bundle until the missing runtime evidence is available. This makes no change to release capability.

The implementation should use approach 1. Any remaining genuinely human-only browser approval must be a separate non-self-review step; it cannot be synthesized by the builder.

## Design

### Staging and candidate identity

A protected staging workflow runs only from `main` and accepts a successful CI run ID. It independently verifies the run is for the current main SHA, the required 12 jobs all passed, and the repository/project/team match. It builds with production environment values and stages the exact built deployment with domain assignment skipped. It records the deployment ID and uses that immutable candidate for every later probe.

The Vercel project must report the expected BuyerOS repository, team, production branch `main`, and `autoAssignCustomDomains: false`. The workflow must stop if these remote settings cannot be read or differ. Main must be protected with strict required checks. The promotion environment must restrict deployments to protected branches and require at least one reviewer who is not the initiator.

### Runtime database binding

Add a narrowly scoped release-binding endpoint to the existing Python API. It accepts only a protected probe credential and returns a fixed response containing the runtime deployment/source identity, schema head, and a SHA-256 digest of normalized database target fields (database name plus endpoint host/port). It never returns the connection string, credentials, user/workspace rows, or arbitrary configuration. Responses must be `Cache-Control: no-store`; invalid credentials return the normal sanitized error envelope. Tests verify constant-time credential comparison, exact response keys, no DSN disclosure, and mismatch refusal.

The protected workflow fetches the Vercel production database connection only into an ephemeral file, calculates the same target digest without logging the DSN, and compares it with both the staged API response and the independent read-only schema receipt. It removes the temporary file on success or failure. Only digests and pass/fail codes may enter the encrypted bundle.

### Implementation review refinements

Independent review found that SQLAlchemy preserves percent-encoded database names in its effective driver arguments. Database binding therefore hashes the engine's exact database field and shares endpoint normalization with schema inspection; it never decodes two distinct actual database names into one digest.

A second fixed, protected `/v1/internal/release-configuration` endpoint proves the candidate's effective release-settings fingerprint, actual worker-control state, and passive contact-provider readiness. Stage, signing, and promotion require this proof; a pulled environment snapshot cannot assert runtime activation. The runtime login needs only the explicit read-only metadata columns documented in the operational runbook; no production grant or migration is applied by the workflow.

The installed Vercel CLI retries promotion POSTs internally, so the mutating promotion uses one direct HTTPS request with redirects/retries disabled. Before that request, a project-scoped GitHub deployment intent persists candidate, source, bundle, and run identities outside the runner. Any unresolved intent blocks new dispatches until separately authorized read-only reconciliation is recorded against the original intent. No alternate key or fresh runner bypasses the hold.

### Complete workspace evidence

The bundle builder runs `evaluate_release(..., "workspace")` and emits nothing unless the full gate is `ready`. It composes, without inventing fields:

- exact source/tree/configuration/database-target tuple and staged deployment ID;
- fresh CI run ID, source SHA, complete required job inventory, and verified frontend/API service artifacts;
- current typed schema-readiness receipt for the bound target;
- current bounded API receipt from the seven owned/foreign/empty/revoked reads;
- protected browser-canary receipt containing observed workspace/project/roles and reload/retry results, with a separate human sign-off identity;
- rollback receipt bound to exact frontend and API rollback deployments and compatibility tests;
- explicit activation settings with providers, worker, and delivery set to `disabled`.

The builder rejects partial `runtime-observations.v1`, missing fields, duplicate JSON keys, unknown receipt names, stale/future receipts, wrong source/deployment/DB target, failed or skipped tests, missing rollback artifacts, and any non-workspace gate. It is read-only and has no provider, email, alias, migration, or buyer-write capability.

### Confidentiality and attestation

The bundle is AES-256-GCM encrypted with a 256-bit key held only in the protected GitHub environment. The public repository artifact contains the encrypted envelope only; plaintext manifests, receipts, browser evidence, DB targets, credentials, and company identities remain in the ephemeral protected runner or protected secrets. Encryption includes the source SHA as authenticated metadata and rejects tampering or a wrong key.

A protected workflow attests the exact ciphertext with GitHub artifact attestations. Promotion verifies that exact artifact against the designated main-only runtime workflow, decrypts only after signature verification, re-runs the release evaluator, and re-reads GitHub branch/environment state plus Vercel team/project/repository/configuration/deployment state. It makes one promotion call only after every check passes. Unknown outcomes remain `promotion_unknown`; the workflow never retries an uncertain alias operation.

### Golden Resources source records

After production promotion and readback confirm the exact deployment, source, migration head, and disabled paid/delivery controls, use the BuyerOS authenticated API/UI as `willylai@fimmick.com` to create one independent append-only source-check record per existing Golden Resources buyer. Each record comes only from that buyer’s unchanged existing note and preserves its observed date, A/B/C evidence grade, rationale, limitations, and official-source links. Read each record back and confirm exactly 24 records and 57 links; compare each buyer’s original note before/after and require identical values. Do not create research runs, enrichment jobs, drafts, cost reservations, or delivery attempts.

## Verification and stop conditions

- Unit tests prove valid workspace receipts compose and encrypt, and that partial summaries, wrong keys, ciphertext tampering, stale/mismatched receipts, non-workspace gates, paid activation, and missing canary/rollback never produce a bundle.
- Workflow tests prove bundle creation and attestation are main-only, environment-protected, default-off, encrypted-only artifact publication, and use the exact required artifact name.
- Full PR CI must pass on the final source SHA.
- A staged candidate is not production acceptance. Stop before alias promotion if any remote control, runtime probe, second reviewer, decryption, release evaluation, or readback is missing.
- After promotion, verify the production alias resolves to the exact staged deployment before writing the 24 source checks.
- After saving, verify every record by readback and confirm paid research and email remain disabled, contact enrichment remains unconfigured/disabled, and budgets stay zero/frozen.
- Keep the existing `%TEMP%` source-audit backup; do not modify `.gitignore`.

## Explicit non-goals

No paid research, contact enrichment, email/CRM delivery, worker activation, identity linking, schema change beyond the already applied 0054, or source-note mutation. No publication of plaintext private evidence. No bypass of branch protection, required reviewer, or Vercel deployment controls.