"""Server-owned reviewed enrichment; never accepts a client output candidate.

Input receipt closure remains authoritative on every read. An applied record
authorizes exactly its own buyer revision transition, not later edits.
"""
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit
from sqlalchemy import select, text
from ..api.errors import ApiError
from ..api.idempotency import begin_idempotency, complete_idempotency
from ..db.buyers import Company, Evidence
from ..db.runs import Person, ContactPoint
from ..db.xverum import XverumStage
from ..db.xverum_enrichment import XverumEnrichment as Record
from ..sales.contracts import EnrichmentProposal, FieldChoice, SourceRef, NativeRef, OutputCandidate
from ..sales.context import resolve_context, digest
from . import xverum_dispatch as dispatch, xverum_quotes as quotes


def conflict(message='enrichment authority changed'):
    return ApiError(409,'STALE_REVISION',message)


def person_state(person):
    return None if person is None else {'id':str(person.id),'name':person.full_name,'role':person.role,
        'retention':person.retention_expires_at.isoformat() if person.retention_expires_at else None}


def domain(value):
    if not value: return None
    parsed=urlsplit(value if '://' in value else 'https://'+value)
    return (parsed.hostname or '').lower().removeprefix('www.') or None


def identity_match(name, native_domain, projection):
    """Name alone and null chronology never prove current employer identity."""
    name_match=(projection.get('company_name') or '').strip().casefold()==name.strip().casefold()
    hint=domain(projection.get('website'))
    if hint and native_domain and hint!=domain(native_domain): return 'conflicting'
    if name_match and hint and hint==domain(native_domain): return 'resolved'
    return 'unresolved'


async def permission(session,scope):
    from .xverum_connections import authority
    await authority(session,scope,'updateBuyer')


async def subject_guard(session,scope,buyer,proposal,applied=None):
    """Never expose an alternate copy of a quarantined/expired native contact."""
    now=datetime.now(timezone.utc)
    emails=[f.proposed_value for f in proposal.fields if f.field=='business_email' and f.proposed_value]
    contacts=list((await session.scalars(select(ContactPoint).where(
        ContactPoint.workspace_id==scope.workspace_id,ContactPoint.company_id==buyer.company_id,
        ContactPoint.normalized_value.in_(emails)))).all()) if emails else []
    for cid in (applied or {}).get('contacts',[]):
        contact=await session.get(ContactPoint,uuid.UUID(cid))
        if contact is None: raise conflict('native contact unavailable')
        if contact not in contacts: contacts.append(contact)
    if contacts:
        if any(c.quarantined or not c.retention_expires_at or c.retention_expires_at<=now
               or c.validity=='unavailable' for c in contacts): raise conflict('native contact unavailable')
    for pid in (applied or {}).get('people',[]):
        person=await session.get(Person,uuid.UUID(pid))
        if person is None or not person.retention_expires_at or person.retention_expires_at<=now:
            raise conflict('native person unavailable')


async def load_record(session,scope,proposal_id,*,edit=False):
    await dispatch.gates(session,scope.workspace_id)
    await permission(session,scope)
    row=await session.scalar(select(Record).where(Record.workspace_id==scope.workspace_id,
        Record.project_id==scope.project_id,Record.actor_id==scope.actor_id,Record.id==proposal_id)
        .with_for_update().execution_options(populate_existing=True))
    if row is None or not row.proposal: raise ApiError(404,'NOT_FOUND','enrichment unavailable')
    from .sales_retention import require_current
    await require_current(session,scope.workspace_id,[row.id])
    if row.task_id:
        from .sales_tasks import task_row
        task=await task_row(session,scope,row.task_id,edit=edit)
        from ..execution.sales_tasks import intake_hash
        if task.skill_id!='sales-contacts' or intake_hash(task)!=row.proof['intake_hash']:
            raise conflict()
        if edit and task.state in {'cancelled','cancel_requested','failed','outcome_unknown'}:
            raise conflict('contacts task is no longer applicable')
    return row


