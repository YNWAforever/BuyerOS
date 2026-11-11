"""Bounded conversation-turn contracts: request, typed parts, decisions.

These shapes are the shared interface for the persisted thread transcript. They
carry no authority: tenant identity, permissions, approvals and budget are always
resolved server-side from the authenticated scope. Every value here is untrusted
data that is validated before it can be persisted or returned.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (AwareDatetime, BaseModel, ConfigDict, Field, JsonValue,
    StrictBool, StrictInt, StringConstraints, field_validator)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]
Language = Literal["en", "zh-HK"]
TemplateId = Literal["first-project", "understand-documents", "research-market",
    "review-buyers", "check-company", "prepare-follow-up", "custom"]
TurnStatus = Literal["completed", "needs_input", "needs_approval", "failed",
    "outcome_unknown", "cancelled"]
ActivityState = Literal["proposed", "approved", "running", "completed", "failed",
    "skipped", "outcome_unknown"]
OutputKind = Literal["profile_proposal", "research_report", "qualification_assessment",
    "enrichment_proposal", "competitive_document", "outreach_preparation",
    "followup_preparation", "meeting_brief", "sales_proposal", "objection_playbook",
    "pipeline_report", "report_export", "project_setup", "document_understanding",
    "buyer_review"]
# Bounded plan: one grounded answer plus at most two reviewed steps for one turn.
MAX_TURN_STEPS = 3
MAX_MESSAGE_PARTS = 24


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class TextPart(Contract):
    kind: Literal["text"] = "text"
    text: Text
    language: Language


class CitationItem(Contract):
    id: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    label: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    kind: Literal["document", "fact", "drive", "run", "results", "buyer"]
    href: Annotated[str, StringConstraints(pattern=r"^/[A-Za-z0-9/_.?:=&%-]{1,240}$")] | None = None


class CitationsPart(Contract):
    kind: Literal["citations"] = "citations"
    items: Annotated[tuple[CitationItem, ...], Field(min_length=1, max_length=20)]


class ToolActivityPart(Contract):
    kind: Literal["tool_activity"] = "tool_activity"
    call_id: UUID
    capability: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.]{2,63}$")]
    title: ShortText
    state: ActivityState
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    summary: Annotated[str, StringConstraints(max_length=500)] | None = None
    error_code: Code | None = None


class ProposalCost(Contract):
    kind: Literal["nonbillable", "provider_credits"]
    amount: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
    unit: Literal["USD", "credits"]
    may_incur_provider_charges: StrictBool = False
    # False means the reviewed tariff is not available yet; never invent USD.
    known: StrictBool = True


class ProposalPart(Contract):
    kind: Literal["proposal"] = "proposal"
    proposal_id: UUID
    capability: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_.]{2,63}$")]
    title: ShortText
    rationale: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    arguments_preview: dict[str, JsonValue] = Field(max_length=16)
    cost: ProposalCost | None = None
    requires_approval: Literal[True] = True


class OutputRef(Contract):
    output_id: UUID
    kind: OutputKind
    # Authored revision; never a client-supplied identifier.
    revision: StrictInt = Field(ge=1)
    status: Literal["available", "needs_review", "unavailable"]


class OutputLinkPart(Contract):
    kind: Literal["output_link"] = "output_link"
    output: OutputRef
    title: ShortText
    href: Annotated[str, StringConstraints(pattern=r"^/[A-Za-z0-9/_.?:=&%-]{1,240}$")] | None = None


class Recovery(Contract):
    label: ShortText
    href: Annotated[str, StringConstraints(pattern=r"^/[A-Za-z0-9/_.?:=&%-]{1,240}$")] | None = None


class NoticePart(Contract):
    kind: Literal["notice"] = "notice"
    code: Code
    message: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    recovery: Recovery | None = None


TurnPart = Annotated[
    TextPart | CitationsPart | ToolActivityPart | ProposalPart | OutputLinkPart | NoticePart,
    Field(discriminator="kind"),
]


class TurnNotice(Contract):
    code: Code
    message: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    recovery: Recovery | None = None


class TurnRequest(Contract):
    # ``thread_id`` is optional: a turn-first request creates the thread and the
    # first user message in the same transaction (Amendment A1).
    thread_id: UUID | None = None
    client_message_id: UUID
    expected_thread_version: Annotated[StrictInt, Field(ge=1)] | None = None
    language: Language
    text: Text
    skill_id: ShortText | None = None
    template_id: TemplateId | None = None
    # Only honoured when this request creates the thread (Amendment A1 path).
    buyer_id: UUID | None = None

    @field_validator("text")
    @classmethod
    def device_text_bound(cls, value):
        if "\x00" in value or len(value.encode("utf-16-le")) > 8000:
            raise ValueError("turn text exceeds device character bound")
        return value


class TurnDecisionRequest(Contract):
    proposal_id: UUID
    decision: Literal["approve", "reject"]
    expected_thread_version: StrictInt = Field(ge=1)


class TurnPayload(Contract):
    id: UUID
    status: TurnStatus
    parts: Annotated[tuple[TurnPart, ...], Field(max_length=MAX_MESSAGE_PARTS)]
    notices: Annotated[tuple[TurnNotice, ...], Field(max_length=8)]


class TurnPlan(Contract):
    steps: Annotated[tuple[str, ...], Field(max_length=MAX_TURN_STEPS)]
    proposals: Annotated[tuple[ProposalPart, ...], Field(max_length=2)] = ()
    notices: Annotated[tuple[TurnNotice, ...], Field(max_length=8)] = ()


def part_payload(part) -> dict:
    """JSONB storage form; validated by the database CHECK as well."""
    return part.model_dump(mode="json")


class ExecutionOutcome(Contract):
    """Bounded result of one approved continuation step.

    ``saved``/``task_id`` are canonical server references; ``code`` is an
    allowlisted machine code surfaced to the client, never provider text.
    """

    kind: Literal["output", "notice", "unknown", "failed"]
    code: Code
    message: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    output: OutputRef | None = None
    task_id: UUID | None = None


class ThreadFirstResult(Contract):
    thread_id: UUID
    # Title chosen by the server's existing title rules, never by the model.
    title: ShortText
    created: StrictBool


def validate_part_list(parts) -> tuple:
    """Validate a persisted parts array; never trust stored JSON blindly."""
    from pydantic import TypeAdapter
    return tuple(TypeAdapter(TurnPart).validate_python(part) for part in parts)


def validate_notices(notices) -> tuple[TurnNotice, ...]:
    if len(notices) > 8:
        raise ValueError("too many notices")
    return tuple(TurnNotice.model_validate(notice) for notice in notices)
