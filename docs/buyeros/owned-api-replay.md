# Owned API rate-window and replay verification

C61-25 section18 / F07,F11,F12,F18, with C61-19/20 uncertainty safeguards. These cases use the existing guarded disposable PostgreSQL16 fixture, the real RS256 verifier with local JWKS, current canonical mapping/membership and the nonprivileged API role. They certify source behavior in isolation. Real Neon sessions, live API/DB/worker binding, provider acceptance, rollback targets, numerical performance budgets and employee UAT remain separate gates.

Run from `services/api` with the existing frozen API environment and `BUYEROS_STRICT_INTEGRATION=1`:

```sh
uv run --frozen pytest tests/test_owned_api_rate_window_db.py tests/test_owned_api_idempotency_db.py tests/test_owned_api_unknown_replay_db.py --collect-only -q
uv run --frozen pytest tests/test_owned_api_rate_window_db.py tests/test_owned_api_idempotency_db.py tests/test_owned_api_unknown_replay_db.py -q --junitxml=artifacts/c61-owned-api-replay.xml
```

The default API suite discovers all9 cases. Each case attaches `owned_evidence` to native JUnit, containing raw response envelopes/request IDs and durable SQL readbacks. No JWT, DSN or real customer data is attached. Required CI must compare exact discovery identities with execution and refuse empty, filtered, skipped or failed suites.

- Rate-window: controlled clock, eight concurrent requests with a two-slot threshold; the same actor in two tenants; actual minute rollover; failed business transaction consuming admission without partial business writes. The clock is controlled to avoid a minute boundary race in the test; this does not measure production clock skew or request latency.
- Concurrent idempotency: both original session reads observe an absent scoped key before either inserts. Original savepoints/unique index arbitrate identical and changed-body requests. One project, one completed record and one audit are required; original replay returns the winner's exact result.
- Response loss: transport drops all bytes after original bulk admission commits. Replaying the original key/body/digest/If-Match reads the original job and outbox. A fresh key is refused. A separate injected abort before commit verifies zero partial state and subsequent single commit using the same key.
- Synthetic unknown/accepted delivery: admission is selected only inside the disposable fixture; no worker is dispatched. Original intent, revision, recipient, sender, approval, provider operation/ref/hash, outbox and full active hold remain unchanged across three same-payload replays and a refused fresh key. The concrete Resend submit boundary refuses any attempted POST. These synthetic states prove replay safety; they do not demonstrate a real send or provider receipt.

Existing limiter, idempotency, Neon, bulk, provider and delivery implementations are reused unless an actual causal regression proves a defect. G0 remains independent of paid provider activation. The unchanged actual thirty-minute mixed workload and all twelve required CI jobs remain required on the same final candidate.
