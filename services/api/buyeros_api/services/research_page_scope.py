"""Current exact-source page permission; no retrieval, promotion or new grants.

A caller must use this port in both its prepare and commit transactions. The
frozen return value is server memory, never a client-supplied permission token.
Generic project research permission and search snippets do not license a page.
"""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
import uuid
from sqlalchemy import select,text
from ..db.buyers import SourceDocument
from ..db.runs import RawCandidate,RunEvent,SearchRun,CompanyAlias
from ..db.policy import PolicyDecision
from ..providers.live_search import PostgresSearchReceipts
from .search_intake import ingest_received_search
from .run_usage import UsageExceeded
from .safe_fetch import MAX_DECODED_BYTES
from .offer_source_policy import canonical_source_url

@dataclass(frozen=True)
class ResearchPageScope:
    workspace_id:uuid.UUID
    run_id:uuid.UUID
    raw_candidate_id:uuid.UUID
    source_document_id:uuid.UUID
    receipt_id:uuid.UUID
    source_url:str
    metadata_digest:str
    policy_id:uuid.UUID
    policy_version:int
    runtime_backend:str
    runtime_epoch:int
    retention_until:datetime
    max_page_bytes:int

    @property
    def retention_seconds(self):
        return max(0,int((self.retention_until-datetime.now(timezone.utc)).total_seconds()))

