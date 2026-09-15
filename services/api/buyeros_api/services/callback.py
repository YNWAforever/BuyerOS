"""Provider callback replay detection (BO-020)."""


def event_key(provider: str, account: str, event_id: str) -> str:
    return f"{provider}:{account}:{event_id}"


def is_replay(seen_keys: set[str], key: str, digest: str) -> bool:
    return key in seen_keys


def digest_conflict(seen: dict[str, str], key: str, digest: str) -> bool:
    return key in seen and seen[key] != digest
