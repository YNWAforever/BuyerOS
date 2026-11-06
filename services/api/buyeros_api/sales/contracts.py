"""Sales extension data contracts; validation does not authorise execution.

Runtime owners recheck ACLs, source eligibility, native revisions, quotes and
reservations. This module imports no database, provider or model registration.
"""
from __future__ import annotations
import json
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import (AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StrictBool,
    StringConstraints, StrictInt, PrivateAttr, field_serializer, field_validator, model_validator)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Revision = Annotated[StrictInt, Field(ge=1)]
Credits = Annotated[StrictInt, Field(ge=0)]
Language = Literal["en", "zh-HK"]
TaskState = Literal["needs_input", "ready_for_review", "queued", "running",
    "partially_completed", "completed", "failed", "cancel_requested", "cancelled", "outcome_unknown"]
OutputKind = Literal["profile_proposal", "research_report", "qualification_assessment",
    "enrichment_proposal", "competitive_document", "outreach_preparation",
    "followup_preparation", "meeting_brief", "sales_proposal", "objection_playbook",
    "pipeline_report", "report_export", "project_setup", "document_understanding", "buyer_review"]
ContactTool = Literal["search_company_xverum", "search_people_xverum",
    "enrich_company_xverum", "enrich_person_xverum", "get_email_xverum"]
CONTACT_ALLOWLIST = ("search_company_xverum", "search_people_xverum",
    "enrich_company_xverum", "enrich_person_xverum", "get_email_xverum")
Capability = Literal["search_company_xverum", "search_people_xverum",
    "enrich_company_xverum", "enrich_person_xverum", "get_email_xverum",
    "research.read", "profile.propose", "buyers.review", "lists.propose",
    "drafts.prepare", "documents.read", "documents.prepare", "reports.read",
    "reports.export", "tasks.plan"]
Availability = Literal["available", "source_deleted", "permission_revoked", "retention_expired", "unavailable"]
EnrichmentField = Literal["company_name", "domain", "industry", "location",
    "employee_count", "person_name", "job_title", "employer", "business_email"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class Scope(Contract):
    workspace_id: UUID
    project_id: UUID
    actor_id: UUID


class PurgeReceipt(Contract):
    affected_ids: tuple[UUID, ...]
    completed_at: AwareDatetime


class SourceRef(Contract):
    id: UUID
    version: Revision
    kind: Literal["project_fact", "profile", "buyer", "document", "output", "run", "provider_evidence", "drive"]
    locator: Annotated[str, StringConstraints(min_length=1, max_length=500, pattern=r"^[^\r\n]+$")]
    retention_class: Literal["durable", "metadata_only", "zero_content"]


class ContextSnapshot(Contract):
    # Request memory only; never emitted in contracts, tasks or usage receipts.
    _sources: list[dict] = PrivateAttr(default_factory=list)
    _profile_hash: str = PrivateAttr(default="")
    refs: Annotated[tuple[SourceRef, ...], Field(max_length=64)]
    digest: Digest
    profile_version: Revision | None
    connection_generations: dict[UUID, Revision] = Field(default_factory=dict, max_length=16)

    @field_validator("connection_generations")
    @classmethod
    def freeze_generations(cls, value):
        return FrozenDict(value)


class NativeRef(Contract):
    surface: Literal["profile", "buyer", "list", "run", "draft", "document", "export"]
    id: UUID
    revision: Revision


class OutputDependency(Contract):
    id: UUID
    revision: Revision


class ExecutionBounds(Contract):
    max_steps: Annotated[StrictInt, Field(ge=1, le=16)] = 16
    max_model_calls: Annotated[StrictInt, Field(ge=0, le=8)] = 8
    max_concurrent_steps: Annotated[StrictInt, Field(ge=1, le=2)] = 2
    automatic_model_repair: Literal[False] = False


class FrozenDict(dict):
    """JSON-compatible recursively immutable code-owned schema."""
    def _immutable(self, *args, **kwargs):
        raise TypeError("skill definitions are immutable")
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable


class FrozenList(list):
    def _immutable(self, *args, **kwargs):
        raise TypeError("skill definitions are immutable")
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = __iadd__ = __imul__ = _immutable


def _freeze(value):
    if isinstance(value, dict):
        return FrozenDict({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return FrozenList(_freeze(item) for item in value)
    return value


class SkillDefinition(Contract):
    id: ShortText
    version: Literal["1"]
    inputs_schema: dict[str, JsonValue]
    output_kind: OutputKind
    allowed_actions: tuple[Capability, ...]
    languages: tuple[Literal["en"], Literal["zh-HK"]] = ("en", "zh-HK")
    budget_class: Literal["model", "model_and_provider_credits", "export", "bounded_orchestration"]
    upstream_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{40}$")] | None

    @field_validator("inputs_schema")
    @classmethod
    def immutable_schema(cls, value):
        return _freeze(value)

    @field_serializer("inputs_schema")
    def serialize_schema(self, value):
        return json.loads(json.dumps(value))


class SkillArguments(Contract):
    language: Language = "en"


class ResearchArguments(SkillArguments):
    buyer_id: UUID | None = None
    research_question: Text | None = None
    max_sources: Annotated[StrictInt, Field(ge=1, le=12)] = 12

    @model_validator(mode="after")
    def target_required(self):
        if self.buyer_id is None and self.research_question is None:
            raise ValueError("select a buyer or supply a research question")
        return self


class QuickArguments(ResearchArguments):
    max_sources: Annotated[StrictInt, Field(ge=1, le=3)] = 3


class ProspectArguments(SkillArguments):
    buyer_id: UUID
    objective: Text
    bounds: ExecutionBounds = Field(default_factory=ExecutionBounds)


class BuyerArguments(SkillArguments):
    buyer_id: UUID


class QualificationArguments(BuyerArguments):
    profile_id: UUID
    profile_version: Revision
    rubric: Literal["BANT_MEDDIC"] = "BANT_MEDDIC"


class ContactsArguments(BuyerArguments):
    purpose: Text
    roles: Annotated[tuple[ShortText, ...], Field(min_length=1, max_length=5)]


class OutreachArguments(BuyerArguments):
    profile_id: UUID
    recipient_id: UUID | None = None
    objective: Text
    framework: Literal["PAS", "AIDA", "BAB", "direct"] = "direct"


class FollowupArguments(OutreachArguments):
    interaction_ref: SourceRef
    scenario: Literal["post_meeting", "post_demo", "post_proposal", "recovery", "nurture"]


class MeetingArguments(BuyerArguments):
    meeting_at: AwareDatetime
    objective: Text
    attendee_ids: Annotated[tuple[UUID, ...], Field(max_length=20)] = ()
    duration_minutes: Literal[30, 60] = 30


class Money(Contract):
    amount: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


class CommercialTerms(Contract):
    price: Money
    scope: Text
    exclusions: Text
    timeline: Text
    evidence: Annotated[tuple[SourceRef, ...], Field(min_length=1, max_length=16)]


class ProposalArguments(BuyerArguments):
    profile_id: UUID
    pain_points: Annotated[tuple[Text, ...], Field(min_length=1, max_length=10)]
    terms: Annotated[tuple[CommercialTerms, ...], Field(min_length=1, max_length=3)]
    case_study_refs: Annotated[tuple[SourceRef, ...], Field(max_length=10)] = ()


class ObjectionsArguments(SkillArguments):
    profile_id: UUID
    buyer_id: UUID | None = None
    objections: Annotated[tuple[Text, ...], Field(min_length=1, max_length=20)]


class ICPArguments(SkillArguments):
    offer_description: Text
    profile_id: UUID | None = None


class CompetitorsArguments(BuyerArguments):
    profile_id: UUID
    competitor_names: Annotated[tuple[ShortText, ...], Field(max_length=5)] = ()


class ReportArguments(SkillArguments):
    as_of: AwareDatetime
    buyer_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=100)]
    list_id: UUID | None = None


class ExportArguments(SkillArguments):
    output_id: UUID
    output_revision: Revision
    export_id: UUID | None = None


class OutputExportInput(Contract):
    revision: Revision
    format: Literal['markdown','pdf']
    approved: Literal[True]


class ProjectArguments(SkillArguments):
    offer_description: Text
    buyer_id: UUID | None = None
    recipient_id: UUID | None = None


class DocumentsArguments(SkillArguments):
    document_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]
    question: Text


