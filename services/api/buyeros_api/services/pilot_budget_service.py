"""USD10 shared pilot liability, manual proofs and native ledger deduplication."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.errors import ApiError
from ..api.lead_schemas import (
    LeadScope, PilotBudgetView, PilotCostInput, PilotCreditInput, PilotReconcileInput,
)
from ..db.budget import BudgetAccount, BudgetReservation, BudgetReservationAllocation, CostEvent
from ..db.icp import canonical_hash
from ..db.ingestion import OfferDocument
from ..db.lead_workflow import (
    PilotBudgetPolicy, PilotCostEvent, PilotCreditObservation, PilotReconciliation, LeadPrivatePayload,
)
from ..settings import get_settings
from .audit_service import append_audit
from .budget_service import ZERO, _period, _money, lock_budget_workspace
from .lead_evidence_service import require_permission, retained_payload, save_private_payload
from .lead_intent_service import LOCAL_CONFIGURATION_INTENT_DAYS
from datetime import timedelta


def money(value):
    return format(Decimal(value), ".6f")


def month_start(value):
    utc = value.astimezone(timezone.utc)
    if utc != utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0):
        raise ApiError(422, "INVALID_REQUEST", "UTC calendar month start required")
    return utc


async def _policy(session, scope, *, lock=False, create=False):
    query = select(PilotBudgetPolicy).where(
        PilotBudgetPolicy.workspace_id == scope.workspace_id, PilotBudgetPolicy.project_id == scope.project_id,
    )
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None and create:
        row = PilotBudgetPolicy(id=uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
                                monthly_limit=Decimal("10"), version=1, ledger_version=1)
        session.add(row)
        await session.flush()
    return row


async def _source_documents(session, scope, sources, now):
    documents = []
    for source in sources:
        if source.document_id:
            row = await session.scalar(select(OfferDocument).where(
                OfferDocument.workspace_id == scope.workspace_id, OfferDocument.project_id == scope.project_id,
                OfferDocument.id == source.document_id,
            ))
            if row is None:
                raise ApiError(404, "NOT_FOUND", "cost evidence document not found")
            if row.deleted_at is not None or row.retention_until is None or row.retention_until <= now:
                raise ApiError(403, "POLICY_BLOCKED", "cost evidence is no longer retained")
            documents.append(str(row.id))
    return documents


async def _store(session, scope, data, now):
    docs = await _source_documents(session, scope, data.source_refs, now)
    return await save_private_payload(session, scope, {
        "input": data.model_dump(mode="json"), "offer_document_ids": docs,
    }, now + timedelta(days=LOCAL_CONFIGURATION_INTENT_DAYS))


async def _native(session, workspace_id, project_id, start):
    project_accounts = select(BudgetAccount.id).where(
        BudgetAccount.workspace_id == workspace_id, BudgetAccount.scope == "project",
        BudgetAccount.scope_id == project_id, BudgetAccount.category == "all", BudgetAccount.currency == "USD",
        BudgetAccount.period_start <= start,
    )
    allocations = select(BudgetReservationAllocation.reservation_id).where(
        BudgetReservationAllocation.workspace_id == workspace_id,
        BudgetReservationAllocation.account_id.in_(project_accounts),
    )
    reservations = list((await session.scalars(select(BudgetReservation).where(
        BudgetReservation.workspace_id == workspace_id, BudgetReservation.id.in_(allocations),
        BudgetReservation.origin_period_start <= start, BudgetReservation.currency == "USD",
    ))).all())
    current = await session.scalar(select(BudgetAccount).where(
        BudgetAccount.workspace_id == workspace_id, BudgetAccount.scope == "project",
        BudgetAccount.scope_id == project_id, BudgetAccount.category == "all", BudgetAccount.currency == "USD",
        BudgetAccount.period_start == start,
    ))
    operations = {row.operation_id: row for row in reservations}
    events = list((await session.scalars(select(CostEvent).where(
        CostEvent.workspace_id == workspace_id, CostEvent.operation_id.in_(operations),
    ))).all()) if operations else []
    net = defaultdict(lambda: ZERO)
    for event in events:
        net[event.operation_id] += event.amount
    held = sum((row.remaining_hold for row in reservations), ZERO)
    carried = sum((row.remaining_hold for row in reservations if row.origin_period_start < start), ZERO)
    return current.settled_spend if current else ZERO, held, carried, operations, net


async def _snapshot(session, scope, now):
    start, end, _ = _period(now)
    policy = await _policy(session, scope)
    rows = list((await session.scalars(select(PilotCostEvent).where(
        PilotCostEvent.workspace_id == scope.workspace_id, PilotCostEvent.project_id == scope.project_id,
        PilotCostEvent.period_start <= start,
    ).order_by(PilotCostEvent.sequence))).all())
    latest = {}
    for row in rows:
        latest[row.economic_key_hash] = row
    credits = list((await session.scalars(select(PilotCreditObservation).where(
        PilotCreditObservation.workspace_id == scope.workspace_id,
        PilotCreditObservation.project_id == scope.project_id,
        PilotCreditObservation.period_start <= now, PilotCreditObservation.period_end > now,
        PilotCreditObservation.as_of <= now,
    ).order_by(PilotCreditObservation.as_of, PilotCreditObservation.id))).all())
    credit_latest = {}
    for row in credits:
        credit_latest[(row.provider, row.unit, row.period_start, row.period_end)] = row
    ledger_hash = canonical_hash({
        "events": sorted(str(row.id) for row in latest.values()),
        "credits": sorted(str(row.id) for row in credit_latest.values()),
    })
    native_settled, held, carried, operations, native_net = await _native(session, scope.workspace_id, scope.project_id, start)
    external_settled, external_hold, blockers = ZERO, ZERO, []
    for row in latest.values():
        _, proof = await retained_payload(session, scope, row.payload_id, now)
        data = proof.get("input", {}) if proof else {}
        if not data.get("fees_included") or not data.get("minimum_purchase_included"):
            blockers.append("complete_cost_evidence_required")
        if row.native_operation_id:
            operation = operations.get(row.native_operation_id)
            if operation is None or operation.origin_period_start != row.period_start:
                blockers.append("native_operation_scope_unverified")
            elif row.effective_state == "settled" and native_net[row.native_operation_id] == row.usd_amount:
                continue
            elif row.effective_state in {"committed", "unknown"} and row.usd_upper_bound is not None and operation.remaining_hold >= row.usd_upper_bound:
                continue
            else:
                blockers.append("native_cost_mismatch")
                # A contradictory copy is not a second economic charge.
                continue
        if row.effective_state == "settled":
            if row.usd_amount is None:
                blockers.append("unknown_cost_amount")
            elif row.period_start == start:
                external_settled += row.usd_amount
        else:
            if row.usd_upper_bound is None:
                blockers.append("unknown_cost_upper_bound")
            else:
                external_hold += row.usd_upper_bound
    reconciliation = await session.scalar(select(PilotReconciliation).where(
        PilotReconciliation.workspace_id == scope.workspace_id, PilotReconciliation.project_id == scope.project_id,
        PilotReconciliation.period_start == start,
    ).order_by(PilotReconciliation.created_at.desc(), PilotReconciliation.id.desc()).limit(1))
    status = "unknown"
    if reconciliation:
        _, evidence = await retained_payload(session, scope, reconciliation.payload_id, now)
        status = "reconciled" if (
            evidence is not None and reconciliation.shared_usage_known
            and reconciliation.ledger_hash == ledger_hash
            and policy is not None and reconciliation.ledger_version == policy.ledger_version
        ) else "stale"
    if status != "reconciled":
        blockers.append("external_usage_reconciliation_required")
    settled = native_settled + external_settled
    limit = policy.monthly_limit if policy else Decimal("10")
    committed = settled + held + external_hold
    remaining = max(ZERO, limit - committed) if not blockers else None
    settings = get_settings()
    mismatch = bool(settings.paid_admission_enabled or settings.delivery_admission_enabled
                    or settings.cloudflare_execution_enabled)
    if mismatch:
        blockers.append("pilot_activation_mismatch")
    return PilotBudgetView(
        id=policy.id if policy else None, workspace_id=scope.workspace_id, project_id=scope.project_id,
        version=policy.version if policy else 1, ledger_version=policy.ledger_version if policy else 1,
        ledger_hash=ledger_hash, limit=money(limit), settled_total=money(settled) if status == "reconciled" and not blockers else None,
        recorded_settled=money(settled), reserved_total=money(held), carried_reserved=money(carried),
        external_unsettled=money(external_hold) if not any("cost" in item for item in blockers) else None,
        remaining=money(remaining) if remaining is not None else None, currency="USD",
        period_start=start, period_end=end, reconciliation_status=status,
        activation="configuration_mismatch" if mismatch else "disabled",
        budget_state="unconfigured" if policy is None else "over_limit" if committed > limit
                     else "reconciliation_required" if blockers else "within_limit",
        last_reconciliation_id=reconciliation.id if reconciliation else None,
        credits=[{"provider": row.provider, "unit": row.unit, "period_start": row.period_start.isoformat(),
                  "period_end": row.period_end.isoformat(), "used": money(row.used) if row.used is not None else None,
                  "remaining": money(row.remaining) if row.remaining is not None else None,
                  "as_of": row.as_of.isoformat(), "provenance": "manual_observation"}
                 for row in credit_latest.values()],
        blockers=list(dict.fromkeys(blockers)), as_of=now,
    ).model_dump(mode="json")


async def project_pilot_budget(session: AsyncSession, *, scope: LeadScope, now: datetime):
    require_permission(scope, "listBudgets")
    return await _snapshot(session, scope, now)


async def set_pilot_policy(session, *, scope, data, expected_version, now):
    require_permission(scope, "updateBudget")
    await lock_budget_workspace(session, scope.workspace_id)
    row = await _policy(session, scope, lock=True, create=True)
    if row.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "pilot budget changed")
    row.monthly_limit = _money(Decimal(data.monthly_limit))
    row.version += 1
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="pilot.budget.policy_recorded", entity_type="pilot_budget", entity_id=row.id, reason=data.reason)
    await session.flush()
    return await _snapshot(session, scope, now)


async def validate_pilot_input(session, scope, action, data, now):
    require_permission(scope, "updateBudget")
    if hasattr(data, "source_refs"):
        await _source_documents(session, scope, data.source_refs, now)
    if hasattr(data, "period_start") and action != "credits.record":
        start = month_start(data.period_start)
        if start > _period(now)[0]:
            raise ApiError(422, "INVALID_REQUEST", "future accounting period is not accepted")
    if action == "credits.record" and data.as_of > now:
        raise ApiError(422, "INVALID_REQUEST", "future credit observation is not accepted")
    if action == "cost.record" and data.native_operation_id:
        _, _, _, operations, _ = await _native(session, scope.workspace_id, scope.project_id, _period(now)[0])
        row = operations.get(data.native_operation_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", "native budget operation not found")
        if row.origin_period_start != month_start(data.period_start):
            raise ApiError(422, "INVALID_REQUEST", "native charge keeps its original period")


async def _write_policy(session, scope, expected_version):
    require_permission(scope, "updateBudget")
    await lock_budget_workspace(session, scope.workspace_id)
    row = await _policy(session, scope, lock=True, create=True)
    if row.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "pilot budget changed")
    return row


async def record_pilot_cost(
    session: AsyncSession, *, scope: LeadScope, data: PilotCostInput, expected_version: int, now: datetime,
):
    policy = await _write_policy(session, scope, expected_version)
    await validate_pilot_input(session, scope, "cost.record", data, now)
    key_hash = canonical_hash(data.economic_charge_key)
    previous = await session.scalar(select(PilotCostEvent).where(
        PilotCostEvent.workspace_id == scope.workspace_id, PilotCostEvent.project_id == scope.project_id,
        PilotCostEvent.economic_key_hash == key_hash,
    ).order_by(PilotCostEvent.sequence.desc()).limit(1))
    if (previous is None and data.previous_event_id is not None) or (
        previous is not None and previous.id != data.previous_event_id
    ):
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "original charge event is required")
    if previous and (previous.period_start != month_start(data.period_start)
                     or previous.native_operation_id != data.native_operation_id):
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "charge identity and original period cannot change")
    if data.native_operation_id:
        other = await session.scalar(select(PilotCostEvent.id).where(
            PilotCostEvent.workspace_id == scope.workspace_id, PilotCostEvent.project_id == scope.project_id,
            PilotCostEvent.native_operation_id == data.native_operation_id,
            PilotCostEvent.economic_key_hash != key_hash,
        ).limit(1))
        if other:
            raise ApiError(409, "IDEMPOTENCY_CONFLICT", "native charge already has an economic identity")
    private = await _store(session, scope, data, now)
    row = PilotCostEvent(id=uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
        economic_key_hash=key_hash, sequence=previous.sequence + 1 if previous else 1,
        previous_event_id=previous.id if previous else None, native_operation_id=data.native_operation_id,
        period_start=month_start(data.period_start), state=data.state,
        effective_state=previous.effective_state if data.state == "corrected" and previous else data.state,
        usd_amount=Decimal(data.usd_amount) if data.usd_amount is not None else None,
        usd_upper_bound=Decimal(data.usd_upper_bound) if data.usd_upper_bound is not None else None,
        payload_id=private.id, recorded_by_user_id=scope.actor_id)
    session.add(row)
    policy.version += 1
    policy.ledger_version += 1
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="pilot.cost.recorded", entity_type="pilot_cost_event", entity_id=row.id, reason=data.reason)
    await session.flush()
    return {"id": str(row.id), "event_id": str(row.id), "version": row.sequence, "budget_version": policy.version}


async def record_credit_observation(
    session: AsyncSession, *, scope: LeadScope, data: PilotCreditInput, expected_version: int, now: datetime,
):
    policy = await _write_policy(session, scope, expected_version)
    await validate_pilot_input(session, scope, "credits.record", data, now)
    private = await _store(session, scope, data, now)
    row = PilotCreditObservation(id=uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
        provider=data.provider, unit=data.unit, period_start=data.period_start, period_end=data.period_end,
        used=Decimal(data.used) if data.used is not None else None,
        remaining=Decimal(data.remaining) if data.remaining is not None else None, as_of=data.as_of,
        payload_id=private.id, recorded_by_user_id=scope.actor_id)
    session.add(row)
    policy.version += 1
    policy.ledger_version += 1
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="pilot.credits.observed", entity_type="pilot_credit_observation", entity_id=row.id)
    await session.flush()
    return {"id": str(row.id), "event_id": str(row.id), "version": 1, "budget_version": policy.version}


async def reconcile_pilot_budget(
    session: AsyncSession, *, scope: LeadScope, data: PilotReconcileInput, expected_version: int, now: datetime,
):
    policy = await _write_policy(session, scope, expected_version)
    await validate_pilot_input(session, scope, "budget.reconcile", data, now)
    current = await _snapshot(session, scope, now)
    if (data.period_start != _period(now)[0] or data.coverage_start != data.period_start
            or not data.coverage_start <= data.coverage_end <= now
            or data.ledger_version != policy.ledger_version or data.ledger_hash != current["ledger_hash"]):
        raise ApiError(412, "STALE_REVISION", "current complete period and exact ledger required")
    private = await _store(session, scope, data, now)
    row = PilotReconciliation(id=uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
        period_start=data.period_start, ledger_version=policy.ledger_version, ledger_hash=data.ledger_hash,
        coverage_start=data.coverage_start, coverage_end=data.coverage_end, shared_usage_known=data.shared_usage_known,
        payload_id=private.id, recorded_by_user_id=scope.actor_id)
    session.add(row)
    policy.version += 1
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="pilot.budget.reconciled", entity_type="pilot_reconciliation", entity_id=row.id, reason=data.reason)
    await session.flush()
    return await _snapshot(session, scope, now)


async def assert_pilot_admission(
    session: AsyncSession, *, workspace_id: UUID, project_id: UUID, operation_id: UUID,
    upper_bound: Decimal, now: datetime,
) -> None:
    from .lead_schema import lead_schema_available
    if not await lead_schema_available(session):
        return
    scope = LeadScope(workspace_id, project_id, None, None, UUID(int=0), 0, frozenset())
    policy = await _policy(session, scope)
    if policy is None:
        return
    # Native workers can identify the pilot but cannot read private accounting
    # proofs or lead payloads. Pilot execution is disabled, so refuse admission
    # here while leaving projects with no pilot policy on their existing path.
    if not await session.scalar(text("SELECT pg_has_role(current_user,'buyeros_api','USAGE')")):
        raise ApiError(409, "POLICY_BLOCKED", "disabled pilot does not admit native worker operations")
    view = await _snapshot(session, scope, now)
    if view["remaining"] is None or view["activation"] != "disabled":
        raise ApiError(409, "POLICY_BLOCKED", "pilot accounting or disabled-mode configuration requires reconciliation")
    if Decimal(view["remaining"]) < upper_bound:
        raise ApiError(409, "BUDGET_LIMIT", "shared monthly pilot cap cannot cover operation")


async def list_pilot_cost_events(session, *, scope, offset, limit, now):
    require_permission(scope, "updateBudget")
    query = select(PilotCostEvent).where(
        PilotCostEvent.workspace_id == scope.workspace_id, PilotCostEvent.project_id == scope.project_id,
    )
    total = await session.scalar(select(func.count()).select_from(PilotCostEvent).where(
        PilotCostEvent.workspace_id == scope.workspace_id, PilotCostEvent.project_id == scope.project_id,
    ))
    rows = (await session.scalars(query.order_by(PilotCostEvent.created_at.desc(), PilotCostEvent.id)
                                 .offset(offset).limit(limit))).all()
    items = []
    for row in rows:
        _, proof = await retained_payload(session, scope, row.payload_id, now)
        items.append({"id": str(row.id), "sequence": row.sequence, "economic_key_hash": row.economic_key_hash,
            "previous_event_id": str(row.previous_event_id) if row.previous_event_id else None,
            "native_operation_id": str(row.native_operation_id) if row.native_operation_id else None,
            "period_start": row.period_start.isoformat(), "state": row.state, "effective_state": row.effective_state,
            "usd_amount": money(row.usd_amount) if row.usd_amount is not None else None,
            "usd_upper_bound": money(row.usd_upper_bound) if row.usd_upper_bound is not None else None,
            "source": proof.get("input") if proof else None, "redacted": proof is None,
            "recorded_by_user_id": str(row.recorded_by_user_id), "created_at": row.created_at.isoformat()})
    return {"items": items, "offset": offset, "limit": limit, "total": total}
