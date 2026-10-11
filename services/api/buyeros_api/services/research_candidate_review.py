"""Explicit human review of a current native page into an existing entity.

Internal API-role port. Its caller supplies the authenticated canonical actor;
there is no public client permission token, automatic entity merge or role fact.
"""
import hashlib,json,re,uuid
from datetime import datetime,timezone
from sqlalchemy import select,text
from sqlalchemy.dialects.postgresql import insert
from ..db.models import Membership
from ..db.buyers import Company,ProjectBuyer,SourceDocument,Evidence
from ..db.runs import RawCandidate,RunEvent,SearchRun,CompanyAlias
from ..db.outcomes import AuditEvent
from .research_page_scope import research_page_scope
from ..execution.research_page_runner import scope_hash
from .run_events import append_event

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def company_digest(company):
    return digest({'id':str(company.id),'legal_name':company.legal_name,'display_name':company.display_name,
        'domain':company.domain,'registry_id':company.registry_id})

async def _current_reviewed_material(session,*,workspace_id,run,raw,company,source,prior):
    try:
        result=prior.payload['result'];input_hash=prior.payload['input_hash']
        alias_id,evidence_id,buyer_id=(uuid.UUID(result[k]) for k in ('alias_id','evidence_id','buyer_id'))
    except (AttributeError,KeyError,TypeError,ValueError) as exc:raise ValueError('current accepted review references required') from exc
    if (not isinstance(input_hash,str) or not re.fullmatch('[0-9a-f]{64}',input_hash)
        or alias_id!=uuid.uuid5(raw.id,'review-alias:'+input_hash) or evidence_id!=uuid.uuid5(raw.id,'review-evidence:'+input_hash)):
        raise ValueError('current accepted review hashes required')
    alias=(await session.execute(select(CompanyAlias).where(CompanyAlias.workspace_id==workspace_id,CompanyAlias.id==alias_id,
        CompanyAlias.raw_candidate_id==raw.id,CompanyAlias.superseded_at.is_(None)).with_for_update(read=True))).scalar_one_or_none()
    buyer=(await session.execute(select(ProjectBuyer).where(ProjectBuyer.workspace_id==workspace_id,ProjectBuyer.id==buyer_id,
        ProjectBuyer.project_id==run.project_id).with_for_update(read=True))).scalar_one_or_none()
    evidence=(await session.execute(select(Evidence).where(Evidence.workspace_id==workspace_id,Evidence.id==evidence_id)
        .with_for_update(read=True))).scalar_one_or_none()
    audit=(await session.execute(select(AuditEvent).where(AuditEvent.workspace_id==workspace_id,AuditEvent.action=='candidate.page_reviewed',
        AuditEvent.subject_type=='raw_candidate',AuditEvent.subject_id==str(raw.id),AuditEvent.detail_digest=='sha256:'+input_hash))).scalar_one_or_none()
    frozen=prior.payload
    if (audit is None or frozen.get('review_actor_id')!=str(audit.actor_id)
        or frozen.get('company_hash')!=company_digest(company) or evidence is None
        or frozen.get('review_excerpt_hash')!=hashlib.sha256(evidence.excerpt.encode()).hexdigest()
        or not isinstance(frozen.get('review_reason_hash'),str) or not re.fullmatch('[0-9a-f]{64}',frozen['review_reason_hash'])
        or digest({'raw':str(raw.id),'source':str(source.id),'page_digest':source.digest,'company':str(company.id),
            'company_hash':company_digest(company),'actor':str(audit.actor_id),
            'excerpt_digest':hashlib.sha256(evidence.excerpt.encode()).hexdigest(),'reason_digest':frozen['review_reason_hash'],
            'scope_hash':frozen.get('scope_hash')})!=input_hash):
        raise ValueError('original review quote/material proof unavailable or changed')
    if (alias is None or alias.company_id!=company.id or not alias.reviewed or alias.alias_type!='reviewed_page'
        or alias.decision_state!='reviewed_page' or alias.normalized_value!=company_digest(company) or audit is None
        or alias.provenance!='actor:'+str(audit.actor_id) or buyer is None or buyer.company_id!=company.id
        or evidence is None or evidence.version!=1 or evidence.company_id!=company.id or evidence.source_document_id!=source.id
        or evidence.content_hash!=input_hash or evidence.project_id!=run.project_id or evidence.run_id!=run.id
        or evidence.raw_candidate_id!=raw.id or evidence.provider_operation_id!=raw.provider_operation_id
        or evidence.stance!='qualifies' or not evidence.is_inference or evidence.excerpt not in source.excerpt):
        raise ValueError('accepted review mapping material no longer current')

