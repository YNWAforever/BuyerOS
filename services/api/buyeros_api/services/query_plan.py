"""Bounded multilingual query plan validation (BO-013)."""

from dataclasses import dataclass
import hashlib
import json
import re

MAX_QUERIES_PER_RUN = 12
SUPPORTED_DIALECTS = ("de", "nl", "fr", "en")


class UnsupportedDialect(Exception):
    pass


class TooManyQueries(Exception):
    pass


@dataclass
class QueryPlan:
    queries: list[dict]
    rationale_summary: str


def validate_plan(
    plan: dict, *, max_queries: int = MAX_QUERIES_PER_RUN, dialects=SUPPORTED_DIALECTS
) -> QueryPlan:
    queries = plan.get("queries") or []
    if len(queries) > max_queries:
        raise TooManyQueries(f"plan exceeds {max_queries} queries")
    for query in queries:
        if query.get("language") not in dialects:
            raise UnsupportedDialect(query.get("language"))
    return QueryPlan(queries=queries, rationale_summary=plan.get("rationale_summary", ""))


_ROLE_TERMS = {
    "distributor": {"de": "Händler", "nl": "distributeur", "fr": "distributeur", "en": "distributor"},
    "importer": {"de": "Importeur", "nl": "importeur", "fr": "importateur", "en": "importer"},
    "wholesaler": {"de": "Großhändler", "nl": "groothandel", "fr": "grossiste", "en": "wholesaler"},
    "manufacturer": {"de": "Hersteller", "nl": "fabrikant", "fr": "fabricant", "en": "manufacturer"},
    "retailer": {"de": "Einzelhändler", "nl": "detailhandel", "fr": "détaillant", "en": "retailer"},
}


def _limit(value, label: str, maximum: int, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"invalid {label}")
    return value


def _terms(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("requirement text required")
    # The planner is deterministic: source text is never evaluated as a prompt.
    # Keep the first search phrase and discard later instruction-like clauses.
    first = re.split(r"[.;\r\n]", value, maxsplit=1)[0]
    words = " ".join(re.findall(r"[\w-]+", first, flags=re.UNICODE))
    if not 2 <= len(words) <= 160:
        raise ValueError("requirement phrase is outside query bounds")
    return words


def build_query_plan(icp: dict, capabilities: dict, remaining_limits: dict) -> dict:
    """Create query-plan.v1 from approved ICP terms and verified filter scope.

    This pure function cannot activate a provider or spend. The caller must
    bind `capabilities` to a verified adapter before dispatch.
    """
    if not all(isinstance(value, dict) for value in (icp, capabilities, remaining_limits)):
        raise ValueError("ICP, capabilities and remaining limits required")
    if capabilities.get("service") != "search" or not capabilities.get("provider"):
        raise ValueError("search capability required")
    verified_filters = set(capabilities.get("verified_filters") or [])
    if not {"market", "language"}.issubset(verified_filters):
        raise ValueError("market and language filter capability must be verified")
    markets = icp.get("markets")
    languages = icp.get("languages")
    roles = icp.get("buyer_types")
    requirements = icp.get("requirements")
    if (not isinstance(markets, list) or not markets or not isinstance(languages, list)
            or not languages or not isinstance(roles, list) or not roles
            or not isinstance(requirements, list) or not requirements):
        raise ValueError("approved ICP markets, languages, roles and requirements required")
    allowed_markets = set(capabilities.get("markets") or [])
    allowed_languages = set(capabilities.get("languages") or [])
    allowed_roles = set(capabilities.get("roles") or [])
    if any(not isinstance(m, str) or m not in allowed_markets for m in markets):
        raise ValueError("unsupported market")
    if any(not isinstance(language, str) or language not in allowed_languages for language in languages):
        raise UnsupportedDialect("unsupported language")
    if any(not isinstance(role, str) or role not in allowed_roles for role in roles):
        raise ValueError("unsupported buyer role")
    rounds = _limit(remaining_limits.get("query_rounds", 3), "query rounds", 3)
    total = _limit(remaining_limits.get("max_queries_per_run", 12), "total query cap", 12)
    remaining = _limit(remaining_limits.get("remaining_queries", total),
                       "remaining queries", 12, minimum=0)
    if remaining == 0:
        raise TooManyQueries("no search queries remain in this logical run")
    limit = min(total, remaining)
    market_languages = capabilities.get("market_languages")
    if not isinstance(market_languages, dict):
        raise ValueError("verified market-language pairs required")
    per_market = {}
    for market in markets:
        supported = market_languages.get(market)
        if not isinstance(supported, (list, tuple)):
            raise ValueError("unsupported market-language pair")
        matched = [language for language in supported if language in languages]
        if not matched:
            raise UnsupportedDialect(f"no supported dialect for {market}")
        per_market[market] = matched
    requirement = next((item for item in requirements if isinstance(item, dict)
                        and item.get("category") == "must" and item.get("id") and item.get("text")), None)
    if requirement is None:
        raise ValueError("approved must requirement required")
    phrase = _terms(requirement["text"])
    role = roles[0]
    pairs = []
    for index in range(max(len(values) for values in per_market.values())):
        for market in markets:
            if index < len(per_market[market]):
                pairs.append((market, per_market[market][index]))
    queries = []
    for market, language in pairs[:limit]:
        role_term = _ROLE_TERMS.get(role, {}).get(language, role)
        query_text = f'"{phrase}" {role_term}'
        if len(query_text) > 256:
            raise ValueError("query text exceeds bound")
        identity = {"market": market, "language": language, "role": role,
                    "requirement_id": str(requirement["id"]), "query": query_text}
        query_id = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
        queries.append({"id": query_id, **identity, "round": 1,
                        "filters": {"market": market, "language": language}})
    return {"schema": "query-plan.v1", "queries": queries,
            "rationale_summary": f"Deterministic first round; {len(queries)}/{limit} remaining query slots; {rounds} round ceiling."}
