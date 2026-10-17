"""Capture immutable research observations with read-only DB access; never call providers.

The v1 prediction schema is unchanged. Sidecar metadata preserves abstentions,
unresolved receipts and scope failures without exposing source prose or credentials.
Human/provider accuracy and billing remain separate acceptance gates.
"""
import argparse,asyncio,hashlib,json,os,re,sys
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.quality_metrics import provenance,write_new_report
from tools.evaluate_research_goldset import Goldset,Predictions

class StrictModel(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Subject(StrictModel):
    company_id:UUID
    buyer_id:UUID

class CaptureManifest(StrictModel):
    schema_version:Literal['buyeros.research-capture-manifest.v1']=Field(alias='schema')
    dataset_marker:str=Field(min_length=1,max_length=128,pattern=r'^[a-zA-Z0-9_-]+$')
    environment:Literal['owned-fixture','authorized-readonly']
    database:str=Field(min_length=1,max_length=128)
    workspace_id:UUID
    project_id:UUID
    actor_id:UUID
    frozen_at:datetime
    goldset_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    thresholds_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
    goldset_file:str=Field(min_length=1)
    thresholds_file:str=Field(min_length=1)
    run_ids:list[UUID]=Field(min_length=3,max_length=3)
    holdout:list[Subject]=Field(min_length=1,max_length=100)

def validated_manifest(data):
    m=CaptureManifest.model_validate(data)
    if (m.frozen_at.tzinfo is None or len(set(m.run_ids))!=3
        or len({row.company_id for row in m.holdout})!=len(m.holdout)
        or len({row.buyer_id for row in m.holdout})!=len(m.holdout)):
        raise ValueError('fixed distinct runs/companies/buyers and timezone-aware freeze required')
    return m

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _same_scope(row,m):
    return row.get('workspace_id')==str(m.workspace_id) and row.get('project_id')==str(m.project_id)

def capture_snapshot(manifest,snapshot):
    m=validated_manifest(manifest);predictions=[];observations=[]
    runs={row['id']:row for row in snapshot['runs']};buyers={row['id']:row for row in snapshot['buyers']}
    if len(runs)!=len(snapshot['runs']) or len(buyers)!=len(snapshot['buyers']):raise ValueError('ambiguous captured run/buyer identity')
    evidence={row['id']:row for row in snapshot['evidence']};receipts={row['id']:row for row in snapshot['receipts']}
    if len(evidence)!=len(snapshot['evidence']) or len(receipts)!=len(snapshot['receipts']):raise ValueError('ambiguous captured evidence/receipt identity')
    for run_id in map(str,m.run_ids):
        run=runs.get(run_id)
        if (run is None or not _same_scope(run,m) or run.get('actor_id')!=str(m.actor_id)
            or run['status'] not in {'completed','failed','partial','cancelled','paused_budget'}
            or datetime.fromisoformat(run['created_at'])<m.frozen_at):
            raise ValueError('run missing, nonterminal, foreign scope or posthoc freeze')
        rows=[]
        for subject in m.holdout:
            company,buyer_id=str(subject.company_id),str(subject.buyer_id);buyer=buyers.get(buyer_id);blockers=[];qualified=[];receipt=None;fit=None
            if buyer is not None and not _same_scope(buyer,m):raise ValueError('foreign captured buyer scope')
            actual_company=buyer['company_id'] if buyer is not None else company
            if buyer is None:blockers.append('missing_buyer')
            elif actual_company!=company:blockers.append('wrong_company')
            fits=[row for row in snapshot['assessments'] if row.get('run_id')==run_id and row.get('project_buyer_id')==buyer_id]
            if any(not _same_scope(row,m) for row in fits):raise ValueError('foreign captured assessment scope')
            if len(fits)!=1:blockers.append('missing_assessment' if not fits else 'ambiguous_assessment')
            else:
                fit=fits[0];model=fit.get('model_provenance') or {};receipt=receipts.get(model.get('receipt_id'))
                if (receipt is None or not _same_scope(receipt,m) or receipt.get('run_id')!=run_id
                    or receipt.get('buyer_id')!=buyer_id or receipt.get('company_id')!=company
                    or receipt.get('state')!='received' or receipt.get('redacted') is not False or receipt.get('expired') is not False
                    or any(not isinstance(model.get(k),str) or re.fullmatch(r'[0-9a-f]{64}',model[k]) is None for k in ['request_hash','response_hash'])
                    or receipt.get('request_hash')!=model.get('request_hash') or receipt.get('response_hash')!=model.get('response_hash')
                    or fit.get('fit_algorithm_version')!='live-model-v1'):
                    blockers.append('unproven_model_receipt')
                revisions={row['id']:row for row in model.get('evidence_revisions',[]) if isinstance(row,dict) and 'id' in row}
                for evidence_id in fit.get('evidence_ids',[]):
                    item=evidence.get(evidence_id);revision=revisions.get(evidence_id)
                    if (item is None or not _same_scope(item,m) or item.get('company_id')!=company or item.get('run_id')!=run_id
                        or item.get('current') is not True or item.get('is_inference') is not False
                        or revision is None or any(item.get(k)!=revision.get(k) for k in ['version','source_id','source_hash'])):
                        blockers.append('unsupported_evidence')
                    elif item.get('stance') not in {'supports','contradicts','qualifies'} or fit.get('verdict')=='match' and item.get('stance')!='supports':blockers.append('contradictory_or_qualified_evidence')
                    else:qualified.append(evidence_id)
                if fit.get('verdict')=='match' and not qualified:blockers.append('match_without_qualified_evidence')
            if run['status']!='completed':blockers.append('incomplete_run')
            if actual_company!=company:qualified=[]
            verdict={'match':'match','not_a_match':'not_match','needs_review':'needs_review'}.get(fit.get('verdict') if fit else None,'needs_review')
            if blockers:verdict='needs_review'
            rows.append({'company_id':company,'predicted_company_id':actual_company,'workspace_id':str(m.workspace_id),'verdict':verdict,'evidence_ids':sorted(set(qualified))})
            metadata={k:receipt.get(k) for k in ['id','state','request_hash','response_hash','contract_hash','pricing_version','model_id','prompt_version','redacted','expired']} if receipt else None
            observations.append({'run_id':run_id,'run_status':run['status'],'company_id':company,'buyer_id':buyer_id,'assessment_id':fit['id'] if fit else None,'fit_version':fit.get('fit_algorithm_version') if fit else None,'blockers':list(dict.fromkeys(blockers)),'receipt_metadata':metadata})
        predictions.append({'run_id':run_id,'rows':rows})
    data={'schema':'buyeros.research-predictions.v1','runs':predictions};Predictions.model_validate(data)
    proof={'schema':'buyeros.research-capture-provenance.v1','dataset_marker':m.dataset_marker,'manifest_hash':digest(manifest),'goldset_sha256':m.goldset_sha256,'thresholds_sha256':m.thresholds_sha256,'frozen_at':m.frozen_at.isoformat(),'environment':m.environment,'observations':observations,'run_metadata':[{'run_id':str(run),'snapshot_hash':runs[str(run)]['snapshot_hash'],'versions':runs[str(run)]['versions']} for run in m.run_ids],'repeat_policy':'separate company-level runs; no pooled 3n sample','live_verified':False,'release_accepted':False,'provider_calls':0,'billing_status':'not measured; no settlement inferred from received, unknown or absent cost events','label_independence':'not authenticated by capture'}
    return data,proof

async def capture_from_db(engine,manifest):
    from sqlalchemy import select,text
    from buyeros_api.db.session import tenant_session
    from buyeros_api.db.runs import SearchRun
    from buyeros_api.db.buyers import ProjectBuyer,FitAssessment,Evidence,SourceDocument,Company
    from buyeros_api.services.receipt_retention import require_current_receipt_read
    m=validated_manifest(manifest);url=engine.url
    if url.username!='buyeros_api' or url.database!=m.database:raise ValueError('exact capture target and restricted API role required')
    if m.environment=='owned-fixture' and (url.host not in {'127.0.0.1','localhost','::1'} or not m.database.startswith('buyeros_test_')):raise ValueError('owned loopback test database required')
    now=datetime.now(timezone.utc);snapshot={'runs':[],'buyers':[],'assessments':[],'evidence':[],'receipts':[]}
    async with tenant_session(engine,m.workspace_id,read_only=True) as session:
        identity=(await session.execute(text("SELECT current_user,current_database(),current_setting('transaction_read_only'),current_setting('transaction_isolation'),rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"))).one()
        if tuple(identity)!=('buyeros_api',m.database,'on','repeatable read',False,False):raise ValueError('restricted repeatable-read transaction required')
        # Resolve the domain of each held-out company through its actual buyer
        # relation. No caller-supplied URL can authorize the metadata capture.
        domains=(await session.execute(select(ProjectBuyer.id,Company.domain).join(Company,
            (Company.workspace_id==ProjectBuyer.workspace_id)&(Company.id==ProjectBuyer.company_id)).where(
            ProjectBuyer.workspace_id==m.workspace_id,ProjectBuyer.project_id==m.project_id,
            ProjectBuyer.id.in_([row.buyer_id for row in m.holdout])))).all()
        if {row[0] for row in domains}!={row.buyer_id for row in m.holdout} or any(not row[1] for row in domains):
            raise ValueError('current scoped company domains required for capture')
        await require_current_receipt_read(session,workspace_id=m.workspace_id,actor_id=m.actor_id,project_id=m.project_id,
            source_urls=tuple('https://'+row[1] for row in domains))
        scope={'workspace_id':m.workspace_id,'project_id':m.project_id}
        runs=(await session.execute(select(SearchRun).filter_by(**scope).where(SearchRun.id.in_(m.run_ids)))).scalars().all()
        for row in runs:
            frozen=row.execution_snapshot or {};cap=frozen.get('capability',{})
            snapshot['runs'].append({'id':str(row.id),'workspace_id':str(row.workspace_id),'project_id':str(row.project_id),'actor_id':frozen.get('actor_id'),'status':row.status,'created_at':row.created_at.isoformat(),'snapshot_hash':digest(frozen),'versions':{k:cap[k] for k in ['provider','price_version','receipt_contract_hash','registry_contract_hash'] if k in cap}})
        buyers=(await session.execute(select(ProjectBuyer).filter_by(**scope).where(ProjectBuyer.id.in_([row.buyer_id for row in m.holdout])))).scalars().all()
        snapshot['buyers']=[{'id':str(row.id),'company_id':str(row.company_id),'workspace_id':str(row.workspace_id),'project_id':str(row.project_id)} for row in buyers]
        fits=(await session.execute(select(FitAssessment).filter_by(**scope).where(FitAssessment.run_id.in_(m.run_ids),FitAssessment.project_buyer_id.in_([row.buyer_id for row in m.holdout])))).scalars().all()
        ids=set();receipt_ids=set()
        for row in fits:
            model=(row.assessment_details or {}).get('model_provenance') or {}
            snapshot['assessments'].append({'id':str(row.id),'workspace_id':str(row.workspace_id),'project_id':str(row.project_id),'project_buyer_id':str(row.project_buyer_id),'run_id':str(row.run_id),'verdict':row.verdict,'evidence_ids':row.evidence_ids,'fit_algorithm_version':row.fit_algorithm_version,'model_provenance':model})
            ids.update(UUID(value) for value in row.evidence_ids)
            if model.get('receipt_id'):receipt_ids.add(UUID(model['receipt_id']))
        items=(await session.execute(select(Evidence).filter_by(**scope).where(Evidence.id.in_(ids)))).scalars().all() if ids else []
        sources=(await session.execute(select(SourceDocument).filter_by(**scope).where(SourceDocument.id.in_([row.source_document_id for row in items if row.source_document_id])))).scalars().all() if items else []
        sources={row.id:row for row in sources}
        if items:
            if len(sources)!=len({row.source_document_id for row in items}):
                raise ValueError('current scoped evidence sources required for capture')
            await require_current_receipt_read(session,workspace_id=m.workspace_id,actor_id=m.actor_id,project_id=m.project_id,
                source_urls=tuple(row.canonical_url for row in sources.values()))
        for row in items:
            source=sources.get(row.source_document_id)
            current=source is not None and source.run_id==row.run_id and source.retention_until is not None and source.retention_until>now and source.permission_purpose=='account_research'
            snapshot['evidence'].append({'id':str(row.id),'workspace_id':str(row.workspace_id),'project_id':str(row.project_id),'company_id':str(row.company_id),'run_id':str(row.run_id),'version':row.version,'source_id':str(row.source_document_id) if row.source_document_id else None,'source_hash':source.digest if source else None,'current':current,'is_inference':row.is_inference,'stance':row.stance})
        if receipt_ids:
            # Only IDs/hashes/version metadata; never response/request/source prose.
            from sqlalchemy import bindparam
            query=text("SELECT r.id,r.workspace_id,r.project_id,r.request#>>'{basis,run_id}' AS run_id,r.request#>>'{basis,buyer_id}' AS buyer_id,r.request#>>'{basis,company_id}' AS company_id,r.state,r.request_hash,r.response_hash,r.contract_hash,r.pricing_version,r.request->>'model_id' AS model_id,r.request#>>'{route,prompt_version}' AS prompt_version,(r.redacted_at IS NOT NULL) AS redacted,public.buyeros_receipt_dependency_expired(r.workspace_id,'model',r.id,r.request) AS expired FROM model_receipts r WHERE r.workspace_id=:workspace_id AND r.project_id=:project_id AND r.id IN :ids").bindparams(bindparam('ids',expanding=True))
            for row in (await session.execute(query,{**scope,'ids':list(receipt_ids)})).mappings():snapshot['receipts'].append({k:str(v) if isinstance(v,UUID) else v for k,v in row.items()})
    data,proof=capture_snapshot(manifest,snapshot);proof.update(database_read_only=True,database_role='buyeros_api',isolation='repeatable read',observed_at=now.isoformat())
    return data,proof

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    sidecar=args.output.with_name(args.output.stem+'-provenance.json')
    try:
        raw=args.manifest.read_bytes();manifest=json.loads(raw);m=validated_manifest(manifest)
        inputs=[args.manifest]+[(args.manifest.parent/Path(name)).resolve() for name in [m.goldset_file,m.thresholds_file]]
        protected={p.resolve() for p in inputs}
        if args.output.resolve() in protected or sidecar.resolve() in protected or args.output.exists() or sidecar.exists():raise ValueError('both capture outputs must be new and cannot alias inputs')
        gold_raw,threshold_raw=[p.read_bytes() for p in inputs[1:]]
        if hashlib.sha256(gold_raw).hexdigest()!=m.goldset_sha256 or hashlib.sha256(threshold_raw).hexdigest()!=m.thresholds_sha256:raise ValueError('frozen goldset/threshold hashes changed')
        gold=Goldset.model_validate_json(gold_raw);held=[row for row in gold.rows if row.split=='holdout']
        if len(held)!=len(m.holdout) or {(row.company_id,row.workspace_id) for row in held}!={(row.company_id,m.workspace_id) for row in m.holdout}:raise ValueError('capture must cover exactly the frozen holdout')
        threshold=json.loads(threshold_raw)
        if threshold.get('schema')!='buyeros.research-thresholds.v1' or datetime.fromisoformat(threshold['frozen_at'])!=m.frozen_at:raise ValueError('threshold freeze must match capture manifest')
        dsn=os.environ.get('C61_RESEARCH_CAPTURE_DATABASE_URL')
        if not dsn:raise ValueError('explicit C61_RESEARCH_CAPTURE_DATABASE_URL required; inherited application DSNs unused')
        from sqlalchemy.ext.asyncio import create_async_engine
        from buyeros_api.api.deps import async_database_url
        async def read():
            engine=create_async_engine(async_database_url(dsn),isolation_level='REPEATABLE READ')
            try:return await capture_from_db(engine,manifest)
            finally:await engine.dispose()
        if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        data,proof=asyncio.run(read());root=Path(__file__).resolve().parents[3]
        proof.update(provenance(root,[Path(__file__).resolve(),Path(__file__).with_name('evaluate_research_goldset.py'),Path(__file__).with_name('quality_metrics.py')]))
        proof.update(manifest_file_sha256=hashlib.sha256(raw).hexdigest(),predictions_sha256=digest(data))
        write_new_report(args.output,data,tuple(inputs));write_new_report(sidecar,proof,tuple(inputs))
    except (OSError,ValueError,KeyError) as error:parser.error(str(error))
    except Exception:parser.error('capture DB read failed; no provider call; reconcile local output files before retry')
    print('Read-only capture written; provider_calls=0; live_verified=false; release_accepted=false')
    return 0

if __name__=='__main__':raise SystemExit(main())
