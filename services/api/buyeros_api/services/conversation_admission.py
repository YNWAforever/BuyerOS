"""Atomic paid conversation admission, then single claim/await/finish.

No threads, worker jobs, automatic retries or settlements. Even a received model
receipt retains the upper-bound hold until authoritative billing reconciliation.
Selection is code-owned and deliberately absent in this release.
"""
import asyncio
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, text

from ..api.deps import permission_for_roles
from ..api.errors import ApiError
from ..db.contact import ProviderOperation
from ..db.icp import IcpVersion, Project
from ..db.ingestion import OfferDocument
from ..db.models import Membership
from ..db.outbox import OutboxEvent
from ..execution.config import get_settings as dispatch_settings
from ..execution.external_runner import input_digest
from ..providers import conversation_route
from ..providers.base import ProviderIntent, activation_blockers
from ..providers.live_model import ModelRequest, LiveModelAdapter, canonical_json
from ..providers.model_receipts import PostgresModelReceipts
from ..settings import get_settings
from .budget_service import lock_budget_workspace, reserve_operation
from .conversation_reply import ROUTE, resolve_sources
from .policy_service import evaluate_current_policy, evaluate_current_policy_readonly
from .research_policy_context import research_use

# The frozen conversation basis is validated at <=32,000 bytes; the actual
# transport payload is additionally bounded by the reviewed route. History is
# trimmed to fit that real payload, never treated as free context.
MAX_CONVERSATION_INPUT_BYTES = 32_000


def fit_history(grounding, *, history, route, model_id, workspace_id, project_id, actor_id,
                question, thread_id=None, thread_version=None):
    """Return the largest suffix of readable history that fits the real payload.

    Oldest messages are dropped first. The returned basis is the exact frozen
    receipt shape, so ``require_current_basis`` can reproduce the same trim from
    current messages/sources. If the question/sources alone cannot fit, this is an
    honest no-dispatch condition rather than an unbounded provider attempt.
    """
    from ..providers.opencode_model import model_payload
    candidate = [dict(item) for item in (history or ())]
    while True:
        basis = make_basis(grounding, workspace_id=workspace_id, project_id=project_id,
            actor_id=actor_id, question=question, history=candidate or None,
            thread_id=thread_id, thread_version=thread_version)
        if len(canonical_json(model_payload(basis, route, model_id))) <= route.max_input_tokens:
            return candidate, basis
        if not candidate:
            raise ApiError(503, 'CONVERSATION_CONTEXT_TOO_LARGE',
                'selected sources and question exceed the model input budget')
        candidate = candidate[1:]
# A separate reviewed conversation ProviderRegistration is required. Never borrow
# the fit registration or infer selection from a credential/environment switch.
# ``REGISTRATION`` is the explicit test seam; production reads only reviewed
# code-owned registration facts from ``conversation_route`` plus its exact
# workspace/project opt-in.
REGISTRATION = None


def _registration():
    return REGISTRATION if REGISTRATION is not None else conversation_route.conversation_registration()


def unavailable():
    return ApiError(503, 'CONVERSATION_MODEL_UNAVAILABLE', 'conversation model admission is unavailable')


