"""Preview-bound, atomic candidate imports; never contacts, fit, review or paid jobs."""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select, text

from ..api.errors import ApiError
from ..db.buyer_imports import BuyerImport, BuyerImportRow
from ..db.buyers import Company, ProjectBuyer
from ..db.icp import Project
from .audit_service import append_audit
from .buyer_import_parser import identity_keys


async def require_project(session, workspace_id, project_id, *, lock=False):
    query = select(Project).where(Project.workspace_id == workspace_id, Project.id == project_id)
    if lock:
        query = query.with_for_update()
    project = (await session.execute(query)).scalar_one_or_none()
    if project is None:
        raise ApiError(404, "NOT_FOUND", "project not found")
    if project.status != "active":
        raise ApiError(409, "INVALID_REQUEST", "buyers can only be imported to an active project")
    return project


async def _matching_companies(session, workspace_id, project_id, rows):
    names = {identity_keys(row["name"], None)[0].removeprefix("name:") for row in rows}
    domains = {row["normalized_domain"] for row in rows if row["normalized_domain"]}
    normalized_name = lambda column: func.lower(func.regexp_replace(func.btrim(func.normalize(column, text("NFKC"))), r"\s+", " ", "g"))
    conditions = [normalized_name(Company.display_name).in_(names), normalized_name(Company.legal_name).in_(names)]
    if domains:
        conditions.append(func.lower(Company.domain).in_(domains | {"www." + value for value in domains}))
    pairs = (await session.execute(select(Company, ProjectBuyer.id).outerjoin(ProjectBuyer, and_(
        ProjectBuyer.workspace_id == Company.workspace_id, ProjectBuyer.company_id == Company.id,
        ProjectBuyer.project_id == project_id,
    )).where(Company.workspace_id == workspace_id, or_(*conditions)).order_by(Company.id))).all()
    known = {}
    for company, buyer_id in pairs:
        domain = company.domain.lower().rstrip(".").removeprefix("www.") if company.domain else None
        for key in set(identity_keys(company.display_name, domain) + identity_keys(company.legal_name, domain)):
            known.setdefault(key, []).append((company, buyer_id))
    return known


def _classify(rows, known):
    classified, seen = [], {}
    companies = {"company:" + str(company.id): (company, buyer_id)
                 for matches in known.values() for company, buyer_id in matches}
    for index, source in enumerate(rows):
        row = dict(source)
        keys = identity_keys(row["name"], row["normalized_domain"])
        matches = {"company:" + str(company.id) for key in keys for company, _ in known.get(key, [])}
        identities = matches | {identity for key in keys for identity in seen.get(key, set())}
        identity = next(iter(identities)) if len(identities) == 1 else None
        duplicate = companies[identity][1] if identity in companies else None
        if not row["errors"]:
            if len(identities) > 1:
                row["errors"] = ["Name and domain identify different or ambiguous companies; manual identity mapping is required"]
            elif identity in companies and duplicate is None:
                row["errors"] = ["A company outside this project has a similar name or domain; manual identity mapping is required"]
        row["duplicate_buyer_id"] = str(duplicate) if duplicate and not row["errors"] else None
        row["status"] = "invalid" if row["errors"] else "duplicate" if identities else "ready"
        if not row["errors"]:
            for key in keys:
                seen.setdefault(key, set()).add(identity or f"row:{index}")
        classified.append(row)
    return classified


