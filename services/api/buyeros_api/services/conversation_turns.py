"""Bounded conversation-turn orchestration inside one durable discussion.

One authenticated turn appends the user message exactly once, derives grounding
from the thread's persisted source selection, produces a deterministic plan from
the code-owned skill registry, and persists typed assistant parts. Capabilities
are only ever *proposed* here; a separate authenticated decision executes one
proposal through the existing typed sales-task / sales-output services. Model
and provider output never supply tenant identity, permissions, approvals or
budget, and paid admission is never enabled by this module.
"""
import hashlib
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
import logging
import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency
from ..db.conversation_threads import ConversationThread, ConversationThreadMessage
from ..db.conversation_turns import (ConversationTurn, ConversationTurnDecision,
    ConversationTurnProposal)
from ..db.icp import Project
from ..sales.contracts import Scope, SourceRef, TaskInput
from ..sales.registry import TEMPLATE_SKILLS, load_skill
from ..sales.turn_contracts import (CitationsPart, CitationItem, ExecutionOutcome,
    Language, MAX_TURN_STEPS, NoticePart, OutputLinkPart, OutputRef, ProposalCost,
    ProposalPart, Recovery, TextPart, ToolActivityPart, TurnDecisionRequest, TurnNotice,
    TurnPayload, TurnPlan, TurnRequest, validate_notices, validate_part_list)
from .conversation_access import load, not_found, sales_enabled
from .conversation_turn_events import append_turn_events, read_turn_events
from .turn_deadline import TURN_DEADLINE_EXCEEDED, deadline_notice, turn_deadline
from .conversation_reply import Grounding, reply_from_grounding, resolve_sources

MAX_THREAD_MESSAGES = 100
MAX_GROUNDING_SOURCES = 20
TITLE_LIMIT = 80
# Code-owned inline capability registry: only these proposals can ever exist.
CAPABILITY_BY_SKILL = {
    'understand-documents': 'documents.read',
    'sales-research': 'research.read',
    'sales-quick': 'research.read',
}
# Reviewed proposal-only capabilities: an approval records a decision and an
# honest terminal notice; no executor in this increment dispatches anywhere.
PROPOSAL_ONLY = frozenset({'xverum.enrich_company', 'drive.read'})
EXECUTORS = {}
# Only these unique constraints prove an exact-once replay/race. Any other
# integrity violation is a real defect and must never be reported as a bogus
# idempotency conflict (that masked the original turn-test failures).
TURN_CONFLICT_CONSTRAINTS = frozenset({
    'uq_conversation_turns_workspace_id_thread_id_client_message_id',
    'uq_conversation_turns_actor_client',
    'uq_conversation_thread_messages_client',
})
DECISION_CONFLICT_CONSTRAINTS = frozenset({
    'uq_conversation_turn_decisions_workspace_id_proposal_id',
})
CANCEL_CONFLICT_CONSTRAINTS = frozenset({
    'conversation_turns_pkey',
    'uq_conversation_turns_workspace_id_id',
})
LOGGER = logging.getLogger(__name__)


def constraint_name(exc) -> str | None:
    """Safe diagnostic name only (no SQL, binds or payloads are logged)."""
    original = getattr(exc, 'orig', None)
    diag = getattr(original, 'diag', None)
    name = getattr(diag, 'constraint_name', None)
    if isinstance(name, str) and name:
        return name
    text_value = str(original if original is not None else exc)
    for candidate in (TURN_CONFLICT_CONSTRAINTS | DECISION_CONFLICT_CONSTRAINTS
                      | CANCEL_CONFLICT_CONSTRAINTS):
        if candidate in text_value:
            return candidate
    return None


def is_expected_conflict(exc, constraints) -> bool:
    return constraint_name(exc) in constraints


def raise_unexpected_integrity(exc, operation: str):
    """Non-masking error for an integrity failure we do not recognise."""
    LOGGER.error('conversation_turn_integrity operation=%s constraint=%s',
        operation, constraint_name(exc))
    raise ApiError(500, 'INTERNAL_ERROR', 'request failed') from exc


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False).encode()).hexdigest()


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Deterministic answer path (no live model registration in this increment)
# ---------------------------------------------------------------------------

def model_answer(grounding):
    """Fail closed until a live conversation registration exists.

    Tests may monkeypatch this function with a deterministic fixture adapter that
    calls ``reply_from_grounding(..., fixture_candidate=...)``; production has no
    way to enable it through environment, headers or request fields.
    """
    return reply_from_grounding(grounding)


def advisory_text(grounding, language) -> str:
    count = len(grounding.citations)
    if language == 'zh-HK':
        return (f'已選取 {count} 個已核准來源。對話模型尚未設定，'
                '以下只顯示來源引用摘要，並非模型生成的答案。')
    return (f'Selected {count} citation(s). The live conversation model is not '
            'configured, so this is a source/buyer summary with citations, not a generated answer.')


def missing_source_text(language) -> str:
    if language == 'zh-HK':
        return '請先在討論中選取已核准的報價資料或文件，以引用來源。'
    return 'Select approved offer facts or documents in this discussion to ground an answer.'


def _citation_item(source_id: str, label: str) -> CitationItem:
    kind = source_id.split(':', 1)[0]
    return CitationItem(id=source_id, label=label,
        kind=kind if kind in {'document', 'fact', 'drive', 'run', 'results', 'buyer'}
            else 'document')


def citations_part(grounding) -> CitationsPart | None:
    items = tuple(_citation_item(item['id'], item['label']) for item in grounding.citations)
    return CitationsPart(items=items) if items else None


def answer_parts(grounding, language):
    """Return ``(parts, notices)`` for the advisory/grounded answer step."""
    if not grounding.citations:
        return ([TextPart(text=missing_source_text(language), language=language)],
            [TurnNotice(code='SOURCES_REQUIRED',
                message='No approved source is selected in this discussion.',
                recovery=Recovery(label='Select sources'))])
    try:
        candidate = model_answer(grounding)
    except ApiError as exc:
        if exc.code != 'CONVERSATION_MODEL_UNAVAILABLE':
            raise
        parts = [TextPart(text=advisory_text(grounding, language), language=language)]
        citations = citations_part(grounding)
        if citations is not None:
            parts.append(citations)
        return parts, [TurnNotice(code='CONVERSATION_MODEL_UNAVAILABLE',
            message='Conversation model admission is not configured.',
            recovery=Recovery(label='Open the saved sources'))]
    # Strict citation/tool/refusal boundary is applied by the adapter itself.
    text = candidate['text']
    cited = [source for source in grounding.citations if source in candidate['citations']]
    parts = [TextPart(text=text, language=language)]
    if cited:
        parts.append(CitationsPart(items=tuple(
            _citation_item(item['id'], item['label']) for item in cited)))
    return parts, []


# ---------------------------------------------------------------------------
# Deterministic plan derived from the code-owned skill registry
# ---------------------------------------------------------------------------

def skill_for(thread, payload: TurnRequest):
    skill_id = payload.skill_id or TEMPLATE_SKILLS.get(thread.template_id, 'sales-prospect')
    try:
        return load_skill(skill_id, '1')
    except ValueError as exc:
        raise ApiError(422, 'INVALID_REQUEST', 'unknown skill') from exc


def _execution_refs(grounding) -> list[dict]:
    revision = grounding.offer_revision
    refs = []
    for citation in grounding.citations:
        source_id = citation['id']
        prefix, _, rest = source_id.partition(':')
        try:
            if prefix == 'document':
                ref = SourceRef(id=uuid.UUID(rest), version=revision, kind='document',
                    locator=source_id, retention_class='durable')
            elif prefix == 'fact':
                # fact:profile:<profile>:<fact>
                fact_id = rest.rsplit(':', 1)[-1]
                ref = SourceRef(id=uuid.UUID(fact_id), version=revision, kind='project_fact',
                    locator=source_id, retention_class='durable')
            else:
                continue
        except (ValueError, TypeError):
            continue
        refs.append(ref.model_dump(mode='json'))
    return refs


def _document_ids(grounding) -> list[uuid.UUID]:
    values = []
    for citation in grounding.citations:
        prefix, _, rest = citation['id'].partition(':')
        if prefix != 'document':
            continue
        try:
            values.append(uuid.UUID(rest))
        except ValueError:
            continue
    return list(dict.fromkeys(values))


