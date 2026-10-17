"""Candidate search transport and durable ports; default registry remains closed.

Search snippets are source data, never entity proof, tool instructions or billing
receipts. Only the versioned activation registry may admit a real provider.
"""
from __future__ import annotations
import asyncio,hashlib,json,re,uuid
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from typing import Protocol
import httpx
from .base import LIVE_SEARCH_PROVIDERS,Money,ProviderCapability,ProviderIntent,SubmissionResult,StatusResult
from .search import SearchResult
from ..services.safe_fetch import _safe_https_url,fetch_permitted_document

ENDPOINT='https://api.search.brave.com/res/v1/web/search'
MAX_RESPONSE_BYTES=262144

class SearchResponseUnknown(Exception):
    """No exception implies authoritative proof of non-acceptance or no charge."""

def canonical_json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()

@dataclass(frozen=True)
class SearchRequest:
    key:str
    query:str
    market:str
    language:str
    role:str
    limit:int
    project_id:uuid.UUID
    actor_id:uuid.UUID

    def __post_init__(self):
        if not isinstance(self.key,str) or not 1<=len(self.key)<=128 or self.key!=self.key.strip():raise ValueError('stable search intent required')
        if not isinstance(self.query,str) or not self.query.strip() or len(self.query)>600 or len(self.query.split())>75:raise ValueError('bounded query required')
        if type(self.limit) is not int or not 1<=self.limit<=20:raise ValueError('one bounded vendor request required')
        if not isinstance(self.project_id,uuid.UUID) or not isinstance(self.actor_id,uuid.UUID):raise ValueError('canonical DB references required')
        if not re.fullmatch(r'[A-Z]{2}',self.market) or self.role!='company' or not isinstance(self.language,str) or not 1<=len(self.language)<=32:raise ValueError('bounded company search scope required')

    @property
    def digest(self):return hashlib.sha256(canonical_json(asdict(self))).hexdigest()

class SearchReceipts(Protocol):
    async def claim(self,intent:ProviderIntent)->tuple[dict,bool]:...
    async def finish(self,ref:str,*,state:str,sources:list|None=None,digest:str|None=None)->None:...
    async def get(self,ref:str)->dict|None:...

class BraveSearchClient:
    def __init__(self,*,api_key:str,http:httpx.AsyncClient,language_codes:dict[str,str],api_version:str):
        if not isinstance(api_key,str) or not 1<=len(api_key)<=4096 or any(ord(c)<33 or ord(c)>126 for c in api_key):raise ValueError('server-only subscription token required')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',api_version):raise ValueError('explicit account-verified API version required')
        if not language_codes or any(not isinstance(k,str) or not isinstance(v,str) or not re.fullmatch(r'[a-z]{2,3}(?:-[a-z]{2,8})?',v) for k,v in language_codes.items()):raise ValueError('explicit verified locale mapping required')
        self._api_key,self.http,self.language_codes,self.api_version=api_key,http,dict(language_codes),api_version

    async def search(self,query:str,market:str,language:str,limit:int)->list[SearchResult]:
        if (type(limit) is not int or not 1<=limit<=20 or not isinstance(query,str) or not query.strip() or len(query)>600 or len(query.split())>75 or not re.fullmatch(r'[A-Z]{2}',market) or language not in self.language_codes):raise ValueError('unsupported or unbounded search scope')
        params={'q':query,'country':market,'search_lang':self.language_codes[language],'count':limit,'offset':0,'result_filter':'web','text_decorations':'false','spellcheck':'false'}
        headers={'X-Subscription-Token':self._api_key,'Accept':'application/json','Api-Version':self.api_version}
        try:
            async with asyncio.timeout(10):
                async with self.http.stream('GET',ENDPOINT,params=params,headers=headers,follow_redirects=False,timeout=10) as response:
                    if response.status_code!=200:raise SearchResponseUnknown('vendor result unavailable')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw)+len(chunk)>MAX_RESPONSE_BYTES:raise SearchResponseUnknown('vendor result exceeds limit')
                        raw.extend(chunk)
            body=json.loads(raw)
            if not isinstance(body,dict) or not isinstance(body.get('web'),dict) or not isinstance(body['web'].get('results'),list):raise SearchResponseUnknown('vendor result schema unavailable')
            items=body['web']['results']
            if len(items)>limit:raise SearchResponseUnknown('vendor result count exceeds scope')
            results=[]
            for item in items:
                if (not isinstance(item,dict) or not isinstance(item.get('url'),str) or not 1<=len(item['url'])<=2000 or not isinstance(item.get('title'),str) or not 1<=len(item['title'])<=512 or not isinstance(item.get('description',''),str) or len(item.get('description',''))>4000):raise SearchResponseUnknown('vendor item schema unavailable')
                values=(item['url'],item['title'],item.get('description',''))
                if any(self._api_key in value for value in values):raise SearchResponseUnknown('credential echoed in vendor data')
                checked=_safe_https_url(item['url'])
                if checked is None:raise SearchResponseUnknown('unsafe source URL')
                results.append(SearchResult(checked[0],item['title'],item.get('description','')))
            return results
        except (httpx.HTTPError,TimeoutError,ValueError,UnicodeError) as error:
            raise SearchResponseUnknown('search acceptance or result is unknown') from error

