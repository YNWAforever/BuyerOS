"""Strict machine protocol, separate from the staff API contract."""
from typing import Annotated, Literal
from uuid import UUID
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field, field_validator

SafePositiveInt = Annotated[int, Field(strict=True, ge=1, le=9007199254740991)]


class WorkerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobEnvelope(WorkerModel):
    v: Literal[1]
    workspace_id: UUID
    outbox_id: UUID
    generation: SafePositiveInt
    runtime_epoch: SafePositiveInt

    @field_validator("v", mode="before")
    @classmethod
    def version_must_be_integer(cls, value):
        if type(value) is not int:
            raise ValueError("protocol version must be an integer")
        return value


class ClaimBatch(WorkerModel):
    items: list[JobEnvelope] = Field(max_length=10)
    next_cursor: UUID | None
    runtime_epoch: SafePositiveInt


class ClaimRequest(WorkerModel):
    runtime_epoch: SafePositiveInt
    max_total: Annotated[int, Field(strict=True, ge=1, le=10)] = 10
    time_budget_seconds: Annotated[int, Field(strict=True, ge=1, le=10)] = 10


StepKey = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9:_-]{0,63}$", max_length=64)]


class StepRequest(WorkerModel):
    envelope: JobEnvelope
    step_key: StepKey


class StepOutcome(WorkerModel):
    state: Literal["done", "continue", "retry_later", "reconcile", "blocked", "stale"]
    code: Literal["OK", "EXECUTION_DISABLED", "CAPABILITY_UNAVAILABLE", "POLICY_CHANGED",
                  "ACTOR_CHANGED", "INVALID_INTENT", "STALE_FENCE", "IN_PROGRESS",
                  "TRANSIENT_UNAVAILABLE", "PROVIDER_UNKNOWN", "LIMIT_EXCEEDED", "STEP_FAILED"]
    next_step_key: StepKey | None
    retry_at: datetime | None

    @field_validator("retry_at")
    @classmethod
    def utc_retry_time(cls, value):
        if value is not None and (value.utcoffset() is None or value.utcoffset() != timedelta(0)):
            raise ValueError("retry_at must use UTC")
        return value


class PublicationRequest(WorkerModel):
    envelope: JobEnvelope
    state: Literal["published", "unknown", "failed"]


class MaintenanceRequest(WorkerModel):
    runtime_epoch: SafePositiveInt


class MaintenanceResult(WorkerModel):
    runtime_epoch: SafePositiveInt
    recovered: Annotated[int, Field(strict=True, ge=0, le=10)]
    enabled: bool
