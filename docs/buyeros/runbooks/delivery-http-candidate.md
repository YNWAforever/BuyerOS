# C61-20 unselected delivery HTTP candidate

This is reviewable local code. Production selection remainsNone and public deliver
remains403. MockTransport and ownedPG/native evidence do not prove vendor sandbox,
actual billing/sender/domain, production, Neon-only or human acceptance.

`ResendDeliveryAdapter` consumes server-resolved immutable PreparedDelivery,
current independent DeliveryBudgetAuthorization, separately reviewed retained
status authority, explicit DeliveryWirePricing and a server-owned HTTP client/key.
Its factory must bind the already prepared payload locally and reuse/own a reviewed
HTTP pool lifecycle; it must perform no I/O before the native POST permit commits.
No key is read from environment, no account/sender/price is guessed or selected.
The default selector is unchanged and no production factory invokes this candidate.

The code follows the official [send contract](https://resend.com/docs/api-reference/emails/send-email)
and [original-reference GET contract](https://resend.com/docs/api-reference/emails/retrieve-email).
The vendor [idempotency window](https://resend.com/docs/dashboard/emails/idempotency-keys)
does not authorize another BuyerOS POST: permanent unknown intent/hold survives
response loss, process crash, cancellation and expiration of that vendor window.
Losing the original ref remains manual reconciliation, without an invented key lookup.

All non200/redirect/network/malformed/ambiguous/oversized/credential-echo responses
stay unknown. API acceptance does not prove delivery, signed event or charge.
GET-only cold reconciliation can use a retained reviewed account/scope/ref even
after the old new-send authority expires or is revoked. It exposes no submit or
estimate method. Suppressed and opened/clicked observations cannot fabricate
unsubscribe consent or delivery; separate reviewed suppression/billing evidence is
still required before the independent native-send release gate.

## Local evidence and rollback

C61-20 unselected Resend HTTP candidate now available locally. Separate exact reviewed DeliveryWirePricing is mandatory and bounded by the original independent delivery authorization; no account/sender/price/secret selection is installed. The adapter binds only immutable server-approved plain text/from/to[one]/subject, fixed HTTPS api.resend.com/emails, original intent key and server credential header; 10s timeout, bounded request/response, no redirect/retry, no compressed/duplicate/nonfinite/credential-echo/ambiguous response acceptance. Only canonical nonzero UUID from exact200 id-only response means accepted, never delivered/cost/no-charge proof. Every non200/malformed/network outcome stays unknown. Synchronous attempt marker before the first await permits one in-process POST across12 parallel calls, including cancellation; permanent0050 unknown permit remains the cross-process authority and denies a fresh adapter resend. GET uses only an existing original canonical UUID and validates exact returned id; no status-by-intent-key lookup or lost-ref resend is invented. Only sent/delivered/bounced/complained/failed observations map to their independent state; opened/clicked/suppressed/queued/scheduled/delivery_delayed/unreviewed states conservatively stay unknown. Suppression consent/overlay and billing/readback remain separate gates. A cold ResendDeliveryStatusReader needs only separately reviewed retained account/scope/contract/ref authority and has no estimate/submit method; expired/revoked new-send authority/body is not needed. First oversized pytest parameter/windows artifact error and overbroad refusal catch invalid run retained; corrected bounded65 RED65F0E/S→65GREEN; cold5RED5→current70GREEN; actual ownedPG/native runner + bounded MockTransport accepted/500/timeout joins3 more, combined73P0F/E/S with exact native nonempty unique collection=freshJUnit. During each actual mock POST a separate restricted workflow fixture reads committed unknown/unknown_acceptance/fullhold and owner NOWAIT locks succeed; final native receipt reconciles, repeated native execution is stale and never resends. CI adds73/all14named families with2positive/6negative guard probes; all prior API steps/otherjobs retained. Existing45/382/128/4 runner results remain source0d7b7b2 scoped and are not added to73 or reclassified as full current jobs. No schema/migration/UUID/FK/RLS/JWT/public-route/production selector change. Public PR12 remains1b21dc4; LOCAL_ONLY; no external credentials/provider requests/spend/send/publication. Actual selected registry/production HTTP pool lifecycle/account/sender/pricing/billing, public delivery admission/UI/status dispatch/suppression route and separate C61-30 remain open. ReleaseA,Neon-only,native send NOT_ACCEPTED.

Source parent:0d7b7b2ad3feeec71e332196b3fde2d5f535b178. Exact input hashes and the
committed-source bridge accompany73 actual named cases; no hostedCI/full current
all-jobs claim. Prior frozen159 full jobs and0d7 native groups retain original scopes.

No new migration is introduced; existing0047→48→49→50 SQL/rollback payloads remain
unchanged and unapplied. Roll back this unselected HTTP/CI slice to0d7b7b2, preserving
the prior native orchestration/JWKS fix and0050-compatible runtime/schema. Keep
actual selection/new admission/dispatch closed; preserve original UUID/FK, intents,
refs, events/scopes and full unresolved holds. Never downgrade a populated ledger
or use an old unproven production artifact for0050. No remote rollback is authorized.


2026-10-09 C61-20 unselected owned HTTP pool: explicit finite server limits, fixed10s/no redirect/trust_envfalse; constructor/entry/prepared binding/estimate perform zero HTTP. One async-runtime owner closes only its own client after normal/exception/cancelled exit, refuses before enter/after close/reopen and waits for close despite owner cancellation. Same retained original account/workspace/contract/scope validates every prepared new-send binding; cold GET-only factory needs no revoked/expired new-send authority or pricing. No env/account/credential/sender/pricing selection is installed. Pure25RED25F0ES ->25GREEN; actual native runner three accepted/500/timeout cases now use the owned pool, prove committed unknown/full hold and no transaction lock during one POST, stale replay never resends and owned client closes. Current combined native98P0FES exact unique collection=JUnit (25pool+70wire+cold+3ownedPG/native). CI adds independent required25/nine named families,2positive8negative guards; all prior API steps/other jobs retained. This is ownedPG/MockTransport evidence, not vendor/billing/production/human acceptance. Fresh complete current API suite and rebuilt backend payload after package change still required; prior2444 fullAPI/b660 wheel bridge remain old source scope. No migration/UUID/FK/RLS/JWT or production selector/public deliver change; original403/503 retained. ReleaseA/Neon-only/native send NOT_ACCEPTED, LOCAL_ONLY.

Pool slice rollback:54b7f0d; close new admission/selection, retain0050 ledger, original refs and full unresolved holds; no external rollback or provider resend authorized.
