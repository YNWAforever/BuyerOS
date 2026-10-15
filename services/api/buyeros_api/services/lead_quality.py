"""Pure source-quality rules. Technical deliverability is a separate property."""
from datetime import datetime, timedelta

from ..api.lead_schemas import LeadObservationRecord, LeadReviewRecord, LeadQuality

SHARED_MAILBOXES = frozenset({
    "info", "sales", "contact", "hello", "office", "admin", "support", "orders",
    "purchasing", "procurement", "buying", "enquiries", "enquiry", "accounts",
})


def relevant_observations(observations, person_id, contact_id):
    selected = [
        row for row in observations
        if (row.person_id == person_id and row.claim in {"employment", "procurement_scope"})
        or (contact_id is not None and row.contact_id == contact_id and row.claim == "channel_ownership")
    ]
    superseded = {row.supersedes_id for row in observations if row.supersedes_id is not None}
    return [row for row in selected if row.id not in superseded]


def evaluate_lead_quality(
    *, observations: list[LeadObservationRecord], review: LeadReviewRecord | None, now: datetime,
) -> LeadQuality:
    blockers = []
    if review is None:
        return LeadQuality(employment_current=False, procurement_current=False, channel_ownership_current=False,
            qualified_person=False, direct_channel=False, needs_review=False,
            blockers=["manual_review_required"], expires_at=None)
    rows = relevant_observations(observations, review.person_id, review.contact_id)
    ids = {row.id for row in rows}
    context_current = review.context_current and ids == set(review.observation_ids) and not review.redacted
    if not context_current:
        blockers.append("review_context_changed")
    conflicted = any(row.stance == "refutes" for row in rows)
    unresolved = conflicted and not (review.conflict_resolution or "").strip()
    if unresolved:
        blockers.append("source_conflict_unresolved")
    base = context_current and not unresolved and review.created_at <= now
    expiries = []

    def supported(claim, days):
        candidates = [row for row in rows if row.claim == claim and row.stance == "supports"]
        valid = [row for row in candidates if not row.redacted and row.availability == "available"
                 and row.checked_at <= now < row.checked_at + timedelta(days=days)
                 and row.sources]
        if valid:
            expiries.extend(row.checked_at + timedelta(days=days) for row in valid)
        if candidates and not valid:
            blockers.append(f"{claim}_expired_or_unavailable")
        return valid

    employment = supported("employment", 30)
    procurement = supported("procurement_scope", 30)
    channel = supported("channel_ownership", 7)
    role_review_current = review.created_at <= now < review.created_at + timedelta(days=30)
    channel_review_current = review.created_at <= now < review.created_at + timedelta(days=7)
    official_role = any(source.source_kind == "official" for row in employment + procurement for source in row.sources)
    employment_ok = bool(base and role_review_current and review.employment == "accepted" and employment)
    procurement_ok = bool(base and role_review_current and review.procurement_scope == "accepted" and procurement)
    person_ok = employment_ok and procurement_ok and official_role
    channel_ok = bool(base and channel_review_current and review.channel_ownership == "accepted"
                      and channel and any(source.source_kind == "official" for row in channel for source in row.sources))
    direct = False
    for row in channel:
        point = row.channel or {}
        value = point.get("value", "")
        local = value.split("@", 1)[0].casefold() if "@" in value else ""
        if (point.get("type") in {"business_email", "business_phone"}
                and point.get("person_id") == str(review.person_id)
                and local not in SHARED_MAILBOXES):
            direct = True
    if not employment_ok:
        blockers.append("employment_not_confirmed")
    if not procurement_ok:
        blockers.append("procurement_not_confirmed")
    if not official_role:
        blockers.append("official_role_source_required")
    if review.contact_id and (not channel_ok or not direct):
        blockers.append("direct_person_channel_not_confirmed")
    expiries.append(review.created_at + timedelta(days=7 if review.contact_id else 30))
    return LeadQuality(
        employment_current=employment_ok, procurement_current=procurement_ok,
        channel_ownership_current=channel_ok, qualified_person=person_ok,
        direct_channel=bool(person_ok and channel_ok and direct),
        needs_review=bool(not base or any("expired" in item for item in blockers)
                          or (review.employment == "accepted" and not role_review_current)
                          or (review.contact_id and review.channel_ownership == "accepted" and not channel_review_current)),
        blockers=list(dict.fromkeys(blockers)), expires_at=min(expiries) if expiries else None,
    )
