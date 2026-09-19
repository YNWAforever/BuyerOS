"""Contract-shaped Buyer, FitAssessment, HumanReview, Evidence and snapshot subsets (BO-008)."""


def fit_data(fit) -> dict:
    return {
        "id": str(fit.id),
        "icp_version_id": str(fit.icp_version_id),
        "assessment_version": 1,
        "verdict": fit.verdict,
        "rationale": fit.rationale,
        "supported_requirement_ids": [],
        "contradictory_evidence_ids": [],
        "evidence_refs": [],
        "unknowns": [],
        "next_action": "human_review",
        "freshness": "current",
        "evidence_set_hash": fit.evidence_set_hash,
        "prompt_version": "unversioned",
        "model_route_version": "unversioned",
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


def evidence_data(evidence, source) -> dict:
    data = {
        "id": str(evidence.id),
        "workspace_id": str(evidence.workspace_id),
        "project_id": str(evidence.project_id),
        "company_id": str(evidence.company_id),
        "source_document_id": str(evidence.source_document_id) if evidence.source_document_id else None,
        "version": 1,
        "excerpt": evidence.excerpt,
        "kind": "inference" if evidence.is_inference else "observation",
        "relationship": evidence.stance,
        "status": "available",
        "data_mode": "live",
    }
    if source is not None:
        data["source_url"] = source.canonical_url
        data["retrieved_at"] = source.retrieved_at.isoformat() if source.retrieved_at else None
        if source.language:
            data["original_language"] = source.language
    if evidence.requirement_id:
        data["requirement_id"] = evidence.requirement_id
    if evidence.translation:
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


def buyer_data(buyer, company, *, fit=None, review=None, owner_membership_id=None, evidence_count=0) -> dict:
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
        "note": buyer.note,
        "evidence_count": evidence_count,
    }
    if company.domain:
        data["normalized_domain"] = company.domain
    if fit is not None:
        data["fit"] = fit_data(fit)
    # The review is contract-valid only when its assessment is known; a review stored without a fit
    # (reviewBuyers on a fit-less buyer) is omitted rather than emitted incomplete.
    if review is not None and fit is not None and review.fit_assessment_id is not None:
        data["review"] = review_data(review, fit)
    return data
