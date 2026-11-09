"""Bounded wall-clock deadline for one synchronous conversation turn.

The deadline is measured with an injectable ``clock`` (``time.monotonic`` by
default) so tests never sleep. A crossed deadline is a *persisted* outcome:
callers stop starting work, persist the parts they already produced, append a
terminal event in the same transaction, and return a failed turn with exactly
one ``TURN_DEADLINE_EXCEEDED`` notice. Nothing here creates provider work or
exposes request ids/provider text; the observability bucket is a constant.
"""
import time
from dataclasses import dataclass, field
from typing import Callable

from ..sales.turn_contracts import TurnNotice

TURN_DEADLINE_EXCEEDED = 'TURN_DEADLINE_EXCEEDED'
TURN_BUSY_RETRY = 'TURN_BUSY_RETRY'
MIN_SECONDS = 5
MAX_SECONDS = 90
DEFAULT_SECONDS = 60
# Coarse observability bucket only; never a request id, provider reference or payload.
ELAPSED_BUCKET_OVER = 'over_deadline'
ELAPSED_BUCKET_WITHIN = 'within_deadline'

_DEADLINE_MESSAGES = {
    'en': ('The turn exceeded its time limit and was stopped; completed work is '
           f'saved. Retry when ready. ({ELAPSED_BUCKET_OVER})'),
    'zh-HK': ('此回合已超過時間上限並停止；已完成的工作已儲存。請稍後再試。'
              f'（{ELAPSED_BUCKET_OVER}）'),
}


def validate_seconds(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError('turn deadline must be an integer number of seconds')
    if not MIN_SECONDS <= value <= MAX_SECONDS:
        raise ValueError(f'turn deadline must be between {MIN_SECONDS} and {MAX_SECONDS} seconds')
    return value


def deadline_message(language: str | None = 'en') -> str:
    return _DEADLINE_MESSAGES.get(language or 'en', _DEADLINE_MESSAGES['en'])


def deadline_notice(language: str | None = 'en') -> TurnNotice:
    return TurnNotice(code=TURN_DEADLINE_EXCEEDED, message=deadline_message(language))


@dataclass
class TurnDeadline:
    """One turn's bounded budget; all methods are read-only and idempotent."""

    seconds: int = DEFAULT_SECONDS
    clock: Callable[[], float] = time.monotonic
    started: float = field(init=False)

    def __post_init__(self):
        self.seconds = validate_seconds(self.seconds)
        self.started = self.clock()

    def elapsed(self) -> float:
        return max(0.0, self.clock() - self.started)

    def exceeded(self) -> bool:
        return self.elapsed() >= self.seconds

    def should_start(self) -> bool:
        """False means: do not start another step."""
        return not self.exceeded()

    def remaining(self) -> float:
        return max(0.0, self.seconds - self.elapsed())

    @property
    def elapsed_bucket(self) -> str:
        return ELAPSED_BUCKET_OVER if self.exceeded() else ELAPSED_BUCKET_WITHIN


def turn_deadline() -> TurnDeadline:
    from ..settings import get_settings
    return TurnDeadline(seconds=get_settings().turn_deadline_seconds)
