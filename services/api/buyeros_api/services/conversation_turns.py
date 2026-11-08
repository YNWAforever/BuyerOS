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
from datetime import datetime, timezone

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
    Language, NoticePart, OutputLinkPart, OutputRef, ProposalCost, ProposalPart,
    Recovery, TextPart, ToolActivityPart, TurnDecisionRequest, TurnNotice, TurnPayload,
    TurnPlan, TurnRequest, validate_notices, validate_part_list)
from .conversation_access import load, not_found, sales_enabled
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
EXECUTORS = {}


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
    return (f'Selected {count} approved source(s). The live conversation model is not '
            'configured, so this is a source summary with citations, not a generated answer.')


def missing_source_text(language) -> str:
    if language == 'zh-HK':
        return '請先在討論中選取已核准的報價資料或文件，以引用來源。'
    return 'Select approved offer facts or documents in this discussion to ground an answer.'


def _citation_item(source_id: str, label: str) -> CitationItem:
    kind = source_id.split(':', 1)[0]
    return CitationItem(id=source_id, label=label,
        kind=kind if kind in {'document', 'fact', 'drive', 'run', 'results'} else 'document')


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


def build_plan(thread, payload: TurnRequest, skill, project, grounding,
               sales_ok: bool, language_ok: bool):
    """Return ``(TurnPlan, staged_proposal_payload | None)`` deterministically."""
    notices = []
    proposal = None
    staged = None
    steps = ['answer']
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
    elif not grounding.citations:
        notices.append(TurnNotice(code='NEEDS_SELECTED_SOURCE',
            message='Select an approved source before proposing a reviewed action.'))
    elif capability == 'documents.read':
        document_ids = _document_ids(grounding)
        if not document_ids:
            notices.append(TurnNotice(code='NEEDS_SELECTED_DOCUMENT',
                message='Select at least one approved offer document.'))
        else:
            proposal, staged = _proposal(thread, payload, skill, capability, grounding,
                arguments={'document_ids': [str(value) for value in document_ids],
                    'question': payload.text, 'language': payload.language},
                preview={'document_ids': [str(value) for value in document_ids],
                    'question': payload.text[:160], 'language': payload.language},
                title='Summarise selected documents' if payload.language == 'en'
                    else '摘要已選文件',
                rationale='Reads only the currently approved offer sources already selected '
                    'in this discussion; no new discovery or provider call.' if payload.language == 'en'
                    else '只讀取本討論已選取且已核准的報價來源；不新增探索或供應商呼叫。')
            steps.append('propose')
    elif capability == 'research.read':
        proposal, staged = _proposal(thread, payload, skill, capability, grounding,
            arguments={'research_question': payload.text, 'language': payload.language},
            preview={'research_question': payload.text[:160], 'language': payload.language},
            title='Prepare bounded research' if payload.language == 'en' else '準備有界研究',
            rationale='Prepares a research result from selected approved evidence; requires '
                'an existing current native research run.' if payload.language == 'en'
                else '以已選取核准證據準備研究結果；需要現有且最新的原生研究執行。')
        steps.append('propose')
    return TurnPlan(steps=tuple(steps), proposal=proposal, notices=tuple(notices)), staged


def _proposal(thread, payload, skill, capability, grounding, *, arguments, preview,
              title, rationale):
    proposal_id = uuid.uuid5(uuid.UUID(str(thread.id)),
        f'conversation-proposal:{payload.client_message_id}:{capability}')
    staged = {'capability': capability, 'skill_id': skill.id,
        'skill_version': skill.version, 'arguments': arguments,
        'source_refs': _execution_refs(grounding), 'title': title,
        'rationale': rationale, 'arguments_preview': preview}
    part = ProposalPart(proposal_id=proposal_id, capability=capability, title=title,
        rationale=rationale, arguments_preview=preview,
        cost=ProposalCost(kind='nonbillable', amount=0, unit='USD',
            may_incur_provider_charges=False))
    return part, staged


# ---------------------------------------------------------------------------
# Turn creation
# ---------------------------------------------------------------------------

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


async def _turn_by_id(session, scope: Scope, turn_id):
    return (await session.execute(select(ConversationTurn).where(
        ConversationTurn.workspace_id == scope.workspace_id,
        ConversationTurn.project_id == scope.project_id,
        ConversationTurn.id == turn_id))).scalar_one_or_none()


async def _replay(session, scope: Scope, row: ConversationTurn, payload: TurnRequest):
    thread, role = await load(session, scope.workspace_id, scope.project_id, row.thread_id,
        scope.actor_id, edit=True, lock=True)
    if row.request_fingerprint != request_fingerprint(scope, payload, row.thread_id):
        raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
            'this client message key belongs to a different turn request')
    return thread, role, _payload(row)