async def _current_review_basis(session,*,workspace_id,run_id,raw_candidate_id,company_id,actor_id,capability,
        page_source_id=None,expected_page_digest=None,expected_company_hash=None,excerpt=None):
    if not all(isinstance(x,uuid.UUID) for x in (workspace_id,run_id,raw_candidate_id,company_id,actor_id)):
        raise ValueError('canonical review references required')
    api_only=(await session.execute(text("SELECT pg_has_role(session_user,'buyeros_api','MEMBER') AND NOT pg_has_role(session_user,'buyeros_worker','MEMBER')"))).scalar_one()
    if not api_only or (await session.execute(text("SELECT current_setting('app.workspace_id',true)"))).scalar_one()!=str(workspace_id):
        raise ValueError('current tenant API review required')
    member=(await session.execute(select(Membership).where(Membership.workspace_id==workspace_id,
        Membership.user_id==actor_id,Membership.active.is_(True)).with_for_update(read=True))).scalar_one_or_none()
    if member is None or not {'reviewer','workspace_admin'}.intersection(member.roles):raise ValueError('current reviewer membership required')
    run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id).with_for_update())).scalar_one_or_none()
    raw=(await session.execute(select(RawCandidate).where(RawCandidate.workspace_id==workspace_id,
        RawCandidate.run_id==run_id,RawCandidate.id==raw_candidate_id).with_for_update())).scalar_one_or_none()
    company=(await session.execute(select(Company).where(Company.workspace_id==workspace_id,Company.id==company_id).with_for_update(read=True))).scalar_one_or_none()
    if run is None or raw is None or company is None or (expected_company_hash is not None and company_digest(company)!=expected_company_hash):
        raise ValueError('current run/candidate/explicit existing company required')
    if raw.canonical_company_id is not None and raw.canonical_company_id!=company_id:raise ValueError('review replay cannot relink a canonical entity')
    claim=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='page.fetch.prepared',RunEvent.payload['raw_candidate_id'].astext==str(raw.id)))).scalar_one_or_none()
    if claim is None:raise ValueError('original durable page claim required')
    scope=await research_page_scope(session,workspace_id=workspace_id,run_id=run_id,raw_candidate_id=raw.id,
        capability=capability,page_claim_id=claim.id,reviewed_company_id=company_id if raw.canonical_company_id is not None else None)
    frozen=scope_hash(scope)
    final=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='page.fetch.finished',RunEvent.payload['claim_id'].astext==str(claim.id)))).scalar_one_or_none()
    page_source_id=page_source_id or uuid.uuid5(raw.id,'page:'+frozen)
    source=(await session.execute(select(SourceDocument).where(SourceDocument.workspace_id==workspace_id,
        SourceDocument.id==page_source_id).with_for_update(read=True))).scalar_one_or_none()
    now=datetime.now(timezone.utc)
    if (claim.payload.get('scope_hash')!=frozen or final is None or
        final.payload.get('result')!={'status':'retrieved','source_document_id':str(page_source_id),'entity_status':'needs_review'} or
        source is None or source.id!=uuid.uuid5(raw.id,'page:'+frozen) or source.project_id!=run.project_id or source.run_id!=run.id or
        source.storage_mode!='research_page_excerpt' or source.object_key is not None or source.permission_purpose!='account_research' or
        source.canonical_url!=scope.source_url or (expected_page_digest is not None and source.digest!=expected_page_digest) or
        final.payload.get('page_digest')!=source.digest or not source.excerpt or
        final.payload.get('excerpt_digest')!=hashlib.sha256(source.excerpt.encode()).hexdigest() or
        source.retention_until is None or source.retention_until<=now or source.retention_until>scope.retention_until or
        source.retrieved_at is None or source.retrieved_at>now or (excerpt is not None and excerpt not in source.excerpt) or
        not company.legal_name.strip() or company.legal_name.casefold() not in source.excerpt.casefold()):
        raise ValueError('current exact retrieved page and independently selected entity anchor required')
    if raw.canonical_company_id is not None:
        prior=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
            RunEvent.event_type=='candidate.page_reviewed',RunEvent.payload['raw_candidate_id'].astext==str(raw.id)))).scalar_one_or_none()
        await _current_reviewed_material(session,workspace_id=workspace_id,run=run,raw=raw,company=company,source=source,prior=prior)
    return run,raw,company,source,frozen,claim.id

