"""Server-owned canonical use context; never deserialize an authority from HTTP."""
from datetime import datetime, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..api.policy_activation_schemas import PolicyUseContext, MANUAL_DATA
from ..db.buyers import Company, ProjectBuyer
from ..db.drafts import OutreachDraft


async def company_context(session, *, project_id, company_id, action, **scope):
    domain = await session.scalar(select(Company.domain).where(Company.id == company_id))
    return PolicyUseContext(action=action, project_id=project_id,
                            source_domains=(domain,) if domain else (), data_categories=MANUAL_DATA, **scope)


async def contact_context(session, *, project_id, company_id, capability, configuration=None, environment="production"):
    # A non-selected capability alone is not a provider account. Existing test
    # execution may explicitly bind a synthetic account; production never does.
    account, contract = None, None
    if configuration is not None:
        account = configuration["account_reference"]
        contract = configuration["registry_contract_hash"]
    elif environment == "test":
        from ..providers.registry import ProviderRegistration
        account, contract = "fixture-test", ProviderRegistration(capability, lambda: None).contract_hash
    return await company_context(session, project_id=project_id, company_id=company_id,
        action="contact.enrich", provider_name=capability.provider, account_reference=account,
        contract_sha256=contract)


async def addressed_context(session, *, project_id, company_id, sender_id, recipient_id, action="draft.generate"):
    return await company_context(session, project_id=project_id, company_id=company_id,
        action=action, sender_identity_id=sender_id, recipient_ref=recipient_id)


async def validate_provider_resources(session, terms, now):
    """Resolve addressed identities at application and approval, within RLS."""
    if terms.template_version != "provider-native.v1":
        return
    from ..db.icp import Project
    from ..db.drafts import SenderIdentityVersion
    from ..db.runs import ContactPoint
    scope = terms.provider_scope
    sender = True if terms.purpose == "contact_research" else await session.scalar(select(SenderIdentityVersion.id).join(
        Project, (Project.active_sender_identity_version_id == SenderIdentityVersion.id)
        & (Project.workspace_id == SenderIdentityVersion.workspace_id)).where(
        Project.workspace_id == terms.workspace_id, Project.id == terms.project_id,
        SenderIdentityVersion.project_id == terms.project_id, SenderIdentityVersion.id == scope.sender_identity_id,
        SenderIdentityVersion.retired.is_(False), SenderIdentityVersion.reviewed_at.is_not(None)))
    recipients = set(await session.scalars(select(ContactPoint.id).join(
        ProjectBuyer, (ProjectBuyer.company_id == ContactPoint.company_id)
        & (ProjectBuyer.workspace_id == ContactPoint.workspace_id)).where(
        ProjectBuyer.workspace_id == terms.workspace_id, ProjectBuyer.project_id == terms.project_id,
        ContactPoint.id.in_(scope.recipient_refs), ContactPoint.type == "business_email",
        ContactPoint.quarantined.is_(False), ContactPoint.validity == "provider_marked_valid",
        ContactPoint.checked_at.is_not(None), ContactPoint.retention_expires_at > now)))
    if sender is None or recipients != set(scope.recipient_refs):
        raise ApiError(404, "NOT_FOUND", "current addressed policy resources unavailable")


async def require_delivery_policy(session, *, prepared, authorization, project_id, draft_id):
    from .policy_service import evaluate_current_policy
    company_id = await session.scalar(select(ProjectBuyer.company_id).join(
        OutreachDraft, (OutreachDraft.buyer_id == ProjectBuyer.id)
        & (OutreachDraft.workspace_id == ProjectBuyer.workspace_id)).where(
        OutreachDraft.id == draft_id, OutreachDraft.project_id == project_id))
    context = await company_context(session, project_id=project_id, company_id=company_id,
        action="delivery.send", sender_identity_id=prepared.intent.sender_identity_id,
        recipient_ref=prepared.intent.recipient_ref, provider_name=authorization.provider_name,
        account_reference=authorization.account_reference, contract_sha256=authorization.reviewed_contract_hash)
    gate = await evaluate_current_policy(session, {
        "workspace_id": prepared.intent.workspace_id, "project_id": project_id,
        "company_id": company_id, "contact_point_id": prepared.intent.recipient_ref,
    }, "outreach", datetime.now(timezone.utc), use_context=context)
    if not gate["allowed"]:
        raise ApiError(403, "POLICY_BLOCKED", "exact current provider send policy required")
