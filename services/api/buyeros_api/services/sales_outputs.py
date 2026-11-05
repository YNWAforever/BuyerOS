"""Canonical authored-output owner. Reads always re-evaluate audience and sources."""
import uuid
import html
from sqlalchemy import select, and_, or_, exists, func
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency
from ..db.sales_outputs import (SalesOutput, SalesOutputVersion, SalesOutputSection,
    SalesOutputDependency, SalesOutputNativeLink)
from ..db.sales_execution import SalesExecution, SalesStep
from ..db.conversation_threads import ConversationThread, ConversationThreadShare
from ..sales.contracts import (OutputCandidate, OutputVersion, OutputDependency, SourceRef,
    SalesSectionCandidate, OUTPUT_MODELS, OutputCollectionPage, OutputListQuery)
from ..sales.context import resolve_context, require_scope, digest
from ..sales.registry import load_skill, validate_output
from ..sales.sections import section_groups, section_model, SERVER_DEFAULTS, require_supported_identity_kind
from ..sales.model import validate_basis, validate_proposal, wire_basis
from . import sales_tasks as tasks
from .conversation_access import load, not_found


async def output_scope(session,scope):
    try: await require_scope(session,scope)
    except ValueError as exc: raise not_found() from exc


def render_markdown(text):
    """Small inert Markdown subset: headings, list items and paragraphs only.

    Escape first; authored HTML, images and link syntax remain plain text. There
    is deliberately no URL parser or raw-HTML escape hatch on this read path.
    """
    blocks=[]
    for line in text.splitlines():
        if not line.strip(): continue
        if line.startswith(('# ','## ','### ')):
            blocks.append('<h2>'+html.escape(line.split(' ',1)[1])+'</h2>')
        elif line.startswith(('- ','* ')):
            blocks.append('<ul><li>'+html.escape(line[2:])+'</li></ul>')
        else: blocks.append('<p>'+html.escape(line)+'</p>')
    return ''.join(blocks)


def render_output(output):
    if output.availability!='available': return '<p>Output unavailable</p>'
    def render(value):
        if isinstance(value,str): return render_markdown(value)
        if isinstance(value,list): return ''.join(render(item) for item in value)
        if isinstance(value,dict):
            return ''.join('<section><h2>'+html.escape(key.replace('_',' '))+'</h2>'+render(item)+'</section>' for key,item in value.items())
        return '<p>'+html.escape(str(value))+'</p>'
    return '<!doctype html><html><head><meta charset="utf-8"><title>Saved output</title></head><body>'+render(output.content.model_dump(mode='json'))+'</body></html>'


def assemble_sections(kind, candidates):
    groups=section_groups(kind)
    candidates=[SalesSectionCandidate.model_validate(c.model_dump(mode='json') if hasattr(c,'model_dump') else c) for c in candidates]
    if len(candidates)!=len(groups) or {c.section for c in candidates}!=set(groups):
        raise ValueError('exact planned section set required')
    content={}; citations=[]
    for child in candidates:
        if child.kind!=kind or set(child.content)!=set(groups[child.section]):
            raise ValueError('foreign kind or section-owned fields')
        typed=section_model(kind,child.section).model_validate(child.content)
        content.update(typed.model_dump(mode='json'))
        for ref in child.citations:
            if ref not in citations: citations.append(ref)
    for name,field in OUTPUT_MODELS[kind].model_fields.items():
        if name in SERVER_DEFAULTS:
            content[name]=field.default
    # Full model validation includes cross-section coverage, not just child validation.
    return OutputCandidate(kind=kind,content=OUTPUT_MODELS[kind].model_validate(content),
        citations=citations,dependencies=[OutputDependency(id=r.id,revision=r.version) for r in citations if r.kind=='output'],native_refs=[])


