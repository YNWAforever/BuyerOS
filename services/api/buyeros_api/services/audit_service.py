"""One redacted audit append/read boundary for tenant mutations."""
import hashlib
import re
import uuid
from contextvars import ContextVar

from ..db.outcomes import AuditEvent

request_correlation: ContextVar[str | None] = ContextVar("request_correlation", default=None)


def reason_code(reason: str) -> str:
    """Expose only short nonsensitive decision words; always keep the full text out."""
    lowered = reason.lower().strip()
    if (len(lowered) > 80 or "@" in lowered or "http" in lowered
            or any(term in lowered for term in ("bearer", "token", "secret", "password", "key="))):
        return "reason_recorded"
    code = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")[:64]
    return code or "reason_recorded"


def append_audit(session, *, workspace_id: uuid.UUID, actor_id: uuid.UUID | None,
                 action: str, entity_type: str, entity_id: uuid.UUID | str | None,
                 request_id: str | None = None, reason: str | None = None,
                 detail_digest: str | None = None) -> AuditEvent:
    try:
        correlation_id = uuid.UUID(request_id or request_correlation.get()) if (request_id or request_correlation.get()) else None
    except ValueError:
        correlation_id = None
    event = AuditEvent(
        workspace_id=workspace_id, actor_id=actor_id, action=action,
        subject_type=entity_type, subject_id=str(entity_id) if entity_id else None,
        detail_digest=detail_digest or ("sha256:" + hashlib.sha256(reason.encode()).hexdigest() if reason else None),
        reason=reason_code(reason) if reason else None,
        request_id=correlation_id,
    )
    session.add(event)
    return event


def audit_data(event: AuditEvent) -> dict:
    try:
        entity_id = str(uuid.UUID(event.subject_id)) if event.subject_id else None
    except (ValueError, TypeError):
        entity_id = None
    data = {
        "id": str(event.id), "workspace_id": str(event.workspace_id),
        "action": event.action, "entity_type": event.subject_type,
        "occurred_at": event.created_at.isoformat(),
    }
    if event.actor_id:
        data["actor_id"] = str(event.actor_id)
    if entity_id:
        data["entity_id"] = entity_id
    if event.request_id:
        data["request_id"] = str(event.request_id)
    if event.reason and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", event.reason):
        data["reason_code"] = event.reason
    return data
