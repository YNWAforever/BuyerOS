import asyncio
from threading import Lock

from . import handlers  # noqa: F401  (import registers handlers)
from .app import celery_app
from .registry import get_handler

_engine_lock = Lock()
_engine = None


def get_engine():
    """One process-wide async engine; disposing happens at worker shutdown."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from sqlalchemy.ext.asyncio import create_async_engine

                from buyeros_api.settings import get_settings

                _engine = create_async_engine(get_settings().database_url)
    return _engine


def dispose_engine() -> None:
    global _engine
    _engine = None


async def run_intent(handler, payload, session, context) -> str:
    """Execute one handler inside the tenant session and commit before ack.

    The caller passes a session already scoped with the transaction-local
    tenant context; nothing is committed if the handler raises.
    """
    result = handler(session, context, payload)
    if asyncio.iscoroutine(result):
        result = await result
    await session.commit()
    return result.state


def resolve_handler_state(event_type: str) -> str:
    from .registry import UnknownHandler, get_handler

    try:
        get_handler(event_type)
    except UnknownHandler:
        return "unknown_handler"
    return "known"


@celery_app.task(name="buyeros.execute_intent", acks_late=True, bind=True)
def execute_intent(self, intent_key: str, event_type: str, payload: dict, generation: int) -> str:
    if resolve_handler_state(event_type) == "unknown_handler":
        return "unknown_handler"
    handler = get_handler(event_type)

    async def _run() -> str:
        from buyeros_api.db.session import tenant_session

        engine = get_engine()
        async with tenant_session(engine, payload["workspace_id"]) as session:
            return await run_intent(handler, payload, session, context={"workspace_id": payload["workspace_id"]})

    result_state = asyncio.run(_run())
    if result_state == "retry":
        raise self.retry(countdown=30, max_retries=3)
    return result_state
