"""Strict manual lead contracts. None of these requests can dispatch a provider."""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Generic, Literal, TypeVar, Union
from urllib.parse import urlparse
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator


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


class LeadReviewInput(LeadStrict):
    person_id: UUID
    contact_id: UUID | None = None
    employment: Literal["accepted", "uncertain", "rejected"]
    procurement_scope: Literal["accepted", "uncertain", "rejected"]
    channel_ownership: Literal["accepted", "uncertain", "rejected"]
    observation_ids: list[UUID] = Field(min_length=1, max_length=100)
    conflict_resolution: StrictStr | None = Field(default=None, max_length=4000)
    rationale: StrictStr = Field(min_length=1, max_length=4000)
    previous_review_id: UUID | None = None

    @model_validator(mode="after")
    def valid_review(self):
        if len(set(self.observation_ids)) != len(self.observation_ids) or not self.rationale.strip():
            raise ValueError("unique references and a rationale are required")
        if self.contact_id is None and self.channel_ownership == "accepted":
            raise ValueError("accepted ownership requires a selected channel")
        return self


class LeadCaseUpdate(LeadStrict):
    priority: StrictBool
    priority_reason: StrictStr = Field(default="", max_length=4000)
    next_action: StrictStr = Field(default="", max_length=200)
    due_on: date | None = None

    @model_validator(mode="after")
    def priority_has_reason(self):
        if self.priority and not self.priority_reason.strip():
            raise ValueError("priority requires a reason")
        return self


class LeadReviewIntent(LeadStrict):
    action: Literal["lead.review"]
    buyer_id: UUID
    target_id: UUID | None = None
    expected_version: StrictInt = Field(ge=1)
    payload: LeadReviewInput


class LeadCaseIntent(LeadStrict):
    action: Literal["case.update"]
    buyer_id: UUID
    target_id: UUID | None = None
    expected_version: StrictInt = Field(ge=1)
    payload: LeadCaseUpdate


LeadIntentInput = Annotated[
    Union[ObservationIntent, LeadReviewIntent, LeadCaseIntent], Field(discriminator="action"),
]


class LeadQuality(LeadStrict):
    employment_current: bool
    procurement_current: bool
    channel_ownership_current: bool
    qualified_person: bool
    direct_channel: bool
    needs_review: bool
    blockers: list[str]
    expires_at: AwareDatetime | None


class LeadReviewRecord(LeadStrict):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    buyer_id: UUID
    company_id: UUID
    person_id: UUID
    contact_id: UUID | None
    employment: Literal["accepted", "uncertain", "rejected"]
    procurement_scope: Literal["accepted", "uncertain", "rejected"]
    channel_ownership: Literal["accepted", "uncertain", "rejected"]
    case_version: int
    context_hash: str
    context_current: bool = True
    observation_ids: list[UUID]
    previous_review_id: UUID | None
    recorded_by_user_id: UUID
    created_at: AwareDatetime
    rationale: str | None
    conflict_resolution: str | None
    redacted: bool


LeadStage = Literal[
    "find_person", "verify_employment", "verify_procurement", "verify_channel",
    "refresh_evidence", "review_preparation", "complete",
]
LeadCriterion = Literal[
    "company_card", "priority_company", "qualified_person", "direct_channel", "reviewed_preparation",
]


class LeadFilters(LeadStrict):
    priority: bool | None = None
    stage: LeadStage | None = None
    owner_user_id: UUID | None = None
    due_before: date | None = None
    qualifies_for: LeadCriterion | None = None


class LeadProgressQuery(LeadFilters):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class LeadCaseView(LeadStrict):
    workspace_id: UUID
    project_id: UUID
    buyer_id: UUID
    company_id: UUID
    company_name: str
    version: int
    state_exists: bool
    priority: bool
    priority_reason: str
    owner_user_id: UUID | None
    next_action: str
    due_on: date | None
    selected_person_id: UUID | None
    selected_contact_id: UUID | None
    quality: LeadQuality
    observations: list[LeadObservationRecord] | None
    observations_total: int
    reviews: list[LeadReviewRecord]
    reviews_total: int
    source_check_ids: list[UUID]
    stage: LeadStage
    reviewed_preparation: bool = False
    as_of: AwareDatetime


class LeadMetrics(LeadStrict):
    company_cards: int = Field(ge=0)
    priority_companies: int = Field(ge=0)
    qualified_people_companies: int = Field(ge=0)
    direct_channel_companies: int = Field(ge=0)
    reviewed_preparation_companies: int = Field(ge=0)


