"""Strict machine protocol, separate from the staff API contract."""
from typing import Annotated, Literal
from uuid import UUID

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
