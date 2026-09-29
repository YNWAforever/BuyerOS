"""Exact-source permission for untrusted offer website retrieval."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from ..db.policy import PolicyDecision
from .safe_fetch import _safe_https_url
from .policy_service import policy_workspace_lock


def canonical_source_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 1000:
        raise ValueError("source URL length")
    checked = _safe_https_url(url)
    if checked is None:
        raise ValueError("source must be public HTTPS")
    normalized, host = checked
    if " " in normalized or ("." not in host and ":" not in host):
        raise ValueError("invalid source hostname")
    if ":" not in host and not re.fullmatch(r"[a-z0-9.-]+", host):
        raise ValueError("invalid source hostname")
    return normalized


async def current_offer_source_permission(session, *, workspace_id: uuid.UUID,
                                          project_id: uuid.UUID, source_url: str):
    """Latest project decision must permit this exact canonical URL."""
    await policy_workspace_lock(session, workspace_id)
    decision = (await session.execute(select(PolicyDecision).where(
        PolicyDecision.workspace_id == workspace_id,
        PolicyDecision.controller_scope_id == workspace_id,
        PolicyDecision.subject_type == "project",
        PolicyDecision.subject_id == project_id,
        PolicyDecision.purpose == "offer_research",
    ).order_by(PolicyDecision.created_at.desc(), PolicyDecision.id.desc()).limit(1))).scalar_one_or_none()
    if (decision is None or decision.status != "permitted"
            or decision.expires_at <= datetime.now(timezone.utc)
            or decision.basis_reference != source_url
            or not 1 <= decision.retention_days <= 30):
        return None
    return decision