class LeadProgressPage(LeadStrict):
    items: list[LeadCaseView]
    offset: int
    limit: int
    total: int
    metrics: LeadMetrics
    as_of: AwareDatetime
    context_hash: str


class LeadProductFactRef(LeadStrict):
    id: UUID
    icp_version_id: UUID
    icp_content_hash: StrictStr = Field(min_length=1, max_length=80)
    offer_revision: StrictInt = Field(ge=1)


class LeadPreparationInput(LeadStrict):
    person_id: UUID | None = None
    contact_id: UUID | None = None
    subject: StrictStr = Field(default="", max_length=300)
    body: StrictStr = Field(default="", max_length=12000)
    language: Literal["en", "zh-HK"] = "en"
    product_fact_refs: list[LeadProductFactRef] = Field(default_factory=list, max_length=20)
    observation_ids: list[UUID] = Field(default_factory=list, max_length=100)
    lead_review_id: UUID | None = None
    company_source_check_ids: list[UUID] = Field(default_factory=list, max_length=10)
    previous_revision_id: UUID | None = None

    @model_validator(mode="after")
    def unique_references(self):
        for values in (self.observation_ids, self.company_source_check_ids, [ref.id for ref in self.product_fact_refs]):
            if len(values) != len(set(values)):
                raise ValueError("references must be unique")
        return self


class LeadPreparationReviewInput(LeadStrict):
    revision_id: UUID
    context_hash: StrictStr = Field(min_length=1, max_length=80)
    reason: StrictStr = Field(min_length=3, max_length=4000)
    confirmation: StrictBool

    @field_validator("confirmation")
    @classmethod
    def confirmed(cls, value):
        if value is not True:
            raise ValueError("exact-content review confirmation required")
        return value


class LeadPreparationStateInput(LeadStrict):
    reason: StrictStr = Field(min_length=3, max_length=4000)


class LeadPreparationIntent(LeadStrict):
    action: Literal["preparation.create", "preparation.revise"]
    buyer_id: UUID
    target_id: UUID | None = None
    expected_version: StrictInt | None = Field(default=None, ge=1)
    payload: LeadPreparationInput

    @model_validator(mode="after")
    def target(self):
        if self.action == "preparation.create" and (self.target_id is not None or self.expected_version is not None):
            raise ValueError("creation has no previous preparation")
        if self.action == "preparation.revise" and (self.target_id is None or self.expected_version is None):
            raise ValueError("revision requires target and precondition")
        return self


class LeadPreparationReviewIntent(LeadStrict):
    action: Literal["preparation.review"]
    buyer_id: UUID
    target_id: UUID
    expected_version: StrictInt = Field(ge=1)
    payload: LeadPreparationReviewInput


class LeadPreparationStateIntent(LeadStrict):
    action: Literal["preparation.archive", "preparation.request_review"]
    buyer_id: UUID
    target_id: UUID
    expected_version: StrictInt = Field(ge=1)
    payload: LeadPreparationStateInput


LeadIntentInput = Annotated[
    Union[ObservationIntent, LeadReviewIntent, LeadCaseIntent, LeadPreparationIntent,
          LeadPreparationReviewIntent, LeadPreparationStateIntent], Field(discriminator="action"),
]


class LeadPreparationView(LeadStrict):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    buyer_id: UUID
    company_id: UUID
    version: int
    revision_id: UUID
    revision_number: int
    state: Literal["editing", "review_requested", "reviewed", "needs_review", "archived"]
    stored_state: str
    context_hash: str
    content_hash: str
    content: LeadPreparationInput | None
    facts: list[dict]
    source_references: list[dict]
    blockers: list[str]
    context_current: bool
    redacted: bool
    reviewed_by_user_id: UUID | None
    reviewed_at: AwareDatetime | None
    created_at: AwareDatetime


class LeadPreparationPage(LeadStrict):
    items: list[LeadPreparationView]
    offset: int
    limit: int
    total: int


class LeadPreparationRevisionView(LeadStrict):
    id: UUID
    preparation_id: UUID
    revision_number: int
    content_hash: str
    context_hash: str
    created_at: AwareDatetime
    content: LeadPreparationInput | None
    historical: Literal[True]
    redacted: bool


class LeadPreparationRevisionPage(LeadStrict):
    items: list[LeadPreparationRevisionView]
    offset: int
    limit: int
    total: int
