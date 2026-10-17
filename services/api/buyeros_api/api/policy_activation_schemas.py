"""Closed, immutable manual controller-policy contracts. No activation side effects."""
from datetime import datetime, timezone
import ipaddress
import re
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator, model_serializer

ActivationPurpose = Literal["account_research", "contact_research", "draft_preparation", "outreach"]
PROVIDER_ACTIONS = {
    "contact_research": frozenset({"contact.enrich", "contact.read"}),
    "draft_preparation": frozenset({"draft.generate"}),
    "outreach": frozenset({"delivery.review", "delivery.send"}),
}
RESEARCH_ACTIONS = frozenset({"research.search", "research.model", "research.read", "research.persist", "research.fetch"})
MANUAL_ACTIONS = frozenset({
    "observation.append", "lead.review", "lead.evidence.read", "preparation.create",
    "preparation.revise", "preparation.request_review", "preparation.review", "preparation.read",
})
MANUAL_DATA = frozenset({
    "professional_identity", "employment", "procurement_scope", "business_channel",
    "evidence_excerpt", "review_note", "preparation_content",
})
SUPPORTED_ACTIONS = MANUAL_ACTIONS | frozenset().union(*PROVIDER_ACTIONS.values()) | RESEARCH_ACTIONS


class ActivationStrict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def exact_domain(value: str) -> str:
    if not isinstance(value, str) or value != value.strip() or len(value) > 253:
        raise ValueError("exact domain required")
    try:
        result = value.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValueError("exact domain required") from exc
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", result):
        raise ValueError("exact domain required; no URL, wildcard, userinfo or port")
    try:
        ipaddress.ip_address(result)
    except ValueError:
        return result
    raise ValueError("IP address is not an official domain scope")