async def transition_chain(session,scope,row):
    """At most three explicitly reviewed identities from the exact same paid batch.

    Links are immutable producer proof, never inferred from a matching current
    buyer version. A fork, gap, foreign receipt/task, or repeated identity fails.
    """
    chain=[row]
    while chain[0].proof.get('previous_proposal_id'):
        if len(chain)>=3: raise conflict('bounded batch transition required')
        prior=await load_record(session,scope,uuid.UUID(chain[0].proof['previous_proposal_id']))
        if not prior.applied or prior.id in {r.id for r in chain}: raise conflict('applied predecessor required')
        chain.insert(0,prior)
    while True:
        children=list((await session.scalars(select(Record).where(Record.workspace_id==scope.workspace_id,
            Record.project_id==scope.project_id,Record.actor_id==scope.actor_id,
            Record.proof['previous_proposal_id'].astext==str(chain[-1].id),Record.applied.is_not(None)))).all())
        if not children: break
        if len(children)!=1 or len(chain)>=3: raise conflict('ambiguous batch transition')
        chain.append(await load_record(session,scope,children[0].id))
    identities=set();root=chain[0]
    for index,item in enumerate(chain):
        proposal=EnrichmentProposal.model_validate(item.proposal)
        if proposal.id!=item.id or proposal.buyer_id!=item.buyer_id: raise conflict('producer identity changed')
        if (item.buyer_id!=root.buyer_id or item.task_id!=root.task_id
            or item.proof.get('receipt_ids')!=root.proof.get('receipt_ids')
            or proposal.buyer_version!=root.proposal['buyer_version']+index
            or item.proof['provider_identity'] in identities): raise conflict('exact batch transition required')
        identities.add(item.proof['provider_identity'])
        if index and (not chain[index-1].applied or item.proof['company']!=chain[index-1].applied['company']):
            raise conflict('batch before state changed')
        if item.applied and NativeRef.model_validate(item.applied['native'])!=NativeRef(
                surface='buyer',id=item.buyer_id,revision=proposal.buyer_version+1):
            raise conflict('exact enrichment revision transition required')
    return chain


async def _native_record_state(session,scope,row):
    """Validate every exact native step, without recursively resolving provider data."""
    proposal=EnrichmentProposal.model_validate(row.proposal)
    chain=await transition_chain(session,scope,row)
    latest=chain[-1]
    buyer=await quotes.buyer(session,scope,row.buyer_id)
    expected=latest.applied['native']['revision'] if latest.applied else latest.proposal['buyer_version']
    if buyer.version!=expected: raise conflict('buyer revision changed')
    company=await session.get(Company,buyer.company_id,populate_existing=True)
    expected_company=latest.applied['company'] if latest.applied else latest.proof['company']
    if {'name':company.display_name,'legal_name':company.legal_name,'domain':company.domain}!=expected_company:
        raise conflict('canonical company changed')
    for item in chain:
        await subject_guard(session,scope,buyer,EnrichmentProposal.model_validate(item.proposal),item.applied)
        if item.applied:
            for expected in item.applied['people_state']:
                person=await session.get(Person,uuid.UUID(expected['id']),populate_existing=True)
                if person_state(person)!=expected: raise conflict('native person changed')
            for expected in item.applied['contact_state']:
                contact=await session.get(ContactPoint,uuid.UUID(expected['id']),populate_existing=True)
                if contact is None or contact.version!=expected['version'] or digest({'value':contact.normalized_value})!=expected['value_digest']:
                    raise conflict('native contact changed')
        elif item.proof.get('person_id'):
            person=await session.get(Person,uuid.UUID(item.proof['person_id']),populate_existing=True)
            if person_state(person)!=item.proof['person_before']: raise conflict('native person changed')
    return proposal,buyer,company


async def transition_native_source(session,scope,producer_id,ref):
    row=await load_record(session,scope,producer_id)
    if not row.applied and not row.proof.get('previous_proposal_id'):
        return ref
    proposal,buyer,_=await _native_record_state(session,scope,row)
    if ref.kind=='buyer' and ref.id==buyer.id and ref.version==row.proof.get('source_buyer_version',proposal.buyer_version):
        return ref.model_copy(update={'version':buyer.version})
    return ref


