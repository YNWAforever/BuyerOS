"""Explicit DB-only native edits; no specialized skill runner or provider dispatch."""
from datetime import datetime, timezone
from sqlalchemy import select
from ..api.deps import permission_for_roles
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency
from ..db.models import Membership
from ..db.buyers import ProjectBuyer, BuyerList
from ..db.drafts import OutreachDraft
from ..db.icp import IcpVersion
from ..db.runs import SearchRun
from ..db.ingestion import OfferDocument
from ..sales.contracts import NativeRef, ACTION_MODELS, ActionProposal
from ..sales.context import require_scope, resolve_context


async def read_native(session,scope,ref,*,lock=False,check_revision=True):
    await require_scope(session,scope)
    if ref.surface=='export':
        from .export_service import authorize_export_content
        result=await authorize_export_content(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,export_id=ref.id,_metadata_only=True)
        row=result['job']
        if row.project_id!=scope.project_id or row.kind!='sales_output' or row.selection_manifest['revision']!=ref.revision:
            raise ValueError('exact native export required')
        return row
    models={'buyer':(ProjectBuyer,'version','getBuyer'),'list':(BuyerList,'version','getBuyerList'),
        'draft':(OutreachDraft,'state_version','getDraft'),'profile':(IcpVersion,'number','getProject'),
        'run':(SearchRun,'version','getProject'),'document':(OfferDocument,'version','getProject')}
    model,column,permission=models[ref.surface]
    member=(await session.execute(select(Membership).where(Membership.workspace_id==scope.workspace_id,
        Membership.user_id==scope.actor_id,Membership.active.is_(True)))).scalar_one_or_none()
    if member is None or not permission_for_roles(member.roles,permission):
        raise ApiError(404,'NOT_FOUND','native record not available')
    query=select(model).where(model.workspace_id==scope.workspace_id,model.project_id==scope.project_id,model.id==ref.id)
    if lock: query=query.with_for_update()
    row=(await session.execute(query.execution_options(populate_existing=True))).scalar_one_or_none()
    if row is None: raise ApiError(404,'NOT_FOUND','native record not available')
    if check_revision and getattr(row,column)!=ref.revision: raise ApiError(412,'STALE_REVISION','native record changed')
    if ref.surface=='profile' and (row.approved_at is None or row.superseded_at is not None):
        raise ValueError('approved current native profile required')
    if ref.surface=='document' and (row.status!='ready' or row.deleted_at is not None
        or row.retention_until is None or row.retention_until<=datetime.now(timezone.utc)):
        raise ValueError('native document unavailable')
    return row


