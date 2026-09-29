"""Versioned canonical-JSON approval fingerprint (BO-022).

Python and TypeScript must compute identical digests; shared golden vectors
(pinned in ``services/generated/approval-golden-vectors.json``) enforce that.
"""

import hashlib
import json

SERIALIZER_VERSION = "approval-cjson-v1"

PRESENTATION_FIELDS = frozenset({"display_locale", "ui_theme", "sidebar_state"})

MATERIAL_FIELDS = frozenset(
    {
        "draft_id",
        "revision_number",
        "subject",
        "body",
        "follow_up",
        "recipient_hash",
        "sender_version_key",
        "icp_version",
        "evidence_ids",
        "policy_decision_ids",
        "suppression_epoch",
    }
)


def fingerprint(context: dict) -> str:
    material = {k: v for k, v in context.items() if k not in PRESENTATION_FIELDS}
    if isinstance(material.get("body"), str):
        material["body"] = material["body"].replace("\r\n", "\n")
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


# New approvals use a strict, recursively canonicalized context. The v1 function
# above remains frozen so historical digests never change during rollout.
CURRENT_SERIALIZER_VERSION = "approval-cjson-v2"
CURRENT_CONTEXT_FIELDS = frozenset({
    "draft_id", "revision_id", "revision_number", "content_hash", "subject",
    "body", "kind", "language", "recipient", "sender", "icp", "buyer",
    "fit", "review", "evidence", "offer_fact_ids", "policy", "suppression",
})


def _normalize_current(value):
    if isinstance(value, str):
        return value.replace("\r\n", "\n")
    if isinstance(value, list):
        return [_normalize_current(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_current(value[key]) for key in sorted(value)}
    return value


def fingerprint_current(context: dict) -> str:
    """Return a prefixed digest; API context_hash carries its raw 64 hex digits."""
    if set(context) != CURRENT_CONTEXT_FIELDS:
        raise ValueError("approval context fields do not match v2 schema")
    material = {"serializer_version": CURRENT_SERIALIZER_VERSION,
                "context": _normalize_current(context)}
    raw = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
