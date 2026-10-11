"""Private single-claim contact receipt; current confirmed quote/policy/fence."""
from datetime import datetime,timezone
from dataclasses import asdict
import uuid,hashlib
from sqlalchemy import select,text
from .live_contact import ContactRequest,ContactReceiptCipher,canonical_json,MAX_RESPONSE_BYTES,validate_contact_response
from .registry import ProviderRegistration
from ..db.session import tenant_session
from ..execution.provider_context import execution_session

class PostgresContactReceipts:
    def __init__(self,engine,workspace_id,capability,*,cipher,environment='production'):
        if (engine is None or not isinstance(workspace_id,uuid.UUID) or capability.provider!='hunter' or capability.service!='contact' or capability.max_liability is None or not isinstance(cipher,ContactReceiptCipher)):raise ValueError('bounded private contact contract and key owner required')
        if environment not in {'test','staging','production'}:raise ValueError('known contact execution environment required')
        self.engine,self.workspace_id,self.capability,self.cipher=engine,workspace_id,capability,cipher
        self.environment=environment
        self.contract_hash=ProviderRegistration(capability,lambda:None).contract_hash

    async def _schema(self,session):
        if (await session.execute(text('SELECT public.buyeros_contact_receipts_writable()'))).scalar_one() is not True:raise ValueError('compatible0042 private contact receipt writes required')

    def _decode(self,row,*,reveal=False):
        if row is None:return None
        from ..services.receipt_retention import redacted_receipt
        erased=redacted_receipt(row,response_key='response')
        if erased is not None:return erased
        data=dict(row['request'])
        for key in ['workspace_id','project_id','actor_id','buyer_id','company_id','quote_id']:data[key]=uuid.UUID(data[key])
        request=ContactRequest(**data)
        if (request.workspace_id!=self.workspace_id or request.digest!=row['request_hash'] or request.key!=row['intent_key'] or request.project_id!=row['project_id'] or request.actor_id!=row['actor_id'] or request.buyer_id!=row['buyer_id'] or request.company_id!=row['company_id'] or request.quote_id!=row['quote_id'] or
            row['contract_hash']!=self.contract_hash or request.pricing_version!=self.capability.pricing_version or request.adapter_version!=self.capability.adapter_version):raise ValueError('frozen contact receipt changed')
        response=None;state=row['state']
        if state=='received':
            if row['retention_until']<=datetime.now(timezone.utc):state='expired'
            elif reveal:
                response=self.cipher.open(bytes(row['response_ciphertext']),workspace_id=self.workspace_id,ref=row['id'],request_digest=request.digest,expires_at=row['retention_until'])
                validate_contact_response(response,request)
                if hashlib.sha256(canonical_json(response)).hexdigest()!=row['response_hash']:raise ValueError('private contact response changed')
        return {'ref':str(row['id']),'request':request,'state':state,'response':response,'digest':row['response_hash']}

    async def _scope(self,session,request,*,read_only=False):
        from ..db.models import Membership
        from ..db.icp import Project
        from ..db.buyers import ProjectBuyer,Company
        from ..db.runs import CompanyAlias
        from ..api.deps import permission_for_roles
        from ..services.policy_service import evaluate_current_policy, evaluate_current_policy_readonly
        member=(await session.execute(select(Membership).where(Membership.user_id==request.actor_id,Membership.active.is_(True)))).scalar_one_or_none()
        project=(await session.execute(select(Project).where(Project.id==request.project_id))).scalar_one_or_none()
        buyer=(await session.execute(select(ProjectBuyer).where(ProjectBuyer.id==request.buyer_id,ProjectBuyer.project_id==request.project_id))).scalar_one_or_none()
        company=(await session.execute(select(Company).where(Company.id==request.company_id))).scalar_one_or_none()
        alias=(await session.execute(select(CompanyAlias.id).where(CompanyAlias.company_id==request.company_id,CompanyAlias.alias_type=='domain',CompanyAlias.normalized_value==request.domain,CompanyAlias.reviewed.is_(True),CompanyAlias.superseded_at.is_(None),CompanyAlias.provenance.is_not(None)).limit(1))).scalar_one_or_none()
        if (member is None or not permission_for_roles(member.roles,'confirmLookup') or project is None or project.status!='active' or request.market not in project.markets or request.language not in project.language_preferences or buyer is None or buyer.version!=request.buyer_version or buyer.company_id!=request.company_id or company is None or company.domain!=request.domain or alias is None):raise ValueError('current confirmed contact actor/company basis unavailable')
        evaluate = evaluate_current_policy_readonly if read_only else evaluate_current_policy
        policy=await evaluate(session,{'workspace_id':self.workspace_id,'project_id':request.project_id,'company_id':request.company_id},'contact_research',datetime.now(timezone.utc))
        if not policy['allowed']:raise ValueError('current contact purpose permission unavailable')

    async def _authorize(self,session,request,operation_id,outbox_id,*,statuses):
        from ..db.contact import EnrichmentJob,EnrichmentQuote,ProviderOperation
        from ..db.budget import BudgetReservation
        from ..db.outbox import OutboxEvent
        from ..services.policy_service import policy_workspace_lock
        from ..services.quote_service import quote_hash
        await policy_workspace_lock(session,self.workspace_id)
        if request.workspace_id!=self.workspace_id or request.market not in self.capability.markets or request.language not in self.capability.languages or request.role not in self.capability.roles:raise ValueError('contact scope outside frozen contract')
        candidate=(await session.execute(select(ProviderOperation).where(ProviderOperation.id==operation_id))).scalar_one_or_none()
        if candidate is None or candidate.job_id is None:raise ValueError('confirmed contact operation unavailable')
        job=(await session.execute(select(EnrichmentJob).where(EnrichmentJob.id==candidate.job_id).with_for_update())).scalar_one_or_none()
        quote=(await session.execute(select(EnrichmentQuote).where(EnrichmentQuote.id==request.quote_id))).scalar_one_or_none()
        operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.id==operation_id).with_for_update())).scalar_one()
        event=(await session.execute(select(OutboxEvent).where(OutboxEvent.id==outbox_id).with_for_update())).scalar_one_or_none()
        hold=(await session.execute(select(BudgetReservation).where(BudgetReservation.id==job.reservation_id).with_for_update())).scalar_one_or_none() if job is not None else None
        count=(await session.execute(text('SELECT count(*) FROM provider_operations WHERE job_id=:job'),{'job':job.id})).scalar_one() if job else 0
        control=(await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
        bound=self.capability.max_liability
        basis=next((b for b in (quote.selection or {}).get('resolved',[]) if b.get('buyer_id')==str(request.buyer_id)),None) if quote else None
        if (job is None or job.quote_id!=request.quote_id or job.cancel_requested or job.state not in {'reserved','submitting','pending'} or quote is None or quote.status!='consumed' or quote.consumed_job_id!=job.id or quote.actor_id!=request.actor_id or quote.project_id!=request.project_id or quote.purpose!='contact_research' or quote.quote_hash!=request.quote_hash or quote.price_version!=request.pricing_version or quote.adapter_version!=request.adapter_version or request.role not in quote.roles or quote.contact_type!=request.contact_type or basis is None or not basis.get('eligible') or basis.get('company_id')!=str(request.company_id) or basis.get('buyer_version')!=request.buyer_version or
            operation.intent_key!=request.key or operation.buyer_id!=request.buyer_id or operation.capability!='contact' or operation.status not in statuses or operation.cancel_requested or operation.input_hash!=quote_hash({'quote_hash':quote.quote_hash,'buyer_id':str(request.buyer_id),'roles':quote.roles,'contact_type':quote.contact_type}) or
            event is None or event.intent_key!='contact.lookup:'+str(job.id) or event.event_type!='contact.lookup' or event.state!='dispatched' or event.fencing_generation<1 or (event.runtime_backend,event.runtime_epoch)!=tuple(control) or not isinstance(event.payload,dict) or event.payload.get('job_id')!=str(job.id) or event.payload.get('workspace_id')!=str(self.workspace_id) or
            hold is None or hold.operation_id!=job.id or hold.state!='active' or hold.currency!=bound.currency or hold.price_version!=request.pricing_version or hold.upper_bound!=quote.max_cost or hold.remaining_hold<quote.max_cost or count<1 or quote.max_cost!=count*bound.amount):raise ValueError('current contact confirmation, hold or fence unavailable')
        frozen=(quote.selection or {}).get('contact_configuration')
        # Only explicit owned test environments may prepare legacy unscoped
        # fixtures. New scoped quotes are checked in every environment. Original
        # received/unknown claims return before this new-call authorization.
        if self.environment!='test' or frozen is not None:
            from ..services.contact_configuration import current_contact_configuration
            current=current_contact_configuration(self.capability,market=request.market,
                language=request.language,role=request.role,environment=self.environment)
            if (frozen!=current or request.limit!=current['limit'] or request.contact_type!=current['contact_type']
                or not quote.roles or request.role!=quote.roles[0]):
                raise ValueError('current contact frozen quote configuration changed')
        await self._scope(session,request)
        return event

    async def prepare(self,request,*,operation_id,outbox_id,expires_at):
        if not isinstance(request,ContactRequest) or not isinstance(expires_at,datetime) or expires_at.tzinfo is None or not datetime.now(timezone.utc)<expires_at:raise ValueError('current private contact request required')
        ref=uuid.uuid5(self.workspace_id,request.key)
        # Validate finite retention before any database write without retaining PII.
        self.cipher.seal({},workspace_id=self.workspace_id,ref=ref,request_digest=request.digest,expires_at=expires_at)
        async with tenant_session(self.engine,self.workspace_id) as session:
            await self._schema(session)
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$contact$service$,r.id,r.request) AS dependency_expired FROM contact_receipts r WHERE intent_key=:key'),{'key':request.key})).mappings().one_or_none()
            if row is not None:
                saved=self._decode(row)
                if saved['request']!=request or row['operation_id']!=operation_id or row['outbox_id']!=outbox_id:raise ValueError('contact intent already frozen')
                return saved['ref']
            event=await self._authorize(session,request,operation_id,outbox_id,statuses={'intent','reserved'})
            await session.execute(text("""INSERT INTO contact_receipts(id,workspace_id,project_id,actor_id,buyer_id,company_id,quote_id,operation_id,outbox_id,intent_key,request,request_hash,contract_hash,pricing_version,generation,runtime_epoch,runtime_backend,retention_until)
                VALUES(:id,:ws,:project,:actor,:buyer,:company,:quote,:operation,:outbox,:key,CAST(:request AS jsonb),:hash,:contract,:price,:generation,:epoch,:backend,:expiry) ON CONFLICT(workspace_id,intent_key) DO NOTHING"""),
                {'id':ref,'ws':self.workspace_id,'project':request.project_id,'actor':request.actor_id,'buyer':request.buyer_id,'company':request.company_id,'quote':request.quote_id,'operation':operation_id,'outbox':outbox_id,'key':request.key,'request':canonical_json(asdict(request)).decode(),'hash':request.digest,'contract':self.contract_hash,'price':self.capability.pricing_version,'generation':event.fencing_generation,'epoch':event.runtime_epoch,'backend':event.runtime_backend,'expiry':expires_at})
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$contact$service$,r.id,r.request) AS dependency_expired FROM contact_receipts r WHERE intent_key=:key'),{'key':request.key})).mappings().one()
            if (row['request_hash'],row['operation_id'],row['outbox_id'])!=(request.digest,operation_id,outbox_id):raise ValueError('concurrent frozen contact intent changed')
        return str(ref)

    async def claim(self,intent):
        if intent.service!='contact':raise ValueError('contact intent required')
        async with execution_session(self.engine,self.workspace_id) as session:
            await self._schema(session)
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$contact$service$,r.id,r.request) AS dependency_expired FROM contact_receipts r WHERE intent_key=:key FOR UPDATE'),{'key':intent.key})).mappings().one_or_none();saved=self._decode(row)
            if saved is None:raise ValueError('private durable contact receipt unavailable')
            if saved['state'] in {'redacted','expired'}:return saved,False
            request=saved['request']
            if (request.market,request.language,request.role)!=(intent.market,intent.language,intent.role):raise ValueError('frozen contact scope changed')
            if saved['state']!='prepared':return saved,False
            if row['retention_until']<=datetime.now(timezone.utc):raise ValueError('contact retention expired before dispatch')
            event=await self._authorize(session,request,row['operation_id'],row['outbox_id'],statuses={'submitting'})
            if (event.fencing_generation,event.runtime_backend,event.runtime_epoch)!=(row['generation'],row['runtime_backend'],row['runtime_epoch']):raise ValueError('stale contact receipt fence')
            await session.execute(text("UPDATE contact_receipts SET state='submitting',updated_at=now() WHERE id=:id AND state='prepared'"),{'id':row['id']});saved['state']='submitting'
        return saved,True

    async def finish(self,ref,*,state,response=None,digest=None):
        if state not in {'received','unknown'} or (state=='unknown' and (response is not None or digest is not None)):raise ValueError('terminal private contact receipt required')
        if state=='received' and (not isinstance(response,dict) or response.get('verified_contacts')!=[] or len(canonical_json(response))>MAX_RESPONSE_BYTES or hashlib.sha256(canonical_json(response)).hexdigest()!=digest):raise ValueError('hashed bounded unverified contact result required')
        async with execution_session(self.engine,self.workspace_id) as session:
            await self._schema(session)
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$contact$service$,r.id,r.request) AS dependency_expired FROM contact_receipts r WHERE id=:id FOR UPDATE'),{'id':uuid.UUID(ref)})).mappings().one_or_none()
            if row is None or row['state']!='submitting':return
            if response is not None:validate_contact_response(response,self._decode(row)['request'])
            blob=self.cipher.seal(response,workspace_id=self.workspace_id,ref=row['id'],request_digest=row['request_hash'],expires_at=row['retention_until']) if response is not None else None
            await session.execute(text("""UPDATE contact_receipts r SET state=:state,response_ciphertext=:blob,response_hash=:digest,updated_at=now()
                WHERE r.id=:id AND r.state='submitting' AND r.redacted_at IS NULL AND EXISTS(SELECT 1 FROM outbox_events e JOIN worker_runtime_control c ON c.singleton=1
                WHERE e.id=r.outbox_id AND e.workspace_id=r.workspace_id AND e.state='dispatched' AND e.fencing_generation=r.generation
                AND e.runtime_backend=r.runtime_backend AND e.runtime_epoch=r.runtime_epoch AND c.backend=r.runtime_backend AND c.epoch=r.runtime_epoch)"""),{'id':row['id'],'state':state,'blob':blob,'digest':digest})

    async def get(self,ref):
        try:receipt_id=uuid.UUID(ref)
        except (ValueError,TypeError,AttributeError):return None
        async with tenant_session(self.engine,self.workspace_id,read_only=True) as session:
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$contact$service$,r.id,r.request) AS dependency_expired FROM contact_receipts r WHERE id=:id'),{'id':receipt_id})).mappings().one_or_none()
            saved=self._decode(row)
            if saved is None:return None
            if saved['state']=='received':
                await self._scope(session,saved['request'],read_only=True)
                return self._decode(row,reveal=True)
            return saved
