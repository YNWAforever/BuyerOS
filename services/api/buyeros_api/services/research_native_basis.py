"""Server-row proof for a reviewed native page in downstream model basis.

This read-only API/worker port makes no retrieval, grant or accounting decision.
The caller still validates current actor/profile, model contract/hold and fence.
"""
import hashlib,uuid
from datetime import datetime,timezone,timedelta
from sqlalchemy import select,text
from ..db.buyers import Company,ProjectBuyer,Evidence,SourceDocument
from ..db.runs import RawCandidate,RunEvent,SearchRun
from ..db.policy import PolicyDecision
from .research_candidate_review import _current_reviewed_material

async def reviewed_research_evidence(session,*,workspace_id,run_id,buyer_id,evidence_id):
    if not all(isinstance(x,uuid.UUID) for x in (workspace_id,run_id,buyer_id,evidence_id)):
        raise ValueError('canonical native evidence references required')
    if (await session.execute(text("SELECT current_setting('app.workspace_id',true)"))).scalar_one()!=str(workspace_id):
        raise ValueError('current tenant evidence proof required')
    run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id))).scalar_one_or_none()
    buyer=(await session.execute(select(ProjectBuyer).where(ProjectBuyer.workspace_id==workspace_id,ProjectBuyer.id==buyer_id))).scalar_one_or_none()
    evidence=(await session.execute(select(Evidence).where(Evidence.workspace_id==workspace_id,Evidence.id==evidence_id))).scalar_one_or_none()
    if (run is None or buyer is None or evidence is None or buyer.project_id!=run.project_id
        or evidence.project_id!=run.project_id or evidence.run_id!=run_id or evidence.company_id!=buyer.company_id):
        raise ValueError('current same-run buyer evidence required')
    source=(await session.execute(select(SourceDocument).where(SourceDocument.workspace_id==workspace_id,
        SourceDocument.id==evidence.source_document_id).with_for_update(read=True))).scalar_one_or_none()
    raw=(await session.execute(select(RawCandidate).where(RawCandidate.workspace_id==workspace_id,
        RawCandidate.id==evidence.raw_candidate_id,RawCandidate.run_id==run_id))).scalar_one_or_none()
    company=(await session.execute(select(Company).where(Company.workspace_id==workspace_id,Company.id==buyer.company_id)
        .with_for_update(read=True))).scalar_one_or_none()
    now=datetime.now(timezone.utc)
    if (source is None or raw is None or company is None or source.run_id!=run_id or source.project_id!=run.project_id
        or source.storage_mode!='research_page_excerpt' or source.object_key is not None or source.permission_purpose!='account_research'
        or source.retrieved_at is None or source.retrieved_at>now or source.retention_until is None or source.retention_until<=now
        or not source.excerpt or not 1<=len(source.excerpt.encode())<=4000 or evidence.excerpt not in source.excerpt
        or raw.canonical_company_id!=buyer.company_id or raw.merge_state!='reviewed_page'
        or raw.provider_operation_id!=evidence.provider_operation_id or raw.source_url!=source.canonical_url):
        raise ValueError('current reviewed native source unavailable')
    claim=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='page.fetch.prepared',RunEvent.payload['raw_candidate_id'].astext==str(raw.id)))).scalar_one_or_none()
    prior=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='candidate.page_reviewed',RunEvent.payload['raw_candidate_id'].astext==str(raw.id)))).scalar_one_or_none()
    if claim is None or prior is None:raise ValueError('original native page/review proof required')
    final=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='page.fetch.finished',RunEvent.payload['claim_id'].astext==str(claim.id)))).scalar_one_or_none()
    try:
        receipt_id=uuid.UUID(raw.raw_payload['receipt_id']);metadata_id=uuid.UUID(raw.raw_payload['source_document_id'])
        expected=uuid.uuid5(raw.id,'page:'+claim.payload['scope_hash'])
    except (KeyError,TypeError,ValueError,AttributeError) as exc:raise ValueError('exact native parent references required') from exc
    if (source.id!=expected or prior.payload.get('page_claim_id')!=str(claim.id)
        or prior.payload.get('scope_hash')!=claim.payload.get('scope_hash') or prior.payload.get('page_source_id')!=str(source.id)
        or final is None or final.payload.get('page_digest')!=source.digest
        or final.payload.get('excerpt_digest')!=hashlib.sha256(source.excerpt.encode()).hexdigest()
        or final.payload.get('result')!={'status':'retrieved','source_document_id':str(source.id),'entity_status':'needs_review'}):
        raise ValueError('frozen full page and excerpt proof changed')
    receipt=(await session.execute(text("SELECT operation_id,project_id,state,retention_until,redacted_at FROM search_receipts WHERE workspace_id=:ws AND id=:id"),{'ws':workspace_id,'id':receipt_id})).mappings().one_or_none()
    bindings=(await session.execute(text("SELECT source_id FROM receipt_source_bindings WHERE workspace_id=:ws AND service='search' AND receipt_id=:id AND source_id IN(:page,:metadata)"),{'ws':workspace_id,'id':receipt_id,'page':source.id,'metadata':metadata_id})).scalars().all()
    metadata=(await session.execute(select(SourceDocument).where(SourceDocument.workspace_id==workspace_id,SourceDocument.id==metadata_id))).scalar_one_or_none()
    if (receipt is None or receipt['state']!='received' or receipt['redacted_at'] is not None or receipt['retention_until']<=now
        or receipt['operation_id']!=raw.provider_operation_id or receipt['project_id']!=run.project_id
        or set(bindings)!={source.id,metadata_id} or metadata is None or metadata.run_id!=run_id or metadata.project_id!=run.project_id
        or metadata.retention_until is None or metadata.retention_until<=now or metadata.digest!=raw.candidate_fingerprint
        or metadata.storage_mode!='search_result_metadata' or metadata.canonical_url!=source.canonical_url
        or claim.payload.get('receipt_id')!=str(receipt_id) or claim.payload.get('source_document_id')!=str(metadata_id)):
        raise ValueError('current bound native receipt/metadata unavailable')
    policy=(await session.execute(select(PolicyDecision).where(PolicyDecision.workspace_id==workspace_id,
        PolicyDecision.subject_type=='project',PolicyDecision.subject_id==run.project_id,PolicyDecision.purpose=='account_research')
        .order_by(PolicyDecision.created_at.desc(),PolicyDecision.id.desc()).limit(1))).scalar_one_or_none()
    if (policy is None or policy.controller_scope_id!=workspace_id or policy.status!='permitted' or policy.expires_at<=now
        or policy.basis_reference!=source.canonical_url or not policy.provenance.strip() or policy.decision_author_id is None
        or policy.id!=uuid.UUID(claim.payload['policy_id']) or policy.version!=claim.payload.get('policy_version')
        or not 1<=policy.retention_days<=30 or source.retention_until>min(receipt['retention_until'],metadata.retention_until,
            policy.expires_at,policy.created_at+timedelta(days=policy.retention_days))):
        raise ValueError('current exact source license unavailable')
    from .policy_activation_read import resolve_approved_policy_terms
    from .policy_activation_terms import match_policy_use
    from .research_policy_context import research_use
    terms=await resolve_approved_policy_terms(session,policy,now)
    if terms is None or not match_policy_use(terms,research_use(run.project_id,'research.read',urls=(source.canonical_url,)),now):
        raise ValueError('current approved source read permission required')
    await _current_reviewed_material(session,workspace_id=workspace_id,run=run,raw=raw,company=company,source=source,prior=prior)
    return {'current':True,'source_hash':hashlib.sha256(source.excerpt.encode()).hexdigest(),
        'source_document_hash':source.digest,'source_kind':'research_page_excerpt'}
