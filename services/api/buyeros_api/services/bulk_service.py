"""Durable 50-row bulk mutations, resumed through the existing transactional outbox."""
import uuid

from .membership_directory import eligible_owner_predicate
from sqlalchemy import func, select

from ..api.errors import ApiError
from ..api.deps import permission_for_roles
from ..db.icp import Project
from ..db.buyers import ProjectBuyer
from ..db.models import Membership
from ..db.outbox import AsyncJob, AsyncJobItem, OutboxEvent
from .buyer_review import _resolve_items, apply as apply_reviews
from .buyer_management import assign_owners, change_memberships, get_list
from .outbox_service import build_intent

CHUNK_SIZE = 50
MAX_BULK = 1000


def job_data(job: AsyncJob, *, results: list[dict] | None = None, offset: int = 0,
             limit: int = 50, total: int | None = None) -> dict:
    data = {
        "id": str(job.id), "workspace_id": str(job.workspace_id), "project_id": str(job.project_id),
        "kind": job.kind, "status": job.status, "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(), "data_mode": "live",
        "requested": job.requested, "processed": job.processed, "updated": job.updated,
        "unchanged": job.unchanged, "blocked": job.blocked, "conflicts": job.conflicts,
        "cancelled": job.processed - job.updated - job.unchanged - job.blocked - job.conflicts,
        "result_page": {"items": results or [], "offset": offset, "limit": limit, "total": total or 0},
    }
    if job.kind == "draft_generation" and job.status == "completed":
        draft_id = job.command.get("result_draft_id") if isinstance(job.command, dict) else None
        if draft_id:
            data["result_id"] = draft_id
    return data


async def create_bulk_job(session, *, workspace_id, project_id, actor_user_id,
                          operation: str, selection: dict, command: dict) -> AsyncJob:
    pairs = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id,
                                 actor_user_id=actor_user_id, selection=selection)
    if len(pairs) <= 100 or len(pairs) > MAX_BULK:
        raise ApiError(422, "INVALID_REQUEST", "async bulk selection must contain 101..1000 buyers")
    if operation == "assignBuyerOwners" and command.get("owner_membership_id"):
        owner_id = uuid.UUID(command["owner_membership_id"])
        active_owner = (await session.execute(select(Membership.id).where(
            Membership.id == owner_id, eligible_owner_predicate(workspace_id),
        ))).scalar_one_or_none()
        if active_owner is None:
            raise ApiError(422, "INVALID_REQUEST", "owner membership is not active in this workspace")
    job = AsyncJob(
        workspace_id=workspace_id, project_id=project_id, actor_user_id=actor_user_id,
        kind="bulk_mutation", operation=operation, command=command, status="queued",
        requested=len(pairs), processed=0, updated=0, unchanged=0, blocked=0, conflicts=0,
    )
    session.add(job)
    await session.flush()
    for ordinal, (buyer_id, version) in enumerate(pairs):
        session.add(AsyncJobItem(
            workspace_id=workspace_id, job_id=job.id, buyer_id=buyer_id,
            ordinal=ordinal, expected_version=version, status="pending",
        ))
    intent_payload = {"job_id": str(job.id)}
    session.add(OutboxEvent(
        workspace_id=workspace_id, intent_key=build_intent("bulk.mutate", intent_payload, 0),
        event_type="bulk.mutate", payload=intent_payload, state="ready", attempts=0,
        fencing_generation=0,
    ))
    await session.flush()
    await session.refresh(job)
    return job


