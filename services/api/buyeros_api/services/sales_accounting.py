"""Operator-attested supplier bills, never token estimates or content receipts."""
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid5
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.models import Membership
from ..db.sales_execution import SalesExecution, SalesStep
from ..db.sales_accounting import SalesFinancialEvidence, SalesAccountingReceipt
from ..db.session import tenant_session
from ..sales.context import digest


class FinancialObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    step_id: UUID
    claim_id: UUID
    request_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    account_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    evidence_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    resolution: Literal['billed', 'not_billed']
    amount: Decimal = Field(ge=0, max_digits=20, decimal_places=6, allow_inf_nan=False)
    currency: Literal['USD']
    pricing_version: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_.:-]+$')

    @model_validator(mode='after')
    def money(self):
        if self.resolution == 'not_billed' and self.amount != 0:
            raise ValueError('not billed evidence cannot contain a charge')
        return self


async def operator(session, scope):
    # No token roles or possession of a receipt grants accounting authority.
    row = await session.scalar(select(Membership).where(Membership.workspace_id == scope.workspace_id,
        Membership.user_id == scope.actor_id, Membership.active.is_(True)).with_for_update()
        .execution_options(populate_existing=True))
    if row is None or 'workspace_admin' not in row.roles:
        raise ApiError(404, 'NOT_FOUND', 'accounting authority unavailable')


async def locked_parent(session, scope, execution_id):
    from ..execution.sales_tasks import lock_authority, children, parent_reservation
    from ..db.conversation_threads import ConversationThread
    await lock_authority(session, scope.workspace_id)
    await operator(session, scope)
    parent = await session.scalar(select(SalesExecution).where(SalesExecution.id == execution_id,
        SalesExecution.workspace_id == scope.workspace_id, SalesExecution.project_id == scope.project_id))
    if parent is None:
        raise ApiError(404, 'NOT_FOUND', 'accounting parent unavailable')
    # Accounting operators need not read a private transcript to settle its bill.
    await session.execute(select(ConversationThread.id).where(ConversationThread.id == parent.thread_id,
        ConversationThread.workspace_id == scope.workspace_id).with_for_update())
    parent = await session.scalar(select(SalesExecution).where(SalesExecution.id == execution_id,
        SalesExecution.workspace_id == scope.workspace_id).with_for_update().execution_options(populate_existing=True))
    steps = await children(session, parent)
    hold = await parent_reservation(session, parent)
    if (hold.operation_id, hold.currency, hold.upper_bound) != (parent.id, 'USD', parent.upper_bound):
        raise ValueError('foreign reservation')
    return parent, steps, hold


def validate_observation(parent, step, hold, observation):
    if (step is None or observation.claim_id != step.claim_id or step.definitely_unsubmitted
        or observation.account_hash != parent.provider_account_hash
        or observation.pricing_version != hold.price_version or observation.amount > step.liability
        or step.state not in {'received', 'unknown', 'submitting'}):
        raise ApiError(409, 'INVALID_EVIDENCE', 'financial evidence does not bind the exact admitted claim')
    if step.usage and observation.request_hash != digest(step.usage['provider_ref']):
        raise ApiError(409, 'INVALID_EVIDENCE', 'supplier request differs from received claim')


async def record_evidence(session, scope, execution_id, observation, *, key):
    """Trusted operational entry: operator attests an exact provider-account bill.

    The body is a closed financial schema. A hash names the privately verified
    supplier observation, never an access-bearing URL, response or token count.
    Unknown calls are omitted until authoritative financial evidence is available.
    """
    observation = FinancialObservation.model_validate(observation)
    if not isinstance(key, str) or not 1 <= len(key) <= 200:
        raise ValueError('stable evidence key required')
    parent, steps, hold = await locked_parent(session, scope, execution_id)
    step = next((s for s in steps if s.id == observation.step_id), None)
    validate_observation(parent, step, hold, observation)
    payload = observation.model_dump(mode='json')
    fingerprint = digest(payload)
    identity = uuid5(scope.actor_id, f'sales-bill:{execution_id}:{key}')
    keyed = await session.get(SalesFinancialEvidence, identity)
    if keyed:
        if keyed.fingerprint != fingerprint:
            raise ApiError(409,'IDEMPOTENCY_CONFLICT','evidence key already used')
        return keyed.id
    previous = await session.scalar(select(SalesFinancialEvidence).where(
        SalesFinancialEvidence.workspace_id == scope.workspace_id,
        SalesFinancialEvidence.execution_id == execution_id,
        SalesFinancialEvidence.step_id == observation.step_id))
    if previous:
        raise ApiError(409, 'IDEMPOTENCY_CONFLICT', 'child already has a financial resolution; replay its stable key')
    row = SalesFinancialEvidence(id=identity, workspace_id=scope.workspace_id, execution_id=execution_id,
        step_id=observation.step_id, actor_id=scope.actor_id, fingerprint=fingerprint, observation=payload)
    session.add(row)
    await session.flush()
    return identity