def selected_configuration(market, language, *, workspace_id=None, project_id=None):
    """Select the dedicated conversation route only for its exact explicit scope.

    The route is absent unless every reviewed nonsecret fact is present and the
    request's workspace/project pair is the operator's exact opt-in. The caller's
    market/language must fit the reviewed capability; no request field can widen
    the route, provider, model or account.
    """
    item = _registration()
    if item is None:
        return None
    try:
        opted_in = conversation_route.opted_in(workspace_id, project_id)
    except (TypeError, ValueError):
        opted_in = False
    # The dedicated conversation credential is the only provider-selection fact
    # this route may use. It never selects research or worker provider operations.
    blockers = tuple(code for code in activation_blockers(
        item.capability, market=market, language=language, role='company')
        if code != 'PROVIDER_UNSELECTED')
    if (not opted_in
        or os.environ.get('NEXT_PUBLIC_CONVERSATION_HOME') != 'true'
        or not get_settings().paid_admission_enabled or not dispatch_settings().paid_dispatch_enabled
        or not conversation_route.credential_present()
        or item.model_route != conversation_route.CONVERSATION_ROUTE
        or ROUTE != conversation_route.CONVERSATION_ROUTE
        or item.policy_binding is None or not item.sandbox_evidence
        or item.capability.provider != 'opencode-go'
        or item.capability.service != 'model' or item.capability.max_liability is None
        or item.capability.max_liability.amount <= 0
        or item.capability.max_liability.amount > conversation_route.MAX_QA_CALL_LIABILITY.amount
        or item.capability.max_liability.currency != 'USD'
        or not item.model_id
        or ROUTE.max_input_tokens > 6000 or ROUTE.max_output_tokens > 1000
        or ROUTE.deadline_seconds > 30 or ROUTE.repair_limit != 0 or ROUTE.permitted_tools
        or blockers):
        return None
    return item


def make_basis(grounding, *, workspace_id, project_id, actor_id, question, history=None,
               thread_id=None, thread_version=None):
    basis = {'schema': 'conversation-basis.v1', 'workspace_id': str(workspace_id),
        'project_id': str(project_id), 'actor_id': str(actor_id), 'question': question,
        'icp_version_id': grounding.profile_id, 'icp_hash': grounding.profile_hash,
        'offer_revision': grounding.offer_revision, 'sources': grounding.sources,
        'document_ids': grounding.document_ids}
    # Optional history/thread identity are additive: receipts frozen before
    # context-aware turns have no keys and still reconstruct exactly.
    if history:
        basis['history'] = history
    if thread_id is not None:
        basis['thread_id'] = str(thread_id)
        basis['thread_version'] = int(thread_version)
    return {**basis, 'basis_hash': hashlib.sha256(canonical_json(basis)).hexdigest()}


def configured_for(project, language, *, workspace_id=None, project_id=None):
    """Whether this exact project/workspace currently selects the conversation route.

    Selection is code-owned and disabled by default. This only answers a
    capability question; it never starts an external call.
    """
    market = sorted(project.markets)[0] if project.markets else ''
    return selected_configuration(market, language, workspace_id=workspace_id,
        project_id=project_id) is not None


