"""Bounded read-only discovery using a trusted server-resolved canonical actor."""
import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_authorized_workspaces(session: AsyncSession, *, user_id: uuid.UUID,
                                    offset: int, limit: int) -> dict:
    if (not isinstance(user_id, uuid.UUID) or type(offset) is not int or offset < 0
            or type(limit) is not int or not 1 <= limit <= 100):
        raise ValueError('canonical actor and bounded pagination required')
    await session.execute(text("SELECT set_config('app.user_id', :actor, true), "
                               "set_config('app.workspace_id', '', true)"), {'actor': str(user_id)})
    # PostgreSQL COUNT has a bigint bound. Larger public offsets must be an
    # empty page; avoid turning a valid empty pagination request into overflow.
    query_offset = min(offset, 9223372036854775807)
    page = (await session.execute(text(
        "SELECT public.buyeros_workspace_directory(CAST(:actor AS uuid), "
        "CAST(:offset AS bigint), CAST(:limit AS integer))"),
        {'actor': str(user_id), 'offset': query_offset, 'limit': limit})).scalar_one()
    page['offset'] = offset
    return page
