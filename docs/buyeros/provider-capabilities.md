# Provider capabilities (T14, fixture implementation)

Reviewed against BuyerOS source at `f43a9d88b334c2c4029fa06fa71624ed52efe4a2` and the pinned upstream inventory in `research/UPSTREAM_AUDIT.md`. This file records the local interface and evidence gap; it is not a vendor approval record.

| Service | Named live provider | Price and liability proof | Idempotency/status proof | Activation |
| --- | --- | --- | --- | --- |
| Public-web search | None selected | None | None | Blocked |
| Model routes | None selected | None | None | Blocked |
| Optional business-contact lookup | None selected | None | None | Blocked |

`ProviderCapability` records provider, adapter version, service, supported markets/languages/roles, auth model, price version, maximum USD liability, idempotency/status/callback/cancel evidence states, retention, verification time and source URLs. `activation_blockers` rejects an unsupported market, language or role, a missing bound, unknown status semantics, missing safe reconciliation, incomplete evidence and any provider absent from the selected-live registry. That registry is empty. The synthetic `fixture` adapter can only pass its gate in the test environment. Search, model and contact are evaluated separately.

`ProviderAdapter` exposes `estimate`, `submit` and `status`. A submission returns accepted, rejected or unknown plus a stable provider reference and redacted digest where known. The deterministic fixture stores an accepted request before simulating a timeout, returns unknown, keeps the same reference on duplicate intent and makes no HTTP call. Unknown holds remain reserved under T13; only verified economic events can settle or release them. Quote confirmation must compare the exact recorded pricing version; a changed version requires a fresh quote and user confirmation. A capability gate alone does not authorize a paid call.

Model routes record a prompt version, selected route ID, fixed tool set, token ceilings, deadline and repair count. No route ID is selected. Source pages and prompt text cannot grant tools. The current fixture route permits no external tools. Contact remains independent of search readiness.

No upstream code was copied in T14. The pinned audit identifies selected AI_Find_Customer material as MIT but flags dependency and parser-license review; OpenOutFind/OpenOutreach are GPL and deferred, and OpenOutSend is separate from the disabled delivery scope. A future live adapter requires a named provider and official request/error/pricing evidence, account rights, retention and data-use review, demonstrated maximum charge, verified acceptance/reconciliation semantics, and a separately authorized activation. No endpoint, webhook schema, model ID, price, credential or owner approval is inferred here.

Local verification: `uv run --frozen pytest -q tests/test_provider_contracts.py tests/test_search_adapter.py tests/test_provider_op.py` against disposable PostgreSQL. Fixtures prove protocol behavior only; no real-provider integration is verified.
