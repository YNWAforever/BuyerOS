# C61-16 search transport and durable receipt candidate

This is local implementation and fixture verification, not a production release or real-provider acceptance. The registry remains empty, live providers remain unselected, paid admission stays closed, and research 503/native-send 403 remain truthful gates. The candidate cannot yet complete a real research run; C61-17/18/19 and the selected supplier contract are separate dependencies.

## Implemented boundary

`BraveSearchClient` makes one bounded GET to the code-owned HTTPS endpoint, with an injected HTTP client and server-only subscription token. Query length includes whitespace; maximum 600 characters/75 words, count 1–20, no pagination or redirects, 10-second deadline, and 262,144 decoded response-byte ceiling. Country and language mappings and the API-version date are explicit configuration, not model-supplied URL/headers. Bad schemas, unsafe result URLs, credential echoes, timeout, rate limiting and errors remain unknown. No HTTP retry or no-charge claim is made.

The protocol was checked against [Brave authentication](https://api-dashboard.search.brave.com/documentation/guides/authentication), [web search](https://api-dashboard.search.brave.com/api-reference/web/search/get) and [versioning](https://api-dashboard.search.brave.com/documentation/guides/versioning). The tests' `2026-10-01` API version, tariff and keys are synthetic; they establish no account availability, supported version or invoice terms.

`LiveSearchAdapter` implements the existing `estimate/submit/status` boundary; vendor work still runs through `execute_external`. Native generic intents select their validated payload service instead of accidentally using contact. The activation registry is consumed with the declared environment, without fallback or automatic registration.

`PostgresSearchReceipts` freezes canonical actor/project UUIDs, query/input hash, pricing/contract hash, operation/outbox references and worker generation/backend/epoch. Current DB membership/startRun permission, active project, account-research policy, cancellation, reservation and original payload are checked before claim. API prepares; worker claims/finalizes; runtime roles do not own the table and cannot bypass its forced tenant RLS. Unknown/received cannot return to prepared. Claim commits before network await; actual tests use another connection with `FOR UPDATE NOWAIT` during the synthetic response to establish that receipt/operation locks are not held across HTTP.

A local result is accepted only after durable readback. A lost write acknowledgement triggers read-only reconciliation. A response blocked by a stale epoch cannot claim accepted. Restart/submission replay checks the receipt instead of another vendor request. A supplier's request ID, invoice, native status semantics and authoritative observed charge are still absent: local succeeded status is only a saved search response. No cost is invented and the budget hold is preserved until separate authoritative settlement.

Each candidate source includes URL, title, excerpt, retrieval time and metadata content hash. A search snippet is tagged `search_result_metadata/page_retrieved=false`; it is not fetched page text, evidence correctness, or legal-entity proof. Same name/domain/country, parent groups and subsidiaries never auto-attach a canonical company UUID. They remain `needs_review` with `company_ref=null`. Search-source instructions are plain source data. Fetching delegates to the existing pinned, purpose/retention-aware fetch service; every permitted redirect rechecks origin/DNS/public IP, TLS uses the original hostname, and private/link-local, decompression bombs, bad MIME and oversized content are blocked/quarantined. C19 must persist reviewed company/source/evidence rows and apply retention/deletion before opening result consumption.

## Migration and rollback

Review `0040_c61_search_receipts.py` with the code payload. No production migration has run. It adds scoped receipt FKs and its own policy/trigger; historical User UUIDs/FK definitions and existing policies remain unchanged. API gets SELECT/INSERT, worker SELECT/UPDATE only; neither gets DELETE/TRUNCATE or schema ownership. A pinned-search-path security-definer function reveals only whether the exact writable revision is present; API does not gain direct access to `alembic_version`.

Metadata downgrade to 0039 retains every populated receipt, including unknown and received results. Compatible readback remains available; writes require exact 0040. Empty receipt tables can be dropped for earlier empty-schema rehearsals. Re-upgrade is idempotent and does not overwrite frozen payload/results. Do not downgrade below the compatible additive schema with retained receipts; pause admission/workers and inspect refs first. Never delete receipt rows to make rollback pass, release an unknown hold, or decrement the worker epoch.

App rollback point is the recorded pre-C16 source SHA `4eabf17f57b42bffcd85fd0cfb48a51740d57d76`. Disable search admission, fence/pause workers, retain 0040/0039 data and read-only reconcile every accepted/unknown operation before any reviewed code revert. Do not restore an older backup into service until deletion/retention tombstones and unknown acceptance records have been reconciled. The existing compatible Neon API artifact and C13 cold proof remain separate.

The C09/C13 identity rehearsals explicitly target 0039 so their exact historical-FK/policy comparison remains an identity-migration proof. General HEAD roundtrips target 0040; the worker-recovery allowlist adds only this reviewed revision and continues rejecting 0099/unreviewed future revisions.

## Verification and remaining gates

Fresh source/blob/test provenance is in `artifacts/c61/C61-16-tested-source.json`. RED logs are retained, including new-fixture mistakes (wrong outbox replay expectation, migration owner selection, epoch alignment and oversized pytest IDs on Windows). These are not evidence for the historical workspace 500 root cause. Original 114 case fields/results are preserved; only execution fields are updated.

Reports are independent: offline HTTP/owned PG fixture; built preview (no new C16 browser claim); real provider sandbox; production source/config/result readback; human entity/evidence/UAT. A fixture pass or merged PR cannot close the latter gates. Required tests/JUnit must contain cases and have zero fail/error/skip; CI verifies named search discovery explicitly.

Before supplier activation, review the actual account/region and API version, selected versioned contract/filter mappings, pricing/currency/maximum liability, server credential source, safe idempotency/status or authoritative unknown reconciliation, approved bounded allowance, retention terms and sandbox evidence. No account secrets have been inspected or copied. These are local-ready artifacts with external gates pending, not blanket authority to spend, deploy, change auth or contact recipients.

Release A, Neon-only and native send remain NOT_ACCEPTED. Next local dependencies: C61-17 model evidence/basis validation and C61-18 contact quote/confirmation/results; C61-19 wires reviewed durable ports into the real research run.

The 1045-case full API attempt was stopped after 3200 seconds with no fresh JUnit; it is NOT a pass. The focused seven-case membership rerun finished 0F/E/S after a 45-second fixture startup stack diagnostic. Both logs are retained. Full-suite rerun is pending; the 10,000/50 bulk case is not newly accepted from partial stdout. No historical workspace500 root cause is inferred.
