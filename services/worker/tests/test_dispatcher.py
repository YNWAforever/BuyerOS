from datetime import datetime, timedelta, timezone

from buyeros_worker.dispatcher import dispatch_once, select_ready, sweep_expired

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


def test_dispatch_once_publishes_persisted_intent_key():
    import asyncio

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

    class FakeRow:
        def __init__(self, mapping):
            self._mapping = mapping

    class FakeSession:
        def __init__(self, rows):
            self._rows = rows
            self.executed = []

        async def execute(self, statement, params=None):
            self.executed.append(params)
            return FakeResult([FakeRow(r) for r in self._rows])

    rows = [{"id": 1, "intent_key": "job:aaa", "event_type": "fetch.evidence", "payload": {"url": "https://e.com"}, "fencing_generation": 1}]
    published = []
    session = FakeSession(rows)
    out = asyncio.run(dispatch_once(session, lambda intent, row: published.append(intent), "worker-1", __import__("datetime").datetime.now(__import__("datetime").timezone.utc), 10))
    assert published == ["job:aaa"]
    assert out == ["job:aaa"]


def test_sweep_expired_returns_int_ids():
    assert sweep_expired.__annotations__["return"] == list[int]