def source_candidate(item:dict,*,expected_company:dict|None=None)->dict:
    if not isinstance(item,dict):raise ValueError('bounded source metadata required')
    url=item.get('url');title=item.get('title');snippet=item.get('snippet','')
    if (not isinstance(url,str) or len(url)>2000 or not isinstance(title,str) or not 1<=len(title)<=512 or not isinstance(snippet,str) or len(snippet)>4000):raise ValueError('bounded source metadata required')
    checked=_safe_https_url(url)
    if checked is None:raise ValueError('unsafe source URL')
    # Domain/name/country hints alone do not establish a legal entity. Do not
    # attach a parent/subsidiary or fabricate a registry identity from a title.
    content={'url':checked[0],'title':title,'snippet':snippet}
    return {'source_url':checked[0],'title':title,'excerpt':snippet,'company_ref':None,'registry_id':None,'entity_status':'needs_review','entity_reason':'legal_entity_proof_required','retrieved_at':datetime.now(timezone.utc).isoformat(),'content_hash':hashlib.sha256(canonical_json(content)).hexdigest(),'content_kind':'search_result_metadata','page_retrieved':False}

class LiveSearchAdapter:
    def __init__(self,*,capability:ProviderCapability,client,receipts:SearchReceipts,source_transport=None):
        if capability.provider not in LIVE_SEARCH_PROVIDERS or capability.service!='search':raise ValueError('code-owned candidate search contract required')
        self.capability,self.client,self.receipts=capability,client,receipts
        self.source_transport=source_transport

    def estimate(self,request:ProviderIntent)->Money:
        if (request.service!='search' or request.market not in self.capability.markets or request.language not in self.capability.languages or request.role not in self.capability.roles or self.capability.max_liability is None):raise ValueError('search contract or scope unavailable')
        return self.capability.max_liability

    async def submit(self,intent:ProviderIntent)->SubmissionResult:
        self.estimate(intent)
        receipt,claimed=await self.receipts.claim(intent)
        request=receipt['request'];ref=receipt['ref']
        if (not isinstance(request,SearchRequest) or (request.key,request.market,request.language,request.role)!=(intent.key,intent.market,intent.language,intent.role)):
            if claimed:await self.receipts.finish(ref,state='unknown')
            return SubmissionResult('unknown',ref)
        if not claimed:return SubmissionResult('accepted' if receipt['state']=='received' else 'unknown',ref)
        try:
            items=await self.client.search(request.query,request.market,request.language,request.limit)
            if not isinstance(items,list) or len(items)>request.limit or any(not isinstance(item,SearchResult) for item in items):raise SearchResponseUnknown('invalid search port result')
            sources=[source_candidate({'url':item.url,'title':item.title,'snippet':item.snippet}) for item in items]
            digest=hashlib.sha256(canonical_json(sources)).hexdigest()
            await self.receipts.finish(ref,state='received',sources=sources,digest=digest)
            saved=await self.receipts.get(ref)
            if saved is None or saved['state']!='received' or saved['digest']!=digest:
                raise SearchResponseUnknown('durable response receipt unavailable')
            return SubmissionResult('accepted',ref,redacted_digest='sha256:'+digest)
        except Exception:
            # The durable claim already precedes the external await. A lost
            # response/finish never resets it to prepared or repeats submission.
            # A write acknowledgement may be lost after a received result was
            # committed. Reconcile read-only before marking an unresolved claim.
            try:
                saved=await self.receipts.get(ref)
                if saved is not None and saved['state']=='received':
                    return SubmissionResult('accepted',ref,redacted_digest='sha256:'+saved['digest'])
                await self.receipts.finish(ref,state='unknown')
            except Exception:pass
            return SubmissionResult('unknown',ref)

    async def status(self,provider_ref:str)->StatusResult:
        receipt=await self.receipts.get(provider_ref)
        if receipt is None or receipt['state']!='received':return StatusResult('unknown',provider_ref)
        # This is the local response receipt, not a supplier invoice or a native
        # request-status/idempotency guarantee. Economic settlement stays separate.
        return StatusResult('succeeded',provider_ref,redacted_digest='sha256:'+receipt['digest'])

    async def fetch_source(self,intent:dict,transport,object_store)->dict:
        return await fetch_permitted_document(intent,transport,object_store)