async def require_current_basis(session, request, capability, *, readonly=False):
    """Receipt claims and reads require current permission, sources and exact policy."""
    basis = request.basis
    ws, project_id, actor = (uuid.UUID(basis[key]) for key in ('workspace_id', 'project_id', 'actor_id'))
    item = selected_configuration(request.market, request.language,
        workspace_id=ws, project_id=project_id)
    if item is None or (item.capability, item.model_route, item.model_id) != (capability, request.route, request.model_id):
        raise unavailable()
    member_query = select(Membership).where(Membership.workspace_id == ws, Membership.user_id == actor)
    if not readonly:
        member_query = member_query.with_for_update(read=True)
    member = (await session.execute(member_query)).scalar_one_or_none()
    if member is None or not member.active or not permission_for_roles(member.roles, 'saveICPVersion'):
        raise ApiError(403, 'PERMISSION_DENIED', 'insufficient role')
    evaluate = evaluate_current_policy_readonly if readonly else evaluate_current_policy
    policy = await evaluate(session, {'workspace_id': ws, 'project_id': project_id},
        'account_research', datetime.now(timezone.utc),
        use_context=research_use(project_id, 'research.model', binding=item.policy_binding).model_copy(
            update={'source_ids': tuple(uuid.UUID(value) for value in basis['document_ids'])}))
    if not policy['allowed']:
        raise ApiError(409, 'POLICY_BLOCKED', 'current conversation model policy required')
    if 'thread_id' in basis:
        from .conversation_access import load as load_thread
        from .conversation_context import readable_history
        try:
            thread_id = uuid.UUID(basis['thread_id'])
            thread, _role = await load_thread(session, ws, project_id, thread_id, actor,
                edit=not readonly, lock=False)
        except (ValueError, TypeError, ApiError) as exc:
            raise unavailable() from exc
        if not readonly and thread.version != basis['thread_version']:
            raise ApiError(412, 'STALE_REVISION', 'conversation thread changed')
    if not readonly:
        # Freeze the brief source check through this short prepare/claim transaction.
        await session.execute(select(Project.id).where(Project.id == project_id).with_for_update(read=True))
        await session.execute(select(IcpVersion.id).where(IcpVersion.id == uuid.UUID(basis['icp_version_id'])).with_for_update(read=True))
        if basis['document_ids']:
            await session.execute(select(OfferDocument.id).where(OfferDocument.id.in_(
                [uuid.UUID(value) for value in basis['document_ids']])).order_by(OfferDocument.id).with_for_update(read=True))
    grounding = await resolve_sources(session, workspace_id=ws, project_id=project_id,
        source_ids=[source['citation']['id'] for source in basis['sources']], readonly=readonly)
    if not grounding.paid_eligible:
        raise ApiError(409, 'POLICY_BLOCKED', 'every selected fact needs an approved document policy scope')
    if make_basis(grounding, workspace_id=ws, project_id=project_id, actor_id=actor, question=basis['question'],
                  history=basis.get('history'), thread_id=basis.get('thread_id'),
                  thread_version=basis.get('thread_version')) != basis:
        raise ApiError(412, 'STALE_REVISION', 'conversation sources changed')
    if not readonly and 'thread_id' in basis:
        # Frozen history is not evidence: re-derive the same bounded/trimmed
        # window from current messages and the real transport budget.
        try:
            current = await readable_history(session, ws, project_id, uuid.UUID(basis['thread_id']))
            trimmed, _ = fit_history(grounding, history=current, route=request.route,
                model_id=request.model_id, workspace_id=ws, project_id=project_id,
                actor_id=actor, question=basis['question'], thread_id=basis['thread_id'],
                thread_version=basis['thread_version'])
        except ApiError:
            raise
        if trimmed != basis.get('history', []):
            raise ApiError(412, 'STALE_REVISION', 'readable conversation history changed')
    project = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one()
    if request.market not in project.markets or request.language not in project.language_preferences:
        raise unavailable()
    return item


