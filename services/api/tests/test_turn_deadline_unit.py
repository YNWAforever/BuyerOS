"""Unit: bounded turn deadline arithmetic, placement and notice taxonomy."""
import uuid

import pytest
from pydantic import ValidationError

from buyeros_api.services.turn_deadline import (ELAPSED_BUCKET_OVER, MAX_SECONDS,
    MIN_SECONDS, TURN_DEADLINE_EXCEEDED, TurnDeadline, deadline_message,
    deadline_notice, validate_seconds)
from buyeros_api.settings import Settings


class FakeClock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def test_deadline_arithmetic_and_single_step_start():
    clock = FakeClock()
    deadline = TurnDeadline(seconds=5, clock=clock)
    assert not deadline.exceeded() and deadline.should_start()
    assert deadline.elapsed() == 0.0 and deadline.remaining() == 5.0
    started = []
    for step in ('first', 'second', 'third'):
        # Placement: the check happens before every step start.
        if not deadline.should_start():
            break
        started.append(step)
        clock.advance(5)  # this step consumed the whole bound
    assert started == ['first']  # no second step ever started
    assert deadline.exceeded()
    assert deadline.remaining() == 0.0
    assert deadline.elapsed_bucket == ELAPSED_BUCKET_OVER
    assert not deadline.should_start()


def test_deadline_notice_is_localized_and_leaks_no_ids():
    english = deadline_notice('en')
    chinese = deadline_notice('zh-HK')
    assert english.code == chinese.code == TURN_DEADLINE_EXCEEDED
    assert ELAPSED_BUCKET_OVER in english.message
    assert '時間上限' in chinese.message
    request_like = str(uuid.uuid4())
    for notice in (english, chinese):
        assert request_like not in notice.message
        assert 'req_' not in notice.message and 'provider' not in notice.message.lower()
    assert deadline_message('fr') == deadline_message('en')


def test_deadline_seconds_are_validated_as_integers_in_range():
    for value in (4, 0, -1, 91, 1000):
        with pytest.raises(ValueError):
            validate_seconds(value)
        with pytest.raises(ValidationError):
            Settings(turn_deadline_seconds=value)
    for value in (MIN_SECONDS, 60, MAX_SECONDS):
        assert validate_seconds(value) == value
        assert Settings(turn_deadline_seconds=value).turn_deadline_seconds == value
    with pytest.raises(ValueError):
        validate_seconds(5.0)
    # Environment values arrive as text; the reviewed field accepts the numeric
    # form and still rejects invalid/out-of-range text.
    assert Settings(turn_deadline_seconds='60').turn_deadline_seconds == 60
    for bad in ('abc', '4', '91', '60.5'):
        with pytest.raises(ValidationError):
            Settings(turn_deadline_seconds=bad)
    assert Settings().turn_deadline_seconds == 60