class ReviewArguments(SkillArguments):
    buyer_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=100)]
    profile_id: UUID
    profile_version: Revision


INPUT_MODELS = {
    "sales-prospect": ProspectArguments, "sales-research": ResearchArguments,
    "sales-quick": QuickArguments, "sales-qualify": QualificationArguments,
    "sales-contacts": ContactsArguments, "sales-outreach": OutreachArguments,
    "sales-followup": FollowupArguments, "sales-prep": MeetingArguments,
    "sales-proposal": ProposalArguments, "sales-objections": ObjectionsArguments,
    "sales-icp": ICPArguments, "sales-competitors": CompetitorsArguments,
    "sales-report": ReportArguments, "sales-report-pdf": ExportArguments,
    "first-project": ProjectArguments, "understand-documents": DocumentsArguments,
    "review-buyers": ReviewArguments,
}


class SearchArguments(Contract):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    page: Annotated[StrictInt, Field(ge=1, le=1)] = 1
    page_size: Annotated[StrictInt, Field(ge=1, le=5)] = 5


class CompanyDetailArguments(Contract):
    company_id: ShortText


class PersonDetailArguments(Contract):
    id: ShortText


class NativeActionArguments(Contract):
    refs: Annotated[tuple[NativeRef, ...], Field(max_length=100)]
    purpose: Text


class BuyerNoteMutation(Contract):
    note: Annotated[str, StringConstraints(max_length=20000)]


class ListMutation(Contract):
    operation: Literal['add','remove']
    buyers: Annotated[tuple[NativeRef,...], Field(min_length=1,max_length=100)]


class DraftMutation(Contract):
    subject: Annotated[str,StringConstraints(min_length=1,max_length=300)]
    body: Annotated[str,StringConstraints(min_length=1,max_length=20000)]


class BuyerNativeArguments(NativeActionArguments):
    output: OutputDependency | None = None
    mutation: BuyerNoteMutation | None = None


class ListNativeArguments(NativeActionArguments):
    output: OutputDependency | None = None
    mutation: ListMutation | None = None


class DraftNativeArguments(NativeActionArguments):
    output: OutputDependency | None = None
    mutation: DraftMutation | None = None


ACTION_MODELS = {
    "search_company_xverum": SearchArguments, "search_people_xverum": SearchArguments,
    "enrich_company_xverum": CompanyDetailArguments,
    "enrich_person_xverum": PersonDetailArguments, "get_email_xverum": PersonDetailArguments,
    **{name: NativeActionArguments for name in (
        "research.read", "profile.propose", "buyers.review", "lists.propose", "drafts.prepare",
        "documents.read", "documents.prepare", "reports.read", "reports.export", "tasks.plan")},
}
ACTION_MODELS.update({'buyers.review':BuyerNativeArguments,'lists.propose':ListNativeArguments,
    'drafts.prepare':DraftNativeArguments})


class ActionProposal(Contract):
    id: UUID
    capability: Capability
    arguments: dict[str, JsonValue]
    source_versions: Annotated[tuple[SourceRef, ...], Field(max_length=64)]

    @model_validator(mode="after")
    def typed_arguments(self):
        ACTION_MODELS[self.capability].model_validate(self.arguments)
        return self


class Finding(Contract):
    statement: Text
    evidence: Annotated[tuple[SourceRef, ...], Field(min_length=1, max_length=16)]
    confidence: Literal["high", "medium", "low", "inference"]
    observed_at: AwareDatetime | None = None


class AuthoredContent(Contract):
    summary: Text
    unknowns: Annotated[tuple[Text, ...], Field(max_length=32)]


class ResearchReport(AuthoredContent):
    findings: Annotated[tuple[Finding, ...], Field(max_length=64)]
    opportunities: Annotated[tuple[Text, ...], Field(max_length=10)]
    concerns: Annotated[tuple[Text, ...], Field(max_length=10)]


class ProfileProposal(AuthoredContent):
    criteria: Annotated[tuple[Finding, ...], Field(min_length=1, max_length=32)]
    exclusions: Annotated[tuple[Text, ...], Field(max_length=20)]
    personas: Annotated[tuple[Text, ...], Field(min_length=1, max_length=5)]
    approval_required: Literal[True] = True


class AssessmentDimension(Contract):
    dimension: Literal["budget", "authority", "need", "timeline", "metrics", "economic_buyer",
        "decision_criteria", "decision_process", "pain", "champion"]
    score: Annotated[StrictInt, Field(ge=0, le=100)] | None
    rationale: Text
    evidence: Annotated[tuple[SourceRef, ...], Field(max_length=16)]

    @model_validator(mode="after")
    def score_needs_evidence(self):
        if self.score is not None and not self.evidence:
            raise ValueError("unknown dimensions must have null score")
        return self


