"""Strict request bodies (contract `additionalProperties: false` and x-validation)."""

from typing import Annotated, Literal, Union
from datetime import datetime
import re
import uuid
from urllib.parse import urlparse

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_website(value: str | None) -> str | None:
    """The contract declares `format: uri`; an annotated value must still have a scheme."""
    if value is None:
        return value
    parsed = urlparse(value)
    if not parsed.scheme or (parsed.scheme in ("http", "https") and not parsed.netloc):
        raise ValueError(f"website must be an absolute URI: {value!r}")
    return value


class _ProjectFields(_Strict):
    name: str = Field(min_length=2, max_length=160)
    company_name: str = Field(min_length=2, max_length=200)
    offer: str = Field(max_length=20000)
    website: str | None = Field(default=None, max_length=2000)
    markets: list[str] = Field(min_length=1, max_length=20)
    language_preferences: list[str] = Field(min_length=1, max_length=10)

    @field_validator("markets")
    @classmethod
    def _iso_markets(cls, value: list[str]) -> list[str]:
        for code in value:
            if len(code) != 2 or not code.isalpha() or code != code.upper():
                raise ValueError(f"market code must be ISO-3166 alpha-2: {code!r}")
        return value

    @field_validator("website")
    @classmethod
    def _uri_website(cls, value: str | None) -> str | None:
        return _check_website(value)

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "_ProjectFields":
        """The contract types every project field non-nullable; `null` is not an omitted field."""
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class ProjectCreate(_ProjectFields):
    pass