class PolicySourceScope(ActivationStrict):
    domains: tuple[StrictStr, ...] = Field(default=(), max_length=100)
    document_ids: tuple[UUID, ...] = Field(default=(), max_length=100)

    @field_validator("domains")
    @classmethod
    def domains_exact(cls, values):
        result = tuple(exact_domain(v) for v in values)
        if len(set(result)) != len(result):
            raise ValueError("duplicate domains")
        return tuple(sorted(result))

    @field_validator("document_ids")
    @classmethod
    def documents_unique(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("duplicate documents")
        return tuple(sorted(values, key=str))

    @model_validator(mode="after")
    def source_required(self):
        if not self.domains and not self.document_ids:
            raise ValueError("at least one exact source scope required")
        return self


class PolicyDeletionPlan(ActivationStrict):
    method: Literal["redact_private_payload"]
    audit: Literal["retain_non_content"]
    backup: Literal["expiry_and_replay"]
    reference: StrictStr = Field(min_length=3, max_length=1000)


class ProviderPolicyScope(ActivationStrict):
    provider_name: StrictStr = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    account_reference: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
    contract_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    sender_identity_id: UUID | None = None
    recipient_refs: tuple[UUID, ...] = Field(default=(), max_length=100)
    allow_unaddressed_drafts: StrictBool = False

    @field_validator("recipient_refs")
    @classmethod
    def recipients_unique(cls, values):
        if len(set(values)) != len(values) or any(v.int == 0 for v in values):
            raise ValueError("unique exact nonzero recipient references required")
        return tuple(sorted(values, key=str))


class ResearchProviderBinding(ActivationStrict):
    provider_name: StrictStr = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    account_reference: StrictStr = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
    contract_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class ResearchPolicyScope(ActivationStrict):
    search: ResearchProviderBinding | None = None
    model: ResearchProviderBinding | None = None

    @model_validator(mode="after")
    def bound_service_required(self):
        if self.search is None and self.model is None:
            raise ValueError("at least one exact reviewed research provider binding required")
        return self


class PolicyTerms(ActivationStrict):
    workspace_id: UUID
    controller_scope_id: UUID
    project_id: UUID
    purpose: ActivationPurpose
    template_version: Literal["manual-native.v1", "provider-native.v1", "provider-research.v1"]
    provider_scope: ProviderPolicyScope | None = Field(default=None, json_schema_extra=lambda schema: schema.pop("default", None))
    research_scope: ResearchPolicyScope | None = Field(default=None, json_schema_extra=lambda schema: schema.pop("default", None))
    allowed_data_categories: tuple[StrictStr, ...] = Field(min_length=1, max_length=20)
    allowed_sources: PolicySourceScope
    allowed_actions: tuple[StrictStr, ...] = Field(min_length=1, max_length=20)
    valid_from: AwareDatetime
    expires_at: AwareDatetime
    retention_days: StrictInt = Field(ge=1, le=3650)
    deletion_plan: PolicyDeletionPlan
    countries: tuple[StrictStr, ...] = Field(min_length=1, max_length=20)
    policy_version: StrictStr = Field(min_length=1, max_length=64)
    basis_reference: StrictStr = Field(min_length=3, max_length=1000)
    provenance: StrictStr = Field(min_length=3, max_length=1000)
    owner_evidence_reference: StrictStr = Field(min_length=3, max_length=1000)
    owner_evidence_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("valid_from", "expires_at")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc)

    @field_validator("allowed_data_categories")
    @classmethod
    def supported_data(cls, values):
        if len(set(values)) != len(values) or frozenset(values) != MANUAL_DATA:
            raise ValueError("UNSUPPORTED_POLICY_SCOPE: approve the whole supported data template")
        return tuple(sorted(values))

    @field_validator("allowed_actions")
    @classmethod
    def supported_actions(cls, values):
        if len(set(values)) != len(values) or not set(values) <= SUPPORTED_ACTIONS:
            raise ValueError("UNSUPPORTED_POLICY_SCOPE: supported actions required")
        return tuple(sorted(values))

    @field_validator("countries")
    @classmethod
    def countries_exact(cls, values):
        if len(set(values)) != len(values) or any(not re.fullmatch(r"[A-Z]{2}", v) for v in values):
            raise ValueError("unique alpha-2 country codes required")
        return tuple(sorted(values))

    @field_validator("policy_version", "basis_reference", "provenance", "owner_evidence_reference")
    @classmethod
    def confirmed_content(cls, value):
        if not value.strip() or value.strip().casefold() in {"todo", "tbd", "unknown", "pending", "待確認", "待資料擁有人確認"}:
            raise ValueError("confirmed nonblank policy content required")
        return value

    @model_validator(mode="after")
    def bounded_controller(self):
        if self.controller_scope_id != self.workspace_id or self.valid_from >= self.expires_at:
            raise ValueError("exact controller and increasing validity window required")
        if self.template_version == "manual-native.v1":
            if (self.provider_scope is not None or self.research_scope is not None or self.purpose == "outreach"
                    or not set(self.allowed_actions) <= MANUAL_ACTIONS):
                raise ValueError("manual grant cannot authorize provider operations")
        elif self.template_version == "provider-research.v1":
            scope = self.research_scope
            if (self.provider_scope is not None or scope is None or self.purpose != "account_research"
                or not RESEARCH_ACTIONS.intersection(self.allowed_actions)
                or not set(self.allowed_actions) <= (RESEARCH_ACTIONS | MANUAL_ACTIONS)
                or ("research.search" in self.allowed_actions and scope.search is None)
                or ("research.model" in self.allowed_actions and scope.model is None)):
                raise ValueError("exact separate search/model scope and research actions required")
        else:
            scope = self.provider_scope
            provider_actions = PROVIDER_ACTIONS.get(self.purpose, frozenset())
            if (scope is None or self.research_scope is not None or not provider_actions.intersection(self.allowed_actions)
                    or not set(self.allowed_actions) <= (provider_actions | MANUAL_ACTIONS)):
                raise ValueError("exact provider scope and purpose-specific actions required")
            if self.purpose == "contact_research":
                if scope.sender_identity_id is not None or scope.allow_unaddressed_drafts:
                    raise ValueError("contact enrichment cannot authorize addressed delivery")
                if ("contact.read" in self.allowed_actions) != bool(scope.recipient_refs):
                    raise ValueError("contact.read requires exact approved contact references")
            elif (scope.sender_identity_id is None or scope.sender_identity_id.int == 0
                  or (not scope.recipient_refs and not (self.purpose == "draft_preparation" and scope.allow_unaddressed_drafts))
                  or (self.purpose == "outreach" and scope.allow_unaddressed_drafts)):
                raise ValueError("exact sender and explicit addressed scope required")
        return self

    @model_serializer(mode="wrap")
    def stable_manual_wire(self, handler):
        value = handler(self)
        if self.provider_scope is None:
            value.pop("provider_scope", None)
        if self.research_scope is None:
            value.pop("research_scope", None)
        return value