def _label(value, limit=120) -> str:
    return ' '.join(str(value or '').split())[:limit] or 'Linked company'


async def _buyer_projection(session, scope: Scope, buyer_id):
    """Minimal safe canonical buyer/company projection (no contact data)."""
    from ..db.buyers import Company, HumanReview, ProjectBuyer
    from ..sales.contracts import NativeRef
    from .sales_native import read_native
    row = (await session.execute(select(ProjectBuyer).where(
        ProjectBuyer.workspace_id == scope.workspace_id,
        ProjectBuyer.project_id == scope.project_id,
        ProjectBuyer.id == buyer_id))).scalar_one_or_none()
    if row is None:
        raise not_found()
    # Exactly the permission the native buyer read requires; never leak existence.
    await read_native(session, scope, NativeRef(surface='buyer', id=row.id,
        revision=row.version))
    company = (await session.execute(select(Company).where(
        Company.workspace_id == scope.workspace_id,
        Company.id == row.company_id))).scalar_one_or_none()
    review = (await session.execute(select(HumanReview.state).where(
        HumanReview.workspace_id == scope.workspace_id,
        HumanReview.project_buyer_id == row.id).order_by(
            HumanReview.created_at.desc()).limit(1))).scalar_one_or_none()
    return {'id': row.id, 'version': row.version, 'company_id': row.company_id,
        'name': _label(company.display_name if company is not None else ''),
        'domain': _label(company.domain, 255) if company is not None and company.domain else None,
        'review_state': review or 'unreviewed'}


def _buyer_citation(buyer):
    return {'id': f"buyer:{buyer['id']}", 'label': buyer['name'],
        'locator': {'surface': 'buyer', 'id': str(buyer['id'])}}


def _buyer_source_ref(buyer):
    return {'id': str(buyer['id']), 'version': buyer['version'], 'kind': 'buyer',
        'locator': f"buyer:{buyer['id']}", 'retention_class': 'durable'}


async def _drive_sources(session, scope: Scope, thread):
    """DB-only scope check of the existing Drive connection; no gateway call."""
    ids = [source.get('id') for source in (thread.sources or [])
        if isinstance(source, dict) and isinstance(source.get('id'), str)
        and source['id'].startswith('drive:')]
    if not ids:
        return []
    from .conversation_connections import SOURCE, load as load_connection
    row = await load_connection(session, scope.workspace_id, scope.project_id)
    if row is None or not row.connected or not row.folders:
        return []
    values = []
    for value in ids:
        match = SOURCE.fullmatch(value)
        if match is not None and match[1] == str(row.generation):
            values.append(value)
    return list(dict.fromkeys(values))[:10]


ENRICHMENT_WORDS = ('enrich', 'verify', 'check the company', 'look up the company',
    'company data', 'company research', 'find contacts', 'find people',
    '驗證', '查證', '補充', '查詢公司', '公司資料', '聯絡人')


def _enrichment_intent(text: str) -> bool:
    value = text.casefold()
    return any(word in value for word in ENRICHMENT_WORDS)


def build_plan(thread, payload: TurnRequest, skill, project, grounding, *,
               buyer=None, drive_ids=(), sales_ok: bool, language_ok: bool):
    """Deterministic, bounded plan from the code-owned registry."""
    notices = []
    proposals = []
    staged = []
    steps = ['answer']

    def add(proposal, staged_payload):
        # Bounded plan ceiling: at most MAX_TURN_STEPS-1 reviewed proposals
        # (the first step is always the advisory/grounded answer).
        if len(proposals) >= MAX_TURN_STEPS - 1:
            return
        proposals.append(proposal)
        staged.append(staged_payload)
        steps.append('propose')

    evidence_citations = [citation for citation in grounding.citations
        if not citation['id'].startswith('buyer:')]
    capability = CAPABILITY_BY_SKILL.get(skill.id)
    if not sales_ok:
        notices.append(TurnNotice(code='SALES_ADMISSION_DISABLED',
            message='Guided sales actions are disabled for this workspace.',
            recovery=Recovery(label='Open the native workspace')))
    elif not language_ok:
        notices.append(TurnNotice(code='LANGUAGE_UNAVAILABLE',
            message='This project does not support the requested language.'))
    elif capability is None or capability not in skill.allowed_actions:
        notices.append(TurnNotice(code='CAPABILITY_NOT_AVAILABLE',
            message='No reviewed inline capability is available for this skill.'))
    elif not evidence_citations:
        notices.append(TurnNotice(code='NEEDS_SELECTED_SOURCE',
            message='Select an approved source before proposing a reviewed action.'))
    elif capability == 'documents.read':
        document_ids = _document_ids(grounding)
        if not document_ids:
            notices.append(TurnNotice(code='NEEDS_SELECTED_DOCUMENT',
                message='Select at least one approved offer document.'))
        else:
            proposal, staged_payload = _proposal(thread, payload, skill, capability, grounding,
                arguments={'document_ids': [str(value) for value in document_ids],
                    'question': payload.text, 'language': payload.language},
                preview={'document_ids': [str(value) for value in document_ids],
                    'question': payload.text[:160], 'language': payload.language},
                title='Summarise selected documents' if payload.language == 'en'
                    else '摘要已選文件',
                rationale='Reads only the currently approved offer sources already selected '
                    'in this discussion; no new discovery or provider call.' if payload.language == 'en'
                    else '只讀取本討論已選取且已核准的報價來源；不新增探索或供應商呼叫。')
            add(proposal, staged_payload)
    elif capability == 'research.read':
        proposal, staged_payload = _proposal(thread, payload, skill, capability, grounding,
            arguments={'research_question': payload.text, 'language': payload.language},
            preview={'research_question': payload.text[:160], 'language': payload.language},
            title='Prepare bounded research' if payload.language == 'en' else '準備有界研究',
            rationale='Prepares a research result from selected approved evidence; requires '
                'an existing current native research run.' if payload.language == 'en'
                else '以已選取核准證據準備研究結果；需要現有且最新的原生研究執行。')
        add(proposal, staged_payload)

    if sales_ok and language_ok and buyer is not None and (
            skill.id == 'sales-contacts' or _enrichment_intent(payload.text)):
        proposal, staged_payload = _inline_proposal(thread, payload, skill,
            'xverum.enrich_company',
            arguments={'buyer_id': str(buyer['id']), 'company_id': str(buyer['company_id']),
                'purpose': payload.text[:200], 'language': payload.language},
            preview={'buyer_id': str(buyer['id']), 'company_id': str(buyer['company_id']),
                'purpose': payload.text[:120]},
            title='Enrich the linked company' if payload.language == 'en'
                else '補充連結公司資料',
            rationale='Reviewed Xverum company enrichment for the linked canonical buyer. '
                'Requires a separate cost review and provider admission before any paid call.'
                if payload.language == 'en' else
                '為連結的正式買家公司進行經審閱的 Xverum 補充。任何付費呼叫前須另經成本審閱及供應商准入。',
            cost=ProposalCost(kind='provider_credits', amount=0, unit='credits',
                may_incur_provider_charges=True, known=False),
            source_refs=[_buyer_source_ref(buyer)])
        add(proposal, staged_payload)

    if sales_ok and language_ok and drive_ids:
        proposal, staged_payload = _inline_proposal(thread, payload, skill, 'drive.read',
            arguments={'source_ids': list(drive_ids), 'purpose': payload.text[:200],
                'language': payload.language},
            preview={'source_ids': list(drive_ids), 'purpose': payload.text[:120]},
            title='Read selected Drive evidence' if payload.language == 'en'
                else '讀取已選 Drive 證據',
            rationale='Reads an already authorised Google Drive source as a citation. '
                'Drive content is never retained in durable receipts.' if payload.language == 'en'
                else '將已授權的 Google Drive 來源讀取為引用。Drive 內容不會保留於持久收據。',
            cost=ProposalCost(kind='nonbillable', amount=0, unit='USD',
                may_incur_provider_charges=False),
            source_refs=[])
        add(proposal, staged_payload)
    return TurnPlan(steps=tuple(steps), proposals=tuple(proposals),
        notices=_dedupe_notices(notices)), staged