def _digest(item):
    bound = {"id": str(item.id), "workspace_id": str(item.workspace_id), "project_id": str(item.project_id),
             "actor_user_id": str(item.actor_user_id), "manifest": item.manifest}
    encoded = json.dumps(bound, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def import_data(item):
    if item.status == "completed":
        return item.result
    return {"id": str(item.id), "workspace_id": str(item.workspace_id), "project_id": str(item.project_id),
            "status": "previewed", "preview_digest": item.preview_digest,
            "expires_at": item.expires_at.isoformat(), **item.manifest}


async def stage_import(session, *, workspace_id, project_id, actor_user_id, parsed):
    known = await _matching_companies(session, workspace_id, project_id, parsed["rows"])
    rows = _classify(parsed["rows"], known)
    counts = {status: sum(row["status"] == status for row in rows) for status in ("ready", "duplicate", "invalid")}
    item = BuyerImport(id=uuid.uuid4(), workspace_id=workspace_id, project_id=project_id, actor_user_id=actor_user_id,
        status="previewed", expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        manifest={"file_name": parsed["file_name"], "file_sha256": parsed["file_sha256"], "rows": rows,
                  "total_rows": len(rows), "ready_rows": counts["ready"], "duplicate_rows": counts["duplicate"],
                  "invalid_rows": counts["invalid"], "can_import": counts["invalid"] == 0 and counts["ready"] > 0})
    item.preview_digest = _digest(item)
    session.add(item)
    await session.flush()
    return item


async def get_import(session, *, workspace_id, project_id, actor_user_id, import_id, lock=False):
    query = select(BuyerImport).where(BuyerImport.workspace_id == workspace_id, BuyerImport.project_id == project_id,
                                    BuyerImport.actor_user_id == actor_user_id, BuyerImport.id == import_id)
    if lock:
        query = query.with_for_update()
    item = (await session.execute(query)).scalar_one_or_none()
    if item is None:
        raise ApiError(404, "NOT_FOUND", "buyer import not found")
    return item


async def confirm_import(session, *, item, preview_digest, actor_user_id):
    if not hmac.compare_digest(item.preview_digest, preview_digest) or not hmac.compare_digest(_digest(item), preview_digest):
        raise ApiError(409, "IMPORT_PREVIEW_CHANGED", "preview digest does not match the stored source rows")
    if item.status == "completed":
        return item.result
    if item.expires_at <= datetime.now(timezone.utc):
        raise ApiError(409, "IMPORT_PREVIEW_EXPIRED", "preview has expired; preview the file again")
    if not item.manifest["can_import"]:
        raise ApiError(422, "INVALID_REQUEST", "fix invalid rows or provide new candidates before importing")
    # Serialize import writers across projects because companies belong to the workspace.
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"), {"scope": "buyer-import:" + str(item.workspace_id)})
    source_rows = item.manifest["rows"]
    known = await _matching_companies(session, item.workspace_id, item.project_id, source_rows)
    current = _classify(source_rows, known)
    if [(row["status"], row["duplicate_buyer_id"]) for row in current] != [(row["status"], row["duplicate_buyer_id"]) for row in source_rows]:
        raise ApiError(409, "IMPORT_PREVIEW_CHANGED", "buyer duplicates changed; preview the file again")
    buyer_ids = []
    for index, row in enumerate(source_rows):
        if row["status"] != "ready":
            continue
        company = Company(id=uuid.uuid4(), workspace_id=item.workspace_id,
                          display_name=row["name"], legal_name=row["name"], domain=row["normalized_domain"])
        session.add(company)
        await session.flush()
        buyer = ProjectBuyer(id=uuid.uuid4(), workspace_id=item.workspace_id, project_id=item.project_id,
                             company_id=company.id, version=1)
        session.add(buyer)
        await session.flush()
        session.add(BuyerImportRow(workspace_id=item.workspace_id, project_id=item.project_id,
                                  import_id=item.id, project_buyer_id=buyer.id, row_index=index))
        buyer_ids.append(str(buyer.id))
    result = {"id": str(item.id), "status": "completed", "imported_rows": len(buyer_ids),
              "skipped_duplicate_rows": item.manifest["duplicate_rows"], "buyer_ids": buyer_ids,
              "preview_digest": item.preview_digest}
    item.status, item.result = "completed", result
    append_audit(session, workspace_id=item.workspace_id, actor_id=actor_user_id,
                 action="buyer_import.completed", entity_type="buyer_import", entity_id=item.id,
                 detail_digest=item.preview_digest)
    await session.flush()
    return result


async def buyer_import_source(session, *, workspace_id, buyer_id):
    buyer = (await session.execute(select(ProjectBuyer).where(ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.id == buyer_id))).scalar_one_or_none()
    if buyer is None:
        raise ApiError(404, "NOT_FOUND", "buyer not found")
    pair = (await session.execute(select(BuyerImportRow, BuyerImport).join(BuyerImport, and_(
        BuyerImport.workspace_id == BuyerImportRow.workspace_id, BuyerImport.project_id == BuyerImportRow.project_id,
        BuyerImport.id == BuyerImportRow.import_id,
    )).where(BuyerImportRow.workspace_id == workspace_id, BuyerImportRow.project_id == buyer.project_id,
             BuyerImportRow.project_buyer_id == buyer_id))).one_or_none()
    if pair is None:
        return None
    link, item = pair
    row = item.manifest["rows"][link.row_index]
    return {"import_id": str(item.id), "file_name": item.manifest["file_name"], "file_sha256": item.manifest["file_sha256"],
            "candidate_status": "unreviewed", **{key: row[key] for key in (
                "row_number", "source_row", "source_date", "website", "source_urls", "original_fields")}}
