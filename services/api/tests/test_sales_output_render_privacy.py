"""Backend privacy: saved-output preview renders only whitelisted human fields.

Pre-existing renderer leak surfaced by the inline preview: the old renderer walked
the whole content model, including ``SourceRef`` evidence (UUIDs/locators),
native ids and internal basis maps. These tests fix the contract of
``render_output``: human labels remain; no internal reference is emitted.
"""
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from buyeros_api.sales.contracts import (AgendaItem, AssessmentDimension, BuyerReview,
    CommercialTerms,
    DocumentUnderstanding, Finding, FollowupPreparation, MeetingBrief, Money,
    NativeRef, ObjectionPlaybook, ObjectionResponse, OutputDependency, OutputVersion,
    OutreachPreparation, PipelineReport, PipelineRow, PreparedMessage, ProfileProposal,
    QualificationAssessment, ReportExport, ResearchReport, SalesProposal, SourceRef)
from buyeros_api.services.sales_outputs import render_output

UUID_PATTERN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)


def ref(kind='document'):
    value = uuid.uuid4()
    return SourceRef(id=value, version=1, kind=kind,
        locator=f'{kind}:{value}', retention_class='durable')


def finding(evidence):
    return Finding(statement='Human finding statement', evidence=(evidence,),
        confidence='high', observed_at=datetime(2026, 11, 9, tzinfo=timezone.utc))


def prepared(evidence):
    return PreparedMessage(subject='Human message subject', body='Human message body',
        rationale='Human message rationale', evidence=(evidence,), suggested_day=2)


def version(kind, content, *, citations=(), dependencies=(), native_refs=()):
    return OutputVersion(id=uuid.uuid4(), revision=1, visibility='thread',
        native_refs=tuple(native_refs), kind=kind, content=content,
        citations=tuple(citations), dependencies=tuple(dependencies),
        availability='available')


def assert_no_internal_refs(html, strings=()):
    assert UUID_PATTERN.search(html) is None, html
    for value in strings:
        assert value not in html
    for marker in ('source_refs', 'retention_class', 'interaction_ref',
                   'document_basis', 'record_basis', 'buyer_id', 'document_ids',
                   'proposed_buyer_ids', 'buyer_version', 'profile_id', 'locator'):
        assert marker not in html, marker


def test_sales_proposal_preview_keeps_human_labels_and_hides_evidence():
    document, fact = ref('document'), ref('project_fact')
    terms = CommercialTerms(price=Money(amount=Decimal('1200.00'), currency='USD'),
        scope='Commercial scope text', exclusions='Commercial exclusions text',
        timeline='Four weeks', evidence=(document,))
    output = version('sales_proposal', SalesProposal(
        summary='Human summary text', unknowns=('Human unknown text',),
        problem='Human problem text', solution='Human solution text', terms=(terms,),
        assumptions=('Human assumption text',),
        proof_points=(finding(fact),), followup=(prepared(document),)), citations=(document, fact))
    html = render_output(output)
    for text in ('Human summary text', 'Human problem text', 'Human solution text',
                 'Human finding statement', 'Human message body', 'Commercial scope text',
                 'Commercial exclusions text', 'Human unknown text'):
        assert text in html
    assert_no_internal_refs(html, (str(document.id), str(fact.id), document.locator,
        fact.locator, 'document:', 'project_fact:'))
    assert 'Evidence' not in html and 'evidence' not in html


@pytest.mark.parametrize('builder', [
    lambda evidence: version('research_report', ResearchReport(
        summary='Research summary', unknowns=('Research unknown',),
        findings=(finding(evidence),), opportunities=('Opportunity text',),
        concerns=('Concern text',)), citations=(evidence,)),
    lambda evidence: version('followup_preparation', FollowupPreparation(
        summary='Followup summary', unknowns=(), scenario='post_demo',
        interaction_ref=evidence, messages=(prepared(evidence),)), citations=(evidence,)),
    lambda evidence: version('document_understanding', DocumentUnderstanding(
        summary='Document summary', unknowns=(), document_ids=(uuid.uuid4(),),
        findings=(finding(evidence),), extraction_status='complete',
        document_basis=({'document_id': str(uuid.uuid4()), 'sha256': 'a' * 64},),
        extracted_passages=('Human passage text',), question='Human question text'),
        citations=(evidence,)),
    lambda evidence: version('pipeline_report', PipelineReport(
        summary='Pipeline summary', unknowns=(),
        as_of=datetime(2026, 11, 9, tzinfo=timezone.utc),
        scope=(pipeline_buyer := uuid.uuid4(),),
        rows=(PipelineRow(buyer=NativeRef(surface='buyer', id=pipeline_buyer,
            revision=1), stage='Qualified', advisory_score=70,
            value=Money(amount=Decimal('5000'), currency='USD'),
            next_action='Human next action'),),
        unavailable_buyer_ids=(), methodology='Human methodology text',
        filters={'buyer_ids': [str(pipeline_buyer)]},
        record_basis=({'id': str(pipeline_buyer)},))),
    lambda evidence: version('objection_playbook', ObjectionPlaybook(
        summary='Objection summary', unknowns=(),
        responses=(ObjectionResponse(objection='Human objection text',
            feel_felt_found='Human feel text', acknowledge_bridge_close='Human bridge text',
            followup_question='Human followup question', walk_away_criteria='Human criteria',
            proof_points=(finding(evidence),)),)), citations=(evidence,)),
    lambda evidence: version('meeting_brief', MeetingBrief(
        summary='Meeting summary', unknowns=(), cheat_sheet='Human cheat sheet text',
        attendees=(finding(evidence),), talking_points=('Human talking point',),
        discovery_questions=('Human discovery question',),
        agenda=(AgendaItem(topic='Human agenda topic', minutes=15),),
        next_steps=('Human next step',)), citations=(evidence,)),
    lambda evidence: version('profile_proposal', ProfileProposal(
        summary='Profile summary', unknowns=(), criteria=(finding(evidence),),
        exclusions=('Human exclusion',), personas=('Human persona',)),
        citations=(evidence,)),
    lambda evidence: version('qualification_assessment', QualificationAssessment(
        summary='Qualification summary', unknowns=(), rubric='BANT_MEDDIC',
        dimensions=(AssessmentDimension(dimension='budget', score=50,
            rationale='Human dimension rationale', evidence=(evidence,)),),
        next_questions=('Human next question',)), citations=(evidence,)),
])
def test_other_output_kinds_render_no_internal_references(builder):
    evidence = ref('document')
    output = builder(evidence)
    html = render_output(output)
    assert_no_internal_refs(html, (str(evidence.id), evidence.locator, 'document:'))
    assert 'Human' in html


def test_report_export_preview_hides_output_ids_and_native_refs():
    output_id, export_id = uuid.uuid4(), uuid.uuid4()
    export_ref = NativeRef(surface='export', id=export_id, revision=1)
    output = version('report_export', ReportExport(output_id=output_id,
        output_revision=1, export_ref=export_ref, media_type='application/pdf'),
        dependencies=(OutputDependency(id=output_id, revision=1),), native_refs=(export_ref,))
    html = render_output(output)
    assert 'application/pdf' in html
    assert_no_internal_refs(html, (str(output_id), str(export_id), 'export:'))


def test_unavailable_output_preview_stays_generic():
    class Unavailable:
        availability = 'unavailable'
        content = None
    assert render_output(Unavailable()) == '<p>Output unavailable</p>'