class QualificationAssessment(AuthoredContent):
    rubric: Literal["BANT_MEDDIC"]
    dimensions: Annotated[tuple[AssessmentDimension, ...], Field(min_length=1, max_length=10)]
    advisory: Literal[True] = True
    next_questions: Annotated[tuple[Text, ...], Field(min_length=1, max_length=20)]


class FieldChoice(Contract):
    field: EnrichmentField
    existing_value: str | int | None
    proposed_value: str | int | None
    status: Literal["proposed", "conflict", "unknown"]
    source_refs: Annotated[tuple[SourceRef, ...], Field(min_length=1, max_length=16)]
    retrieved_at: AwareDatetime
    provider_freshness: ShortText | None


class XverumToolLiability(Contract):
    id: UUID
    ordinal: Annotated[StrictInt, Field(ge=0,le=5)]
    tool: ContactTool
    state: Literal['queued','submitting','unknown','received','nonaccepted','cancelled']
    request_id: ShortText | None
    credits_used: Credits | None


class XverumLiability(Contract):
    receipt: XverumReceipt
    connection_id: UUID
    connection_generation: Revision
    account_ref: ShortText
    tools: Annotated[tuple[XverumToolLiability,...],Field(max_length=6)]


class EnrichmentProposal(Contract):
    id: UUID
    buyer_id: UUID
    buyer_version: Revision
    identity_match: Literal["resolved", "ambiguous", "conflicting", "unresolved"]
    fields: Annotated[tuple[FieldChoice, ...], Field(max_length=40)]
    source_refs: Annotated[tuple[SourceRef, ...], Field(max_length=64)]


class CompetitiveDocument(AuthoredContent):
    competitors: Annotated[tuple[Finding, ...], Field(min_length=1, max_length=20)]
    strengths: Annotated[tuple[Finding, ...], Field(max_length=20)]
    gaps: Annotated[tuple[Finding, ...], Field(max_length=20)]
    switching_costs: Annotated[tuple[Text, ...], Field(max_length=20)]


class PreparedMessage(Contract):
    subject: ShortText
    body: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    rationale: Text
    evidence: Annotated[tuple[SourceRef, ...], Field(min_length=1, max_length=16)]
    suggested_day: Annotated[StrictInt, Field(ge=0, le=365)]


class OutreachPreparation(AuthoredContent):
    framework: Literal["PAS", "AIDA", "BAB", "direct"]
    messages: Annotated[tuple[PreparedMessage, ...], Field(min_length=1, max_length=5)]
    review_required: Literal[True] = True


class FollowupPreparation(AuthoredContent):
    scenario: Literal["post_meeting", "post_demo", "post_proposal", "recovery", "nurture"]
    interaction_ref: SourceRef
    messages: Annotated[tuple[PreparedMessage, ...], Field(min_length=1, max_length=6)]
    review_required: Literal[True] = True


class AgendaItem(Contract):
    topic: ShortText
    minutes: Annotated[StrictInt, Field(ge=1, le=60)]


class MeetingBrief(AuthoredContent):
    cheat_sheet: Text
    attendees: Annotated[tuple[Finding, ...], Field(max_length=20)]
    talking_points: Annotated[tuple[Text, ...], Field(min_length=1, max_length=7)]
    discovery_questions: Annotated[tuple[Text, ...], Field(min_length=1, max_length=10)]
    agenda: Annotated[tuple[AgendaItem, ...], Field(min_length=1, max_length=10)]
    next_steps: Annotated[tuple[Text, ...], Field(min_length=1, max_length=3)]


class SalesProposal(AuthoredContent):
    problem: Text
    solution: Text
    terms: Annotated[tuple[CommercialTerms, ...], Field(min_length=1, max_length=3)]
    assumptions: Annotated[tuple[Text, ...], Field(max_length=20)]
    proof_points: Annotated[tuple[Finding, ...], Field(max_length=10)]
    followup: Annotated[tuple[PreparedMessage, ...], Field(max_length=6)]
    review_required: Literal[True] = True


class ObjectionResponse(Contract):
    objection: Text
    feel_felt_found: Text
    acknowledge_bridge_close: Text
    followup_question: Text
    walk_away_criteria: Text
    proof_points: Annotated[tuple[Finding, ...], Field(max_length=10)]


class ObjectionPlaybook(AuthoredContent):
    responses: Annotated[tuple[ObjectionResponse, ...], Field(min_length=1, max_length=20)]


class PipelineRow(Contract):
    buyer: NativeRef
    stage: ShortText | None
    advisory_score: Annotated[StrictInt, Field(ge=0, le=100)] | None
    value: Money | None
    next_action: Text | None


class PipelineReport(AuthoredContent):
    as_of: AwareDatetime
    scope: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=100)]
    rows: Annotated[tuple[PipelineRow, ...], Field(max_length=100)]
    unavailable_buyer_ids: Annotated[tuple[UUID, ...], Field(max_length=100)]
    methodology: Text
    filters: dict[str, JsonValue] = {}
    record_basis: tuple[dict[str, JsonValue], ...] = ()

    @model_validator(mode="after")
    def complete_coverage(self):
        ids = [row.buyer.id for row in self.rows]
        if any(row.buyer.surface != "buyer" for row in self.rows):
            raise ValueError("pipeline rows must reference buyers")
        if len(ids) != len(set(ids)) or set(ids) & set(self.unavailable_buyer_ids):
            raise ValueError("duplicate pipeline coverage")
        if set(ids) | set(self.unavailable_buyer_ids) != set(self.scope):
            raise ValueError("every selected buyer must be represented or unavailable")
        return self


class ReportExport(Contract):
    output_id: UUID
    output_revision: Revision
    export_ref: NativeRef
    media_type: Literal["application/pdf"]


class ProjectSetup(AuthoredContent):
    offer: Text
    missing_fields: Annotated[tuple[ShortText, ...], Field(max_length=20)]
    next_steps: Annotated[tuple[Text, ...], Field(min_length=1, max_length=10)]
    setup_basis: dict[str, JsonValue] | None = None


class DocumentUnderstanding(AuthoredContent):
    document_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]
    findings: Annotated[tuple[Finding, ...], Field(max_length=64)]
    extraction_status: Literal["complete", "partial", "unavailable"]
    document_basis: tuple[dict[str, JsonValue], ...] = ()
    extracted_passages: Annotated[tuple[Text, ...], Field(max_length=64)] = ()
    question: Text | None = None


