"""CI opt-in: gate before DB fixtures, including both conftest module aliases."""
import os
from pathlib import Path
import pytest
from tests.policy_activation_target import inspect_target, owned_cluster_factory, assert_owned_test_dsn
from tools.run_policy_activation_tests import OwnedFixturePlugin


def pytest_configure(config):
    path = os.environ.get("BUYEROS_POLICY_TARGET_RECEIPT")
    if not path:
        raise pytest.UsageError("owned CI fixture receipt required; no application URL fallback")
    receipt = Path(path).resolve()
    inspect_target(receipt)
    from tests.conftest import DB_NAME
    config.pluginmanager.register(OwnedFixturePlugin(owned_cluster_factory(receipt,database_name=DB_NAME), assert_owned_test_dsn),
                                  "verified-policy-fixture-allocator")
