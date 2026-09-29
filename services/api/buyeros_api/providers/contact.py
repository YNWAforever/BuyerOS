"""Optional business-contact capability stays independently blocked until verified."""
from .base import ProviderAdapter, ProviderCapability, activation_blockers


def contact_activation_blockers(capability: ProviderCapability, *, market: str,
                                language: str, role: str,
                                environment: str = "production") -> tuple[str, ...]:
    blockers = list(activation_blockers(capability, market=market, language=language,
                                        role=role, environment=environment))
    if capability.service != "contact":
        blockers.append("WRONG_SERVICE")
    if capability.idempotency != "verified" and capability.status != "verified":
        if "NO_SAFE_RECONCILIATION" not in blockers:
            blockers.append("NO_SAFE_RECONCILIATION")
    return tuple(blockers)


ContactAdapter = ProviderAdapter
