"""Manual source observations. This module has no provider or network dependency."""
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.auth import Principal
from ..api.deps import load_membership, permission_for_roles
from ..api.errors import ApiError
from ..api.lead_schemas import LeadScope, LeadObservationInput, LeadObservationRecord
from ..db.buyers import ProjectBuyer
from ..db.icp import Project, canonical_hash
from ..db.ingestion import OfferDocument
from ..db.lead_workflow import LeadCaseState, LeadObservation, LeadPrivatePayload
from ..db.models import Membership
from ..db.policy import PolicyDecision
from ..db.runs import Person, ContactPoint
from .audit_service import append_audit
from .policy_service import evaluate_current_policy, policy_workspace_lock


async def resolve_lead_scope(
    session: AsyncSession, *, workspace_id: uuid.UUID, project_id: uuid.UUID,
    buyer_id: uuid.UUID | None, principal: Principal,
) -> LeadScope:
    member = await load_membership(session, principal=principal, workspace_id=workspace_id)
    project = await session.scalar(select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id))
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    buyer = None
    if buyer_id is not None:
        buyer = await session.scalar(select(ProjectBuyer).where(
            ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id, ProjectBuyer.id == buyer_id,
        ))
        if buyer is None:
            raise ApiError(404, "NOT_FOUND", "buyer not found")
    current_member = await session.scalar(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == member["user_id"], Membership.active.is_(True),
    ))
    if current_member is None:
        raise ApiError(404, "NOT_FOUND", "workspace not found")
    return LeadScope(workspace_id, project_id, buyer_id, buyer.company_id if buyer else None,
                     member["user_id"], current_member.version, frozenset(current_member.roles))


def require_permission(scope: LeadScope, operation: str) -> None:
    if not permission_for_roles(list(scope.roles), operation):
        raise ApiError(403, "PERMISSION_DENIED", "insufficient role")


async def personal_policy(session, scope: LeadScope, now: datetime, contact_id=None, *, required=True,
                          action="lead.evidence.read", sources=None, source_ids=(), observation_ids=None):
    try:
        receipt = await authorize_native_policy_use(
            session, scope, action=action, source_ids=tuple(source_ids), now=now,
            sources=sources, contact_id=contact_id, observation_ids=observation_ids)
        return receipt.deadline
    except ApiError:
        if required:
            raise
        return None


async def _native_source_context(session, scope, action, source_ids, sources, now, observation_ids=None):
    from urllib.parse import urlsplit
    from ..api.policy_activation_schemas import PolicyUseContext, MANUAL_DATA, exact_domain
    if sources is None:
        sources = []
        if scope.buyer_id is not None:
            query = select(LeadPrivatePayload.contents).join(
                LeadObservation, (LeadObservation.workspace_id == LeadPrivatePayload.workspace_id)
                & (LeadObservation.payload_id == LeadPrivatePayload.id)
            ).where(
                LeadObservation.workspace_id == scope.workspace_id,
                LeadObservation.project_id == scope.project_id,
                LeadObservation.buyer_id == scope.buyer_id,
                LeadPrivatePayload.retention_expires_at > now,
                LeadPrivatePayload.contents.is_not(None),
            )
            if observation_ids is not None:
                query = query.where(LeadObservation.id.in_(observation_ids))
            for body in (await session.scalars(query)).all():
                sources.extend(body.get("sources", []))
    domains = []
    for item in sources:
        source = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        parsed = urlsplit(source.get("url", ""))
        try:
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in {None, 443}):
                raise ValueError("exact HTTPS source required")
            domains.append(exact_domain(parsed.hostname))
        except ValueError:
            raise ApiError(403, "POLICY_BLOCKED", "source does not match supported manual scope") from None
    deadlines = []
    for identity in source_ids:
        document = await session.scalar(select(OfferDocument).where(
            OfferDocument.workspace_id == scope.workspace_id, OfferDocument.project_id == scope.project_id,
            OfferDocument.id == identity))
        if (not document or document.status != "ready" or document.deleted_at is not None
            or document.retention_until is None or document.retention_until <= now):
            raise ApiError(403, "POLICY_BLOCKED", "provided source is no longer retained")
        deadlines.append(document.retention_until)
    if observation_ids is not None:
        # Every cited observation must still exist with a retained payload; a
        # source-free longer-lived sibling may not keep an expired citation alive.
        requested = [uuid.UUID(str(value)) for value in observation_ids]
        if requested:
            query = select(LeadObservation.id, LeadPrivatePayload.retention_expires_at).join(
                LeadPrivatePayload, (LeadPrivatePayload.workspace_id == LeadObservation.workspace_id)
                & (LeadPrivatePayload.id == LeadObservation.payload_id)).where(
                LeadObservation.workspace_id == scope.workspace_id,
                LeadObservation.project_id == scope.project_id,
                LeadObservation.id.in_(requested),
                LeadPrivatePayload.retention_expires_at > now,
                LeadPrivatePayload.contents.is_not(None),
            )
            if scope.buyer_id is not None:
                query = query.where(LeadObservation.buyer_id == scope.buyer_id)
            rows = (await session.execute(query)).all()
            if {row[0] for row in rows} != set(requested):
                raise ApiError(403, "POLICY_BLOCKED", "a cited observation is no longer retained")
            deadlines.extend(row[1] for row in rows)
    return PolicyUseContext(action=action, project_id=scope.project_id, source_ids=tuple(source_ids),
                            source_domains=tuple(sorted(set(domains))), data_categories=MANUAL_DATA), deadlines