def _inline_proposal(thread, payload, skill, capability, *, arguments, preview,
                     title, rationale, cost, source_refs):
    proposal_id = uuid.uuid5(uuid.UUID(str(thread.id)),
        f'conversation-proposal:{payload.client_message_id}:{capability}')
    staged = {'proposal_id': proposal_id, 'capability': capability,
        'skill_id': skill.id, 'skill_version': skill.version, 'arguments': arguments,
        'source_refs': source_refs, 'title': title, 'rationale': rationale,
        'arguments_preview': preview}
    part = ProposalPart(proposal_id=proposal_id, capability=capability, title=title,
        rationale=rationale, arguments_preview=preview, cost=cost)
    return part, staged


def _proposal(thread, payload, skill, capability, grounding, *, arguments, preview,
              title, rationale):
    return _inline_proposal(thread, payload, skill, capability, arguments=arguments,
        preview=preview, title=title, rationale=rationale,
        cost=ProposalCost(kind='nonbillable', amount=0, unit='USD',
            may_incur_provider_charges=False),
        source_refs=_execution_refs(grounding))


def thread_title(text: str) -> str:
    value = ' '.join(text.replace('\x00', ' ').split())
    return value[:TITLE_LIMIT] or 'New discussion'


def request_fingerprint(scope: Scope, payload: TurnRequest, thread_id) -> str:
    return digest({'operation': 'conversationTurn', 'workspace_id': str(scope.workspace_id),
        'project_id': str(scope.project_id), 'actor_id': str(scope.actor_id),
        'thread_id': str(thread_id) if thread_id else None,
        'client_message_id': str(payload.client_message_id),
        'expected_thread_version': payload.expected_thread_version,
        'language': payload.language, 'text': payload.text,
        'skill_id': payload.skill_id, 'template_id': payload.template_id})


def _check_version(actual, expected):
    if actual != expected:
        raise ApiError(409, 'STALE_REVISION', 'discussion changed; reload before retrying')


def _payload(row: ConversationTurn) -> TurnPayload:
    return TurnPayload(id=row.id, status=row.status,
        parts=validate_part_list(row.parts or ()), notices=validate_notices(row.notices or ()))


async def _project(session, scope: Scope):
    row = (await session.execute(select(Project).where(Project.workspace_id == scope.workspace_id,
        Project.id == scope.project_id, Project.status == 'active'))).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row


async def _existing_turn(session, scope: Scope, client_message_id):
    return (await session.execute(select(ConversationTurn).where(
        ConversationTurn.workspace_id == scope.workspace_id,
        ConversationTurn.project_id == scope.project_id,
        ConversationTurn.actor_id == scope.actor_id,
        ConversationTurn.client_message_id == client_message_id))).scalar_one_or_none()


async def _turn_by_id(session, scope: Scope, turn_id, thread_id=None):
    filters = [ConversationTurn.workspace_id == scope.workspace_id,
        ConversationTurn.project_id == scope.project_id,
        ConversationTurn.id == turn_id]
    if thread_id is not None:
        filters.append(ConversationTurn.thread_id == thread_id)
    return (await session.execute(select(ConversationTurn).where(*filters))).scalar_one_or_none()


async def _replay(session, scope: Scope, row: ConversationTurn, payload: TurnRequest):
    thread, role = await load(session, scope.workspace_id, scope.project_id, row.thread_id,
        scope.actor_id, edit=True, lock=True)
    if row.request_fingerprint != request_fingerprint(scope, payload, row.thread_id):
        raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
            'this client message key belongs to a different turn request')
    return thread, role, _payload(row)


async def _next_seq(session, thread) -> int:
    from .conversation_messages import next_message_seq
    return await next_message_seq(session, thread.workspace_id, thread.id)


async def _message_count(session, thread) -> int:
    return (await session.execute(select(func.count()).select_from(ConversationThreadMessage)
        .where(ConversationThreadMessage.workspace_id == thread.workspace_id,
            ConversationThreadMessage.thread_id == thread.id))).scalar_one()


async def _grounding(session, scope: Scope, thread, buyer=None):
    raw = [source.get('id') for source in (thread.sources or [])
        if isinstance(source, dict) and isinstance(source.get('id'), str)]
    resolvable = [value for value in raw if value.split(':', 1)[0] in
        {'document', 'fact', 'drive'}][:MAX_GROUNDING_SOURCES]
    notices = []
    grounding = Grounding([], [])
    if resolvable:
        try:
            grounding = await resolve_sources(session, workspace_id=scope.workspace_id,
                project_id=scope.project_id, source_ids=resolvable, readonly=True)
        except (ApiError, ValueError):
            notices.append(TurnNotice(code='SOURCE_UNAVAILABLE',
                message='The selected sources need current review before use.',
                recovery=Recovery(label='Review selected sources')))
    if buyer is not None:
        # Authorised canonical identity is contextual evidence, not a paid source.
        # Only the minimal safe projection reaches request memory (no contact data).
        summary = (f"Linked buyer: {buyer['name']}; "
            f"domain: {buyer['domain'] or 'unknown'}; "
            f"review state: {buyer['review_state']}.")
        grounding = replace(grounding,
            citations=[*grounding.citations, _buyer_citation(buyer)],
            excerpts=[*grounding.excerpts, summary])
    return grounding, notices


def _dedupe_notices(notices):
    seen, values = set(), []
    for notice in notices:
        if notice.code in seen:
            continue
        seen.add(notice.code)
        values.append(notice)
    return tuple(values[:8])


def _assistant_text(parts, notices) -> str:
    texts = [part.text for part in parts if isinstance(part, TextPart)]
    if texts:
        return ' '.join(texts)[:4000]
    if notices:
        return notices[0].message[:4000]
    return 'Turn recorded.'


async def _stage_turn(session, scope: Scope, thread, payload: TurnRequest, *,
                      client_message_id, user_text, request_fp, steps_count, skill_id,
                      skill_version, parts, notices, status, staged=None,
                      parent_turn_id=None, source_turn_id=None):
    """Persist turn + messages + reviewed proposal rows inside the caller's savepoint."""
    if client_message_id:
        turn_id = uuid.uuid5(uuid.UUID(str(thread.id)),
            f'conversation-turn:{client_message_id}')
    else:
        turn_id = uuid.uuid5(uuid.UUID(str(source_turn_id)), f'continuation:{request_fp}')
    turn = ConversationTurn(id=turn_id, workspace_id=scope.workspace_id,
        project_id=scope.project_id, thread_id=thread.id, owner_user_id=thread.owner_user_id,
        actor_id=scope.actor_id, client_message_id=client_message_id,
        request_fingerprint=request_fp, parent_turn_id=parent_turn_id,
        language=payload.language,
        skill_id=skill_id, skill_version=skill_version, status=status,
        step_count=steps_count,
        expected_thread_version=payload.expected_thread_version if payload is not None else None,
        parts=[part.model_dump(mode='json') for part in parts],
        notices=[notice.model_dump(mode='json') for notice in notices])
    session.add(turn)
    await session.flush()
    seq = await _next_seq(session, thread)
    if client_message_id:
        session.add(ConversationThreadMessage(workspace_id=scope.workspace_id,
            project_id=scope.project_id, thread_id=thread.id,
            owner_user_id=thread.owner_user_id, author_user_id=scope.actor_id,
            text=user_text, seq=seq, role='user', client_message_id=client_message_id,
            turn_id=turn.id, parts=[]))
        seq += 1
    session.add(ConversationThreadMessage(workspace_id=scope.workspace_id,
        project_id=scope.project_id, thread_id=thread.id,
        owner_user_id=thread.owner_user_id, author_user_id=scope.actor_id,
        text=_assistant_text(parts, notices), seq=seq, role='assistant',
        client_message_id=None, turn_id=turn.id,
        parts=[part.model_dump(mode='json') for part in parts]))
    if staged:
        parts_by_id = {part.proposal_id: part for part in parts
            if isinstance(part, ProposalPart)}
        for staged_payload in staged:
            part = parts_by_id[staged_payload['proposal_id']]
            session.add(ConversationTurnProposal(id=part.proposal_id,
                workspace_id=scope.workspace_id, project_id=scope.project_id,
                thread_id=thread.id, turn_id=turn.id, actor_id=scope.actor_id,
                capability=staged_payload['capability'],
                skill_id=staged_payload['skill_id'],
                skill_version=staged_payload['skill_version'],
                title=staged_payload['title'], rationale=staged_payload['rationale'],
                arguments=staged_payload['arguments'],
                source_refs=staged_payload['source_refs'],
                arguments_preview=staged_payload['arguments_preview'],
                cost=part.cost.model_dump(mode='json') if part.cost else None))
    thread.version += 1
    thread.updated_at = now()
    await session.flush()
    return turn