async def _transition_source_digests(session,scope,producer_id,receipt_id,quote):
    """Re-load server-owned mutation proof for exactly its selected receipt closure.

    Not a supplied buyer/version exemption. Generic source/model consumers never
    pass a producer ID. The original search is authorized only as the immutable
    parent of a selected detail; its source digest/ACL/expiry remain enforced by
    source_search_evidence. Linked contexts may advance only the exact selected
    buyer through this producer; all other sources remain current-version checked.
    """
    from ..db.xverum import XverumToolReceipt, XverumReceiptRow, XverumCreditReservation, XverumQuoteRow
    row=await load_record(session,scope,producer_id)
    if not row.applied and not row.proof.get('previous_proposal_id'): raise conflict('committed native mutation proof required')
    proposal,buyer,_=await _native_record_state(session,scope,row)
    if quote.buyer_id!=buyer.id or quote.buyer_version!=row.proof.get('source_buyer_version',proposal.buyer_version):
        raise conflict('source is not part of the native revision transition')
    tools=list((await session.scalars(select(XverumToolReceipt).where(
        XverumToolReceipt.workspace_id==scope.workspace_id,
        XverumToolReceipt.id.in_([ref.id for ref in proposal.source_refs])))).all())
    if len(tools)!=len(proposal.source_refs): raise conflict('producer source identity changed')
    stages={tool.stage_id for tool in tools}
    if receipt_id not in stages:
        parents=set((await session.scalars(select(XverumQuoteRow.source_receipt_id)
            .join(XverumCreditReservation,XverumCreditReservation.quote_id==XverumQuoteRow.id)
            .join(XverumReceiptRow,XverumReceiptRow.reservation_id==XverumCreditReservation.id)
            .where(XverumReceiptRow.workspace_id==scope.workspace_id,XverumReceiptRow.id.in_(stages)))).all())
        if receipt_id not in parents: raise conflict('receipt is outside the reviewed producer closure')
        return None  # Original search: the calling source_search_evidence verifies its exact digest.
    expected={str(ref.id):value for ref,value in zip(proposal.source_refs,row.proof['evidence_digests'],strict=True)}
    return row.proof.get('receipt_digests',{}).get(str(receipt_id)) or {str(tool.id):expected[str(tool.id)] for tool in tools if tool.stage_id==receipt_id}


async def validate_record(session,scope,row):
    proposal,buyer,company=await _native_record_state(session,scope,row)
    values=[await dispatch.resolve_evidence(session,scope,ref,
        _enrichment_id=row.id if row.applied or row.proof.get('previous_proposal_id') else None) for ref in proposal.source_refs]
    if [digest(v) for v in values]!=row.proof['evidence_digests']: raise conflict('source revision changed')
    if any(v['buyer_id']!=str(buyer.id) or v['buyer_version']!=row.proof.get('source_buyer_version',proposal.buyer_version) for v in values):
        raise conflict('source buyer binding changed')
    return proposal,buyer,company,values


