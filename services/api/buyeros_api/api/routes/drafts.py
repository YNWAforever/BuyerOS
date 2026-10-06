"""Durable, grounded draft preparation routes. Delivery remains disabled."""
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from ..auth import Principal, get_principal
from ..deps import load_membership, permission_for_roles, tenant_scoped
from ..errors import ApiError, envelope
from ..idempotency import begin_idempotency, complete_idempotency, if_match_version
from ..schemas import DraftApproveRequest, DraftGroundingReviewRequest, DraftGenerateRequest, DraftReviewRequest, DraftUpdate

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["drafts"])


@router.post("/projects/{project_id}/drafts", status_code=202)
async def generate_draft(workspace_id: uuid.UUID, project_id: uuid.UUID,
                         payload: DraftGenerateRequest, request: Request,
                         principal: Principal = Depends(get_principal),
                         idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict:
    from ...services.bulk_service import job_data
    from ...services.draft_service import admit_grounded_template

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "generateDraft"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        body = payload.model_dump(mode="json")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=membership["user_id"], operation_id="generateDraft", key=idempotency_key,
            body=body, target={"workspace_id": str(workspace_id), "project_id": str(project_id)},
            precondition=None)
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            return envelope(outcome.response["data"], request.state.request_id)
        job = await admit_grounded_template(session, workspace_id=workspace_id,
                    project_id=project_id, actor_id=membership["user_id"], request=payload)
        data = job_data(job)
        complete_idempotency(outcome, str(job.id),
                             response={"http_status": 202, "data": data})
    return envelope(data, request.state.request_id)


@router.get("/projects/{project_id}/drafts")
async def list_drafts(workspace_id: uuid.UUID, project_id: uuid.UUID, request: Request,
                      principal: Principal = Depends(get_principal),
                      offset: int = Query(default=0, ge=0),
                      limit: int = Query(default=20, ge=1, le=100)) -> dict:
    from sqlalchemy import func, select
    from ...db.drafts import Approval, DraftRevision, OutreachDraft
    from ...db.icp import Project
    from ...services.draft_service import draft_data

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "listDrafts"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        project = (await session.execute(select(Project.id).where(
            Project.workspace_id == workspace_id, Project.id == project_id,
        ))).scalar_one_or_none()
        if project is None:
            raise ApiError(404, "NOT_FOUND", "project not found")
        predicate = (OutreachDraft.workspace_id == workspace_id) & (OutreachDraft.project_id == project_id)
        total = (await session.execute(select(func.count()).select_from(OutreachDraft).where(predicate))).scalar_one()
        rows = (await session.execute(select(OutreachDraft, DraftRevision).join(
            DraftRevision,
            (DraftRevision.workspace_id == OutreachDraft.workspace_id)
            & (DraftRevision.draft_id == OutreachDraft.id)
            & (DraftRevision.revision_number == OutreachDraft.current_revision),
        ).where(predicate).order_by(OutreachDraft.created_at, OutreachDraft.id)
          .offset(offset).limit(limit))).all()
        ids = [draft.id for draft, _ in rows]
        approvals = (await session.execute(select(Approval).where(
            Approval.workspace_id == workspace_id, Approval.draft_id.in_(ids),
            Approval.invalidated_reason.is_(None),
        ))).scalars().all() if ids else []
        by_draft = {row.draft_id: row for row in approvals}
        items = [draft_data(draft, revision, by_draft.get(draft.id)) for draft, revision in rows]
    return envelope({"items": items, "offset": offset, "limit": limit, "total": total},
                    request.state.request_id)


@router.get("/drafts/{draft_id}")
async def get_draft(workspace_id: uuid.UUID, draft_id: uuid.UUID, request: Request,
                    response: Response, principal: Principal = Depends(get_principal)) -> dict:
    from sqlalchemy import select
    from ...db.drafts import Approval, DraftRevision, OutreachDraft
    from ...services.draft_service import draft_data

    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "getDraft"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        row = (await session.execute(select(OutreachDraft, DraftRevision).join(
            DraftRevision,
            (DraftRevision.workspace_id == OutreachDraft.workspace_id)
            & (DraftRevision.draft_id == OutreachDraft.id)
            & (DraftRevision.revision_number == OutreachDraft.current_revision),
        ).where(OutreachDraft.workspace_id == workspace_id, OutreachDraft.id == draft_id))).one_or_none()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "draft not found")
        from ...db.icp import Project
        from ...services.approval_service import current_review_matches
        draft, revision = row
        approval = (await session.execute(select(Approval).where(
            Approval.workspace_id == workspace_id, Approval.draft_id == draft.id,
            Approval.invalidated_reason.is_(None),
        ))).scalar_one_or_none()
        current = True
        if draft.state in {"review_requested", "approved"}:
            project = (await session.execute(select(Project).where(
                Project.workspace_id == workspace_id, Project.id == draft.project_id,
            ))).scalar_one_or_none()
            current = bool(project) and await current_review_matches(session,
                workspace_id=workspace_id, project=project, draft=draft, revision=revision)
            if not current:
                approval = None
        data = draft_data(draft, revision, approval, context_current=current,
            include_review_context=bool({"operator", "reviewer", "workspace_admin"}
                                        .intersection(membership["roles"])))
        response.headers["ETag"] = f'"{draft.state_version}"'
    return envelope(data, request.state.request_id)


