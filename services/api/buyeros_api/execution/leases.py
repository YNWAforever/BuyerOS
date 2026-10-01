from datetime import datetime, timedelta


def lease_expiry(now: datetime, seconds: int) -> datetime:
    return now + timedelta(seconds=seconds)


def can_claim(state: str, expires_at: datetime | None, now: datetime) -> bool:
    if state == "free" or expires_at is None:
        return True
    return expires_at <= now


def fence_ok(worker_generation: int, row_generation: int) -> bool:
    return worker_generation == row_generation
