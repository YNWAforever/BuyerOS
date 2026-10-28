"""Selected approved grounding; fixtures are test-only, live admission is separate."""
import re
from dataclasses import dataclass, field

from sqlalchemy import select

from ..api.errors import ApiError
from ..api.schemas import OfferFact
from ..db.icp import IcpVersion, Project, canonical_hash
from ..providers.model import ModelRoute
from .icp_service import effective_offer_facts
from .offer_document_refs import validate_offer_document_refs

ROUTE = ModelRoute(prompt_version="conversation-grounded.v1", permitted_tools=frozenset(),
                   max_input_tokens=6000, max_output_tokens=1000, deadline_seconds=30,
                   repair_limit=0)  # route_id=None: deliberately unselected, no live call.
UUID = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"


def unavailable_source():
    return ApiError(422, "CONVERSATION_SOURCE_UNAVAILABLE", "selected sources need review")


@dataclass(frozen=True)
class Grounding:
    citations: list[dict]
    excerpts: list[str]  # Request/receipt memory only; never local thread source bodies.
    sources: list[dict] = field(default_factory=list)
    profile_id: str = ""
    profile_hash: str = ""
    offer_revision: int = 0
    document_ids: list[str] = field(default_factory=list)
    paid_eligible: bool = False


async def resolve_sources(session, *, workspace_id, project_id, source_ids, readonly=False):
    if not 1 <= len(source_ids) <= 20 or len(set(source_ids)) != len(source_ids):
        raise unavailable_source()
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == project_id,
    ))).scalar_one_or_none()
    if project is None or project.status != "active":
        raise unavailable_source()
    profile = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.project_id == project_id,
        IcpVersion.id == project.active_icp_version_id,
    ))).scalar_one_or_none()
    if (profile is None or profile.approved_at is None or profile.approved_by is None
            or profile.superseded_at is not None or profile.basis_offer_revision != project.offer_revision
            or profile.content_hash != canonical_hash(profile.content)):
        raise unavailable_source()
    facts = effective_offer_facts(profile)
    fact_map = {str(row.get("id")): row for row in facts if row.get("approved") is True}
    citations, excerpts, sources, dependencies = [], [], [], set()
    paid_eligible = True
    for source_id in source_ids:
        document_match = re.fullmatch(rf"document:({UUID})", source_id)
        fact_match = re.fullmatch(rf"fact:profile:({UUID}):({UUID})", source_id)
        if fact_match and fact_match[1] == str(profile.id) and fact_match[2] in fact_map:
            selected = [fact_map[fact_match[2]]]
            locator = {"surface": "profile", "id": str(profile.id)}
            label = "Approved offer fact"
        elif document_match:
            # A selected document grants only its reviewer-approved excerpts, never the body
            # or extraction candidates. The profile's other facts stay outside this request.
            selected = [row for row in fact_map.values()
                        if row.get("source_document_id") == document_match[1]
                        and row.get("provenance") == "document_excerpt"]
            locator = {"surface": "document", "id": document_match[1]}
            label = "Offer document"
        else:
            # Candidate/document fact IDs, run summaries and results are not approved evidence.
            raise unavailable_source()
        if not selected or len(selected) > 20:
            raise unavailable_source()
        try:
            qualified = [OfferFact.model_validate(row) for row in selected]
            document_ids = sorted({row.source_document_id for row in qualified if row.source_document_id}, key=str)
            if any(str(value) not in profile.content.get("offer_document_ids", []) for value in document_ids):
                raise unavailable_source()
            await validate_offer_document_refs(session, workspace_id=workspace_id,
                project_id=project_id, document_ids=document_ids, facts=qualified, lock=not readonly)
        except (ApiError, ValueError, TypeError) as exc:
            raise unavailable_source() from exc
        paid_eligible = paid_eligible and all(fact.source_document_id is not None and fact.provenance == 'document_excerpt' for fact in qualified)
        dependencies.update(str(value) for value in document_ids)
        for fact in qualified:
            if not fact.value.strip() or len(fact.value) > 400:
                raise unavailable_source()
            # Excerpts must also be bounded. Source instructions never change ROUTE/tools.
            if fact.excerpt and len(fact.excerpt) > 800:
                raise unavailable_source()
            excerpts.append(fact.value)
        citation = {"id": source_id, "label": label, "locator": locator}
        citations.append(citation)
        sources.append({"citation": citation, "excerpts": [fact.value for fact in qualified]})
    if sum(len(value.encode("utf-8")) for value in excerpts) > 12000:
        raise unavailable_source()
    return Grounding(citations=citations, excerpts=excerpts, sources=sources, profile_id=str(profile.id),
        profile_hash=profile.content_hash, offer_revision=project.offer_revision, document_ids=sorted(dependencies), paid_eligible=paid_eligible)


def reply_from_grounding(grounding, *, fixture_candidate=None):
    """Fail closed until an atomic reservation/receipt operation exists for this use.

    Fixture output has the same strict citation/tool/refusal boundary as draft generation.
    It cannot be enabled through environment, headers or request fields.
    """
    if fixture_candidate is None:
        raise ApiError(503, "CONVERSATION_MODEL_UNAVAILABLE", "conversation model admission is unavailable")
    candidate = fixture_candidate
    refs = candidate.get("citations") if isinstance(candidate, dict) else None
    text = candidate.get("text") if isinstance(candidate, dict) else None
    if (not isinstance(candidate, dict) or set(candidate) != {"text", "citations", "status", "fixture"}
            or candidate["status"] != "needs_review" or candidate["fixture"] is not True
            or not isinstance(text, str) or not text.strip() or len(text) > 4000
            or not isinstance(refs, list) or not 1 <= len(refs) <= 20
            or any(ref not in grounding.citations for ref in refs)
            or len({ref["id"] for ref in refs}) != len(refs)):
        raise ApiError(422, "CONVERSATION_REPLY_UNVERIFIED", "reply requires review")
    return candidate
