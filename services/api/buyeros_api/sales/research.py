"""DB-only core skill producers over explicit, current canonical evidence.

Selected native discovery is reused, never launched implicitly. New discovery is
a separately admitted native operation; this producer has no transport capability.
"""
import json
from uuid import UUID
from sqlalchemy import select
from .contracts import OutputCandidate, SourceRef, NativeRef, OutputDependency
from .registry import load_skill, validate_arguments
from .context import resolve_context

CORE_SKILLS=frozenset({'sales-icp','sales-research','sales-quick','sales-prospect',
    'sales-qualify','review-buyers','sales-outreach','sales-followup','first-project'})


def work_declaration(skill_id):
    if skill_id not in CORE_SKILLS: raise ValueError('not a core skill')
    return {'steps':5 if skill_id=='sales-prospect' else 1,'model_calls':0,
        'provider_calls':0,'max_concurrent_steps':1,'model_liability_usd':'0',
        'native_provider_liability':'Separate human-reviewed startRun max_cost and RunLimits; no new liability in preparation',
        'discovery':'reuse one selected native run; no child redispatch'}


def compose(skill_id,arguments,context):
    """Reproducible evidence excerpts; intake objectives never become factual claims."""
    skill=load_skill(skill_id,'1')
    if skill_id not in CORE_SKILLS: raise ValueError('not a core skill')
    zh=arguments.get('language')=='zh-HK'
    refs=list(context.refs)
    limit=3 if skill_id=='sales-quick' else min(arguments.get('max_sources',12),12)
    findings=[]
    for source in context._sources[:limit]:
        ref=SourceRef.model_validate(source['ref'])
        for excerpt in source['excerpts'][:1]:
            inferred=ref.kind in {'profile','output'} or any(p.get('is_inference') for p in source.get('native_proof',[]))
            findings.append({'statement':excerpt,'evidence':[ref],'confidence':'inference' if inferred else 'high'})
    unknowns=['預算、決策權及時間表未經確認。' if zh else 'Budget, authority and timing are not verified.']
    common={'summary':'已選取資料的審閱草稿' if zh else 'Review of selected evidence','unknowns':unknowns}
    if skill_id in {'sales-research','sales-quick','sales-prospect'}:
        content={**common,'findings':findings,'opportunities':[],
            'concerns':['新增研究須另行核准。' if zh else 'New discovery requires separate native admission.']}
        if skill_id=='sales-prospect':
            # Two DB-only analysis branches consume the same immutable context.
            # Neither owns discovery, model reservations, or provider tools.
            qualification=compose('sales-qualify',arguments,context)
            content['unknowns']=list(qualification.content.unknowns)
            content['opportunities']=list(qualification.content.next_questions)
            content['concerns'].append('審閱買家名單後才可套用變更。' if zh else 'Review the proposed buyer shortlist before applying changes.')
    elif skill_id=='sales-qualify':
        content={**common,'rubric':'BANT_MEDDIC','dimensions':[
            {'dimension':d,'score':None,'rationale':unknowns[0],'evidence':[]}
            for d in ('budget','authority','need','timeline','metrics','economic_buyer','decision_criteria','decision_process','pain','champion')],
            'next_questions':['請確認預算、決策者及採購時間。' if zh else 'Confirm budget, decision maker and purchasing timeline.']}
    elif skill_id=='sales-icp':
        if not findings: raise ValueError('selected approved facts required for evidence-backed criteria')
        content={**common,'criteria':findings,'exclusions':[],
            'personas':['待確認採購角色' if zh else 'Purchasing role to confirm']}
    elif skill_id=='review-buyers':
        selected={str(r.id) for r in refs if r.kind=='buyer'}
        ids=arguments['buyer_ids']
        if any(str(i) not in selected for i in ids): raise ValueError('select exact current buyers')
        content={**common,'assessments':findings,'proposed_buyer_ids':ids}
    elif skill_id=='first-project':
        content={**common,'offer':arguments['offer_description'],
            'missing_fields':[],  # populated from current native setup before save
            'next_steps':['在原有專案頁審批客戶輪廓；透過文件上載流程檢查擷取狀態；再審閱買家名單。' if zh else
                'Review the profile on the native project page; upload documents and check extraction status; then review the buyer shortlist.']}
    else:
        if not findings: raise ValueError('selected evidence required for preparation')
        body=('你好，\n\n參考已選資料：\n' if zh else 'Hello,\n\nSelected source excerpts:\n')+'\n'.join(f['statement'] for f in findings)
        body+=('\n\n如果合適，歡迎安排交流。' if zh else '\n\nWould a conversation be useful?')
        content={**common,'messages':[{'subject':'業務交流' if zh else 'Business conversation',
            'body':body,'rationale':'僅引用已選資料。' if zh else 'Only selected evidence is quoted.',
            'evidence':refs,'suggested_day':0}]}
        if skill_id=='sales-followup':
            interaction=SourceRef.model_validate(arguments['interaction_ref'])
            if interaction not in refs: raise ValueError('select the exact interaction evidence')
            content.update(scenario=arguments['scenario'],interaction_ref=interaction)
        else: content['framework']=arguments.get('framework','direct')
    return OutputCandidate(kind=skill.output_kind,content=content,citations=refs,
        dependencies=[OutputDependency(id=r.id,revision=r.version) for r in refs if r.kind=='output'],native_refs=[])