async def _stage_deadline_create(session, scope: Scope, thread, payload: TurnRequest,
                                request_fp, *, parts=(), notices=()):
    """Persist the produced parts + one terminal deadline notice, failed.

    Rendering channel: the localized deadline message lives in the persisted
    notice only (the assistant message text falls back to it). Produced text /
    citation parts are kept. Proposal parts are intentionally dropped: a failed
    deadline turn can never accept their decision, so persisting the part or its
    proposal row would be unreachable UI state. Everything persisted here is
    faithful; nothing spent is silently retained (canonical writes are rolled
    back before this helper is called).
    """
    language = payload.language
    notice = deadline_notice(language)
    values = [part for part in parts if not isinstance(part, ProposalPart)]
    merged = _dedupe_notices([*notices, notice])
    skill = skill_for(thread, payload)
    turn = await _stage_turn(session, scope, thread, payload,
        client_message_id=payload.client_message_id, user_text=payload.text,
        request_fp=request_fp, steps_count=0, skill_id=skill.id,
        skill_version=skill.version, parts=tuple(values), notices=merged, status='failed')
    await append_turn_events(session, scope, turn, tuple(values), merged, 'failed')
    from .audit_service import append_audit
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
        action='conversation_turn.created', entity_type='conversation_turn',
        entity_id=turn.id)
    return turn


async def _deadline_simple_continuation(session, scope: Scope, thread, source_turn,
                                        fingerprint, language):
    """Terminal failed continuation; the notice is the one rendering channel."""
    notice = deadline_notice(language)
    continuation, _fresh = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, language, parts=[], notices=(notice,), status='failed')
    return continuation


async def _deadline_failure(session, scope: Scope, thread, source_turn, proposal,
                            request, fingerprint):
    """Decision continuation that timed out before/around a nonbillable step.

    The executor savepoint is rolled back before this helper is reached, so no
    canonical task/output row survives and the step is terminal ``skipped`` --
    never a guessed ``outcome_unknown``. If a future provider-dispatched step is
    added it must NOT use this helper: it must persist the task/receipt reference
    and ``outcome_unknown`` on a turn status that ``reconcile`` accepts.
    """
    language = source_turn.language
    notice = deadline_notice(language)
    parts = [_decision_part(proposal, 'skipped', summary=notice.message[:500],
                error_code=TURN_DEADLINE_EXCEEDED,
                started_at=proposal.created_at or now(), finished_at=now())]
    continuation, created = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, language, parts=parts, notices=(notice,), status='failed')
    proposal.status = 'failed'
    proposal.revision += 1
    proposal.result = {'code': TURN_DEADLINE_EXCEEDED, 'output_id': None,
        'output_revision': None, 'task_id': None}
    _record_decision(session, scope, source_turn, proposal, request, fingerprint,
        continuation, 'failed')
    return continuation, created


async def create_turn(session, scope: Scope, payload: TurnRequest, key: str,
                      admit=None):
    """Create one turn; ``admit`` is the optional workspace admission hook.

    It runs after client-message/idempotency replay detection and before any
    turn, event, task, budget or idempotency write. Existing callers and tests
    pass None (no dedicated admission); the HTTP turn route supplies the
    workspace turn-rate ceiling.
    """
    thread = None
    buyer = None
    if payload.thread_id is not None:
        thread, role = await load(session, scope.workspace_id, scope.project_id,
            payload.thread_id, scope.actor_id, edit=True, lock=True)
        if payload.expected_thread_version is None:
            raise ApiError(400, 'INVALID_REQUEST', 'If-Match thread version is required')
        if payload.buyer_id is not None:
            if thread.buyer_id is None or thread.buyer_id != payload.buyer_id:
                raise ApiError(409, 'BUYER_LINK_MISMATCH',
                    'a discussion company link can only be set when the discussion is created')
    else:
        role = 'owner'
    project = await _project(session, scope)
    if payload.buyer_id is not None:
        # New thread link: the buyer must be current, same-project and readable now.
        buyer = await _buyer_projection(session, scope, payload.buyer_id)
    existing = await _existing_turn(session, scope, payload.client_message_id)
    if existing is not None:
        return await _replay(session, scope, existing, payload)
    target = ({'project_id': str(scope.project_id), 'thread_id': str(thread.id)}
              if thread is not None else {'project_id': str(scope.project_id), 'new_thread': True})
    precondition = (f'"{payload.expected_thread_version}"'
                    if payload.expected_thread_version is not None else None)
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id,
        actor_id=scope.actor_id, operation_id='conversationTurn', key=key,
        body=payload.model_dump(mode='json'), target=target, precondition=precondition,
        before_insert=admit)
    if outcome.replay:
        row = await _turn_by_id(session, scope, uuid.UUID(outcome.record.resource_id))
        if row is None:
            raise not_found()
        return await _replay(session, scope, row, payload)
    if thread is not None:
        _check_version(thread.version, payload.expected_thread_version)
    deadline = turn_deadline()
    saved_fp = request_fingerprint(scope, payload, thread.id if thread is not None else None)
    try:
        async with session.begin_nested():
            if thread is None:
                thread = ConversationThread(workspace_id=scope.workspace_id,
                    project_id=scope.project_id, owner_user_id=scope.actor_id,
                    buyer_id=payload.buyer_id,
                    template_id=payload.template_id or 'custom',
                    title=thread_title(payload.text), sources=[], runs=[], version=1)
                session.add(thread)
                await session.flush()
                saved_fp = request_fingerprint(scope, payload, thread.id)
            if await _message_count(session, thread) + 2 > MAX_THREAD_MESSAGES:
                raise ApiError(409, 'MESSAGE_LIMIT',
                    'discussion note limit reached; start another discussion and keep unsent text')
            source_notices = []
            if thread.buyer_id is not None and buyer is None:
                try:
                    buyer = await _buyer_projection(session, scope, thread.buyer_id)
                except ApiError:
                    if payload.thread_id is None:
                        raise
                    source_notices.append(TurnNotice(code='BUYER_LINK_UNAVAILABLE',
                        message='The linked buyer is no longer readable; ask a project editor '
                            'to relink it.'))
            if not deadline.should_start():
                turn = await _stage_deadline_create(session, scope, thread, payload,
                    saved_fp, notices=tuple(source_notices))
            else:
                grounding, grounding_notices = await _grounding(session, scope, thread, buyer)
                skill = skill_for(thread, payload)
                drive_ids = await _drive_sources(session, scope, thread)
                answer_values, answer_notices = answer_parts(grounding, payload.language)
                if not deadline.should_start():
                    # Keep the faithful answer/citation parts produced so far;
                    # only proposal parts are intentionally dropped (a failed
                    # deadline turn can never accept their decision).
                    produced = _dedupe_notices([*source_notices, *grounding_notices,
                        *answer_notices])
                    turn = await _stage_deadline_create(session, scope, thread, payload,
                        saved_fp, parts=tuple(answer_values), notices=produced)
                else:
                    plan, staged = build_plan(thread, payload, skill, project, grounding,
                        buyer=buyer, drive_ids=tuple(drive_ids),
                        sales_ok=sales_enabled(scope.workspace_id),
                        language_ok=payload.language in (project.language_preferences or []))
                    parts = list(answer_values)
                    parts.extend(plan.proposals)
                    notices = _dedupe_notices([*source_notices, *grounding_notices,
                        *answer_notices, *plan.notices])
                    if not deadline.should_start():
                        turn = await _stage_deadline_create(session, scope, thread, payload,
                            saved_fp, parts=tuple(parts), notices=notices)
                    else:
                        if plan.proposals:
                            status = 'needs_approval'
                        elif not grounding.citations:
                            status = 'needs_input'
                        else:
                            status = 'completed'
                        turn = await _stage_turn(session, scope, thread, payload,
                            client_message_id=payload.client_message_id, user_text=payload.text,
                            request_fp=saved_fp, steps_count=len(plan.steps),
                            skill_id=skill.id, skill_version=skill.version,
                            parts=tuple(parts), notices=notices, status=status, staged=staged)
                        # Same transaction as the persisted turn/parts/status: the
                        # terminal event can never disagree with conversation_turns.status.
                        await append_turn_events(session, scope, turn, tuple(parts), notices,
                            status)
                        from .audit_service import append_audit
                        append_audit(session, workspace_id=scope.workspace_id,
                            actor_id=scope.actor_id, action='conversation_turn.created',
                            entity_type='conversation_turn', entity_id=turn.id)
    except IntegrityError as exc:
        if not is_expected_conflict(exc, TURN_CONFLICT_CONSTRAINTS):
            raise_unexpected_integrity(exc, 'conversation_turn.create')
        existing = await _existing_turn(session, scope, payload.client_message_id)
        if existing is None:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
                'a concurrent request with this client message key is in progress') from exc
        if existing.request_fingerprint != saved_fp:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
                'this client message key belongs to a different turn request') from exc
        thread, role = await load(session, scope.workspace_id, scope.project_id,
            existing.thread_id, scope.actor_id, edit=True, lock=True)
        complete_idempotency(outcome, str(existing.id))
        return thread, role, _payload(existing)
    complete_idempotency(outcome, str(turn.id))
    return thread, role, _payload(turn)


