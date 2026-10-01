"""Contract-shaped Buyer, FitAssessment, HumanReview, Evidence and snapshot subsets (BO-008)."""

from datetime import datetime, timezone


def fit_data(fit, *, freshness: str = "current") -> dict:
    details = fit.assessment_details or {}
    return {
        "id": str(fit.id),
        "icp_version_id": str(fit.icp_version_id),
        "assessment_version": 1,
        "verdict": fit.verdict,
        "rationale": fit.rationale,
        "supported_requirement_ids": details.get("supported_requirement_ids", []),
        "contradictory_evidence_ids": details.get("contradictory_evidence_ids", []),
        "evidence_refs": details.get("evidence_refs", []),
        "unknowns": (["Source evidence needs refresh"] if freshness == "stale"
                     else details.get("unknown_requirement_ids", [])),
        "next_action": "request_evidence" if freshness == "stale" else details.get("next_action", "human_review"),
        "freshness": freshness,
        "evidence_set_hash": fit.evidence_set_hash.removeprefix("sha256:"),
        "prompt_version": fit.fit_algorithm_version,
        "model_route_version": "none" if fit.fit_algorithm_version == "fit-v1" else "unversioned",
    }


def review_data(review, fit) -> dict:
    """The contract HumanReview must carry both assessment_id and icp_version_id; only call this
    when both are known (see buyer_data)."""
    return {
        "id": str(review.id),
        "status": review.state,
        "reason": review.reason or "",
        "actor_id": str(review.actor_user_id),
        "at": review.created_at.isoformat(),
        "assessment_id": str(review.fit_assessment_id),
        "icp_version_id": str(fit.icp_version_id),
    }


def evidence_data(evidence, source, *, mapped_company_id=None) -> dict:
    """Expose source provenance and current accessibility without leaking retired content."""
    modern = source is not None and source.project_id is not None
    if source is None:
        status = "deleted"
    elif modern and (source.project_id != evidence.project_id
                     or source.permission_purpose != "account_research"
                     or (evidence.run_id is not None and source.run_id != evidence.run_id)):
        status = "access_blocked"
    elif modern and not source.excerpt and not source.object_key:
        status = "deleted"
    elif evidence.raw_candidate_id is not None and mapped_company_id != evidence.company_id:
        status = "stale"
    elif source.retention_until is not None and source.retention_until <= datetime.now(timezone.utc):
        status = "expired"
    elif not modern or source.retention_until is None or not source.excerpt:
        status = "stale"
    else:
        status = "available"
    available = status == "available"
    data = {
        "id": str(evidence.id),
        "workspace_id": str(evidence.workspace_id),
        "project_id": str(evidence.project_id),
        "company_id": str(evidence.company_id),
        "version": evidence.version,
        "excerpt": evidence.excerpt if available or not modern else "Source unavailable",
        "kind": "inference" if evidence.is_inference else "observation",
        "relationship": evidence.stance,
        "status": status,
        "data_mode": "live",
    }
    if evidence.source_document_id:
        data["source_document_id"] = str(evidence.source_document_id)
    if source is not None and status not in {"deleted", "access_blocked"}:
        data["source_url"] = source.canonical_url
        if source.retrieved_at:
            data["retrieved_at"] = source.retrieved_at.isoformat()
        if source.language:
            data["original_language"] = source.language
        if source.retention_until:
            data["retention_until"] = source.retention_until.isoformat()
    if evidence.observed_at:
        data["observed_at"] = evidence.observed_at.isoformat()
    if evidence.content_hash:
        data["content_hash"] = evidence.content_hash
    if evidence.requirement_id:
        data["requirement_id"] = evidence.requirement_id
    if evidence.translation and available:
        data["translated_excerpt"] = evidence.translation
    return data


def snapshot_data(snapshot, *, sort: str, total: int, result_limit_reached: bool) -> dict:
    return {
        "id": str(snapshot.id),
        "workspace_id": str(snapshot.workspace_id),
        "project_id": str(snapshot.project_id),
        "actor_id": str(snapshot.actor_user_id),
        "filters_hash": snapshot.filter_hash,
        "sort": sort,
        "total": total,
        "created_at": snapshot.created_at.isoformat(),
        "expires_at": snapshot.expires_at.isoformat() if snapshot.expires_at else None,
        "snapshot_version": 1,
        "result_limit_reached": result_limit_reached,
    }


def buyer_data(buyer, company, *, fit=None, fit_freshness="current", review=None, review_fit=None, owner_membership_id=None, evidence_count=0) -> dict:
    data = {
        "id": str(buyer.id),
        "workspace_id": str(buyer.workspace_id),
        "version": buyer.version,
        "created_at": buyer.created_at.isoformat(),
        "updated_at": buyer.updated_at.isoformat(),
        "data_mode": "live",
        "project_id": str(buyer.project_id),
        "company_id": str(buyer.company_id),
        "name": company.display_name,
        "contact_research_status": "not_researched",
        "suppressed": False,
        "owner_membership_id": str(owner_membership_id) if owner_membership_id else None,
        "note": buyer.note or "",
        "contacts": [],
        "policies": [],
        "evidence_count": evidence_count,
    }
    if company.domain:
        data["normalized_domain"] = company.domain
    if fit is not None:
        data["fit"] = fit_data(fit, freshness=fit_freshness)
    # The review is contract-valid only when its assessment is known; a review stored without a fit
    # (reviewBuyers on a fit-less buyer) is omitted rather than emitted incomplete.
    if review is not None and review_fit is not None and review.fit_assessment_id is not None:
        data["review"] = review_data(review, review_fit)
    return data
