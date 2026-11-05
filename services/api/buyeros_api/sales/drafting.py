"""Separate authored preparation from explicit eligible native formal creation."""
import uuid
from sqlalchemy import select
from .contracts import NativeRef,SourceRef
from ..api.errors import ApiError


async def prepare_draft(scope,task_id,context):
    from .research import run_research_skill
    return await run_research_skill(scope,task_id,context)


async def grounded_preparation(session,scope,args,context):
    """Use the same reviewed fact/evidence rendering as the native free route."""
    from ..db.icp import IcpVersion
    from ..services.icp_service import effective_offer_facts
    from ..services.sales_outputs import policy_source_refs
    from .native_sources import resolve_native_source
    from ..execution.handlers.draft_generate import render_grounded_template
    refs=await policy_source_refs(session,scope,context.refs)
    buyer=next((r for r in refs if r.kind=='buyer' and str(r.id)==str(args['buyer_id'])),None)
    if buyer is None: raise ValueError('selected native buyer evidence required')
    profile=await session.get(IcpVersion,uuid.UUID(str(args['profile_id'])))
    facts_ids={str(r.id) for r in refs if r.kind=='project_fact'}
    facts=[f for f in effective_offer_facts(profile) if str(f['id']) in facts_ids]
    _,proof=await resolve_native_source(session,scope,buyer)
    evidence=[{'id':p['id'],'version':p['version'],'excerpt':p['excerpt'],'stance':p['stance']}
        for p in proof if p['stance']=='supports' and not p['is_inference']]
    rendered=render_grounded_template(facts=facts,evidence=evidence,objective=args['objective'],tone='professional',
        language=args.get('language','en'),kind='follow_up' if 'scenario' in args else 'initial')
    if 'scenario' in args:
        scenario=args['scenario']
        if scenario!='nurture':
            raise ValueError(scenario+': verified interaction and agreed actions required; use reviewed model sections with explicit unknowns')
        interaction=SourceRef.model_validate(args['interaction_ref'])
        source=next((s for s in context._sources if SourceRef.model_validate(s['ref'])==interaction),None)
        if source is None or not source['excerpts']:
            raise ValueError('nurture: selected authorized interaction context required')
        # Quote selected context as context, never assert a meeting/agreement.
        excerpt=source['excerpts'][0]
        zh=args.get('language')=='zh-HK'
        rendered={**rendered,'subject':'保持聯繫' if zh else 'Keeping in touch',
            'body':('你好，\n\n所選參考資料（並非會議或承諾的證明）：\n' if zh else
                'Hello,\n\nSelected reference context (not proof of a meeting or agreement):\n')+excerpt+
                ('\n\n如仍有興趣，歡迎交流。任何已同意的行動及日期均待確認。' if zh else
                 '\n\nWould you like to continue the conversation? Any agreed actions and dates remain to be confirmed.')}
    return rendered