async def prepare_conversation(session, *, workspace_id, project_id, actor_id, question, language, key, grounding,
                               history=None, thread_id=None, thread_version=None):
    project = (await session.execute(select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id))).scalar_one()
    market = sorted(project.markets)[0] if project.markets else ''
    item = selected_configuration(market, language, workspace_id=workspace_id, project_id=project_id)
    if item is None:
        return None
    if not grounding.paid_eligible:
        raise ApiError(409, 'POLICY_BLOCKED', 'every selected fact needs an approved document policy scope')
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise ApiError(400, 'INVALID_REQUEST', 'Idempotency-Key header is required')
    intent_key = 'conversation:' + str(uuid.uuid5(workspace_id, f'{actor_id}:{project_id}:{key}'))
    _, basis = fit_history(grounding, history=history, route=ROUTE, model_id=item.model_id,
        workspace_id=workspace_id, project_id=project_id, actor_id=actor_id, question=question,
        thread_id=thread_id, thread_version=thread_version)
    request = ModelRequest(intent_key, basis, ROUTE, item.model_id, market, language, 'company')
    from ..providers.opencode_model import model_payload
    if len(canonical_json(model_payload(basis,ROUTE,item.model_id)))>ROUTE.max_input_tokens:
        raise unavailable()
    await require_current_basis(session, request, item.capability)
    await lock_budget_workspace(session, workspace_id)
    operation_id, event_id = (uuid.uuid5(workspace_id, prefix + intent_key) for prefix in ('operation:', 'event:'))
    intent = ProviderIntent(intent_key, 'model', market, language, 'company')
    store = PostgresModelReceipts(session.bind, workspace_id, item.capability,
        model_id=item.model_id, route=ROUTE, policy_binding=item.policy_binding)
    try:
        await store._schema(session)
    except ValueError as exc:
        raise unavailable() from exc
    operation = (await session.execute(select(ProviderOperation).where(ProviderOperation.id == operation_id).with_for_update())).scalar_one_or_none()
    if operation is None:
        await reserve_operation(session, operation_id, {'workspace_id': workspace_id,
            'project_id': project_id, 'category': 'conversation'}, item.capability.max_liability.amount, 'USD', item.capability.pricing_version)
        control = (await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
        # Terminal sync fence: never claimable/published by either worker dispatcher.
        session.add(OutboxEvent(id=event_id, workspace_id=workspace_id, intent_key=intent_key,
            event_type='conversation.model', state='done', fencing_generation=1,
            runtime_backend=control.backend, runtime_epoch=control.epoch,
            payload={'operation_id': str(operation_id), 'service': 'model', 'market': market,
                'language': language, 'role': 'company', 'registry_contract_hash': item.contract_hash}))
        operation = ProviderOperation(id=operation_id, workspace_id=workspace_id, intent_key=intent_key,
            capability='model', input_hash=input_digest(intent), status='reserved',
            deadline=datetime.now(timezone.utc) + timedelta(seconds=ROUTE.deadline_seconds))
        session.add(operation)
        await session.flush()
    # prepare_in_session validates exact replay against the frozen payload. It
    # cannot reset submitting/received/unknown receipts or acquire a second hold.
    try:
        ref = await store.prepare_in_session(session, request, operation_id=operation_id, outbox_id=event_id)
    except ValueError as exc:
        raise ApiError(409, 'IDEMPOTENCY_CONFLICT', 'conversation intent already frozen') from exc
    operation.provider_ref = ref
    return request, intent, ref, item


async def complete_conversation(engine, workspace_id, prepared):
    """Called only after prepare commits. Adapter claim commits before complete's await.

    A retry never repeats provider work after a received receipt: the frozen
    response is returned as-is. Only a non-received receipt may be submitted.
    """
    request, intent, ref, item = prepared
    store = PostgresModelReceipts(engine, workspace_id, item.capability,
        model_id=item.model_id, route=request.route, policy_binding=item.policy_binding)
    saved = await store.get(ref)
    if saved is not None and saved.get('state') == 'received':
        response = saved.get('response')
        if (not isinstance(response, dict) or not isinstance(response.get('assessment'), dict)
                or saved.get('redacted_at') is not None):
            raise unavailable()
        return response['assessment']
    async with httpx.AsyncClient() as http:
        from ..providers.opencode_model import CONVERSATION_ENDPOINT, OpenCodeGoModelClient
        credential = os.environ.get(conversation_route.CREDENTIAL_ENV)
        if item.capability.provider != 'opencode-go' or not credential:
            raise unavailable()
        client = OpenCodeGoModelClient(api_key=credential, http=http, model_id=item.model_id,
            endpoint=CONVERSATION_ENDPOINT)
        adapter = LiveModelAdapter(capability=item.capability, client=client, receipts=store)
        try:
            # The client enforces its stream deadline too; outer bound covers adapters.
            async with asyncio.timeout(request.route.deadline_seconds + 5):
                result = await adapter.submit(intent)
            if result.state != 'accepted':
                raise unavailable()
            saved = await store.get(ref)
            if saved is None or saved['state'] != 'received':
                raise unavailable()
            return saved['response']['assessment']
        except (ValueError, TimeoutError, asyncio.CancelledError) as exc:
            raise unavailable() from exc
