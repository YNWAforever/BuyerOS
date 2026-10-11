# C61-20 scoped admin original delivery reconciliation

The local candidate POST /v1/workspaces/{workspace_id}/delivery-messages/{message_id}/reconciliation
uses the existing independent reconciliation gate and a reviewed retained provider
registry. The latter remainsNone, so no account/HTTP status call is enabled. New
delivery admission/paid flags do not authorize or prevent the separately retained
status scope. Original /deliver remains403. This is not native-send acceptance.

Only a current canonical workspace_admin may initiate this operation. The body
is optional and strict/empty: provider ref, key, account, authority, content and
amount must not come from HTTP JSON. Workspace/message are tenant selectors only;
foreign or inactive memberships/messages return non-enumerating404, insufficient
role403. A single durable expensive-write admission occurs before provider work.
Canonical membership/rate transactions close before the independently reviewed
private original-ref GET orchestrator runs. Missing original ref remains409/manual
unknown; no intent-key lookup, new key, submit, extra hold/outbox or cost settlement.

Received original observation survives mid-GET caller revocation. A fresh current
canonical membership/admin check gates the HTTP response after recording that
independent receipt, using no second rate slot. Response private,no-store exposes
only message_id/state/event_id/replayed, without raw account/ref/content. Unknown,
accepted, delivered/adverse observations remain separate from charge/no-charge
proof; canonical original refs/scopes and full unresolved holds stay intact.

## Evidence and rollback

C61-20 scoped admin retained delivery consumer implemented locally as POST /v1/workspaces/{workspace_id}/delivery-messages/{message_id}/reconciliation (reconcileDeliveryMessage). Existing reconciliation_enabled can pause new requests503; independent server retained-account/contract selection remainsNone and refuses503, never activated by client body or new-delivery flag. Optional empty strict body forbids raw ref/key/provider/account/scope/economics/content fields. Canonical JWT identity/current workspace_admin membership and one durable expensive-write rate slot are checked before closing all caller membership/rate transactions; private retained orchestration then resolves only saved original message/ref and performs GET outside canonical locks. A fresh canonical membership/admin check gates response after independently persisting received original observation, so revoked/downgraded caller receives404/403 without discarding original receipt/ref/fullhold. It does not consume a second rate slot after GET. Response private,no-store contains only message_id/state/event_id/replayed, no raw provider/account/content or charge proof. Original always403 /deliver and default-closed admission preserved; all90 prior OpenAPI operations unchanged, additive91st operation regenerates types and operation map; common Service enum/migrations/RLS/JWT/UUID/FK and native worker/HTTP transport/status protocol unchanged. Initial26 route RED26F0E/S and additional actual expensive classification/one-time rate2RED2F0E/S→focused28P0FES. Owned PG real originalA message is denied404 from current authorized B admin with matching A200 control; nonadmin403 has admin200 control; inactive404 beforeGET; midGET revocation storesaccepted observation then deniesresponse; fullholds/intents/operation/outbox/cost remain exact. Related10 actual modules169P0F/E/S, nonempty unique native collection=freshJUnit and source/protected10freeze; includes28/34/46 subgroups and must not be summed with prior291/442. CI28/all16families2positive6negative, all previous API steps/otherjobs unchanged. Actual generated91 types/routes/TypeScript/lint fourchecks0, lint7warnings; native Node generator1P0FES separate, no independent Node discovery/full frontend claim. Original114 wholefile unchanged; newcase12/13/16 evidenceappend only. Production retained registry/HTTP pool lifecycle/scheduler, reviewed signed callback route/contract, independent economics/sendUI andC61-30 remain open; actual account/sender/domain/pricing/billing/nonbillable-status quota/isolated-recipient receipts/production/human gates separate. LOCAL_ONLY, PR12 public1b21dc4; actualprovider requests/spend/send0, no allcurrentjobs/hostedCI/live/Neon/provider/human acceptance. ReleaseA/Neon-only/native send NOT_ACCEPTED.

Source parent:3dcb846a3df847acd1854d7e1d7e5e6917a83c0c. Source input hashes,
nonempty native discovery/freshJUnit and committed-source bridge bind this slice.
Roll back only admin consumer/schema/rate/contract/CI slice to3dcb846a, retaining
prior retained GET/native delivery/JWKS/exact admission and0050-compatible runtime
and schema. Keep actual selection/new send admission/dispatch closed; retain all
original UUID/FK/intent/ref/event/scope/history and full unknown holds. Existing
0047→48→49→50 migration/rollback payloads are unchanged/unapplied. No populated
downgrade, unknown resend, external rollback/promotion or supplier operation is
authorized by this local implementation/evidence.
