import asyncio

from . import handlers  # noqa: F401  (import registers handlers)
from .app import celery_app
from .registry import get_handler


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


@celery_app.task(name="buyeros.execute_intent", acks_late=True)
def execute_intent(intent_key: str, event_type: str, payload: dict, generation: int) -> str:
    handler = get_handler(event_type)

    async def _run() -> str:
        from buyeros_api.db.session import tenant_session

        engine = _engine()
        async with tenant_session(engine, payload["workspace_id"]) as session:
            return await run_intent(handler, payload, session, context={"workspace_id": payload["workspace_id"]})

    return asyncio.run(_run())


def _engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    from buyeros_api.settings import get_settings

    return create_async_engine(get_settings().database_url)
