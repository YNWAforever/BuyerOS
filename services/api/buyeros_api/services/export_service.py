"""Actor-bound, revocable export references; content is rebuilt behind current gates."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..api.errors import ApiError
from ..db.buyers import Company, Evidence, ProjectBuyer, SourceDocument
from ..db.drafts import Approval
from ..db.icp import Project
from ..db.models import Membership
from ..db.outbox import AsyncJob, AsyncJobItem
from ..db.outcomes import ExportJob
from ..db.runs import ContactPoint
from .approval_fingerprint import fingerprint_current
from .approval_service import _locked_draft, current_approval_context
from .audit_service import append_audit
from .buyer_review import _resolve_items
from .csv_export import to_csv
from .policy_service import evaluate_current_policy, policy_workspace_lock

EXPORT_LIFETIME = timedelta(seconds=900)
MAX_EXPORT_BYTES = 1_000_000
BUYER_COLUMNS = ("buyer_id", "company_id", "display_name", "domain", "evidence_refs")
CONTACT_COLUMNS = BUYER_COLUMNS + ("contact_id", "contact_value")
_EXPORT_ROLES = frozenset({"operator", "reviewer", "workspace_admin"})


def _hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bounded(content: str) -> str:
    if len(content.encode("utf-8")) > MAX_EXPORT_BYTES:
        raise ApiError(422, "INVALID_REQUEST", "export exceeds the 1 MB limit")
    return content


def job_data(job: ExportJob) -> dict:
    return {
        "id": str(job.id), "workspace_id": str(job.workspace_id), "version": job.version,
        "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(),
        "data_mode": "live", "project_id": str(job.project_id),
        "status": job.state, "kind": job.kind, "format": job.format, "record_count": job.record_count,
        "requested_record_count": job.requested_record_count,
        "excluded_records": (job.redaction_summary or {}).get("excluded_records", []),
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
    }


async def _buyer_material(session, *, workspace_id, project_id, items, include_contact_data,
                          purpose, now):
    """Return explicit rows, non-PII exclusions and frozen row identities."""
    if not items or len(items) > 1000:
        raise ApiError(422, "INVALID_REQUEST", "select between 1 and 1000 buyers")
    ids = [buyer_id for buyer_id, _ in items]
    rows = (await session.execute(select(ProjectBuyer, Company).join(
        Company, (Company.workspace_id == ProjectBuyer.workspace_id)
        & (Company.id == ProjectBuyer.company_id),
    ).where(ProjectBuyer.workspace_id == workspace_id,
            ProjectBuyer.project_id == project_id, ProjectBuyer.id.in_(ids)))).all()
    by_id = {buyer.id: (buyer, company) for buyer, company in rows}
    contacts = {}
    if include_contact_data:
        company_ids = [company.id for _, company in rows]
        points = (await session.execute(select(ContactPoint).where(
            ContactPoint.workspace_id == workspace_id,
            ContactPoint.company_id.in_(company_ids),
            ContactPoint.type == "business_email",
            ContactPoint.validity == "provider_marked_valid",
            ContactPoint.quarantined.is_(False),
        ).order_by(ContactPoint.company_id, ContactPoint.id))).scalars().all()
        for point in points:
            contacts.setdefault(point.company_id, []).append(point)
    exported, excluded, identities = [], [], []
    for buyer_id, expected_version in items:
        pair = by_id.get(buyer_id)
        if pair is None or pair[0].version != expected_version:
            excluded.append({"entity_id": str(buyer_id), "reason_code": "STALE_REVISION"})
            continue
        buyer, company = pair
        subject = {"workspace_id": workspace_id, "project_id": project_id,
                   "company_id": company.id}
        account_gate = await evaluate_current_policy(session, subject, "export_accounts", now)
        if not account_gate["allowed"]:
            excluded.append({"entity_id": str(buyer.id), "reason_code": "POLICY_BLOCKED"})
            continue
        point = None
        if include_contact_data:
            for candidate in contacts.get(company.id, []):
                contact_subject = {**subject, "contact_point_id": candidate.id}
                contact_gate = await evaluate_current_policy(session, contact_subject,
                                                              "export_contacts", now)
                outreach_gate = await evaluate_current_policy(session, contact_subject,
                                                               "outreach", now)
                if contact_gate["allowed"] and outreach_gate["allowed"]:
                    point = candidate
                    break
            if point is None:
                excluded.append({"entity_id": str(buyer.id), "reason_code": "POLICY_BLOCKED"})
                continue
        # Evidence references are tenant/project/company IDs only. Source text and notes stay out of CSV.
        evidence_ids = (await session.execute(select(Evidence.id).join(
            SourceDocument, (SourceDocument.workspace_id == Evidence.workspace_id)
            & (SourceDocument.id == Evidence.source_document_id),
        ).where(Evidence.workspace_id == workspace_id, Evidence.project_id == project_id,
            Evidence.company_id == company.id, Evidence.stance == "supports",
            Evidence.is_inference.is_(False), SourceDocument.project_id == project_id,
            SourceDocument.permission_purpose == "account_research",
            SourceDocument.retention_until > now,
        ).order_by(Evidence.id).limit(50))).scalars().all()
        data = {"buyer_id": str(buyer.id), "company_id": str(company.id),
                "display_name": company.display_name, "domain": company.domain or "",
                "evidence_refs": ";".join(str(value) for value in evidence_ids)}
        if point is not None:
            data.update({"contact_id": str(point.id), "contact_value": point.normalized_value})
        exported.append(data)
        identities.append({"buyer_id": str(buyer.id), "version": buyer.version,
                           "contact_id": str(point.id) if point else None,
                           "contact_version": point.version if point else None})
    return exported, excluded, identities


async def _current_export_member(session, *, workspace_id, actor_id):
    member = (await session.execute(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == actor_id,
    ).with_for_update())).scalar_one_or_none()
    if member is None or not member.active or not _EXPORT_ROLES.intersection(member.roles):
        raise ApiError(403, "PERMISSION_DENIED", "current membership cannot export")
    return member


async def create_buyer_export(session, *, workspace_id, project_id, actor_id, request):
    now = datetime.now(timezone.utc)
    await policy_workspace_lock(session, workspace_id)
    await _current_export_member(session, workspace_id=workspace_id, actor_id=actor_id)
    project = (await session.execute(select(Project).where(Project.workspace_id == workspace_id,
        Project.id == project_id))).scalar_one_or_none()
    if project is None or project.status != "active":
        raise ApiError(404, "NOT_FOUND", "project not found")
    items = await _resolve_items(session, workspace_id=workspace_id, project_id=project_id,
                                 actor_user_id=actor_id,
                                 selection=request.selection.model_dump(mode="json"))
    rows, excluded, identities = await _buyer_material(session, workspace_id=workspace_id,
        project_id=project_id, items=items, include_contact_data=request.include_contact_data,
        purpose=request.purpose, now=now)
    if not rows:
        raise ApiError(403, "POLICY_BLOCKED", "no selected buyers are exportable")
    columns = CONTACT_COLUMNS if request.include_contact_data else BUYER_COLUMNS
    _bounded(to_csv(rows, list(columns), "live"))
    manifest = {"rows": identities, "purpose": request.purpose,
                "include_contact_data": request.include_contact_data, "format": "csv"}
    job = ExportJob(workspace_id=workspace_id, project_id=project_id,
        actor_user_id=actor_id, kind="buyer_csv", scope_hash=_hash(manifest),
        state="ready", expires_at=now + EXPORT_LIFETIME, selection_manifest=manifest,
        format="csv", include_contact_data=request.include_contact_data,
        policy_purpose=request.purpose, record_count=len(rows),
        requested_record_count=len(items), redaction_summary={"excluded_records": excluded})
    session.add(job)
    await session.flush()
    await session.refresh(job)
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="export.created", entity_type="export_job", entity_id=job.id,
                 detail_digest="sha256:" + job.scope_hash)
    return job


async def _bulk_failure_rows(session, *, workspace_id, source_job_id, actor_id):
    source = (await session.execute(select(AsyncJob).where(
        AsyncJob.workspace_id == workspace_id, AsyncJob.id == source_job_id,
    ).with_for_update())).scalar_one_or_none()
    if (source is None or source.actor_user_id != actor_id or source.kind != "bulk_mutation"
            or source.status not in {"completed", "failed"}):
        raise ApiError(403, "POLICY_BLOCKED", "bulk failure report is unavailable")
    items = (await session.execute(select(AsyncJobItem).where(
        AsyncJobItem.workspace_id == workspace_id, AsyncJobItem.job_id == source_job_id,
        AsyncJobItem.status.in_(("blocked", "conflict")),
    ).order_by(AsyncJobItem.ordinal))).scalars().all()
    if not items or len(items) > 1000:
        raise ApiError(422, "INVALID_REQUEST", "select a completed job with 1 to 1000 failures")
    rows = [{"buyer_id": str(item.buyer_id), "status": item.status,
             "reason_code": item.reason_code or ""} for item in items]
    return source, rows


async def create_bulk_failure_export(session, *, workspace_id, source_job_id, actor_id):
    locator = (await session.execute(select(AsyncJob.project_id).where(
        AsyncJob.workspace_id == workspace_id, AsyncJob.id == source_job_id,
        AsyncJob.actor_user_id == actor_id,
    ))).scalar_one_or_none()
    if locator is None:
        raise ApiError(404, "NOT_FOUND", "bulk job not found")
    await policy_workspace_lock(session, workspace_id)
    await _current_export_member(session, workspace_id=workspace_id, actor_id=actor_id)
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == locator,
    ).with_for_update())).scalar_one_or_none()
    if project is None or project.status != "active":
        raise ApiError(412, "STALE_REVISION", "report project changed")
    source, rows = await _bulk_failure_rows(session, workspace_id=workspace_id,
        source_job_id=source_job_id, actor_id=actor_id)
    _bounded(to_csv(rows, ["buyer_id", "status", "reason_code"], "live",
                    include_data_mode=False))
    manifest = {"source_job_id": str(source.id), "rows": rows, "format": "csv"}
    now = datetime.now(timezone.utc)
    job = ExportJob(workspace_id=workspace_id, project_id=project.id, actor_user_id=actor_id,
        kind="bulk_failure_csv", scope_hash=_hash(manifest), state="ready",
        expires_at=now + EXPORT_LIFETIME, selection_manifest=manifest,
        format="csv", include_contact_data=False, record_count=len(rows),
        requested_record_count=source.requested, redaction_summary={"excluded_records": []})
    session.add(job)
    await session.flush()
    await session.refresh(job)
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="export.created", entity_type="export_job", entity_id=job.id,
                 detail_digest="sha256:" + job.scope_hash)
    return job


def _draft_text(context: dict) -> str:
    sender = context["sender"]
    recipient = context["recipient"]
    sources = ", ".join(row["source_id"] for row in context["evidence"])
    return _bounded("To: " + recipient["value"] + "\nFrom: " + sender["display_name"]
        + " <" + sender["business_email"] + ">\nSubject: " + context["subject"]
        + "\n\n" + context["body"] + "\n\nSources: " + sources + "\n")


async def _approved_draft_content(session, *, workspace_id, draft_id, actor_id,
                                  revision_id, approval_id):
    project, draft, revision = await _locked_draft(session, workspace_id=workspace_id,
        draft_id=draft_id, actor_id=actor_id, roles=_EXPORT_ROLES)
    if draft.state != "approved" or revision.id != revision_id:
        raise ApiError(412, "STALE_REVISION", "approved draft revision changed")
    approval = (await session.execute(select(Approval).where(
        Approval.workspace_id == workspace_id, Approval.id == approval_id,
        Approval.draft_id == draft.id, Approval.draft_revision_id == revision.id,
        Approval.invalidated_reason.is_(None),
    ))).scalar_one_or_none()
    if approval is None:
        raise ApiError(412, "STALE_REVISION", "current approval is required")
    context, _ = await current_approval_context(session, workspace_id=workspace_id,
        project=project, draft=draft, revision=revision)
    digest = fingerprint_current(context)
    if (draft.review_context_hash != digest.removeprefix("sha256:")
            or approval.context_fingerprint != digest):
        raise ApiError(412, "STALE_REVISION", "approval context changed")
    return project, draft, revision, approval, _draft_text(context)


async def create_draft_export(session, *, workspace_id, draft_id, actor_id,
                              request, expected_version):
    project, draft, revision, approval, content = await _approved_draft_content(session,
        workspace_id=workspace_id, draft_id=draft_id, actor_id=actor_id,
        revision_id=request.revision_id, approval_id=request.approval_id)
    if draft.state_version != expected_version:
        raise ApiError(412, "STALE_REVISION", "draft version changed")
    now = datetime.now(timezone.utc)
    manifest = {"draft_id": str(draft.id), "revision_id": str(revision.id),
                "approval_id": str(approval.id), "format": request.format}
    job = ExportJob(workspace_id=workspace_id, project_id=project.id, actor_user_id=actor_id,
        kind="draft_text", scope_hash=_hash(manifest), state="ready",
        expires_at=now + EXPORT_LIFETIME, selection_manifest=manifest,
        format=request.format, include_contact_data=True, policy_purpose="export_contacts",
        draft_id=draft.id, draft_revision_id=revision.id, approval_id=approval.id,
        record_count=1, requested_record_count=1, redaction_summary={"excluded_records": []})
    session.add(job)
    await session.flush()
    await session.refresh(job)
    append_audit(session, workspace_id=workspace_id, actor_id=actor_id,
                 action="export.created", entity_type="export_job", entity_id=job.id,
                 detail_digest="sha256:" + job.scope_hash)
    return job


async def load_actor_export(session, *, workspace_id, actor_id, export_id):
    job = (await session.execute(select(ExportJob).where(
        ExportJob.workspace_id == workspace_id, ExportJob.id == export_id,
        ExportJob.actor_user_id == actor_id,
    ))).scalar_one_or_none()
    if job is None or not job.selection_manifest or _hash(job.selection_manifest) != job.scope_hash:
        raise ApiError(404, "NOT_FOUND", "export not found")
    return job


async def authorize_export_content(session, *, workspace_id, actor_id, export_id) -> dict:
    job = await load_actor_export(session, workspace_id=workspace_id,
                                  actor_id=actor_id, export_id=export_id)
    if job.state != "ready":
        raise ApiError(403, "POLICY_BLOCKED", "export is not available")
    if job.expires_at is None or job.expires_at <= datetime.now(timezone.utc):
        raise ApiError(403, "POLICY_BLOCKED", "export expired")
    manifest = job.selection_manifest
    await policy_workspace_lock(session, workspace_id)
    await _current_export_member(session, workspace_id=workspace_id, actor_id=actor_id)
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == job.project_id,
    ).with_for_update())).scalar_one_or_none()
    if project is None or project.status != "active":
        raise ApiError(412, "STALE_REVISION", "export project changed")
    if job.kind == "buyer_csv":
        if (manifest.get("purpose") != job.policy_purpose
                or manifest.get("include_contact_data") != job.include_contact_data
                or manifest.get("format") != "csv"):
            raise ApiError(403, "POLICY_BLOCKED", "export scope changed")
        refs = manifest["rows"]
        items = [(uuid.UUID(ref["buyer_id"]), int(ref["version"])) for ref in refs]
        rows, excluded, identities = await _buyer_material(session, workspace_id=workspace_id,
            project_id=job.project_id, items=items,
            include_contact_data=job.include_contact_data,
            purpose=job.policy_purpose, now=datetime.now(timezone.utc))
        if excluded or identities != refs or len(rows) != job.record_count:
            raise ApiError(403, "POLICY_BLOCKED", "export scope or permission changed")
        columns = CONTACT_COLUMNS if job.include_contact_data else BUYER_COLUMNS
        return {"body": _bounded(to_csv(rows, list(columns), "live")),
                "media_type": "text/csv; charset=utf-8", "filename": f"buyeros-export-{job.id}.csv",
                "job": job}
    if job.kind == "bulk_failure_csv":
        if manifest.get("format") != "csv" or job.format != "csv":
            raise ApiError(403, "POLICY_BLOCKED", "report format changed")
        source_id = uuid.UUID(manifest["source_job_id"])
        source, rows = await _bulk_failure_rows(session, workspace_id=workspace_id,
            source_job_id=source_id, actor_id=actor_id)
        if source.project_id != job.project_id or rows != manifest["rows"] or len(rows) != job.record_count:
            raise ApiError(403, "POLICY_BLOCKED", "failure report changed")
        return {"body": _bounded(to_csv(rows, ["buyer_id", "status", "reason_code"],
                    "live", include_data_mode=False)),
                "media_type": "text/csv; charset=utf-8",
                "filename": f"buyer-job-{source.id}-failed.csv", "job": job}
    if job.kind == "draft_text" and job.draft_id and job.draft_revision_id and job.approval_id:
        if (manifest.get("draft_id") != str(job.draft_id)
                or manifest.get("revision_id") != str(job.draft_revision_id)
                or manifest.get("approval_id") != str(job.approval_id)
                or manifest.get("format") != job.format):
            raise ApiError(403, "POLICY_BLOCKED", "export scope changed")
        _project, _draft, _revision, _approval, content = await _approved_draft_content(
            session, workspace_id=workspace_id, draft_id=job.draft_id, actor_id=actor_id,
            revision_id=job.draft_revision_id, approval_id=job.approval_id)
        return {"body": content, "media_type": "text/plain; charset=utf-8",
                "filename": f"buyeros-draft-{job.id}.txt" if job.format == "text" else None,
                "job": job}
    raise ApiError(403, "POLICY_BLOCKED", "export manifest is unsupported")