class BuyerReview(AuthoredContent):
    assessments: Annotated[tuple[Finding, ...], Field(max_length=100)]
    proposed_buyer_ids: Annotated[tuple[UUID, ...], Field(max_length=100)]
    review_required: Literal[True] = True


OUTPUT_MODELS = {
    "profile_proposal": ProfileProposal, "research_report": ResearchReport,
    "qualification_assessment": QualificationAssessment, "enrichment_proposal": EnrichmentProposal,
    "competitive_document": CompetitiveDocument, "outreach_preparation": OutreachPreparation,
    "followup_preparation": FollowupPreparation, "meeting_brief": MeetingBrief,
    "sales_proposal": SalesProposal, "objection_playbook": ObjectionPlaybook,
    "pipeline_report": PipelineReport, "report_export": ReportExport,
    "project_setup": ProjectSetup, "document_understanding": DocumentUnderstanding,
    "buyer_review": BuyerReview,
}
Content = (ProfileProposal | ResearchReport | QualificationAssessment | EnrichmentProposal |
    CompetitiveDocument | OutreachPreparation | FollowupPreparation | MeetingBrief |
    SalesProposal | ObjectionPlaybook | PipelineReport | ReportExport | ProjectSetup |
    DocumentUnderstanding | BuyerReview)


