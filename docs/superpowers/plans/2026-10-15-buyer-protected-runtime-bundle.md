# BuyerOS Protected Runtime Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete a source-bound, encrypted, attested workspace release path for BuyerOS, then deploy the reviewed candidate and save/read back the 24 approved Golden Resources source-check records.

**Architecture:** A read-only API probe exposes only the running source, immutable deployment ID, schema head, and a digest of normalized database target fields. A protected workflow stages the exact CI-green main build without alias assignment and stores private observations only as an encrypted intermediate artifact. A non-self GitHub environment reviewer then checks the candidate in a browser and approves with a source/deployment-bound canary comment; the workflow verifies that identity from GitHub's workflow-run approval history, composes and encrypts the complete bundle, and attests ciphertext only. A separate protected promoter rechecks remote controls before one alias change; only exact production readback permits the 24 source-check writes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest, GitHub Actions, GitHub artifact attestations, GitHub Actions REST API, Vercel CLI, AES-256-GCM.

**Spec:** `docs/superpowers/specs/2026-10-15-buyer-protected-runtime-bundle-design.md`

## Global Constraints

- Work only in the PR #21 checkout on `codex/buyer-source-check-records-20261015`; preserve untracked `artifacts/c61/fixture-runs/`, existing source-check plan/spec, and the external fixture backup; never edit `.gitignore`.
- Require the exact current `main` SHA and all 12 required CI jobs green before staging; deploy the exact staged production-target deployment with domain assignment skipped.
- The release-binding endpoint is read-only, requires a protected probe credential checked with constant-time comparison, returns fixed identity/schema/digest fields, and uses `Cache-Control: no-store`.
- Bind runtime source, deployment ID, schema head, and database-name/endpoint-host/port digest to the independent schema observation and manifest; never emit a DSN, username, password, arbitrary settings, or tenant rows.
- Compose only a complete `workspace` gate. Reject partial observation summaries, duplicate or unknown JSON keys, stale/future or mismatched receipts, missing canary/rollback/binding evidence, and any paid or delivery activation.
- Keep plaintext observations on ephemeral runners. Intermediate and final workflow artifacts contain only AES-256-GCM ciphertext. The final 256-bit bundle key is available only in the protected `buyeros-production-promote` environment.
- Verify the actual environment approver using `GET /repos/YNWAforever/BuyerOS/actions/runs/{run_id}/approvals`; require an approved `buyeros-production-promote` environment review by a user whose ID differs from the workflow initiator. Do not accept a manually supplied reviewer name.
- Require strict main protection, protected-branch environment policy, a non-self reviewer, and Vercel project/team/repository identity with `autoAssignCustomDomains=false`. Missing controls block release; do not bypass them.
- The reviewer must inspect the staged candidate using the company account and approve with the exact comment `workspace-canary-pass:<source_sha>:<deployment_id>:roles-project-reload-retry`. Bind the verified reviewer identity and comment digest into the encrypted bundle.
- Owner update (2026-10-15): pull-request approval is optional; the 12 CI checks and protected environment's independent approval remain required.
- Promotion makes at most one alias call. An uncertain outcome remains `promotion_unknown`; reconcile by read-only production alias lookup and never retry automatically.
- Keep research providers, contact enrichment, worker, delivery, CRM, and email disabled; do not create research runs, cost reservations, drafts that queue provider work, or delivery attempts.
- Migration `0054_buyer_source_checks` is already applied with zero records. Apply no further production migration; create the 24 append-only source-check records only after exact deployment and settings readback.

## Review Focus