@dataclass(frozen=True)
class PolicyUseReceipt:
    deadline: datetime
    context_hash: str
    use_context: object


async def authorize_native_policy_use(session, scope: LeadScope, *, action: str,
                                       source_ids: tuple, now: datetime, sources=None,
                                       contact_id=None, observation_ids=None, purposes=None) -> PolicyUseReceipt:
    await policy_workspace_lock(session, scope.workspace_id)
    now = max(now, datetime.now(timezone.utc))
    context, deadlines = await _native_source_context(
        session, scope, action, source_ids, sources, now, observation_ids)
    subject = {"workspace_id": scope.workspace_id, "project_id": scope.project_id,
               "company_id": scope.company_id}
    if contact_id is not None:
        subject["contact_point_id"] = contact_id
    needed = purposes or ("account_research", "contact_research")
    for purpose in needed:
        gate = await evaluate_current_policy(session, subject, purpose, now, use_context=context)
        if not gate["allowed"]:
            raise ApiError(403, "POLICY_BLOCKED", "current source-bound manual purpose permission required")
    conditions = [((PolicyDecision.subject_type == "project") & (PolicyDecision.subject_id == scope.project_id))]
    if scope.company_id:
        conditions.append((PolicyDecision.subject_type == "company") & (PolicyDecision.subject_id == scope.company_id))
    if contact_id:
        conditions.append((PolicyDecision.subject_type == "contact_point") & (PolicyDecision.subject_id == contact_id))
    policies = list((await session.scalars(select(PolicyDecision).where(
        PolicyDecision.workspace_id == scope.workspace_id, PolicyDecision.controller_scope_id == scope.workspace_id,
        PolicyDecision.purpose.in_(needed), or_(*conditions),
    ).distinct(PolicyDecision.subject_type, PolicyDecision.subject_id, PolicyDecision.purpose)
      .order_by(PolicyDecision.subject_type, PolicyDecision.subject_id, PolicyDecision.purpose,
                PolicyDecision.version.desc(), PolicyDecision.created_at.desc(), PolicyDecision.id.desc()))).all())
    if not policies or any(row.retention_days <= 0 or row.expires_at <= now for row in policies):
        raise ApiError(403, "POLICY_BLOCKED", "a current retention period is required")
    deadline = min([now + timedelta(days=min(row.retention_days for row in policies))]
                   + [row.expires_at for row in policies] + deadlines)
    if deadline <= datetime.now(timezone.utc):
        raise ApiError(403, "POLICY_BLOCKED", "manual policy or source deadline elapsed")
    from ..db.policy_activation import PolicyActivationRequest, PolicyActivationResolution
    proof_rows = (await session.execute(select(
        PolicyActivationResolution.decision_id, PolicyActivationRequest.terms_hash,
        PolicyActivationRequest.authority_id, PolicyActivationRequest.authority_version,
    ).join(PolicyActivationRequest, (PolicyActivationRequest.workspace_id == PolicyActivationResolution.workspace_id)
           & (PolicyActivationRequest.id == PolicyActivationResolution.request_id)).where(
        PolicyActivationResolution.workspace_id == scope.workspace_id,
        PolicyActivationResolution.decision_id.in_([row.id for row in policies]),
    ))).all()
    proofs = {row.decision_id: {"terms_hash": row.terms_hash, "authority_id": str(row.authority_id),
                              "authority_version": row.authority_version} for row in proof_rows}
    fingerprint = canonical_hash([
        {"id": str(row.id), "version": row.version, "expires_at": row.expires_at.isoformat()}
        | proofs.get(row.id, {})
        for row in sorted(policies, key=lambda row: str(row.id))])
    return PolicyUseReceipt(deadline, fingerprint, context)


