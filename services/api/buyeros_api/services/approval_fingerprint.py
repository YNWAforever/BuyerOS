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
