"""Bounded frozen maintenance, distinct from 1000-row browser snapshots."""
import hashlib,json,uuid
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,insert,func,literal
from ..api.errors import ApiError
from ..api.deps import permission_for_roles
from ..db.icp import Project
from ..db.models import Membership
from ..db.buyers import ProjectBuyer
from ..db.outbox import BulkManifest,BulkManifestItem,AsyncJob,AsyncJobItem,OutboxEvent
from .buyer_selection import selection_query
from .membership_directory import eligible_owner_predicate
from .bulk_service import job_data,assign_owners,apply_reviews,change_memberships,get_list
from .audit_service import append_audit
from .outbox_service import build_intent
MAX_ITEMS=10000
PAGE=250
TTL=timedelta(minutes=15)


def data(row):
    result={"id":str(row.id),"workspace_id":str(row.workspace_id),"project_id":str(row.project_id),
        "actor_user_id":str(row.actor_user_id),"operation":row.operation,"target":row.specification["target"],
        "filters":row.specification["filters"],"excluded_ids":row.specification["excluded_ids"],
        "reason":row.specification["reason"],"count":row.count,"digest":row.digest,"expires_at":row.expires_at.isoformat(),
        "status":row.status,"version":row.version,"created_at":row.created_at.isoformat()}
    if row.job_id:result["job_id"]=str(row.job_id)
    if row.result is not None:result["result"]=row.result
    if row.specification.get("source_job_id"):result["source_job_id"]=row.specification["source_job_id"]
    return result


async def authorize(session,*,workspace_id,project_id,actor_id,operation,command):
    project=(await session.execute(select(Project).where(Project.workspace_id==workspace_id,Project.id==project_id).with_for_update())).scalar_one_or_none()
    if project is None:raise ApiError(404,"NOT_FOUND","project not found")
    if project.status!="active":raise ApiError(409,"INVALID_STATE","project is not active")
    member=(await session.execute(select(Membership).where(Membership.workspace_id==workspace_id,Membership.user_id==actor_id,Membership.active.is_(True)).with_for_update())).scalar_one_or_none()
    if member is None or not permission_for_roles(member.roles,operation):raise ApiError(403,"PERMISSION_DENIED","current role does not permit this operation")
    if operation=="assignBuyerOwners" and command.get("owner_membership_id"):
        owner=(await session.execute(select(Membership.id).where(Membership.id==uuid.UUID(command["owner_membership_id"]),eligible_owner_predicate(workspace_id)).with_for_update())).scalar_one_or_none()
        if owner is None:raise ApiError(422,"INVALID_REQUEST","owner membership is not active in this workspace")
    if operation=="changeListMemberships":
        item=await get_list(session,workspace_id=workspace_id,list_id=uuid.UUID(command["list_id"]),lock=True)
        if item.project_id!=project_id:raise ApiError(404,"NOT_FOUND","buyer list not found")
    return project


def basis(row):
    raw={"actor_id":str(row.actor_user_id),"workspace_id":str(row.workspace_id),"project_id":str(row.project_id),"specification":row.specification}
    return hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode())


def add_digest(digest,ordinal,buyer_id,version):digest.update(f"\n{ordinal}:{buyer_id}:{version}".encode())


async def get(session,*,workspace_id,project_id,actor_id,manifest_id,lock=False):
    query=select(BulkManifest).where(BulkManifest.workspace_id==workspace_id,BulkManifest.project_id==project_id,BulkManifest.actor_user_id==actor_id,BulkManifest.id==manifest_id)
    row=(await session.execute(query.with_for_update() if lock else query)).scalar_one_or_none()
    if row is None:raise ApiError(404,"NOT_FOUND","manifest not found")
    return row