async def apply_bulk_chunk(session, job_id: uuid.UUID, limit: int = CHUNK_SIZE) -> dict:
    if not 1 <= limit <= CHUNK_SIZE:
        raise ValueError("bulk chunk limit must be 1..50")
    job = (await session.execute(select(AsyncJob).where(AsyncJob.id == job_id)
                                 .with_for_update())).scalar_one_or_none()
    if job is None:
        raise ApiError(404, "NOT_FOUND", "bulk job not found")
    if job.status in {"completed", "cancelled", "failed"}:
        return {"job_id": str(job.id), "processed": 0, "remaining": job.requested - job.processed}
    pending = (await session.execute(select(AsyncJobItem).where(
        AsyncJobItem.workspace_id == job.workspace_id, AsyncJobItem.job_id == job.id,
        AsyncJobItem.status == "pending").order_by(AsyncJobItem.ordinal).limit(limit)
    )).scalars().all()
    if not pending:
        job.status = "completed"
        await session.flush()
        return {"job_id": str(job.id), "processed": 0, "remaining": 0}
    if job.status == "cancel_requested":
        for item in pending:
            item.status = "cancelled"
            item.reason_code = "job_cancelled"
        job.processed += len(pending)
        if job.processed == job.requested:
            job.status = "cancelled"
    else:
        membership = (await session.execute(select(Membership).where(
            Membership.workspace_id == job.workspace_id,
            Membership.user_id == job.actor_user_id,
            Membership.active.is_(True)).with_for_update())).scalar_one_or_none()
        permitted = membership is not None and permission_for_roles(membership.roles, job.operation)
        target_active = True
        if permitted and job.operation == "assignBuyerOwners" and job.command.get("owner_membership_id"):
            owner_id = uuid.UUID(job.command["owner_membership_id"])
            target_active = (await session.execute(select(Membership.id).where(
                Membership.id == owner_id, eligible_owner_predicate(job.workspace_id),
            ))).scalar_one_or_none() is not None
        if permitted and target_active:
            selection = {"kind": "explicit", "buyers": [
                {"id": str(item.buyer_id), "version": item.expected_version} for item in pending
            ]}
            if job.operation == "assignBuyerOwners":
                raw_owner = job.command.get("owner_membership_id")
                owner_id = uuid.UUID(raw_owner) if raw_owner else None
                data = await assign_owners(
                    session, workspace_id=job.workspace_id, project_id=job.project_id,
                    actor_user_id=job.actor_user_id, selection=selection,
                    owner_membership_id=owner_id, reason=job.command["reason"],
                )
            elif job.operation == "reviewBuyers":
                project = (await session.execute(select(Project).where(
                    Project.workspace_id == job.workspace_id, Project.id == job.project_id
                ))).scalar_one()
                data = await apply_reviews(
                    session, workspace_id=job.workspace_id, project_id=job.project_id,
                    actor_user_id=job.actor_user_id, active_icp_version_id=project.active_icp_version_id,
                    selection=selection, status=job.command["status"], reason=job.command["reason"],
                )
            elif job.operation == "changeListMemberships":
                item = await get_list(session, workspace_id=job.workspace_id,
                                      list_id=uuid.UUID(job.command["list_id"]), lock=True)
                data = await change_memberships(
                    session, item=item, actor_user_id=job.actor_user_id,
                    selection=selection, operation=job.command["operation"],
                )
            else:
                raise ApiError(422, "INVALID_REQUEST", "unsupported bulk operation")
            by_id = {row["id"]: row for row in data["results"]}
        else:
            reason = "actor_role_revoked" if not permitted else "owner_membership_inactive"
            by_id = {str(item.buyer_id): {"status": "blocked", "reason_code": reason}
                     for item in pending}
        for item in pending:
            result = by_id[str(item.buyer_id)]
            item.status = result["status"]
            item.reason_code = result.get("reason_code")
            item.resulting_version = result.get("version")
            setattr(job, item.status if item.status != "conflict" else "conflicts",
                    getattr(job, item.status if item.status != "conflict" else "conflicts") + 1)
        job.processed += len(pending)
        job.status = "completed" if job.processed == job.requested else "running"
    if job.processed < job.requested:
        payload = {"job_id": str(job.id)}
        session.add(OutboxEvent(
            workspace_id=job.workspace_id,
            intent_key=build_intent("bulk.mutate", payload, job.processed),
            event_type="bulk.mutate", payload=payload, state="ready", attempts=0,
            fencing_generation=0,
        ))
    await session.flush()
    return {"job_id": str(job.id), "processed": len(pending),
            "remaining": job.requested - job.processed}


async def read_job_page(session, *, workspace_id, job_id, actor_user_id, is_admin,
                        offset: int, limit: int) -> dict:
    job = (await session.execute(select(AsyncJob).where(
        AsyncJob.workspace_id == workspace_id, AsyncJob.id == job_id
    ))).scalar_one_or_none()
    if job is None or (job.actor_user_id != actor_user_id and not is_admin):
        raise ApiError(404, "NOT_FOUND", "bulk job not found")
    total = (await session.execute(select(func.count()).select_from(AsyncJobItem).where(
        AsyncJobItem.workspace_id == workspace_id, AsyncJobItem.job_id == job_id,
        AsyncJobItem.status != "pending"
    ))).scalar_one()
    rows = (await session.execute(select(AsyncJobItem).where(
        AsyncJobItem.workspace_id == workspace_id, AsyncJobItem.job_id == job_id,
        AsyncJobItem.status != "pending"
    ).order_by(AsyncJobItem.ordinal).offset(offset).limit(limit))).scalars().all()
    results = [{"id": str(item.buyer_id), "status": item.status,
                **({"reason_code": item.reason_code} if item.reason_code else {}),
                **({"version": item.resulting_version} if item.resulting_version else {})}
               for item in rows]
    return job_data(job, results=results, offset=offset, limit=limit, total=total)



