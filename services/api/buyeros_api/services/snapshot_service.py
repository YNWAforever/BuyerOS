"""Stable buyer selection snapshots (BO-008)."""

MAX_SELECTION_IDS = 1000
DEFAULT_TTL_SECONDS = 900


class TooManyIds(Exception):
    pass


def materialize_snapshot(
    ids_and_versions: list[tuple[str, int]],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    max_ids: int = MAX_SELECTION_IDS,
) -> list[tuple[int, str, int]]:
    if len(ids_and_versions) > max_ids:
        raise TooManyIds(f"selection exceeds {max_ids}")
    return [(ordinal, buyer_id, version) for ordinal, (buyer_id, version) in enumerate(ids_and_versions)]
