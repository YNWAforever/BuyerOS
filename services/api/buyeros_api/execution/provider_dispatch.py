"""Bounded native provider routing; the production adapter registry stays empty."""
import uuid

from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import ProviderIntent
from buyeros_api.services.worker_execution import outcome
from .provider_context import execution_scope, terminal_business_outcome
from .domain_executor import StaleFenced


def resolve_provider_adapter(service: str, *, environment='production'):
    """Consume the closed activation registry; no fallback or implicit provider."""
    from buyeros_api.providers import registry
    if service not in {'search','model','contact'}:
        return None
    try:
        return registry.resolve_provider(service,environment=environment)
    except registry.ProviderUnavailable:
        return None


def _provider_command(intent_key, event_type, payload):
    from .external_runner import reconcile_intent_key
    if not isinstance(payload, dict):
        return None
    try:
        operation_id = uuid.UUID(payload['operation_id'])
        original = payload['original_intent_key'] if event_type == 'provider.reconcile' else intent_key
        if event_type == 'provider.reconcile' and intent_key != reconcile_intent_key(operation_id):
            return None
        intent = ProviderIntent(original, payload['service'], payload['market'], payload['language'], payload['role'])
        if intent.service not in {'search', 'model', 'contact'}:
            return None
        return operation_id, intent
    except (KeyError, TypeError, ValueError):
        return None


async def execute_provider_claimed(engine, execution, *, adapter=None, checkpoint_dsn=None, environment='production', research_engine=None):
    from .config import get_settings
    envelope = execution.envelope
    async with tenant_session(engine, envelope.workspace_id) as session:
        if not await execution.guard(session):
            return outcome('stale', 'STALE_FENCE')
        event_type, intent_key, payload = execution.row.event_type, execution.row.intent_key, execution.row.payload
    command = _provider_command(intent_key,event_type,payload) if event_type in {'provider.external','provider.reconcile'} else None
    service = (command[1].service if command else None) if event_type in {'provider.external','provider.reconcile'} else ('search' if event_type in {'run.discover','research.reconcile'} else 'contact')
    chosen = adapter or resolve_provider_adapter(service, environment=environment)
    from ..providers.live_search import LiveSearchAdapter
    from ..providers.live_model import LiveModelAdapter
    try:
        with execution_scope(execution):
            if event_type == 'run.fit':
                from .fit_execution import execute_fit
                dsn = checkpoint_dsn or get_settings().checkpoint_database_url
                state = (await execute_fit(engine, envelope.workspace_id, intent_key, envelope.generation,
                                           checkpoint_dsn=dsn, max_buyers=1) if dsn else 'capability_unavailable')
            elif chosen is None or (adapter is not None and environment != 'test'):
                state = 'capability_unavailable'
            elif event_type in {'run.discover', 'contact.lookup', 'provider.external'} and environment != 'test' and not get_settings().paid_dispatch_enabled:
                state = 'execution_disabled'
            elif event_type=='run.discover' and type(chosen) is LiveSearchAdapter:
                from .live_research_runner import execute_live_run_search
                state=await execute_live_run_search(engine,execution,chosen,research_engine=research_engine,environment=environment)
            elif event_type in {'run.discover', 'research.reconcile'}:
                from .discovery_runner import execute_discovery, execute_discovery_reconcile
                runner = execute_discovery if event_type == 'run.discover' else execute_discovery_reconcile
                state = await runner(engine, envelope.workspace_id, intent_key, envelope.generation, adapter=chosen, environment=environment)
            elif event_type == 'contact.lookup':
                from .handlers.contact_submit import execute_contact_lookup
                if payload.get('workspace_id') != str(envelope.workspace_id):
                    state = 'invalid_intent'
                else:
                    from ..providers.live_contact import LiveContactAdapter
                    if type(chosen) is LiveContactAdapter:
                        from .live_contact_runner import execute_live_contact_lookup
                        state=await execute_live_contact_lookup(engine,execution,chosen,
                            research_engine=research_engine,environment=environment)
                    else:
                        state = await execute_contact_lookup(engine, envelope.workspace_id, uuid.UUID(payload['job_id']),
                            envelope.generation, chosen, environment=environment, max_operations=1)
            elif event_type == 'contact.reconcile':
                from .handlers.reconcile import execute_contact_reconcile
                if payload.get('workspace_id') != str(envelope.workspace_id):
                    state = 'invalid_intent'
                else:
                    state = await execute_contact_reconcile(engine, envelope.workspace_id, uuid.UUID(payload['job_id']),
                        uuid.UUID(payload['operation_id']), intent_key, envelope.generation, chosen, environment=environment)
            elif event_type=='provider.external' and type(chosen) is LiveModelAdapter and isinstance(payload,dict) and payload.get('run_id'):
                from .live_run_model import execute_live_run_model
                state=await execute_live_run_model(engine,execution,chosen,research_engine=research_engine,environment=environment)
            elif event_type in {'provider.external', 'provider.reconcile'}:
                from .external_runner import execute_external
                if (event_type=='provider.reconcile' and command and command[1].key.startswith('run-model:') and type(chosen) is LiveModelAdapter):
                    from .live_run_model import execute_received_run_model_status
                    state=await execute_received_run_model_status(engine,execution,chosen,command[0],command[1],environment=environment)
                else:
                    state = (await execute_external(engine, envelope.workspace_id, command[0], envelope.generation,
                    chosen, command[1], environment=environment, outbox_intent_key=intent_key) if command else 'invalid_intent')
                if (event_type=='provider.reconcile' and state=='succeeded' and type(chosen) is LiveSearchAdapter and research_engine is not None):
                    from ..services.run_search import resume_received_run_search
                    async with tenant_session(research_engine,envelope.workspace_id) as session:
                        resumed=await resume_received_run_search(session,workspace_id=envelope.workspace_id,operation_id=command[0],capability=chosen.capability)
                    if chosen.source_transport is not None:
                        from .research_page_runner import execute_permitted_run_pages
                        await execute_permitted_run_pages(research_engine,workspace_id=envelope.workspace_id,
                            run_id=uuid.UUID(resumed['run_id']),capability=chosen.capability,transport=chosen.source_transport)
            else:
                state = 'capability_unavailable'
    except StaleFenced:
        return outcome('stale', 'STALE_FENCE')
    if execution.finished:
        # Status may finish its durable receipt before the optional page await.
        # Keep that earlier proof immutable, but fence this late return against
        # current runtime/generation exactly as a repeated native step is fenced.
        from sqlalchemy import select
        from buyeros_api.db.outbox import OutboxEvent
        from buyeros_api.services.worker_execution import control_row,selected
        async with tenant_session(engine,envelope.workspace_id) as session:
            control=await control_row(session,lock=True)
            row=(await session.execute(select(OutboxEvent).where(OutboxEvent.id==envelope.outbox_id))).scalar_one_or_none()
            if row is None or not selected(control,envelope,row):
                return outcome('stale','STALE_FENCE')
        return execution.result
    async with tenant_session(engine, envelope.workspace_id) as session:
        if not await execution.guard(session):
            return outcome('stale', 'STALE_FENCE')
        result = await terminal_business_outcome(session, execution.row)
        if result is None:
            result = (outcome('reconcile', 'PROVIDER_UNKNOWN') if state in {'unknown', 'pending', 'accepted'} else
                      outcome('blocked', 'EXECUTION_DISABLED' if state == 'execution_disabled' else
                              'CAPABILITY_UNAVAILABLE' if state == 'capability_unavailable' else
                              'ACTOR_CHANGED' if state == 'actor_changed' else 'STEP_FAILED'))
        execution.finish(result)
        return result
