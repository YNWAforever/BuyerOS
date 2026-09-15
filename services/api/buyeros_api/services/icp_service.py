"""Hash-bound ICP approval helpers (BO-007).

The P2 plan specified this module but it was never landed; P9 Task 5 creates it
so the ICP approve route reuses the same names. ICP content is immutable once
saved, so approval binds the exact ``content_hash``.
"""


class StaleRevision(Exception):
    pass


class AlreadyApproved(Exception):
    pass


def verify_approval_hash(row, expected_hash: str) -> None:
    if row.content_hash != expected_hash:
        raise StaleRevision("content hash changed; reload the profile")
