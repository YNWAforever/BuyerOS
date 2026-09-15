"""Usage projections and manual outcome chains (BO-024)."""

from decimal import ROUND_HALF_UP, Decimal


def safe_ratio(numerator: str, denominator: int) -> str | None:
    """Zero denominator returns None (rendered as an em dash), never 0."""
    if denominator == 0:
        return None
    value = (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return f"{value:.6f}"


def outcome_chain(events: list[dict]) -> dict:
    """Latest non-superseded manual stage per buyer."""
    latest: dict[str, str] = {}
    for event in events:
        if not event.get("superseded", False):
            latest[event["buyer_id"]] = event["stage"]
    return latest