- URL normalization with percent-encoded database names, omitted/default ports, mixed-case hostnames, and IPv6 never changes the intended database-target digest — Task 1 `test_database_target_digest_uses_only_normalized_name_host_port`.
- Missing, stale, duplicated, or future runtime evidence cannot produce an encrypted bundle — Tasks 2–3 `test_workspace_gate_requires_bound_candidate_database_receipt`, `test_runtime_bundle_rejects_duplicate_and_stale_inputs`.
- A valid-looking response from the wrong deployment or database target is rejected — Tasks 1–2 `test_release_binding_refuses_incomplete_runtime_identity`, `test_workspace_gate_rejects_mismatched_binding`.
- Workflow logs and artifacts never expose raw DSNs, private receipts, tokens, or plaintext bundles on success or failure — Tasks 3–4 `test_bundle_cli_publishes_ciphertext_only`, `test_runtime_bundle_workflow_keeps_private_payload_out_of_logs_and_artifacts`.
- A forged reviewer name/comment, missing approval record, missing remote control, or timeout prevents bundle publication or a second alias attempt — Tasks 4–5 `test_runtime_bundle_requires_verified_nonself_approval_and_bound_canary_comment`, `test_promotion_blocks_missing_reviewer_and_unknown_outcome_is_not_retried`.

---

### Task 1: Read-only runtime database-binding endpoint

**Files:**
- Create: `services/api/buyeros_api/services/release_binding.py`
- Create: `services/api/buyeros_api/api/routes/release_binding.py`
- Modify: `services/api/buyeros_api/settings.py`
- Modify: `services/api/buyeros_api/api/app.py`
- Test: `services/api/tests/test_release_binding.py`

**Interfaces:**
- Produces `database_target_sha256(database_url: str) -> str`, hashing canonical JSON containing only decoded database name, normalized endpoint host, and effective port (5432 when omitted).
- Produces `GET /v1/internal/release-binding`, authorized by `Authorization: Bearer <BUYEROS_RELEASE_PROBE_TOKEN>`. Its fixed JSON keys are `schema`, `source_sha`, `deployment_id`, `schema_head`, and `db_target_sha256`; `schema` is `buyeros.runtime-db-binding.v1`.
- Runtime identity comes from `BUYEROS_RUNTIME_SOURCE_SHA` and `BUYEROS_RUNTIME_DEPLOYMENT_ID`; absent or malformed identity fails closed. The handler reads the current single schema head without migration or writes.

- [x] **Step 1: Write failing route/helper tests** for exact target hashing, incomplete identity, wrong/missing token before database access, constant-time credential comparison, exact response keys, no-store cache policy, and absence of DSN/credentials in response or errors.
- [x] **Step 2: Run the focused tests and confirm they fail** because the helper, route, and settings are absent.
- [x] **Step 3: Implement the minimal helper, settings, and route** and register the router in `api/app.py`; use the existing request/error conventions.
- [x] **Step 4: Run `python -m pytest services/api/tests/test_release_binding.py -q` and confirm all focused tests pass.**
- [x] **Step 5: Commit** the endpoint and tests as `feat: expose protected runtime database binding`.

### Task 2: Require deployment/database binding in the workspace release gate

**Files:**
- Modify: `scripts/check-release-readiness.py`
- Modify: `tests/test_release_readiness.py`

**Interfaces:**
- Add `deployment_binding` to the required `workspace` receipt set.
- Its `data` has the exact fields `schema`, `verified`, `source_sha`, `deployment_id`, `db_target_sha256`, `schema_head`, and `api_origin_sha256`; schema is `buyeros.deployment-db-binding.v1`.
- Accept only when verification is true and source, candidate deployment, database digest, and schema head match the manifest and compatible schema receipt. `api_origin_sha256` must be a lowercase SHA-256 digest.

- [x] **Step 1: Add failing tests** for a missing binding, false verification, wrong source/deployment/database digest/schema head, and malformed origin digest.
- [x] **Step 2: Run `python -m pytest tests/test_release_readiness.py -q` and confirm the new tests fail** on missing/unknown binding rather than an import or fixture error.
- [x] **Step 3: Implement the strict binding receipt contract** without weakening existing gates.
- [x] **Step 4: Run the focused readiness tests and confirm all pass**, including existing workspace, research, and native-send separation tests.
- [x] **Step 5: Commit** the gate and tests as `fix: require candidate database binding for workspace release`.

### Task 3: Build and encrypt a complete workspace runtime bundle

**Files:**
- Modify: `scripts/runtime_bundle.py`
- Create: `scripts/build-runtime-bundle.py`
- Modify: `tests/test_candidate_promotion.py`
- Create: `tests/test_runtime_bundle.py`

