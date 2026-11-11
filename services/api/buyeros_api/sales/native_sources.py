"""Selected native business evidence; contact values are never materialized here."""
import json
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select
from .contracts import NativeRef


def policy_documents(context):
    """Native source IDs for canonical URL resolution, not offer-document grants."""
    return tuple(sorted({UUID(p['source_id']) for source in context._sources
        for p in source.get('native_proof',[])},key=str))


async def resolve_native_source(session,scope,ref,*,readonly=False):
    from ..services.sales_retention import require_current
    await require_current(session,scope.workspace_id,[ref.id])
    from ..services.sales_native import read_native
    from ..db.icp import Project, IcpVersion, canonical_hash
    from ..db.buyers import Evidence, SourceDocument
    from ..db.runs import RawCandidate
    from ..services.buyer_view import current_evidence_data
    from ..services.policy_service import evaluate_current_policy, evaluate_current_policy_readonly
    from ..services.research_policy_context import research_use
    # Mutations keep the transaction-serialized gate; the read-only enumeration
    # route passes readonly=True and uses the read-only policy snapshot instead.
    evaluate = evaluate_current_policy_readonly if readonly else evaluate_current_policy
    row=await read_native(session,scope,NativeRef(surface=ref.kind,id=ref.id,revision=ref.version))
    project=await session.get(Project,scope.project_id)
    if ref.kind=='profile':
        if (project.active_icp_version_id!=row.id or project.offer_revision!=row.basis_offer_revision
            or canonical_hash(row.content)!=row.content_hash): raise ValueError('current approved profile required')
        from ..services.icp_service import effective_offer_facts
        from ..services.offer_document_refs import validate_offer_document_refs
        from ..api.schemas import OfferFact
        facts=[OfferFact.model_validate(f) for f in effective_offer_facts(row)]
        await validate_offer_document_refs(session,workspace_id=scope.workspace_id,project_id=scope.project_id,
            document_ids=row.content.get('offer_document_ids',[]),facts=facts,lock=False)
        body=json.dumps(row.content,sort_keys=True,ensure_ascii=False)
        if len(body)>12000: raise ValueError('select individual profile facts')
        return [body[i:i+800] for i in range(0,len(body),800)],[]
    query=select(Evidence,SourceDocument,RawCandidate.canonical_company_id).join(SourceDocument,
        (SourceDocument.workspace_id==Evidence.workspace_id)&(SourceDocument.id==Evidence.source_document_id)).outerjoin(
        RawCandidate,(RawCandidate.workspace_id==Evidence.workspace_id)&(RawCandidate.id==Evidence.raw_candidate_id)).where(
        Evidence.workspace_id==scope.workspace_id,Evidence.project_id==scope.project_id)
    if ref.kind=='run':
        if row.icp_version_id!=project.active_icp_version_id: raise ValueError('run profile is no longer current')
        profile=await session.get(IcpVersion,row.icp_version_id)
        if (profile is None or profile.approved_at is None or profile.superseded_at is not None
            or profile.basis_offer_revision!=project.offer_revision
            or canonical_hash(profile.content)!=profile.content_hash):
            raise ValueError('run approved profile basis is no longer current')
        if row.status not in {'completed','partially_completed','partial'}: raise ValueError('native research is not complete; read native run progress')
        query=query.where(Evidence.run_id==row.id)
    else: query=query.where(Evidence.company_id==row.company_id)
    rows=(await session.execute(query.order_by(Evidence.id).limit(13))).all()
    if len(rows)>12: raise ValueError('select a smaller native research scope')
    excerpts=[];sources=[]
    for evidence,source,mapped in rows:
        await require_current(session,scope.workspace_id,[source.id])
        item=await current_evidence_data(session,workspace_id=scope.workspace_id,evidence=evidence,
            source=source,mapped_company_id=mapped,buyer_id=row.id if ref.kind=='buyer' else None)
        if item['status']!='available': raise ValueError('native source evidence unavailable')
        gate=await evaluate(session,{'workspace_id':scope.workspace_id,'project_id':scope.project_id,
            'company_id':evidence.company_id},'account_research',datetime.now(timezone.utc),
            use_context=research_use(scope.project_id,'research.read',urls=[source.canonical_url]))
        if not gate['allowed']: raise ValueError('native evidence policy unavailable')
        excerpts.append(evidence.excerpt)
        sources.append({'id':str(evidence.id),'version':evidence.version,'source_id':str(source.id),
            'digest':source.digest,'excerpt':evidence.excerpt,'stance':evidence.stance,'is_inference':evidence.is_inference})
    if not excerpts: raise ValueError('selected native evidence missing')
    # Include identity/version/provenance in the digest, not just current prose.
    return excerpts,sources