async def _next_seq(session, thread_id) -> int:
    current = (await session.execute(select(func.coalesce(func.max(ConversationThreadMessage.seq), 0))
        .where(ConversationThreadMessage.thread_id == thread_id))).scalar_one()
    return current + 1


async def _message_count(session, thread) -> int:
    return (await session.execute(select(func.count()).select_from(ConversationThreadMessage)
        .where(ConversationThreadMessage.workspace_id == thread.workspace_id,
            ConversationThreadMessage.thread_id == thread.id))).scalar_one()


async def _grounding(session, scope: Scope, thread):
    thread = thread
    raw = [source.get('id') for source in (thread.sources or [])
        if isinstance(source, dict) and isinstance(source.get('id'), str)]
    resolvable = [value for value in raw if value.split(':', 1)[0] in
        {'document', 'fact', 'drive'}][:MAX_GROUNDING_SOURCES]
    if not resolvable:
        return Grounding([], []), []
    try:
        return await resolve_sources(session, workspace_id=scope.workspace_id,
            project_id=scope.project_id, source_ids=resolvable, readonly=True), []
    except (ApiError, ValueError):
        return Grounding([], []), [TurnNotice(code='SOURCE_UNAVAILABLE',
            message='The selected sources need current review before use.',
            recovery=Recovery(label='Review selected sources'))]


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
    seq = await _next_seq(session, thread.id)
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
    if staged is not None:
        part = next(part for part in parts if isinstance(part, ProposalPart))
        session.add(ConversationTurnProposal(id=part.proposal_id,
            workspace_id=scope.workspace_id, project_id=scope.project_id,
            thread_id=thread.id, turn_id=turn.id, actor_id=scope.actor_id,
            capability=staged['capability'], skill_id=staged['skill_id'],
            skill_version=staged['skill_version'], title=staged['title'],
            rationale=staged['rationale'], arguments=staged['arguments'],
            source_refs=staged['source_refs'], arguments_preview=staged['arguments_preview'],
            cost=part.cost.model_dump(mode='json') if part.cost else None))
    thread.version += 1
    thread.updated_at = now()
    await session.flush()
    return turn


async def create_turn(session, scope: Scope, payload: TurnRequest, key: str):
    thread = None
    if payload.thread_id is not None:
        thread, role = await load(session, scope.workspace_id, scope.project_id,
            payload.thread_id, scope.actor_id, edit=True, lock=True)
        if payload.expected_thread_version is None:
            raise ApiError(400, 'INVALID_REQUEST', 'If-Match thread version is required')
        _check_version(thread.version, payload.expected_thread_version)
    else:
        role = 'owner'
    project = await _project(session, scope)
    existing = await _existing_turn(session, scope, payload.client_message_id)
    if existing is not None:
        return await _replay(session, scope, existing, payload)
    target = ({'project_id': str(scope.project_id), 'thread_id': str(thread.id)}
              if thread is not None else {'project_id': str(scope.project_id), 'new_thread': True})
    precondition = (f'"{payload.expected_thread_version}"'
                    if payload.expected_thread_version is not None else None)
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id,
        actor_id=scope.actor_id, operation_id='conversationTurn', key=key,
        body=payload.model_dump(mode='json'), target=target, precondition=precondition)
    if outcome.replay:
        row = await _turn_by_id(session, scope, uuid.UUID(outcome.record.resource_id))
        if row is None:
            raise not_found()
        return await _replay(session, scope, row, payload)
    saved_fp = request_fingerprint(scope, payload, thread.id if thread is not None else None)
    try:
        async with session.begin_nested():
            if thread is None:
                thread = ConversationThread(workspace_id=scope.workspace_id,
                    project_id=scope.project_id, owner_user_id=scope.actor_id,
                    template_id=payload.template_id or 'custom',
                    title=thread_title(payload.text), sources=[], runs=[], version=1)
                session.add(thread)
                await session.flush()
                saved_fp = request_fingerprint(scope, payload, thread.id)
            if await _message_count(session, thread) + 2 > MAX_THREAD_MESSAGES:
                raise ApiError(409, 'MESSAGE_LIMIT',
                    'discussion note limit reached; start another discussion and keep unsent text')
            grounding, source_notices = await _grounding(session, scope, thread)
            skill = skill_for(thread, payload)
            plan, staged = build_plan(thread, payload, skill, project, grounding,
                sales_enabled(scope.workspace_id),
                payload.language in (project.language_preferences or []))
            parts, answer_notices = answer_parts(grounding, payload.language)
            if plan.proposal is not None:
                parts.append(plan.proposal)
            notices = _dedupe_notices([*source_notices, *answer_notices, *plan.notices])
            if plan.proposal is not None:
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
    except IntegrityError as exc:
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