class PolicyUseContext(ActivationStrict):
    action: StrictStr
    project_id: UUID
    source_ids: tuple[UUID, ...] = ()
    source_domains: tuple[StrictStr, ...] = ()
    data_categories: frozenset[StrictStr] = frozenset()
    provider_name: StrictStr | None = None
    account_reference: StrictStr | None = None
    contract_sha256: StrictStr | None = None
    sender_identity_id: UUID | None = None
    recipient_ref: UUID | None = None


class ActivationSubmit(ActivationStrict):
    client_request_id: UUID
    authority_id: UUID
    authority_version: StrictInt = Field(ge=1)
    expected_policy_id: UUID | None
    expected_policy_version: StrictInt | None = Field(ge=1)
    terms: PolicyTerms
    request_deadline: AwareDatetime

    @field_validator("request_deadline")
    @classmethod
    def deadline_utc(cls, value):
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def paired_head(self):
        if (self.expected_policy_id is None) != (self.expected_policy_version is None):
            raise ValueError("paired policy head required")
        if self.request_deadline > self.terms.expires_at:
            raise ValueError("request deadline exceeds policy expiry")
        return self


class ActivationDecision(ActivationStrict):
    action: Literal["approve", "reject"]
    terms_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    expected_policy_id: UUID | None
    expected_policy_version: StrictInt | None = Field(ge=1)
    reason: StrictStr = Field(min_length=3, max_length=2000)
    expected_request_state: Literal["submitted"] = "submitted"

    @model_validator(mode="after")
    def paired_head(self):
        if (self.expected_policy_id is None) != (self.expected_policy_version is None) or not self.reason.strip():
            raise ValueError("paired head and reason required")
        return self


class ActivationWithdrawal(ActivationStrict):
    terms_hash: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    reason: StrictStr = Field(min_length=3, max_length=2000)


class ActivationReceipt(ActivationStrict):
    request_id: UUID
    resolution_id: UUID | None = None
    decision_id: UUID | None = None
    terms_hash: str
    outcome: Literal["submitted", "approved", "rejected", "withdrawn"]
    policy_version: int | None = None


class ActivationView(ActivationStrict):
    id: UUID
    project_id: UUID
    client_request_id: UUID
    requester_id: UUID
    authority_id: UUID
    authority_version: int
    terms: PolicyTerms
    terms_hash: str
    request_deadline: datetime
    request_state: str
    effective_status: str
    receipt: ActivationReceipt


class AuthoritySummary(ActivationStrict):
    id: UUID
    version: int
    project_id: UUID
    approver_user_id: UUID
    purposes: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    valid_from: datetime
    expires_at: datetime
    eligible: bool


class ActivationPage(ActivationStrict):
    items: tuple[ActivationView, ...]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class AuthorityPage(ActivationStrict):
    items: tuple[AuthoritySummary, ...]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
