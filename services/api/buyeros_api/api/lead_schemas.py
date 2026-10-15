"""Strict manual lead contracts. None of these requests can dispatch a provider."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Generic, Literal, TypeVar
from urllib.parse import urlparse
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


class LeadStrict(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class LeadScope:
    workspace_id: UUID
    project_id: UUID
    buyer_id: UUID | None
    company_id: UUID | None
    actor_id: UUID
    membership_version: int
    roles: frozenset[str]


def credential_free_url(value: str) -> str:
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid source URL") from exc
    if (parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or any(character.isspace() for character in value)
            or (port is not None and not 1 <= port <= 65535)):
        raise ValueError("absolute credential-free HTTP(S) source required")
    return value


class LeadSourceInput(LeadStrict):
    title: StrictStr = Field(min_length=1, max_length=300)
    url: StrictStr = Field(min_length=1, max_length=2048)
    excerpt: StrictStr = Field(min_length=1, max_length=4000)
    source_kind: Literal["official", "professional", "other"]
    published_on: date | None = None
    published_precision: Literal["date"] | None = None

    _url = field_validator("url")(credential_free_url)

    @field_validator("title", "excerpt")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("source text must not be blank")
        return value

    @model_validator(mode="after")
    def date_precision(self):
        if (self.published_on is None) != (self.published_precision is None):
            raise ValueError("publication date and precision must be provided together")
        return self


class LeadPersonInput(LeadStrict):
    person_id: UUID | None = None
    full_name: StrictStr | None = Field(default=None, min_length=1, max_length=200)
    role: StrictStr | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def identity_choice(self):
        if self.person_id is not None:
            if self.full_name is not None or self.role is not None:
                raise ValueError("use existing identity or an explicit new person")
        elif not self.full_name or not self.full_name.strip():
            raise ValueError("a name is required for a new person")
        return self


class LeadChannelInput(LeadStrict):
    contact_id: UUID | None = None
    type: Literal["business_email", "business_phone", "procurement_form", "referral"] | None = None
    value: StrictStr | None = Field(default=None, min_length=3, max_length=400)
    person_id: UUID | None = None

    @model_validator(mode="after")
    def identity_choice(self):
        if self.contact_id is not None:
            if self.type is not None or self.value is not None:
                raise ValueError("use existing identity or an explicit new channel")
        elif self.type is None or self.value is None:
            raise ValueError("channel type and value are required")
        if self.type in {"procurement_form", "referral"} and self.value:
            credential_free_url(self.value)
        if self.type == "business_email" and self.value:
            local, separator, domain = self.value.strip().partition("@")
            if not separator or not local or "." not in domain or "@" in domain or any(c.isspace() for c in self.value):
                raise ValueError("business email format is invalid")
        return self


class LeadObservationInput(LeadStrict):
    claim: Literal["employment", "procurement_scope", "channel_ownership"]
    stance: Literal["supports", "refutes", "uncertain"]
    person: LeadPersonInput | None = None
    channel: LeadChannelInput | None = None
    checked_at: AwareDatetime
    sources: list[LeadSourceInput] = Field(min_length=1, max_length=10)
    rationale: StrictStr = Field(min_length=1, max_length=4000)
    limitations: StrictStr | None = Field(default=None, max_length=4000)
    supersedes_id: UUID | None = None

    @field_validator("rationale")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("rationale must not be blank")
        return value

    @model_validator(mode="after")
    def subject_required(self):
        if self.claim in {"employment", "procurement_scope"} and self.person is None:
            raise ValueError("person required")
        if self.claim == "channel_ownership" and self.channel is None:
            raise ValueError("channel required")
        return self


class ObservationIntent(LeadStrict):
    action: Literal["observation.append"]
    buyer_id: UUID
    target_id: UUID | None = None
    expected_version: StrictInt | None = Field(default=None, ge=1)
    payload: LeadObservationInput


LeadIntentInput = ObservationIntent


class EmptyLeadBody(LeadStrict):
    pass


class LeadObservationRecord(LeadStrict):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    buyer_id: UUID
    company_id: UUID
    person_id: UUID | None
    contact_id: UUID | None
    claim: str
    stance: str
    checked_at: AwareDatetime
    content_hash: str
    supersedes_id: UUID | None
    recorded_by_user_id: UUID
    created_at: AwareDatetime
    sources: list[LeadSourceInput]
    rationale: str | None
    limitations: str | None
    person: dict | None
    channel: dict | None
    redacted: bool
    availability: Literal["available", "expired", "policy_blocked", "redacted"]


class LeadEvidencePage(LeadStrict):
    items: list[LeadObservationRecord]
    offset: int
    limit: int
    total: int
    reviews: list[dict] = Field(default_factory=list)


class LeadIntentReceipt(LeadStrict):
    intent_id: UUID
    resource_type: str
    resource_id: UUID
    resource_version: int
    state: Literal["applied"]
    redacted: bool


class LeadIntentView(LeadStrict):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    buyer_id: UUID | None
    action: str
    target_id: UUID | None
    expected_version: int | None
    submission_key: str
    payload_hash: str
    payload: dict | None
    state: Literal["prepared", "applied", "cancelled"]
    receipt: LeadIntentReceipt | None
    acknowledged_at: AwareDatetime | None
    redacted: bool
    created_at: AwareDatetime


class LeadIntentPage(LeadStrict):
    items: list[LeadIntentView]
    offset: int
    limit: int
    total: int


T = TypeVar("T")


class LeadEnvelope(LeadStrict, Generic[T]):
    data: T
    request_id: str
    data_mode: Literal["live"]