# ---------------------------------------------------------------------------
# Explicit decisions
# ---------------------------------------------------------------------------

def _executor(capability):
    return EXECUTORS.get(capability)


async def _execute_documents(session, scope: Scope, thread, turn: ConversationTurn,
                             proposal: ConversationTurnProposal) -> ExecutionOutcome:
    from .sales_outputs import assemble_or_core, save_output
    from .sales_tasks import create_task, task_row
    data = TaskInput(thread_id=proposal.thread_id, skill_id=proposal.skill_id,
        skill_version=proposal.skill_version,
        user_message=await _user_text(session, scope, turn.id),
        source_refs=tuple(SourceRef.model_validate(ref) for ref in proposal.source_refs),
        arguments=proposal.arguments)
    key = f'conversation-turn-output:{proposal.id}'
    record = await create_task(session, scope, data, key, thread.version)
    row = await task_row(session, scope, record.id, edit=True)
    candidate = await assemble_or_core(session, scope, row)
    saved = await save_output(session, scope, row.id, candidate,
        f'conversation-turn-save:{proposal.id}', visibility='thread')
    status = 'needs_review' if saved.availability != 'available' else 'available'
    return ExecutionOutcome(kind='output' if status == 'available' else 'notice',
        code='OUTPUT_SAVED' if status == 'available' else 'OUTPUT_NEEDS_REVIEW',
        message='Saved a reviewed document-understanding revision.' if status == 'available'
            else 'Saved output requires native review.',
        output=OutputRef(output_id=saved.id, kind=saved.kind, revision=saved.revision,
            status=status), task_id=row.id)


async def _execute_research(session, scope: Scope, thread, turn: ConversationTurn,
                            proposal: ConversationTurnProposal) -> ExecutionOutcome:
    from .sales_outputs import assemble_or_core, save_output
    from .sales_tasks import create_task, task_row
    data = TaskInput(thread_id=proposal.thread_id, skill_id=proposal.skill_id,
        skill_version=proposal.skill_version,
        user_message=await _user_text(session, scope, turn.id),
        source_refs=tuple(SourceRef.model_validate(ref) for ref in proposal.source_refs),
        arguments=proposal.arguments)
    key = f'conversation-turn-research:{proposal.id}'
    record = await create_task(session, scope, data, key, thread.version)
    row = await task_row(session, scope, record.id, edit=True)
    try:
        candidate = await assemble_or_core(session, scope, row)
    except ValueError:
        # Honest state: the approved request is durably admitted, but preparing
        # it needs an existing current native research run. No provider call.
        return ExecutionOutcome(kind='failed', code='NEEDS_NATIVE_PREREQUISITE',
            message='Select an existing completed native research run before preparing '
                'this research output.', task_id=row.id)
    saved = await save_output(session, scope, row.id, candidate,
        f'conversation-turn-save:{proposal.id}', visibility='thread')
    return ExecutionOutcome(kind='output', code='OUTPUT_SAVED',
        message='Saved a research revision.', output=OutputRef(output_id=saved.id,
            kind=saved.kind, revision=saved.revision, status='available'), task_id=row.id)



def _terminal(code, message):
    return ExecutionOutcome(kind='failed', code=code, message=message)


async def _execute_xverum_proposal_only(session, scope: Scope, thread, turn,
                                        proposal) -> ExecutionOutcome:
    """Honest terminal outcome; this phase never calls the provider transport."""
    from ..settings import get_settings
    from ..db.worker_execution import WorkerRuntimeControl
    if not sales_enabled(scope.workspace_id):
        return _terminal('SALES_ADMISSION_DISABLED',
            'Guided sales execution is disabled for this workspace; no provider call was made.')
    if not get_settings().paid_admission_enabled:
        return _terminal('PAID_ADMISSION_DISABLED',
            'Paid provider admission is disabled; no Xverum request was dispatched.')
    try:
        control = (await session.execute(select(WorkerRuntimeControl.backend,
            WorkerRuntimeControl.enabled))).one()
    except Exception:
        return _terminal('EXECUTION_RUNTIME_REQUIRED',
            'The reviewed native execution runtime is not enabled; no Xverum request was dispatched.')
    if (control.backend != 'cloudflare' or not control.enabled
            or not get_settings().cloudflare_execution_enabled):
        return _terminal('EXECUTION_RUNTIME_REQUIRED',
            'The reviewed native execution runtime is not enabled; no Xverum request was dispatched.')
    try:
        from .xverum_connections import list_connections
        connections = await list_connections(session, scope)
    except (ApiError, ValueError):
        connections = []
    if not connections:
        return _terminal('XVERUM_NOT_CONFIGURED',
            'No project-assigned Xverum connection is configured; no provider call was made.')
    return _terminal('XVERUM_DISPATCH_NOT_ENABLED',
        'Reviewed Xverum dispatch is not enabled in this increment; no provider call was made.')


async def _execute_drive_proposal_only(session, scope: Scope, thread, turn,
                                       proposal) -> ExecutionOutcome:
    """Scope revalidation only; no gateway call and no content retention."""
    from .conversation_connections import SOURCE, load as load_connection
    source_ids = list(proposal.arguments.get('source_ids') or [])
    try:
        row = await load_connection(session, scope.workspace_id, scope.project_id)
    except (ApiError, ValueError):
        row = None
    if row is None or not row.connected or not row.folders:
        return _terminal('DRIVE_NOT_CONFIGURED',
            'No connected Google Drive source is available; no content was read.')
    for value in source_ids:
        match = SOURCE.fullmatch(value) if isinstance(value, str) else None
        if match is None or match[1] != str(row.generation):
            return _terminal('DRIVE_SOURCE_UNAVAILABLE',
                'The selected Drive source is no longer authorised; no content was read.')
    return _terminal('DRIVE_READ_NOT_ENABLED',
        'Reading Drive content from a conversation turn is not enabled in this increment; '
        'no content was read or retained.')


EXECUTORS.update({'documents.read': _execute_documents, 'research.read': _execute_research,
    'xverum.enrich_company': _execute_xverum_proposal_only, 'drive.read': _execute_drive_proposal_only})


async def _user_text(session, scope, turn_id) -> str:
    value = (await session.execute(select(ConversationThreadMessage.text).where(
        ConversationThreadMessage.workspace_id == scope.workspace_id,
        ConversationThreadMessage.turn_id == turn_id,
        ConversationThreadMessage.role == 'user'))).scalar_one_or_none()
    return value or 'Conversation request'


async def _continuation_turn(session, scope: Scope, thread, source_turn, request_fp,
                             payload_language, *, parts, notices, status):
    turn_id = uuid.uuid5(uuid.UUID(str(source_turn.id)), f'continuation:{request_fp}')
    existing = await _turn_by_id(session, scope, turn_id, thread.id)
    if existing is not None:
        return existing, False
    if await _message_count(session, thread) + 1 > MAX_THREAD_MESSAGES:
        raise ApiError(409, 'MESSAGE_LIMIT',
            'discussion note limit reached; start another discussion')
    seq = await _next_seq(session, thread)
    turn = ConversationTurn(id=turn_id, workspace_id=scope.workspace_id,
        project_id=scope.project_id, thread_id=thread.id, owner_user_id=thread.owner_user_id,
        actor_id=scope.actor_id, client_message_id=None, request_fingerprint=request_fp,
        parent_turn_id=source_turn.id, language=payload_language,
        skill_id=source_turn.skill_id, skill_version=source_turn.skill_version,
        status=status, step_count=1, expected_thread_version=None,
        parts=[part.model_dump(mode='json') for part in parts],
        notices=[notice.model_dump(mode='json') for notice in notices])
    session.add(turn)
    await session.flush()
    session.add(ConversationThreadMessage(workspace_id=scope.workspace_id,
        project_id=scope.project_id, thread_id=thread.id, owner_user_id=thread.owner_user_id,
        author_user_id=scope.actor_id, text=_assistant_text(parts, notices), seq=seq,
        role='assistant', client_message_id=None, turn_id=turn.id,
        parts=[part.model_dump(mode='json') for part in parts]))
    thread.version += 1
    thread.updated_at = now()
    await session.flush()
    await append_turn_events(session, scope, turn, parts, notices, status)
    return turn, True


