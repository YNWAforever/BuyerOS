from datetime import datetime, timedelta, timezone

from buyeros_worker.leases import can_claim, fence_ok, lease_expiry

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_free_lease_can_be_claimed():
    assert can_claim("free", None, NOW) is True


def test_unexpired_lease_cannot_be_claimed():
    assert can_claim("held", NOW + timedelta(seconds=30), NOW) is False


def test_expired_lease_can_be_claimed():
    assert can_claim("held", NOW - timedelta(seconds=1), NOW) is True


def test_lease_expiry_adds_seconds():
    assert lease_expiry(NOW, 120) == NOW + timedelta(seconds=120)


def test_fence_rejects_stale_worker():
    assert fence_ok(3, 3) is True
    assert fence_ok(2, 3) is False
