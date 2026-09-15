import json
from pathlib import Path

from buyeros_api.services.approval_fingerprint import SERIALIZER_VERSION, fingerprint

VECTORS = [
    {
        "name": "plain-lf",
        "context": {
            "draft_id": "d1",
            "revision_number": 1,
            "subject": "Hi",
            "body": "Body\n",
            "follow_up": None,
            "recipient_hash": "sha256:r",
            "sender_version_key": "s1",
            "icp_version": 2,
            "evidence_ids": ["ev1", "ev2"],
            "policy_decision_ids": ["p1"],
            "suppression_epoch": 0,
        },
    },
    {
        "name": "crlf-and-presentation-field",
        "context": {
            "draft_id": "d2",
            "revision_number": 3,
            "subject": "Angebot",
            "body": "Zeile1\r\nZeile2",
            "follow_up": "F1",
            "recipient_hash": "sha256:zz",
            "sender_version_key": "s9",
            "icp_version": 5,
            "evidence_ids": [],
            "policy_decision_ids": [],
            "suppression_epoch": 1,
            "display_locale": "zh-HK",
        },
    },
]

out = []
for vector in VECTORS:
    out.append({"name": vector["name"], "serializer_version": SERIALIZER_VERSION, "context": vector["context"], "digest": fingerprint(vector["context"])})

target = Path(__file__).resolve().parents[2] / "generated" / "approval-golden-vectors.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", target)
print(json.dumps(out, indent=2))
