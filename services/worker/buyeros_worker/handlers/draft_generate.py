"""Zero-cost grounded preparation template; no model or mailbox capability."""

import uuid


ROUTE = "grounded-template.v1"


def _sources(facts: list[dict], evidence: list[dict]) -> tuple[list[dict], list[dict]]:
    if not facts or not evidence or len(facts) > 50 or len(evidence) > 50:
        raise ValueError("approved facts and evidence are required and bounded")
    for fact in facts:
        uuid.UUID(str(fact["id"]))
        if fact.get("approved") is not True or not isinstance(fact.get("value"), str):
            raise ValueError("unapproved offer fact")
        if not fact["value"].strip() or len(fact["value"]) > 400:
            raise ValueError("invalid offer fact text")
    for item in evidence:
        uuid.UUID(str(item["id"]))
        if (item.get("stance") != "supports" or not isinstance(item.get("excerpt"), str)
                or not item["excerpt"].strip() or len(item["excerpt"]) > 800
                or not isinstance(item.get("version"), int) or item["version"] < 1):
            raise ValueError("unsupported or unversioned evidence")
    return facts, evidence


def render_grounded_template(*, facts: list[dict], evidence: list[dict], objective: str,
                             tone: str, language: str, kind: str) -> dict:
    facts, evidence = _sources(facts, evidence)
    if tone not in {"professional", "concise", "warm"} or kind not in {"initial", "follow_up"}:
        raise ValueError("unsupported draft style")
    if language not in {"en", "zh-HK"}:
        raise ValueError("unsupported draft language")
    if not isinstance(objective, str) or not 3 <= len(objective) <= 1000:
        raise ValueError("invalid objective")
    claims = ([{"text": row["value"], "kind": "offer_fact", "offer_fact_ids": [str(row["id"])],
                "evidence_ids": []} for row in facts]
              + [{"text": row["excerpt"], "kind": "observation", "offer_fact_ids": [],
                  "evidence_ids": [str(row["id"])]} for row in evidence])
    if language == "zh-HK":
        salutation = "你好，"
        offer_prefix = "我們提供："
        observation_prefix = "參考公開資料："
        close = "如果合適，歡迎安排交流。"
        subject_prefix = "業務簡介：" if kind == "initial" else "跟進："
    else:
        salutation = "Hello,"
        offer_prefix = "We offer: "
        observation_prefix = "Public source excerpt: "
        close = "Would a conversation be useful?"
        subject_prefix = "Introduction: " if kind == "initial" else "Follow-up: "
    body = "\n\n".join([
        salutation,
        *[offer_prefix + row["value"] + f" [offer_fact:{row['id']}]" for row in facts],
        *[observation_prefix + '"' + row["excerpt"] + '"' + f" [evidence:{row['id']}:v{row['version']}]"
          for row in evidence],
        close,
    ])
    if len(body) > 20000:
        raise ValueError("grounded draft exceeds body bound")
    return {"subject": subject_prefix + facts[0]["value"][:100], "body": body,
            "claims": claims, "recipient_contact_id": None, "route": ROUTE,
            "prompt_version": ROUTE, "objective": objective, "tone": tone,
            "language": language, "kind": kind}


def validate_grounded_output(candidate: dict, *, facts: list[dict], evidence: list[dict]) -> dict:
    """The free route accepts only its reproducible fact/evidence projection."""
    expected = render_grounded_template(
        facts=facts, evidence=evidence, objective=candidate["objective"],
        tone=candidate["tone"], language=candidate["language"], kind=candidate["kind"],
    )
    if candidate != expected:
        raise ValueError("unsupported claim or altered grounded output")
    return candidate