async def section_authority(session,scope,parent,step,basis):
    from ..execution.sales_tasks import intake_hash
    parsed=validate_basis(basis); req=parsed.request
    row=await tasks.task_row(session,scope,parent.task_id,edit=True)
    if (parent.cancelled or parent.workspace_id!=scope.workspace_id or parent.project_id!=scope.project_id
        or parent.actor_id!=scope.actor_id or parsed.scope!=scope or step.execution_id!=parent.id
        or step.workspace_id!=scope.workspace_id or step.claim_id is None or step.state!='received'
        or req.task_id!=row.id or req.step_id!=step.id or req.section!=step.section
        or (req.skill_id,req.skill_version,req.arguments)!=(row.skill_id,row.skill_version,row.arguments)
        or parent.intake_hash!=intake_hash(row) or parent.intake_revision!=row.intake_history[-1]['revision']
        or parsed.basis_hash!=step.basis_hash or digest(wire_basis(basis))!=step.projection_hash):
        raise ValueError('section task/intake/claim/basis authority changed')
    current=await resolve_context(session,scope,list(req.context.refs))
    from ..sales.planning import plan_task
    plan=plan_task(load_skill(row.skill_id,row.skill_version),row.arguments,current)
    if current.digest!=row.context_digest or current.digest!=req.context.digest or plan.model_dump(mode='json')!=parent.plan:
        raise ValueError('section context or frozen plan changed')
    return row


class SectionOwner:
    async def save_section(self,session,scope,parent,step,basis,candidate):
        await section_authority(session,scope,parent,step,basis)
        payload=validate_proposal(candidate.model_dump(mode='json'),basis)
        result_digest=digest(payload)
        if result_digest!=step.result_digest: raise ValueError('section receipt digest mismatch')
        existing=(await session.execute(select(SalesOutputSection).where(
            SalesOutputSection.workspace_id==scope.workspace_id,SalesOutputSection.step_id==step.id))).scalar_one_or_none()
        values=dict(workspace_id=scope.workspace_id,execution_id=parent.id,step_id=step.id,claim_id=step.claim_id,
            section=step.section,basis_hash=step.basis_hash,projection_hash=step.projection_hash,
            result_digest=result_digest,candidate=payload)
        if existing is not None:
            if any(getattr(existing,k)!=v for k,v in values.items()): raise ValueError('section receipt replay conflict')
        else:
            existing=SalesOutputSection(**values);session.add(existing);await session.flush()
        # DB-only canonical receipt readback; never transitions the task.
        await session.refresh(existing)
        if existing.candidate!=payload: raise ValueError('section readback mismatch')
        return existing.id


SECTION_OWNER=SectionOwner()