async def apply_native_action(session,scope,proposal,expected_revision,key):
    from .xverum_dispatch import gates
    await gates(session,scope.workspace_id)
    from . import sales_outputs as outputs
    from ..db.sales_outputs import SalesOutput
    from .sales_tasks import task_row
    proposal=ActionProposal.model_validate(proposal.model_dump(mode='json'))
    routes={'buyers.review':('buyer','updateBuyer'),'lists.propose':('list','changeListMemberships'),
        'drafts.prepare':('draft','editDraft')}
    if proposal.capability not in routes: raise ValueError('native mutation owner is not registered')
    args=ACTION_MODELS[proposal.capability].model_validate(proposal.arguments)
    if args.output is None or args.mutation is None or len(args.refs)!=1:
        raise ValueError('explicit saved output, native target and mutation required')
    target=args.refs[0];surface,permission=routes[proposal.capability]
    if target.surface!=surface or target.revision!=expected_revision: raise ValueError('exact native precondition required')
    await require_scope(session,scope)
    # Match native draft approval/edit ordering: project before draft (and before thread).
    from ..db.icp import Project
    await session.execute(select(Project.id).where(Project.workspace_id==scope.workspace_id,
        Project.id==scope.project_id).with_for_update())
    member=(await session.execute(select(Membership).where(Membership.workspace_id==scope.workspace_id,
        Membership.user_id==scope.actor_id,Membership.active.is_(True)))).scalar_one()
    if not permission_for_roles(member.roles,permission): raise ApiError(403,'PERMISSION_DENIED','insufficient role')
    saved=await outputs.get_output(session,scope,args.output.id,args.output.revision)
    identity=(await session.execute(select(SalesOutput).where(SalesOutput.workspace_id==scope.workspace_id,
        SalesOutput.project_id==scope.project_id,SalesOutput.id==saved.id))).scalar_one()
    await task_row(session,scope,identity.task_id,edit=True)
    # Native write is explicitly human requested; task/domain specialization is a later owner.
    if not any(r.kind=='output' and r.id==saved.id and r.version==saved.revision for r in proposal.source_versions):
        raise ValueError('native action must select the exact saved output')
    operation=await begin_idempotency(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        operation_id='applySalesNativeAction',key=key,body=proposal.model_dump(mode='json'),
        target={'project_id':str(scope.project_id)},precondition=f'"{expected_revision}"')
    if operation.replay:
        result=NativeRef.model_validate(operation.response)
        # The atomic link always appends exactly one revision to the selected input.
        # Reauthorize that committed revision, not the now-obsolete native CAS input.
        committed=await outputs.get_output(session,scope,saved.id,saved.revision+1)
        if (committed.availability!='available' or result not in committed.native_refs
            or (result.surface,result.id)!=(target.surface,target.id)
            or operation.record.resource_id!=str(result.id)):
            raise ValueError('committed native output unavailable')
        replay_sources=[ref.model_copy(update={'version':committed.revision})
            if ref.kind=='output' and ref.id==saved.id and ref.version==saved.revision else
            ref.model_copy(update={'version':result.revision})
            if target.surface=='buyer' and ref.kind=='buyer' and ref.id==target.id and ref.version==target.revision
                and ref.model_copy(update={'version':result.revision}) in committed.citations else ref
            for ref in proposal.source_versions]
        await resolve_context(session,scope,replay_sources)
        await read_native(session,scope,result)
        return result
    if saved.availability!='available': raise ValueError('saved output dependencies unavailable')
    await resolve_context(session,scope,list(proposal.source_versions))
    # Capture the exact output basis before our own native mutation. The linked
    # revision may advance only this selected buyer and only with unchanged facts.
    from ..db.sales_outputs import SalesOutputVersion
    version=await session.scalar(select(SalesOutputVersion).where(
        SalesOutputVersion.workspace_id==scope.workspace_id,SalesOutputVersion.output_id==saved.id,
        SalesOutputVersion.revision==saved.revision))
    before=await resolve_context(session,scope,version.source_refs)
    row=await read_native(session,scope,target,lock=True)
    if surface=='buyer':
        from .buyer_management import update_buyer_note
        await update_buyer_note(session,row,expected_revision,args.mutation.note)
        revision=row.version
    elif surface=='list':
        from .buyer_management import change_memberships
        if any(r.surface!='buyer' for r in args.mutation.buyers): raise ValueError('list members must be buyers')
        for ref in args.mutation.buyers: await read_native(session,scope,ref,lock=True)
        result=await change_memberships(session,item=row,actor_user_id=scope.actor_id,
            selection={'kind':'explicit','buyers':[{'id':str(r.id),'version':r.revision} for r in args.mutation.buyers]},operation=args.mutation.operation)
        if result['blocked'] or result['conflicts']: raise ValueError('native member selection changed')
        revision=row.version
    else:
        from .draft_service import edit_draft
        await edit_draft(session,workspace_id=scope.workspace_id,draft=row,expected_version=expected_revision,
            changes=args.mutation.model_dump(mode='json'))
        revision=row.state_version
    result=NativeRef(surface=surface,id=row.id,revision=revision)
    await read_native(session,scope,result)
    # Link a new authored revision without changing native approval or output history.
    await outputs.link_native_action(session,scope,identity,saved,result,key,before=before,target=target)
    from .audit_service import append_audit
    append_audit(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        action='sales.native_applied',entity_type=surface,entity_id=row.id)
    complete_idempotency(operation,str(row.id),response=result.model_dump(mode='json'))
    await session.flush()
    return result