def decision_fingerprint(scope: Scope, thread_id, source_turn_id,
                         request: TurnDecisionRequest) -> str:
    """Continuation identity: includes the decision precondition version.

    A non-terminal blocked decision leaves the proposal open; a later decision
    after the workspace is configured must create a NEW continuation, so the
    expected version is part of the fingerprint (without it a resume reused the
    earlier ``needs_input`` continuation).
    """
    return digest({'operation': 'conversationTurnDecision',
        'proposal_id': str(request.proposal_id), 'decision': request.decision,
        'actor_id': str(scope.actor_id), 'thread_id': str(thread_id),
        'turn_id': str(source_turn_id),
        'expected_thread_version': request.expected_thread_version})


def _decision_part(proposal, state, *, summary=None, error_code=None, started_at=None,
                   finished_at=None) -> ToolActivityPart:
    return ToolActivityPart(call_id=proposal.id, capability=proposal.capability,
        title=proposal.title, state=state,
        started_at=started_at or proposal.created_at or now(),
        finished_at=finished_at, summary=summary, error_code=error_code)


async def decide(session, scope: Scope, turn_id, request: TurnDecisionRequest, key: str):
    source_turn = await _turn_by_id(session, scope, turn_id)
    if source_turn is None:
        raise not_found()
    thread, role = await load(session, scope.workspace_id, scope.project_id,
        source_turn.thread_id, scope.actor_id, edit=True, lock=True)
    fingerprint = decision_fingerprint(scope, thread.id, source_turn.id, request)
    # Durable replay precedes the write precondition. A retry after an uncertain
    # first response reuses the same key and the same expected version, while the
    # first commit already advanced thread.version; the fingerprint still binds
    # both, so a genuinely different request keeps conflicting.
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id,
        actor_id=scope.actor_id, operation_id='conversationTurnDecision', key=key,
        body=request.model_dump(mode='json'),
        target={'project_id': str(scope.project_id), 'turn_id': str(source_turn.id)},
        precondition=f'"{request.expected_thread_version}"')
    if outcome.replay:
        row = await _turn_by_id(session, scope, uuid.UUID(outcome.record.resource_id), thread.id)
        if row is None:
            raise not_found()
        await load(session, scope.workspace_id, scope.project_id, row.thread_id,
            scope.actor_id, edit=True, lock=True)
        return thread, role, _payload(row), False
    existing = (await session.execute(select(ConversationTurnDecision).where(
        ConversationTurnDecision.workspace_id == scope.workspace_id,
        ConversationTurnDecision.project_id == scope.project_id,
        ConversationTurnDecision.thread_id == thread.id,
        ConversationTurnDecision.turn_id == source_turn.id,
        ConversationTurnDecision.proposal_id == request.proposal_id))).scalar_one_or_none()
    if existing is not None:
        if existing.decision != request.decision:
            raise ApiError(409, 'ALREADY_DECIDED', 'this proposal already has a decision')
        row = await _turn_by_id(session, scope, existing.continuation_turn_id, thread.id)
        if row is None:
            raise not_found()
        complete_idempotency(outcome, str(existing.continuation_turn_id))
        return thread, role, _payload(row), True
    # Genuinely new decision: authoritative current version and open proposal.
    _check_version(thread.version, request.expected_thread_version)
    proposal = (await session.execute(select(ConversationTurnProposal).where(
        ConversationTurnProposal.workspace_id == scope.workspace_id,
        ConversationTurnProposal.project_id == scope.project_id,
        ConversationTurnProposal.thread_id == thread.id,
        ConversationTurnProposal.turn_id == source_turn.id,
        ConversationTurnProposal.id == request.proposal_id).with_for_update())).scalar_one_or_none()
    if proposal is None:
        raise not_found()
    if source_turn.status != 'needs_approval' or proposal.status != 'proposed':
        raise ApiError(409, 'INVALID_STATE', 'this turn has no open proposal')
    deadline = turn_deadline()
    try:
        async with session.begin_nested():
            continuation, effective = await _apply_decision(session, scope, thread,
                source_turn, proposal, request, fingerprint, deadline=deadline)
    except IntegrityError as exc:
        if not is_expected_conflict(exc, DECISION_CONFLICT_CONSTRAINTS):
            raise_unexpected_integrity(exc, 'conversation_turn.decide')
        existing = (await session.execute(select(ConversationTurnDecision).where(
            ConversationTurnDecision.workspace_id == scope.workspace_id,
            ConversationTurnDecision.project_id == scope.project_id,
            ConversationTurnDecision.thread_id == thread.id,
            ConversationTurnDecision.turn_id == source_turn.id,
            ConversationTurnDecision.proposal_id == request.proposal_id))).scalar_one_or_none()
        if existing is None:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
                'a concurrent decision for this proposal is in progress') from exc
        complete_idempotency(outcome, str(existing.continuation_turn_id))
        row = await _turn_by_id(session, scope, existing.continuation_turn_id, thread.id)
        if row is None:
            raise not_found()
        return thread, role, _payload(row), True
    complete_idempotency(outcome, str(continuation.id))
    if effective:
        # Exactly one audit row per effective decision transition; an
        # idempotent replay of an existing continuation appends nothing.
        from .audit_service import append_audit
        append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
            action='conversation_turn.decided', entity_type='conversation_turn',
            entity_id=continuation.id)
    return thread, role, _payload(continuation), effective


