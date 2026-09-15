"""Reversible company canonicalization (BO-014).

A domain is an identity *hint*. Automatic merge is allowed only when registry
identifiers match exactly; shared domains and fuzzy matches go to human review.
"""


def registrable_hint(url_or_host: str) -> str:
    host = url_or_host.split("://")[-1].split("/")[0].lower()
    return host[4:] if host.startswith("www.") else host


def canonical_key(url: str) -> str:
    return registrable_hint(url)


def is_auto_merge_allowed(a: dict, b: dict) -> bool:
    registry_a = a.get("registry_id")
    registry_b = b.get("registry_id")
    return bool(registry_a) and registry_a == registry_b
