"""Offline sales contracts: widening authority or losing schema checks must fail."""
import importlib
import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
UID = "00000000-0000-4000-8000-000000000001"


def registry():
    try:
        return importlib.import_module("buyeros_api.sales.registry")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Task 2 registry is absent: {exc}")


def test_contacts_registry_is_allowlisted():
    r = registry()
    skill = r.load_skill("sales-contacts", "1")
    assert skill.allowed_actions == r.CONTACT_ALLOWLIST
    assert set(skill.allowed_actions) == {
        "search_company_xverum", "search_people_xverum",
        "enrich_company_xverum", "enrich_person_xverum", "get_email_xverum",
    }


def test_complete_catalogue_and_languages():
    r = registry()
    expected = {
        "sales-prospect", "sales-research", "sales-qualify", "sales-contacts",
        "sales-outreach", "sales-followup", "sales-prep", "sales-proposal",
        "sales-objections", "sales-icp", "sales-competitors", "sales-report",
        "sales-report-pdf", "first-project", "understand-documents", "review-buyers",
        "sales-quick",
    }
    catalogue = r.catalogue()
    assert {s.id for s in catalogue} == expected
    assert all(s.languages == ("en", "zh-HK") for s in catalogue)
    for skill in catalogue:
        assert skill.inputs_schema["additionalProperties"] is False
        assert r.output_schema(skill.output_kind)["additionalProperties"] is False
        with pytest.raises((ValueError, ValidationError)):
            r.validate_output(skill, {})
        with pytest.raises((ValueError, ValidationError)):
            r.validate_arguments(skill, {"workspace_id": UID})


@pytest.mark.parametrize("skill,version", [("missing", "1"), ("sales-research", "2"), ("../research", "1")])
def test_unknown_definition_fails_closed(skill, version):
    with pytest.raises(ValueError):
        registry().load_skill(skill, version)


def test_strict_inputs_and_immutable_definitions():
    r = registry()
    skill = r.load_skill("sales-research", "1")
    assert r.validate_arguments(skill, {"buyer_id": UID})["buyer_id"] == UID
    for args in ({"buyer_id": UID, "shell": "anything"}, {"buyer_id": "not-a-uuid"},
                 {"buyer_id": UID, "max_sources": True}, {"buyer_id": UID, "max_sources": 1000}):
        with pytest.raises((ValueError, ValidationError)):
            r.validate_arguments(skill, args)
    with pytest.raises((TypeError, ValidationError)):
        skill.version = "2"
    with pytest.raises(TypeError):
        skill.inputs_schema["properties"]["buyer_id"]["type"] = "integer"
    assert r.load_skill("sales-research", "1").version == "1"


@pytest.mark.parametrize("capability", ["get_phone_xverum", "find_person_by_email_xverum",
    "find_person_by_phone_xverum", "predict_job_change_xverum", "shell", "send_email"])
def test_disabled_capabilities_are_rejected(capability):
    r = registry()
    with pytest.raises(ValueError):
        r.validate_action(r.load_skill("sales-contacts", "1"), capability, {"id": "123"})


def test_contact_actions_are_typed_and_stage_specific():
    r = registry()
    skill = r.load_skill("sales-contacts", "1")
    assert r.validate_action(skill, "search_company_xverum", {"query": "Example", "page_size": 5})["page"] == 1
    for args in ({"query": "Example", "page": 2}, {"query": "Example", "page_size": 6},
                 {"query": "Example", "actor_id": UID}):
        with pytest.raises(ValueError):
            r.validate_action(skill, "search_company_xverum", args)
    with pytest.raises(ValueError):
        r.validate_action(skill, "enrich_person_xverum", {"query": "Example"})


def test_compatibility_and_bounded_alias():
    r = registry()
    assert dict(r.TEMPLATE_SKILLS) == {
        "first-project": "first-project", "understand-documents": "understand-documents",
        "research-market": "sales-research", "review-buyers": "review-buyers",
        "check-company": "sales-research", "prepare-follow-up": "sales-followup",
        "custom": "sales-prospect",
    }
    quick = r.load_skill("sales-quick", "1")
    assert quick.output_kind == r.load_skill("sales-research", "1").output_kind
    with pytest.raises(ValueError):
        r.validate_arguments(quick, {"buyer_id": UID, "max_sources": 4})


