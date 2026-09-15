from buyeros_api.services.approval_service import material_change, stale


def test_material_field_change_detected():
    assert material_change({"body": "a"}, {"body": "b"}) is True
    assert material_change({"body": "a"}, {"body": "a"}) is False


def test_presentation_change_is_not_material():
    old = {"body": "a", "display_locale": "en"}
    new = {"body": "a", "display_locale": "zh-HK"}
    assert material_change(old, new) is False


def test_evidence_change_is_material():
    assert material_change({"evidence_ids": ["ev1"]}, {"evidence_ids": ["ev2"]}) is True


def test_stale_hash_or_revision():
    assert stale(expected_hash="h1", actual_hash="h2", expected_revision=4, actual_revision=4) is True
    assert stale(expected_hash="h1", actual_hash="h1", expected_revision=4, actual_revision=5) is True
    assert stale(expected_hash="h1", actual_hash="h1", expected_revision=4, actual_revision=4) is False
