import json
from pathlib import Path

from buyeros_api.services.approval_fingerprint import SERIALIZER_VERSION, fingerprint

GOLDEN = Path(__file__).resolve().parents[2] / "generated" / "approval-golden-vectors.json"

CONTEXT = {
    "draft_id": "d1",
    "revision_number": 1,
    "subject": "Hi",
    "body": "Body\n",
    "evidence_ids": ["ev1"],
    "suppression_epoch": 0,
}


def test_golden_vectors_file_exists():
    assert GOLDEN.exists(), GOLDEN


def test_fingerprint_matches_golden_vectors():
    for vector in json.loads(GOLDEN.read_text(encoding="utf-8")):
        assert vector["serializer_version"] == SERIALIZER_VERSION
        assert fingerprint(vector["context"]) == vector["digest"], vector["name"]


def test_presentation_fields_do_not_change_the_fingerprint():
    assert fingerprint(CONTEXT) == fingerprint({**CONTEXT, "display_locale": "zh-HK", "ui_theme": "dark"})


def test_body_line_endings_are_normalized():
    assert fingerprint({**CONTEXT, "body": "a\r\nb"}) == fingerprint({**CONTEXT, "body": "a\nb"})


def test_material_change_changes_the_fingerprint():
    assert fingerprint(CONTEXT) != fingerprint({**CONTEXT, "body": "different"})