def test_unavailable_output_does_not_leak_content():
    registry()
    from buyeros_api.sales.contracts import OutputVersion
    base = dict(id=UID, revision=1, visibility="thread", native_refs=[], kind="research_report",
                content=None, citations=[], dependencies=[], availability="source_deleted")
    assert OutputVersion.model_validate(base).content is None
    with pytest.raises(ValidationError):
        OutputVersion.model_validate({**base, "content": {"summary": "secret"}})


def test_untrusted_contracts_reject_authority_and_raw_data():
    registry()
    from buyeros_api.sales.contracts import TaskInput, XverumReceipt, NativeRef, TaskEvent, ExecutionBounds
    with pytest.raises(ValidationError):
        TaskInput.model_validate(dict(thread_id=UID, skill_id="sales-research", skill_version="1",
            user_message="Research", source_refs=[], arguments={}, actor_id=UID))
    with pytest.raises(ValidationError):
        XverumReceipt.model_validate(dict(id=UID, dispatch_state="outcome_unknown", request_id=None,
            credits_used=None, held_credits=5, projection_digest=None, raw_response={}))
    with pytest.raises(ValidationError):
        NativeRef(surface="url", id=UUID(UID), revision=1)
    with pytest.raises(ValidationError):
        TaskEvent.model_validate(dict(task_id=UID, sequence=1, kind="progress", payload={"tokens": "secret"}))
    with pytest.raises(ValidationError):
        ExecutionBounds(max_steps=17)
    with pytest.raises(ValidationError):
        ExecutionBounds(max_model_calls=9)
    with pytest.raises(ValidationError):
        ExecutionBounds(max_concurrent_steps=3)


def test_output_evidence_and_pdf_revision_contract():
    r = registry()
    research = r.load_skill("sales-research", "1")
    content = dict(summary="Evidence is unavailable", findings=[], unknowns=["Company size"],
                   opportunities=[], concerns=[])
    candidate = dict(kind="research_report", content=content, citations=[], dependencies=[], native_refs=[])
    assert r.validate_output(research, candidate).content.summary == content["summary"]
    with pytest.raises(ValueError):
        r.validate_output(research, {**candidate, "kind": "pipeline_report"})
    pdf = r.load_skill("sales-report-pdf", "1")
    args = r.validate_arguments(pdf, {"output_id": UID, "output_revision": 3})
    assert args["output_revision"] == 3
    with pytest.raises(ValueError):
        r.validate_arguments(pdf, {"output_id": UID})
    result = dict(kind="report_export", content=dict(output_id=UID, output_revision=3,
                  export_ref=dict(surface='export',id=UID,revision=3), media_type="application/pdf"), citations=[],
                  dependencies=[dict(id=UID, revision=3)], native_refs=[dict(surface="export", id=UID, revision=3)])
    assert r.validate_output(pdf, result).content.output_revision == 3
    with pytest.raises(ValueError):
        r.validate_output(pdf, {**result, "dependencies": [dict(id=UID, revision=4)]})


def test_quote_cannot_turn_search_into_detail_or_float_credits():
    registry()
    from buyeros_api.sales.contracts import XverumQuote
    base = dict(id=UID, stage="search", actor_id=UID, connection_generation=1,
        query="Example", provider_ids=[], tool_plan=[dict(tool="search_company_xverum",
        arguments={"query": "Example", "page": 1, "page_size": 5})], max_credits=5,
        tariff_version="v1", expires_at="2026-11-05T12:00:00Z", fingerprint="a"*64,
        buyer_id=UID, connection_id=UID)
    assert XverumQuote.model_validate(base).max_credits == 5
    for change in ({"max_credits": 1.5}, {"provider_ids": ["123"]},
                   {"tool_plan": [dict(tool="enrich_company_xverum", arguments={"company_id": "123"})]}):
        with pytest.raises(ValidationError):
            XverumQuote.model_validate({**base, **change})


