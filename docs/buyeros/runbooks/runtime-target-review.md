# Private runtime-target review

Use the **BuyerOS private runtime-target review** workflow to diagnose a staged candidate, the canonical deployment, the protected schema credential, or existing QA accounts. The encrypted report is for diagnosis.

## Authority and destination

Only a fresh owner (`201698560`) manual dispatch on this repository's `main` runs. Reruns are rejected. The job uses `buyeros-runtime-readonly`, checks out the exact dispatch SHA and disables persisted checkout credentials.

Supply an RSA public PEM and keep the private key in the Git-excluded operator store. To review a candidate, also supply both `candidate_deployment_id` and `candidate_source_sha`. Obtain them from the reviewed staging run.

Before sending the application probe credential, the script reads the fixed canonical alias through the Vercel management API and verifies the deployment's project, team, production/READY state, repository, full source SHA and immutable hostname. Management requests have a fixed API host, bounded JSON bodies, no inherited proxy and no redirects. A changed canonical assignment at the end aborts publication.

## What is collected

- Canonical deployment/source identity and whether its listed environment contains the runtime-source setting.
- One direct metadata transaction using the protected `buyeros_api` credential. The transaction is read-only, bounded by connection/statement timeouts, and checks the real login, lack of privileged-role membership and a single schema head.
- One protected GET to the verified immutable canonical deployment's binding endpoint. The result records its HTTP status and whether the exact deployment, source, schema head, and database target match.
- When a candidate is supplied, verify its source, project, team, repository, READY state, and empty alias inventory before making one GET to its binding endpoint. Use the project's existing automation credential for both reads. The encrypted `candidate_binding` report contains a fixed failure category and separate comparisons for source, deployment, database target, and schema head.
- Unverified expiration-claim hints for the four existing credentials. These hints are explicitly **not** signature verification, authentication or revocation evidence. Opaque or invalid claims remain unknown.
- The existing seven account reads only when the seed already names that exact source and immutable origin. Otherwise they are not attempted. A stale seed is never rebound to another source or host for this review.

The script performs no schema or business-data mutation, build, deploy, activation, alias assignment or signoff. HTTP GETs may still cause ordinary server access logging/rate-limit bookkeeping. Raw API bodies, credentials and exception text are excluded from review metadata. Known credential values accidentally embedded in otherwise allowed metadata stop publication.

## Encryption and output

Only `buyeros-runtime-target-review.encrypted.json` is uploaded, for one day. The envelope reuses the tested RSA-OAEP-SHA256/AES-256-GCM private input-review protocol, recipient fingerprint and authenticated header. Clear diagnostic metadata is never written to a runner file.

The encrypted payload schema is `buyeros.private-runtime-target-review.v1`. Canonical-only calls keep their existing format. Calls with a candidate add `candidate` and `candidate_binding`, each tied to the supplied deployment and source. The top-level source identifies the diagnostic code. Its `promotable`, `acceptance` and top-level `deployment_binding_verified` fields are always false, including when the legacy binding matches. It cannot substitute for the protected release's current-source candidate binding, account-state proof, authenticated journey or compatible rollback acceptance.

On the backend, verify the Actions run's exact source, owner and success, decrypt to the retained recipient, check the closed payload schema and keep the result user-encrypted outside the preview root. Do not publish the private metadata in chat or commit it.

## Interpreting results

A failed binding read does not authorize a target change or migration. A denied metadata read does not justify granting broad table access. An expired or rejected credential does not prove revocation. Resolve the reported facts, prepare source-specific reviewed records and retain every existing production gate.

The separate input-review workflow remains network-free. Use it to recover validated seed metadata; use this workflow only for bounded current-state diagnostics.
