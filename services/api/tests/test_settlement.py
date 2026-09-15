from decimal import Decimal

from buyeros_api.services.settlement import cancel_effect, settle_effect


def test_success_commits_charge():
    assert settle_effect("succeeded", "0.300000") == {"commit": Decimal("0.300000"), "release": Decimal("0.000000")}


def test_unknown_settles_nothing():
    assert settle_effect("unknown", "0.300000") == {"commit": Decimal("0.000000"), "release": Decimal("0.000000")}


def test_cancel_releases_only_proven_unsent():
    assert cancel_effect("intent") == "release"
    assert cancel_effect("reserved") == "release"
    assert cancel_effect("submitting") == "reconcile"
    assert cancel_effect("unknown") == "reconcile"