def test_provenance_matches_pinned_source_blobs():
    import hashlib
    r = registry()
    upstream = json.loads((ROOT / ".superpowers/sdd/2026-11-05-guided-sales-skills-xverum/upstream-source.json").read_text(encoding="utf-8"))
    provenance = json.loads((ROOT / "services/api/buyeros_api/sales/provenance.json").read_text(encoding="utf-8"))
    assert provenance["commit"] == "efef8b8a4ce8c93d8d6b4af9d1423db38f0de2ce"
    for source in upstream["files"]:
        data = source["content"].encode()
        blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        assert blob == source["blob"]
        assert provenance["sources"][source["path"]]["blob"] == blob
    assert len(provenance["sources"]) == 15
    for skill in r.catalogue():
        if skill.id.startswith("sales-"):
            assert skill.upstream_hash in {f["blob"] for f in upstream["files"]}


def test_openapi_schemas_match_python_contracts():
    r = registry()
    from buyeros_api.sales.contracts import contract_schemas
    api = json.loads((ROOT / "docs/buyeros/contracts/sales.openapi.yaml").read_text())
    documented = api['components']['schemas']
    runtime = contract_schemas()
    # Explicit response-only shapes are owned by the Task13 OpenAPI contract.
    route_only = {'OutputPermissions','OutputPermissionsResponse','XverumCandidates',
        'XverumCandidatesResponse','XverumTaskStage','XverumTaskStages','XverumTaskStagesResponse'}
    assert documented.keys() - runtime.keys() == route_only
    assert runtime.keys() - documented.keys() == {'PurgeReceipt'}  # internal service, no HTTP route
    assert {k:v for k,v in documented.items() if k not in route_only} == {
        k:v for k,v in runtime.items() if k != 'PurgeReceipt'}
    assert documented['XverumTaskStages']['properties']['items']['maxItems'] == 16
    assert documented['XverumCandidates']['oneOf'] == [
        {'$ref':'#/components/schemas/XverumCompanySearch'},
        {'$ref':'#/components/schemas/XverumPeopleSearch'}]
    for skill in r.catalogue():
        assert skill.inputs_schema == api["components"]["schemas"][r.INPUT_MODELS[skill.id].__name__]

SOURCE = dict(id=UID, version=1, kind="project_fact", locator="fact:offer", retention_class="durable")
FINDING = dict(statement="Selected business evidence", evidence=[SOURCE], confidence="high", observed_at=None)
MESSAGE = dict(subject="A useful next step", body="Evidence-based proposed next step.",
               rationale="Selected offer", evidence=[SOURCE], suggested_day=1)
TERMS = dict(price={"amount": "100.00", "currency": "USD"}, scope="Pilot",
             exclusions="Additional work", timeline="Four weeks", evidence=[SOURCE])


