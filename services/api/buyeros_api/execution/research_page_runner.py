"""One durable page claim with two short API transactions around pinned IO.

The page is a bounded permitted excerpt, not canonical entity/role/fit proof.
No object storage upload, paid provider settlement or overall run completion.
"""
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib,uuid
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.session import tenant_session
from ..db.runs import RawCandidate,RunEvent,SearchRun
from ..db.buyers import SourceDocument
from ..providers.live_search import canonical_json
from ..services.research_page_scope import research_page_scope
from ..services.run_events import append_event
from ..services.run_usage import advance_usage
from ..services.receipt_retention import bind_receipt_source
from ..services.safe_fetch import fetch_permitted_document

def scope_hash(scope):return hashlib.sha256(canonical_json(asdict(scope))).hexdigest()

class _ExcerptBuffer:
    # The central sanitizer writes only to this bounded ephemeral server buffer.
    # A private bucket is not needed for excerpt-only research sources.
    def __init__(self):self.body=None;self.digest=None
    async def put_private(self,body,*,digest,retention_seconds):
        if not isinstance(body,bytes) or len(body)>2097152 or retention_seconds<1 or hashlib.sha256(body).hexdigest()!=digest:
            raise ValueError('bounded sanitized page buffer required')
        self.body,self.digest=body,digest
        return 'ephemeral:'+digest

async def execute_research_page(engine,*,workspace_id,run_id,raw_candidate_id,capability,transport=None):
    if transport is None:return {'status':'capability_unavailable'}
    claim=None
    try:
        async with tenant_session(engine,workspace_id) as session:
            # Scope first locks the run; an existing claim may consume the last
            # page slot but cannot authorize a second GET or exceed the ceiling.
            run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id).with_for_update())).scalar_one_or_none()
            claim=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
                RunEvent.event_type=='page.fetch.prepared',RunEvent.payload['raw_candidate_id'].astext==str(raw_candidate_id)))).scalar_one_or_none()
            scope=await research_page_scope(session,workspace_id=workspace_id,run_id=run_id,raw_candidate_id=raw_candidate_id,
                capability=capability,page_claim_id=claim.id if claim is not None else None)
            digest=scope_hash(scope)
            if claim is not None:
                if claim.payload.get('scope_hash')!=digest:return {'status':'stale'}
                final=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
                    RunEvent.event_type=='page.fetch.finished',RunEvent.payload['claim_id'].astext==str(claim.id)))).scalar_one_or_none()
                return dict(final.payload['result']) if final is not None else {'status':'awaiting_reconciliation'}
            advance_usage(run,{'pages':1,'in_flight':1},at=datetime.now(timezone.utc),external=True)
            claim=await append_event(session,run,'page.fetch.prepared',payload={'raw_candidate_id':str(raw_candidate_id),
                'source_document_id':str(scope.source_document_id),'receipt_id':str(scope.receipt_id),'scope_hash':digest,
                'policy_id':str(scope.policy_id),'policy_version':scope.policy_version,
                'runtime_backend':scope.runtime_backend,'runtime_epoch':scope.runtime_epoch})
            claim_id=claim.id;run.version+=1
    except (ValueError,ApiError):return {'status':'stale' if claim is not None else 'blocked'}

    buffer=_ExcerptBuffer()
    result=await fetch_permitted_document({'url':scope.source_url,'permitted':True,'retention_seconds':scope.retention_seconds,'max_page_bytes':scope.max_page_bytes},transport,buffer)
    # Body/byte/permission assertions are code-owned, not vendor instructions.
    if result.get('status')=='retrieved' and (result.get('source_url')!=scope.source_url or
        type(result.get('bytes')) is not int or result['bytes']>scope.max_page_bytes or
        buffer.body is None or result.get('digest')!=buffer.digest or
        result.get('excerpt')!=buffer.body[:4000].decode('utf-8',errors='ignore')):
        result={'status':'quarantined','reason':'page_scope_or_byte_limit'}
    try:
        async with tenant_session(engine,workspace_id) as session:
            current=await research_page_scope(session,workspace_id=workspace_id,run_id=run_id,raw_candidate_id=raw_candidate_id,
                capability=capability,page_claim_id=claim_id)
            if current!=scope:return {'status':'stale'}
            run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id))).scalar_one()
            if result['status']=='retrieved':
                source_id=uuid.uuid5(raw_candidate_id,'page:'+digest)
                session.add(SourceDocument(id=source_id,workspace_id=workspace_id,project_id=run.project_id,run_id=run_id,
                    permission_purpose='account_research',canonical_url=scope.source_url,digest=result['digest'],
                    retrieved_at=datetime.now(timezone.utc),language=result['language'],storage_mode='research_page_excerpt',
                    object_key=None,excerpt=result['excerpt'],retention_until=scope.retention_until))
                await session.flush()
                await bind_receipt_source(session,service='search',receipt_id=scope.receipt_id,source_id=source_id)
                outcome={'status':'retrieved','source_document_id':str(source_id),'entity_status':'needs_review'}
            else:outcome={'status':result['status'],'reason':result.get('reason','retrieval_unavailable')}
            advance_usage(run,{'in_flight':-1},at=datetime.now(timezone.utc));run.version+=1
            await append_event(session,run,'page.fetch.finished',payload={'claim_id':str(claim_id),'result':outcome,
                'page_digest':result.get('digest') if result['status']=='retrieved' else None,
                'excerpt_digest':hashlib.sha256(result['excerpt'].encode()).hexdigest() if result['status']=='retrieved' else None,
                'source_digest':result.get('source_digest') if result['status']=='retrieved' else None,
                'page_bytes':result.get('bytes') if result['status']=='retrieved' else None})
            return outcome
    except (ValueError,ApiError):return {'status':'stale'}
    finally:buffer.body=None

async def execute_permitted_run_pages(engine,*,workspace_id,run_id,capability,transport=None):
    if transport is None:return []
    async with tenant_session(engine,workspace_id) as session:
        raw_ids=list((await session.execute(select(RawCandidate.id).where(RawCandidate.workspace_id==workspace_id,
            RawCandidate.run_id==run_id,RawCandidate.canonical_company_id.is_(None)).order_by(RawCandidate.id).limit(20))).scalars())
    return [await execute_research_page(engine,workspace_id=workspace_id,run_id=run_id,raw_candidate_id=raw,
        capability=capability,transport=transport) for raw in raw_ids]