async def save_formal_draft(session,scope,output_id,recipient_id,expected_revision,key):
    from ..services.xverum_dispatch import gates
    from ..services.sales_outputs import get_output,link_native_action,policy_source_refs
    from ..services.sales_tasks import task_row
    from ..services.draft_service import admit_grounded_template
    from ..execution.handlers.draft_generate import _materialize
    from ..db.sales_outputs import SalesOutput
    from ..db.icp import Project
    from ..api.idempotency import begin_idempotency,complete_idempotency
    from ..api.schemas import DraftGenerateRequest
    await gates(session,scope.workspace_id)
    # Match native approval locking, before any thread lock.
    await session.execute(select(Project.id).where(Project.workspace_id==scope.workspace_id,
        Project.id==scope.project_id).with_for_update())
    if recipient_id is None: raise ValueError('explicit eligible recipient required')
    identity=await session.scalar(select(SalesOutput).where(SalesOutput.workspace_id==scope.workspace_id,
        SalesOutput.project_id==scope.project_id,SalesOutput.id==output_id))
    if identity is None: raise ApiError(404,'NOT_FOUND','output unavailable')
    row=await task_row(session,scope,identity.task_id,edit=True)
    saved=await get_output(session,scope,output_id,expected_revision)
    if saved.availability!='available' or saved.kind not in {'outreach_preparation','followup_preparation'}:
        raise ValueError('current authored preparation required')
    operation=await begin_idempotency(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        operation_id='createSalesFormalDraft',key=key,body={'output_id':str(output_id),'recipient_id':str(recipient_id)},
        target={'project_id':str(scope.project_id)},precondition=str(expected_revision))
    if operation.replay:
        from ..services.sales_native import read_native
        result=NativeRef.model_validate(operation.response)
        await read_native(session,scope,result)
        return result
    if identity.revision!=expected_revision: raise ValueError('saved preparation changed')
    from .context import resolve_context
    from .research import validate_intake_authority
    context=await resolve_context(session,scope,[SourceRef.model_validate(r) for r in row.source_refs])
    args=await validate_intake_authority(session,scope,row,context)
    refs=await policy_source_refs(session,scope,context.refs)
    buyer=next((r for r in refs if r.kind=='buyer' and str(r.id)==str(args['buyer_id'])),None)
    facts=[str(r.id) for r in refs if r.kind=='project_fact']
    if buyer is None or not facts: raise ValueError('select buyer evidence and approved offer facts')
    from .native_sources import resolve_native_source
    _,proof=await resolve_native_source(session,scope,buyer)
    evidence=[{'id':p['id'],'version':p['version']} for p in proof if p['stance']=='supports' and not p['is_inference']]
    if not evidence: raise ValueError('supporting native buyer evidence required')
    parent_id=None
    if saved.kind=='followup_preparation':
        interaction=saved.content.interaction_ref
        if interaction.kind!='output': raise ValueError('select a saved interaction linked to its current native parent draft')
        parent_output=await get_output(session,scope,interaction.id,interaction.version)
        parents=[r for r in parent_output.native_refs if r.surface=='draft']
        if parent_output.availability!='available' or len(parents)!=1:
            raise ValueError('explicit current native parent draft required for formal follow-up')
        parent_id=str(parents[0].id)
    request=DraftGenerateRequest.model_validate({'buyer_id':str(buyer.id),'buyer_version':buyer.version,
        'recipient_contact_id':str(recipient_id),'objective':args['objective'],'tone':'professional',
        'language':args.get('language','en'),'approved_offer_fact_ids':facts,'evidence_refs':evidence,
        'kind':'follow_up' if parent_id else 'initial','parent_draft_id':parent_id,
        'max_cost':{'amount':'0.000000','currency':'USD'}})
    job=await admit_grounded_template(session,workspace_id=scope.workspace_id,project_id=scope.project_id,
        actor_id=scope.actor_id,request=request)
    # Existing DB-only deterministic owner; zero models/providers. Its queued
    # native outbox subsequently sees the completed job and performs no duplicate.
    status=await _materialize(session,scope.workspace_id,job.id)
    if status!='completed': raise ValueError('native preparation rejected: '+status)
    result=NativeRef(surface='draft',id=uuid.UUID(job.command['result_draft_id']),revision=1)
    from ..db.drafts import OutreachDraft,DraftRevision
    from ..services.draft_service import edit_draft
    draft=await session.get(OutreachDraft,result.id)
    revision=await session.scalar(select(DraftRevision).where(DraftRevision.draft_id==draft.id,
        DraftRevision.workspace_id==scope.workspace_id,DraftRevision.revision_number==draft.current_revision))
    message=saved.content.messages[0]
    if (revision.content['subject'],revision.content['body'])!=(message.subject,message.body):
        # Authored/model text is preserved, but cannot inherit template grounding
        # or approval. Native manual grounding review must approve that revision.
        await edit_draft(session,workspace_id=scope.workspace_id,draft=draft,expected_version=draft.state_version,
            changes={'subject':message.subject,'body':message.body})
        result=NativeRef(surface='draft',id=draft.id,revision=draft.state_version)
    await link_native_action(session,scope,identity,saved,result,key,before=context,target=result)
    complete_idempotency(operation,str(result.id),response=result.model_dump(mode='json'))
    await session.flush()
    return result
