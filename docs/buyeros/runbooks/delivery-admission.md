# C61-20 independent exact-revision public admission

This locally verified candidate does not enable native send. The original
`POST /drafts/{draft_id}/deliver` kill boundary remains403. The new independent
`POST /drafts/{draft_id}/delivery-intents` requires valid canonical authentication,
current tenant membership and reviewer/workspace_admin permission. The independent
`BUYEROS_DELIVERY_ADMISSION_ENABLED` setting defaultsfalse. It does not select a
provider or activate account/sender/pricing; the server-owned authorization selector
still returnsNone. Enabling only the flag returns503, without paid ledger writes.

The request accepts only draft_revision_id, recipient_ref, sender_identity_id and
approval_id, all nonzero UUIDs. Stable Idempotency-Key is8..128 ASCII characters
from `[A-Za-z0-9:_/-]`; client text, provider/account, amount and actor are forbidden.
Actual body, digest and canonical actor come from current server-owned records.
Admission uses the original production-paid gate/atomic0050 producer, not test mode.
It creates one original operation, full reservation with three budget scopes,
immutable message/liability/authorization and registered native outbox. The HTTP
request performs no provider network I/O and returns only message_id/state/replayed.

Same-body replay always rechecks current exact approval/policy/suppression and
permissions; cached202 never grants authority. Original unknown/accepted state and
full hold survive a replay. A new key does not authorize another send. Inactive or
foreign workspace membership uses the existing non-enumerating404; an operator's
insufficient reviewer role is403. A real foreign draft is404 under owned tenant scope.

## Evidence and rollback

C61-20 independent public admission now wired as POST /v1/workspaces/{workspace_id}/drafts/{draft_id}/delivery-intents (admitDraftDelivery). Default new delivery_admission_enabled=False preserves403; enabling it without a reviewed server-owned DeliveryBudgetAuthorization still refuses503. Existing /deliver/disabledDeliveryBoundary remains unconditionally403 and all89 original OpenAPI operations are semantically unchanged; additive90th operation and strict four-nonzero-UUID body regenerate both type/route maps. No arbitrary content/provider/account/money/actor/client scope is accepted. Signed canonical principal/current tenant membership/reviewer-or-admin/rate admission feed original0050 atomic exact-approved-revision producer in environment=production, never a test bypass. Stable8..128 ASCII key and actor/operation/tenant/draft body fingerprint preserve original intent; replays recheck current approval/policy/suppression and return current original message state rather than cached202. Accepted/unknown cannot resend under a new key or create another operation/hold/outbox. Initial27 missing-route RED retained; refined46 RED46F0E/S→46GREEN; real foreign draft and foreign-workspace404 have matching owned202 controls, inactive membership follows existing non-enumerating404 contract. Required affected15 actual modules442P0F/E/S, exact unique native collection=freshJUnit and immutable input/protected10; this count contains46/45/73 subsets and must not be summed. First plan-proposed nonexistent test_delivery_db.py collection is invalid setup, retained separately, no product RED/pass. CI46/all17families adds2positive/6negative probes, all prior API steps/other jobs unchanged. Actual generated types/90routes/TypeScript/lint fourchecks exit0; lint retains7 warnings; native Node generator1P0FES is separate, no independent Node discovery/full frontend job claim. No migration/RLS/JWT/UUID/FK/provider or worker runtime change; selection remainsNone, provider network/spend/send0. Public PR12 stays1b21dc4, LOCAL_ONLY. Current complete API/frontend/built/hostedCI/provider/production/human acceptance is not claimed. Reviewed registry/HTTP pool lifecycle, original-ref status dispatch/suppression routing, verified economic settlement, send UI and independentC61-30 remain open. ReleaseA, Neon-only and native send NOT_ACCEPTED.

Source parent:73aee0cb064bcfda85b5c97648adeca9fc38b7d2. Exact input hashes, native
discovery/JUnit and committed-source bridge bind this slice. Existing0050 migration
and0047→50 rollback payloads are unchanged/unapplied. Roll back only this new route,
setting/contract/CI slice to73aee0c, retaining prior JWKS/native delivery/HTTP reader
and0050-compatible schema/runtime. Close new admission/selection/dispatch, preserve
all canonical UUID/FK/intents/refs/events/scopes/history and full unresolved holds.
No populated ledger downgrade, unknown resend or remote rollback is authorized.