class ParentAccountingOwner:
    async def reconcile_parent(self, engine, *, scope, execution_id, evidence_ids, expected_revision, key):
        if (not isinstance(key, str) or not 1 <= len(key) <= 200 or type(expected_revision) is not int
            or expected_revision < 0 or len(evidence_ids) > 8 or len(set(evidence_ids)) != len(evidence_ids)):
            raise ValueError('bounded evidence, revision and stable mutation key required')
        async with tenant_session(engine, scope.workspace_id) as session:
            parent, steps, hold = await locked_parent(session, scope, execution_id)
            identity = uuid5(scope.actor_id, f'sales-accounting:{execution_id}:{key}')
            fingerprint = digest({'evidence': sorted(map(str, evidence_ids)), 'revision': expected_revision})
            previous = await session.get(SalesAccountingReceipt, identity)
            if previous:
                if previous.fingerprint != fingerprint:
                    raise ApiError(409, 'IDEMPOTENCY_CONFLICT', 'accounting key differs')
                return previous.id
            if parent.accounting_revision != expected_revision:
                raise ApiError(409, 'STALE_REVISION', 'accounting revision changed')
            rows = list((await session.scalars(select(SalesFinancialEvidence).where(
                SalesFinancialEvidence.workspace_id == scope.workspace_id,
                SalesFinancialEvidence.execution_id == execution_id,
                SalesFinancialEvidence.id.in_(evidence_ids)))).all())
            if len(rows) != len(evidence_ids):
                raise ApiError(404, 'NOT_FOUND', 'financial evidence unavailable')
            prior = list((await session.scalars(select(SalesAccountingReceipt).where(
                SalesAccountingReceipt.workspace_id == scope.workspace_id,
                SalesAccountingReceipt.execution_id == execution_id))).all())
            used = {UUID(i) for r in prior for i in r.evidence_ids}
            if used.intersection(evidence_ids):
                raise ApiError(409, 'IDEMPOTENCY_CONFLICT', 'evidence already settled')
            actual = Decimal(0)
            bound = Decimal(0)
            for evidence in rows:
                observation = FinancialObservation.model_validate(evidence.observation)
                step = next((s for s in steps if s.id == evidence.step_id), None)
                validate_observation(parent, step, hold, observation)
                actual += observation.amount
                bound += step.liability
            # Locally proven unused terminal children need no supplier bill.
            # Their IDs are included in the receipt to prevent a second release.
            unused = [s for s in steps if s.id not in used and s.state in {'failed','cancelled'}
                and (s.claim_id is None or s.definitely_unsubmitted) and not s.usage and not s.result_digest]
            if not parent.unused_released:
                bound += sum((s.liability for s in unused), Decimal(0))
            if bound == 0 and (not parent.unused_released or prior):
                raise ApiError(409, 'INVALID_EVIDENCE', 'no newly known liability')
            from .settlement import settle_known_portion
            event_id = None
            if not parent.unused_released:
                if hold.remaining_hold != parent.upper_bound-parent.accounted_bound:
                    raise ValueError('unresolved hold mismatch')
                event_id = await settle_known_portion(session, parent.id, actual, bound, f'sales:{identity}')
                parent.accounted_bound += bound
                parent.settled_usd += actual
            parent.accounting_revision += 1
            session.add(SalesAccountingReceipt(id=identity, workspace_id=scope.workspace_id,
                execution_id=parent.id, reservation_id=hold.id, actor_id=scope.actor_id,
                revision=parent.accounting_revision, fingerprint=fingerprint,
                evidence_ids=list(map(str, evidence_ids))+[str(s.id) for s in unused],
                settled_usd=parent.settled_usd, remaining_hold=hold.remaining_hold, cost_event_id=event_id))
            await session.flush()
            return identity


ACCOUNTING_OWNER = ParentAccountingOwner()
