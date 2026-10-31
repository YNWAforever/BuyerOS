"""Current Drive authorization checks. No metadata/content cache."""
import os
import re
import asyncio
from sqlalchemy import select
from ..api.errors import ApiError
from ..db.conversation_connections import DriveConnection
from . import drive_mcp

SOURCE = re.compile(r'^drive:([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}):(' + drive_mcp.ID + r')$')
SOURCE_DEADLINE_SECONDS = 20


def unavailable_source():
    return ApiError(422, 'CONVERSATION_SOURCE_UNAVAILABLE', 'selected sources need review')


async def load(session, workspace_id, project_id, *, lock=False):
    query = select(DriveConnection).where(DriveConnection.workspace_id == workspace_id,
                                         DriveConnection.project_id == project_id)
    if lock:
        query = query.with_for_update()
    else:
        query = query.with_for_update(read=True)
    return (await session.execute(query)).scalar_one_or_none()


async def approved_sources(session, workspace_id, project_id, source_ids, *, content=False):
    try:
        async with asyncio.timeout(SOURCE_DEADLINE_SECONDS):
            return await _approved_sources(session, workspace_id, project_id, source_ids, content=content)
    except TimeoutError:
        raise drive_mcp.unavailable() from None


async def _approved_sources(session, workspace_id, project_id, source_ids, *, content=False):
    if os.environ.get('NEXT_PUBLIC_CONVERSATION_HOME') != 'true':
        raise unavailable_source()
    row = await load(session, workspace_id, project_id)
    if row is None or not row.connected or not row.folders:
        raise unavailable_source()
    matches = [SOURCE.fullmatch(value) for value in source_ids]
    if any(match is None or match[1] != str(row.generation) for match in matches):
        raise unavailable_source()
    gateway = drive_mcp.adapter()
    folders = [folder['id'] for folder in row.folders]
    # Re-resolve direct parent/access on every selection and every Ask, even replay.
    available = {item['id'] for item in await gateway.items(workspace_id, project_id, folders)}
    if any(match[2] not in available for match in matches):
        raise unavailable_source()
    result = []
    for ident, match in zip(source_ids, matches):
        citation = {'id': ident, 'label': 'Google Drive item', 'locator': {'surface': 'drive', 'id': ident}}
        excerpts = [await gateway.read(workspace_id, project_id, folders, match[2])] if content else []
        result.append({'citation': citation, 'excerpts': excerpts})
    if sum(len(text.encode('utf-8')) for item in result for text in item['excerpts']) > 12000:
        raise unavailable_source()
    return result
