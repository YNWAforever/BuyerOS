"""T17: one transactional, idempotent raw candidate → buyer → evidence write."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.buyers import Company, Evidence, FitAssessment, ProjectBuyer, SourceDocument
from ..db.contact import ProviderOperation
from ..db.icp import IcpVersion, Project
from ..db.models import Membership
from ..db.outcomes import AuditEvent
from ..db.runs import CompanyAlias, RawCandidate, RunEvent, SearchRun
from .canonicalize import normalize_source_url, normalized_registry_id, registrable_hint


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text(value: object, *, label: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"invalid {label}")
    result = " ".join(value.split())
    if not result or len(result) > maximum or "\x00" in result:
        raise ValueError(f"invalid {label}")
    return result


def _uuid(value: object, *, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"invalid {label}") from exc


async def persist_candidate_evidence(
    session: AsyncSession, run_id: uuid.UUID, provider_operation_id: uuid.UUID,
    candidate: dict, sources: list[dict],
) -> uuid.UUID:
    """Commit all domain rows in the caller's tenant transaction or none.

    The run row serializes per-run counters and sequence allocation. Registry
    uniqueness protects cross-run races; domains and names never auto-merge.
    """
    run_id = _uuid(run_id, label="run")
    provider_operation_id = _uuid(provider_operation_id, label="provider operation")
    if not isinstance(candidate, dict) or not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        raise ValueError("candidate and 1-20 sources required")
    source_url = _text(candidate.get("source_url"), label="source URL", maximum=2000)
    normalized_url = normalize_source_url(source_url)
    legal_name = _text(candidate.get("legal_name"), label="legal name", maximum=400)
    display_name = _text(candidate.get("display_name", legal_name), label="display name", maximum=400)
    domain = registrable_hint(candidate.get("domain") or normalized_url)
    registry_id = normalized_registry_id(candidate.get("registry_id"))
    external_ref = candidate.get("external_ref")
    if external_ref is not None:
        external_ref = _text(external_ref, label="external reference", maximum=255)
    assessment = candidate.get("assessment")
    if assessment is not None:
        if not isinstance(assessment, dict) or assessment.get("verdict") not in {
            "match", "needs_review", "not_a_match",
        }:
            raise ValueError("invalid assessment verdict")
        rationale = _text(assessment.get("rationale"), label="assessment rationale", maximum=4000)
    else:
        rationale = None
    raw_payload = {
        "legal_name": legal_name, "display_name": display_name, "domain": domain,
        "registry_id": registry_id, "external_ref": external_ref,
    }
    fingerprint = _hash({"url": normalized_url, **raw_payload})

    run = (await session.execute(select(SearchRun).where(SearchRun.id == run_id)
                                 .with_for_update())).scalar_one_or_none()
    if run is None or run.status not in {"running", "partial", "cancel_requested"}:
        raise ValueError("active tenant run required")
    workspace_id, project_id = run.workspace_id, run.project_id
    operation = (await session.execute(select(ProviderOperation).where(
        ProviderOperation.workspace_id == workspace_id,
        ProviderOperation.id == provider_operation_id,
    ))).scalar_one_or_none()
    plan = (run.execution_snapshot or {}).get("query_plan")
    if isinstance(plan, dict) and plan.get("schema") == "query-plan.v1":
        query_ids = {item["id"] for item in plan.get("queries", [])
                     if isinstance(item, dict) and isinstance(item.get("id"), str)
                     and re.fullmatch(r"[0-9a-f]{24}", item["id"])}
        allowed_intents = {f"research:{run_id}:{query_id}" for query_id in query_ids}
    else:
        # Pre-T18 run rows have no immutable query plan and retain their original
        # one-operation binding; new runs must bind one of their planned queries.
        allowed_intents = {f"research:{run_id}"}
    if (operation is None or operation.capability != "account_search"
            or operation.intent_key not in allowed_intents
            or operation.status not in {"accepted", "completed", "settled"}):
        raise ValueError("accepted search provider operation required")
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ))).scalar_one_or_none()
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id,
        IcpVersion.id == run.icp_version_id,
    ))).scalar_one_or_none()
    if (project is None or icp is None or icp.approved_at is None
            or project.active_icp_version_id != icp.id or icp.superseded_at is not None):
        raise ValueError("current approved ICP required")
    requirement_ids = {
        str(item.get("id")) for item in icp.content.get("requirements", [])
        if isinstance(item, dict) and item.get("id")
    }

    prepared: list[tuple[SourceDocument, dict, str, str | None]] = []
    seen_claims: set[str] = set()
    now = datetime.now(timezone.utc)
    for claim in sources:
        if not isinstance(claim, dict):
            raise ValueError("invalid evidence claim")
        source_id = _uuid(claim.get("source_document_id"), label="source document")
        source = (await session.execute(select(SourceDocument).where(
            SourceDocument.workspace_id == workspace_id,
            SourceDocument.id == source_id,
        ))).scalar_one_or_none()
        if (source is None or source.project_id != project_id or source.run_id != run_id
                or source.permission_purpose != "account_research"
                or source.retention_until is None or source.retention_until <= now
                or source.retrieved_at is None or not source.excerpt
                or not re.fullmatch(r"[0-9a-f]{64}", source.digest)):
            raise ValueError("source is absent, foreign, stale or not permitted")
        excerpt = _text(claim.get("excerpt"), label="evidence excerpt", maximum=4000)
        if excerpt not in source.excerpt:
            raise ValueError("evidence excerpt is not anchored to source")
        stance = claim.get("stance")
        if stance not in {"supports", "contradicts", "qualifies"}:
            raise ValueError("invalid evidence stance")
        requirement_id = claim.get("requirement_id")
        if requirement_id is not None and str(requirement_id) not in requirement_ids:
            raise ValueError("evidence requirement is outside the approved ICP")
        key = _hash({"source": str(source_id), "digest": source.digest,
                     "excerpt": excerpt, "stance": stance,
                     "requirement_id": str(requirement_id) if requirement_id else None,
                     "is_inference": claim.get("is_inference") is True})
        if key in seen_claims:
            raise ValueError("duplicate evidence claim")
        seen_claims.add(key)
        prepared.append((source, claim, excerpt, str(requirement_id) if requirement_id else None))

    result = await session.execute(pg_insert(RawCandidate).values(
        id=uuid.uuid4(), workspace_id=workspace_id, run_id=run_id,
        source_url=source_url, normalized_url=normalized_url,
        external_ref=external_ref, raw_digest=_hash(raw_payload),
        provider_operation_id=provider_operation_id,
        candidate_fingerprint=fingerprint, raw_payload=raw_payload,
        merge_state="unmapped",
    ).on_conflict_do_nothing().returning(RawCandidate.id))
    raw_id = result.scalar_one_or_none()
    raw_new = raw_id is not None
    if raw_id is None:
        raw_id = (await session.execute(select(RawCandidate.id).where(
            RawCandidate.workspace_id == workspace_id,
            RawCandidate.run_id == run_id,
            RawCandidate.provider_operation_id == provider_operation_id,
            RawCandidate.candidate_fingerprint == fingerprint,
        ))).scalar_one()
    raw = (await session.execute(select(RawCandidate).where(
        RawCandidate.workspace_id == workspace_id, RawCandidate.id == raw_id,
    ))).scalar_one()

    company_id = raw.canonical_company_id
    preexisting_registry = False
    if company_id is None:
        if registry_id is not None:
            preexisting_registry = (await session.execute(select(Company.id).where(
                Company.workspace_id == workspace_id, Company.registry_id == registry_id,
            ))).scalar_one_or_none() is not None
            inserted = await session.execute(pg_insert(Company).values(
                id=uuid.uuid4(), workspace_id=workspace_id, legal_name=legal_name,
                display_name=display_name, domain=domain, registry_id=registry_id,
            ).on_conflict_do_nothing().returning(Company.id))
            company_id = inserted.scalar_one_or_none()
            if company_id is None:
                company_id = (await session.execute(select(Company.id).where(
                    Company.workspace_id == workspace_id, Company.registry_id == registry_id,
                ))).scalar_one()
        else:
            company_id = uuid.uuid4()
            session.add(Company(id=company_id, workspace_id=workspace_id,
                                legal_name=legal_name, display_name=display_name,
                                domain=domain, registry_id=None))
            await session.flush()
        other_domain_entity = (await session.execute(select(Company.id).where(
            Company.workspace_id == workspace_id, Company.domain == domain,
            Company.id != company_id,
        ).limit(1))).scalar_one_or_none()
        decision = ("needs_review" if registry_id is None or other_domain_entity is not None
                    else "exact_registry" if preexisting_registry else "created")
        raw.canonical_company_id = company_id
        raw.merge_state = decision
        session.add(CompanyAlias(
            id=uuid.uuid4(), workspace_id=workspace_id, company_id=company_id,
            raw_candidate_id=raw_id, alias_type="registry_id" if registry_id else "domain_hint",
            normalized_value=registry_id or domain,
            provenance=f"provider_operation:{provider_operation_id}",
            reviewed=False, decision_state=decision,
        ))
        await session.flush()
    else:
        decision = raw.merge_state

    buyer_insert = await session.execute(pg_insert(ProjectBuyer).values(
        id=uuid.uuid4(), workspace_id=workspace_id, project_id=project_id,
        company_id=company_id, version=1,
    ).on_conflict_do_nothing().returning(ProjectBuyer.id))
    buyer_id = buyer_insert.scalar_one_or_none()
    if buyer_id is None:
        buyer_id = (await session.execute(select(ProjectBuyer.id).where(
            ProjectBuyer.workspace_id == workspace_id,
            ProjectBuyer.project_id == project_id,
            ProjectBuyer.company_id == company_id,
        ))).scalar_one()

    evidence_ids: list[uuid.UUID] = []
    evidence_hashes: list[str] = []
    evidence_new = 0
    for source, claim, excerpt, requirement_id in prepared:
        claim_hash = _hash({
            "source_id": str(source.id), "source_digest": source.digest,
            "excerpt": excerpt, "stance": claim["stance"],
            "requirement_id": requirement_id,
            "is_inference": claim.get("is_inference") is True,
        })
        evidence_id = uuid.uuid5(raw_id, f"{company_id}:{claim_hash}")
        inserted = await session.execute(pg_insert(Evidence).values(
            id=evidence_id, workspace_id=workspace_id, project_id=project_id,
            company_id=company_id, source_document_id=source.id,
            requirement_id=requirement_id, stance=claim["stance"],
            excerpt=excerpt, translation=None,
            is_inference=claim.get("is_inference") is True,
            run_id=run_id, raw_candidate_id=raw_id,
            provider_operation_id=provider_operation_id,
            content_hash=claim_hash, observed_at=claim.get("observed_at"), version=1,
        ).on_conflict_do_nothing().returning(Evidence.id))
        evidence_new += int(inserted.scalar_one_or_none() is not None)
        evidence_ids.append(evidence_id)
        evidence_hashes.append(claim_hash)

    assessment_new = False
    if assessment is not None:
        verdict = assessment["verdict"]
        if decision == "needs_review" or not any(
            legal_name.casefold() in source.excerpt.casefold() for source, *_ in prepared
        ):
            verdict = "needs_review"
        evidence_set_hash = _hash(sorted(zip(map(str, evidence_ids), evidence_hashes)))
        assessment_id = uuid.uuid5(
            buyer_id, _hash({"run": str(run_id), "evidence": evidence_set_hash,
                             "verdict": verdict, "rationale": rationale}),
        )
        inserted = await session.execute(pg_insert(FitAssessment).values(
            id=assessment_id, workspace_id=workspace_id, project_id=project_id,
            project_buyer_id=buyer_id, icp_version_id=icp.id,
            evidence_set_hash=evidence_set_hash, verdict=verdict,
            rationale=rationale, evidence_ids=[str(value) for value in evidence_ids],
            run_id=run_id,
        ).on_conflict_do_nothing().returning(FitAssessment.id))
        assessment_new = inserted.scalar_one_or_none() is not None

    if raw_new:
        cap = min(int(run.limits.get("max_results", 300)), 300)
        if run.raw_result_count >= cap:
            raise ValueError("run raw result limit reached")
        run.raw_result_count += 1
    if raw_new or evidence_new or assessment_new:
        sequence = (await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(
            RunEvent.workspace_id == workspace_id, RunEvent.run_id == run_id,
        ))).scalar_one() + 1
        session.add(RunEvent(
            id=uuid.uuid4(), workspace_id=workspace_id, run_id=run_id,
            sequence=sequence, event_type="candidate.persisted",
            payload={"raw_candidate_id": str(raw_id), "project_buyer_id": str(buyer_id),
                     "evidence_count": len(evidence_ids), "assessment_created": assessment_new},
        ))
    await session.flush()
    return buyer_id


async def repair_candidate_mapping(
    session: AsyncSession, raw_candidate_id: uuid.UUID, target_company_id: uuid.UUID,
    actor_user_id: uuid.UUID, reason: str,
) -> None:
    """Supersede an erroneous canonical link without rewriting historical evidence.

    Only a current reviewer/admin can make the correction. Replaying the same
    provider candidate then creates evidence and assessment for the corrected
    buyer; old citations remain in history and read as stale.
    """
    raw_candidate_id = _uuid(raw_candidate_id, label="raw candidate")
    target_company_id = _uuid(target_company_id, label="target company")
    actor_user_id = _uuid(actor_user_id, label="actor")
    reason = _text(reason, label="correction reason", maximum=400)
    if len(reason) < 10:
        raise ValueError("correction reason must be at least ten characters")
    raw = (await session.execute(select(RawCandidate).where(
        RawCandidate.id == raw_candidate_id,
    ))).scalar_one_or_none()
    if raw is None or raw.canonical_company_id is None:
        raise ValueError("mapped tenant candidate required")
    run = (await session.execute(select(SearchRun).where(
        SearchRun.workspace_id == raw.workspace_id, SearchRun.id == raw.run_id,
    ).with_for_update())).scalar_one_or_none()
    if run is None:
        raise ValueError("tenant run required")
    raw = (await session.execute(select(RawCandidate).where(
        RawCandidate.workspace_id == run.workspace_id,
        RawCandidate.id == raw_candidate_id,
    ).with_for_update())).scalar_one()
    membership = (await session.execute(select(Membership).where(
        Membership.workspace_id == run.workspace_id,
        Membership.user_id == actor_user_id,
        Membership.active.is_(True),
    ))).scalar_one_or_none()
    if membership is None or not {"reviewer", "workspace_admin"}.intersection(membership.roles):
        raise ValueError("current reviewer membership required")
    target = (await session.execute(select(Company).where(
        Company.workspace_id == run.workspace_id,
        Company.id == target_company_id,
    ))).scalar_one_or_none()
    if target is None or target.id == raw.canonical_company_id:
        raise ValueError("distinct tenant company required")
    previous = raw.canonical_company_id
    alias = (await session.execute(select(CompanyAlias).where(
        CompanyAlias.workspace_id == run.workspace_id,
        CompanyAlias.raw_candidate_id == raw.id,
        CompanyAlias.superseded_at.is_(None),
    ).with_for_update())).scalar_one_or_none()
    if alias is None or alias.company_id != previous:
        raise ValueError("current canonical alias required")
    alias.superseded_at = datetime.now(timezone.utc)
    await session.flush()
    session.add(CompanyAlias(
        id=uuid.uuid4(), workspace_id=run.workspace_id,
        company_id=target.id, raw_candidate_id=raw.id,
        alias_type="reviewed_split", normalized_value=alias.normalized_value,
        provenance=f"actor:{actor_user_id}", reviewed=True,
        decision_state="reviewed_split",
    ))
    raw.canonical_company_id = target.id
    raw.merge_state = "reviewed_split"
    session.add(AuditEvent(
        id=uuid.uuid4(), workspace_id=run.workspace_id, actor_id=actor_user_id,
        action="canonical_alias.repaired", subject_type="raw_candidate", subject_id=str(raw.id),
        detail_digest=_hash({"raw": str(raw.id), "before": str(previous), "after": str(target.id)}),
        reason=reason,
    ))
    sequence = (await session.execute(select(func.coalesce(func.max(RunEvent.sequence), 0)).where(
        RunEvent.workspace_id == run.workspace_id, RunEvent.run_id == run.id,
    ))).scalar_one() + 1
    session.add(RunEvent(
        id=uuid.uuid4(), workspace_id=run.workspace_id, run_id=run.id,
        sequence=sequence, event_type="candidate.alias_repaired",
        payload={"raw_candidate_id": str(raw.id), "from_company_id": str(previous),
                 "to_company_id": str(target.id)},
    ))
    await session.flush()