async def propose_enrichment(session,scope,buyer_id:uuid.UUID,receipt_ids:list[uuid.UUID],*,task_id=None,selected_id=None,previous_proposal_id=None):
    await dispatch.gates(session,scope.workspace_id)
    await permission(session,scope)
    if not receipt_ids or len(receipt_ids)>6 or len(set(receipt_ids))!=len(receipt_ids):
        raise ApiError(422,'INVALID_REQUEST','select one to six distinct detail receipts')
    buyer=await quotes.buyer(session,scope,buyer_id)
    company=await session.get(Company,buyer.company_id)
    previous=None
    if previous_proposal_id:
        previous=await load_record(session,scope,previous_proposal_id,edit=True)
        await validate_record(session,scope,previous)
        if (not previous.applied or previous.buyer_id!=buyer_id or
            previous.proof.get('receipt_ids')!=[str(r) for r in receipt_ids] or
            (task_id is not None and previous.task_id!=task_id)):
            raise conflict('exact reviewed batch predecessor required')
        task_id=previous.task_id
        if buyer.version!=previous.applied['native']['revision']:
            raise conflict('latest batch predecessor required')
    values=[];receipt_digests={}
    for rid in receipt_ids:
        evidence=await dispatch.read_evidence(session,scope,rid,_enrichment_id=previous.id if previous else None)
        receipt_digests[str(rid)]={v['id']:digest(v) for v in evidence}
        if not evidence: raise conflict('selected evidence expired')
        values.extend(evidence)
        stage=await session.get(XverumStage,rid)
        if task_id is None and stage.task_id: task_id=stage.task_id
    source_version=previous.proof.get('source_buyer_version',previous.proposal['buyer_version']) if previous else buyer.version
    if any(v['buyer_id']!=str(buyer_id) or v['buyer_version']!=source_version for v in values):
        raise conflict('receipt buyer revision changed')
    details=[v for v in values if v['tool'] in {'enrich_company_xverum','enrich_person_xverum'}]
    batch_identities=[v['provider_ids'][0] for v in details]
    if selected_id is not None:
        if previous:
            chain=await transition_chain(session,scope,previous)
            if any(r.proof['provider_identity']==selected_id for r in chain):
                raise conflict('identity already reviewed in this batch')
        if any(v['tool']=='enrich_company_xverum' for v in details) and len(details)!=1:
            raise conflict('company detail is restricted to one identity')
        details=[v for v in details if v['provider_ids']==[selected_id]]
        values=[v for v in values if v['provider_ids']==[selected_id]]
    if not details or len(details)>1:
        raise ApiError(409,'IDENTITY_SELECTION_REQUIRED','select one returned company or person detail identity')
    detail=details[0]; projection=detail['projection']
    if any(v['provider_ids']!=detail['provider_ids'] or v['connection_id']!=detail['connection_id'] for v in values):
        raise ApiError(409,'IDENTITY_SELECTION_REQUIRED','detail and email must identify the same selected person')
    refs=tuple(SourceRef(id=uuid.UUID(v['id']),version=1,kind='provider_evidence',
        locator='provider_evidence:'+v['id'],retention_class='durable') for v in values)
    match=identity_match(company.display_name,company.domain,projection)
    person=None;person_id=None
    pairs=[]
    if detail['tool']=='enrich_company_xverum':
        pairs=[('company_name',company.display_name,projection.get('company_name')),
               ('domain',company.domain,domain(projection.get('website'))),
               ('industry',None,projection.get('industry')),('location',None,projection.get('headquarters')),
               ('employee_count',None,projection.get('employees_num'))]
    else:
        person_id=uuid.uuid5(company.id,detail['connection_id']+':'+detail['provider_ids'][0])
        person=await session.get(Person,person_id)
        emails=[v for v in values if v['tool']=='get_email_xverum']
        entries=emails[0]['projection']['emails'] if emails else []
        # Explicit current employer field plus corroborating business email domain.
        # Experience.end_time=None is deliberately never inspected as current evidence.
        if ((projection.get('company_name') or '').casefold()==company.display_name.casefold()
            and len(entries)==1 and domain(entries[0]['email'].split('@')[-1])==domain(company.domain)):
            match='resolved'
        pairs=[('person_name',person.full_name if person else None,projection.get('full_name')),
               ('job_title',person.role if person else None,projection.get('position')),
               ('employer',company.display_name,projection.get('company_name'))]
        if len(entries)==1: pairs.append(('business_email',None,entries[0]['email'].lower()))
        elif len(entries)>1: match='ambiguous'
    now=datetime.now(timezone.utc)
    fields=tuple(FieldChoice(field=f,existing_value=before,proposed_value=after,
        status='unknown' if after is None else 'conflict' if before is not None and before!=after else 'proposed',
        source_refs=refs,retrieved_at=datetime.fromisoformat(detail['retrieved_at']),
        provider_freshness=('Xverum: '+str(entries[0].get('confidence') or 'unknown'))[:240]
            if f=='business_email' else None) for f,before,after in pairs)
    proposal=EnrichmentProposal(id=uuid.uuid4(),buyer_id=buyer.id,buyer_version=buyer.version,
        identity_match=match,fields=fields,source_refs=refs)
    await subject_guard(session,scope,buyer,proposal)
    proof={'company':{'name':company.display_name,'legal_name':company.legal_name,'domain':company.domain},
        'evidence_digests':[digest(v) for v in values], 'provider':'xverum',
        'provider_identity':detail['provider_ids'][0], 'intake_hash':None,
        'receipt_ids':[str(r) for r in receipt_ids],'receipt_digests':receipt_digests,'batch_identities':batch_identities,
        'source_buyer_version':source_version,'previous_proposal_id':str(previous.id) if previous else None}
    proof.update(person_id=str(person_id) if person_id else None,person_before=person_state(person))
    if task_id:
        from .sales_tasks import task_row
        from ..execution.sales_tasks import intake_hash
        task=await task_row(session,scope,task_id,edit=True)
        if task.skill_id!='sales-contacts' or task.arguments.get('buyer_id')!=str(buyer_id) or task.state in {'cancelled','cancel_requested','failed','outcome_unknown'} or (task.state=='completed' and not previous):
            raise conflict('current contacts task required')
        await resolve_context(session,scope,task.source_refs,_enrichment_id=previous.id if previous else None)
        proof['intake_hash']=intake_hash(task)
    row=Record(id=proposal.id,workspace_id=scope.workspace_id,project_id=scope.project_id,
        actor_id=scope.actor_id,buyer_id=buyer.id,task_id=task_id,thread_id=task.thread_id if task_id else None,
        proposal=proposal.model_dump(mode='json'),proof=proof)
    session.add(row);await session.flush()
    for ref in proposal.source_refs:
        await session.execute(text('INSERT INTO xverum_enrichment_dependencies(workspace_id,enrichment_id,source_id) VALUES(:ws,:id,:source)'),
            dict(ws=scope.workspace_id,id=row.id,source=ref.id))
    if task_id:
        from .sales_outputs import save_enrichment_output
        await save_enrichment_output(session,scope,row)
    return proposal