async def _materialize(session, workspace_id: uuid.UUID, job_id: uuid.UUID):
    import hashlib
    import json
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy.sql import and_, or_

    from buyeros_api.db.buyers import Evidence, FitAssessment, HumanReview, ProjectBuyer, SourceDocument
    from buyeros_api.db.drafts import DraftRevision, OutreachDraft, SenderIdentityVersion
    from buyeros_api.db.icp import IcpVersion, Project, canonical_hash
    from buyeros_api.db.outbox import AsyncJob, AsyncJobItem
    from buyeros_api.db.models import Membership
    from buyeros_api.db.policy import PolicyDecision
    from buyeros_api.services.audit_service import append_audit
    from buyeros_api.services.buyer_read import _fit_freshness
    from buyeros_api.services.policy_service import evaluate_current_policy
    from buyeros_api.services.policy_service import policy_workspace_lock
    from buyeros_api.services.draft_service import preparation_recipient_context
    from buyeros_api.api.errors import ApiError
    from buyeros_api.services.icp_service import effective_offer_facts

    await policy_workspace_lock(session, workspace_id)
    job = (await session.execute(select(AsyncJob).where(
        AsyncJob.workspace_id == workspace_id, AsyncJob.id == job_id,
        AsyncJob.kind == "draft_generation", AsyncJob.operation == "generateDraft",
    ).with_for_update())).scalar_one_or_none()
    if job is None:
        return "missing"
    if job.status in {"completed", "failed", "cancelled"}:
        return "duplicate"
    item = (await session.execute(select(AsyncJobItem).where(
        AsyncJobItem.workspace_id == workspace_id, AsyncJobItem.job_id == job_id,
        AsyncJobItem.ordinal == 0,
    ).with_for_update())).scalar_one_or_none()
    if item is None:
        return "missing"

    def reject(code: str):
        job.status = "failed"
        job.processed = 1
        job.blocked = 1
        item.status = "blocked"
        item.reason_code = code
        return code

    command = job.command
    if command.get("route") != ROUTE or command.get("max_cost") != "0.000000":
        return reject("unsupported_route")
    member = (await session.execute(select(Membership).where(
        Membership.workspace_id == workspace_id, Membership.user_id == job.actor_user_id,
    ).with_for_update())).scalar_one_or_none()
    if member is None or not member.active or not set(member.roles) & {"operator", "workspace_admin"}:
        return reject("membership_changed")
    project = (await session.execute(select(Project).where(
        Project.workspace_id == workspace_id, Project.id == job.project_id,
    ).with_for_update())).scalar_one_or_none()
    if project is None or project.status != "active":
        return reject("project_unavailable")
    icp = (await session.execute(select(IcpVersion).where(
        IcpVersion.workspace_id == workspace_id, IcpVersion.id == uuid.UUID(command["icp_id"]),
        IcpVersion.project_id == project.id,
    ))).scalar_one_or_none()
    if (icp is None or project.active_icp_version_id != icp.id or icp.approved_at is None
            or icp.superseded_at is not None or icp.basis_offer_revision != project.offer_revision
            or icp.content_hash != command["icp_hash"] or icp.content_hash != canonical_hash(icp.content)):
        return reject("profile_changed")
    sender = (await session.execute(select(SenderIdentityVersion).where(
        SenderIdentityVersion.workspace_id == workspace_id,
        SenderIdentityVersion.project_id == project.id,
        SenderIdentityVersion.id == uuid.UUID(command["sender_id"]),
        SenderIdentityVersion.retired.is_(False),
    ))).scalar_one_or_none()
    if (sender is None or project.active_sender_identity_version_id != sender.id
            or sender.version_key != command["sender_version"]):
        return reject("sender_changed")
    buyer = (await session.execute(select(ProjectBuyer).where(
        ProjectBuyer.workspace_id == workspace_id, ProjectBuyer.project_id == project.id,
        ProjectBuyer.id == uuid.UUID(command["buyer_id"]),
    ))).scalar_one_or_none()
    if buyer is None or buyer.version != command["buyer_version"]:
        return reject("buyer_changed")
    fit = (await session.execute(select(FitAssessment).where(
        FitAssessment.workspace_id == workspace_id, FitAssessment.id == uuid.UUID(command["fit_id"]),
        FitAssessment.project_buyer_id == buyer.id,
    ))).scalar_one_or_none()
    review = (await session.execute(select(HumanReview).where(
        HumanReview.workspace_id == workspace_id, HumanReview.id == uuid.UUID(command["review_id"]),
        HumanReview.project_buyer_id == buyer.id,
    ))).scalar_one_or_none()
    if (fit is None or fit.icp_version_id != icp.id or fit.verdict != "match"
            or fit.evidence_set_hash != command["evidence_set_hash"] or review is None
            or review.state != "accepted" or review.fit_assessment_id != fit.id
            or (await _fit_freshness(session, workspace_id=workspace_id,
                 fits=[fit], buyers_by_id={buyer.id: buyer})).get(fit.id) != "current"):
        return reject("review_or_evidence_changed")
    decision = await evaluate_current_policy(session, {
        "workspace_id": workspace_id, "project_id": project.id,
        "company_id": buyer.company_id,
    }, "draft_preparation", datetime.now(timezone.utc))
    if not decision["allowed"]:
        return reject("policy_blocked")
    recipient_id = None
    if command.get("recipient_context") is not None:
        expected = command["recipient_context"]
        try:
            recipient_id = uuid.UUID(expected["contact"]["id"])
            current = await preparation_recipient_context(session, workspace_id=workspace_id,
                project_id=project.id, company_id=buyer.company_id, contact_id=recipient_id)
        except (ApiError, ValueError, TypeError, KeyError):
            return reject("recipient_or_policy_changed")
        if current != expected:
            return reject("recipient_or_policy_changed")
    policy_ids = (await session.execute(select(PolicyDecision.id).where(
        PolicyDecision.workspace_id == workspace_id,
        PolicyDecision.purpose == "draft_preparation",
        or_(and_(PolicyDecision.subject_type == "project", PolicyDecision.subject_id == project.id),
            and_(PolicyDecision.subject_type == "company", PolicyDecision.subject_id == buyer.company_id)),
        PolicyDecision.expires_at > datetime.now(timezone.utc),
    ).order_by(PolicyDecision.id))).scalars().all()
    if [str(value) for value in policy_ids] != command["policy_decision_ids"]:
        return reject("policy_changed")
    fact_map = {str(row.get("id")): row for row in effective_offer_facts(icp)
                if isinstance(row, dict) and row.get("approved") is True}
    try:
        facts = [fact_map[value] for value in command["offer_fact_ids"]]
    except KeyError:
        return reject("offer_fact_changed")
    evidence = []
    for ref in command["evidence_refs"]:
        if ref["id"] not in set(fit.evidence_ids or []):
            return reject("evidence_changed")
        row = (await session.execute(select(Evidence, SourceDocument).outerjoin(
            SourceDocument,
            (SourceDocument.workspace_id == Evidence.workspace_id)
            & (SourceDocument.id == Evidence.source_document_id),
        ).where(Evidence.workspace_id == workspace_id, Evidence.id == uuid.UUID(ref["id"]),
                Evidence.project_id == project.id, Evidence.company_id == buyer.company_id))).one_or_none()
        if row is None:
            return reject("evidence_missing")
        e, source = row
        if (e.version != ref["version"] or e.stance != "supports" or e.is_inference
                or source is None or source.project_id != project.id
                or source.permission_purpose != "account_research"
                or source.retention_until is None or source.retention_until <= datetime.now(timezone.utc)
                or not source.excerpt):
            return reject("evidence_stale")
        evidence.append({"id": str(e.id), "version": e.version,
                         "excerpt": e.excerpt, "stance": e.stance})
    if command["kind"] == "follow_up":
        parent_id = command.get("parent_draft_id")
        parent = (await session.execute(select(OutreachDraft).where(
            OutreachDraft.workspace_id == workspace_id, OutreachDraft.id == uuid.UUID(parent_id),
            OutreachDraft.project_id == project.id, OutreachDraft.buyer_id == buyer.id,
        ))).scalar_one_or_none() if parent_id else None
        if parent is None:
            return reject("parent_changed")
    try:
        generated = render_grounded_template(
            facts=facts, evidence=evidence, objective=command["objective"],
            tone=command["tone"], language=command["language"], kind=command["kind"])
        validate_grounded_output(generated, facts=facts, evidence=evidence)
    except (ValueError, TypeError, KeyError):
        return reject("grounding_failed")
    content = {**generated, "recipient_contact_id": str(recipient_id) if recipient_id else None,
               "sender_identity_version": sender.version_key,
               "evidence_refs": command["evidence_refs"],
               "value_proposition_fact_ids": command["offer_fact_ids"],
               "icp_version_id": str(icp.id), "evidence_set_hash": fit.evidence_set_hash,
               "policy_decision_ids": command["policy_decision_ids"],
               "parent_draft_id": command.get("parent_draft_id"),
               "grounding_status": "grounded"}
    digest = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    content["context_hash"] = digest(command)
    draft = OutreachDraft(workspace_id=workspace_id, project_id=project.id,
                          buyer_id=buyer.id, current_revision=1, state="draft")
    session.add(draft)
    await session.flush()
    revision = DraftRevision(workspace_id=workspace_id, draft_id=draft.id,
                             revision_number=1, content=content,
                             content_hash=digest(content),
                             evidence_ids=[row["id"] for row in evidence],
                             offer_fact_ids=command["offer_fact_ids"])
    session.add(revision)
    job.command = {**command, "result_draft_id": str(draft.id)}
    job.status = "completed"
    job.processed = 1
    job.updated = 1
    item.status = "updated"
    item.resulting_version = 1
    append_audit(session, workspace_id=workspace_id, actor_id=job.actor_user_id,
                 action="draft.generated", entity_type="draft", entity_id=draft.id,
                 detail_digest="sha256:" + revision.content_hash)
    await session.flush()
    return "completed"


from buyeros_worker.registry import HandlerResult, register


@register("draft.generate")
async def handle(session, context, payload) -> HandlerResult:
    if not isinstance(payload, dict) or set(payload) != {"job_id"}:
        return HandlerResult(state="blocked", detail="draft.generate: invalid payload")
    try:
        workspace_id = uuid.UUID(context["workspace_id"])
        job_id = uuid.UUID(payload["job_id"])
    except (KeyError, ValueError, TypeError, AttributeError):
        return HandlerResult(state="blocked", detail="draft.generate: invalid scope")
    outcome = await _materialize(session, workspace_id, job_id)
    if outcome == "missing":
        return HandlerResult(state="blocked", detail="draft.generate: job missing")
    return HandlerResult(state="done", detail=f"draft.generate: {outcome}")