@router.patch("/drafts/{draft_id}")
async def edit_draft(workspace_id: uuid.UUID, draft_id: uuid.UUID, payload: DraftUpdate,
                     request: Request, response: Response,
                     principal: Principal = Depends(get_principal),
                     idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                     if_match: str | None = Header(default=None, alias="If-Match")) -> dict:
    from sqlalchemy import select
    from ...db.drafts import OutreachDraft
    from ...services.draft_service import draft_data, edit_draft as apply_edit

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "editDraft"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=membership["user_id"], operation_id="editDraft", key=idempotency_key,
            body=changes, target={"workspace_id": str(workspace_id), "draft_id": str(draft_id)},
            precondition=if_match)
        if outcome.replay:
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(outcome.response["data"], request.state.request_id)
        # Approval and edits both lock project before draft, avoiding inverse-order deadlocks.
        from ...db.icp import Project
        project_id = (await session.execute(select(OutreachDraft.project_id).where(
            OutreachDraft.workspace_id == workspace_id, OutreachDraft.id == draft_id,
        ))).scalar_one_or_none()
        if project_id is None:
            raise ApiError(404, "NOT_FOUND", "draft not found")
        await session.execute(select(Project).where(
            Project.workspace_id == workspace_id, Project.id == project_id,
        ).with_for_update())
        draft = (await session.execute(select(OutreachDraft).where(
            OutreachDraft.workspace_id == workspace_id, OutreachDraft.id == draft_id,
        ).with_for_update())).scalar_one_or_none()
        if draft is None:
            raise ApiError(404, "NOT_FOUND", "draft not found")
        revision = await apply_edit(session, workspace_id=workspace_id, draft=draft,
                                    expected_version=expected_version, changes=changes)
        data = draft_data(draft, revision)
        complete_idempotency(outcome, str(draft.id),
                             response={"http_status": 200, "version": draft.state_version, "data": data})
        response.headers["ETag"] = f'"{draft.state_version}"'
    return envelope(data, request.state.request_id)


@router.post("/drafts/{draft_id}/review")
async def request_draft_review(workspace_id: uuid.UUID, draft_id: uuid.UUID,
                               payload: DraftReviewRequest, request: Request, response: Response,
                               principal: Principal = Depends(get_principal),
                               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                               if_match: str | None = Header(default=None, alias="If-Match")) -> dict:
    from ...services.approval_service import request_draft_review as apply_review
    from ...services.draft_service import draft_data

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "requestDraftReview"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=membership["user_id"], operation_id="requestDraftReview", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "draft_id": str(draft_id)},
            precondition=if_match)
        if outcome.replay:
            from sqlalchemy import select
            from ...db.drafts import Approval
            from ...services.approval_service import (_REVIEW_ROLES, _locked_draft,
                current_review_matches)
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            project, draft, revision = await _locked_draft(session, workspace_id=workspace_id,
                draft_id=draft_id, actor_id=membership["user_id"], roles=_REVIEW_ROLES)
            if draft.state not in {"review_requested", "approved"} or not await current_review_matches(
                    session, workspace_id=workspace_id, project=project, draft=draft,
                    revision=revision):
                raise ApiError(412, "STALE_REVISION", "review context changed")
            approval = (await session.execute(select(Approval).where(
                Approval.workspace_id == workspace_id, Approval.draft_id == draft.id,
                Approval.invalidated_reason.is_(None),
            ))).scalar_one_or_none()
            data = draft_data(draft, revision, approval, include_review_context=True)
            response.headers["ETag"] = f'"{draft.state_version}"'
            return envelope(data, request.state.request_id)
        draft, revision, _policy_ids = await apply_review(session, workspace_id=workspace_id,
            actor_id=membership["user_id"], draft_id=draft_id, expected_version=expected_version,
            binding=payload)
        data = draft_data(draft, revision, include_review_context=True)
        complete_idempotency(outcome, str(draft.id),
            response={"http_status": 200, "version": draft.state_version, "data": data})
        response.headers["ETag"] = f'"{draft.state_version}"'
    return envelope(data, request.state.request_id)


