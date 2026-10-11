# C61-15 provider contract and selection gate

Reviewed 2026-10-07 Asia/Hong_Kong. Decision: no live vendor is selected or activated. Search, model and contact are independent contracts; native delivery remains C61-20/30.

The immutable registry resolves only code-owned provider names and versioned capabilities. A registration carries official sources/date, auth model, markets/languages/roles, exact Decimal USD maximum liability, pricing/adapter versions, idempotency/status/callback/cancel evidence, retention and isolated sandbox evidence. Contract hashes change with tariff or any capability evidence. Admission rejects an old price/hash, unknown reconciliation, missing evidence or excess budget before constructing an adapter. `test` cannot bypass the live allowlist. Fixtures are constructible only in explicit tests and never production/staging. Capability API retains unconfigured/disabled states and adds safe reason codes. Settings gives a bilingual administrative next step.

## Candidates for owner selection

These are review options, not approved registrations. All account-specific fields and sandbox acceptance remain unverified.

| Service / candidate | Official contract checked | Remaining activation evidence |
| --- | --- | --- |
| Search / Brave Web Search | API key in `X-Subscription-Token`; public Search plan lists USD 5/1000 requests. [Authentication](https://api-dashboard.search.brave.com/documentation/guides/authentication), [public pricing](https://brave.com/search/api/) | Confirm account tariff, HK/zh-HK results/filter mapping, retention, exact bounded liability and uncertainty reconciliation. Public plan text is not an approved account tariff. No request-status/idempotency guarantee was established. |
| Model / OpenAI Responses | Bearer API key; background response retrieval and cancellation are documented. [Background workflow](https://developers.openai.com/api/docs/guides/background), [retention](https://developers.openai.com/api/docs/guides/your-data) | Choose exact model/version, tokenizer and input/output caps; confirm tariff, location/language quality, retention and create-request uncertainty semantics. Default stored responses retain application state for 30 days; account controls must be checked. A returned response ID supports retrieval but does not prove safe retry of an unknown create. |
| Contact / Hunter V2 | API key header supported; Domain Search provides sourced contacts. Official test key returns dummy results. [V2 API](https://hunter.io/api-documentation/v2) | Confirm account credits→USD maximum liability, role/market coverage, status/idempotency, retention and lawful purpose. Dummy test-key results cannot validate real contacts or billing; no external request was made. |

No verified adapter/auth secret/account tariff exists in this execution. Registry defaults remain empty; `SELECTED_LIVE_PROVIDERS` remains empty. Runtime liability/pricing fields are not filled with public guesses. External spending ceiling for this execution is **USD 0.000000** until the owner names vendors/accounts and authorizes a specific isolated test allowance. This is an authorization ceiling, not a vendor price.

## Credential and authorization map

| Candidate | Proposed server-only credential source | Required owner input before live testing |
| --- | --- | --- |
| Brave | `BRAVE_SEARCH_API_KEY`, account API-key dashboard | account/plan, exact approved tariff and maximum queries/USD |
| OpenAI | `OPENAI_API_KEY`, selected project service-account key | project/model, token caps, tariff, retention policy and USD allowance |
| Hunter | `HUNTER_API_KEY`, account API dashboard | account/plan, credit tariff, roles/purpose and lookup/USD allowance |

These names document a future adapter contract; this commit does not read credentials or create live transports. Supply references/IDs through the existing secret manager, never paste secrets into the tracker. No email/contact enrichment, mailbox send or provider account mutation is authorized by an offline registry test.

## Verification and rollback

RED exact adapter resolution: 3 assertion failures; the activation boundary adds one failing test-environment bypass case. Final required registry + provider + capability suite: 38 passed, 0 fail/error/skip, including one owned-PG economic-event reconciliation case. Artifacts: `artifacts/c61/C61-15-verified.json`, `c61-providers-final.xml`; failed attempts are retained.

L0/L1 passed. Built fixture UI copy needs the combined-source smoke; real-provider sandbox (L2), production readback (L3) and human UAT (L4) are blocked/not run. P08/S04/S05 remain blocked for their live requirements. Rollback: revert registry/readiness/copy, retaining contract/evidence; no migration, production activation or spending occurred. C61-16 can consume the local registry contract and implement offline lifecycle integration while each live selection gate remains blocked.
