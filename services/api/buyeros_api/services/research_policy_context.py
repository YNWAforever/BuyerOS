"""Canonical contexts for existing research; no selection, activation or I/O."""
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select

from ..api.policy_activation_schemas import PolicyUseContext, ResearchProviderBinding, MANUAL_DATA, exact_domain
from ..db.buyers import Evidence, SourceDocument
from pydantic import ValidationError


def selected_binding(capability):
    """Read only private reviewed metadata; never construct an adapter."""
    from ..providers import registry
    item = registry.DEFAULT_REGISTRY.registration(capability.service)
    return item.policy_binding if item is not None and item.capability == capability else None


def metadata_binding(metadata, *, historical=False):
    """Only for server-owned selection/snapshots, never an HTTP request field."""
    raw = metadata.get("policy_binding")
    try:
        binding = raw if isinstance(raw, ResearchProviderBinding) else ResearchProviderBinding.model_validate(raw)
    except (ValidationError, TypeError):
        return None
    if binding.provider_name != metadata.get("provider"):
        return None
    frozen_hash=metadata.get("registry_contract_hash")
    # An original receipt may outlive the new-call registry field. Its typed
    # frozen binding must still match current approved terms. A conflicting
    # present hash stays refused; new work uses the strict default.
    if (metadata.get("provider") != "fixture" and binding.contract_sha256 != frozen_hash
        and not (historical and frozen_hash is None)):
        return None
    return binding


def adapter_binding(adapter):
    binding = getattr(adapter, "policy_binding", None)
    if isinstance(binding, ResearchProviderBinding):
        return binding
    capability = getattr(adapter, "capability", None)
    return selected_binding(capability) if capability is not None else None


def research_use(project_id, action, *, binding=None, urls=()):
    domains = set()
    for value in urls:
        try:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or parsed.username is not None:
                raise ValueError("public source URL required")
            domains.add(exact_domain(parsed.hostname))
        except (ValueError, TypeError, AttributeError):
            domains = {"<invalid-source>"}
            break
    scope = binding.model_dump() if isinstance(binding, ResearchProviderBinding) else {}
    return PolicyUseContext(project_id=UUID(str(project_id)), action=action,
                            source_domains=tuple(sorted(domains)), data_categories=MANUAL_DATA, **scope)


async def evidence_urls(session, *, project_id, evidence_ids=(), source_ids=(), run_id=None, company_id=None):
    """Resolve retained identities through RLS, never trust HTTP URL assertions."""
    project_id = UUID(str(project_id))
    if evidence_ids:
        ids = {UUID(str(value)) for value in evidence_ids}
        rows = (await session.execute(select(Evidence.id, SourceDocument.canonical_url).join(
            SourceDocument, (SourceDocument.workspace_id == Evidence.workspace_id)
            & (SourceDocument.id == Evidence.source_document_id)).where(
            Evidence.project_id == project_id, SourceDocument.project_id == project_id, Evidence.id.in_(ids)))).all()
        return [url for _, url in rows] if {item for item, _ in rows} == ids else ["<missing-source>"]
    statement = select(SourceDocument.id, SourceDocument.canonical_url).where(SourceDocument.project_id == project_id)
    if source_ids:
        ids = {UUID(str(value)) for value in source_ids}
        statement = statement.where(SourceDocument.id.in_(ids))
    elif run_id is not None:
        ids = None
        statement = statement.where(SourceDocument.run_id == run_id)
        if company_id is not None:
            statement = statement.join(Evidence, (Evidence.workspace_id == SourceDocument.workspace_id)
                & (Evidence.source_document_id == SourceDocument.id)).where(Evidence.company_id == company_id)
    else:
        return []
    rows = (await session.execute(statement)).all()
    if ids is not None and {item for item, _ in rows} != ids:
        return ["<missing-source>"]
    return [url for _, url in rows]
