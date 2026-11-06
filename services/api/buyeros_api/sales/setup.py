"""Current native setup facts, with a revalidatable content-free authority basis."""
from uuid import UUID
from sqlalchemy import select
from .context import require_scope,digest
from .contracts import SourceRef,NativeRef
from ..api.errors import ApiError


async def setup_state(session,scope,args):
    from ..db.icp import Project,IcpVersion
    from ..db.drafts import SenderIdentityVersion
    from ..db.buyers import ProjectBuyer
    from .native_sources import resolve_native_source
    from ..services.sales_native import read_native
    from ..services.draft_service import preparation_recipient_context
    await require_scope(session,scope)
    project=await session.get(Project,scope.project_id,populate_existing=True)
    missing=[]
    basis={'project_id':str(project.id),'offer_revision':project.offer_revision,
        'profile_id':str(project.active_icp_version_id) if project.active_icp_version_id else None,
        'sender_id':str(project.active_sender_identity_version_id) if project.active_sender_identity_version_id else None,
        'buyer_id':str(args['buyer_id']) if args.get('buyer_id') else None,
        'recipient_id':str(args['recipient_id']) if args.get('recipient_id') else None}
    profile=await session.scalar(select(IcpVersion).where(IcpVersion.workspace_id==scope.workspace_id,
        IcpVersion.project_id==scope.project_id,IcpVersion.id==project.active_icp_version_id)) if project.active_icp_version_id else None
    profile_ok=False
    if profile:
        basis['profile_hash']=profile.content_hash
        basis['profile_version']=profile.number
        try:
            await resolve_native_source(session,scope,SourceRef(kind='profile',id=profile.id,version=profile.number,
                locator=f'profile:{profile.id}',retention_class='durable'))
            profile_ok=True
        except (ValueError,ApiError): pass
    if not profile_ok: missing.append('approved_profile')
    sender=await session.scalar(select(SenderIdentityVersion).where(SenderIdentityVersion.workspace_id==scope.workspace_id,
        SenderIdentityVersion.project_id==scope.project_id,SenderIdentityVersion.id==project.active_sender_identity_version_id)) if project.active_sender_identity_version_id else None
    if sender:
        basis['sender_version']=sender.version_key
        basis['sender_review']=digest({'reviewed_at':str(sender.reviewed_at),'reviewed_by':str(sender.reviewed_by),
            'retired':sender.retired,'name':sender.display_name,'email':sender.business_email})
    if not sender or sender.retired or not sender.reviewed_at or not sender.reviewed_by:
        missing.append('reviewed_sender')
    if not basis['recipient_id']:
        missing.append('unselected_recipient')
    else:
        buyer=await session.scalar(select(ProjectBuyer).where(ProjectBuyer.workspace_id==scope.workspace_id,
            ProjectBuyer.project_id==scope.project_id,ProjectBuyer.id==UUID(basis['buyer_id']))) if basis['buyer_id'] else None
        try:
            if buyer is None: raise ValueError('recipient requires a selected current buyer')
            await read_native(session,scope,NativeRef(surface='buyer',id=buyer.id,revision=buyer.version))
            authority=await preparation_recipient_context(session,workspace_id=scope.workspace_id,
                project_id=scope.project_id,company_id=buyer.company_id,contact_id=UUID(basis['recipient_id']))
            basis['buyer_version']=buyer.version
            basis['recipient_authority']=digest(authority)
        except (ValueError,ApiError): missing.append('ineligible_recipient')
    basis['missing_fields']=missing
    return missing,basis
