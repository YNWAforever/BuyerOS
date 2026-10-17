"""Real controlled approval for worker fixtures, with no persistent credential changes."""
from pathlib import Path
import importlib
import sys
from types import ModuleType


def api_fixture_helpers():
    gate = sys.modules.get("_buyeros_owned_policy_gate")
    if gate is None:
        raise ValueError("worker controller fixtures require the verified owned runner")
    package = "_buyeros_owned_api_test_support"
    if package not in sys.modules:
        module = ModuleType(package)
        module.__path__ = [str(Path(__file__).resolve().parents[2] / "api/tests")]
        sys.modules[package] = module
        sys.modules[package + ".policy_activation_target"] = gate
    return importlib.import_module(package + ".policy_activation_fixtures")


def fixture_research_binding(service, *, provider="fixture", account="owned-research-account", contract=None):
    from buyeros_api.api.policy_activation_schemas import ResearchProviderBinding
    from buyeros_api.db.icp import canonical_hash
    return ResearchProviderBinding(provider_name=provider, account_reference=account,
        contract_sha256=canonical_hash(contract or {"schema": "owned-research-fixture.v1", "service": service,
                                                     "provider": provider}).removeprefix("sha256:"))
