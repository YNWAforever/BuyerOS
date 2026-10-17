"""Pure manual-policy matching. Does not fetch sources or create authority."""
from datetime import datetime

from ..api.policy_activation_schemas import PolicyTerms, PolicyUseContext, exact_domain
from ..db.icp import canonical_hash


def validate_manual_scope(terms: PolicyTerms) -> None:
    PolicyTerms.model_validate(terms.model_dump(mode="json"))


def canonicalize_terms(terms: PolicyTerms) -> tuple[PolicyTerms, str]:
    checked = PolicyTerms.model_validate(terms.model_dump(mode="json"))
    # The existing helper includes its algorithm label; this closed wire schema
    # carries the SHA-256 algorithm in the field name and accepts 64 hex digits.
    return checked, canonical_hash(checked.model_dump(mode="json")).removeprefix("sha256:")


def match_policy_use(terms: PolicyTerms, use: PolicyUseContext, now: datetime) -> bool:
    if now.tzinfo is None or not terms.valid_from <= now < terms.expires_at:
        return False
    if use.project_id != terms.project_id or use.action not in terms.allowed_actions:
        return False
    if not use.data_categories <= set(terms.allowed_data_categories):
        return False
    if terms.template_version == "provider-research.v1":
        scope = terms.research_scope
        if scope is None:
            return False
        if use.action in {"research.search", "research.model"}:
            binding = scope.search if use.action == "research.search" else scope.model
            if (binding is None or use.provider_name != binding.provider_name
                or use.account_reference != binding.account_reference
                or use.contract_sha256 != binding.contract_sha256):
                return False
            # Search admission precedes result URLs. This only authorizes the
            # exact selected provider call; later read/persist must match sources.
            if use.action == "research.search" and not use.source_ids and not use.source_domains:
                return True
    if terms.template_version == "provider-native.v1":
        scope = terms.provider_scope
        if scope is None:
            return False
        if use.action in {"contact.enrich", "delivery.send"} and (
            use.provider_name != scope.provider_name or use.account_reference != scope.account_reference
            or use.contract_sha256 != scope.contract_sha256
        ):
            return False
        if use.action == "contact.read" and use.recipient_ref not in scope.recipient_refs:
            return False
        if use.action in {"draft.generate", "delivery.review", "delivery.send"}:
            if use.sender_identity_id != scope.sender_identity_id:
                return False
            if use.recipient_ref not in scope.recipient_refs:
                if not (use.action == "draft.generate" and use.recipient_ref is None and scope.allow_unaddressed_drafts):
                    return False
    if not use.source_ids and not use.source_domains:
        return False
    if not set(use.source_ids) <= set(terms.allowed_sources.document_ids):
        return False
    try:
        domains = {exact_domain(domain) for domain in use.source_domains}
    except ValueError:
        return False
    return domains <= set(terms.allowed_sources.domains)