def _source_refs(value):
    if isinstance(value, SourceRef):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _source_refs(getattr(value, name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _source_refs(item)


class OutputCandidate(Contract):
    kind: OutputKind
    content: Content
    citations: Annotated[tuple[SourceRef, ...], Field(max_length=64)]
    dependencies: Annotated[tuple[OutputDependency, ...], Field(max_length=64)]
    native_refs: Annotated[tuple[NativeRef, ...], Field(max_length=100)]

    @model_validator(mode="after")
    def validate_content(self):
        if not isinstance(self.content, OUTPUT_MODELS[self.kind]):
            raise ValueError("content does not match output kind")
        refs = tuple(_source_refs(self.content)) + self.citations
        if any(ref.retention_class != "durable" or ref.kind == "drive" for ref in refs):
            raise ValueError("restricted source content cannot enter durable outputs")
        cited = set(self.citations)
        if any(ref not in cited for ref in _source_refs(self.content)):
            raise ValueError("content evidence must occur in citations")
        if isinstance(self.content, ReportExport):
            expected = OutputDependency(id=self.content.output_id, revision=self.content.output_revision)
            if expected not in self.dependencies:
                raise ValueError("export must depend on the exact selected report revision")
            if (self.content.export_ref.surface!='export' or self.content.export_ref.revision!=self.content.output_revision
                or self.content.export_ref not in self.native_refs):
                raise ValueError("export must reference its exact native export")
        return self


class OutputVersion(Contract):
    id: UUID
    revision: Revision
    visibility: Literal["thread", "project"]
    native_refs: Annotated[tuple[NativeRef, ...], Field(max_length=100)]
    kind: OutputKind
    content: Content | None
    citations: Annotated[tuple[SourceRef, ...], Field(max_length=64)]
    dependencies: Annotated[tuple[OutputDependency, ...], Field(max_length=64)]
    availability: Availability

    @model_validator(mode="after")
    def visibility_guard(self):
        if self.availability != "available":
            if self.content is not None or self.citations or self.dependencies or self.native_refs:
                raise ValueError("unavailable output may expose permitted audit metadata only")
        else:
            OutputCandidate(kind=self.kind, content=self.content, citations=self.citations,
                dependencies=self.dependencies, native_refs=self.native_refs)
        return self


class TaskInput(Contract):
    thread_id: UUID
    skill_id: ShortText
    skill_version: ShortText
    user_message: Text
    source_refs: Annotated[tuple[SourceRef, ...], Field(max_length=64)]
    arguments: dict[str, JsonValue]

    @model_validator(mode="after")
    def registered_arguments(self):
        from .registry import load_skill, validate_intake
        validate_intake(load_skill(self.skill_id, self.skill_version), self.arguments)
        return self


class TaskFollowup(Contract):
    user_message: Text
    arguments: dict[str, JsonValue]
    source_refs: Annotated[tuple[SourceRef, ...], Field(max_length=20)] | None = None


class IntakeEntry(Contract):
    id: UUID
    revision: Revision
    user_message: Text
    arguments: dict[str, JsonValue]
    source_refs: Annotated[tuple[SourceRef, ...], Field(max_length=20)] = ()


class PlanStep(Contract):
    section: ShortText
    kind: Literal["model", "review"]
    max_input_tokens: Literal[6000] = 6000
    max_output_tokens: Literal[1000] = 1000
    deadline_seconds: Literal[30] = 30


class TaskPlan(Contract):
    steps: Annotated[tuple[PlanStep, ...], Field(max_length=16)]
    missing_inputs: Annotated[tuple[ShortText, ...], Field(max_length=32)]
    output_kind: OutputKind
    bounds: ExecutionBounds = Field(default_factory=ExecutionBounds)
    input_token_budget: Annotated[StrictInt, Field(ge=0, le=48000)] = 0
    output_token_budget: Annotated[StrictInt, Field(ge=0, le=8000)] = 0


class PendingReview(Contract):
    id: UUID
    kind: Literal["scope", "cost", "identity", "fields", "profile", "draft"]
    revision: Revision


class TaskRecord(Contract):
    id: UUID
    state: TaskState
    revision: Revision
    context_digest: Digest | None
    output_ids: Annotated[tuple[UUID, ...], Field(max_length=64)]
    pending_review: PendingReview | None

    @model_validator(mode="after")
    def completed_result(self):
        if self.state == "completed" and (not self.output_ids or self.pending_review is not None):
            raise ValueError("completed tasks require outputs and no outstanding review")
        return self


class TaskDetail(TaskRecord):
    thread_id: UUID
    skill_id: ShortText
    skill_version: ShortText
    message_sequence: Revision
    intake: Annotated[tuple[IntakeEntry, ...], Field(min_length=1, max_length=33)]
    arguments: dict[str, JsonValue]
    source_refs: Annotated[tuple[SourceRef, ...], Field(max_length=64)]
    missing_inputs: Annotated[tuple[ShortText, ...], Field(max_length=32)]


class TaskCollectionPage(Contract):
    items: Annotated[tuple[TaskDetail, ...], Field(max_length=50)]
    total: Credits
    offset: Annotated[StrictInt, Field(ge=0, le=10000)]
    limit: Annotated[StrictInt, Field(ge=1, le=50)]


class ProgressPayload(Contract):
    step_id: UUID
    completed_steps: Annotated[StrictInt, Field(ge=0, le=16)]
    total_steps: Annotated[StrictInt, Field(ge=1, le=16)]

    @model_validator(mode="after")
    def valid_progress(self):
        if self.completed_steps > self.total_steps:
            raise ValueError("completed steps exceed total")
        return self


class StatePayload(Contract):
    state: TaskState
    revision: Revision


class OutputPayload(Contract):
    output_id: UUID
    revision: Revision


class ErrorPayload(Contract):
    code: Literal["configuration_required", "source_unavailable", "permission_revoked",
        "stale_revision", "budget_exhausted", "provider_unavailable", "invalid_output", "outcome_unknown"]
    retryable: bool


class TaskEvent(Contract):
    task_id: UUID
    sequence: Revision
    kind: Literal["progress", "state", "output", "review", "error"]
    payload: ProgressPayload | StatePayload | OutputPayload | PendingReview | ErrorPayload

    @model_validator(mode="after")
    def typed_payload(self):
        expected = {"progress": ProgressPayload, "state": StatePayload, "output": OutputPayload,
            "review": PendingReview, "error": ErrorPayload}
        if not isinstance(self.payload, expected[self.kind]):
            raise ValueError("event kind/payload mismatch")
        return self


class ToolPlanItem(Contract):
    tool: ContactTool
    arguments: SearchArguments | CompanyDetailArguments | PersonDetailArguments

    @model_validator(mode="after")
    def matching_tool(self):
        if not isinstance(self.arguments, ACTION_MODELS[self.tool]):
            raise ValueError("tool arguments do not match")
        return self


class XverumQuote(Contract):
    id: UUID
    stage: Literal["search", "detail"]
    actor_id: UUID
    connection_generation: Revision
    query: Annotated[str, StringConstraints(max_length=500)] | None
    provider_ids: Annotated[tuple[ShortText, ...], Field(max_length=4)]
    tool_plan: Annotated[tuple[ToolPlanItem, ...], Field(min_length=1, max_length=7)]
    max_credits: Credits
    tariff_version: ShortText
    expires_at: AwareDatetime
    fingerprint: Digest
    buyer_id: UUID
    connection_id: UUID

    @model_validator(mode="after")
    def staged_plan(self):
        search = {"search_company_xverum", "search_people_xverum"}
        if self.stage == "search":
            if self.provider_ids or len(self.tool_plan) != 1 or self.tool_plan[0].tool not in search:
                raise ValueError("search cannot authorise downstream identities or details")
            args = self.tool_plan[0].arguments
            if self.query != args.query or self.max_credits < args.page_size:
                raise ValueError("search query/liability mismatch")
        else:
            if self.query is not None or not self.provider_ids or any(item.tool in search for item in self.tool_plan):
                raise ValueError("detail requires selected IDs, never search")
            selected, seen, used = set(self.provider_ids), set(), set()
            counts = {"enrich_company_xverum": 0, "enrich_person_xverum": 0, "get_email_xverum": 0}
            liability = 0
            for item in self.tool_plan:
                provider_id = getattr(item.arguments, "company_id", None) or item.arguments.id
                if provider_id not in selected or (item.tool, provider_id) in seen:
                    raise ValueError("unselected or duplicate detail action")
                seen.add((item.tool, provider_id))
                used.add(provider_id)
                counts[item.tool] += 1
                liability += 2 if item.tool == "get_email_xverum" else 4
            if used != selected or counts["enrich_company_xverum"] > 1 or counts["enrich_person_xverum"] > 3 or counts["get_email_xverum"] > 3:
                raise ValueError("detail selection exceeds bounded quote")
            if self.max_credits < liability:
                raise ValueError("quote cannot understate maximum liability")
        return self


class ReconciliationEvidence(Contract):
    provider_request_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{1,128}$')
    authoritative_usage: StrictInt | None = Field(default=None, ge=0)
    evidence_ref: UUID  # private evidence registry identity; never an access-bearing URL
    resolution: Literal['usage','non_dispatch','unknown']
    expected_version: StrictInt = Field(ge=1)
    tool_receipt_id: UUID | None = None



class XverumReceipt(Contract):
    id: UUID
    version: Revision = 1
    dispatch_state: Literal["reserved", "dispatched", "settled", "outcome_unknown", "cancelled"]
    request_id: ShortText | None
    credits_used: Credits | None
    held_credits: Credits
    projection_digest: Digest | None

    @model_validator(mode="after")
    def settlement_state(self):
        if self.dispatch_state == "outcome_unknown" and (self.credits_used is not None or self.held_credits == 0):
            raise ValueError("unknown outcome retains liability, never assumes usage")
        if self.dispatch_state == "settled" and (self.credits_used is None or self.held_credits != 0):
            raise ValueError("settled receipt requires known usage and no hold")
        return self


class SalesModelRequest(Contract):
    section: ShortText = "summary"
    task_id: UUID
    step_id: UUID
    skill_id: ShortText
    skill_version: ShortText
    context: ContextSnapshot
    model_id: ShortText
    route: ShortText
    arguments: dict[str, JsonValue]

    @model_validator(mode="after")
    def safe_model_context(self):
        from .registry import load_skill, validate_arguments
        validate_arguments(load_skill(self.skill_id, self.skill_version), self.arguments)
        arguments = INPUT_MODELS[self.skill_id].model_validate(self.arguments)
        if any(ref not in self.context.refs for ref in _source_refs(arguments)):
            raise ValueError("argument evidence must be currently selected durable context")
        if any(ref.kind == "drive" or ref.retention_class != "durable" for ref in self.context.refs):
            raise ValueError("Drive/restricted content is not eligible for sales model receipts")
        return self


class ModelUsage(Contract):
    input_tokens: Credits
    output_tokens: Credits
    cost: Money | None


class SalesSectionCandidate(Contract):
    """A validated child, never acceptable to OutputSave as a complete output."""
    kind: OutputKind
    section: ShortText
    content: dict[str, JsonValue]
    citations: Annotated[tuple[SourceRef, ...], Field(max_length=20)]
    complete: Literal[False]

    @model_validator(mode="after")
    def typed_section(self):
        from .sections import section_model
        section_model(self.kind, self.section).model_validate(self.content)
        return self


class SalesModelResult(Contract):
    candidate: SalesSectionCandidate | ActionProposal
    usage: ModelUsage
    provider_ref: ShortText
    model_id: ShortText
    prompt_version: ShortText


class RevisionRequest(Contract):
    expected_revision: Revision


class QuoteApproval(Contract):
    quote_id: UUID
    fingerprint: Digest


class EnrichmentApply(Contract):
    proposal_id: UUID
    buyer_version: Revision
    selected_fields: Annotated[tuple[EnrichmentField, ...], Field(min_length=1, max_length=9)]


class EnrichmentCreate(Contract):
    selected_id: Annotated[str, Field(min_length=1,max_length=200)] | None = None
    previous_proposal_id: UUID | None = None
    buyer_id: UUID
    receipt_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=6)]
    task_id: UUID | None = None