async def validate_intake_authority(session,scope,row,context):
    """Native IDs are selections, never evidence or permission by themselves."""
    from ..services.sales_native import read_native
    from ..db.icp import Project
    args=validate_arguments(load_skill(row.skill_id,row.skill_version),row.arguments)
    for field,kind in (('buyer_id','buyer'),('profile_id','profile')):
        if row.skill_id=='first-project': continue  # setup_state owns explicit native selection
        if args.get(field):
            ref=next((r for r in context.refs if r.kind==kind and str(r.id)==str(args[field])),None)
            if ref is None: raise ValueError('select current native '+kind+' evidence')
            await read_native(session,scope,NativeRef(surface=kind,id=ref.id,revision=ref.version))
            if kind=='profile' and args.get('profile_version',ref.version)!=ref.version:
                raise ValueError('profile revision changed')
    if row.skill_id in {'sales-research','sales-quick','sales-prospect'}:
        runs=[r for r in context.refs if r.kind=='run']
        if len(runs)!=1: raise ValueError('select one existing native research run; new research requires native admission/configuration')
    if row.skill_id=='sales-prospect':
        bounds=args['bounds'];work=work_declaration(row.skill_id)
        if work['steps']>bounds['max_steps']: raise ValueError('core work exceeds declared step bound')
    return args


async def candidate_for(session,scope,row):
    context=await resolve_context(session,scope,[SourceRef.model_validate(r) for r in row.source_refs])
    if context.digest!=row.context_digest: raise ValueError('selected source closure changed')
    args=await validate_intake_authority(session,scope,row,context)
    candidate=compose(row.skill_id,args,context)
    if row.skill_id=='first-project':
        from .setup import setup_state
        missing,basis=await setup_state(session,scope,args)
        data=candidate.model_dump(mode='json')
        data['content'].update(missing_fields=missing,setup_basis=basis)
        candidate=OutputCandidate.model_validate(data)
    if row.skill_id=='sales-prospect':
        missing=await prospect_missing(session,scope,row)
        data=candidate.model_dump(mode='json')
        data['content']['unknowns'] += [('尚未選取所需輸出：' if args.get('language')=='zh-HK' else 'Required saved output not selected: ')+kind for kind in missing]
        candidate=OutputCandidate.model_validate(data)
    if row.skill_id in {'sales-outreach','sales-followup'}:
        from .drafting import grounded_preparation
        generated=await grounded_preparation(session,scope,args,context)
        data=candidate.model_dump(mode='json')
        data['content']['messages'][0].update(subject=generated['subject'],body=generated['body'])
        if row.skill_id=='sales-followup':
            data['content']['unknowns'].append('已同意的行動及日期未經確認。' if args.get('language')=='zh-HK' else 'Prior meetings, agreed actions and dates are not verified.')
        candidate=OutputCandidate.model_validate(data)
    native=[NativeRef(surface=r.kind,id=r.id,revision=r.version) for r in context.refs if r.kind in {'buyer','profile','run'}]
    # ICP proposal is not a native profile creation or approval.
    return candidate.model_copy(update={'native_refs':tuple(native)})


