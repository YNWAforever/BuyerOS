import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

import buyeros_worker.dispatcher as dispatcher
from buyeros_worker.dispatcher import claimable, dispatch_once, select_ready, sweep_once

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _wire(monkeypatch, rows, workspaces=("ws-1",)):
    async def fake_workspace_ids(engine):
        return list(workspaces)

    @asynccontextmanager
    async def fake_tenant_session(engine, workspace_id):
        yield object()

    calls = []

    async def fake_claim(session, owner, limit, now, lease_seconds, *, expired_only=False):
        calls.append(expired_only)
        return list(rows)

    released = []

    async def fake_release(session, intent_key):
        released.append(intent_key)

    monkeypatch.setattr(dispatcher, "_workspace_ids", fake_workspace_ids)
    monkeypatch.setattr(dispatcher, "tenant_session", fake_tenant_session)
    monkeypatch.setattr(dispatcher, "claim_outbox_rows", fake_claim)
    monkeypatch.setattr(dispatcher, "release_claim", fake_release)
    return calls, released


def _row(intent_key="job:aaa", generation=7, workspace_id="ws-1"):
    return {
        "id": 1,
        "workspace_id": workspace_id,
        "intent_key": intent_key,
        "event_type": "fetch.evidence",
        "payload": {"url": "https://e.com"},
        "fencing_generation": generation,
    }


def test_only_ready_and_expired_rows_are_selected():
    rows = [
        {"id": 1, "state": "ready", "lease_expires_at": None},
        {"id": 2, "state": "dispatched", "lease_expires_at": NOW + timedelta(seconds=60)},
        {"id": 3, "state": "dispatched", "lease_expires_at": NOW - timedelta(seconds=1)},
        {"id": 4, "state": "done", "lease_expires_at": None},
        {"id": 5, "state": "failed", "lease_expires_at": NOW - timedelta(days=1)},
    ]
    assert [r["id"] for r in select_ready(rows, NOW)] == [1, 3]


def test_batch_is_bounded():
    rows = [{"id": i, "state": "ready", "lease_expires_at": None} for i in range(20)]
    assert len(select_ready(rows, NOW, limit=5)) == 5


def test_terminal_rows_are_never_claimable():
    assert claimable("done", NOW - timedelta(days=1), NOW) is False
    assert claimable("failed", None, NOW) is False


def test_dispatch_once_publishes_only_opaque_ids(monkeypatch):
    calls, _ = _wire(monkeypatch, [_row()])
    messages = []
    out = asyncio.run(dispatch_once(object(), messages.append, "owner", NOW, 10, 120))
    assert out == ["job:aaa"]
    assert messages == [{"intent_key": "job:aaa", "workspace_id": "ws-1", "generation": 7}]
    assert calls == [False]


def test_publish_failure_releases_the_claim(monkeypatch):
    _, released = _wire(monkeypatch, [_row(generation=3)])

    def boom(message):
        raise RuntimeError("broker down")

    with pytest.raises(RuntimeError):
        asyncio.run(dispatch_once(object(), boom, "owner", NOW, 10, 120))
    assert released == ["job:aaa"]


def test_sweep_once_only_targets_expired_rows(monkeypatch):
    calls, _ = _wire(monkeypatch, [_row(generation=2)])
    messages = []
    out = asyncio.run(sweep_once(object(), messages.append, "sweeper", NOW, 10, 120))
    assert out == ["job:aaa"]
    assert calls == [True]
    assert messages[0] == {"intent_key": "job:aaa", "workspace_id": "ws-1", "generation": 2}


def test_dispatch_fans_out_over_every_workspace(monkeypatch):
    calls, _ = _wire(monkeypatch, [], workspaces=("ws-a", "ws-b", "ws-c"))
    asyncio.run(dispatch_once(object(), lambda message: None, "owner", NOW, 10, 120))
    assert calls == [False, False, False]
