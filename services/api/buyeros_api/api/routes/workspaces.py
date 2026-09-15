from fastapi import APIRouter, Depends, Request

from ..auth import Principal, get_principal
from ..errors import envelope

router = APIRouter(prefix="/v1/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(request: Request, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select, text

    from ...db.models import Membership, User, Workspace
    from ..deps import get_engine

    items: list[dict] = []
    async with get_engine().connect() as conn:
        # `users` is not RLS-protected: resolve the actor by immutable (issuer, subject).
        user = (
            await conn.execute(select(User).where(User.issuer == principal.issuer, User.subject == principal.subject))
        ).scalar_one_or_none()
        if user is not None:
            # `workspaces` is not RLS-protected either; enumerate candidates, then read the
            # membership only under that workspace's transaction-local tenant context.
            candidates = (await conn.execute(select(Workspace.id, Workspace.name))).all()
            for workspace_id, name in candidates:
                await conn.execute(
                    text("SELECT set_config('app.workspace_id', :ws, true)"), {"ws": str(workspace_id)}
                )
                membership = (
                    await conn.execute(
                        select(Membership).where(
                            Membership.workspace_id == workspace_id,
                            Membership.user_id == user.id,
                            Membership.active.is_(True),
                        )
                    )
                ).scalar_one_or_none()
                if membership is not None:
                    items.append(
                        {
                            "id": str(workspace_id),
                            "name": name,
                            "roles": list(membership.roles),
                            "data_mode": "live",
                        }
                    )
    return envelope(
        {"items": items, "offset": 0, "limit": len(items), "total": len(items)}, request.state.request_id
    )
