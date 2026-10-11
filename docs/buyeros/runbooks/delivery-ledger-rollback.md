# C61-20 delivery ledger deployment/rollback payload

Prepared local artifact only; no production SQL, account activation, send or deployment performed. Historical0048 foundation expand is `0047_c61_legacy_source_privacy`→`0048_c61_delivery_ledger`; rendered transactional SQL is `artifacts/c61/C61-20-delivery-ledger-expand.sql`. Verify actual target head before any separately authorized application. Never execute it against a guessed branch or production fixture.

## Expand and compatibility

Create independent metadata tables/tenant composite FKs/indexes/guards, FORCE RLS, narrow API/worker grants; retain existing User UUIDs and existing parent FK values. Existing search/model/contact writable predicates move from exact0047 to exact0048 while retaining privacy behavior and ACLs. Public delivery gate remains403 and no outbox delivery event is admitted or dispatched by this phase. Do not add an unregistered delivery event to the generic unpaid selector. Generic delivery cannot use contact tariffs or Service enum to evade liability checks.

## Read-only inventory before rollback

Capture the actual candidate API/worker/selector/epoch, schema version and exact scoped ledger counts/state/refs. Under the migration owner only for authorized readback, inspect:

```sql
SELECT version_num FROM alembic_version;
SELECT workspace_id,state,count(*) FROM delivery_messages GROUP BY workspace_id,state;
SELECT count(*) FROM delivery_events;
SELECT l.workspace_id,l.message_id,l.operation_id,l.reservation_id,l.max_liability,b.remaining_hold,b.state
FROM delivery_liabilities l JOIN budget_reservations b ON b.workspace_id=l.workspace_id AND b.id=l.reservation_id;
```

Store redacted metadata without sender/recipient addresses, tokens or message body. Runtime reads must keep normal tenant context and non-BYPASS roles.

## Application rollback with populated history

Disable only new delivery admission (currently already closed). Retain0048, accepted/submitting/unknown message state, original provider/account/reference, unique intents/events, current reservations/full unknown hold and immutable canonical refs. Keep the reviewed API artifact identified by `C61-20-delivery-ledger-committed-source.json` (once committed), or a later artifact proven on retained0048. Earlier core `a7e17c4ae28c68f8e80624bf2b2d01a69eb1d374` refuses0048 at its runtime-selector guard and is not an established rollback target. Any older compatible rollback archive must receive a separate exact-source rehearsal; promotion requires its reviewed payload and actual authorization. Existing research/export and privacy guards must still pass on the retained schema. Do not resubmit accepted/unknown, invent a new key, infer not-found=nonacceptance, or release liability without economic evidence. Before real delivery activation, complete the status/callback reconciliation service so it continues even with new admission off.

## Empty schema rollback only

Alembic0048 downgrade first checks all three tables are empty; any history raises `retain delivery history and liabilities` and leaves the transaction/head unchanged. Only an entirely empty owned rehearsal may drop the new tables/functions and restore exact0047 receipt predicates. Required DB tests verify refusal with unknown state, exact UUID/approval/actor refs and remaining0.010000 hold, then separate empty downgrade/reupgrade. No production destructive rollback is authorized by these fixture tests. Never delete rows to make the downgrade gate pass.

## Open delivery gates

Schema constraints are the local foundation. Actual idempotent admission/economic allocation, frozen independent capability/account/tariff, worker policy recheck/durable submit claim, signed callback dedup/suppression/status-only reconciliation and genuine authorized sandbox receipt remain pending. Default403 stays effective. Release A, Neon-only and native-send acceptance remain independent and NOT_ACCEPTED.


## Current0049 precision expansion and rollback retention

The current local candidate adds0049_c61_delivery_money. Existing0048 is immutable. Its separate offline payload artifacts/c61/C61-20-delivery-money-expand.sql expands only max_liability fromNumeric18,6 toNumeric20,6 to match original reservations, then updates the same three receipt writable head predicates toexact49. Runtime selector accepts only the reviewed exact49 alongside prior reviewed heads; arbitraryschema/epoch/drain checks remain. Verify actual target head before any authorized SQL: the48→49 range cannot replace an unknown remote migration inventory.

Retain49 on application rollback with any liability history. The downgrade refuses any liability row without touching canonical IDs/FKs, provider references, amounts or unknown holds; do not delete rows to bypass it. Empty owned rehearsal can downgrade49→48, and only when all0048 ledger history is empty can the earlier48→47 drop execute. Neither is a production rollback authorization. Earlier0048-only runtime artifacts refuse49 and are not proven compatible rollback targets. Retain the current reviewed49-compatible artifact, close newadmission and continue original accepted/unknown reconciliation. Any oldercompatible artifact needs a separate exact-source retained49 rehearsal before promotion. All public delivery routes remain403; no external send or provider quota used.


## C61-20 native runner local validation

C61-20 local native orchestration now binds the immutable server-resolved approved payload to a reviewed private delivery factory and positive exact Money estimate within the original0050 authorization/hold. Initial claim commits/closes, a fresh current policy/approval/recipient/role/runtime-fence transaction commits a permanent unknown POST permit, then one adapter submit awaits outside all tenant transactions. A separate retained-authority transaction records a typed original response without needing new admission/role/lease permissions. Provider errors, malformed responses, unknown/rejection, cancellation and receipt-commit failure retain uncertainty and the full original hold; none creates another POST/key/ref/liability or releases money. Twelve concurrent real owned-worker calls produce one original submission/receipt. The actual native execute_claimed and fresh execute_step entrypoint now enter the separate delivery runner after closing the initial runtime guard; final receipts remain reconcile/PROVIDER_UNKNOWN, never delivered/settled/done. Received acceptance survives late lease failure; the worker returns stale without losing the original provider reference. Default selected_delivery_runtime remainsNone, public deliver remains403, common contact/search/model adapters cannot activate delivery, and the prior closed registered handler behavior is retained. Focused37 expected missing-runner assertionRED then37GREEN; actual native8 RED5F3P then current45GREEN, each zero errors/skips. Related9-module382P and graph-selected11 native caller modules128P and independent worker routing4P each0F/E/S with exact nonempty native collection=freshJUnit;45 overlaps382 and counts are not summed. CI adds one API step requiring45 unique cases/all18 named families and exact freshJUnit;2positive/6negative native guard probes pass; every previous API step and all other jobs unchanged. Generated types/operation-route checks exit0,89operations unchanged. Helper count/indent/name lookup failures and initial unspawned pnpm checks are invalid setup, retained separately, never product RED/pass. No schema/migration/RLS/JWT/UUID/FK changes; existing0050 migration/rollback guards remain. LOCAL_ONLY; not a full current all-jobs/hostedCI/build/provider/Neon/production/human acceptance. Actual factory/account/sender/HTTP transport, status reconciliation/economic settlement/public admission/UI and independent C61-30 remain pending. ReleaseA,Neon-only,native send NOT_ACCEPTED.

Unused runner/CI slice rollback:8806a95; retain0050-compatible runtime/schema, closed actual selection/admission/dispatch, exact UUID/FK/intent/ref/event/scope/history and full unknown holds. No remote action authorized.
