# C61-33a / C61-28a guarded promotion

This candidate adds an executable alias entry point in `.github/workflows/buyeros-promote.yml` → `scripts/promote-candidate.py` → `evaluate_release`. It is **not adopted in production**. G0, GN, GA and GS remain unaccepted.

The source configuration disables main Git deployments. The remote project currently has `autoAssignCustomDomains=true`, production branch main, and main is unprotected. The owner must adopt reviewed staging controls before the entry point permits promotion. A repo configuration change alone is not remote evidence.

The entry point verifies the exact bundle bytes using GitHub artifact attestation from the designated protected `buyeros-runtime-acceptance.yml` producer on main. That live receipt producer is **not available in this batch**; fabricated/local JSON cannot use the alias path. It then re-reads the bound CI run and all original required jobs plus `release-readiness`, staged production deployment source/READY state, main protection and the environment's non-self review/branch rules. Missing API metadata fails closed. `--execute` is allowed only from the reviewed main guarded workflow. Its environment must have required reviewers, prevent self review and allow protected branches only.

The operator first stages a production build without alias assignment. Live runtime collection must bind source/tree, exact configuration digest, DB target digest, deployment/artifact IDs, schema contract, known-account roles/projects/revoked/foreign controls and compatible frontend+API rollback. The reviewed bundle has a maximum 15-minute age; expiry requires fresh reads, never changing a boolean. G0 excludes paid provider and worker activation. Research and native send require their separate GN/GA/GS evidence.

Pending adoption packet: disable remote auto assignment, protect main with the required checks, configure `buyeros-production-promote` reviewers/branch policy and server-only credentials, implement/review the real runtime collector, fix exact deployed DB binding, produce a real canary and compatible rollback artifacts, then seek scoped promotion authorization. No setting, secret, deployment, schema, provider or alias was mutated in this batch.

The protected environment's `BUYEROS_PROMOTION_METADATA_TOKEN` must be a short-lived repository-scoped GitHub App installation token with Actions/Contents/Attestations and Administration **read only**. The workflow's default token cannot read branch protection. Provisioning/minting this token remains an owner prerequisite; missing credentials fail closed. Vercel credentials remain server-only in the same environment.

Promotion invokes the alias command once. A timeout/unknown outcome is recorded as `promotion_unknown` and must be reconciled read-only; no automatic retry. A successful submission still requires alias/source/config/schema/workspace readback before acceptance. Check remote auto assignment again after promotion and stop rollout on unexpected control drift.

Local transport tests prove a missing identity relation, unattested JSON, preview build, wrong source, failed CI or unprotected controls never call the alias function. Their normal fixture calls it once. These are isolated control tests, not live Vercel promotion receipts.

References: [staged production deployments](https://vercel.com/docs/deployments/promoting-a-deployment), [Git deployment controls](https://vercel.com/docs/project-configuration/git-configuration), [artifact attestation verification](https://cli.github.com/manual/gh_attestation_verify).
