"""Prepare a server-owned private contact receipt before one bounded native submit."""
from datetime import datetime,timedelta,timezone
import uuid
from sqlalchemy import select
from ..db.session import tenant_session
from ..db.contact import EnrichmentJob,EnrichmentQuote,ProviderOperation
from ..db.buyers import Company
from ..providers.live_contact import LiveContactAdapter,ContactRequest,ContactReceiptCipher
from ..providers.contact_receipts import PostgresContactReceipts
from ..services.contact_configuration import current_contact_configuration
from .handlers.contact_submit import execute_contact_lookup


async def execute_live_contact_lookup(engine,execution,adapter,*,research_engine,environment):
    envelope=execution.envelope
    store=getattr(adapter,'receipts',None)
    if (research_engine is None or type(adapter) is not LiveContactAdapter
        or type(store) is not PostgresContactReceipts or store.workspace_id!=envelope.workspace_id
        or store.capability!=adapter.capability or store.environment!=environment
        or not isinstance(store.cipher,ContactReceiptCipher)):
        return 'capability_unavailable'
    request=None;operation_id=None
    try:
        # This read transaction closes before private prepare or adapter IO.
        # Receipt prepare then rechecks actor/company/policy/hold and original
        # outbox fence under its own short transaction, before inserting.
        async with tenant_session(research_engine,envelope.workspace_id,read_only=True) as session:
            job=(await session.execute(select(EnrichmentJob).where(EnrichmentJob.id==uuid.UUID(execution.row.payload['job_id'])))).scalar_one_or_none()
            if job is None:
                return 'missing'
            operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.job_id==job.id,
                ProviderOperation.status.in_({'intent','reserved'})).order_by(ProviderOperation.id).limit(1))).scalar_one_or_none()
            if operation is not None and not job.cancel_requested:
                quote=(await session.execute(select(EnrichmentQuote).where(EnrichmentQuote.id==job.quote_id))).scalar_one()
                frozen=(quote.selection or {}).get('contact_configuration')
                if not isinstance(frozen,dict) or not quote.roles:
                    return 'capability_unavailable'
                config=current_contact_configuration(adapter.capability,market=frozen.get('market'),
                    language=frozen.get('language'),role=quote.roles[0],environment=environment)
                if frozen!=config or adapter.account_reference!=config['account_reference']:
                    return 'capability_unavailable'
                basis=next((row for row in (quote.selection or {}).get('resolved',[])
                    if row.get('buyer_id')==str(operation.buyer_id) and row.get('eligible') is True),None)
                if basis is None:
                    return 'capability_unavailable'
                company=(await session.execute(select(Company).where(Company.id==uuid.UUID(basis['company_id'])))).scalar_one()
                request=ContactRequest(key=operation.intent_key,workspace_id=envelope.workspace_id,
                    project_id=quote.project_id,actor_id=quote.actor_id,buyer_id=operation.buyer_id,
                    company_id=company.id,buyer_version=basis['buyer_version'],quote_id=quote.id,
                    quote_hash=quote.quote_hash,pricing_version=quote.price_version,adapter_version=quote.adapter_version,
                    domain=company.domain,market=config['market'],language=config['language'],role=quote.roles[0],
                    contact_type=config['contact_type'],limit=config['limit'])
                operation_id=operation.id
                job_id=job.id
            else:
                job_id=job.id
        if request is not None:
            preparing=PostgresContactReceipts(research_engine,envelope.workspace_id,adapter.capability,
                cipher=store.cipher,environment=environment)
            try:
                await preparing.prepare(request,operation_id=operation_id,outbox_id=envelope.outbox_id,
                    expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
            except ValueError as error:
                if str(error)!='current contact purpose permission unavailable':
                    return 'capability_unavailable'
                # Preserve the existing proven-unsent policy cancellation and
                # bounded release. Mixed accepted/unknown jobs keep their holds.
    except (ValueError,KeyError,TypeError):
        return 'capability_unavailable'
    return await execute_contact_lookup(engine,envelope.workspace_id,job_id,envelope.generation,
        adapter,environment=environment,max_operations=1)