async def research_candidate_review_context(session,*,workspace_id,run_id,raw_candidate_id,company_id,actor_id,capability):
    run,raw,company,source,_,_=await _current_review_basis(session,workspace_id=workspace_id,run_id=run_id,
        raw_candidate_id=raw_candidate_id,company_id=company_id,actor_id=actor_id,capability=capability)
    return {'run_id':str(run.id),'project_id':str(run.project_id),'raw_candidate_id':str(raw.id),
        'company':{'id':str(company.id),'legal_name':company.legal_name,'domain':company.domain,'hash':company_digest(company)},
        'page':{'id':str(source.id),'digest':source.digest,'excerpt':source.excerpt,'url':source.canonical_url,
            'retention_until':source.retention_until.isoformat()},
        'entity_status':'reviewed' if raw.canonical_company_id is not None else 'needs_review','fit_status':'needs_review'}

async def review_research_candidate(session,*,workspace_id,run_id,raw_candidate_id,page_source_id,
        company_id,actor_id,expected_page_digest,expected_company_hash,excerpt,reason,capability,model_environment=None):
    if not all(isinstance(x,uuid.UUID) for x in (workspace_id,run_id,raw_candidate_id,page_source_id,company_id,actor_id)):
        raise ValueError('canonical review references required')
    if (not isinstance(excerpt,str) or not 5<=len(excerpt.encode())<=4000 or not isinstance(reason,str)
        or not 10<=len(reason.strip())<=400 or not all(isinstance(x,str) and re.fullmatch('[0-9a-f]{64}',x)
            for x in (expected_page_digest,expected_company_hash))):raise ValueError('bounded explicit review and current hashes required')
    run,raw,company,source,frozen,claim_id=await _current_review_basis(session,workspace_id=workspace_id,run_id=run_id,
        raw_candidate_id=raw_candidate_id,company_id=company_id,actor_id=actor_id,capability=capability,
        page_source_id=page_source_id,expected_page_digest=expected_page_digest,expected_company_hash=expected_company_hash,excerpt=excerpt)
    input_hash=digest({'raw':str(raw.id),'source':str(source.id),'page_digest':source.digest,'company':str(company_id),
        'company_hash':expected_company_hash,'actor':str(actor_id),'excerpt_digest':hashlib.sha256(excerpt.encode()).hexdigest(),
        'reason_digest':hashlib.sha256(reason.strip().encode()).hexdigest(),'scope_hash':frozen})
    prior=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='candidate.page_reviewed',RunEvent.payload['raw_candidate_id'].astext==str(raw.id)))).scalar_one_or_none()
    if prior is not None:
        if prior.payload.get('input_hash')!=input_hash:raise ValueError('review replay must retain actor/entity/source/material')
        alias=(await session.execute(select(CompanyAlias).where(CompanyAlias.workspace_id==workspace_id,
            CompanyAlias.id==uuid.UUID(prior.payload['result']['alias_id']),CompanyAlias.raw_candidate_id==raw.id,
            CompanyAlias.superseded_at.is_(None)))).scalar_one_or_none()
        buyer=(await session.execute(select(ProjectBuyer).where(ProjectBuyer.workspace_id==workspace_id,
            ProjectBuyer.project_id==run.project_id,ProjectBuyer.id==uuid.UUID(prior.payload['result']['buyer_id'])))).scalar_one_or_none()
        if (alias is None or alias.company_id!=company_id or not alias.reviewed or alias.alias_type!='reviewed_page'
            or alias.decision_state!='reviewed_page' or alias.normalized_value!=expected_company_hash
            or alias.provenance!='actor:'+str(actor_id) or buyer is None or buyer.company_id!=company_id):
            raise ValueError('reviewed alias or buyer material no longer current')
        evidence=(await session.execute(select(Evidence).where(Evidence.workspace_id==workspace_id,
            Evidence.id==uuid.UUID(prior.payload['result']['evidence_id'])))).scalar_one_or_none()
        if (evidence is None or evidence.version!=1 or evidence.company_id!=company_id or evidence.source_document_id!=source.id
            or evidence.excerpt!=excerpt or evidence.stance!='qualifies' or not evidence.is_inference
            or evidence.content_hash!=input_hash or evidence.raw_candidate_id!=raw.id or evidence.run_id!=run.id
            or evidence.project_id!=run.project_id or evidence.provider_operation_id!=raw.provider_operation_id):raise ValueError('reviewed citation no longer current')
        return dict(prior.payload['result'])
    if raw.canonical_company_id is not None:raise ValueError('current initial unmapped review required')
    existing=(await session.execute(select(CompanyAlias.id).where(CompanyAlias.workspace_id==workspace_id,
        CompanyAlias.raw_candidate_id==raw.id,CompanyAlias.superseded_at.is_(None)))).scalar_one_or_none()
    if existing is not None:raise ValueError('initial review cannot replace an existing alias')
    buyer=(await session.execute(insert(ProjectBuyer).values(id=uuid.uuid5(raw.id,'review-buyer:'+str(company_id)),
        workspace_id=workspace_id,project_id=run.project_id,company_id=company_id,version=1)
        .on_conflict_do_nothing().returning(ProjectBuyer.id))).scalar_one_or_none()
    if buyer is None:buyer=(await session.execute(select(ProjectBuyer.id).where(ProjectBuyer.workspace_id==workspace_id,
        ProjectBuyer.project_id==run.project_id,ProjectBuyer.company_id==company_id))).scalar_one()
    alias_id=uuid.uuid5(raw.id,'review-alias:'+input_hash);evidence_id=uuid.uuid5(raw.id,'review-evidence:'+input_hash)
    session.add(CompanyAlias(id=alias_id,workspace_id=workspace_id,company_id=company_id,raw_candidate_id=raw.id,
        alias_type='reviewed_page',normalized_value=expected_company_hash,provenance='actor:'+str(actor_id),
        reviewed=True,decision_state='reviewed_page'))
    session.add(Evidence(id=evidence_id,workspace_id=workspace_id,project_id=run.project_id,company_id=company_id,
        source_document_id=source.id,run_id=run.id,raw_candidate_id=raw.id,provider_operation_id=raw.provider_operation_id,
        requirement_id=None,stance='qualifies',excerpt=excerpt,translation=None,is_inference=True,content_hash=input_hash,version=1))
    raw.canonical_company_id=company_id;raw.merge_state='reviewed_page';run.version+=1
    result={'buyer_id':str(buyer),'evidence_id':str(evidence_id),'alias_id':str(alias_id),'entity_status':'reviewed','fit_status':'needs_review'}
    await append_event(session,run,'candidate.page_reviewed',payload={'raw_candidate_id':str(raw.id),'company_id':str(company_id),
        'page_source_id':str(source.id),'page_claim_id':str(claim_id),'scope_hash':frozen,'input_hash':input_hash,
        'company_hash':expected_company_hash,'review_actor_id':str(actor_id),
        'review_excerpt_hash':hashlib.sha256(excerpt.encode()).hexdigest(),
        'review_reason_hash':hashlib.sha256(reason.strip().encode()).hexdigest(),'result':result})
    session.add(AuditEvent(id=uuid.uuid4(),workspace_id=workspace_id,actor_id=actor_id,action='candidate.page_reviewed',
        subject_type='raw_candidate',subject_id=str(raw.id),detail_digest='sha256:'+input_hash,reason='explicit_existing_entity_review'))
    await session.flush()
    if model_environment=='production':
        from .run_model import schedule_reviewed_run_model
        await schedule_reviewed_run_model(session,workspace_id=workspace_id,run_id=run_id,buyer_id=buyer,
            raw_candidate_id=raw_candidate_id,search_capability=capability)
    return result
