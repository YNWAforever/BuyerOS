"""T11 outbox handler only resumes a persisted job id."""
import asyncio
import uuid

from buyeros_worker.registry import get_handler


def test_bulk_mutate_registered_and_calls_one_chunk(monkeypatch):
    import buyeros_api.services.bulk_service as bulk_service
    import buyeros_worker.handlers  # noqa: F401

    job_id = uuid.uuid4()
    seen = []

    async def fake_apply(session, selected_id):
        seen.append((session, selected_id))
        return {"job_id": str(selected_id), "processed": 50, "remaining": 51}

    monkeypatch.setattr(bulk_service, "apply_bulk_chunk", fake_apply)
    result = asyncio.run(get_handler("bulk.mutate")(object(), {}, {"job_id": str(job_id)}))
    assert result.state == "done"
    assert seen[0][1] == job_id


def test_bulk_mutate_rejects_untrusted_payload_without_db_work(monkeypatch):
    import buyeros_api.services.bulk_service as bulk_service
    import buyeros_worker.handlers  # noqa: F401

    async def forbidden(*args):
        raise AssertionError("invalid payload reached the database")

    monkeypatch.setattr(bulk_service, "apply_bulk_chunk", forbidden)
    for payload in ({}, {"job_id": "not-a-uuid"}, {"job_id": str(uuid.uuid4()), "buyer_ids": ["extra"]}):
        result = asyncio.run(get_handler("bulk.mutate")(object(), {}, payload))
        assert result.state == "blocked"
