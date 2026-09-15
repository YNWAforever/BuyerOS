"""Exact-context approval rules (BO-022)."""

from .approval_fingerprint import MATERIAL_FIELDS, PRESENTATION_FIELDS


class StaleApproval(Exception):
    pass


def material_change(old: dict, new: dict) -> bool:
    for field in MATERIAL_FIELDS:
        if field in PRESENTATION_FIELDS:
            continue
        if old.get(field) != new.get(field):
            return True
    return False


def stale(*, expected_hash: str, actual_hash: str, expected_revision: int, actual_revision: int) -> bool:
    return expected_hash != actual_hash or expected_revision != actual_revision