EXECUTORS.update({'documents.read': _execute_documents, 'research.read': _execute_research})


async def _user_text(session, scope, turn_id) -> str:
    value = (await session.execute(select(ConversationThreadMessage.text).where(
        ConversationThreadMessage.workspace_id == scope.workspace_id,
        ConversationThreadMessage.turn_id == turn_id,
        ConversationThreadMessage.role == 'user'))).scalar_one_or_none()
    return value or 'Conversation request'


async def _continuation_turn(session, scope: Scope, thread, source_turn, request_fp,
                             payload_language, *, parts, notices, status):
    turn_id = uuid.uuid5(uuid.UUID(str(source_turn.id)), f'continuation:{request_fp}')
    existing = await _turn_by_id(session, scope, turn_id)
    if existing is not None:
        return existing
    seq = await _next_seq(session, thread.id)
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
    return turn


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
    _check_version(thread.version, request.expected_thread_version)
    proposal = (await session.execute(select(ConversationTurnProposal).where(
        ConversationTurnProposal.workspace_id == scope.workspace_id,
        ConversationTurnProposal.project_id == scope.project_id,
        ConversationTurnProposal.thread_id == thread.id,
        ConversationTurnProposal.turn_id == source_turn.id,
        ConversationTurnProposal.id == request.proposal_id).with_for_update())).scalar_one_or_none()
    if proposal is None:
        raise not_found()
    fingerprint = digest({'operation': 'conversationTurnDecision',
        'proposal_id': str(request.proposal_id), 'decision': request.decision,
        'actor_id': str(scope.actor_id), 'thread_id': str(thread.id),
        'turn_id': str(source_turn.id)})
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id,
        actor_id=scope.actor_id, operation_id='conversationTurnDecision', key=key,
        body=request.model_dump(mode='json'),
        target={'project_id': str(scope.project_id), 'turn_id': str(source_turn.id)},
        precondition=f'"{request.expected_thread_version}"')
    if outcome.replay:
        row = await _turn_by_id(session, scope, uuid.UUID(outcome.record.resource_id))
        if row is None:
            raise not_found()
        await load(session, scope.workspace_id, scope.project_id, row.thread_id,
            scope.actor_id, edit=True, lock=True)
        return thread, role, _payload(row), False
    existing = (await session.execute(select(ConversationTurnDecision).where(
        ConversationTurnDecision.workspace_id == scope.workspace_id,
        ConversationTurnDecision.proposal_id == request.proposal_id))).scalar_one_or_none()
    if existing is not None:
        if existing.decision != request.decision:
            raise ApiError(409, 'ALREADY_DECIDED', 'this proposal already has a decision')
        row = await _turn_by_id(session, scope, existing.continuation_turn_id)
        complete_idempotency(outcome, str(existing.continuation_turn_id))
        return thread, role, _payload(row), True
    if source_turn.status != 'needs_approval' or proposal.status != 'proposed':
        raise ApiError(409, 'INVALID_STATE', 'this turn has no open proposal')
    try:
        async with session.begin_nested():
            continuation, decided = await _apply_decision(session, scope, thread,
                source_turn, proposal, request, fingerprint)
    except IntegrityError as exc:
        existing = (await session.execute(select(ConversationTurnDecision).where(
            ConversationTurnDecision.workspace_id == scope.workspace_id,
            ConversationTurnDecision.proposal_id == request.proposal_id))).scalar_one_or_none()
        if existing is None:
            raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
                'a concurrent decision for this proposal is in progress') from exc
        complete_idempotency(outcome, str(existing.continuation_turn_id))
        row = await _turn_by_id(session, scope, existing.continuation_turn_id)
        return thread, role, _payload(row), True
    complete_idempotency(outcome, str(continuation.id))
    return thread, role, _payload(continuation), decided


