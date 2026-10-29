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
from decimal import Decimal

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
from ..providers.base import ProviderIntent, activation_blockers
from ..providers.live_model import ModelRequest, LiveModelAdapter, canonical_json
from ..providers.model_receipts import PostgresModelReceipts
from ..settings import get_settings
from .budget_service import lock_budget_workspace, reserve_operation
from .conversation_reply import ROUTE, resolve_sources
from .policy_service import evaluate_current_policy, evaluate_current_policy_readonly
from .research_policy_context import research_use

MAX_LIABILITY = Decimal('0.100000')
# A separate reviewed conversation ProviderRegistration is required. Never borrow
# the fit registration or infer selection from a credential/environment switch.
REGISTRATION = None


def unavailable():
    return ApiError(503, 'CONVERSATION_MODEL_UNAVAILABLE', 'conversation model admission is unavailable')


def selected_configuration(market, language):
    item = REGISTRATION
    if (os.environ.get('NEXT_PUBLIC_CONVERSATION_HOME') != 'true'
        or not get_settings().paid_admission_enabled or not dispatch_settings().paid_dispatch_enabled
        or ROUTE.route_id != 'conversation-grounded.v1' or item is None
        or item.model_route != ROUTE or item.policy_binding is None or not item.sandbox_evidence
        or item.capability.provider != 'opencode-go'
        or item.capability.service != 'model' or item.capability.max_liability is None
        or item.capability.max_liability.amount != MAX_LIABILITY
        or item.capability.max_liability.currency != 'USD'
        or ROUTE.max_input_tokens > 6000 or ROUTE.max_output_tokens > 1000
        or ROUTE.deadline_seconds > 30 or ROUTE.repair_limit != 0 or ROUTE.permitted_tools
        or activation_blockers(item.capability, market=market, language=language, role='company')):
        return None
    return item


def make_basis(grounding, *, workspace_id, project_id, actor_id, question):
    basis = {'schema': 'conversation-basis.v1', 'workspace_id': str(workspace_id),
        'project_id': str(project_id), 'actor_id': str(actor_id), 'question': question,
        'icp_version_id': grounding.profile_id, 'icp_hash': grounding.profile_hash,
        'offer_revision': grounding.offer_revision, 'sources': grounding.sources,
        'document_ids': grounding.document_ids}
    return {**basis, 'basis_hash': hashlib.sha256(canonical_json(basis)).hexdigest()}


async def require_current_basis(session, request, capability, *, readonly=False):
    """Receipt claims and reads require current permission, sources and exact policy."""
    basis = request.basis
    ws, project_id, actor = (uuid.UUID(basis[key]) for key in ('workspace_id', 'project_id', 'actor_id'))
    item = selected_configuration(request.market, request.language)
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
    if make_basis(grounding, workspace_id=ws, project_id=project_id, actor_id=actor, question=basis['question']) != basis:
        raise ApiError(412, 'STALE_REVISION', 'conversation sources changed')
    project = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one()
    if request.market not in project.markets or request.language not in project.language_preferences:
        raise unavailable()
    return item


async def prepare_conversation(session, *, workspace_id, project_id, actor_id, question, language, key, grounding):
    project = (await session.execute(select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id))).scalar_one()
    market = sorted(project.markets)[0] if project.markets else ''
    item = selected_configuration(market, language)
    if item is None:
        return None
    if not grounding.paid_eligible:
        raise ApiError(409, 'POLICY_BLOCKED', 'every selected fact needs an approved document policy scope')
    if not isinstance(key, str) or not key.strip() or len(key) > 200:
        raise ApiError(400, 'INVALID_REQUEST', 'Idempotency-Key header is required')
    intent_key = 'conversation:' + str(uuid.uuid5(workspace_id, f'{actor_id}:{project_id}:{key}'))
    basis = make_basis(grounding, workspace_id=workspace_id, project_id=project_id, actor_id=actor_id, question=question)
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
            'project_id': project_id, 'category': 'conversation'}, MAX_LIABILITY, 'USD', item.capability.pricing_version)
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
    """Called only after prepare commits. Adapter claim commits before complete's await."""
    request, intent, ref, item = prepared
    store = PostgresModelReceipts(engine, workspace_id, item.capability,
        model_id=item.model_id, route=request.route, policy_binding=item.policy_binding)
    async with httpx.AsyncClient() as http:
        from ..providers.opencode_model import OpenCodeGoModelClient
        if item.capability.provider != 'opencode-go' or not os.environ.get('BUYEROS_OPENCODE_API_KEY'):
            raise unavailable()
        client = OpenCodeGoModelClient(api_key=os.environ['BUYEROS_OPENCODE_API_KEY'], http=http, model_id=item.model_id)
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