async def preview(session,*,workspace_id,project_id,actor_id,payload):
    specification=payload.model_dump(mode="json",exclude_none=True)
    # Explicit clear-owner null is material, even though optional unused target fields are absent.
    specification["target"]=payload.target.model_dump(mode="json",include=payload.target.model_fields_set)
    specification["excluded_ids"]=sorted(specification["excluded_ids"])
    specification["reason"]=payload.reason.strip()
    filters={k:v for k,v in specification["filters"].items() if v not in (None,[],False,"")}
    if "q" in filters:filters["q"]=filters["q"].strip()
    specification["filters"]=filters
    command={**specification["target"],"reason":specification["reason"]}
    await authorize(session,workspace_id=workspace_id,project_id=project_id,actor_id=actor_id,operation=payload.operation,command=command)
    if payload.source_job_id:
        source=(await session.execute(select(AsyncJob).where(AsyncJob.workspace_id==workspace_id,AsyncJob.project_id==project_id,AsyncJob.actor_user_id==actor_id,AsyncJob.id==payload.source_job_id).with_for_update())).scalar_one_or_none()
        if source is None:raise ApiError(404,"NOT_FOUND","source job not found")
        if source.status not in {"completed","failed","cancelled"}:raise ApiError(409,"JOB_IN_PROGRESS","wait until the job has finished")
        if filters or source.operation!=payload.operation or any(source.command.get(k)!=v for k,v in specification["target"].items()):
            raise ApiError(422,"INVALID_REQUEST","retry preview must preserve the source operation/target and use only failed rows")
        query=select(AsyncJobItem.buyer_id,func.coalesce(ProjectBuyer.version,AsyncJobItem.expected_version)).outerjoin(ProjectBuyer,(ProjectBuyer.workspace_id==AsyncJobItem.workspace_id)&(ProjectBuyer.project_id==project_id)&(ProjectBuyer.id==AsyncJobItem.buyer_id)).where(AsyncJobItem.workspace_id==workspace_id,AsyncJobItem.job_id==source.id,AsyncJobItem.status.in_(["blocked","conflict"])).order_by(AsyncJobItem.ordinal)
    else:
        query=await selection_query(session,workspace_id=workspace_id,project_id=project_id,filters=filters,sort="name_asc")
    if payload.excluded_ids:query=query.where((AsyncJobItem.buyer_id if payload.source_job_id else ProjectBuyer.id).not_in(payload.excluded_ids))
    row=BulkManifest(workspace_id=workspace_id,project_id=project_id,actor_user_id=actor_id,specification=specification,operation=payload.operation,command=command,expires_at=datetime.now(timezone.utc)+TTL,status="preparing",version=1,count=0,digest="")
    session.add(row);await session.flush()
    digest=basis(row);count=0
    # One server cursor has one PostgreSQL statement snapshot, not repeated LIMIT/OFFSET reads.
    cursor=await session.stream(query.limit(MAX_ITEMS+1).execution_options(yield_per=PAGE))
    try:
        async for batch in cursor.partitions(PAGE):
            if count+len(batch)>MAX_ITEMS:raise ApiError(422,"INVALID_REQUEST","more than 10000 buyers; narrow or segment filters; nothing was truncated")
            values=[]
            for buyer_id,version in batch:
                add_digest(digest,count,buyer_id,version)
                values.append({"id":uuid.uuid4(),"workspace_id":workspace_id,"manifest_id":row.id,"buyer_id":buyer_id,"ordinal":count,"expected_version":version});count+=1
            if values:await session.execute(insert(BulkManifestItem),values)
    finally:await cursor.close()
    if not count:raise ApiError(422,"INVALID_REQUEST","selection has no buyer rows")
    row.count=count;row.digest=digest.hexdigest();row.status="ready"
    append_audit(session,workspace_id=workspace_id,actor_id=actor_id,action="previewBulkManifest",entity_type="bulk_manifest",entity_id=row.id,reason=command["reason"],detail_digest="sha256:"+row.digest)
    await session.flush();await session.refresh(row);return row