async def _apply_decision(session, scope: Scope, thread, source_turn, proposal,
                          request: TurnDecisionRequest, fingerprint, *, deadline=None):
    started = proposal.created_at or now()
    if request.decision == 'reject':
        parts = [_decision_part(proposal, 'skipped', summary='Rejected by the reviewer.',
                    started_at=started, finished_at=now()),
            TextPart(text='Proposal rejected; nothing was executed.'
                if source_turn.language == 'en' else '已拒絕提案；未執行任何動作。',
                language=source_turn.language)]
        notices = (TurnNotice(code='PROPOSAL_REJECTED',
            message='The reviewer rejected this proposal.'),)
        continuation, created = await _continuation_turn(session, scope, thread, source_turn,
            fingerprint, source_turn.language, parts=parts, notices=notices, status='completed')
        proposal.status = 'rejected'
        proposal.revision += 1
        _record_decision(session, scope, source_turn, proposal, request, fingerprint,
            continuation, 'applied')
        return continuation, created
    # Approval: revalidate current membership, role, project, language, sales
    # admission and policy/budget gate state *now*, then execute once.
    project = await _project(session, scope)
    proposal_only = proposal.capability in PROPOSAL_ONLY
    if not proposal_only and not sales_enabled(scope.workspace_id):
        return await _blocked_continuation(session, scope, thread, source_turn, proposal,
            fingerprint, 'SALES_ADMISSION_DISABLED',
            'Guided sales execution is disabled for this workspace.')
    if source_turn.language not in (project.language_preferences or []):
        return await _blocked_continuation(session, scope, thread, source_turn, proposal,
            fingerprint, 'LANGUAGE_UNAVAILABLE',
            'This project no longer supports the reviewed language.')
    from .xverum_dispatch import gates
    await gates(session, scope.workspace_id)  # current policy + budget serialization
    if deadline is not None and not deadline.should_start():
        # The bound was crossed during gate serialization; no step was dispatched.
        return await _deadline_failure(session, scope, thread, source_turn, proposal,
            request, fingerprint)
    executor = _executor(proposal.capability)
    if executor is None:
        return await _finish_failure(session, scope, thread, source_turn, proposal,
            request, fingerprint, 'failed', 'CAPABILITY_NOT_AVAILABLE',
            'No reviewed executor is registered for this capability.')
    try:
        savepoint = await session.begin_nested()
        try:
            result = await executor(session, scope, thread, source_turn, proposal)
        except BaseException:
            # Existing failure semantics: durable effects a failing executor
            # already produced stay recovery-visible; the decision becomes
            # terminal below. Only a deadline crossing discards spent work.
            await savepoint.commit()
            raise
        if deadline is not None and not deadline.should_start():
            # The current executors are nonbillable local producers: roll the
            # savepoint back so a deadline-failed turn cannot leave canonical
            # sales_tasks/sales_outputs rows (or any other spent work) behind.
            # A future provider-dispatched step MUST NOT be rolled back this
            # way: it must persist its task/receipt reference and
            # ``outcome_unknown`` on a turn status that ``reconcile`` accepts
            # (explicitly out of scope for this increment).
            await savepoint.rollback()
            return await _deadline_failure(session, scope, thread, source_turn, proposal,
                request, fingerprint)
        await savepoint.commit()
    except ApiError as exc:
        if exc.status_code in {403, 404}:
            raise
        # Any durable effects the executor already committed inside this
        # savepoint stay recovery-visible, but the decision and proposal become
        # terminal so the same proposal can never be approved again.
        return await _finish_failure(session, scope, thread, source_turn, proposal,
            request, fingerprint, 'failed', exc.code, exc.message)
    except Exception:
        return await _finish_failure(session, scope, thread, source_turn, proposal,
            request, fingerprint, 'failed', 'EXECUTION_REJECTED',
            'Current policy, source authority or configuration rejected this execution.')
    status = {'output': 'completed', 'notice': 'needs_input',
              'failed': 'failed', 'unknown': 'outcome_unknown'}[result.kind]
    proposal_status = {'output': 'executed', 'notice': 'failed',
                       'failed': 'failed', 'unknown': 'outcome_unknown'}[result.kind]
    parts = [_decision_part(proposal, 'completed' if result.kind == 'output'
        else 'outcome_unknown' if result.kind == 'unknown' else 'failed',
        summary=result.message[:500], error_code=None if result.kind == 'output' else result.code,
        started_at=started, finished_at=now())]
    if result.output is not None:
        parts.append(OutputLinkPart(output=result.output,
            title='Saved output' if source_turn.language == 'en' else '已儲存結果'))
    parts.append(TextPart(text=result.message, language=source_turn.language))
    notices = () if result.kind == 'output' else (TurnNotice(code=result.code,
        message=result.message),)
    continuation, created = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, source_turn.language, parts=parts, notices=notices, status=status)
    proposal.status = proposal_status
    proposal.revision += 1
    proposal.result = {'code': result.code,
        'output_id': str(result.output.output_id) if result.output else None,
        'output_revision': result.output.revision if result.output else None,
        'task_id': str(result.task_id) if result.task_id else None}
    _record_decision(session, scope, source_turn, proposal, request, fingerprint,
        continuation, 'applied')
    return continuation, created


async def _blocked_continuation(session, scope, thread, source_turn, proposal,
                                fingerprint, code, message):
    parts = [_decision_part(proposal, 'approved', summary=message,
                started_at=proposal.created_at or now()),
        TextPart(text=message, language=source_turn.language)]
    notices = (TurnNotice(code=code, message=message),)
    continuation, created = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, source_turn.language, parts=parts, notices=notices, status='needs_input')
    # Non-terminal: the proposal stays open so it can be approved after the
    # workspace is configured. No decision row is recorded (recoverable notice).
    return continuation, created


async def _finish_failure(session, scope, thread, source_turn, proposal, request,
                          fingerprint, status, code, message):
    parts = [_decision_part(proposal, 'failed' if status == 'failed' else 'outcome_unknown',
                summary=message[:500], error_code=code,
                started_at=proposal.created_at or now(), finished_at=now()),
        TextPart(text=message, language=source_turn.language)]
    notices = (TurnNotice(code=code, message=message),)
    continuation, created = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, source_turn.language, parts=parts, notices=notices, status=status)
    # Terminal: persist proposal/decision state even though the executor failed,
    # so a failed or uncertain step is visible and cannot be re-approved.
    failure_status = 'failed' if status == 'failed' else 'outcome_unknown'
    proposal.status = failure_status
    proposal.revision += 1
    proposal.result = {'code': code, 'output_id': None, 'output_revision': None,
        'task_id': None}
    _record_decision(session, scope, source_turn, proposal, request, fingerprint,
        continuation, 'failed')
    return continuation, created


def _record_decision(session, scope: Scope, source_turn, proposal, request, fingerprint,
                     continuation, status):
    session.add(ConversationTurnDecision(workspace_id=scope.workspace_id,
        project_id=scope.project_id, thread_id=source_turn.thread_id,
        turn_id=source_turn.id, proposal_id=proposal.id, actor_id=scope.actor_id,
        decision=request.decision, request_fingerprint=fingerprint,
        continuation_turn_id=continuation.id, status=status))


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

async def cancel_turn(session, scope: Scope, turn_id, expected_version: int, key: str):
    source_turn = await _turn_by_id(session, scope, turn_id)
    if source_turn is None:
        raise not_found()
    thread, role = await load(session, scope.workspace_id, scope.project_id,
        source_turn.thread_id, scope.actor_id, edit=True, lock=True)
    fingerprint = digest({'operation': 'cancelConversationTurn',
        'turn_id': str(source_turn.id), 'actor_id': str(scope.actor_id)})
    # Durable replay precedes the write precondition (see decide()).
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id,
        actor_id=scope.actor_id, operation_id='cancelConversationTurn', key=key,
        body={}, target={'project_id': str(scope.project_id),
            'turn_id': str(source_turn.id)}, precondition=f'"{expected_version}"')
    if outcome.replay:
        row = await _turn_by_id(session, scope, uuid.UUID(outcome.record.resource_id), thread.id)
        if row is None:
            raise not_found()
        return thread, role, _payload(row)
    recorded = await _recorded_cancellation(session, scope, thread.id, source_turn.id)
    if recorded is not None:
        complete_idempotency(outcome, str(recorded.id))
        return thread, role, _payload(recorded)
    if source_turn.status in {'completed', 'failed', 'outcome_unknown', 'cancelled'}:
        complete_idempotency(outcome, str(source_turn.id))
        return thread, role, _payload(source_turn)
    _check_version(thread.version, expected_version)
    deadline = turn_deadline()
    if not deadline.should_start():
        deadline_fp = digest({'operation': 'cancelConversationTurnDeadline',
            'turn_id': str(source_turn.id)})
        async with session.begin_nested():
            continuation = await _deadline_simple_continuation(session, scope, thread,
                source_turn, deadline_fp, source_turn.language)
        complete_idempotency(outcome, str(continuation.id))
        return thread, role, _payload(continuation)
    continuation, created = None, False
    try:
        async with session.begin_nested():
            proposals = (await session.execute(select(ConversationTurnProposal).where(
                ConversationTurnProposal.workspace_id == scope.workspace_id,
                ConversationTurnProposal.project_id == scope.project_id,
                ConversationTurnProposal.thread_id == thread.id,
                ConversationTurnProposal.turn_id == source_turn.id,
                ConversationTurnProposal.status == 'proposed').with_for_update())).scalars().all()
            parts = [_decision_part(proposal, 'skipped',
                        summary='Cancelled before dispatch.',
                        started_at=proposal.created_at or now(), finished_at=now())
                     for proposal in proposals]
            parts.append(TextPart(text='Turn cancelled; undispatched steps were stopped and no '
                    'provider charge was created.' if source_turn.language == 'en'
                    else '回合已取消；未派送步驟已停止，並未產生供應商費用。',
                    language=source_turn.language))
            notices = (TurnNotice(code='TURN_CANCELLED',
                message='This turn was cancelled; no undispatched step remains.'),)
            continuation, created = await _continuation_turn(session, scope, thread,
                source_turn, fingerprint, source_turn.language, parts=parts,
                notices=notices, status='cancelled')
            for proposal in proposals:
                proposal.status = 'cancelled'
                proposal.revision += 1
    except IntegrityError as exc:
        if not is_expected_conflict(exc, CANCEL_CONFLICT_CONSTRAINTS):
            raise_unexpected_integrity(exc, 'conversation_turn.cancel')
        recorded = await _recorded_cancellation(session, scope, thread.id, source_turn.id)
        if recorded is None:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
                'a concurrent cancellation is in progress') from exc
        complete_idempotency(outcome, str(recorded.id))
        return thread, role, _payload(recorded)
    complete_idempotency(outcome, str(continuation.id))
    if created:
        from .audit_service import append_audit
        append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
            action='conversation_turn.cancelled', entity_type='conversation_turn',
            entity_id=continuation.id)
    return thread, role, _payload(continuation)