def valid_cases():
    authored = dict(summary="A reviewable result", unknowns=[])
    return {
        "sales-prospect": (dict(buyer_id=UID, objective="Assess buyer"), "research_report",
            {**authored, "findings": [FINDING], "opportunities": [], "concerns": []}),
        "sales-research": (dict(buyer_id=UID), "research_report",
            {**authored, "findings": [FINDING], "opportunities": [], "concerns": []}),
        "sales-quick": (dict(buyer_id=UID), "research_report",
            {**authored, "findings": [FINDING], "opportunities": [], "concerns": []}),
        "sales-qualify": (dict(buyer_id=UID, profile_id=UID, profile_version=1), "qualification_assessment",
            {**authored, "rubric": "BANT_MEDDIC", "dimensions": [
                dict(dimension="budget", score=None, rationale="Unknown", evidence=[])],
             "next_questions": ["What budget has been confirmed?"]}),
        "sales-contacts": (dict(buyer_id=UID, purpose="Professional purchasing research", roles=["Purchasing"]),
            "enrichment_proposal", dict(id=UID, buyer_id=UID, buyer_version=1,
                identity_match="unresolved", fields=[], source_refs=[SOURCE])),
        "sales-outreach": (dict(buyer_id=UID, profile_id=UID, objective="Prepare introduction"),
            "outreach_preparation", {**authored, "framework": "direct", "messages": [MESSAGE]}),
        "sales-followup": (dict(buyer_id=UID, profile_id=UID, objective="Recap", interaction_ref=SOURCE,
            scenario="post_meeting"), "followup_preparation", {**authored, "scenario": "post_meeting",
            "interaction_ref": SOURCE, "messages": [MESSAGE]}),
        "sales-prep": (dict(buyer_id=UID, meeting_at="2026-11-06T12:00:00Z", objective="Discovery"),
            "meeting_brief", {**authored, "cheat_sheet": "Review stated needs", "attendees": [FINDING],
            "talking_points": ["Offer fit"], "discovery_questions": ["What is your priority?"],
            "agenda": [dict(topic="Discovery", minutes=30)], "next_steps": ["Agree scope"]}),
        "sales-proposal": (dict(buyer_id=UID, profile_id=UID, pain_points=["Manual work"], terms=[TERMS]),
            "sales_proposal", {**authored, "problem": "Manual work", "solution": "Pilot",
            "terms": [TERMS], "assumptions": [], "proof_points": [FINDING], "followup": []}),
        "sales-objections": (dict(profile_id=UID, objections=["Timing"]), "objection_playbook",
            {**authored, "responses": [dict(objection="Timing", feel_felt_found="I understand.",
                acknowledge_bridge_close="Let's clarify timing.", followup_question="When is useful?",
                walk_away_criteria="No interest", proof_points=[FINDING])]}),
        "sales-icp": (dict(offer_description="Operations service"), "profile_proposal",
            {**authored, "criteria": [FINDING], "exclusions": [], "personas": ["Purchasing role"]}),
        "sales-competitors": (dict(buyer_id=UID, profile_id=UID), "competitive_document",
            {**authored, "competitors": [FINDING], "strengths": [], "gaps": [], "switching_costs": []}),
        "sales-report": (dict(as_of="2026-11-05T12:00:00Z", buyer_ids=[UID]), "pipeline_report",
            {**authored, "as_of": "2026-11-05T12:00:00Z", "scope": [UID], "rows": [],
            "unavailable_buyer_ids": [UID], "methodology": "Selected native records only"}),
        "sales-report-pdf": (dict(output_id=UID, output_revision=3), "report_export",
            dict(output_id=UID, output_revision=3, export_ref=dict(surface='export',id=UID,revision=3), media_type="application/pdf")),
        "first-project": (dict(offer_description="Operations service"), "project_setup",
            {**authored, "offer": "Operations service", "missing_fields": [], "next_steps": ["Review profile"]}),
        "understand-documents": (dict(document_ids=[UID], question="What does this support?"),
            "document_understanding", {**authored, "document_ids": [UID], "findings": [FINDING],
            "extraction_status": "complete"}),
        "review-buyers": (dict(buyer_ids=[UID], profile_id=UID, profile_version=1), "buyer_review",
            {**authored, "assessments": [FINDING], "proposed_buyer_ids": [UID]}),
    }


@pytest.mark.parametrize("skill_id", list(valid_cases()))
def test_each_skill_accepts_native_inputs_and_validated_output(skill_id):
    r = registry()
    args, kind, content = valid_cases()[skill_id]
    skill = r.load_skill(skill_id, "1")
    validated = r.validate_arguments(skill, args)
    assert validated["language"] == "en"
    assert r.validate_arguments(skill, {**args, "language": "zh-HK"})["language"] == "zh-HK"
    candidate = dict(kind=kind, content=content, citations=[SOURCE], dependencies=[], native_refs=[])
    if skill_id == "sales-report-pdf":
        candidate.update(dependencies=[dict(id=UID, revision=3)],
                         native_refs=[dict(surface="export", id=UID, revision=3)])
    output = r.validate_output(skill, candidate)
    assert output.kind == kind
    assert r.playbook(skill).strip()
    with pytest.raises(ValueError):
        r.validate_output(skill, {**candidate, "content": {**content, "send_now": True}})