async def read_proposal(session,scope,proposal_id):
    row=await load_record(session,scope,proposal_id)
    await validate_record(session,scope,row)
    return candidate_for(row).content


async def apply_enrichment(session,scope,proposal_id:uuid.UUID,fields:list[str],expected_buyer_version:int,key:str)->NativeRef:
    row=await load_record(session,scope,proposal_id,edit=True)
    proposal,buyer,company,values=await validate_record(session,scope,row)
    operation=await begin_idempotency(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        operation_id='applyXverumEnrichment',key=key,body={'proposal':str(proposal_id),'fields':fields},
        target={'project_id':str(scope.project_id)},precondition=str(expected_buyer_version))
    if operation.replay:
        if not row.applied or row.applied['native']!=operation.response: raise conflict()
        if row.task_id:
            from .sales_outputs import get_output
            saved=await get_output(session,scope,uuid.UUID(row.applied['output_id']),row.output_revision)
            if saved.availability!='available': raise conflict('committed output unavailable')
        return NativeRef.model_validate(row.applied['native'])
    if row.applied or expected_buyer_version!=proposal.buyer_version or buyer.version!=expected_buyer_version:
        raise conflict('buyer revision changed')
    if proposal.identity_match!='resolved': raise ApiError(409,'IDENTITY_SELECTION_REQUIRED','corroborated identity required')
    chosen={f.field:f for f in proposal.fields if f.field in fields}
    if not fields or len(set(fields))!=len(fields) or len(chosen)!=len(fields) or any(f.proposed_value is None for f in chosen.values()):
        raise ApiError(422,'INVALID_REQUEST','select only known proposed business fields')
    limits={'company_name':400,'domain':255,'person_name':200,'job_title':200,'business_email':320}
    if any(name in limits and len(str(f.proposed_value))>limits[name] for name,f in chosen.items()):
        raise ApiError(422,'INVALID_REQUEST','selected value exceeds the native field bound')
    # Serialize canonical mutations after gates and task authority.
    from ..db.buyers import ProjectBuyer
    await session.execute(select(ProjectBuyer.id).where(ProjectBuyer.id==buyer.id).with_for_update())
    await session.refresh(buyer)
    if buyer.version!=expected_buyer_version: raise conflict('buyer revision changed')
    await session.execute(select(Company.id).where(Company.id==company.id).with_for_update())
    people=[]; contacts=[]
    expiry=min(datetime.fromisoformat(v['expires_at']) for v in values)
    if 'company_name' in chosen: company.display_name=chosen['company_name'].proposed_value
    if 'domain' in chosen: company.domain=chosen['domain'].proposed_value
    if any(f in chosen for f in ('person_name','job_title','business_email')):
        # Stable per-connection provider identity prevents duplicate people across proposals.
        person_id=uuid.uuid5(company.id,values[0]['connection_id']+':'+row.proof['provider_identity'])
        person=await session.get(Person,person_id)
        if person is None:
            if 'person_name' not in chosen: raise ApiError(422,'INVALID_REQUEST','review person name before creating a person')
            person=Person(id=person_id,workspace_id=scope.workspace_id,company_id=company.id,retention_expires_at=expiry)
            session.add(person)
        elif not person.retention_expires_at or person.retention_expires_at<=datetime.now(timezone.utc):
            raise conflict('expired person requires native revalidation')
        if 'person_name' in chosen: person.full_name=chosen['person_name'].proposed_value
        if 'job_title' in chosen: person.role=chosen['job_title'].proposed_value
        people=[str(person.id)]
        await session.flush()
        if 'business_email' in chosen:
            email=chosen['business_email'].proposed_value
            contact=await session.scalar(select(ContactPoint).where(ContactPoint.company_id==company.id,
                ContactPoint.type=='business_email',ContactPoint.normalized_value==email))
            if contact is None:
                contact=ContactPoint(id=uuid.uuid4(),workspace_id=scope.workspace_id,company_id=company.id,
                    person_id=person.id,normalized_value=email,type='business_email',validity='unverified_public',
                    retention_expires_at=expiry,quarantined=False)
                session.add(contact)
            elif contact.person_id!=person.id: raise conflict('contact identity differs')
            contacts=[str(contact.id)]
    # Native evidence stores references, never another ungoverned contact body.
    session.add(Evidence(workspace_id=scope.workspace_id,project_id=scope.project_id,company_id=company.id,
        stance='qualifies',excerpt='Xverum reviewed fields: '+','.join(fields)+'; proposal '+str(row.id),
        is_inference=False,content_hash=digest(row.proposal),observed_at=datetime.now(timezone.utc)))
    buyer.version+=1
    native=NativeRef(surface='buyer',id=buyer.id,revision=buyer.version)
    await session.flush()
    row.applied={'native':native.model_dump(mode='json'),'fields':fields,'people':people,'contacts':contacts,
        'people_state':[person_state(person)] if people else [],
        'contact_state':[{'id':str(contact.id),'version':contact.version,'value_digest':digest({'value':contact.normalized_value})}] if contacts else [],
        'business_fields':{name:f.proposed_value for name,f in chosen.items() if name not in {'person_name','job_title','business_email'}},
        'company':{'name':company.display_name,'legal_name':company.legal_name,'domain':company.domain}}
    await session.flush()
    if row.task_id:
        from .sales_outputs import save_enrichment_output
        saved=await save_enrichment_output(session,scope,row)
        row.applied={**row.applied,'output_id':str(saved.id)}
    await validate_record(session,scope,row)
    from .audit_service import append_audit
    append_audit(session,workspace_id=scope.workspace_id,actor_id=scope.actor_id,
        action='xverum.enrichment_applied',entity_type='buyer',entity_id=buyer.id)
    complete_idempotency(operation,str(buyer.id),response=native.model_dump(mode='json'))
    await session.flush()
    return native


def candidate_for(row):
    proposal=EnrichmentProposal.model_validate(row.proposal)
    if row.applied:
        # Saved results link to native subjects. Reading a contact value belongs
        # exclusively to buyer_read.contact_detail and its contact.read policy.
        proposal=proposal.model_copy(update={'fields':tuple(f.model_copy(update={
            'existing_value':None,'proposed_value':None}) if f.field=='business_email' else f
            for f in proposal.fields if f.field in row.applied['fields'])})
    return OutputCandidate(kind='enrichment_proposal',content=proposal,citations=list(proposal.source_refs),
        dependencies=[],native_refs=[NativeRef.model_validate(row.applied['native'])] if row.applied else [])