TERMINAL_TURN_STATUSES = frozenset({'completed', 'failed', 'needs_input',
    'needs_approval', 'cancelled', 'outcome_unknown'})


async def turn_status(session, scope: Scope, turn_id):
    turn = await _turn_by_id(session, scope, turn_id)
    return None if turn is None else turn.status


async def stream_turn(session, scope: Scope, turn_id):
    """Authorize streaming for the current actor; read ACL only."""
    turn = await _turn_by_id(session, scope, turn_id)
    if turn is None:
        raise not_found()
    await load(session, scope.workspace_id, scope.project_id, turn.thread_id,
        scope.actor_id)
    return turn


async def reconcile_turn(session, scope: Scope, turn_id, key: str):
    """Resolve an outcome_unknown turn from persisted evidence only.

    Effective resolutions are keyed by a digest of the observed evidence:
    an equivalent attempt (any key/actor) returns the recorded continuation with
    no new probe result and no audit row; a later attempt with new authoritative
    evidence records the next resolution and may transition the source turn out
    of ``outcome_unknown`` exactly once. Replay after a terminal resolution keeps
    returning the recorded result. All evidence reads are read-only: no stage,
    quote, receipt, reservation or provider call is created.
    """
    from .conversation_turn_recovery import probe_outcome
    from ..db.conversation_turn_reconciliations import ConversationTurnReconciliation
    from .audit_service import append_audit
    turn = await _turn_by_id(session, scope, turn_id)
    if turn is None:
        raise not_found()
    thread, role = await load(session, scope.workspace_id, scope.project_id,
        turn.thread_id, scope.actor_id, edit=True, lock=True)
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id,
        actor_id=scope.actor_id, operation_id='conversationTurnReconcile', key=key,
        body={}, target={'project_id': str(scope.project_id),
            'turn_id': str(turn.id)}, precondition=None)
    if outcome.replay:
        row = await _turn_by_id(session, scope, uuid.UUID(outcome.record.resource_id), thread.id)
        if row is None:
            raise not_found()
        return thread, role, _payload(row)

    def latest_resolution():
        return select(ConversationTurnReconciliation).where(
            ConversationTurnReconciliation.workspace_id == scope.workspace_id,
            ConversationTurnReconciliation.source_turn_id == turn.id).order_by(
                ConversationTurnReconciliation.evidence_seq.desc()).limit(1)

    latest = (await session.execute(latest_resolution())).scalar_one_or_none()
    # Contract guard first: reconcile is only for outcome_unknown turns. An
    # already-resolved turn returns the recorded resolution for equivalent
    # evidence, 409 for changed evidence, and never a deadline turn.
    if turn.status != 'outcome_unknown':
        if latest is not None:
            probe = await probe_outcome(session, scope, turn)
            if latest.evidence_digest == probe.evidence_digest:
                recorded = await _turn_by_id(session, scope,
                    latest.continuation_turn_id, thread.id)
                if recorded is None:
                    raise not_found()
                complete_idempotency(outcome, str(recorded.id))
                return thread, role, _payload(recorded)
        raise ApiError(409, 'INVALID_STATE',
            'only an outcome_unknown turn can be reconciled')

    deadline = turn_deadline()

    async def deadline_continuation():
        deadline_fp = digest({'operation': 'conversationTurnReconcileDeadline',
            'turn_id': str(turn.id)})
        async with session.begin_nested():
            return await _deadline_simple_continuation(session, scope, thread, turn,
                deadline_fp, turn.language)

    async def deadline_stop():
        continuation = await deadline_continuation()
        complete_idempotency(outcome, str(continuation.id))
        return thread, role, _payload(continuation)

    if not deadline.should_start():
        return await deadline_stop()

    probe = await probe_outcome(session, scope, turn)
    if not deadline.should_start():
        return await deadline_stop()
    if latest is not None and latest.evidence_digest == probe.evidence_digest:
        recorded = await _turn_by_id(session, scope, latest.continuation_turn_id, thread.id)
        if recorded is None:
            raise not_found()
        complete_idempotency(outcome, str(recorded.id))
        return thread, role, _payload(recorded)
    tool = next((part for part in (turn.parts or [])
        if isinstance(part, dict) and part.get('kind') == 'tool_activity'), None)
    call_id = uuid.UUID(tool['call_id']) if tool and tool.get('call_id') else uuid.uuid5(
        uuid.UUID(str(turn.id)), 'reconcile-probe')
    capability = tool.get('capability') if tool else 'reconciliation'
    if not isinstance(capability, str) or not re.match(r'^[a-z][a-z0-9_.]{2,63}$', capability):
        capability = 'reconciliation'
    state = {'completed': 'completed', 'failed': 'failed',
             'unknown': 'outcome_unknown'}[probe.outcome]
    tool_title = tool.get('title') if tool else 'Reconciled execution'
    if not isinstance(tool_title, str) or not tool_title.strip():
        tool_title = 'Reconciled execution'
    parts = [ToolActivityPart(call_id=call_id, capability=capability,
        title=tool_title[:240], state=state, started_at=turn.created_at or now(),
        finished_at=now(), summary=probe.message[:500],
        error_code=None if probe.outcome == 'completed' else probe.code),
        TextPart(text=probe.message, language=turn.language)]
    notices = (TurnNotice(code=probe.code, message=probe.message),)
    status = {'completed': 'completed', 'failed': 'failed',
              'unknown': 'outcome_unknown'}[probe.outcome]
    fingerprint = digest({'operation': 'conversationTurnReconcile',
        'turn_id': str(turn.id), 'thread_id': str(thread.id),
        'evidence_digest': probe.evidence_digest})
    try:
        async with session.begin_nested():
            continuation, _created = await _continuation_turn(session, scope, thread,
                turn, fingerprint, turn.language, parts=parts, notices=notices,
                status=status)
            current = (await session.execute(latest_resolution())).scalar_one_or_none()
            if current is not None and current.evidence_digest == probe.evidence_digest:
                recorded = await _turn_by_id(session, scope,
                    current.continuation_turn_id, thread.id)
                complete_idempotency(outcome, str(recorded.id))
                return thread, role, _payload(recorded)
            next_seq = 1 if current is None else current.evidence_seq + 1
            session.add(ConversationTurnReconciliation(
                workspace_id=scope.workspace_id, project_id=scope.project_id,
                thread_id=thread.id, source_turn_id=turn.id,
                actor_id=scope.actor_id, evidence_digest=probe.evidence_digest,
                evidence_seq=next_seq, outcome=probe.outcome, code=probe.code,
                message=probe.message, continuation_turn_id=continuation.id))
            if status != 'outcome_unknown':
                # Single authoritative transition out of outcome_unknown.
                turn.status = status
                turn.updated_at = now()
            append_audit(session, workspace_id=scope.workspace_id,
                actor_id=scope.actor_id, action='conversation_turn.reconciled',
                entity_type='conversation_turn', entity_id=continuation.id)
            await session.flush()
    except IntegrityError as exc:
        current = await session.execute(latest_resolution())
        current = current.scalar_one_or_none()
        if current is None:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
                'a concurrent reconciliation is in progress') from exc
        recorded = await _turn_by_id(session, scope, current.continuation_turn_id, thread.id)
        if recorded is None:
            raise not_found()
        complete_idempotency(outcome, str(recorded.id))
        return thread, role, _payload(recorded)
    complete_idempotency(outcome, str(continuation.id))
    return thread, role, _payload(continuation)


async def _recorded_cancellation(session, scope: Scope, thread_id, source_turn_id):
    return (await session.execute(select(ConversationTurn).where(
        ConversationTurn.workspace_id == scope.workspace_id,
        ConversationTurn.project_id == scope.project_id,
        ConversationTurn.thread_id == thread_id,
        ConversationTurn.parent_turn_id == source_turn_id,
        ConversationTurn.status == 'cancelled').order_by(
            ConversationTurn.created_at.desc()).limit(1))).scalar_one_or_none()