async def assert_active_project(session, scope):
    status = await session.scalar(select(Project.status).where(
        Project.workspace_id == scope.workspace_id, Project.id == scope.project_id,
    ))
    if status != "active":
        raise ApiError(409, "INVALID_STATE", "project is archived")


def normalized_channel(data):
    value = data.value.strip()
    if data.type == "business_email":
        return value.lower()
    if data.type == "business_phone":
        result = re.sub(r"[\s().-]", "", value)
        if not re.fullmatch(r"\+?[0-9]{7,15}", result):
            raise ApiError(422, "INVALID_REQUEST", "business phone format is invalid")
        return result
    return value


async def observation_subjects(session, scope, data, now, *, create=False, deadline=None):
    person, contact = None, None
    if data.person and data.person.person_id:
        person = await session.scalar(select(Person).where(
            Person.workspace_id == scope.workspace_id, Person.company_id == scope.company_id,
            Person.id == data.person.person_id,
        ))
        if person is None or person.retention_expires_at is None or person.retention_expires_at <= now:
            raise ApiError(404, "NOT_FOUND", "person not found")
    if data.channel:
        query = select(ContactPoint).where(
            ContactPoint.workspace_id == scope.workspace_id, ContactPoint.company_id == scope.company_id,
        )
        if data.channel.contact_id:
            query = query.where(ContactPoint.id == data.channel.contact_id)
        else:
            query = query.where(ContactPoint.type == data.channel.type,
                                ContactPoint.normalized_value == normalized_channel(data.channel))
        contact = await session.scalar(query)
        if data.channel.contact_id and contact is None:
            raise ApiError(404, "NOT_FOUND", "channel not found")
        requested_person = person.id if person else data.channel.person_id
        if data.channel.person_id and person and data.channel.person_id != person.id:
            raise ApiError(409, "INVALID_STATE", "channel person differs from observation")
        if data.channel.person_id and person is None:
            person = await session.scalar(select(Person).where(
                Person.workspace_id == scope.workspace_id, Person.company_id == scope.company_id,
                Person.id == data.channel.person_id,
            ))
            if person is None or person.retention_expires_at is None or person.retention_expires_at <= now:
                raise ApiError(404, "NOT_FOUND", "person not found")
        if contact is not None:
            if contact.person_id != requested_person:
                raise ApiError(409, "INVALID_STATE", "existing channel ownership cannot be reassigned")
            if contact.quarantined or contact.retention_expires_at is None or contact.retention_expires_at <= now:
                raise ApiError(403, "POLICY_BLOCKED", "channel is unavailable")
    if create and data.person and data.person.person_id is None:
        person = Person(workspace_id=scope.workspace_id, company_id=scope.company_id,
                        full_name=data.person.full_name, role=data.person.role, retention_expires_at=deadline)
        session.add(person)
        await session.flush()
    if create and data.channel and contact is None:
        contact = ContactPoint(workspace_id=scope.workspace_id, company_id=scope.company_id,
            person_id=person.id if person else None, type=data.channel.type,
            normalized_value=normalized_channel(data.channel), validity="unverified_public",
            checked_at=None, retention_expires_at=deadline, quarantined=False)
        session.add(contact)
        await session.flush()
    return person, contact