class SenderIdentityUpdate(_Strict):
    display_name: StrictStr = Field(min_length=2, max_length=160)
    role_title: StrictStr | None = Field(default=None, max_length=160)
    organization: StrictStr = Field(min_length=2, max_length=200)
    business_email: StrictStr = Field(max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    country: StrictStr = Field(pattern=r"^[A-Z]{2}$")
    sender_confirmation: Literal[True]
    reason: StrictStr = Field(min_length=3, max_length=400)


class ProjectUpdate(_Strict):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    offer: str | None = Field(default=None, max_length=20000)
    website: str | None = Field(default=None, max_length=2000)
    markets: list[str] | None = Field(default=None, min_length=1, max_length=20)
    language_preferences: list[str] | None = Field(default=None, min_length=1, max_length=10)
    sender_identity: SenderIdentityUpdate | None = None

    @field_validator("markets")
    @classmethod
    def _iso_markets(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        for code in value:
            if len(code) != 2 or not code.isalpha() or code != code.upper():
                raise ValueError(f"market code must be ISO-3166 alpha-2: {code!r}")
        return value

    @field_validator("website")
    @classmethod
    def _uri_website(cls, value: str | None) -> str | None:
        return _check_website(value)

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "ProjectUpdate":
        """A partial update may omit fields, but an explicit `null` is not a value the DB accepts."""
        for name in self.model_fields_set:
            if name != 'website' and getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class RunRetryRequest(_Strict):
    reason: StrictStr = Field(min_length=3, max_length=2000)
    resume_from_last_committed_checkpoint: StrictBool

    @model_validator(mode="after")
    def committed_only(self):
        if self.resume_from_last_committed_checkpoint is not True:
            raise ValueError("only committed-checkpoint resume is supported")
        return self


class ArchiveRequest(_Strict):
    """Contract `ArchiveRequest`: a required, auditable reason."""

    reason: str = Field(min_length=3, max_length=2000)


class ReconcileRequest(ArchiveRequest):
    """Status-only contact reconciliation; the caller never supplies cost."""



class OfferFact(_Strict):
    id: uuid.UUID
    field: StrictStr = Field(min_length=1, max_length=200)
    value: StrictStr = Field(min_length=1, max_length=20000)
    provenance: Literal["user_entered", "document_excerpt", "model_inference"]
    approved: StrictBool
    source_document_id: uuid.UUID | None = None
    excerpt: StrictStr | None = Field(default=None, max_length=20000)


class ICPRequirement(_Strict):
    id: uuid.UUID
    text: StrictStr = Field(min_length=1, max_length=2000)
    category: Literal["must", "nice", "exclude"]
    hard_exclusion: StrictBool


class ICPSaveRequest(_Strict):
    basis_offer_revision: StrictInt = Field(ge=1)
    offer_document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    offer_facts: list[OfferFact] = Field(min_length=1, max_length=100)
    requirements: list[ICPRequirement] = Field(min_length=1, max_length=100)
    markets: list[StrictStr] = Field(min_length=1, max_length=20)
    buyer_types: list[StrictStr] = Field(min_length=1, max_length=10)
    languages: list[StrictStr] = Field(min_length=1, max_length=10)
    desired_roles: list[StrictStr] = Field(default_factory=list, max_length=20)
    parent_icp_version_id: uuid.UUID | None = None

    @field_validator("markets")
    @classmethod
    def _valid_markets(cls, values: list[str]) -> list[str]:
        if any(re.fullmatch(r"[A-Z]{2}", value) is None for value in values):
            raise ValueError("markets must be ISO alpha-2 codes")
        return values

    @field_validator("buyer_types", "languages", "desired_roles")
    @classmethod
    def _nonempty_terms(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("terms must not be blank")
        return values


class ICPApproveRequest(_Strict):
    content_hash: StrictStr = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    confirmation: Literal[True]
    expected_project_version: StrictInt = Field(ge=1)


class BuyerFilters(_Strict):
    """Contract `BuyerFilters`. All optional; the route rejects a deferred non-empty filter."""

    q: str | None = Field(default=None, max_length=200)
    markets: list[str] | None = None
    buyer_types: list[str] | None = None
    fit: list[str] | None = None
    review: list[str] | None = None
    contact: list[str] | None = None
    suppressed: bool | None = None
    source_types: list[str] | None = None
    evidence_retrieved_after: str | None = None
    run_id: str | None = None
    list_id: str | None = None
    owner_membership_id: str | None = None
    owner_unassigned: bool | None = None
    unknown_fit: bool | None = None


class SnapshotCreate(_Strict):
    filters: BuyerFilters
    sort: Literal["best_fit", "name_asc"]
    requested_limit: int = Field(ge=1, le=1000)


class VersionedId(_Strict):
    id: str
    version: int = Field(ge=1)


class ExplicitSelection(_Strict):
    kind: Literal["explicit"]
    buyers: list[VersionedId] = Field(min_length=1, max_length=1000)


class SnapshotSelection(_Strict):
    kind: Literal["snapshot"]
    snapshot_id: str
    excluded_ids: list[str] = Field(max_length=1000)


Selection = Annotated[Union[ExplicitSelection, SnapshotSelection], Field(discriminator="kind")]


class BuyerExportRequest(_Strict):
    selection: Selection
    purpose: Literal["export_accounts", "export_contacts"]
    include_contact_data: bool
    format: Literal["csv"]

    @model_validator(mode="after")
    def _purpose_matches_content(self) -> "BuyerExportRequest":
        if self.include_contact_data != (self.purpose == "export_contacts"):
            raise ValueError("purpose and include_contact_data must agree")
        return self


class DraftExportRequest(_Strict):
    revision_id: uuid.UUID
    approval_id: uuid.UUID
    format: Literal["text", "clipboard"]


class QuoteRequest(_Strict):
    selection: Selection
    purpose: Literal["contact_research"]
    roles: list[StrictStr] = Field(min_length=1, max_length=5)
    contact_type: Literal["business_email"]

    @field_validator("roles")
    @classmethod
    def _bounded_roles(cls, roles: list[str]) -> list[str]:
        if any(not role or len(role) > 100 or role != role.strip() for role in roles):
            raise ValueError("roles must be nonempty, trimmed and at most 100 characters")
        if len(set(roles)) != len(roles):
            raise ValueError("roles must be unique")
        return roles


LookupQuoteRequest = QuoteRequest


class QuoteConfirmRequest(_Strict):
    quote_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    confirm_eligible_only: Literal[True]


LookupConfirmRequest = QuoteConfirmRequest


class ReviewRequest(_Strict):
    selection: Selection
    status: Literal["accepted", "rejected", "needs_information"]
    reason: str = Field(min_length=3, max_length=2000)


class BuyerUpdate(_Strict):
    note: str | None = Field(default=None, max_length=20000)
    owner_membership_id: str | None = None

    @model_validator(mode="after")
    def _required_patch(self) -> "BuyerUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        if "note" in self.model_fields_set and self.note is None:
            raise ValueError("note must not be null")
        return self


class ListWrite(_Strict):
    name: str = Field(min_length=1, max_length=160)

    @model_validator(mode="after")
    def _nonblank(self) -> "ListWrite":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be blank")
        return self


class OwnerAssignRequest(_Strict):
    selection: Selection
    owner_membership_id: uuid.UUID | None
    reason: str = Field(min_length=3, max_length=2000)


class ListMembershipRequest(_Strict):
    selection: Selection
    operation: Literal["add", "remove"]


class PresetWrite(_Strict):
    name: str = Field(min_length=1, max_length=100)
    filters: BuyerFilters
    sort: Literal["best_fit", "name_asc"]

    @model_validator(mode="after")
    def _nonblank(self) -> "PresetWrite":
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be blank")
        return self


PolicyPurpose = Literal["offer_research", "account_research", "contact_research", "draft_preparation", "outreach", "export_accounts", "export_contacts"]
SuppressionPurpose = Literal["contact_research", "draft_preparation", "outreach", "export_contacts"]


class PolicyWrite(_Strict):
    subject_type: Literal["company", "contact_point", "project"]
    subject_id: uuid.UUID
    controller_scope_id: uuid.UUID
    purpose: PolicyPurpose
    status: Literal["requires_review", "permitted", "blocked"]
    policy_version: str = Field(min_length=1, max_length=64)
    basis_reference: str = Field(min_length=3, max_length=1000)
    provenance: str = Field(min_length=3, max_length=1000)
    countries: list[str] = Field(min_length=1, max_length=20)
    expires_at: datetime
    retention_days: int = Field(ge=1, le=3650)

    @field_validator("countries")
    @classmethod
    def _countries(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value) or any(not re.fullmatch(r"[A-Z]{2}", item) for item in value):
            raise ValueError("countries must be unique ISO alpha-2 codes")
        return value

    @field_validator("expires_at")
    @classmethod
    def _aware_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return value


class SuppressionCreate(_Strict):
    subject_type: Literal["company", "contact_point", "domain"]
    subject_id: uuid.UUID | None = None
    normalized_domain: str | None = Field(default=None, max_length=255)
    controller_scope_id: uuid.UUID
    purposes: list[SuppressionPurpose] = Field(min_length=1, max_length=4)
    reason: str = Field(min_length=3, max_length=2000)
    source_reference: str | None = Field(default=None, max_length=1000)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _exact_subject(self) -> "SuppressionCreate":
        if self.subject_type == "domain":
            if self.subject_id is not None or not self.normalized_domain:
                raise ValueError("domain suppression requires only normalized_domain")
        elif self.subject_id is None or self.normalized_domain is not None:
            raise ValueError("company/contact suppression requires only subject_id")
        if len(set(self.purposes)) != len(self.purposes):
            raise ValueError("purposes must be unique")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return self


class SuppressionRemove(_Strict):
    reason: str = Field(min_length=3, max_length=2000)


class PreferencesUpdate(_Strict):
    locale: Literal["en", "zh-HK"] | None = None
    default_markets: list[StrictStr] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def _nonempty(self) -> "PreferencesUpdate":
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("at least one non-null preference is required")
        if self.default_markets is not None:
            if len(set(self.default_markets)) != len(self.default_markets):
                raise ValueError("default markets must be unique")
            if any(re.fullmatch(r"[A-Z]{2}", value) is None for value in self.default_markets):
                raise ValueError("default markets must be ISO alpha-2 codes")
        return self


class MembershipRead(_Strict):
    id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    display_name: StrictStr = Field(min_length=1, max_length=200)
    roles: list[Literal["viewer", "operator", "reviewer", "workspace_admin"]]
    active: StrictBool
    version: int = Field(ge=1)


class EligibleAssignee(_Strict):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    display_name: StrictStr = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)


class MembershipUpdate(_Strict):
    roles: list[Literal["viewer", "operator", "reviewer", "workspace_admin"]] = Field(min_length=1, max_length=4)
    active: StrictBool
    reason: StrictStr = Field(min_length=3, max_length=2000)

    @field_validator("roles")
    @classmethod
    def _unique_roles(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("roles must be unique")
        return values


class BudgetMoney(_Strict):
    amount: StrictStr = Field(pattern=r"^(0|[1-9][0-9]{0,13})\.[0-9]{6}$")
    currency: Literal["USD"]


class DraftGenerateRequest(_Strict):
    buyer_id: uuid.UUID
    buyer_version: StrictInt = Field(ge=1)
    recipient_contact_id: uuid.UUID | None = None
    objective: StrictStr = Field(min_length=3, max_length=1000)
    tone: Literal["professional", "concise", "warm"]
    language: StrictStr = Field(min_length=2, max_length=16)
    approved_offer_fact_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    evidence_refs: list[VersionedId] = Field(min_length=1, max_length=50)
    kind: Literal["initial", "follow_up"]
    parent_draft_id: uuid.UUID | None = None
    max_cost: BudgetMoney

    @model_validator(mode="after")
    def _follow_up_parent(self) -> "DraftGenerateRequest":
        if (self.kind == "follow_up") != (self.parent_draft_id is not None):
            raise ValueError("follow_up requires a parent draft; initial must not provide one")
        return self


class DraftUpdate(_Strict):
    recipient_contact_id: uuid.UUID | None = None
    subject: StrictStr | None = Field(default=None, max_length=300)
    body: StrictStr | None = Field(default=None, max_length=20000)
    sender_identity_version: StrictStr | None = Field(default=None, max_length=100,
        pattern=r"^sender:[a-f0-9-]{36}:[1-9][0-9]*$")
    evidence_refs: list[VersionedId] | None = Field(default=None, max_length=50)
    objective: StrictStr | None = Field(default=None, max_length=1000)
    tone: Literal["professional", "concise", "warm"] | None = None
    language: StrictStr | None = Field(default=None, min_length=2, max_length=16)
    value_proposition_fact_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=20)

    @model_validator(mode="after")
    def _nonempty(self) -> "DraftUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one change is required")
        for field in self.model_fields_set - {"recipient_contact_id"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DraftReviewRequest(_Strict):
    revision_id: uuid.UUID
    content_hash: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    context_hash: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")


class DraftApproveRequest(DraftReviewRequest):
    recipient_contact_id: uuid.UUID
    recipient_contact_version: StrictInt = Field(ge=1)
    evidence_set_hash: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    icp_version_id: uuid.UUID
    policy_decision_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    sender_identity_version: StrictStr = Field(pattern=r"^sender:[a-f0-9-]{36}:[1-9][0-9]*$")
    confirmation: Literal[True]

    @field_validator("policy_decision_ids")
    @classmethod
    def _unique_policy_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("policy_decision_ids must be unique")
        return value


class BudgetUpdate(_Strict):
    approved_limit: BudgetMoney
    reason: StrictStr = Field(min_length=3, max_length=2000)


class OfferIngestMoney(_Strict):
    amount: str = Field(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{6}$")
    currency: Literal["USD"]


class OfferIngestRequest(_Strict):
    source_url: str = Field(min_length=12, max_length=1000)
    max_cost: OfferIngestMoney
    purpose: Literal["offer_research"]


class RunLimits(_Strict):
    query_rounds: StrictInt = Field(ge=1, le=3)
    max_queries_per_run: StrictInt = Field(ge=1, le=12)
    max_results: StrictInt = Field(ge=1, le=300)
    max_pages: StrictInt = Field(ge=1, le=200)
    max_page_bytes: StrictInt = Field(ge=1024, le=2097152)
    max_duration_seconds: StrictInt = Field(ge=60, le=1800)
    max_model_tokens: StrictInt = Field(ge=1, le=100000)
    provider_concurrency: StrictInt = Field(ge=1, le=4)


class RunMoney(_Strict):
    amount: StrictStr = Field(pattern=r"^(0|[1-9][0-9]*)\.[0-9]{6}$")
    currency: Literal["USD"]

    @field_validator("amount")
    @classmethod
    def _database_money_bound(cls, value: str) -> str:
        from decimal import Decimal

        if Decimal(value) >= Decimal("100000000000000"):
            raise ValueError("amount exceeds NUMERIC(20,6)")
        return value


class RunCreate(_Strict):
    icp_version_id: uuid.UUID
    target_companies: StrictInt = Field(ge=1, le=100)
    max_cost: RunMoney
    limits: RunLimits


class OutcomeCreateRequest(_Strict):
    buyer_id: uuid.UUID
    stage: Literal["reply", "meeting", "opportunity", "disqualified"]
    occurred_at: AwareDatetime
    source: Literal["manual"]
    notes: StrictStr = Field(min_length=3, max_length=2000)
    provenance_reference: StrictStr | None = Field(default=None, max_length=1000)


class OutcomeCorrectionRequest(_Strict):
    stage: Literal["reply", "meeting", "opportunity", "disqualified"]
    occurred_at: AwareDatetime
    notes: StrictStr = Field(min_length=3, max_length=2000)
    reason: StrictStr = Field(min_length=3, max_length=1000)
