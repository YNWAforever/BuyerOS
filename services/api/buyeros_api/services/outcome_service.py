"""Append-only manual outcome chain with project-owned, actor-attributed events."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from ..api.errors import ApiError
from ..db.buyers import ProjectBuyer
from ..db.icp import Project
from ..db.outcomes import OutcomeEvent
from ..db.models import User
from .audit_service import append_audit


def _historical_time(value: datetime) -> datetime:
    now = datetime.now(timezone.utc)
    if value > now + timedelta(minutes=5) or value.year < 2000:
        raise ApiError(422, "INVALID_REQUEST", "occurred_at is outside the allowed historical range")
    return value


def outcome_data(event: OutcomeEvent, actor_display_name: str | None = None) -> dict:
    data = {
        "id": str(event.id), "workspace_id": str(event.workspace_id),
        "version": event.version, "created_at": event.created_at.isoformat(),
        "updated_at": event.updated_at.isoformat(), "data_mode": "live",
        "project_id": str(event.project_id), "buyer_id": str(event.buyer_id),
        "stage": event.stage, "source": event.source, "notes": event.notes,
        "occurred_at": event.occurred_at.isoformat(),
        "recorded_at": event.created_at.isoformat(),
        "actor_id": str(event.actor_user_id),
        "actor_display_name": actor_display_name if actor_display_name and actor_display_name.strip() else None,
    }
    if event.provenance_reference:
        data["provenance_reference"] = event.provenance_reference
    if event.correction_reason:
        data["correction_reason"] = event.correction_reason
    if event.supersedes_id:
        data["supersedes_id"] = str(event.supersedes_id)
    return data


async def project_outcome_data(session, event: OutcomeEvent) -> dict:
    # Display metadata is projected from this event's canonical actor only.
    # It never establishes identity, membership or permissions.
    name = (await session.execute(select(User.display_name).where(
        User.id == event.actor_user_id))).scalar_one_or_none()
    return outcome_data(event, name)


async def _active_project(session, *, workspace_id, project_id, lock=False):
    query = select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
    if lock:
        query = query.with_for_update()
    project = (await session.execute(query)).scalar_one_or_none()
    if project is None or (lock and project.status != "active"):
        raise ApiError(404, "NOT_FOUND", "project not found")
    return project


async def record_outcome(session, *, workspace_id, project_id, actor_id, request):
    await _active_project(session, workspace_id=workspace_id, project_id=project_id, lock=True)
    buyer = (await session.execute(select(ProjectBuyer.id).where(
        ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project_id,
        ProjectBuyer.id == request.buyer_id,
    ))).scalar_one_or_none()
    if buyer is None:
        raise ApiError(404, "NOT_FOUND", "buyer not found")
    event = OutcomeEvent(workspace_id=workspace_id, project_id=project_id,
        buyer_id=buyer, actor_user_id=actor_id, stage=request.stage, source="manual",
        occurred_at=_historical_time(request.occurred_at), notes=request.notes,
        provenance_reference=request.provenance_reference)
    session.add(event)
    await session.flush()
    await session.refresh(event)
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="outcome.recorded", entity_type="outcome_event", entity_id=event.id)
    return event


async def correct_outcome(session, *, workspace_id, outcome_id, actor_id, request, expected_version):
    locator = (await session.execute(select(OutcomeEvent.project_id).where(
        OutcomeEvent.workspace_id == workspace_id, OutcomeEvent.id == outcome_id,
    ))).scalar_one_or_none()
    if locator is None:
        raise ApiError(404, "NOT_FOUND", "outcome not found")
    await _active_project(session, workspace_id=workspace_id, project_id=locator, lock=True)
    parent = (await session.execute(select(OutcomeEvent).where(
        OutcomeEvent.workspace_id == workspace_id, OutcomeEvent.id == outcome_id,
    ))).scalar_one_or_none()
    if parent is None or parent.project_id != locator:
        raise ApiError(404, "NOT_FOUND", "outcome not found")
    if parent.version != expected_version:
        raise ApiError(412, "STALE_REVISION", "outcome version changed")
    successor = (await session.execute(select(OutcomeEvent.id).where(
        OutcomeEvent.workspace_id == workspace_id,
        OutcomeEvent.supersedes_id == outcome_id,
    ))).scalar_one_or_none()
    if successor is not None:
        raise ApiError(409, "INVALID_STATE", "outcome already corrected")
    event = OutcomeEvent(workspace_id=workspace_id, project_id=parent.project_id,
        buyer_id=parent.buyer_id, actor_user_id=actor_id, stage=request.stage, source="manual",
        occurred_at=_historical_time(request.occurred_at), notes=request.notes,
        provenance_reference=parent.provenance_reference, correction_reason=request.reason,
        supersedes_id=parent.id)
    session.add(event)
    await session.flush()
    await session.refresh(event)
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="outcome.corrected", entity_type="outcome_event", entity_id=event.id)
    return event


async def list_outcomes(session, *, workspace_id, project_id, offset, limit):
    await _active_project(session, workspace_id=workspace_id, project_id=project_id)
    scope = (OutcomeEvent.workspace_id == workspace_id, OutcomeEvent.project_id == project_id)
    total = (await session.execute(select(func.count()).select_from(OutcomeEvent).where(*scope))).scalar_one()
    events = (await session.execute(select(OutcomeEvent, User.display_name)
        .outerjoin(User, User.id == OutcomeEvent.actor_user_id).where(*scope)
        .order_by(OutcomeEvent.created_at.desc(), OutcomeEvent.id.desc())
        .offset(offset).limit(limit))).all()
    return {"items": [outcome_data(event, name) for event, name in events],
            "offset": offset, "limit": limit, "total": total}


async def load_outcome(session, *, workspace_id, outcome_id, project_id=None):
    query = select(OutcomeEvent).where(OutcomeEvent.workspace_id == workspace_id,
                                      OutcomeEvent.id == outcome_id)
    if project_id is not None:
        query = query.where(OutcomeEvent.project_id == project_id)
    event = (await session.execute(query)).scalar_one_or_none()
    if event is None:
        raise ApiError(404, "NOT_FOUND", "outcome not found")
    return event