class OutputSave(Contract):
    task_id: UUID
    expected_task_revision: Revision
    visibility: Literal["thread", "project"] = "thread"
    candidate: OutputCandidate


class OutputReview(Contract):
    task_id: UUID
    task_revision: Revision
    project_id: UUID
    thread_id: UUID
    visibility: Literal['thread'] = 'thread'
    candidate: OutputCandidate


class ConnectionBinding(Contract):
    id: UUID
    generation: Revision
    version: Revision
    account_ref: ShortText
    tariff_version: ShortText
    status: Literal["configuration_required", "connected", "expired", "disconnected"]
    project_ids: Annotated[tuple[UUID, ...], Field(max_length=100)]


class ConnectionAssignment(Contract):
    project_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=100)]
    expected_generation: Revision

    @field_validator('project_ids')
    @classmethod
    def unique_projects(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('unique projects required')
        return value


class ConnectionRotation(Contract):
    expected_generation: Revision


# Ephemeral server-only capability. Deliberately not a Pydantic/public contract,
# not exportable to JSON, and never stored in an application table.
class SecretHandle:
    __slots__ = ('connection_id', 'generation', '__token')

    def __init__(self, *, connection_id: UUID, generation: int, token: str):
        if (not isinstance(connection_id, UUID) or type(generation) is not int or generation < 1
                or not isinstance(token, str) or not 1 <= len(token) <= 8192
                or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ValueError('invalid credential handle')
        self.connection_id, self.generation, self.__token = connection_id, generation, token

    def _authorization(self):
        return 'Bearer ' + self.__token

    def __repr__(self):
        return 'SecretHandle(<redacted>)'


XverumTool = ContactTool


class XverumPersonCard(Contract):
    id: ShortText
    full_name: Text
    social_url: Text | None
    headline: Text | None
    location: Text | None
    company_name: Text | None
    position: Text | None
    industry: Text | None
    evidence_summary: Text


class XverumCompanyFields(Contract):
    social_url: Text | None
    company_name: Text | None
    slogan: Text | None
    headquarters: Text | None
    country_code: Text | None
    industry: Text | None
    employees_num: Credits | None
    website: Text | None
    founded: Credits | None


class XverumCompanyCard(XverumCompanyFields):
    id: ShortText


class XverumPeopleSearch(Contract):
    result_type: Literal['people']
    results: Annotated[tuple[XverumPersonCard, ...], Field(max_length=5)]
    total_count: Credits
    page: Annotated[StrictInt, Field(ge=1, le=1)]
    page_size: Annotated[StrictInt, Field(ge=1, le=5)]


class XverumCompanySearch(Contract):
    result_type: Literal['company']
    results: Annotated[tuple[XverumCompanyCard, ...], Field(max_length=5)]
    total_count: Credits
    page: Annotated[StrictInt, Field(ge=1, le=1)]
    page_size: Annotated[StrictInt, Field(ge=1, le=5)]


class XverumExperience(Contract):
    """Minimal employer/role chronology; no personal-background narratives."""
    position: Text | None
    company_name: Text | None
    start_time: Text | None
    end_time: Text | None


class XverumPersonDetail(Contract):
    full_name: Text
    social_url: Text | None
    headline: Text | None
    location: Text | None
    company_name: Text | None
    position: Text | None
    industry: Text | None
    evidence_summary: Text
    experience: Annotated[tuple[XverumExperience, ...], Field(max_length=100)]
    seniority: Text | None


class XverumLocation(Contract):
    address: Text | None = None
    address_2: Text | None = None
    primary: StrictBool | None = None


class XverumCompanyDetail(XverumCompanyFields):
    about_us: Text | None
    specialties: Annotated[tuple[Text, ...], Field(max_length=100)]
    locations: Annotated[tuple[XverumLocation, ...], Field(max_length=100)]
    type: Text | None
    social_followers: Credits | None


class XverumEmail(Contract):
    email: Annotated[str, StringConstraints(min_length=3, max_length=320)]
    confidence: Text | None
    last_checked: Text | None


class XverumBusinessEmail(Contract):
    has_email: StrictBool
    emails: Annotated[tuple[XverumEmail, ...], Field(max_length=100)]

    @model_validator(mode='after')
    def consistent_email(self):
        if self.has_email != bool(self.emails):
            raise ValueError('inconsistent email availability')
        return self


class XverumResult(Contract):
    tool: XverumTool
    request_id: Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_-]{1,128}$')]
    credits_used: Credits
    credits_remaining: Credits
    projection: XverumPeopleSearch | XverumCompanySearch | XverumPersonDetail | XverumCompanyDetail | XverumBusinessEmail

    @model_validator(mode='after')
    def matching_projection(self):
        if not isinstance(self.projection, XVERUM_PROJECTIONS[self.tool]):
            raise ValueError('tool projection mismatch')
        return self


XVERUM_PROJECTIONS = {
    'search_company_xverum': XverumCompanySearch, 'search_people_xverum': XverumPeopleSearch,
    'enrich_company_xverum': XverumCompanyDetail, 'enrich_person_xverum': XverumPersonDetail,
    'get_email_xverum': XverumBusinessEmail,
}


class QuoteRequest(Contract):
    stage: Literal["search", "detail"]
    buyer_id: UUID | None = None
    connection_id: UUID | None = None
    query: Annotated[str, StringConstraints(strip_whitespace=True,min_length=1,max_length=500)] | None = None
    target: Literal['company','people'] | None = None
    search_receipt_id: UUID | None = None
    selected_ids: Annotated[tuple[ShortText,...], Field(max_length=3)] = ()
    include_email: StrictBool = False

    @model_validator(mode='after')
    def staged_input(self):
        if self.stage=='search':
            if None in (self.buyer_id,self.connection_id,self.query,self.target) or self.search_receipt_id or self.selected_ids or self.include_email:
                raise ValueError('search requires exact query and buyer, never future selection')
        elif (self.search_receipt_id is None or not self.selected_ids or
              any(x is not None for x in (self.buyer_id,self.connection_id,self.query,self.target))):
            raise ValueError('detail requires a search receipt and explicit selection')
        if self.selected_ids and (len(set(self.selected_ids))!=len(self.selected_ids) or
            any(not i.isascii() or not i.isdecimal() for i in self.selected_ids)):
            raise ValueError('selected provider IDs must be unique numeric identities')
        return self


class EventPage(Contract):
    events: Annotated[tuple[TaskEvent, ...], Field(max_length=100)]
    next_sequence: Revision | None


class OutputPage(Contract):
    outputs: Annotated[tuple[OutputVersion, ...], Field(max_length=100)]
    next_revision: Revision | None


class SkillPage(Contract):
    skills: tuple[SkillDefinition, ...]


class ConnectionPage(Contract):
    connections: Annotated[tuple[ConnectionBinding, ...], Field(max_length=100)]


class ErrorResponse(Contract):
    """Native api.errors.error_body shape, including validation/server errors."""
    code: str
    message: str
    request_id: str
    retryable: StrictBool


class TaskMutationHeaders(Contract):
    """Selected native headers; create targets thread version, cancel task revision."""
    idempotency_key: Annotated[str, StringConstraints(min_length=8, max_length=200)] = Field(alias="Idempotency-Key")
    if_match: Annotated[str, StringConstraints(pattern=r'^"[1-9][0-9]*"$')] = Field(alias="If-Match")


class OutputListQuery(Contract):
    native_surface: Literal["profile", "buyer", "list", "run", "draft", "document", "export"] | None = None
    native_id: UUID | None = None
    offset: Annotated[StrictInt, Field(ge=0, le=10000)] = 0
    limit: Annotated[StrictInt, Field(ge=1, le=100)] = 50

    @model_validator(mode="after")
    def paired_native_filter(self):
        if (self.native_surface is None) != (self.native_id is None):
            raise ValueError("native_surface and native_id must be provided together")
        return self


class OutputReadQuery(Contract):
    revision: Revision | None = None


class OutputCollectionPage(Contract):
    """ACL-filtered latest outputs, distinct from a single output's version history."""
    items: Annotated[tuple[OutputVersion, ...], Field(max_length=100)]
    total: Credits
    offset: Annotated[StrictInt, Field(ge=0, le=10000)]
    limit: Annotated[StrictInt, Field(ge=1, le=100)]


class LiveResponse(Contract):
    """Native api.errors.envelope metadata; data is typed by each response."""
    request_id: str
    data_mode: Literal["live"]


class SkillPageResponse(LiveResponse):
    data: SkillPage


class TaskRecordResponse(LiveResponse):
    data: TaskRecord


class TaskDetailResponse(LiveResponse):
    data: TaskDetail


class TaskCollectionResponse(LiveResponse):
    data: TaskCollectionPage


class EventPageResponse(LiveResponse):
    data: EventPage


class OutputVersionResponse(LiveResponse):
    data: OutputVersion


class OutputPageResponse(LiveResponse):
    data: OutputPage


class OutputCollectionResponse(LiveResponse):
    data: OutputCollectionPage


class ConnectionPageResponse(LiveResponse):
    data: ConnectionPage


class ConnectionBindingResponse(LiveResponse):
    data: ConnectionBinding


class XverumQuoteResponse(LiveResponse):
    data: XverumQuote


class XverumReceiptResponse(LiveResponse):
    data: XverumReceipt


class XverumLiabilityResponse(LiveResponse):
    data: XverumLiability


class EnrichmentProposalResponse(LiveResponse):
    data: EnrichmentProposal


class NativeRefResponse(LiveResponse):
    data: NativeRef


class OutputReviewResponse(LiveResponse):
    data: OutputReview


def contract_schemas() -> dict:
    """Deterministic Pydantic schema export for the additive OpenAPI document."""
    models = [value for value in globals().values()
              if isinstance(value, type) and issubclass(value, Contract) and value is not Contract]
    schemas = {}
    for model in models:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        schemas[model.__name__] = schema
    # Express tagged relationships in JSON Schema too; generated clients must
    # not accept a pipeline kind with research content or arbitrary arguments.
    def tagged(name, tag, payload, choices):
        schemas[name].setdefault("allOf", []).append({"oneOf": [
            {"properties": {tag: {"const": key}, payload: {"$ref": "#/components/schemas/" + model.__name__}},
             "required": [tag, payload]}
            for key, model in choices.items()
        ]})
    tagged("OutputCandidate", "kind", "content", OUTPUT_MODELS)
    tagged("TaskEvent", "kind", "payload", {
        "progress": ProgressPayload, "state": StatePayload, "output": OutputPayload,
        "review": PendingReview, "error": ErrorPayload})
    tagged("ActionProposal", "capability", "arguments", ACTION_MODELS)
    tagged("ToolPlanItem", "tool", "arguments", {key: ACTION_MODELS[key] for key in CONTACT_ALLOWLIST})
    tagged("XverumResult", "tool", "projection", XVERUM_PROJECTIONS)
    def intake_request_schema(value):
        # Request-only copies preserve omission at every depth. Keep nested
        # required fields and all constraints; never alter execution/read models.
        if isinstance(value, list):
            return [intake_request_schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key == "default":
                continue
            if key == "$ref" and item.startswith("#/components/schemas/"):
                original = item.rsplit("/", 1)[-1]
                name = "IntakeValue" + original
                if name not in schemas:
                    schemas[name] = {}  # Break recursive references before cloning.
                    schemas[name] = intake_request_schema(schemas[original])
                result[key] = "#/components/schemas/" + name
            else:
                result[key] = intake_request_schema(item)
        return result

    for model in INPUT_MODELS.values():
        partial = intake_request_schema(schemas[model.__name__])
        partial.pop("required", None)
        schemas["Intake" + model.__name__] = partial
    schemas["TaskFollowup"]["properties"]["source_refs"].pop("default", None)
    # The tagged branch owns the exact argument object; an index signature here
    # would erase TypeScript's rejection of unknown supplied intake keys.
    schemas["TaskInput"]["properties"]["arguments"] = {}
    from .sections import section_groups, section_model
    section_choices = []
    for kind in OUTPUT_MODELS:
        for section in section_groups(kind):
            model = section_model(kind, section)
            schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
            schemas.update(schema.pop("$defs", {}))
            schemas[model.__name__] = schema
            section_choices.append({"properties":{"kind":{"const":kind}, "section":{"const":section},
                "content":{"$ref":"#/components/schemas/" + model.__name__}},
                "required":["kind","section","content"]})
    schemas["SalesSectionCandidate"]["properties"]["content"] = {}
    schemas["SalesSectionCandidate"]["allOf"] = [{"oneOf":section_choices}]
    schemas["TaskInput"].setdefault("allOf", []).append({"oneOf": [
        {"properties": {"skill_id": {"const": key}, "arguments": {"$ref": "#/components/schemas/Intake" + model.__name__}},
         "required": ["skill_id", "arguments"]} for key, model in INPUT_MODELS.items()]})
    tagged("SalesModelRequest", "skill_id", "arguments", INPUT_MODELS)
    for name in ("TaskInput", "SalesModelRequest"):
        schemas[name]["properties"]["skill_version"] = {"type": "string", "const": "1"}
    for name in ("ResearchArguments", "QuickArguments"):
        schemas[name]["anyOf"] = [
            {"required": ["buyer_id"], "properties": {"buyer_id": {"type": "string", "format": "uuid"}}},
            {"required": ["research_question"], "properties": {"research_question": {"type": "string", "minLength": 1}}},
        ]
    schemas["OutputVersion"]["allOf"] = [{"oneOf": [
        {"properties": {"availability": {"const": "available"}}, "allOf": [
            {"oneOf": [{"properties": {"kind": {"const": kind},
                "content": {"$ref": "#/components/schemas/" + model.__name__}}}
                for kind, model in OUTPUT_MODELS.items()]}
        ]},
        {"properties": {"availability": {"enum": ["source_deleted", "permission_revoked", "retention_expired", "unavailable"]},
            "content": {"type": "null"}, "citations": {"maxItems": 0},
            "dependencies": {"maxItems": 0}, "native_refs": {"maxItems": 0}}},
    ]}]
    schemas["TaskRecord"]["allOf"] = [{
        "if": {"properties": {"state": {"const": "completed"}}},
        "then": {"properties": {"output_ids": {"minItems": 1}, "pending_review": {"type": "null"}}},
    }]
    schemas["OutputListQuery"]["oneOf"] = [
        {"properties": {"native_surface": {"type": "null"}, "native_id": {"type": "null"}}},
        {"required": ["native_surface", "native_id"], "properties": {
            "native_surface": {"type": "string"}, "native_id": {"type": "string", "format": "uuid"}}},
    ]
    schemas['QuoteRequest']['oneOf'] = [
        {'required':['stage','buyer_id','connection_id','query','target'],
         'properties':{'stage':{'const':'search'},'buyer_id':{'type':'string','format':'uuid'},
             'connection_id':{'type':'string','format':'uuid'},'query':{'type':'string','minLength':1,'maxLength':500},
             'target':{'enum':['company','people']},'search_receipt_id':{'type':'null'},
             'selected_ids':{'type':'array','maxItems':0},'include_email':{'const':False}}},
        {'required':['stage','search_receipt_id','selected_ids'],
         'properties':{'stage':{'const':'detail'},'search_receipt_id':{'type':'string','format':'uuid'},
             'selected_ids':{'type':'array','minItems':1,'maxItems':3,'uniqueItems':True,
                 'items':{'type':'string','pattern':'^[0-9]+$'}},
             'buyer_id':{'type':'null'},'connection_id':{'type':'null'},'query':{'type':'null'},'target':{'type':'null'}}},
    ]
    return dict(sorted(schemas.items()))



class StepReceipt(Contract):
    id: UUID
    task_id: UUID | None
    dispatch_state: Literal['queued','submitting','received','failed','cancelled','unknown']
    native_operation_id: UUID | None
    reservation_ids: Annotated[tuple[UUID, ...], Field(min_length=1,max_length=1)]


class ExecutionReview(Contract):
    id: UUID
    task_id: UUID
    revision: Revision
    fingerprint: Digest
    expires_at: AwareDatetime
    max_calls: Annotated[StrictInt, Field(ge=1,le=8)]
    max_concurrency: Annotated[StrictInt, Field(ge=1,le=2)]
    max_liability_usd: Decimal


class StepAdmission(Contract):
    proposal: ActionProposal
    review_id: UUID


class StepReceiptResponse(LiveResponse):
    data: StepReceipt


class ExecutionReviewResponse(LiveResponse):
    data: ExecutionReview


class StepReviewInput(Contract):
    proposal: ActionProposal
    fingerprint: Digest


class ExecutionPreview(Contract):
    model_id: Text
    route: Text
    task_id: UUID
    revision: Revision
    fingerprint: Digest
    max_calls: Annotated[StrictInt, Field(ge=1,le=8)]
    max_concurrency: Annotated[StrictInt, Field(ge=1,le=2)]
    max_liability_usd: Decimal


class ExecutionPreviewResponse(LiveResponse):
    data: ExecutionPreview


class StepCollection(Contract):
    items: Annotated[tuple[StepReceipt, ...], Field(max_length=16)]


class StepCollectionResponse(LiveResponse):
    data: StepCollection


class CoreWork(Contract):
    steps: Annotated[StrictInt,Field(ge=1,le=16)]
    model_calls: Literal[0]
    provider_calls: Literal[0]
    max_concurrent_steps: Literal[1]
    model_liability_usd: Literal['0']
    native_provider_liability: Text
    discovery: Text


class CoreDestination(Contract):
    operation_id: Literal['startRun','getProject','generateDraft','changeListMemberships']
    workspace_id: UUID
    project_id: UUID
    task_id: UUID
    requires_human_review: Literal[True] = True
    idempotency_key: ShortText
    result_followup_operation: Literal['followupSalesTask'] = 'followupSalesTask'


class CoreGuidance(Contract):
    state: Literal['needs_input','ready_for_review']
    missing_inputs: tuple[ShortText,...]
    action: CoreDestination
    work: CoreWork


class CoreGuidanceResponse(LiveResponse):
    data: CoreGuidance


class FormalDraftInput(Contract):
    recipient_id: UUID
    expected_revision: Revision


class NativeEvidenceProof(Contract):
    id: UUID
    version: Revision
    source_id: UUID
    digest: Annotated[str,StringConstraints(min_length=1,max_length=80)]
    excerpt: Annotated[str,StringConstraints(min_length=1,max_length=800)]
    stance: Literal['supports','contradicts','qualifies','neutral']
    is_inference: StrictBool


class SalesCapability(Contract):
    admission_enabled: StrictBool


class SalesNativeSource(Contract):
    label: ShortText
    ref: SourceRef


class SalesNativeSources(Contract):
    items: tuple[SalesNativeSource, ...]
