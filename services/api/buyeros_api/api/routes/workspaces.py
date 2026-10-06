from fastapi import APIRouter, Depends, Query, Request

from ..auth import Principal, get_principal
from ..errors import envelope

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(get_principal),
) -> dict:
    from ...db.session import workspace_directory_session
    from ...services.identity_resolver import resolve_user_id
    from ...services.workspace_directory import list_authorized_workspaces
    from ..deps import get_engine

    async with workspace_directory_session(get_engine()) as session:
        user_id = await resolve_user_id(session, principal)
        page = ({'items': [], 'offset': offset, 'limit': limit, 'total': 0} if user_id is None
                else await list_authorized_workspaces(session, user_id=user_id, offset=offset, limit=limit))
    return envelope(page, request.state.request_id)
