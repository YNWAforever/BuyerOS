"""Run only T11 bulk intents from the disposable browser fixture database.

This directly invokes the production run_intent transaction and handler. It deliberately
omits Valkey/Celery dispatch, so it is fixture integration evidence, never live queue proof.
"""
import asyncio
import subprocess
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from buyeros_api.db.outbox import OutboxEvent
from buyeros_api.db.session import tenant_session
from buyeros_worker.tasks import run_intent

WORKSPACE = "e0000000-0000-4000-8000-000000000001"
ROOT = Path(__file__).resolve().parents[3]
MARKER = ROOT / "test-results" / "e2e-db-container.txt"


def disposable_url() -> str:
    container = MARKER.read_text(encoding="utf-8").strip()
    if not container.startswith("buyeros-test-") or len(container) > 32:
        raise RuntimeError("not a disposable test container")
    result = subprocess.run(["docker", "port", container, "5432"], capture_output=True, text=True, check=True)
    port = result.stdout.strip().splitlines()[0].rsplit(":", 1)[1]
    if not port.isdigit():
        raise RuntimeError("invalid disposable database port")
    return f"postgresql+psycopg://buyeros_api:test-only@127.0.0.1:{port}/buyeros_test_api"


async def pump(make_one_stale: bool = False) -> int:
    engine = create_async_engine(disposable_url())
    completed = 0
    try:
        if make_one_stale:
            from uuid import UUID
            async with tenant_session(engine, UUID(WORKSPACE)) as session:
                await session.execute(text(
                    "UPDATE project_buyers SET version=version+1 "
                    "WHERE workspace_id=:workspace AND id='e2000000-0000-4000-8000-000000000001'"
                ), {"workspace": WORKSPACE})
        for _ in range(22):
            from uuid import UUID
            async with tenant_session(engine, UUID(WORKSPACE)) as session:
                row = (await session.execute(select(OutboxEvent).where(
                    OutboxEvent.workspace_id == UUID(WORKSPACE),
                    OutboxEvent.event_type == "bulk.mutate", OutboxEvent.state == "ready",
                ).order_by(OutboxEvent.created_at, OutboxEvent.id).limit(1).with_for_update())).scalar_one_or_none()
                if row is None:
                    break
                row.state = "dispatched"
                await session.flush()
                result = await run_intent(session, {}, row.intent_key, row.fencing_generation)
                if result != "done":
                    raise RuntimeError(f"bulk fixture intent did not complete: {result}")
                completed += 1
        else:
            raise RuntimeError("bulk fixture exceeded 22 chunks")
    finally:
        await engine.dispose()
    return completed


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        completed = asyncio.run(pump("--make-one-stale" in sys.argv), loop_factory=asyncio.SelectorEventLoop)
    else:
        completed = asyncio.run(pump("--make-one-stale" in sys.argv))
    print(f"Committed {completed} disposable bulk chunks through run_intent")