async def _apply_decision(session, scope: Scope, thread, source_turn, proposal,
                          request: TurnDecisionRequest, fingerprint):
    started = proposal.created_at or now()
    if request.decision == 'reject':
        parts = [_decision_part(proposal, 'skipped', summary='Rejected by the reviewer.',
                    started_at=started, finished_at=now()),
            TextPart(text='Proposal rejected; nothing was executed.'
                if source_turn.language == 'en' else '已拒絕提案；未執行任何動作。',
                language=source_turn.language)]
        notices = (TurnNotice(code='PROPOSAL_REJECTED',
            message='The reviewer rejected this proposal.'),)
        continuation = await _continuation_turn(session, scope, thread, source_turn,
            fingerprint, source_turn.language, parts=parts, notices=notices, status='completed')
        proposal.status = 'rejected'
        proposal.revision += 1
        _record_decision(session, scope, source_turn, proposal, request, fingerprint,
            continuation, 'applied')
        return continuation, False
    # Approval: revalidate current membership, role, project, language, sales
    # admission and policy/budget gate state *now*, then execute once.
    project = await _project(session, scope)
    if not sales_enabled(scope.workspace_id):
        return await _blocked_continuation(session, scope, thread, source_turn, proposal,
            fingerprint, 'SALES_ADMISSION_DISABLED',
            'Guided sales execution is disabled for this workspace.'), False
    if source_turn.language not in (project.language_preferences or []):
        return await _blocked_continuation(session, scope, thread, source_turn, proposal,
            fingerprint, 'LANGUAGE_UNAVAILABLE',
            'This project no longer supports the reviewed language.'), False
    from .xverum_dispatch import gates
    await gates(session, scope.workspace_id)  # current policy + budget serialization
    executor = _executor(proposal.capability)
    if executor is None:
        return await _blocked_continuation(session, scope, thread, source_turn, proposal,
            fingerprint, 'CAPABILITY_NOT_AVAILABLE',
            'No reviewed executor is registered for this capability.'), False
    try:
        result = await executor(session, scope, thread, source_turn, proposal)
    except ApiError as exc:
        if exc.status_code in {403, 404}:
            raise
        return await _finish_failure(session, scope, thread, source_turn, proposal,
            fingerprint, 'failed', exc.code, exc.message), False
    except ValueError:
        return await _finish_failure(session, scope, thread, source_turn, proposal,
            fingerprint, 'failed', 'EXECUTION_REJECTED',
            'Current policy, source authority or configuration rejected this execution.'), False
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
    continuation = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, source_turn.language, parts=parts, notices=notices, status=status)
    proposal.status = proposal_status
    proposal.revision += 1
    proposal.result = {'code': result.code,
        'output_id': str(result.output.output_id) if result.output else None,
        'output_revision': result.output.revision if result.output else None,
        'task_id': str(result.task_id) if result.task_id else None}
    _record_decision(session, scope, source_turn, proposal, request, fingerprint,
        continuation, 'applied')
    return continuation, False


async def _blocked_continuation(session, scope, thread, source_turn, proposal,
                                fingerprint, code, message):
    parts = [_decision_part(proposal, 'approved', summary=message,
                started_at=proposal.created_at or now()),
        TextPart(text=message, language=source_turn.language)]
    notices = (TurnNotice(code=code, message=message),)
    continuation = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, source_turn.language, parts=parts, notices=notices, status='needs_input')
    # Non-terminal: the proposal stays open so it can be approved after the
    # workspace is configured. No decision row is recorded.
    return continuation


async def _finish_failure(session, scope, thread, source_turn, proposal, fingerprint,
                          status, code, message):
    parts = [_decision_part(proposal, 'failed' if status == 'failed' else 'outcome_unknown',
                summary=message[:500], error_code=code,
                started_at=proposal.created_at or now(), finished_at=now()),
        TextPart(text=message, language=source_turn.language)]
    notices = (TurnNotice(code=code, message=message),)
    continuation = await _continuation_turn(session, scope, thread, source_turn,
        fingerprint, source_turn.language, parts=parts, notices=notices, status=status)
    return continuation


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
    _check_version(thread.version, expected_version)
    fingerprint = digest({'operation': 'cancelConversationTurn',
        'turn_id': str(source_turn.id), 'actor_id': str(scope.actor_id)})
    outcome = await begin_idempotency(session, workspace_id=scope.workspace_id,
        actor_id=scope.actor_id, operation_id='cancelConversationTurn', key=key,
        body={}, target={'project_id': str(scope.project_id),
            'turn_id': str(source_turn.id)}, precondition=f'"{expected_version}"')
    if outcome.replay:
        row = await _turn_by_id(session, scope, uuid.UUID(outcome.record.resource_id))
        return thread, role, _payload(row)
    if source_turn.status in {'completed', 'failed', 'outcome_unknown', 'cancelled'}:
        complete_idempotency(outcome, str(source_turn.id))
        return thread, role, _payload(source_turn)
    continuation = None
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
            continuation = await _continuation_turn(session, scope, thread, source_turn,
                fingerprint, source_turn.language, parts=parts, notices=notices,
                status='cancelled')
            for proposal in proposals:
                proposal.status = 'cancelled'
                proposal.revision += 1
    except IntegrityError as exc:
        raise ApiError(409, 'IDEMPOTENCY_CONFLICT',
            'a concurrent cancellation is in progress') from exc
    complete_idempotency(outcome, str(continuation.id))
    return thread, role, _payload(continuation)