def test_evidence_cannot_be_uncited_or_restricted():
    r = registry()
    _, kind, content = valid_cases()["sales-research"]
    candidate = dict(kind=kind, content=content, citations=[], dependencies=[], native_refs=[])
    with pytest.raises(ValueError):
        r.validate_output(r.load_skill("sales-research", "1"), candidate)
    restricted = {**SOURCE, "kind": "drive", "retention_class": "zero_content"}
    with pytest.raises(ValueError):
        r.validate_output(r.load_skill("sales-research", "1"), {**candidate, "citations": [restricted],
            "content": {**content, "findings": [{**FINDING, "evidence": [restricted]}]}})


def test_snapshot_connection_generations_are_immutable():
    registry()
    from buyeros_api.sales.contracts import ContextSnapshot
    snapshot = ContextSnapshot.model_validate(dict(refs=[SOURCE], digest="a"*64,
        profile_version=1, connection_generations={UID: 1}))
    with pytest.raises(TypeError):
        snapshot.connection_generations[UUID(UID)] = 2


def test_unknown_scores_and_incomplete_pipeline_are_rejected():
    registry()
    from buyeros_api.sales.contracts import AssessmentDimension, PipelineReport
    with pytest.raises(ValidationError):
        AssessmentDimension(dimension="budget", score=50, rationale="No data", evidence=[])
    with pytest.raises(ValidationError):
        PipelineReport.model_validate(dict(summary="Pipeline", unknowns=[], as_of="2026-11-05T12:00:00Z",
            scope=[UID], rows=[], unavailable_buyer_ids=[], methodology="Selected records"))


def test_schema_rejects_mismatched_output_and_untyped_skill_arguments():
    import jsonschema
    api = json.loads((ROOT / "docs/buyeros/contracts/sales.openapi.yaml").read_text(encoding="utf-8"))
    def validator(name):
        return jsonschema.Draft202012Validator({"$ref": "#/components/schemas/" + name,
            "components": api["components"]}, format_checker=jsonschema.FormatChecker())
    _, _, content = valid_cases()["sales-research"]
    wrong = dict(kind="pipeline_report", content=content, citations=[], dependencies=[], native_refs=[])
    assert list(validator("OutputCandidate").iter_errors(wrong))
    task = dict(thread_id=UID, skill_id="sales-contacts", skill_version="1", user_message="Research",
        source_refs=[], arguments={"shell": "anything"})
    assert list(validator("TaskInput").iter_errors(task))
    for skill_id, (args, kind, content) in valid_cases().items():
        task.update(skill_id=skill_id, arguments=args)
        validator("TaskInput").validate(task)


def test_detail_quotes_bind_selected_ids_and_preserve_unknown_liability():
    registry()
    from buyeros_api.sales.contracts import XverumQuote, XverumReceipt
    base = dict(id=UID, stage="detail", actor_id=UID, connection_generation=1, query=None,
        provider_ids=["person-1"], tool_plan=[dict(tool="get_email_xverum", arguments={"id": "person-1"})],
        max_credits=2, tariff_version="v1", expires_at="2026-11-06T12:00:00Z",
        fingerprint="a"*64, buyer_id=UID, connection_id=UID)
    assert XverumQuote.model_validate(base).stage == "detail"
    for change in ({"provider_ids": ["person-2"]}, {"max_credits": 1},
                   {"tool_plan": base["tool_plan"] * 2}):
        with pytest.raises(ValidationError):
            XverumQuote.model_validate({**base, **change})
    receipt = dict(id=UID, dispatch_state="outcome_unknown", request_id=None,
        credits_used=None, held_credits=2, projection_digest=None)
    assert XverumReceipt.model_validate(receipt).held_credits == 2
    for change in ({"held_credits": 0}, {"credits_used": 0}):
        with pytest.raises(ValidationError):
            XverumReceipt.model_validate({**receipt, **change})