async def assemble_task(session,scope,task_id):
    from ..execution.sales_tasks import intake_hash
    from ..sales.planning import plan_task
    row=await tasks.task_row(session,scope,task_id,edit=True)
    parent=(await session.execute(select(SalesExecution).where(SalesExecution.workspace_id==scope.workspace_id,
        SalesExecution.task_id==task_id).with_for_update())).scalar_one_or_none()
    if parent is None or parent.cancelled or parent.intake_hash!=intake_hash(row):
        raise ValueError('current durable execution required')
    current=await resolve_context(session,scope,[SourceRef.model_validate(r) for r in row.source_refs])
    skill=load_skill(row.skill_id,row.skill_version)
    plan=plan_task(skill,row.arguments,current)
    if (parent.intake_revision!=row.intake_history[-1]['revision'] or current.digest!=row.context_digest
        or parent.plan!=plan.model_dump(mode='json')): raise ValueError('frozen intake/context/plan changed')
    steps=(await session.execute(select(SalesStep).where(SalesStep.workspace_id==scope.workspace_id,
        SalesStep.execution_id==parent.id).with_for_update().execution_options(populate_existing=True))).scalars().all()
    receipts=(await session.execute(select(SalesOutputSection).where(SalesOutputSection.workspace_id==scope.workspace_id,
        SalesOutputSection.execution_id==parent.id))).scalars().all()
    planned={s.section for s in plan.steps}
    if (len(steps)!=len(planned) or {s.section for s in steps}!=planned or len(receipts)!=len(steps)
        or {r.step_id for r in receipts}!={s.id for s in steps}): raise ValueError('missing or foreign section receipt')
    by_id={s.id:s for s in steps}
    for receipt in receipts:
        step=by_id[receipt.step_id]
        if (step.state!='received' or (receipt.claim_id,receipt.section,receipt.basis_hash,receipt.projection_hash,receipt.result_digest)
            !=(step.claim_id,step.section,step.basis_hash,step.projection_hash,step.result_digest)
            or digest(receipt.candidate)!=step.result_digest): raise ValueError('mismatched durable child receipt')
        # Reconstruct the exact full basis using durable content-free model provenance.
        from ..sales.contracts import SalesModelRequest, Scope
        from ..sales.model import make_basis
        usage=step.usage or {}
        request=SalesModelRequest(task_id=row.id,step_id=step.id,skill_id=row.skill_id,skill_version=row.skill_version,
            context=current,model_id=usage.get('model_id'),route=usage.get('prompt_version'),arguments=row.arguments,section=step.section)
        admitted_scope=Scope(workspace_id=parent.workspace_id,project_id=parent.project_id,actor_id=parent.actor_id)
        basis=make_basis(request,admitted_scope,current)
        if basis['basis_hash']!=step.basis_hash or digest(wire_basis(basis))!=step.projection_hash:
            raise ValueError('section basis no longer matches admitted intake')
        validate_proposal(receipt.candidate,basis)
    result=assemble_sections(skill.output_kind,[r.candidate for r in receipts])
    # Every selected output is a dependency, including influence without a citation.
    data=result.model_dump(mode='json')
    data['dependencies']=[{'id':str(r.id),'revision':r.version} for r in current.refs if r.kind=='output']
    if skill.output_kind=='project_setup':
        from ..sales.setup import setup_state
        missing,basis=await setup_state(session,scope,row.arguments)
        data['content'].update(missing_fields=missing,setup_basis=basis)
    return validate_output(skill,data)


async def review_task_candidate(session,scope,row):
    """Read a trusted specialized producer, or assemble the exact model sections."""
    if row.skill_id=='sales-contacts':
        if len(row.output_ids)!=1: raise ValueError('reviewed provider proposal required')
        saved=await get_output(session,scope,uuid.UUID(row.output_ids[0]))
        if saved.availability!='available' or saved.kind!='enrichment_proposal':
            raise ValueError('current trusted provider output required')
        return OutputCandidate(kind=saved.kind,content=saved.content,citations=saved.citations,
            dependencies=saved.dependencies,native_refs=saved.native_refs)
    candidate=await assemble_or_core(session,scope,row)
    await authority(session,scope,candidate,[SourceRef.model_validate(r) for r in row.source_refs],
        row.context_digest,frozenset())
    return candidate


async def assemble_or_core(session,scope,row):
    from ..sales.research import CORE_SKILLS,candidate_for
    from ..sales.documents import DOCUMENT_SKILLS
    parent=await session.scalar(select(SalesExecution.id).where(SalesExecution.workspace_id==scope.workspace_id,
        SalesExecution.task_id==row.id))
    if parent is None and row.skill_id in CORE_SKILLS:
        from ..sales.actions import CORE_SKILL_OWNER
        return await CORE_SKILL_OWNER.candidate(session,scope,row)
    if parent is None and row.skill_id in DOCUMENT_SKILLS:
        from ..sales.actions import DOCUMENT_SKILL_OWNER
        return await DOCUMENT_SKILL_OWNER.candidate(session,scope,row)
    return await assemble_task(session,scope,row.id)


def visible_predicate(scope):
    thread=exists(select(ConversationThread.id).where(ConversationThread.workspace_id==scope.workspace_id,
        ConversationThread.project_id==scope.project_id,ConversationThread.id==SalesOutput.thread_id,
        or_(ConversationThread.owner_user_id==scope.actor_id,
            exists(select(ConversationThreadShare.id).where(ConversationThreadShare.workspace_id==scope.workspace_id,
                ConversationThreadShare.thread_id==ConversationThread.id,ConversationThreadShare.grantee_user_id==scope.actor_id)))))
    return or_(SalesOutputVersion.visibility=='project',thread)


