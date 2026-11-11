# Increment 3.7 contract — provider-acceptance harness (recorded + gated live)

Status: implementation contract. Provider-layer test harness; no migration, no
network, no credential, no paid call in CI.

## Why

Phase 3 asks for a provider-acceptance harness with recorded fixtures plus a
gated live suite. Model and MCP adapters already own strict validation
(`conversation_model.validate_basis` / `validate_proposal`,
`xverum_mcp.validate_arguments` / `projection` / `XverumTransportError`), but
there was no checked-in acceptance record proving an exchange is classified the
same way on every run, and no single refusal point for accidentally running a
paid live check.

## Contract

`buyeros_api/providers/acceptance.py`:

- **Fixture envelope** `provider-acceptance.v1` with exactly
  `schema, kind, case, expect, recorded_at, request, response`. `kind` is
  `conversation_model` or `xverum_mcp`; `case` is a bounded lowercase slug;
  `expect` is `accepted`, `rejected` or `unknown`; `recorded_at` is UTC; the
  fixture is capped at 64 KiB. Unknown keys, malformed JSON and unbounded values
  are rejected before replay. Each fixture is read and parsed once; the receipt
  digest describes exactly the bytes that replayed (no read-then-re-read gap).
- **Replay** re-runs the production validation and asserts the recorded
  expectation:
  - model: the recorded structured output must validate against the recorded
    basis (review-only status, selected citations only, bounded bytes);
  - MCP: arguments are validated first for every recording, then the recorded
    payload is projected and checked (page drift, email/credit consistency), or
    a recorded transport observation is classified exactly as the transport
    classifies it — a failure after `tools/call` begins is `unknown`, never
    `rejected`.
  - A **phase recording must carry the transport evidence it classifies**: an
    `initialize`/`tools/list` rejection needs a bounded JSON-RPC `error`, and a
    `tools/call` observation must be a JSON-RPC envelope (or an error). The
    receipt binds the recorded response digest, so response-shape drift cannot
    silently pass as `unknown`.
  - A **malformed recording is never a provider rejection**: envelope or body
    corruption raises `AcceptanceError` instead of being caught as a clean
    `rejected`/`CONTRACT_REJECTED` classification.
  - A mismatch between the recorded expectation and the replay is an error, not
    a silent pass.
- **Receipts** carry kind, case, outcome, content digest (SHA-256 over canonical
  fixture JSON), reported `credits_used` for accepted MCP exchanges, and the
  recorded response digest for transport-phase recordings.
- **Recorded fixtures** live in `services/api/tests/provider_acceptance/*.json`
  and are regenerated only by
  `services/api/tools/generate_provider_acceptance_fixtures.py` (deterministic,
  no network).
- **Live gate**: live execution requires exactly
  `BUYEROS_PROVIDER_ACCEPTANCE_LIVE=1` *and* a canonical
  `BUYEROS_PROVIDER_ACCEPTANCE_CREDIT_CAP` integer in `1..1000` (no booleans,
  whitespace, signs or thousands separators). The case name must match a
  checked-in recorded fixture case, and the client result must be JSON evidence
  (a non-serializable receipt fails closed). Otherwise the harness raises
  `LiveAcceptanceRefused`/`AcceptanceError`; it never discovers credentials. A
  live case is dispatched exactly once through the injected client callable, and
  a non-accepted or unknown result fails closed with no retry.
- CI runs recorded replay only. A live suite can be added later behind the same
  gate once Phase 1 admission exists; this increment deliberately ships no
  provider client and no credential path.

## Verification

`services/api/tests/test_provider_acceptance.py` covers: full fixture replay and
classification, review-only accepted model output, unselected-citation and
refusal rejections, unknown-vs-rejected MCP classification with evidence-bound
receipts, reported credits, malformed/oversized/mismatched fixture rejection,
malformed bodies that must not masquerade as provider rejections, phase
recordings without transport evidence, digest stability, strict live-gate
refusal (including non-canonical caps), unrecorded live cases, non-JSON live
receipts, and single-dispatch fail-closed execution with a fake client.
API pytest inventory moves 4063 → 4079 (+16) on top of the merged metrics
increment.
