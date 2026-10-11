"""Read-only project work summary and bounded authoritative provider receipts."""
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import APIRouter,Depends,Query,Request
from sqlalchemy import select,text
from ..auth import Principal,get_principal
from ..deps import get_engine,load_membership,permission_for_roles
from ..errors import ApiError,envelope
from ...db.session import workspace_directory_session
from ...db.icp import Project
from ...db.contact import ProviderOperation
from ...services.work_queue import count_query,provider_operation_data,provider_operations_query,read_work_queue

router=APIRouter(prefix='/v1/workspaces/{workspace_id}/projects/{project_id}',tags=['work-queue'])

@asynccontextmanager
async def queue_read_snapshot(workspace_id):
 async with workspace_directory_session(get_engine()) as session:
  await session.execute(text("SELECT set_config('app.workspace_id', :ws, true)"),{'ws':str(workspace_id)})
  yield session

async def authorize(session,principal,workspace_id,project_id,operation):
 member=await load_membership(session,principal=principal,workspace_id=workspace_id)
 if not permission_for_roles(member['roles'],operation):raise ApiError(403,'PERMISSION_DENIED','insufficient role')
 project=(await session.execute(select(Project.id).where(Project.workspace_id==workspace_id,Project.id==project_id))).scalar_one_or_none()
 if project is None:raise ApiError(404,'NOT_FOUND','project not found')
 return member

@router.get('/work-queue')
async def get_work_queue(workspace_id:uuid.UUID,project_id:uuid.UUID,request:Request,principal:Principal=Depends(get_principal)):
 async with queue_read_snapshot(workspace_id) as session:
  member=await authorize(session,principal,workspace_id,project_id,'getWorkQueue')
  data=await read_work_queue(session,workspace_id=workspace_id,project_id=project_id,member=member)
 return envelope(data,request.state.request_id)

@router.get('/provider-operations')
async def list_provider_operations(workspace_id:uuid.UUID,project_id:uuid.UUID,request:Request,
 acceptance:Literal['unknown']|None=None,offset:int=Query(0,ge=0),limit:int=Query(20,ge=1,le=100),principal:Principal=Depends(get_principal)):
 async with queue_read_snapshot(workspace_id) as session:
  member=await authorize(session,principal,workspace_id,project_id,'listProviderOperations')
  query=provider_operations_query(workspace_id=workspace_id,project_id=project_id,member=member,acceptance=acceptance)
  total=(await session.execute(count_query(query))).scalar_one()
  rows=(await session.execute(query.order_by(ProviderOperation.created_at.desc(),ProviderOperation.id.desc()).offset(offset).limit(limit))).scalars().all()
  data={'items':[provider_operation_data(row) for row in rows],'offset':offset,'limit':limit,'total':total}
 return envelope(data,request.state.request_id)