**Interfaces:**
- Keep `compose_workspace_receipts(...) -> dict`, `build_workspace_bundle(...) -> dict`, `encrypt_workspace_bundle(bundle, key_hex) -> dict`, and `decrypt_workspace_bundle(envelope, key_hex) -> dict` as the module API.
- Add `encrypt_observation_packet(packet, key_hex) -> dict` and `decrypt_observation_packet(envelope, key_hex) -> dict` for the intermediate stage artifact; use a separate protected 256-bit observation key and a distinct envelope schema/AAD from the final bundle.
- The CLI accepts a private input directory, exact source SHA, and output path; it composes schema/API/deployment-binding observations with protected canary and rollback receipts, evaluates only the `workspace` gate, writes an immutable encrypted envelope, and never writes plaintext receipts to a public path or stdout.
- Final envelope keys remain exactly `schema`, `algorithm`, `source_sha`, `nonce`, and `ciphertext`; use AES-256-GCM and source SHA as authenticated metadata.

- [x] **Step 1: Write failing tests** for missing binding, wrong source/deployment/database digest, duplicate JSON keys, stale/future receipts, wrong key, tampered ciphertext, paid activation, existing output, intermediate-envelope separation, and ciphertext-only CLI output.
- [x] **Step 2: Run the focused tests and confirm they fail for the expected missing validation/CLI behavior.**
- [x] **Step 3: Complete receipt composition and the CLI** with immutable output creation, bounded input sizes, strict JSON parsing, generic sanitized failures, and best-effort private temp cleanup.
- [x] **Step 4: Run `python -m pytest tests/test_runtime_bundle.py tests/test_candidate_promotion.py -q` and confirm all pass.**
- [x] **Step 5: Commit** bundle code and tests as `feat: create encrypted workspace runtime bundles`.

### Task 4: Stage, probe, human-check, and attest the exact candidate

**Files:**
- Create: `.github/workflows/buyeros-runtime-bundle.yml`
- Create: `scripts/collect-runtime-binding.py`
- Modify: `scripts/runtime-observation-packet.py`
- Create: `tests/test_runtime_bundle_workflow.py`
- Modify: `tests/test_runtime_observation_workflow.py`

**Interfaces:**
- Keep `.github/workflows/buyeros-runtime-acceptance.yml` as the existing redacted, non-promotable observation workflow; partial observations remain unusable for promotion.
- The new `workflow_dispatch` workflow accepts a successful CI run ID and contains two jobs. `stage-probe` runs from protected `main` in `buyeros-runtime-readonly`, verifies the input run is current-main SHA with all 12 required jobs green, stages the exact source to Vercel production target with domain assignment skipped, probes the immutable candidate, and uploads only an intermediate encrypted observation artifact.
- `bundle-signoff` uses `buyeros-production-promote`, so the required reviewer sees the staged deployment URL and redacted probe summary before approving. It reads `GET /repos/YNWAforever/BuyerOS/actions/runs/${{ github.run_id }}/approvals`, requires an approved record for that environment and a reviewer ID different from `${{ github.actor_id }}`, and requires the exact source/deployment-bound canary comment from Global Constraints. It decrypts the intermediate artifact in memory, binds reviewer identity and comment digest, builds the final encrypted bundle, attests its exact ciphertext, and uploads only `buyeros-attested-runtime` containing `runtime-bundle.json`.
- Use `BUYEROS_RUNTIME_OBSERVATION_ENCRYPTION_KEY` only for the intermediate packet and `BUYEROS_RUNTIME_BUNDLE_ENCRYPTION_KEY` only for the final artifact in the protected signoff environment.

- [x] **Step 1: Add workflow tests first** for main-only execution, exact-CI-head and all-job verification, no domain assignment, protected branch/environment rules, encrypted intermediate artifact, approval-history identity binding, exact canary comment, encrypted-only final artifact, exact attestation subject, and retention of partial observations as non-promotable.
- [x] **Step 2: Run `python -m pytest tests/test_runtime_bundle_workflow.py tests/test_runtime_observation_workflow.py -q` and confirm new assertions fail** before adding the workflow.
- [x] **Step 3: Implement the binding collector and two-job workflow**; keep secrets out of command output and ensure failure paths publish neither plaintext files nor partial final bundles.
- [x] **Step 4: Run the workflow tests plus `python -m pytest tests/test_runtime_observation_packet.py tests/test_workspace_runtime_observations.py -q` and confirm all pass.**
- [x] **Step 5: Commit** workflow, collector, and tests as `ci: stage and attest protected workspace runtime bundle`.