async def authority(session,scope,candidate,refs,context_digest,seen,budget=None):
    if candidate.kind=='project_setup':
        from ..sales.setup import setup_state
        if candidate.content.setup_basis is None: raise ValueError('current native setup basis required')
        missing,basis=await setup_state(session,scope,candidate.content.setup_basis)
        if basis!=candidate.content.setup_basis or tuple(missing)!=candidate.content.missing_fields:
            raise ValueError('native setup authority changed')
    current=await resolve_context(session,scope,refs,_seen=seen,_budget=budget)
    if current.digest!=context_digest: raise ValueError('source revision or content changed')
    selected=set(current.refs)
    if len(set(candidate.citations))!=len(candidate.citations) or any(r not in selected for r in candidate.citations):
        raise ValueError('unselected citation')
    deps={(r.id,r.version) for r in refs if r.kind=='output'}
    if len(set(candidate.dependencies))!=len(candidate.dependencies) or {(d.id,d.revision) for d in candidate.dependencies}!=deps:
        raise ValueError('dependencies must cover exact selected output revisions')
    if len({(r.surface,r.id) for r in candidate.native_refs})!=len(candidate.native_refs):
        raise ValueError('duplicate native references')
    for ref in candidate.native_refs:
        await native_ref(session,scope,ref)
    if candidate.kind=='buyer_review':
        selected_buyers={r.id for r in refs if r.kind=='buyer'}
        if set(candidate.content.proposed_buyer_ids)!=selected_buyers:
            raise ValueError('review must cover exact selected native buyers')
    elif candidate.kind in {'pipeline_report','document_understanding','report_export'}:
        from ..sales.documents import validate_native_content
        await validate_native_content(session,scope,candidate)
    else:
        require_supported_identity_kind(candidate.kind)


async def get_output(session,scope,output_id,revision=None,*,_seen=frozenset(),_budget=None):
    if _budget is None: _budget=[0]
    if _budget[0]>=64: raise ValueError('output dependency read budget exceeded')
    _budget[0]+=1
    await output_scope(session,scope)
    from .xverum_dispatch import gates
    await gates(session,scope.workspace_id)
    query=select(SalesOutput,SalesOutputVersion).join(SalesOutputVersion,and_(
        SalesOutputVersion.workspace_id==SalesOutput.workspace_id,SalesOutputVersion.output_id==SalesOutput.id)).where(
        SalesOutput.workspace_id==scope.workspace_id,SalesOutput.project_id==scope.project_id,SalesOutput.id==output_id,
        SalesOutputVersion.revision==(revision if revision is not None else SalesOutput.revision),visible_predicate(scope))
    pair=(await session.execute(query.execution_options(populate_existing=True))).one_or_none()
    if pair is None: raise not_found()
    output,version=pair
    if version.visibility=='thread':
        await load(session,scope.workspace_id,scope.project_id,output.thread_id,scope.actor_id,lock=True)
    identity=(output.id,version.revision)
    if version.candidate.get('purged') is True:
        return OutputVersion(id=output.id,revision=version.revision,visibility=version.visibility,
            availability='unavailable',kind=version.candidate['kind'],content=None,citations=[],dependencies=[],native_refs=[])
    candidate=OutputCandidate.model_validate(version.candidate)
    available=True
    try:
        from .sales_retention import require_current
        dependencies=list((await session.scalars(select(SalesOutputDependency.source_id).where(
            SalesOutputDependency.workspace_id==scope.workspace_id,SalesOutputDependency.output_id==output.id,
            SalesOutputDependency.revision==version.revision))).all())
        # Physical purge pages can reach descendants before their producing task.
        # The root task tombstone is authoritative immediately for every revision
        # and visibility, independent of whether this output has been erased yet.
        await require_current(session,scope.workspace_id,[output.id,output.task_id,*dependencies])
        if identity in _seen or len(_seen)>=32: raise ValueError('cyclic or excessive output dependency depth')
        if candidate.kind=='enrichment_proposal':
            from .xverum_enrichment import load_record, validate_record, candidate_for
            producer=await load_record(session,scope,candidate.content.id)
            await validate_record(session,scope,producer)
            if (producer.task_id!=output.task_id or producer.output_revision!=version.revision
                or candidate_for(producer)!=candidate): raise ValueError('exact trusted producer revision required')
            current=await resolve_context(session,scope,[SourceRef.model_validate(r) for r in version.source_refs],
                _enrichment_id=producer.id if producer.applied or producer.proof.get('previous_proposal_id') else None)
            if current.digest!=version.context_digest: raise ValueError('producer source closure changed')
        else:
            await authority(session,scope,candidate,[SourceRef.model_validate(r) for r in version.source_refs],
                version.context_digest,_seen|{identity},_budget)
    except (ValueError,ApiError): available=False
    data=candidate.model_dump(mode='json') if available else dict(kind=candidate.kind,content=None,citations=[],dependencies=[],native_refs=[])
    # Never return task/thread identifiers or transcript backlinks, even for project shares.
    return OutputVersion(id=output.id,revision=version.revision,visibility=version.visibility,
        availability='available' if available else 'unavailable',**data)


