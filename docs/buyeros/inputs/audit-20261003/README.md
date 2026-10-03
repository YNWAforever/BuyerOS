# BuyerOS audit pack — 2026-10-03 HK

Read the zhHK HTML/Markdown report first. The HTML is self-contained, including
the live screenshot. CSV files are UTF-8 with BOM. Task and case IDs preserve
the previous reports; historical outcomes are not current pass results.

## Reproduce read-only probes

Clone YNWAforever/BuyerOS and check out a78859fe474f5722be3755b10e2586436b53bf97.
Install services/api locked dependencies in an isolated environment. Then run:

    <repo>/services/api/.venv/bin/python evidence/reproduce_audit.py <repo>

This uses fictional data and a fake SQL connection. It counts actual route
execute calls but does not benchmark PostgreSQL or production latency.

## Existing checks rerun during this audit

From services/api, with BUYEROS_TEST_DATABASE_URL and DATABASE_URL removed:

    python -m pytest tests/test_api_app.py tests/test_api_auth.py tests/test_jwks_cache.py tests/test_safe_fetch.py tests/test_provider_contracts.py tests/test_snapshot.py tests/test_approval.py tests/test_settlement.py tests/test_fit_eval.py -q

61 pass / 1 DB skip. The sandbox TestClient timeout is retained separately;
the unchanged bounded rerun passed in 1.75 seconds. No DB was provisioned.

From the repository root, with TypeScript 5.9.3 available:

    node tests/domain-checks.mjs
    node tests/live-adapter-checks.mjs
    node tests/live-auth-checks.mjs
    node tests/live-runs-checks.mjs
    node --experimental-strip-types tests/vercel-services.test.mjs
    node --experimental-strip-types tests/worker-gateway.test.mjs

103 checks total. Original outer --test file summary was 2 files; individual
proxy/gateway runs prove 5+1 checks. Do not add both counts.

## Evidence limits

No credentials, callback authorization code, provider calls, production
business data exports, or full production DB copies are included.
The source excerpts are frozen to the stated SHA. E08 is historical.
SHA256SUMS.json covers the packaged artifacts; the archive itself is excluded.
The builder expects the repo next to this pack as buyeros-audit.
