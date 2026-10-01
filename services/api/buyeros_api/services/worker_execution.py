"""Database arbitration for bounded execution; PG is the durable authority."""
import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from buyeros_api.api.errors import ApiError
from buyeros_api.api.worker_schemas import JobEnvelope, StepOutcome, ClaimBatch, MaintenanceResult
from buyeros_api.db.outbox import OutboxEvent, TERMINAL_STATES
from buyeros_api.db.session import tenant_session
from buyeros_api.db.worker_execution import WorkerRuntimeControl, WorkerStep
from buyeros_api.execution.engine import async_database_url
from buyeros_api.settings import get_settings

WORKER_ROLE_CATALOG_SQL = (
    "SELECT NOT rolsuper AND NOT rolbypassrls AND pg_has_role(current_user,'buyeros_worker','MEMBER') "
    "AND NOT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
    "WHERE n.nspname IN ('public','buyeros_graph') AND c.relkind IN ('r','p') "
    "AND c.relowner=pg_roles.oid) "
    "AND NOT EXISTS(SELECT 1 FROM pg_namespace n WHERE n.nspname IN ('public','buyeros_graph') "
    "AND n.nspowner=pg_roles.oid) FROM pg_roles WHERE rolname=current_user"
)


def create_execution_engine():
    dsn = get_settings().execution_database_url
    if dsn is None:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "worker runtime is not configured")
    return create_async_engine(async_database_url(dsn), pool_size=2, max_overflow=0, pool_pre_ping=True)


async def consume_machine_nonce(engine, principal, now: datetime) -> None:
    """Catalog proof and committed replay guard before any customer query."""
    async with engine.begin() as connection:
        role = (await connection.execute(text(WORKER_ROLE_CATALOG_SQL))).scalar_one()
        if not role:
            raise ApiError(503, "SERVICE_UNAVAILABLE", "worker role catalog proof failed")
        row = (await connection.execute(text(
            "INSERT INTO worker_bridge_nonces(key_id,nonce,expires_at) VALUES(:key,:nonce,:expires) "
            "ON CONFLICT DO NOTHING RETURNING nonce"
        ), {"key": principal.key_id, "nonce": principal.nonce, "expires": now + timedelta(seconds=120)})).first()
        if row is None:
            raise ApiError(409, "CONFLICT", "worker nonce already consumed")
        await connection.execute(text(
            "DELETE FROM worker_bridge_nonces WHERE (key_id,nonce) IN "
            "(SELECT key_id,nonce FROM worker_bridge_nonces WHERE expires_at<:now LIMIT 1000)"
        ), {"now": now})


def outcome(state: str, code: str, *, step_key: str | None = None, retry_at=None) -> StepOutcome:
    return StepOutcome(state=state, code=code, next_step_key=step_key, retry_at=retry_at)


@dataclass(frozen=True)
class StepClaim:
    state: str
    owner: uuid.UUID | None = None
    expires_at: datetime | None = None
    outcome: StepOutcome | None = None


async def control_row(session, *, lock: bool = False):
    query = select(WorkerRuntimeControl).where(WorkerRuntimeControl.singleton == 1)
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one()


async def legacy_runtime_control(session):
    from buyeros_api.execution.config import get_settings as worker_settings
    if not worker_settings().celery_execution_enabled:
        return None
    control = await control_row(session, lock=True)
    return control if control.backend == "celery" and control.enabled else None


def selected(control, envelope: JobEnvelope, row: OutboxEvent) -> bool:
    return (control.backend == "cloudflare" and control.epoch == envelope.runtime_epoch
            and row.runtime_backend == "cloudflare" and row.runtime_epoch == envelope.runtime_epoch
            and row.fencing_generation == envelope.generation)


