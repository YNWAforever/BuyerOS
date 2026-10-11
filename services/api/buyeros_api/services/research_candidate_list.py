"""Bounded read-only candidate observations; metadata never becomes an entity fact."""
import hashlib,re,uuid
from datetime import datetime,timezone,timedelta
from sqlalchemy import select,func,text
from ..db.runs import RawCandidate,RunEvent
from ..db.buyers import SourceDocument
from ..db.policy import PolicyDecision

def reference(value):
    try:return uuid.UUID(value)
    except (ValueError,TypeError,AttributeError):return None

async def list_research_candidates(session,*,workspace_id,run_id,project_id,offset,limit):
    raw_rows=(await session.execute(select(RawCandidate).where(RawCandidate.workspace_id==workspace_id,
        RawCandidate.run_id==run_id).order_by(RawCandidate.created_at,RawCandidate.id).offset(offset).limit(limit))).scalars().all()
    total=(await session.execute(select(func.count()).select_from(RawCandidate).where(
        RawCandidate.workspace_id==workspace_id,RawCandidate.run_id==run_id))).scalar_one()
    if not raw_rows:return {'items':[],'offset':offset,'limit':limit,'total':total}
    ids=[str(x.id) for x in raw_rows]
    claims=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='page.fetch.prepared',RunEvent.payload['raw_candidate_id'].astext.in_(ids)).limit(limit+1))).scalars().all()
    prepared={};ambiguous=set()
    for claim in claims:
        key=claim.payload.get('raw_candidate_id')
        if key in prepared:ambiguous.add(key)
        prepared[key]=claim
    if len(claims)>limit:ambiguous.update(ids)
    finishes=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='page.fetch.finished',RunEvent.payload['claim_id'].astext.in_([str(x.id) for x in claims]))
        .limit(limit+1))).scalars().all() if claims else []
    finished={};duplicate=set()
    for event in finishes:
        key=event.payload.get('claim_id')
        if key in finished:duplicate.add(key)
        finished[key]=event
    if len(finishes)>limit:duplicate.update(str(x.id) for x in claims)
    source_ids=set();receipt_ids=set();refs={}
    for raw in raw_rows:
        payload=raw.raw_payload or {};metadata=reference(payload.get('source_document_id'));receipt=reference(payload.get('receipt_id'))
        claim=prepared.get(str(raw.id));frozen=(claim.payload or {}).get('scope_hash') if claim else None
        page=uuid.uuid5(raw.id,'page:'+frozen) if isinstance(frozen,str) and re.fullmatch('[0-9a-f]{64}',frozen) else None
        source_ids.update(x for x in (metadata,page) if x is not None)
        if receipt:receipt_ids.add(receipt)
        refs[raw.id]=(metadata,receipt,page)
    sources=(await session.execute(select(SourceDocument).where(SourceDocument.workspace_id==workspace_id,
        SourceDocument.id.in_(source_ids)))).scalars().all() if source_ids else []
    documents={x.id:x for x in sources}
    receipts=(await session.execute(text("SELECT id,operation_id,project_id,state,retention_until,redacted_at FROM search_receipts WHERE workspace_id=:ws AND id=ANY(CAST(:ids AS uuid[]))"),{'ws':workspace_id,'ids':list(receipt_ids)})).mappings().all() if receipt_ids else []
    receipt_map={x['id']:x for x in receipts}
    bindings=(await session.execute(text("SELECT source_id,receipt_id FROM receipt_source_bindings WHERE workspace_id=:ws AND service='search' AND source_id=ANY(CAST(:ids AS uuid[]))"),{'ws':workspace_id,'ids':list(source_ids)})).all() if source_ids else []
    bound=set(bindings)
    policy=(await session.execute(select(PolicyDecision).where(PolicyDecision.workspace_id==workspace_id,
        PolicyDecision.subject_type=='project',PolicyDecision.subject_id==project_id,PolicyDecision.purpose=='account_research')
        .order_by(PolicyDecision.created_at.desc(),PolicyDecision.id.desc()).limit(1))).scalar_one_or_none()
    now=datetime.now(timezone.utc)
    permitted=bool(policy and policy.controller_scope_id==workspace_id and policy.status=='permitted' and policy.expires_at>now
        and policy.decision_author_id is not None and policy.provenance.strip() and 1<=policy.retention_days<=30)
    items=[]
    for raw in raw_rows:
        metadata_id,receipt_id,page_id=refs[raw.id];metadata=documents.get(metadata_id);receipt=receipt_map.get(receipt_id)
        valid=bool(permitted and metadata and receipt and receipt['state']=='received' and receipt['redacted_at'] is None
            and receipt['project_id']==project_id and receipt['retention_until']>now and receipt['operation_id']==raw.provider_operation_id
            and raw.candidate_fingerprint and metadata.id==uuid.uuid5(receipt_id,'source:'+raw.candidate_fingerprint)
            and raw.id==uuid.uuid5(run_id,str(receipt['operation_id'])+':'+raw.candidate_fingerprint)
            and (metadata.id,receipt_id) in bound and metadata.project_id==project_id and metadata.run_id==run_id
            and metadata.storage_mode=='search_result_metadata' and metadata.object_key is None and metadata.permission_purpose=='account_research'
            and metadata.digest==raw.candidate_fingerprint==raw.raw_digest and metadata.canonical_url==raw.source_url==raw.normalized_url
            and metadata.excerpt and metadata.retention_until and metadata.retention_until>now and metadata.retrieved_at and metadata.retrieved_at<=now)
        status='metadata_only' if valid else 'unavailable';visible_page=None
        claim=prepared.get(str(raw.id));final=finished.get(str(claim.id)) if claim else None;page=documents.get(page_id)
        if valid and claim and str(raw.id) not in ambiguous and str(claim.id) not in duplicate:
            if final is None:status='awaiting_reconciliation'
            elif (page and claim.payload.get('receipt_id')==str(receipt_id) and claim.payload.get('source_document_id')==str(metadata_id)
                and final.payload.get('result')=={'status':'retrieved','source_document_id':str(page_id),'entity_status':'needs_review'}
                and page.project_id==project_id and page.run_id==run_id and page.storage_mode=='research_page_excerpt'
                and page.object_key is None and page.permission_purpose=='account_research' and page.canonical_url==metadata.canonical_url
                and page.excerpt and final.payload.get('page_digest')==page.digest
                and final.payload.get('excerpt_digest')==hashlib.sha256(page.excerpt.encode()).hexdigest()
                and (page.id,receipt_id) in bound and page.retrieved_at and page.retrieved_at<=now and page.retention_until and page.retention_until>now
                and policy.basis_reference==page.canonical_url and claim.payload.get('policy_id')==str(policy.id)
                and claim.payload.get('policy_version')==policy.version and page.retention_until<=min(metadata.retention_until,receipt['retention_until'],
                    policy.expires_at,policy.created_at+timedelta(days=policy.retention_days))):
                status='page_available';visible_page=str(page.id)
        items.append({'raw_candidate_id':str(raw.id),'mapping_status':'mapped' if raw.canonical_company_id else 'unmapped',
            'company_id':str(raw.canonical_company_id) if raw.canonical_company_id else None,
            'source_status':status,'page_source_id':visible_page,'title':metadata.excerpt[:200] if valid else None,
            'source_url':metadata.canonical_url if valid else None})
    return {'items':items,'offset':offset,'limit':limit,'total':total}