### Task 5: Verify the attested bundle and enforce fail-closed promotion

**Files:**
- Modify: `scripts/promote-candidate.py`
- Modify: `.github/workflows/buyeros-promote.yml`
- Modify: `tests/test_candidate_promotion.py`

**Interfaces:**
- `promote(manifest, receipts, gate, *, attestation_verified, metadata, execute, promote_alias) -> dict` remains the pure decision boundary; it may call `promote_alias(candidate_deployment_id)` once only after all evidence and remote controls pass.
- Verify the exact artifact attestation against `.github/workflows/buyeros-runtime-bundle.yml` on `refs/heads/main` before decrypting. Re-evaluate the decrypted workspace bundle, re-read exact CI jobs, branch/environment protection and current-run approval identity, Vercel project/team/repository and auto-assignment state, and exact staged production deployment.
- The promotion workflow downloads only `buyeros-attested-runtime` from the selected runtime run, pins the gate to `workspace`, and reads its own environment approval record to confirm non-self approval before the alias call. Research and native-send gates remain disabled.

- [x] **Step 1: Add failing tests** for missing/non-self reviewer evidence, changed branch/environment rules, auto-assignment enabled, wrong project/team/repository, CI/job/source/deployment mismatch, preview deployment, and unknown alias-call outcome.
- [x] **Step 2: Run `python -m pytest tests/test_candidate_promotion.py -q` and confirm each new test blocks before invoking the alias callback.**
- [x] **Step 3: Implement strict metadata/attestation checks and preserve the single-call `promotion_unknown` behavior.**
- [x] **Step 4: Run `python -m pytest tests/test_candidate_promotion.py tests/test_runtime_bundle_workflow.py -q` and confirm all pass.**
- [x] **Step 5: Commit** promoter, workflow, and tests as `fix: gate production promotion on attested protected runtime`.

### Task 6: Verify release controls, deploy once, and save the 24 source checks

**Files:**
- Modify as needed: `scripts/promote-candidate.py`, `.github/workflows/buyeros-promote.yml`, and focused release tests only if a verified blocker is found.
- Use existing production source-check API/UI and existing Golden Resources records/notes; do not change their content as part of this task.

**Interfaces:**
- Release prerequisites are observable readbacks: strict required-check branch protection on `main`; `buyeros-production-promote` restricted to protected branches and a non-self reviewer; Vercel repository/team/project match, production branch `main`, and `autoAssignCustomDomains=false`; exact main CI run and staged deployment IDs.
- After promotion, production readback must match the exact staged deployment/source, schema head `0054_buyer_source_checks`, and disabled paid/delivery settings before any source-check write.
- Save one append-only record per existing Golden Resources buyer through authenticated BuyerOS as `willylai@fimmick.com`, preserving original date, grade, rationale, limitations, and official-source links; read back exactly 24 records and 57 links and compare all source notes unchanged.

- [ ] **Step 1: Re-run PR CI on the final implementation SHA** and confirm all required jobs pass; a failed, skipped, or stale run blocks staging.
- [ ] **Step 2: Read remote controls and production migration state without mutation.** If any control is absent, stop and request only the specific reviewer identity or owner action required; do not bypass or invent evidence.
- [ ] **Step 3: Run the protected candidate workflow and inspect encrypted artifact/attestation metadata** without exposing or downloading plaintext outside protected execution.
- [ ] **Step 4: Run the protected promotion workflow once and read back the production alias.** If the result is uncertain, preserve `promotion_unknown` and reconcile read-only; never retry blindly.
- [ ] **Step 5: Read back production settings and migration head, then create/read back the 24 records** only if the exact deployment and all disabled controls are confirmed; stop without writing if any check differs.
- [ ] **Step 6: Record exact source SHA, CI run, staged/production deployment IDs, migration head, record/link counts, and test evidence; commit any resulting source changes separately.**

---