"""Provider-agnostic search adapter and capability manifest (BO-013).

No provider is pinned or activated. Activation requires a verified capability
with bounded pricing; the concrete provider is resolved in BO-002.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    snippet: str = ""
    provider_ref: str = ""


@dataclass(frozen=True)
class SearchCapability:
    verified: bool
    supports_filters: set[str] = field(default_factory=set)
    max_results: int = 0
    bounded_price: bool = False


def is_activation_allowed(cap: SearchCapability) -> bool:
    return cap.verified and cap.bounded_price and cap.max_results > 0


class SearchAdapter(Protocol):
    async def search(self, query: str, market: str, language: str, limit: int) -> list[SearchResult]: ...


class FixtureSearchAdapter:
    """Deterministic adapter for tests; never a live provider."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    async def search(self, query: str, market: str, language: str, limit: int) -> list[SearchResult]:
        return [
            SearchResult(r["url"], r["title"], r.get("snippet", ""), r.get("ref", ""))
            for r in self._rows[:limit]
        ]
