"""Current discussion authority, shared by notes and durable tasks."""
import os
from contextlib import asynccontextmanager
from sqlalchemy import exists, or_, select
from ..api.deps import load_membership, permission_for_roles, tenant_scoped
from ..api.errors import ApiError
from ..db.conversation_threads import ConversationThread as Thread, ConversationThreadShare as Share
from ..db.icp import Project
from ..settings import get_settings


def not_found():
    return ApiError(404, 'NOT_FOUND', 'discussion not found')


def sales_enabled(workspace_id):
    return (os.environ.get('BUYEROS_SALES_SKILLS_ENABLED') == 'true'
        and str(workspace_id) in {x.strip() for x in os.environ.get('BUYEROS_SALES_WORKSPACE_IDS', '').split(',')})


@asynccontextmanager
async def access(workspace_id, project_id, principal, *, lock_project=False, sales=False, admission=True):
    if sales:
        # Entry gating never revokes recovery of persisted, currently authorized work.
        if admission and not sales_enabled(workspace_id):
            raise not_found()
    elif os.environ.get('NEXT_PUBLIC_CONVERSATION_HOME') != 'true':
        raise not_found()
    if not get_settings().live_read_enabled:
        raise ApiError(503, 'READ_DISABLED', 'live reads are temporarily disabled')
    async with tenant_scoped(workspace_id) as session:
        if sales:
            from .xverum_dispatch import gates
            await gates(session,workspace_id)
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member['roles'], 'getProject'):
            raise not_found()
        query = select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
        if lock_project:
            query = query.with_for_update()
        if (await session.execute(query)).scalar_one_or_none() is None:
            raise not_found()
        yield session, member['user_id']


def thread_scope(workspace_id, project_id):
    return (Thread.workspace_id == workspace_id, Thread.project_id == project_id)


def shared(actor):
    return exists(select(Share.id).where(Share.workspace_id == Thread.workspace_id, Share.thread_id == Thread.id, Share.grantee_user_id == actor))


async def load(session, workspace_id, project_id, thread_id, actor, *, owner=False, edit=False, lock=False):
    query = select(Thread).where(*thread_scope(workspace_id, project_id), Thread.id == thread_id,
        Thread.owner_user_id == actor if owner else or_(Thread.owner_user_id == actor, shared(actor)))
    if lock:
        query = query.with_for_update()
    row = (await session.execute(query)).scalar_one_or_none()
    if row is None:
        raise not_found()
    role = 'owner' if row.owner_user_id == actor else (await session.execute(select(Share.role).where(
        Share.workspace_id == workspace_id, Share.thread_id == row.id, Share.grantee_user_id == actor))).scalar_one_or_none()
    if role is None or (owner and role != 'owner') or (edit and role not in {'owner','editor'}):
        raise not_found()
    return row, role