async def validate_observation(session, scope, data, now):
    require_permission(scope, "updateBuyer")
    await assert_active_project(session, scope)
    if scope.buyer_id is None or scope.company_id is None or data.checked_at > now:
        raise ApiError(422, "INVALID_REQUEST", "buyer and an actual observed timestamp are required")
    deadline = await personal_policy(session, scope, now, action="observation.append", sources=data.sources)
    person, contact = await observation_subjects(session, scope, data, now)
    if contact:
        deadline = await personal_policy(session, scope, now, contact.id,
                                         action="observation.append", sources=data.sources)
    if data.supersedes_id:
        previous = await session.scalar(select(LeadObservation).where(
            LeadObservation.workspace_id == scope.workspace_id, LeadObservation.project_id == scope.project_id,
            LeadObservation.buyer_id == scope.buyer_id, LeadObservation.id == data.supersedes_id,
        ))
        if previous is None:
            raise ApiError(404, "NOT_FOUND", "original observation not found")
        if (previous.claim != data.claim
                or (previous.person_id is not None and (person is None or previous.person_id != person.id))
                or (previous.contact_id is not None and (contact is None or previous.contact_id != contact.id))):
            raise ApiError(422, "INVALID_REQUEST", "correction must describe the same subject and claim")
    return deadline


async def lock_case(session, scope):
    buyer = await session.scalar(select(ProjectBuyer).where(
        ProjectBuyer.workspace_id == scope.workspace_id, ProjectBuyer.project_id == scope.project_id,
        ProjectBuyer.id == scope.buyer_id,
    ).with_for_update())
    if buyer is None or buyer.company_id != scope.company_id:
        raise ApiError(404, "NOT_FOUND", "buyer not found")
    case = await session.scalar(select(LeadCaseState).where(
        LeadCaseState.workspace_id == scope.workspace_id, LeadCaseState.project_id == scope.project_id,
        LeadCaseState.buyer_id == scope.buyer_id,
    ).with_for_update())
    if case is None:
        case = LeadCaseState(workspace_id=scope.workspace_id, project_id=scope.project_id,
                             buyer_id=scope.buyer_id, company_id=scope.company_id, version=1)
        session.add(case)
        await session.flush()
    return case


async def save_private_payload(session, scope, contents, deadline, person_id=None, contact_id=None):
    payload = LeadPrivatePayload(workspace_id=scope.workspace_id, project_id=scope.project_id,
        company_id=scope.company_id, person_id=person_id, contact_id=contact_id,
        contents=contents, content_hash=canonical_hash(contents), retention_expires_at=deadline)
    session.add(payload)
    await session.flush()
    return payload


async def retained_payload(session, scope, payload_id, now, *, cache=None):
    payload = cache["payloads"].get(payload_id) if cache is not None else await session.scalar(select(LeadPrivatePayload).where(
        LeadPrivatePayload.workspace_id == scope.workspace_id,
        LeadPrivatePayload.project_id == scope.project_id, LeadPrivatePayload.id == payload_id,
    ))
    if payload is None or payload.contents is None or payload.retention_expires_at <= now:
        return payload, None
    for document_id in payload.contents.get("offer_document_ids", []):
        document = await session.scalar(select(OfferDocument).where(
            OfferDocument.workspace_id == scope.workspace_id, OfferDocument.project_id == scope.project_id,
            OfferDocument.id == uuid.UUID(str(document_id)),
        ))
        if (document is None or document.status == "deleted" or document.deleted_at is not None
                or document.retention_until is None or document.retention_until <= now):
            return payload, None
    if payload.person_id:
        parent = cache["people"].get(payload.person_id) if cache is not None else None
        expiry = parent.retention_expires_at if parent else None
        if cache is None:
            expiry = await session.scalar(select(Person.retention_expires_at).where(
                Person.workspace_id == scope.workspace_id, Person.id == payload.person_id,
            ))
        if expiry is None or expiry <= now:
            return payload, None
    if payload.contact_id:
        contact = cache["contacts"].get(payload.contact_id) if cache is not None else await session.scalar(select(ContactPoint).where(
            ContactPoint.workspace_id == scope.workspace_id, ContactPoint.id == payload.contact_id,
        ))
        if contact is None or contact.quarantined or contact.retention_expires_at is None or contact.retention_expires_at <= now:
            return payload, None
    return payload, payload.contents


