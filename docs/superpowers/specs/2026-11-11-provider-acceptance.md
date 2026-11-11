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
  are rejected before replay.
- **Replay** re-runs the production validation and asserts the recorded
  expectation:
  - model: the recorded structured output must validate against the recorded
    basis (review-only status, selected citations only, bounded bytes);
  - MCP: arguments are validated first, the recorded payload is projected and
    checked (page drift, email/credit consistency), and a recorded transport
    observation is classified exactly as the transport classifies it — a
    failure after `tools/call` begins is `unknown`, never `rejected`.
  - A mismatch between the recorded expectation and the replay is an error, not
    a silent pass.
- **Receipts** carry kind, case, outcome, content digest (SHA-256 over canonical
  fixture JSON), and reported `credits_used` for accepted MCP exchanges.
- **Recorded fixtures** live in `services/api/tests/provider_acceptance/*.json`
  and are regenerated only by
  `services/api/tools/generate_provider_acceptance_fixtures.py` (deterministic,
  no network).
- **Live gate**: live execution requires `BUYEROS_PROVIDER_ACCEPTANCE_LIVE=1`
  *and* `BUYEROS_PROVIDER_ACCEPTANCE_CREDIT_CAP` in `1..1000`. Otherwise the
  harness raises `LiveAcceptanceRefused`; it never discovers credentials. A
  live case is dispatched exactly once through the injected client callable, and
  a non-accepted or unknown result fails closed with no retry.
- CI runs recorded replay only. A live suite can be added later behind the same
  gate once Phase 1 admission exists; this increment deliberately ships no
  provider client and no credential path.

## Verification

`services/api/tests/test_provider_acceptance.py` covers: full fixture replay and
classification, review-only accepted model output, unselected-citation and
refusal rejections, unknown-vs-rejected MCP classification, reported credits,
malformed/oversized/mismatched fixture rejection, digest stability, and both
live-gate refusal and single-dispatch fail-closed execution with a fake client.
API pytest inventory moves 4051 → 4064 (+13).