async def claim_execution_step(session, envelope: JobEnvelope, step_key: str, now: datetime) -> StepClaim:
    # Every caller takes the singleton first; no outbox→control lock inversion.
    control = await control_row(session, lock=True)
    row = (await session.execute(select(OutboxEvent).where(
        OutboxEvent.id == envelope.outbox_id).with_for_update())).scalar_one_or_none()
    if row is None or not selected(control, envelope, row):
        return StepClaim("stale", outcome=outcome("stale", "STALE_FENCE"))
    receipt = (await session.execute(select(WorkerStep).where(
        WorkerStep.outbox_id == row.id, WorkerStep.generation == envelope.generation,
        WorkerStep.step_key == step_key))).scalar_one_or_none()
    if receipt is not None and receipt.state != "running":
        return StepClaim("cached", outcome=StepOutcome.model_validate(receipt.outcome))
    if row.state in TERMINAL_STATES:
        return StepClaim("cached", outcome=outcome("done", "OK") if row.state == "done"
                         else outcome("blocked", "STEP_FAILED"))
    if not control.enabled or not get_settings().cloudflare_execution_enabled:
        return StepClaim("cached", outcome=outcome("blocked", "EXECUTION_DISABLED"))
    if row.state != "dispatched":
        return StepClaim("stale", outcome=outcome("stale", "STALE_FENCE"))
    if receipt is None and step_key != "start":
        predecessor = (await session.execute(select(WorkerStep.id).where(
            WorkerStep.outbox_id == row.id, WorkerStep.generation == envelope.generation,
            WorkerStep.runtime_epoch == envelope.runtime_epoch, WorkerStep.state != "running",
            WorkerStep.outcome["next_step_key"].astext == step_key).limit(1))).first()
        if predecessor is None:
            return StepClaim("stale", outcome=outcome("blocked", "INVALID_INTENT"))
    if receipt is not None:
        # Lease expiry never means a potentially accepted operation is safe to
        # repeat. Recovery must inspect permanent business/provider state.
        result = (outcome("reconcile", "PROVIDER_UNKNOWN", step_key="reconcile", retry_at=now + timedelta(seconds=5))
                  if receipt.expires_at <= now else
                  outcome("retry_later", "IN_PROGRESS", step_key=step_key, retry_at=now + timedelta(seconds=2)))
        return StepClaim("busy", expires_at=receipt.expires_at, outcome=result)
    if control.active_owner is not None and control.active_until > now:
        return StepClaim("busy", outcome=outcome("retry_later", "IN_PROGRESS", step_key=step_key,
                                               retry_at=now + timedelta(seconds=2)))
    count = (await session.execute(select(func.count()).select_from(WorkerStep).where(
        WorkerStep.outbox_id == row.id))).scalar_one()
    if count >= 512:
        return StepClaim("cached", outcome=outcome("blocked", "LIMIT_EXCEEDED"))
    owner, expires = uuid.uuid4(), now + timedelta(seconds=120)
    control.active_owner, control.active_until = owner, expires
    session.add(WorkerStep(workspace_id=envelope.workspace_id, outbox_id=row.id,
                           generation=envelope.generation, step_key=step_key, runtime_epoch=envelope.runtime_epoch,
                           owner=owner, expires_at=expires, state="running", attempts=1))
    row.lease_owner, row.lease_expires_at = str(owner), expires
    await session.flush()
    return StepClaim("claimed", owner=owner, expires_at=expires)


async def _owned_step(session, envelope, step_key, owner):
    control = await control_row(session, lock=True)
    row = (await session.execute(select(OutboxEvent).where(
        OutboxEvent.id == envelope.outbox_id).with_for_update())).scalar_one_or_none()
    receipt = (await session.execute(select(WorkerStep).where(
        WorkerStep.outbox_id == envelope.outbox_id, WorkerStep.generation == envelope.generation,
        WorkerStep.step_key == step_key).with_for_update())).scalar_one_or_none()
    valid = (row is not None and selected(control, envelope, row) and receipt is not None
             and receipt.owner == owner and receipt.state == "running" and control.active_owner == owner)
    return control, row, receipt, valid


def finish_receipt(control, receipt, result: StepOutcome):
    receipt.state = "done" if result.state in {"done", "continue", "retry_later"} else ("reconcile" if result.state == "reconcile" else "blocked")
    receipt.outcome = result.model_dump(mode="json")
    if len(json_bytes(receipt.outcome)) > 2048:
        raise ValueError("worker outcome exceeds safe state bound")
    control.active_owner = control.active_until = None