@router.post("/drafts/{draft_id}/approvals", status_code=201)
async def approve_draft(workspace_id: uuid.UUID, draft_id: uuid.UUID,
                        payload: DraftApproveRequest, request: Request, response: Response,
                        principal: Principal = Depends(get_principal),
                        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                        if_match: str | None = Header(default=None, alias="If-Match")) -> dict:
    from ...services.approval_service import approval_data, approve_draft as apply_approval

    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        membership = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(membership["roles"], "approveDraft"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=membership["user_id"], operation_id="approveDraft", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "draft_id": str(draft_id)},
            precondition=if_match)
        if outcome.replay:
            from sqlalchemy import select
            from ...db.drafts import Approval
            from ...services.approval_service import (_APPROVAL_ROLES, _locked_draft,
                current_review_matches)
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            project, draft, revision = await _locked_draft(session, workspace_id=workspace_id,
                draft_id=draft_id, actor_id=membership["user_id"], roles=_APPROVAL_ROLES)
            approval = (await session.execute(select(Approval).where(
                Approval.workspace_id == workspace_id,
                Approval.id == uuid.UUID(outcome.record.resource_id),
                Approval.draft_id == draft.id, Approval.invalidated_reason.is_(None),
            ))).scalar_one_or_none()
            if (approval is None or draft.state != "approved"
                    or not await current_review_matches(session, workspace_id=workspace_id,
                        project=project, draft=draft, revision=revision)):
                raise ApiError(412, "STALE_REVISION", "approval context changed")
            return envelope(approval_data(approval), request.state.request_id)
        approval = await apply_approval(session, workspace_id=workspace_id,
            actor_id=membership["user_id"], draft_id=draft_id, expected_version=expected_version,
            confirmation=payload.confirmation, binding=payload)
        data = approval_data(approval)
        complete_idempotency(outcome, str(approval.id),
            response={"http_status": 201, "data": data})
    return envelope(data, request.state.request_id)


@router.post("/drafts/{draft_id}/deliver")
async def disabled_delivery_boundary(workspace_id: uuid.UUID, draft_id: uuid.UUID,
                                     principal: Principal = Depends(get_principal)) -> dict:
    # This endpoint must remain side-effect free even for an approved draft.
    raise ApiError(403, "DELIVERY_DISABLED", "delivery is disabled")


@router.post("/drafts/{draft_id}/grounding-reviews")
async def review_draft_grounding(workspace_id: uuid.UUID, draft_id: uuid.UUID,
                                payload: DraftGroundingReviewRequest, request: Request, response: Response,
                                principal: Principal = Depends(get_principal),
                                idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
                                if_match: str | None = Header(default=None, alias="If-Match")) -> dict:
    from ...services.draft_grounding import review_manual_grounding
    from ...services.draft_service import draft_data
    if not idempotency_key:
        raise ApiError(400, "INVALID_REQUEST", "Idempotency-Key header is required")
    expected_version = if_match_version(if_match)
    async with tenant_scoped(workspace_id) as session:
        member = await load_membership(session, principal=principal, workspace_id=workspace_id)
        if not permission_for_roles(member["roles"], "reviewDraftGrounding"):
            raise ApiError(403, "PERMISSION_DENIED", "insufficient role")
        outcome = await begin_idempotency(session, workspace_id=workspace_id,
            actor_id=member["user_id"], operation_id="reviewDraftGrounding", key=idempotency_key,
            body=payload.model_dump(mode="json"),
            target={"workspace_id": str(workspace_id), "draft_id": str(draft_id)}, precondition=if_match)
        if outcome.replay:
            from ...services.approval_service import _locked_draft, current_approval_context
            if outcome.response is None:
                raise ApiError(409, "IDEMPOTENCY_CONFLICT", "legacy replay requires a new key")
            project, draft, revision = await _locked_draft(session, workspace_id=workspace_id,
                draft_id=draft_id, actor_id=member["user_id"], roles={"reviewer", "workspace_admin"})
            if str(revision.id) != outcome.response["data"]["revision_id"]:
                raise ApiError(412, "STALE_REVISION", "reviewed draft was edited again")
            await current_approval_context(session, workspace_id=workspace_id,
                project=project, draft=draft, revision=revision)
            data = outcome.response["data"]
            response.headers["ETag"] = f'"{outcome.response["version"]}"'
            return envelope(data, request.state.request_id)
        draft, revision = await review_manual_grounding(session, workspace_id=workspace_id,
            actor_id=member["user_id"], draft_id=draft_id, expected_version=expected_version, payload=payload)
        data = draft_data(draft, revision)
        complete_idempotency(outcome, str(draft.id),
            response={"http_status": 200, "version": draft.state_version, "data": data})
        response.headers["ETag"] = f'"{draft.state_version}"'
    return envelope(data, request.state.request_id)
