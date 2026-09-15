from datetime import datetime, timedelta, timezone

from buyeros_worker.dispatcher import select_ready

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_only_ready_rows_are_selected():
    rows = [
        {"id": 1, "state": "ready", "lease_expires_at": None},
        {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
        {"id": 3, "state": "ready", "lease_expires_at": NOW - timedelta(seconds=1)},
    ]
    assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]


def test_batch_is_bounded():
    rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
    assert len(select_ready(rows, NOW, limit=5)) == 5
