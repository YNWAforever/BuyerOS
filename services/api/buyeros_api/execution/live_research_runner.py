"""One API-hosted native search unit; separate API/worker DB authority.

Preparation/intake use the API host's existing engine. Only the worker engine
can consume a receipt's submit right. Neither transaction spans vendor IO.
No new live registration or canonical/billing assertion is made here.
"""
from ..db.session import tenant_session
from ..providers.live_search import LiveSearchAdapter,PostgresSearchReceipts
from ..services.run_search import prepare_run_search
from ..services.search_intake import ingest_received_search
from .external_runner import execute_external

async def execute_live_run_search(worker_engine,execution,adapter,*,research_engine,environment):
    if research_engine is None or type(adapter) is not LiveSearchAdapter:
        return 'capability_unavailable'
    envelope=execution.envelope
    # The normal API engine stays local to this signed API host request. It is
    # never passed to Cloudflare/Celery messages or stored in an outbox payload.
    async with tenant_session(research_engine,envelope.workspace_id) as session:
        prepared=await prepare_run_search(session,workspace_id=envelope.workspace_id,outbox_id=envelope.outbox_id,
            generation=envelope.generation,capability=adapter.capability)
    scoped=LiveSearchAdapter(capability=adapter.capability,client=adapter.client,
        receipts=PostgresSearchReceipts(worker_engine,envelope.workspace_id,adapter.capability))
    state=await execute_external(worker_engine,envelope.workspace_id,prepared.operation_id,envelope.generation,
        scoped,prepared.intent,environment=environment,outbox_intent_key=prepared.intent.key)
    if state=='accepted':
        # Received metadata is useful while the financial hold remains unknown.
        # Current profile/policy/receipt/runtime locks are rechecked at commit.
        async with tenant_session(research_engine,envelope.workspace_id) as session:
            await ingest_received_search(session,workspace_id=envelope.workspace_id,run_id=prepared.run_id,
                receipt_id=prepared.receipt_id,capability=adapter.capability)
        if adapter.source_transport is not None:
            from .research_page_runner import execute_permitted_run_pages
            await execute_permitted_run_pages(research_engine,workspace_id=envelope.workspace_id,run_id=prepared.run_id,
                capability=adapter.capability,transport=adapter.source_transport)
    return state