class PostgresSearchReceipts:
    """Runtime-role durable port, with short transactions around one vendor await.

    Preparing a receipt does not authorize dispatch. Claim rechecks the current
    actor, policy, frozen tariff, reservation and runtime/outbox fence. A crash
    after claim remains unknown and cannot reacquire a submission right.
    """
    def __init__(self,engine,workspace_id:uuid.UUID,capability:ProviderCapability,*,policy_binding=None):
        from .registry import ProviderRegistration
        if engine is None or not isinstance(workspace_id,uuid.UUID):raise ValueError('runtime tenant engine required')
        if capability.provider not in LIVE_SEARCH_PROVIDERS or capability.service!='search' or capability.max_liability is None:raise ValueError('bounded search contract required')
        self.engine,self.workspace_id,self.capability=engine,workspace_id,capability
        from ..api.policy_activation_schemas import ResearchProviderBinding
        from ..services.research_policy_context import selected_binding
        if policy_binding is not None and not isinstance(policy_binding, ResearchProviderBinding):
            raise ValueError('private reviewed search policy binding required')
        self.policy_binding=policy_binding if policy_binding is not None else selected_binding(capability)
        self.contract_hash=ProviderRegistration(capability,lambda:None).contract_hash

    async def _require_schema(self,session):
        from sqlalchemy import text
        if (await session.execute(text('SELECT public.buyeros_search_receipts_writable()'))).scalar_one() is not True:
            raise ValueError('compatible 0040 search receipt migration required for writes')

    def _decode(self,row):
        if row is None:return None
        from ..services.receipt_retention import redacted_receipt
        erased=redacted_receipt(row,response_key='sources')
        if erased is not None:return erased
        values=dict(row);data=dict(values['request'])
        data['project_id']=uuid.UUID(data['project_id']);data['actor_id']=uuid.UUID(data['actor_id'])
        request=SearchRequest(**data)
        if (request.digest!=values['request_hash'] or request.key!=values['intent_key'] or
            request.project_id!=values['project_id'] or request.actor_id!=values['actor_id'] or
            values['contract_hash']!=self.contract_hash or values['pricing_version']!=self.capability.pricing_version):
            raise ValueError('frozen search receipt changed')
        sources=values['response']
        if values['state']=='received' and (not isinstance(sources,list) or len(sources)>request.limit or
            hashlib.sha256(canonical_json(sources)).hexdigest()!=values['response_hash']):raise ValueError('search response receipt changed')
        return {'ref':str(values['id']),'request':request,'state':values['state'],
                'sources':sources or [],'digest':values['response_hash']}

    async def _authorize(self,session,request,operation_id,outbox_id,*,statuses):
        from sqlalchemy import select,text
        from ..db.models import Membership
        from ..db.icp import Project
        from ..db.contact import ProviderOperation
        from ..db.outbox import OutboxEvent
        from ..db.budget import BudgetReservation
        from ..api.deps import permission_for_roles
        from ..execution.external_runner import input_digest
        from ..services.policy_service import evaluate_current_policy
        intent=ProviderIntent(request.key,'search',request.market,request.language,request.role)
        if request.market not in self.capability.markets or request.language not in self.capability.languages or request.role not in self.capability.roles:
            raise ValueError('scope outside frozen search contract')
        outbox=(await session.execute(select(OutboxEvent).where(OutboxEvent.id==outbox_id).with_for_update())).scalar_one_or_none()
        operation=(await session.execute(select(ProviderOperation).where(ProviderOperation.id==operation_id).with_for_update())).scalar_one_or_none()
        reservation=(await session.execute(select(BudgetReservation).where(BudgetReservation.operation_id==operation_id).with_for_update())).scalar_one_or_none()
        member=(await session.execute(select(Membership).where(Membership.user_id==request.actor_id,Membership.active.is_(True)).with_for_update())).scalar_one_or_none()
        project=(await session.execute(select(Project).where(Project.id==request.project_id))).scalar_one_or_none()
        control=(await session.execute(text('SELECT backend,epoch FROM worker_runtime_control'))).one()
        scope_ok=False
        if outbox is not None and isinstance(outbox.payload,dict):
            if outbox.event_type=='provider.external':
                scope_ok=(outbox.payload.get('operation_id')==str(operation_id) and
                    all(outbox.payload.get(k)==v for k,v in {'service':'search','market':request.market,'language':request.language,'role':request.role}.items()))
            elif outbox.event_type=='run.discover':
                from ..services.run_search import require_run_search_request
                run,_=await require_run_search_request(session,workspace_id=self.workspace_id,event=outbox,request=request,capability=self.capability,operation_id=operation_id,new_call=True)
                if statuses=={'submitting'}:
                    from ..services.run_usage import advance_usage
                    advance_usage(run,{'in_flight':0},at=datetime.now(timezone.utc),external=True)
                scope_ok=True
        bound=self.capability.max_liability
        if (outbox is None or outbox.intent_key!=request.key or not scope_ok or outbox.state!='dispatched'
            or outbox.fencing_generation<1 or (outbox.runtime_backend,outbox.runtime_epoch)!=tuple(control)
            or operation is None or operation.intent_key!=request.key or operation.capability!='search' or operation.status not in statuses
            or operation.cancel_requested or operation.input_hash!=input_digest(intent)
            or reservation is None or reservation.state!='active' or reservation.currency!=bound.currency
            or reservation.price_version!=self.capability.pricing_version or reservation.upper_bound!=bound.amount
            or reservation.remaining_hold<bound.amount or member is None or not permission_for_roles(member.roles,'startRun')
            or project is None or project.status!='active'):
            raise ValueError('current search actor, hold, payload or fence unavailable')
        from ..services.research_policy_context import research_use
        policy=await evaluate_current_policy(session,{'workspace_id':self.workspace_id,'project_id':request.project_id},
            'account_research',datetime.now(timezone.utc),
            use_context=research_use(request.project_id,'research.search',binding=self.policy_binding))
        if not policy['allowed']:raise ValueError('current account research policy unavailable')
        return outbox

    async def prepare(self,request:SearchRequest,*,operation_id:uuid.UUID,outbox_id:uuid.UUID)->str:
        from ..db.session import tenant_session
        async with tenant_session(self.engine,self.workspace_id) as session:
            return await self.prepare_in_session(session,request,operation_id=operation_id,outbox_id=outbox_id)

    async def prepare_in_session(self,session,request:SearchRequest,*,operation_id:uuid.UUID,outbox_id:uuid.UUID)->str:
        from sqlalchemy import text
        if not isinstance(request,SearchRequest):raise ValueError('frozen search request required')
        ref=uuid.uuid5(self.workspace_id,request.key)
        await self._require_schema(session)
        existing=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$search$service$,r.id,r.request) AS dependency_expired FROM search_receipts r WHERE intent_key=:key'),{'key':request.key})).mappings().one_or_none()
        if existing is not None:
            saved=self._decode(existing)
            if saved['request']!=request or existing['operation_id']!=operation_id or existing['outbox_id']!=outbox_id:raise ValueError('intent payload already frozen')
            return saved['ref']
        event=await self._authorize(session,request,operation_id,outbox_id,statuses={'reserved'})
        params={'id':ref,'ws':self.workspace_id,'project':request.project_id,'actor':request.actor_id,
            'operation':operation_id,'outbox':outbox_id,'intent':request.key,'request':canonical_json(asdict(request)).decode(),
            'hash':request.digest,'contract':self.contract_hash,'price':self.capability.pricing_version,
            'generation':event.fencing_generation,'epoch':event.runtime_epoch,'backend':event.runtime_backend}
        await session.execute(text("""INSERT INTO search_receipts(id,workspace_id,project_id,actor_id,operation_id,outbox_id,
            intent_key,request,request_hash,contract_hash,pricing_version,generation,runtime_epoch,runtime_backend)
            VALUES(:id,:ws,:project,:actor,:operation,:outbox,:intent,CAST(:request AS jsonb),:hash,:contract,:price,:generation,:epoch,:backend)
            ON CONFLICT(workspace_id,intent_key) DO NOTHING"""),params)
        row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$search$service$,r.id,r.request) AS dependency_expired FROM search_receipts r WHERE intent_key=:key'),{'key':request.key})).mappings().one()
        if (row['request_hash'],row['operation_id'],row['outbox_id'])!=(request.digest,operation_id,outbox_id):raise ValueError('concurrent frozen intent changed')
        return str(ref)

    async def claim(self,intent:ProviderIntent)->tuple[dict,bool]:
        from sqlalchemy import text
        from ..execution.provider_context import execution_session
        if intent.service!='search':raise ValueError('search intent required')
        async with execution_session(self.engine,self.workspace_id) as session:
            await self._require_schema(session)
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$search$service$,r.id,r.request) AS dependency_expired FROM search_receipts r WHERE intent_key=:key FOR UPDATE'),{'key':intent.key})).mappings().one_or_none()
            decoded=self._decode(row)
            if decoded is None:raise ValueError('durable search receipt missing')
            if decoded['state'] in {'redacted','expired'}:return decoded,False
            request=decoded['request']
            if (request.market,request.language,request.role)!=(intent.market,intent.language,intent.role):raise ValueError('frozen search scope changed')
            if decoded['state']!='prepared':return decoded,False
            event=await self._authorize(session,request,row['operation_id'],row['outbox_id'],statuses={'submitting'})
            if (event.fencing_generation,event.runtime_epoch,event.runtime_backend)!=(row['generation'],row['runtime_epoch'],row['runtime_backend']):raise ValueError('stale search receipt fence')
            await session.execute(text("UPDATE search_receipts SET state='submitting',updated_at=now() WHERE id=:id AND state='prepared'"),{'id':row['id']})
            decoded['state']='submitting'
        return decoded,True

    async def finish(self,ref:str,*,state:str,sources:list|None=None,digest:str|None=None)->None:
        from sqlalchemy import text
        from ..execution.provider_context import execution_session
        if state not in {'received','unknown'}:raise ValueError('terminal local receipt required')
        if state=='received' and (not isinstance(sources,list) or len(sources)>20 or len(canonical_json(sources))>MAX_RESPONSE_BYTES or hashlib.sha256(canonical_json(sources)).hexdigest()!=digest):raise ValueError('bounded response digest required')
        if state=='unknown' and (sources is not None or digest is not None):raise ValueError('unknown has no successful result')
        async with execution_session(self.engine,self.workspace_id) as session:
            await self._require_schema(session)
            # A stale worker cannot attach a response to a restored/new generation.
            # Terminal rows are never overwritten, including delayed unknown acks.
            await session.execute(text("""UPDATE search_receipts r SET state=:state,response=CAST(:response AS jsonb),
                response_hash=:digest,updated_at=now() WHERE r.id=:id AND r.state='submitting' AND r.redacted_at IS NULL
                AND EXISTS(SELECT 1 FROM outbox_events e JOIN worker_runtime_control c ON c.singleton=1
                  WHERE e.id=r.outbox_id AND e.workspace_id=r.workspace_id AND e.state='dispatched'
                    AND e.fencing_generation=r.generation AND e.runtime_epoch=r.runtime_epoch
                    AND e.runtime_backend=r.runtime_backend AND c.epoch=r.runtime_epoch AND c.backend=r.runtime_backend)"""),
                {'state':state,'response':canonical_json(sources).decode() if sources is not None else None,'digest':digest,'id':uuid.UUID(ref)})

    async def get(self,ref:str)->dict|None:
        from sqlalchemy import text
        from ..db.session import tenant_session
        try:receipt_id=uuid.UUID(ref)
        except (TypeError,ValueError,AttributeError):return None
        async with tenant_session(self.engine,self.workspace_id,read_only=True) as session:
            row=(await session.execute(text('SELECT r.*,public.buyeros_receipt_dependency_expired(r.workspace_id,$service$search$service$,r.id,r.request) AS dependency_expired FROM search_receipts r WHERE id=:id'),{'id':receipt_id})).mappings().one_or_none()
            saved=self._decode(row)
            if saved is not None and saved['state']=='received':
                from ..services.receipt_retention import require_current_receipt_read
                request=saved['request']
                await require_current_receipt_read(session,workspace_id=self.workspace_id,actor_id=request.actor_id,
                    project_id=request.project_id,source_urls=[item.get('source_url') for item in saved['sources']],
                    empty_search_binding=self.policy_binding if not saved['sources'] else None)
            return saved