async def retry_failed_only(session, *, workspace_id, job_id, actor_user_id, roles) -> tuple[int, dict]:
    """Start a new command using only failed rows and their current buyer versions."""
    job = (await session.execute(select(AsyncJob).where(
        AsyncJob.workspace_id == workspace_id, AsyncJob.id == job_id,
    ).with_for_update())).scalar_one_or_none()
    if job is None or job.actor_user_id != actor_user_id:
        raise ApiError(404, "NOT_FOUND", "bulk job not found")
    if not permission_for_roles(roles, job.operation):
        raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
    if job.status not in {"completed", "failed"}:
        raise ApiError(409, "JOB_IN_PROGRESS", "wait until the job has finished")
    failed = (await session.execute(select(AsyncJobItem).where(
        AsyncJobItem.workspace_id == workspace_id, AsyncJobItem.job_id == job_id,
        AsyncJobItem.status.in_(("blocked", "conflict")),
    ).order_by(AsyncJobItem.ordinal))).scalars().all()
    if not failed:
        raise ApiError(409, "NO_FAILED_ITEMS", "job has no failed buyer rows")
    versions = dict((await session.execute(select(ProjectBuyer.id, ProjectBuyer.version).where(
        ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == job.project_id,
        ProjectBuyer.id.in_([item.buyer_id for item in failed]),
    ))).all())
    selection = {"kind": "explicit", "buyers": [
        {"id": str(item.buyer_id), "version": versions.get(item.buyer_id, item.expected_version)}
        for item in failed
    ]}
    if len(failed) > 100:
        retry_job = await create_bulk_job(
            session, workspace_id=workspace_id, project_id=job.project_id,
            actor_user_id=actor_user_id, operation=job.operation,
            selection=selection, command=job.command,
        )
        return 202, job_data(retry_job)
    if job.operation == "assignBuyerOwners":
        raw_owner = job.command.get("owner_membership_id")
        data = await assign_owners(session, workspace_id=workspace_id, project_id=job.project_id,
                                   actor_user_id=actor_user_id, selection=selection,
                                   owner_membership_id=uuid.UUID(raw_owner) if raw_owner else None,
                                   reason=job.command["reason"])
    elif job.operation == "reviewBuyers":
        project = (await session.execute(select(Project).where(
            Project.workspace_id == workspace_id, Project.id == job.project_id,
        ))).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        data = await apply_reviews(session, workspace_id=workspace_id, project_id=job.project_id,
                                   actor_user_id=actor_user_id, active_icp_version_id=project.active_icp_version_id,
                                   selection=selection, status=job.command["status"], reason=job.command["reason"])
    elif job.operation == "changeListMemberships":
        buyer_list = await get_list(session, workspace_id=workspace_id,
                                    list_id=uuid.UUID(job.command["list_id"]), lock=True)
        data = await change_memberships(session, item=buyer_list, actor_user_id=actor_user_id,
                                        selection=selection, operation=job.command["operation"])
    else:
        raise ApiError(422, "INVALID_REQUEST", "unsupported bulk operation")
    return 200, data


async def cancel_bulk_job(session, *, workspace_id, job_id, actor_user_id) -> dict:
    """Request cancellation after the current committed chunk; never undo committed rows."""
    job = (await session.execute(select(AsyncJob).where(
        AsyncJob.workspace_id == workspace_id, AsyncJob.id == job_id,
    ).with_for_update())).scalar_one_or_none()
    if job is None or job.actor_user_id != actor_user_id:
        raise ApiError(404, "NOT_FOUND", "bulk job not found")
    if job.status in {"completed", "cancelled", "failed"}:
        raise ApiError(409, "JOB_TERMINAL", "completed job cannot be cancelled")
    job.status = "cancel_requested"
    await session.flush()
    await session.refresh(job)
    return job_data(job)
