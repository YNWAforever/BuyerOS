from collections.abc import Callable
from dataclasses import dataclass


class UnknownHandler(Exception):
    pass


@dataclass(frozen=True)
class HandlerResult:
    state: str          # "done" | "blocked" | "retry"
    detail: str = ""


HANDLERS: dict[str, Callable] = {}


def register(event_type: str):
    def decorator(func: Callable) -> Callable:
        HANDLERS[event_type] = func
        return func

    return decorator


def get_handler(event_type: str) -> Callable:
    try:
        return HANDLERS[event_type]
    except KeyError as exc:  # pragma: no cover - exercised via test
        raise UnknownHandler(event_type) from exc
