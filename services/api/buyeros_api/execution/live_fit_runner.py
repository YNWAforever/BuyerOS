"""Opt-in shared model fit core; source prose stays out of graph checkpoints."""
from __future__ import annotations
import hashlib,uuid
from dataclasses import asdict
from sqlalchemy import select
from .provider_context import execution_session as tenant_session
from ..db.icp import Project,IcpVersion
from ..db.runs import SearchRun
from ..db.buyers import Evidence,FitAssessment,SourceDocument
from ..providers.live_model import ModelRequest,canonical_json,validate_live_proposal
from .fit_runner import FitDomainRunner

class LiveFitDomainRunner(FitDomainRunner):
    def __init__(self,engine,workspace_id,run_id,buyer_id,*,receipts,dispatch=None):
        super().__init__(engine,workspace_id,run_id,buyer_id)
        self.receipts=receipts
        self.dispatch=dispatch

    async def fit(self,state):
        self._check_state(state)
        if self.dispatch is None:raise ValueError('verified model admission unavailable')
        basis=await self.model_basis(state)
        # The code-owned C19 dispatcher must use execute_external and the frozen
        # reservation/operation/outbox receipt. No provider is selected here.
        ref=await self.dispatch(state,basis)
        if not isinstance(ref,str) or str(uuid.UUID(ref))!=ref:raise ValueError('durable model proposal reference required')
        return {'proposal_id':ref}

    async def _model_basis(self,session,state,*,lock_buyer=False):
        self._check_state(state)
        digest,requirements,current,buyer=await self._basis(session,lock_buyer=lock_buyer)
        if digest!=state['basis_hash']:raise ValueError('fit basis changed')
        run=(await session.execute(select(SearchRun).where(SearchRun.id==self.run_id))).scalar_one()
        project=(await session.execute(select(Project).where(Project.id==buyer.project_id))).scalar_one()
        icp=(await session.execute(select(IcpVersion).where(IcpVersion.id==run.icp_version_id))).scalar_one()
        rows=(await session.execute(select(Evidence,SourceDocument).outerjoin(SourceDocument,
            (Evidence.workspace_id==SourceDocument.workspace_id)&(Evidence.source_document_id==SourceDocument.id))
            .where(Evidence.project_id==buyer.project_id,Evidence.run_id==run.id,Evidence.company_id==buyer.company_id).order_by(Evidence.id).limit(101))).all()
        if len(rows)>100:raise ValueError('bounded current model evidence required')
        claims={item['id']:item for item in current};evidence=[]
        for claim,source in rows:
            if source is None:raise ValueError('model source unavailable')
            if not claims[str(claim.id)]['current']:raise ValueError('current source proof required before model input')
            proof={}
            if source.storage_mode=='research_page_excerpt':
                from ..services.research_native_basis import reviewed_research_evidence
                proof=await reviewed_research_evidence(session,workspace_id=self.workspace_id,run_id=run.id,
                    buyer_id=buyer.id,evidence_id=claim.id)
            evidence.append({**claims[str(claim.id)],'company_id':str(claim.company_id),'source_id':str(source.id),
                'content_hash':claim.content_hash,'source_hash':proof.get('source_hash',source.digest),**proof,'source_excerpt':source.excerpt,'excerpt':claim.excerpt,
                'retrieved_at':source.retrieved_at.isoformat() if source.retrieved_at else None,
                'retention_until':source.retention_until.isoformat() if source.retention_until else None,'permission_purpose':source.permission_purpose})
        return {'schema':'model-basis.v1','workspace_id':str(self.workspace_id),'project_id':str(buyer.project_id),
            'run_id':str(self.run_id),'buyer_id':str(self.buyer_id),'company_id':str(buyer.company_id),
            'actor_id':run.execution_snapshot['actor_id'],'offer_revision':project.offer_revision,
            'icp_version_id':str(icp.id),'icp_hash':icp.content_hash,'requirements':requirements,'evidence':evidence,'basis_hash':digest},buyer

    async def model_basis(self,state):
        async with tenant_session(self.engine,self.workspace_id) as session:
            basis,_=await self._model_basis(session,state)
            return basis

    async def _receipt_details(self,state,basis):
        saved=await self.receipts.get(state['proposal_id'])
        if saved is None or saved['state']!='received' or not isinstance(saved['request'],ModelRequest):raise ValueError('verified model receipt unavailable')
        request=saved['request'];response=saved['response']
        if request.basis!=basis:raise ValueError('fit basis changed before model persistence')
        if (not isinstance(response,dict) or hashlib.sha256(canonical_json(response)).hexdigest()!=saved['digest'] or
            response.get('model_id')!=request.model_id or response.get('prompt_version')!=request.route.prompt_version):raise ValueError('frozen model response changed')
        details=validate_live_proposal(response['proposal'],basis)
        if details!=response.get('assessment'):raise ValueError('model validation is stale')
        details['model_provenance']={'receipt_id':saved['ref'],'provider_ref':response['provider_ref'],'response_hash':saved['digest'],
            'request_hash':request.digest,'model_id':request.model_id,'prompt_version':request.route.prompt_version,'route_id':request.route.route_id,
            'offer_revision':basis['offer_revision'],'icp_version_id':basis['icp_version_id'],'icp_hash':basis['icp_hash'],
            'evidence_revisions':[{'id':item['id'],'version':item['version'],'source_id':item['source_id'],'source_hash':item['source_hash']} for item in basis['evidence']],
            'token_usage':response['usage']}
        return details,saved['digest']

    async def verify(self,state):
        if state.get('hard_excluded') is True:
            if (await super().hard_exclusions(state))['hard_excluded'] is not True:raise ValueError('unproven hard exclusion flag')
            return await super().verify(state)
        basis=await self.model_basis(state)
        await self._receipt_details(state,basis)
        return {'verified':True}

    async def persist(self,state):
        if state.get('hard_excluded') is True:
            if (await super().hard_exclusions(state))['hard_excluded'] is not True:raise ValueError('unproven hard exclusion flag')
            return await super().persist(state)
        if state.get('verified') is not True:raise ValueError('unverified model cannot persist')
        async with tenant_session(self.engine,self.workspace_id) as session:
            basis,buyer=await self._model_basis(session,state,lock_buyer=True)
            details,response_hash=await self._receipt_details(state,basis)
            assessment_id=uuid.uuid5(uuid.NAMESPACE_URL,f"live-model-v1:{self.run_id}:{self.buyer_id}:{state['basis_hash']}:{response_hash}")
            existing=(await session.execute(select(FitAssessment).where(FitAssessment.id==assessment_id))).scalar_one_or_none()
            if existing is not None:
                if existing.evidence_set_hash!=state['basis_hash'] or existing.assessment_details!=details:raise ValueError('immutable model assessment collision')
                return {'assessment_id':str(existing.id)}
            session.add(FitAssessment(id=assessment_id,workspace_id=self.workspace_id,project_id=buyer.project_id,project_buyer_id=buyer.id,
                icp_version_id=uuid.UUID(basis['icp_version_id']),run_id=self.run_id,evidence_set_hash=state['basis_hash'],
                verdict=details['verdict'],rationale=details['rationale'],evidence_ids=details['evidence_ids'],fit_algorithm_version='live-model-v1',assessment_details=details))
            await session.flush()
            return {'assessment_id':str(assessment_id)}
