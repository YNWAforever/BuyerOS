"""Durable run event ordering (BO-016)."""


def next_sequence(last_sequence: int) -> int:
    return last_sequence + 1


def apply_event(applied: int, incoming: int) -> bool:
    """True only for a strictly newer sequence; duplicates/out-of-order ignored."""
    return incoming > applied
