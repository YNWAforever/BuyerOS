"""Fixed-as-of pipeline from current authorized native records, never fabricated metrics."""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from .contracts import OutputCandidate, NativeRef, ReportArguments
from .context import require_scope


async def build_pipeline_report(session, scope, as_of: datetime, filters: dict):
    from ..db.buyers import ProjectBuyer, BuyerList, ListMembership
    from ..db.outcomes import OutcomeEvent
    from ..services.sales_native import read_native
    await require_scope(session,scope)
    args=ReportArguments.model_validate({**filters,'as_of':as_of})
    if as_of>datetime.now(timezone.utc): raise ValueError('as-of cannot be in the future')
    rows=[];missing=[];native=[]
    members=None
    if args.list_id:
        listing=await session.scalar(select(BuyerList).where(BuyerList.workspace_id==scope.workspace_id,BuyerList.project_id==scope.project_id,BuyerList.id==args.list_id))
        if listing is None: raise ValueError('selected list unavailable')
        native.append(NativeRef(surface='list',id=listing.id,revision=listing.version))
        members=set((await session.scalars(select(ListMembership.buyer_id).where(ListMembership.workspace_id==scope.workspace_id,ListMembership.list_id==listing.id))).all())
    receipts=[]
    for id in args.buyer_ids:
        buyer=await session.scalar(select(ProjectBuyer).where(ProjectBuyer.workspace_id==scope.workspace_id,ProjectBuyer.project_id==scope.project_id,ProjectBuyer.id==id))
        if buyer is None: raise ValueError('selected buyer unavailable')
        ref=NativeRef(surface='buyer',id=id,revision=buyer.version)
        await read_native(session,scope,ref)
        native.append(ref)
        if buyer.created_at>as_of or (members is not None and id not in members): missing.append(id);continue
        events=(await session.scalars(select(OutcomeEvent).where(OutcomeEvent.workspace_id==scope.workspace_id,
            OutcomeEvent.project_id==scope.project_id,OutcomeEvent.buyer_id==id,OutcomeEvent.created_at<=as_of,
            (OutcomeEvent.occurred_at.is_(None)) | (OutcomeEvent.occurred_at<=as_of)).order_by(OutcomeEvent.created_at,OutcomeEvent.id))).all()
        superseded={e.supersedes_id for e in events if e.supersedes_id}
        active=[e for e in events if e.id not in superseded]
        last=active[-1] if active else None
        receipts.extend({'id':str(e.id),'version':e.version,'stage':e.stage,'buyer_id':str(id)} for e in events)
        rows.append({'buyer':ref,'stage':last.stage if last else None,'advisory_score':None,'value':None,'next_action':None})
    zh=args.language=='zh-HK'
    return OutputCandidate(kind='pipeline_report',content={'summary':'所選買家的原有紀錄' if zh else 'Native records for selected buyers',
        'unknowns':['金額、評分及下一步未知；缺少階段不代表零。' if zh else 'Value, score and next action are unknown; absent stages are not zero.'],
        'as_of':as_of,'scope':args.buyer_ids,'rows':rows,'unavailable_buyer_ids':missing,
        'methodology':'依截至時間已記錄及已發生的人工結果；名單篩選使用目前成員。' if zh else
            'Manual outcomes recorded and occurred by as-of; list filter uses current membership. No historical value or score is inferred.',
        'filters':args.model_dump(mode='json'),'record_basis':receipts},citations=[],dependencies=[],native_refs=native)