async def observation_data(session, scope, row, now, *, policy_allowed=None, cache=None):
    payload, content = await retained_payload(session, scope, row.payload_id, now, cache=cache)
    bound = await personal_policy(session, scope, now, row.contact_id, required=False,
                                   sources=(content or {}).get("sources", [])) is not None
    policy_allowed = bound and policy_allowed is not False
    availability = "available"
    if not policy_allowed:
        availability, content = "policy_blocked", None
    elif content is None:
        availability = "redacted" if payload and payload.redacted_at else "expired"
    person, contact = None, None
    if content and row.person_id:
        candidate = cache["people"].get(row.person_id) if cache is not None else await session.get(Person, row.person_id)
        if candidate and candidate.workspace_id == scope.workspace_id:
            person = {"id": str(candidate.id), "full_name": candidate.full_name, "role": candidate.role}
    if content and row.contact_id:
        candidate = cache["contacts"].get(row.contact_id) if cache is not None else await session.get(ContactPoint, row.contact_id)
        if candidate and candidate.workspace_id == scope.workspace_id:
            contact = {"id": str(candidate.id), "type": candidate.type,
                       "value": candidate.normalized_value, "validity": candidate.validity,
                       "checked_at": candidate.checked_at.isoformat() if candidate.checked_at else None,
                       "person_id": str(candidate.person_id) if candidate.person_id else None}
    data = content or {}
    return LeadObservationRecord(
        id=row.id, workspace_id=row.workspace_id, project_id=row.project_id,
        buyer_id=row.buyer_id, company_id=row.company_id, person_id=row.person_id, contact_id=row.contact_id,
        claim=row.claim, stance=row.stance, checked_at=row.checked_at, content_hash=row.content_hash,
        supersedes_id=row.supersedes_id, recorded_by_user_id=row.recorded_by_user_id, created_at=row.created_at,
        sources=data.get("sources", []), rationale=data.get("rationale"), limitations=data.get("limitations"),
        person=person, channel=contact, redacted=content is None, availability=availability,
    ).model_dump(mode="json")


async def append_observation(
    session: AsyncSession, *, scope: LeadScope, data: LeadObservationInput, now: datetime,
) -> dict:
    deadline = await validate_observation(session, scope, data, now)
    case = await lock_case(session, scope)
    person, contact = await observation_subjects(session, scope, data, now, create=True, deadline=deadline)
    body = data.model_dump(mode="json")
    payload = await save_private_payload(session, scope, body, deadline,
                                         person.id if person else None, contact.id if contact else None)
    row = LeadObservation(id=uuid.uuid4(), workspace_id=scope.workspace_id, project_id=scope.project_id,
        buyer_id=scope.buyer_id, company_id=scope.company_id, person_id=person.id if person else None,
        contact_id=contact.id if contact else None, claim=data.claim, stance=data.stance,
        checked_at=data.checked_at.astimezone(timezone.utc), content_hash=canonical_hash(body),
        payload_id=payload.id, supersedes_id=data.supersedes_id, recorded_by_user_id=scope.actor_id)
    session.add(row)
    case.version += 1
    append_audit(session, workspace_id=scope.workspace_id, actor_id=scope.actor_id,
                 action="lead.observation.recorded", entity_type="lead_observation", entity_id=row.id,
                 detail_digest=row.content_hash)
    await session.flush()
    return await observation_data(session, scope, row, now, policy_allowed=True)


async def list_observations(session, scope, *, offset, limit, now):
    require_permission(scope, "listBuyerEvidence")
    conditions = (LeadObservation.workspace_id == scope.workspace_id,
                  LeadObservation.project_id == scope.project_id, LeadObservation.buyer_id == scope.buyer_id)
    total = await session.scalar(select(func.count()).select_from(LeadObservation).where(*conditions))
    rows = list((await session.scalars(select(LeadObservation).where(*conditions)
        .order_by(LeadObservation.created_at, LeadObservation.id).offset(offset).limit(limit))).all())
    items = [await observation_data(session, scope, row, now) for row in rows]
    return {"items": items, "offset": offset, "limit": limit, "total": total, "reviews": []}
