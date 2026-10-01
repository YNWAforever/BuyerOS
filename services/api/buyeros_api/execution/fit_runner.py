"""Tenant-scoped evidence-first fit callbacks for the T19 LangGraph.

No model route is activated here. The deterministic fit uses committed,
current evidence and creates an immutable assessment for human review.
"""

from datetime import datetime, timezone
import hashlib
import json
import uuid

from sqlalchemy import select

from buyeros_api.api.deps import permission_for_roles
from buyeros_api.db.buyers import Evidence, FitAssessment, ProjectBuyer, SourceDocument
from buyeros_api.db.icp import IcpVersion, Project
from buyeros_api.db.models import Membership
from buyeros_api.db.runs import SearchRun
from .provider_context import execution_session as tenant_session
from buyeros_api.services.fit import evaluate_evidence_fit
from buyeros_api.services.policy_service import evaluate_current_policy


class FitDomainRunner:
    """Re-read authoritative rows at each node; checkpoints confer no rights."""

    def __init__(self, engine, workspace_id: uuid.UUID, run_id: uuid.UUID,
                 buyer_id: uuid.UUID):
        self.engine = engine
        self.workspace_id = uuid.UUID(str(workspace_id))
        self.run_id = uuid.UUID(str(run_id))
        self.buyer_id = uuid.UUID(str(buyer_id))

    def _check_state(self, state: dict) -> None:
        if (uuid.UUID(state["workspace_id"]) != self.workspace_id or
                uuid.UUID(state["run_id"]) != self.run_id or
                uuid.UUID(state["buyer_id"]) != self.buyer_id or
                state["workflow_version"] != "fit-v1"):
            raise ValueError("fit checkpoint scope mismatch")

    async def _basis(self, session, *, lock_buyer: bool = False) -> tuple[str, list, list, ProjectBuyer]:
        now = datetime.now(timezone.utc)
        run_query = select(SearchRun).where(
            SearchRun.workspace_id == self.workspace_id, SearchRun.id == self.run_id,
        )
        run = (await session.execute(run_query.with_for_update() if lock_buyer else run_query)).scalar_one_or_none()
        buyer_query = select(ProjectBuyer).where(
            ProjectBuyer.workspace_id == self.workspace_id,
            ProjectBuyer.id == self.buyer_id,
        )
        if lock_buyer:
            buyer_query = buyer_query.with_for_update()
        buyer = (await session.execute(buyer_query)).scalar_one_or_none()
        if run is None or buyer is None or buyer.project_id != run.project_id:
            raise ValueError("fit run or buyer is absent")
        if run.status != "running" or run.stage != "fit":
            raise ValueError("fit run is no longer active")
        project = (await session.execute(select(Project).where(
            Project.workspace_id == self.workspace_id, Project.id == run.project_id,
        ))).scalar_one_or_none()
        icp = (await session.execute(select(IcpVersion).where(
            IcpVersion.workspace_id == self.workspace_id, IcpVersion.id == run.icp_version_id,
            IcpVersion.project_id == run.project_id,
        ))).scalar_one_or_none()
        snapshot = run.execution_snapshot or {}
        if (project is None or project.status != "active" or icp is None or
                icp.approved_at is None or icp.superseded_at is not None or
                project.active_icp_version_id != icp.id or
                project.offer_revision != snapshot.get("offer_revision") or
                icp.content_hash != snapshot.get("icp_content_hash")):
            raise ValueError("fit profile is stale")
        try:
            actor_id = uuid.UUID(snapshot["actor_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("fit actor is absent") from exc
        membership = (await session.execute(select(Membership).where(
            Membership.workspace_id == self.workspace_id,
            Membership.user_id == actor_id, Membership.active.is_(True),
        ))).scalar_one_or_none()
        if membership is None or not permission_for_roles(membership.roles, "startRun"):
            raise ValueError("fit actor was revoked")
        policy = await evaluate_current_policy(session, {
            "workspace_id": self.workspace_id, "project_id": run.project_id,
        }, "account_research", now)
        if not policy["allowed"]:
            raise ValueError("fit policy is not current")
        requirements = (icp.content or {}).get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise ValueError("fit requirements are absent")
        evidence_rows = (await session.execute(select(Evidence, SourceDocument).outerjoin(
            SourceDocument,
            (Evidence.workspace_id == SourceDocument.workspace_id) &
            (Evidence.source_document_id == SourceDocument.id),
        ).where(
            Evidence.workspace_id == self.workspace_id,
            Evidence.project_id == run.project_id,
            Evidence.run_id == run.id,
            Evidence.company_id == buyer.company_id,
        ).order_by(Evidence.id))).all()
        evidence = []
        basis_evidence = []
        for claim, source in evidence_rows:
            current = bool(source is not None and source.run_id == run.id and
                           source.project_id == run.project_id and
                           source.permission_purpose == "account_research" and
                           source.retention_until is not None and source.retention_until > now and
                           source.retrieved_at is not None and source.excerpt and
                           hashlib.sha256(source.excerpt.encode()).hexdigest() == source.digest and
                           claim.excerpt in source.excerpt)
            evidence.append({
                "id": str(claim.id), "requirement_id": claim.requirement_id,
                "stance": claim.stance, "current": current,
                "is_inference": claim.is_inference, "version": claim.version,
            })
            basis_evidence.append({"id": str(claim.id), "version": claim.version,
                                   "hash": claim.content_hash,
                                   "excerpt_digest": hashlib.sha256(claim.excerpt.encode()).hexdigest(),
                                   "requirement_id": claim.requirement_id, "stance": claim.stance,
                                   "source_digest": source.digest if source else None,
                                   "source_retention_until": source.retention_until.isoformat()
                                       if source and source.retention_until else None,
                                   "current": current})
        basis = {"icp_id": str(icp.id), "icp_hash": icp.content_hash,
                 "offer_revision": project.offer_revision,
                 "run_id": str(run.id), "buyer_id": str(buyer.id),
                 "requirements": requirements, "evidence": basis_evidence}
        digest = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(",", ":"),
                                          ensure_ascii=False).encode()).hexdigest()
        return digest, requirements, evidence, buyer

    async def load_basis(self, state: dict) -> dict:
        self._check_state(state)
        async with tenant_session(self.engine, self.workspace_id) as session:
            basis_hash, _, _, _ = await self._basis(session)
            return {"basis_hash": basis_hash}

    async def hard_exclusions(self, state: dict) -> dict:
        self._check_state(state)
        async with tenant_session(self.engine, self.workspace_id) as session:
            basis_hash, requirements, evidence, _ = await self._basis(session)
            if basis_hash != state["basis_hash"]:
                raise ValueError("fit basis changed")
            assessment = evaluate_evidence_fit(requirements, evidence)
            return {"hard_excluded": assessment["verdict"] == "not_a_match"}

    async def fit(self, state: dict) -> dict:
        self._check_state(state)
        # No paid/model call is available until a verified T14 route is selected.
        # The ID is a deterministic reference, not a fabricated provider result.
        return {"proposal_id": str(uuid.uuid5(uuid.NAMESPACE_URL,
            f"fit-v1:{self.run_id}:{self.buyer_id}:{state['basis_hash']}"))}

    async def verify(self, state: dict) -> dict:
        self._check_state(state)
        async with tenant_session(self.engine, self.workspace_id) as session:
            basis_hash, requirements, evidence, _ = await self._basis(session)
            if basis_hash != state["basis_hash"]:
                raise ValueError("fit basis changed before verification")
            evaluate_evidence_fit(requirements, evidence)
            return {"verified": True}

    async def persist(self, state: dict) -> dict:
        self._check_state(state)
        if state.get("verified") is not True:
            raise ValueError("unverified fit cannot persist")
        async with tenant_session(self.engine, self.workspace_id) as session:
            basis_hash, requirements, evidence, buyer = await self._basis(session, lock_buyer=True)
            if basis_hash != state["basis_hash"]:
                raise ValueError("fit basis changed before persistence")
            details = evaluate_evidence_fit(requirements, evidence)
            assessment_id = uuid.uuid5(uuid.NAMESPACE_URL,
                f"fit-v1:{self.run_id}:{self.buyer_id}:{basis_hash}")
            existing = (await session.execute(select(FitAssessment).where(
                FitAssessment.workspace_id == self.workspace_id,
                FitAssessment.id == assessment_id,
            ))).scalar_one_or_none()
            if existing is not None:
                if existing.evidence_set_hash != basis_hash or existing.assessment_details != details:
                    raise ValueError("fit assessment identity collision")
                return {"assessment_id": str(existing.id)}
            session.add(FitAssessment(
                id=assessment_id, workspace_id=self.workspace_id,
                project_id=buyer.project_id, project_buyer_id=buyer.id,
                icp_version_id=(await session.execute(select(SearchRun.icp_version_id).where(
                    SearchRun.workspace_id == self.workspace_id,
                    SearchRun.id == self.run_id,
                ))).scalar_one(),
                run_id=self.run_id, evidence_set_hash=basis_hash,
                verdict=details["verdict"], rationale=details["rationale"],
                evidence_ids=details["evidence_ids"],
                fit_algorithm_version="fit-v1", assessment_details=details,
            ))
            await session.flush()
            return {"assessment_id": str(assessment_id)}