async def save_output(session,scope,task_id,candidate,key,visibility='thread',*,expected_revision=None):
    from .xverum_dispatch import gates
    await gates(session,scope.workspace_id)
    await output_scope(session,scope)
    if visibility not in {'thread','project'}: raise ValueError('invalid audience')
    row=await tasks.task_row(session,scope,task_id,edit=True)
    candidate=validate_output(load_skill(row.skill_id,row.skill_version),candidate.model_dump(mode='json'))
    operation=await begin_idempotency(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        operation_id='saveSalesOutput',key=key,body={'candidate':candidate.model_dump(mode='json'),'visibility':visibility},
        target={'project_id':str(scope.project_id),'task_id':str(task_id)},precondition=str(expected_revision))
    if operation.replay:
        oid,rev=operation.record.resource_id.split(':')
        return await get_output(session,scope,uuid.UUID(oid),int(rev))
    if expected_revision is not None: tasks.check_revision(row.revision,expected_revision)
    if row.state not in {'ready_for_review','completed'} and not (row.skill_id=='sales-prospect' and row.state=='partially_completed'):
        raise ValueError('task is not ready to save')
    assembled=await assemble_or_core(session,scope,row)
    from ..sales.research import CORE_SKILLS
    from ..sales.documents import DOCUMENT_SKILLS
    if row.skill_id in CORE_SKILLS | DOCUMENT_SKILLS:
        parent=await session.scalar(select(SalesExecution.id).where(SalesExecution.workspace_id==scope.workspace_id,
            SalesExecution.task_id==row.id))
        if parent is None and candidate!=assembled:
            raise ValueError('core output must match exact server producer; use grounded model sections for authored work')
    if row.state!='completed' and assembled!=candidate:
        raise ValueError('initial save must match complete canonical section assembly')
    if row.state=='completed':
        # Explicit whole-document review may revise authored text after initial assembly.
        # It cannot invent native authority or change supplied commercial commitments.
        current_id=uuid.UUID(row.output_ids[0])
        previous=await get_output(session,scope,current_id)
        if previous.availability!='available' or candidate.native_refs!=previous.native_refs:
            raise ValueError('current saved output authority required')
        if candidate.kind=='sales_proposal' and candidate.content.terms!=assembled.content.terms:
            raise ValueError('commercial terms must match verified intake')
    refs=[SourceRef.model_validate(r) for r in row.source_refs]
    # Persist all selected dependencies, including evidence that influenced uncited prose.
    await authority(session,scope,candidate,refs,row.context_digest,frozenset())
    output=(await session.execute(select(SalesOutput).where(SalesOutput.workspace_id==scope.workspace_id,
        SalesOutput.task_id==task_id).with_for_update())).scalar_one_or_none()
    if output is None:
        output=SalesOutput(workspace_id=scope.workspace_id,project_id=scope.project_id,thread_id=row.thread_id,task_id=row.id,revision=1)
        session.add(output);await session.flush()
    else: output.revision+=1
    version=SalesOutputVersion(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
        visibility=visibility,candidate=candidate.model_dump(mode='json'),source_refs=row.source_refs,
        context_digest=row.context_digest,intake_revision=row.intake_history[-1]['revision'])
    session.add(version);await session.flush()
    for ref in refs:
        session.add(SalesOutputDependency(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
            kind=ref.kind,source_id=ref.id,source_revision=ref.version))
    if candidate.kind=='document_understanding':
        # Extraction status has native document-version semantics, unlike the
        # reviewer-approved offer-excerpt SourceRef. Index both without granting
        # unapproved extractor text the approved-fact resolver's authority.
        selected_documents={(r.id,r.version) for r in refs if r.kind=='document'}
        for item in candidate.content.document_basis:
            identity=(uuid.UUID(item['id']),item['version'])
            if identity not in selected_documents:
                session.add(SalesOutputDependency(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
                    kind='document',source_id=identity[0],source_revision=identity[1]))
    for ref in candidate.native_refs:
        session.add(SalesOutputNativeLink(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
            surface=ref.surface,native_id=ref.id,native_revision=ref.revision))
    await session.flush()
    saved=await get_output(session,scope,output.id,output.revision)
    if saved.availability!='available' or saved.content!=candidate.content: raise ValueError('canonical output readback failed')
    row.output_ids=[str(output.id)];row.pending_review=None;row.state='completed';row.revision+=1
    if candidate.kind=='document_understanding' and candidate.content.extraction_status!='complete':
        row.state='needs_input'
    if row.skill_id=='sales-prospect':
        from ..sales.research import prospect_missing
        if await prospect_missing(session,scope,row): row.state='partially_completed'
    await tasks.append_event(session,row.id,'output',{'output_id':str(saved.id),'revision':saved.revision})
    await tasks.append_event(session,row.id,'state',{'state':row.state,'revision':row.revision})
    complete_idempotency(operation,f'{saved.id}:{saved.revision}')
    await session.flush()
    return saved