async def execute(session,*,row,actor_id,version,payload):
    project=await authorize(session,workspace_id=row.workspace_id,project_id=row.project_id,actor_id=actor_id,operation=row.operation,command=row.command)
    if row.status!="ready":raise ApiError(409,"INVALID_STATE","manifest is not ready for a new execution")
    if row.expires_at<=datetime.now(timezone.utc):raise ApiError(412,"STALE_REVISION","manifest expired; preview current versions")
    if row.version!=version or row.digest!=payload.digest:raise ApiError(412,"STALE_REVISION","exact manifest digest/version changed")
    digest=basis(row);count=0;pairs=[]
    cursor=await session.stream(select(BulkManifestItem).where(BulkManifestItem.workspace_id==row.workspace_id,BulkManifestItem.manifest_id==row.id).order_by(BulkManifestItem.ordinal).execution_options(yield_per=PAGE))
    try:
        async for batch in cursor.scalars().partitions(PAGE):
            for item in batch:
                if item.ordinal!=count:raise ApiError(412,"STALE_REVISION","manifest position changed")
                add_digest(digest,count,item.buyer_id,item.expected_version);count+=1
                if row.count<=100:pairs.append({"id":str(item.buyer_id),"version":item.expected_version})
    finally:await cursor.close()
    if count!=row.count or digest.hexdigest()!=row.digest:raise ApiError(412,"STALE_REVISION","frozen selection changed")
    if row.count<=100:
        selection={"kind":"explicit","buyers":pairs}
        if row.operation=="assignBuyerOwners":
            owner=row.command.get("owner_membership_id");result=await assign_owners(session,workspace_id=row.workspace_id,project_id=row.project_id,actor_user_id=actor_id,selection=selection,owner_membership_id=uuid.UUID(owner) if owner else None,reason=row.command["reason"])
        elif row.operation=="reviewBuyers":result=await apply_reviews(session,workspace_id=row.workspace_id,project_id=row.project_id,actor_user_id=actor_id,active_icp_version_id=project.active_icp_version_id,selection=selection,status=row.command["status"],reason=row.command["reason"])
        else:result=await change_memberships(session,item=await get_list(session,workspace_id=row.workspace_id,list_id=uuid.UUID(row.command["list_id"]),lock=True),actor_user_id=actor_id,selection=selection,operation=row.command["operation"])
        row.result=result;status=200
    else:
        job=AsyncJob(workspace_id=row.workspace_id,project_id=row.project_id,actor_user_id=actor_id,manifest_id=row.id,kind="bulk_mutation",operation=row.operation,command=row.command,status="queued",requested=row.count,processed=0,updated=0,unchanged=0,blocked=0,conflicts=0)
        session.add(job);await session.flush()
        statement=select(func.gen_random_uuid(),BulkManifestItem.workspace_id,literal(job.id),BulkManifestItem.buyer_id,BulkManifestItem.ordinal,BulkManifestItem.expected_version,literal("pending")).where(BulkManifestItem.workspace_id==row.workspace_id,BulkManifestItem.manifest_id==row.id)
        await session.execute(insert(AsyncJobItem).from_select(["id","workspace_id","job_id","buyer_id","ordinal","expected_version","status"],statement,include_defaults=False))
        intent={"job_id":str(job.id)};session.add(OutboxEvent(workspace_id=row.workspace_id,intent_key=build_intent("bulk.mutate",intent,0),event_type="bulk.mutate",payload=intent,state="ready",attempts=0,fencing_generation=0))
        await session.flush();await session.refresh(job);row.job_id=job.id;result=job_data(job);status=202
    row.version+=1;row.status="executed"
    append_audit(session,workspace_id=row.workspace_id,actor_id=actor_id,action="executeBulkManifest",entity_type="bulk_manifest",entity_id=row.id,reason=row.command["reason"],detail_digest="sha256:"+row.digest)
    await session.flush();return status,result