def json_bytes(value) -> bytes:
    import json
    return json.dumps(value, separators=(",", ":")).encode()


async def execute_step(engine, envelope: JobEnvelope, step_key: str, *, timeout_seconds: float = 60,
                       adapter=None, checkpoint_dsn=None, environment="production") -> StepOutcome:
    # Cloudflare selects only a key supplied by the server. One local outbox is
    # one unit; bulk creates its next 50-row outbox in the same transaction.
    now = datetime.now(timezone.utc)
    async with tenant_session(engine, envelope.workspace_id) as session:
        claim = await claim_execution_step(session, envelope, step_key, now)
    if claim.state != "claimed":
        return claim.outcome

    try:
        from buyeros_api.execution.step_runner import execute_claimed
        return await asyncio.wait_for(execute_claimed(engine, envelope, step_key, claim.owner,
            adapter=adapter, checkpoint_dsn=checkpoint_dsn, environment=environment), timeout=min(60, timeout_seconds))
    except Exception:
        # Do not swallow failure as success or release any financial hold. DB-only
        # work rolled back; this inspectable receipt must be explicitly recovered.
        async with tenant_session(engine, envelope.workspace_id) as session:
            control, row, receipt, valid = await _owned_step(session, envelope, step_key, claim.owner)
            if not valid:
                return outcome("stale", "STALE_FENCE")
            from buyeros_api.execution.provider_context import terminal_business_outcome
            result = await terminal_business_outcome(session, row, include_running=True)
            result = result or outcome("blocked", "STEP_FAILED")
            finish_receipt(control, receipt, result)
        return result


async def read_step_status(engine, envelope: JobEnvelope, step_key: str) -> StepOutcome:
    async with tenant_session(engine, envelope.workspace_id) as session:
        control = await control_row(session, lock=True)
        row = (await session.execute(select(OutboxEvent).where(OutboxEvent.id == envelope.outbox_id).with_for_update())).scalar_one_or_none()
        if row is None or not selected(control, envelope, row):
            return outcome("stale", "STALE_FENCE")
        if row.state == "dispatched":
            # Safe permit waits must not let the dispatcher supersede a live
            # current Workflow solely because another job owns the step slot.
            row.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=120)
        receipt = (await session.execute(select(WorkerStep).where(
            WorkerStep.outbox_id == row.id, WorkerStep.generation == envelope.generation,
            WorkerStep.step_key == step_key))).scalar_one_or_none()
        if receipt is not None and receipt.outcome is not None:
            return StepOutcome.model_validate(receipt.outcome)
        if row.state in TERMINAL_STATES:
            return outcome("done", "OK") if row.state == "done" else outcome("blocked", "STEP_FAILED")
        now = datetime.now(timezone.utc)
        if receipt is not None and receipt.expires_at <= now:
            return outcome("reconcile", "PROVIDER_UNKNOWN", step_key="reconcile", retry_at=now + timedelta(seconds=5))
        return outcome("retry_later", "IN_PROGRESS", step_key=step_key, retry_at=now + timedelta(seconds=2))


async def record_publication(engine, envelope, state: str) -> StepOutcome:
    async with tenant_session(engine, envelope.workspace_id) as session:
        control = await control_row(session, lock=True)
        row = (await session.execute(select(OutboxEvent).where(
            OutboxEvent.id == envelope.outbox_id).with_for_update())).scalar_one_or_none()
        if row is None or not selected(control, envelope, row):
            return outcome("stale", "STALE_FENCE")
        if state == "failed" and row.state == "dispatched":
            has_step = (await session.execute(select(WorkerStep.id).where(WorkerStep.outbox_id == row.id).limit(1))).first()
            if has_step is None:
                row.state, row.lease_owner, row.lease_expires_at = "ready", None, None
        # Ambiguous publication retains the lease; no financial settlement.
        return outcome("done", "OK")


async def maintenance(engine, runtime_epoch: int) -> MaintenanceResult:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        control = await control_row(session)
        return MaintenanceResult(runtime_epoch=control.epoch, recovered=0,
                                 enabled=control.enabled and control.backend == "cloudflare"
                                 and control.epoch == runtime_epoch and get_settings().cloudflare_execution_enabled)
