import pytest

from buyeros_api.services.snapshot_service import TooManyIds, materialize_snapshot


def test_snapshot_assigns_stable_ordinals():
    assert materialize_snapshot([("b", 2), ("a", 1)]) == [(0, "b", 2), (1, "a", 1)]


def test_snapshot_rejects_over_cap():
    with pytest.raises(TooManyIds):
        materialize_snapshot([(f"b{i}", 1) for i in range(1001)])


def test_snapshot_accepts_exactly_at_cap():
    out = materialize_snapshot([(f"b{i}", 1) for i in range(1000)])
    assert len(out) == 1000 and out[-1][0] == 999
