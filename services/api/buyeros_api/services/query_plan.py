"""Bounded multilingual query plan validation (BO-013)."""

from dataclasses import dataclass

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