def test_completed_task_requires_output_and_no_pending_review():
    registry()
    from buyeros_api.sales.contracts import TaskRecord
    record = dict(id=UID, state="completed", revision=1, context_digest="a"*64,
        output_ids=[UID], pending_review=None)
    assert TaskRecord.model_validate(record).state == "completed"
    for change in ({"output_ids": []}, {"pending_review": {"id": UID, "kind": "cost", "revision": 1}}):
        with pytest.raises(ValidationError):
            TaskRecord.model_validate({**record, **change})


def test_review_round1_visibility_defaults_to_thread():
    registry()
    from buyeros_api.sales.contracts import OutputSave, OutputVersion
    candidate = dict(kind="project_setup", content={"summary": "Setup", "unknowns": [],
        "offer": "Service", "missing_fields": [], "next_steps": ["Review"]},
        citations=[], dependencies=[], native_refs=[])
    payload = dict(task_id=UID, expected_task_revision=1, candidate=candidate)
    assert OutputSave.model_validate(payload).visibility == "thread"
    for visibility in ("thread", "project"):
        assert OutputSave.model_validate({**payload, "visibility": visibility}).visibility == visibility
        result = dict(id=UID, revision=1, visibility=visibility, availability="available", **candidate)
        assert OutputVersion.model_validate(result).visibility == visibility
    with pytest.raises(ValidationError):
        OutputSave.model_validate({**payload, "visibility": "private"})
    with pytest.raises(ValidationError):
        OutputVersion.model_validate({**result, "visibility": "private"})


def test_review_round1_filters_and_latest_query_are_typed():
    registry()
    from buyeros_api.sales.contracts import OutputListQuery, OutputReadQuery
    assert OutputReadQuery().revision is None
    assert OutputReadQuery(revision=3).revision == 3
    assert OutputListQuery(native_surface="buyer", native_id=UID).native_id == UUID(UID)
    for values in ({"native_surface": "buyer"}, {"native_id": UID}, {"native_surface": "url", "native_id": UID},
                   {"native_surface": "buyer", "native_id": "wrong"}, {"limit": 101}, {"offset": -1}):
        with pytest.raises(ValidationError):
            OutputListQuery.model_validate(values)
    for revision in (0, -1, True):
        with pytest.raises(ValidationError):
            OutputReadQuery(revision=revision)


def test_review_round1_header_contract_matches_native_errors():
    registry()
    from types import SimpleNamespace
    from starlette.requests import Request
    from buyeros_api.api.idempotency import if_match_version
    from buyeros_api.api.errors import ApiError
    from buyeros_api.api.routes.conversation_threads import bump
    from buyeros_api.sales.contracts import TaskMutationHeaders
    headers = {"Idempotency-Key": "opaque-key-123", "If-Match": '"4"'}
    assert TaskMutationHeaders.model_validate(headers).if_match == '"4"'
    assert if_match_version(headers["If-Match"]) == 4
    for missing in ("If-Match", "Idempotency-Key"):
        with pytest.raises(ValidationError):
            TaskMutationHeaders.model_validate({k: v for k, v in headers.items() if k != missing})
    for value in (None, "", "4", 'W/"4"', '"0"', '"01"', "*"):
        with pytest.raises(ValidationError):
            TaskMutationHeaders.model_validate({**headers, "If-Match": value})
        with pytest.raises(ApiError) as error:
            if_match_version(value)
        assert (error.value.status_code, error.value.code) == (400, "INVALID_REQUEST")
    request = Request({"type": "http", "headers": [(b"if-match", b'"3"')]})
    with pytest.raises(ApiError) as error:
        bump(SimpleNamespace(version=4), request)
    assert (error.value.status_code, error.value.code) == (409, "STALE_REVISION")