async def list_outputs(session,scope,query=OutputListQuery()):
    await output_scope(session,scope)
    base=select(SalesOutput.id).join(SalesOutputVersion,and_(SalesOutputVersion.workspace_id==SalesOutput.workspace_id,
        SalesOutputVersion.output_id==SalesOutput.id,SalesOutputVersion.revision==SalesOutput.revision)).where(
        SalesOutput.workspace_id==scope.workspace_id,SalesOutput.project_id==scope.project_id,visible_predicate(scope))
    if query.native_id is not None:
        base=base.where(exists(select(SalesOutputNativeLink.id).where(SalesOutputNativeLink.workspace_id==scope.workspace_id,
            SalesOutputNativeLink.output_id==SalesOutput.id,SalesOutputNativeLink.revision==SalesOutput.revision,
            SalesOutputNativeLink.native_id==query.native_id,SalesOutputNativeLink.surface==query.native_surface)))
    total=(await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    ids=(await session.execute(base.order_by(SalesOutput.created_at,SalesOutput.id).offset(query.offset).limit(query.limit))).scalars().all()
    return OutputCollectionPage(items=[await get_output(session,scope,i) for i in ids],total=total,offset=query.offset,limit=query.limit)


async def save_enrichment_output(session,scope,producer):
    """Specialized DB-only producer, reconstructed from durable reviewed evidence.

    There is deliberately no candidate argument. Model assembly and its native
    identity guard remain unchanged. Only the canonical producer is accepted.
    """
    from .xverum_enrichment import load_record, validate_record, candidate_for
    producer=await load_record(session,scope,producer.id,edit=True)
    await validate_record(session,scope,producer)
    row=await tasks.task_row(session,scope,producer.task_id,edit=True)
    candidate=candidate_for(producer)
    refs=[SourceRef.model_validate(r) for r in row.source_refs]
    for ref in candidate.citations:
        if ref not in refs: refs.append(ref)
    current=await resolve_context(session,scope,refs,_enrichment_id=producer.id if producer.applied or producer.proof.get('previous_proposal_id') else None)
    output=await session.scalar(select(SalesOutput).where(SalesOutput.workspace_id==scope.workspace_id,
        SalesOutput.task_id==row.id).with_for_update())
    if output is None:
        output=SalesOutput(workspace_id=scope.workspace_id,project_id=scope.project_id,task_id=row.id,
            thread_id=row.thread_id,revision=1)
        session.add(output);await session.flush()
    else: output.revision+=1
    producer.output_revision=output.revision
    session.add(SalesOutputVersion(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
        visibility='thread',candidate=candidate.model_dump(mode='json'),source_refs=[r.model_dump(mode='json') for r in refs],
        context_digest=current.digest,intake_revision=row.intake_history[-1]['revision']))
    await session.flush()
    for ref in refs:
        session.add(SalesOutputDependency(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
            kind=ref.kind,source_id=ref.id,source_revision=ref.version))
    for ref in candidate.native_refs:
        session.add(SalesOutputNativeLink(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
            surface=ref.surface,native_id=ref.id,native_revision=ref.revision))
    await session.flush()
    saved=await get_output(session,scope,output.id,output.revision)
    if saved.availability!='available': raise ValueError('trusted producer canonical readback failed')
    row.output_ids=[str(output.id)];row.revision+=1
    row.state='ready_for_review'
    if producer.applied or producer.proof.get('previous_proposal_id'):
        from .xverum_enrichment import transition_chain
        reviewed={r.proof['provider_identity'] for r in await transition_chain(session,scope,producer) if r.applied}
        remaining=set(producer.proof.get('batch_identities',[producer.proof['provider_identity']]))-reviewed
        row.state='partially_completed' if remaining else 'completed'
    row.pending_review=None
    await tasks.append_event(session,row.id,'output',{'output_id':str(saved.id),'revision':saved.revision})
    await tasks.append_event(session,row.id,'state',{'state':row.state,'revision':row.revision})
    return saved


async def versions(session,scope,output_id,before_revision=None,limit=50):
    await output_scope(session,scope)
    base=select(SalesOutputVersion.revision).join(SalesOutput,and_(SalesOutput.workspace_id==SalesOutputVersion.workspace_id,
        SalesOutput.id==SalesOutputVersion.output_id)).where(SalesOutput.workspace_id==scope.workspace_id,
        SalesOutput.project_id==scope.project_id,SalesOutput.id==output_id,visible_predicate(scope))
    total=(await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    if not total: raise not_found()
    if before_revision is not None: base=base.where(SalesOutputVersion.revision<before_revision)
    revisions=(await session.execute(base.order_by(SalesOutputVersion.revision.desc()).limit(limit+1))).scalars().all()
    return {'outputs':[await get_output(session,scope,output_id,r) for r in revisions[:limit]],
        'next_revision':revisions[limit-1] if len(revisions)>limit else None}


async def native_ref(session,scope,ref):
    from .sales_native import read_native
    return await read_native(session,scope,ref)


async def policy_source_refs(session,scope,refs,*,seen=frozenset()):
    """Resolve only explicit output dependencies to current native policy evidence."""
    leaves=[]
    for ref in refs:
        if ref.kind!='output':
            if ref not in leaves: leaves.append(ref)
            continue
        identity=(ref.id,ref.version)
        if identity in seen or len(seen)>=32: raise ValueError('invalid output dependency graph')
        output=await get_output(session,scope,ref.id,ref.version)
        if output.availability!='available': raise ValueError('output policy sources unavailable')
        version=(await session.execute(select(SalesOutputVersion).where(SalesOutputVersion.workspace_id==scope.workspace_id,
            SalesOutputVersion.output_id==ref.id,SalesOutputVersion.revision==ref.version))).scalar_one()
        nested=await policy_source_refs(session,scope,[SourceRef.model_validate(r) for r in version.source_refs],seen=seen|{identity})
        for source in nested:
            if source not in leaves: leaves.append(source)
    return leaves


async def apply_native_action(session,scope,proposal,expected_revision,key):
    from .sales_native import apply_native_action as apply
    return await apply(session,scope,proposal,expected_revision,key)


async def link_native_action(session,scope,output,saved,ref,key,*,before,target):
    """Append a linked authored revision in the same native transaction; never edit history."""
    await session.refresh(output)
    if output.revision!=saved.revision: raise ApiError(409,'STALE_REVISION','saved output changed')
    version=(await session.execute(select(SalesOutputVersion).where(SalesOutputVersion.workspace_id==scope.workspace_id,
        SalesOutputVersion.output_id==output.id,SalesOutputVersion.revision==saved.revision))).scalar_one()
    data=dict(version.candidate)
    data['native_refs']=[r for r in data['native_refs'] if (r['surface'],r['id'])!=(ref.surface,str(ref.id))]+[ref.model_dump(mode='json')]
    refs=[SourceRef.model_validate(r) for r in version.source_refs]
    context_digest=version.context_digest
    if target.surface=='buyer' and any(r.kind=='buyer' and r.id==target.id for r in refs):
        if ref.revision!=target.revision+1 or before.digest!=version.context_digest:
            raise ValueError('exact native buyer transition required')
        old=next(r for r in refs if r.kind=='buyer' and r.id==target.id)
        if old.version!=target.revision: raise ValueError('selected buyer differs')
        new=old.model_copy(update={'version':ref.revision})
        refs=[new if r==old else r for r in refs]
        current=await resolve_context(session,scope,refs)
        # A note save must not silently refresh evidence, other sources or policy.
        expected=[{**entry,'ref':new.model_dump(mode='json')} if entry['ref']==old.model_dump(mode='json') else entry
                  for entry in before._sources]
        if (current._sources!=expected or current._profile_hash!=before._profile_hash
            or current.profile_version!=before.profile_version or current.connection_generations!=before.connection_generations):
            raise ValueError('native mutation changed selected facts')
        def transition(value):
            if isinstance(value,dict):
                if value==old.model_dump(mode='json'): return new.model_dump(mode='json')
                return {k:transition(v) for k,v in value.items()}
            if isinstance(value,list): return [transition(v) for v in value]
            return value
        data=transition(data)
        context_digest=current.digest
    candidate=OutputCandidate.model_validate(data)
    await authority(session,scope,candidate,refs,context_digest,frozenset())
    output.revision+=1
    session.add(SalesOutputVersion(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
        visibility=version.visibility,candidate=data,source_refs=[r.model_dump(mode='json') for r in refs],
        context_digest=context_digest,intake_revision=version.intake_revision))
    await session.flush()
    for source in [r.model_dump(mode='json') for r in refs]:
        session.add(SalesOutputDependency(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
            kind=source['kind'],source_id=uuid.UUID(source['id']),source_revision=source['version']))
    for native in candidate.native_refs:
        session.add(SalesOutputNativeLink(workspace_id=scope.workspace_id,output_id=output.id,revision=output.revision,
            surface=native.surface,native_id=native.id,native_revision=native.revision))
    await session.flush()
    readback=await get_output(session,scope,output.id,output.revision)
    if readback.availability!='available' or ref not in readback.native_refs: raise ValueError('native linked output readback failed')
    await tasks.append_event(session,output.task_id,'output',{'output_id':str(output.id),'revision':output.revision})
    row=await tasks.task_row(session,scope,output.task_id,edit=True)
    row.revision+=1
    await tasks.append_event(session,row.id,'state',{'state':row.state,'revision':row.revision})