async def prospect_missing(session,scope,row):
    """Read independently authorized child results; never dispatch contacts/competitors."""
    from ..services.sales_outputs import get_output,policy_source_refs
    parent=[SourceRef.model_validate(r) for r in row.source_refs if r['kind']!='output']
    kinds=set()
    for ref in row.source_refs:
        if ref['kind']=='output':
            value=await get_output(session,scope,UUID(ref['id']),ref['version'])
            if value.availability=='available':
                closure=await policy_source_refs(session,scope,[SourceRef.model_validate(ref)])
                if compatible_child(value,parent,closure): kinds.add(value.kind)
    return tuple(sorted({'enrichment_proposal','competitive_document','outreach_preparation'}-kinds))


def compatible_child(child,parent,closure):
    """Bind roles to current authoritative subject and exact immutable source basis.

    Enrichment owns an independent provider discovery, so its native subject is
    mandatory but a native research run is optional. Any supplied run must match.
    Other roles must consume the parent's exact selected buyer AND research run.
    """
    groups={kind:{(r.id,r.version) for r in parent if r.kind==kind} for kind in ('buyer','run','profile')}
    if any(len(values)>1 for values in groups.values()): return False
    required={kind:next(iter(values)) for kind,values in groups.items() if values}
    if 'buyer' not in required or 'run' not in required: return False
    actual={kind:{(r.id,r.version) for r in closure if r.kind==kind} for kind in required}
    if child.kind=='enrichment_proposal':
        if (child.content.buyer_id,child.content.buyer_version)!=required['buyer']: return False
    elif any(actual[k]!={required[k]} for k in ('buyer','run')): return False
    return all(not values or values=={required[k]} for k,values in actual.items())


async def run_research_skill(scope,task_id,context):
    from ..api.deps import tenant_scoped
    from ..services.sales_tasks import task_row
    async with tenant_scoped(scope.workspace_id) as session:
        row=await task_row(session,scope,task_id,edit=True)
        if context.digest!=row.context_digest: raise ValueError('task context changed')
        return await candidate_for(session,scope,row)


async def guidance(session,scope,row):
    from .contracts import CoreGuidance,CoreDestination,CoreWork
    from ..db.icp import Project
    from ..api.routes.runs import selected_run_capability
    if row.skill_id not in CORE_SKILLS: raise ValueError('not a core skill')
    project=await session.get(Project,scope.project_id)
    missing=[]
    operation='getProject'
    if row.skill_id in {'sales-research','sales-quick','sales-prospect'}:
        operation='startRun'
        if not any(r['kind']=='run' for r in row.source_refs): missing.append('selected_native_run')
        if project.active_icp_version_id is None: missing.append('approved_profile')
        if selected_run_capability()[0] is None: missing.append('verified_native_search_configuration')
    elif row.skill_id in {'sales-outreach','sales-followup'}: operation='generateDraft'
    elif row.skill_id=='review-buyers': operation='changeListMemberships'
    elif row.skill_id=='first-project':
        from .setup import setup_state
        missing,_=await setup_state(session,scope,row.arguments)
    return CoreGuidance(state='needs_input' if missing else 'ready_for_review',missing_inputs=missing,
        action=CoreDestination(operation_id=operation,workspace_id=scope.workspace_id,project_id=scope.project_id,
            task_id=row.id,idempotency_key=f'sales-research:{row.id}' if operation=='startRun' else f'sales-core:{row.id}'),
        work=CoreWork(**work_declaration(row.skill_id)))
