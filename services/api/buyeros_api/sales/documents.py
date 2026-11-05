"""Nonbillable, evidence-only document preparation. No search or invented proof."""
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from .contracts import OutputCandidate, SourceRef, NativeRef, OutputDependency
from .context import resolve_context, digest, require_scope
from .registry import load_skill, validate_arguments

DOCUMENT_SKILLS=frozenset({'sales-prep','sales-proposal','sales-objections','sales-competitors',
    'sales-report','sales-report-pdf','understand-documents'})


def compose_sales_document(skill_id, context, inputs):
    zh=inputs.get('language')=='zh-HK'
    def tr(en,cn): return cn if zh else en
    findings=[]
    for source in context._sources:
        ref=SourceRef.model_validate(source['ref'])
        if ref.kind=='profile': continue
        for excerpt in source['excerpts'][:1]:
            findings.append({'statement':excerpt,'evidence':[ref], 'confidence':'inference'
                if ref.kind=='output' or any(p.get('is_inference') for p in source.get('native_proof',[])) else 'high'})
    if not findings: raise ValueError('Needs input: selected evidence required')
    excerpts='\n'.join(f['statement'] for f in findings)
    if len(excerpts)>3500: raise ValueError('select a smaller document evidence scope')
    unknown=tr('Needs input: pricing, case-study proof and buyer commitments are unverified.',
        '需要資料：價格、案例證據及買家承諾尚未確認。')
    common={'summary':tr('Selected evidence for review','已選取資料，供審閱'),'unknowns':[unknown]}
    if skill_id=='sales-prep':
        duration=inputs.get('duration_minutes',30)
        content={**common,'cheat_sheet':excerpts,'attendees':[],
            'talking_points':[tr('Proposed objective: ','建議目標：')+inputs['objective']],
            'discovery_questions':[tr('Which requirements and decision criteria should we verify?', '需要確認哪些要求及決策準則？')],
            'agenda':[{'topic':tr('Confirm requirements','確認要求'),'minutes':duration//3},
                {'topic':tr('Review selected evidence','審閱已選資料'),'minutes':duration//3},
                {'topic':tr('Agree possible next steps','討論下一步'),'minutes':duration-2*(duration//3)}],
            'next_steps':[tr('Confirm actions and owners after the meeting; none are agreed yet.','會後確認行動及負責人；目前尚未達成協議。')]}
    elif skill_id=='sales-proposal':
        if not inputs.get('terms'): raise ValueError('Needs input: verified pricing and commercial terms')
        proof=[SourceRef.model_validate(r) for r in inputs.get('case_study_refs',[])]
        if not proof or any(r not in context.refs for r in proof):
            raise ValueError('Needs input: selected case-study proof')
        if any(SourceRef.model_validate(r) not in context.refs for t in inputs['terms'] for r in t['evidence']):
            raise ValueError('Needs input: pricing evidence must be selected')
        content={**common,'problem':tr('Buyer requirements to validate: ','待確認買家要求：')+'; '.join(inputs['pain_points']),
            'solution':excerpts,'terms':inputs['terms'],'assumptions':[tr('Pain points are user-supplied, not buyer commitments.','痛點由使用者提供，並非買家承諾。')],
            'proof_points':[f for f in findings if any(r in proof for r in f['evidence'])][:10],'followup':[]}
    elif skill_id=='sales-objections':
        content={**common,'responses':[{'objection':o,
            'feel_felt_found':tr('Acknowledge the concern. No comparable customer experience is verified; review the selected evidence before claiming results.',
                '先理解顧慮。目前未確認類似客戶經驗；提出成效主張前，請審閱已選證據。'),
            'acknowledge_bridge_close':tr('Acknowledge: '+o+'. Bridge to the selected evidence and ask which requirement remains unmet.',
                '確認顧慮：'+o+'。參照已選證據，詢問仍未滿足的要求。'),
            'followup_question':tr('What evidence would address this concern?','哪些證據能回應這項顧慮？'),
            'walk_away_criteria':tr('Pause if a mandatory requirement cannot be supported.','若無法證明符合必要要求，請暫停。'),
            'proof_points':findings[:10]} for o in inputs['objections']]}
    elif skill_id=='sales-competitors':
        names=inputs.get('competitor_names',[])
        competitors=[f for f in findings if any(n.casefold() in f['statement'].casefold() for n in names)]
        if not names or any(not any(n.casefold() in f['statement'].casefold() for f in competitors) for n in names):
            raise ValueError('Needs input: selected competitor evidence for every named competitor')
        content={**common,'competitors':competitors[:20],'strengths':[],'gaps':[],
            'switching_costs':[tr('Unknown; verify migration costs with the buyer.','未知；請與買家確認轉換成本。')]}
    else: raise ValueError('document kind requires native producer')
    return OutputCandidate(kind=load_skill(skill_id,'1').output_kind,content=content,citations=context.refs,
        dependencies=[OutputDependency(id=r.id,revision=r.version) for r in context.refs if r.kind=='output'],native_refs=[])


async def document_state(session,scope,ids):
    """Native extractor candidates remain unapproved, including ready image-only files."""
    from ..db.ingestion import OfferDocument
    from ..db.document_uploads import DocumentSlide
    await require_scope(session,scope)
    rows=[]
    for id in ids:
        doc=await session.scalar(select(OfferDocument).where(OfferDocument.workspace_id==scope.workspace_id,
            OfferDocument.project_id==scope.project_id,OfferDocument.id==UUID(str(id))))
        if doc is None or doc.deleted_at is not None or doc.status=='deleted' or doc.retention_until is None or doc.retention_until<=datetime.now(timezone.utc):
            raise ValueError('document unavailable or retention expired')
        slides=(await session.scalars(select(DocumentSlide).where(DocumentSlide.workspace_id==scope.workspace_id,
            DocumentSlide.project_id==scope.project_id,DocumentSlide.document_id==doc.id).order_by(DocumentSlide.slide_number))).all()
        text_slides=[s for s in slides if s.text.strip()]
        rows.append({'id':str(doc.id),'version':doc.version,'status':doc.status,'sha256':doc.sha256,
            'extraction_digest':digest({'facts':doc.fact_candidates,'metadata':doc.extraction_metadata,
                'slides':[{'number':s.slide_number,'text':s.text,'classification':s.classification} for s in slides]}),
            'has_text':bool(text_slides or doc.fact_candidates),'partial':bool(slides and len(text_slides)!=len(slides))})
    return rows


async def understanding(session,scope,args):
    from ..db.ingestion import OfferDocument
    from ..db.document_uploads import DocumentSlide
    basis=await document_state(session,scope,args['document_ids'])
    zh=args.get('language')=='zh-HK'
    # Raw unapproved candidates are not silently promoted into model facts.
    summaries=[];passages=[]
    for item in basis:
        doc=await session.get(OfferDocument,UUID(item['id']))
        if item['status']=='ready':
            slides=(await session.scalars(select(DocumentSlide).where(DocumentSlide.workspace_id==scope.workspace_id,
                DocumentSlide.project_id==scope.project_id,DocumentSlide.document_id==doc.id).order_by(DocumentSlide.slide_number))).all()
            if slides:
                passages.extend(f'Slide {s.slide_number}: {s.text}' for s in slides if s.text.strip())
            else: passages.extend(str(f.get('excerpt') or f.get('value')) for f in doc.fact_candidates)
        summaries.append(f"{doc.filename}: {item['status']}; "+('文字已擷取，須於原有文件頁審閱。' if zh and item['has_text'] else
            'Extracted candidates require review on the native document page.' if item['has_text'] else
            '未有可用文字；圖片內容未知。' if zh else 'No extracted text; image content is unknown.'))
    if len(passages)>64 or sum(len(p) for p in passages)>12000:
        raise ValueError('Needs input: select a smaller extraction scope')
    complete=all(r['status']=='ready' and r['has_text'] and not r['partial'] for r in basis)
    return {'summary':'\n'.join(summaries),'unknowns':['擷取內容尚未核實；請審閱原有文件候選資料。' if zh else
        'Extraction is not verified fact; review native document candidates.'], 'document_ids':args['document_ids'],
        'findings':[],'extraction_status':'complete' if complete else 'partial' if any(r['has_text'] for r in basis) else 'unavailable',
        'document_basis':basis,'extracted_passages':passages,'question':args.get('question')}


async def candidate_for(session,scope,row):
    from .research import validate_intake_authority
    context=await resolve_context(session,scope,[SourceRef.model_validate(r) for r in row.source_refs])
    if context.digest!=row.context_digest: raise ValueError('selected source closure changed')
    args=await validate_intake_authority(session,scope,row,context)
    if row.skill_id=='sales-report':
        from .reporting import build_pipeline_report
        result=await build_pipeline_report(session,scope,datetime.fromisoformat(args['as_of']),args)
    elif row.skill_id=='understand-documents':
        result=OutputCandidate(kind='document_understanding',content=await understanding(session,scope,args),citations=[],dependencies=[],native_refs=[])
    elif row.skill_id=='sales-report-pdf':
        from ..services.export_service import load_actor_export, authorize_export_content
        if not args.get('export_id'): raise ValueError('Needs input: explicitly approve an exact saved revision export first')
        job=await load_actor_export(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,export_id=UUID(args['export_id']))
        await authorize_export_content(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,export_id=job.id,_metadata_only=True)
        if (job.project_id!=scope.project_id or job.kind!='sales_output' or job.format!='pdf' or
            job.selection_manifest['output_id']!=args['output_id'] or job.selection_manifest['revision']!=args['output_revision']):
            raise ValueError('exact approved PDF export required')
        if not any(r.kind=='output' and str(r.id)==args['output_id'] and r.version==args['output_revision'] for r in context.refs):
            raise ValueError('select exact exported output revision')
        export_ref=NativeRef(surface='export',id=job.id,revision=args['output_revision'])
        result=OutputCandidate(kind='report_export',content={'output_id':args['output_id'],'output_revision':args['output_revision'],
            'export_ref':export_ref,'media_type':'application/pdf'},citations=[],
            dependencies=[OutputDependency(id=UUID(args['output_id']),revision=args['output_revision'])],native_refs=[export_ref])
    else: result=compose_sales_document(row.skill_id,context,args)
    native=list(result.native_refs)
    native += [NativeRef(surface=r.kind,id=r.id,revision=r.version) for r in context.refs if r.kind in {'buyer','profile','run'} and not any(n.surface==r.kind and n.id==r.id for n in native)]
    return result.model_copy(update={'citations':context.refs,'dependencies':tuple(OutputDependency(id=r.id,revision=r.version) for r in context.refs if r.kind=='output'),'native_refs':tuple(native)})


async def validate_native_content(session,scope,candidate):
    if candidate.kind=='document_understanding':
        if await document_state(session,scope,candidate.content.document_ids)!=list(candidate.content.document_basis):
            raise ValueError('native extraction basis changed')
    elif candidate.kind=='pipeline_report':
        from .reporting import build_pipeline_report
        c=candidate.content
        expected=await build_pipeline_report(session,scope,c.as_of,dict(c.filters))
        if expected.content!=c: raise ValueError('native pipeline authority changed')
    elif candidate.kind=='report_export':
        from ..services.export_service import load_actor_export, authorize_export_content
        c=candidate.content
        job=await load_actor_export(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,export_id=c.export_ref.id)
        await authorize_export_content(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,export_id=job.id,_metadata_only=True)
        if job.project_id!=scope.project_id or job.kind!='sales_output' or job.format!='pdf' or job.selection_manifest['output_id']!=str(c.output_id) or job.selection_manifest['revision']!=c.output_revision or c.export_ref.revision!=c.output_revision:
            raise ValueError('export revision binding changed')