def test_review_round1_native_envelopes_validate_against_response_schemas():
    import jsonschema
    from starlette.requests import Request
    from buyeros_api.api.errors import envelope, error_body
    from buyeros_api.sales.contracts import contract_schemas
    schemas = contract_schemas()
    def validator(name):
        return jsonschema.Draft202012Validator({"$ref": "#/components/schemas/" + name,
            "components": {"schemas": schemas}})
    task = dict(id=UID, state="needs_input", revision=1, context_digest=None, output_ids=[], pending_review=None)
    success = envelope(task, UID)
    validator("TaskRecordResponse").validate(success)
    assert list(validator("TaskRecordResponse").iter_errors(task))
    for change in ({"data_mode": "demo"}, {"data": {"id": UID}}):
        assert list(validator("TaskRecordResponse").iter_errors({**success, **change}))
    request = Request({"type": "http", "headers": [], "state": {"request_id": UID}})
    error = error_body(request, code="STALE_REVISION", message="changed")
    validator("ErrorResponse").validate(error)
    for missing in ("retryable", "request_id"):
        assert list(validator("ErrorResponse").iter_errors({k: v for k, v in error.items() if k != missing}))


def test_review_round1_openapi_transport_matches_python_components():
    import jsonschema
    api = json.loads((ROOT / "docs/buyeros/contracts/sales.openapi.yaml").read_text(encoding="utf-8"))
    prefix = "/workspaces/{workspace_id}/projects/{project_id}"
    for suffix in ("/sales-tasks", "/sales-tasks/{task_id}/cancel"):
        operation = api["paths"][prefix + suffix]["post"]
        headers = [p for p in operation["parameters"] if p["in"] == "header"]
        model = api["components"]["schemas"]["TaskMutationHeaders"]
        for param in headers:
            assert param["schema"] == model["properties"][param["name"]]
            assert param["required"]
    query = api["components"]["schemas"]["OutputListQuery"]
    validator = jsonschema.Draft202012Validator(query, format_checker=jsonschema.FormatChecker())
    validator.validate({"native_surface": "buyer", "native_id": UID})
    assert list(validator.iter_errors({"native_id": UID}))





def test_r1_section_assembly_map_covers_every_field_without_relaxing_full_output():
    from buyeros_api.sales.contracts import OUTPUT_MODELS, OutputCandidate
    from buyeros_api.sales.sections import section_groups, SERVER_DEFAULTS
    for kind,model in OUTPUT_MODELS.items():
        fields=[field for group in section_groups(kind).values() for field in group]
        owned=set(model.model_fields) & SERVER_DEFAULTS
        assert len(fields)==len(set(fields))
        assert set(fields) | owned == set(model.model_fields)
        defaults={'setup_basis':None,'filters':{},'record_basis':(),'document_basis':()}
        assert all(model.model_fields[field].default == defaults.get(field,True) for field in owned)
        assert len(section_groups(kind))<=8
    with pytest.raises(ValueError):
        OutputCandidate.model_validate({'kind':'sales_proposal','content':{'solution':'Only a child'},
            'citations':[],'dependencies':[],'native_refs':[]})


def test_r3_request_omission_does_not_change_full_arguments_or_readback():
    from buyeros_api.sales.contracts import contract_schemas, TaskInput, TaskFollowup, TaskDetail
    schemas=contract_schemas()
    for name in ('IntakeProjectArguments','IntakeQuickArguments'):
        assert not schemas[name].get('required')
        assert all('default' not in value for value in schemas[name]['properties'].values())
    assert 'default' not in schemas['TaskFollowup']['properties']['source_refs']
    assert schemas['ProjectArguments']['properties']['language']['default']=='en'
    assert 'offer_description' in schemas['ProjectArguments']['required']
    assert schemas['IntakeProspectArguments']['properties']['bounds']['$ref'].endswith('/IntakeValueExecutionBounds')
    assert 'default' not in schemas['IntakeValueExecutionBounds']['properties']['max_steps']
    assert schemas['ExecutionBounds']['properties']['max_steps']['default']==16
    assert set(schemas['TaskDetail']['required']) >= {'intake','arguments','source_refs','missing_inputs'}
    assert TaskFollowup(user_message='Synthetic',arguments={}).source_refs is None
    for skill_id in ('first-project','sales-quick'):
        assert TaskInput(thread_id=UID,skill_id=skill_id,skill_version='1',user_message='Synthetic',
            source_refs=[],arguments={}).arguments=={}
