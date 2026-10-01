"""Bounded native provider routing; the production adapter registry stays empty."""
import uuid

from buyeros_api.db.session import tenant_session
from buyeros_api.providers.base import ProviderIntent
from buyeros_api.services.worker_execution import outcome
from .provider_context import execution_scope, terminal_business_outcome
from .domain_executor import StaleFenced


def resolve_provider_adapter(service: str):
    """A real vendor needs separately verified activation evidence."""
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


async def execute_provider_claimed(engine, execution, *, adapter=None, checkpoint_dsn=None, environment='production'):
    from .config import get_settings
    envelope = execution.envelope
    async with tenant_session(engine, envelope.workspace_id) as session:
        if not await execution.guard(session):
            return outcome('stale', 'STALE_FENCE')
        event_type, intent_key, payload = execution.row.event_type, execution.row.intent_key, execution.row.payload
    chosen = adapter or resolve_provider_adapter('search' if event_type in {'run.discover', 'research.reconcile'} else 'contact')
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
            elif event_type in {'run.discover', 'research.reconcile'}:
                from .discovery_runner import execute_discovery, execute_discovery_reconcile
                runner = execute_discovery if event_type == 'run.discover' else execute_discovery_reconcile
                state = await runner(engine, envelope.workspace_id, intent_key, envelope.generation, adapter=chosen, environment=environment)
            elif event_type == 'contact.lookup':
                from .handlers.contact_submit import execute_contact_lookup
                if payload.get('workspace_id') != str(envelope.workspace_id):
                    state = 'invalid_intent'
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
            elif event_type in {'provider.external', 'provider.reconcile'}:
                from .external_runner import execute_external
                command = _provider_command(intent_key, event_type, payload)
                state = (await execute_external(engine, envelope.workspace_id, command[0], envelope.generation,
                    chosen, command[1], environment=environment, outbox_intent_key=intent_key) if command else 'invalid_intent')
            else:
                state = 'capability_unavailable'
    except StaleFenced:
        return outcome('stale', 'STALE_FENCE')
    if execution.finished:
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
