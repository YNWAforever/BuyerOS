import asyncio
import uuid

from buyeros_worker.run_emitter import emit_run_event

RUN_ID = "00000000-0000-4000-8000-0000000000aa"


def test_emit_without_a_session_is_a_noop():
    assert asyncio.run(emit_run_event(None, RUN_ID, "run.started")) == 0


def test_emit_without_a_run_id_is_a_noop():
    assert asyncio.run(emit_run_event(object(), None, "run.started")) == 0


def test_emit_accepts_uuid_or_string_run_ids():
    assert asyncio.run(emit_run_event(None, uuid.UUID(RUN_ID), "run.started")) == 0