async def research_page_scope(session,*,workspace_id,run_id,raw_candidate_id,capability,page_claim_id=None,reviewed_company_id=None):
    if not all(isinstance(x,uuid.UUID) for x in (workspace_id,run_id,raw_candidate_id)):
        raise ValueError('canonical research page scope required')
    run=(await session.execute(select(SearchRun).where(SearchRun.workspace_id==workspace_id,SearchRun.id==run_id).with_for_update())).scalar_one_or_none()
    raw=(await session.execute(select(RawCandidate).where(RawCandidate.workspace_id==workspace_id,RawCandidate.run_id==run_id,RawCandidate.id==raw_candidate_id).with_for_update(read=True))).scalar_one_or_none()
    payload=(raw.raw_payload or {}) if raw is not None else {}
    if (run is None or raw is None or payload.get('content_kind')!='search_result_metadata' or
        payload.get('page_retrieved') is not False or payload.get('entity_status')!='needs_review'):
        raise ValueError('current unmapped received search metadata required')
    if reviewed_company_id is not None and not isinstance(reviewed_company_id,uuid.UUID):raise ValueError('canonical reviewed company reference required')
    if raw.canonical_company_id is not None:
        alias=(await session.execute(select(CompanyAlias.id).where(CompanyAlias.workspace_id==workspace_id,
            CompanyAlias.raw_candidate_id==raw.id,CompanyAlias.company_id==reviewed_company_id,
            CompanyAlias.alias_type=='reviewed_page',CompanyAlias.decision_state=='reviewed_page',
            CompanyAlias.reviewed.is_(True),CompanyAlias.superseded_at.is_(None)))).scalar_one_or_none()
        review=(await session.execute(select(RunEvent.id).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
            RunEvent.event_type=='candidate.page_reviewed',RunEvent.payload['raw_candidate_id'].astext==str(raw.id),
            RunEvent.payload['company_id'].astext==str(reviewed_company_id)))).scalar_one_or_none()
        if reviewed_company_id!=raw.canonical_company_id or raw.merge_state!='reviewed_page' or alias is None or review is None:
            raise ValueError('current unmapped or exact previously reviewed metadata required')

    try:receipt_id=uuid.UUID(payload['receipt_id']);source_id=uuid.UUID(payload['source_document_id'])
    except (ValueError,KeyError,TypeError,AttributeError) as exc:raise ValueError('canonical source receipt binding required') from exc
    prior=(await session.execute(select(RunEvent.id).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
        RunEvent.event_type=='node.committed',RunEvent.payload['receipt_id'].astext==str(receipt_id)))).scalar_one_or_none()
    if prior is None:raise ValueError('committed metadata intake required before page preparation')
    # Rechecks actor, ICP/offer, purpose, full contract, hold allocation and the
    # current original receipt/outbox/runtime fence under the API-only lock.
    await ingest_received_search(session,workspace_id=workspace_id,run_id=run_id,receipt_id=receipt_id,capability=capability)
    source=(await session.execute(select(SourceDocument).where(SourceDocument.workspace_id==workspace_id,SourceDocument.id==source_id).with_for_update(read=True))).scalar_one_or_none()
    receipt=(await session.execute(text('SELECT * FROM search_receipts WHERE workspace_id=:ws AND id=:id'),{'ws':workspace_id,'id':receipt_id})).mappings().one()
    saved=PostgresSearchReceipts(session.bind,workspace_id,capability)._decode(receipt)
    item=next((x for x in saved['sources'] if x['content_hash']==raw.candidate_fingerprint),None)
    now=datetime.now(timezone.utc)
    if (source is None or item is None or source.project_id!=run.project_id or source.run_id!=run.id or
        source.storage_mode!='search_result_metadata' or source.object_key is not None or source.permission_purpose!='account_research' or
        source.id!=uuid.uuid5(receipt_id,'source:'+item['content_hash']) or raw.id!=uuid.uuid5(run_id,str(receipt['operation_id'])+':'+item['content_hash']) or
        source.digest!=item['content_hash'] or raw.raw_digest!=item['content_hash'] or raw.provider_operation_id!=receipt['operation_id'] or
        source.canonical_url!=item['source_url'] or raw.source_url!=source.canonical_url or raw.normalized_url!=source.canonical_url or
        source.excerpt!=item['excerpt'] or source.retrieved_at is None or source.retrieved_at>now or
        source.retrieved_at!=datetime.fromisoformat(item['retrieved_at']) or source.retention_until is None or source.retention_until<=now):
        raise ValueError('exact current metadata provenance required')
    url=canonical_source_url(source.canonical_url)
    from .policy_service import evaluate_current_policy
    from .research_policy_context import research_use
    gate=await evaluate_current_policy(session,{'workspace_id':workspace_id,'project_id':run.project_id},
        'account_research',now,use_context=research_use(run.project_id,'research.fetch',urls=(url,)))
    if not gate['allowed']:
        raise ValueError('current approved research fetch permission required')
    permission=(await session.execute(select(PolicyDecision).where(PolicyDecision.workspace_id==workspace_id,
        PolicyDecision.controller_scope_id==workspace_id,PolicyDecision.subject_type=='project',PolicyDecision.subject_id==run.project_id,
        PolicyDecision.purpose=='account_research').order_by(PolicyDecision.created_at.desc(),PolicyDecision.id.desc()).limit(1))).scalar_one_or_none()
    if (permission is None or permission.status!='permitted' or permission.basis_reference!=url or
        permission.expires_at<=now or not permission.provenance.strip() or permission.decision_author_id is None or
        not 1<=permission.retention_days<=30):
        raise ValueError('current exact-source account research permission required')
    deadline=min(source.retention_until,receipt['retention_until'],permission.expires_at,permission.created_at+timedelta(days=permission.retention_days))
    if (deadline-now).total_seconds()<1:raise ValueError('current bounded page retention required')
    claimed=False
    if page_claim_id is not None:
        if not isinstance(page_claim_id,uuid.UUID):raise ValueError('canonical existing page claim required')
        claim=(await session.execute(select(RunEvent).where(RunEvent.workspace_id==workspace_id,RunEvent.run_id==run_id,
            RunEvent.id==page_claim_id,RunEvent.event_type=='page.fetch.prepared'))).scalar_one_or_none()
        if claim is None or claim.payload.get('raw_candidate_id')!=str(raw.id) or claim.payload.get('receipt_id')!=str(receipt_id):
            raise ValueError('current original page claim required')
        claimed=True
    pages=(run.usage_counters or {}).get('pages',0);maximum=run.limits['max_pages'];byte_limit=run.limits['max_page_bytes']
    if type(pages) is not int or type(maximum) is not int or pages<0 or pages>maximum or (pages==maximum and not claimed):raise UsageExceeded('page ceiling exceeded')
    if type(byte_limit) is not int or byte_limit<1:raise ValueError('positive page byte ceiling required')
    if run.first_dispatch_at is not None and (now-run.first_dispatch_at).total_seconds()>run.limits['max_duration_seconds']:
        raise UsageExceeded('run duration ceiling exceeded')
    return ResearchPageScope(workspace_id,run_id,raw.id,source.id,receipt_id,url,source.digest,permission.id,permission.version,
        receipt['runtime_backend'],receipt['runtime_epoch'],deadline,min(byte_limit,MAX_DECODED_BYTES))
