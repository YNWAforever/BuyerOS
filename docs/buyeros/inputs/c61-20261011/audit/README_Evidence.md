# BuyerOS 2026-10-11 Evidence Pack

Read `BuyerOS_Audit_2026-10-11_zhHK.html` or the Markdown report first.

This is an audit snapshot of source `cbbe0e93b0132ae07ff0d87f6cc57f871f13200e`, deployed to `buyer-os-nu.vercel.app` as `dpl_DWwUAPyLxDR6pLU95BgcUxgseAFZ`.

## Contents and interpretation

- The tracker XLSX shows concise current columns across five sheets. The CSV files retain the fuller historical fields prefixed `baseline_` and latest current fields. Prefer `current_status` / `current_result` for this audit date. Original baseline fields remain historical.
- Findings: F01–F22 preserved, F23 (production missing relation) and F24 (promotion gap) added.
- Cases: 114 original + 16 C61 + 18 N11 = 148 IDs. This is a case inventory, not 148 freshly executed acceptance tests.
- Tasks: 30 original C61 + C61-31/32/33 = 33. Existing code is not automatically accepted in production.
- Operations: 93 declared OpenAPI operations; only workspace directory failure is marked exercised here. This is not 93 endpoint tests.
- UI actions: 48 representative inherited actions, with clearly labelled current observations.
- `evidence/` contains redacted production diagnostic samples, source/deployment/CI receipts, current source excerpts, focused local test logs/XML and extracted historical data.
- `SHA256SUMS.txt` hashes every retained file except itself. This pack does not include the repository, dependency installs or browser credentials/screenshots.

## Local execution receipts

Node v24.19.0, pnpm 11.25.0, uv 0.12.23. Dependencies installed from repository lockfiles using `pnpm install --frozen-lockfile` and API `uv sync --frozen --group dev`.

From the pinned repository root:

```bash
node --test --test-reporter=spec tests/neon-session.test.mjs tests/neon-production-config.test.mjs tests/neon-auth-boundary.test.mjs tests/neon-security-proxy.test.mjs tests/audit-research-intent.test.mjs tests/audit-bulk-manifests.test.mjs tests/audit-draft-grounding.test.mjs tests/audit-job-query.test.mjs
```

From `services/api`:

```bash
uv run --frozen pytest tests/test_provider_registry.py tests/test_delivery_protocol.py tests/test_workspace_benchmark_tools.py -q --junitxml=focused-api-tests.xml
uv run --frozen pytest tests/test_neon_verifier.py tests/test_live_search_adapter.py tests/test_live_model_adapter.py tests/test_live_contact_adapter.py -q --junitxml=auth-provider-tests.xml
uv run --frozen python ../../scripts/generate-operation-routes.py --check
```

Results: Node 81 passed, API focused 105 passed, auth/provider 139 passed. No failed or skipped tests in these batches. The two Python sets do not overlap; hosted CI suites and their focused subgroups must not be summed with these local results.

The local environment did not provide Docker/owned PostgreSQL. Database integration suite evidence comes from GitHub Actions run 38117173377 at the same SHA, explicitly labelled hosted. No production load or paid provider calls were performed.

## Handling production evidence

E03 retains only allowlisted diagnostics and the two request IDs observed in this audit. Raw SQL parameters, identity subjects, passwords, tokens, cookie values, DSNs and OAuth callback parameters are excluded. Runtime errors are samples, not a traffic rate or number of affected users.

Actual DB target, schema head and runtime grants were not read. The runtime proves a required relation is unavailable, but the exact migration/deployment mistake requires C61-31. Never execute a production migration merely because this document mentions a migration revision.

Historical baseline files are normalized readable exports obtained from the named prior report/plan files. They retain original IDs and text but are not asserted to be byte-identical to the original ZIP. The SHA256SUMS file attests this new pack's contents only.

## Release gates

Release A, Neon-only and native send remain not accepted. A green CI or Vercel READY state is not production workflow acceptance. Auth0 login succeeded, workspace failed with 42P01. Provider registry and delivery authorization remain closed in source.

No product code, production schema, membership, provider activation, spending or external messaging was changed during this audit.
