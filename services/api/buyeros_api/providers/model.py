"""Model route limits are code-owned; source text cannot grant tools or spend."""
from dataclasses import dataclass

from .base import ProviderAdapter, ProviderCapability, activation_blockers


@dataclass(frozen=True)
class ModelRoute:
    prompt_version: str
    permitted_tools: frozenset[str]
    max_input_tokens: int
    max_output_tokens: int
    deadline_seconds: int
    repair_limit: int
    route_id: str | None = None

    def __post_init__(self) -> None:
        if not self.prompt_version or self.permitted_tools:
            raise ValueError("model route requires a versioned prompt and no external tools")
        if not (1 <= self.max_input_tokens <= 20000 and 1 <= self.max_output_tokens <= 4000):
            raise ValueError("model token bounds required")
        if not (1 <= self.deadline_seconds <= 120 and 0 <= self.repair_limit <= 2):
            raise ValueError("model deadline and repair bounds required")


def model_activation_blockers(capability: ProviderCapability, route: ModelRoute,
                              *, market: str, language: str) -> tuple[str, ...]:
    blockers = list(activation_blockers(capability, market=market, language=language,
                                        role="company"))
    if capability.service != "model":
        blockers.append("WRONG_SERVICE")
    if route.route_id is None:
        blockers.append("MODEL_ROUTE_UNSELECTED")
    return tuple(blockers)


ModelAdapter = ProviderAdapter
