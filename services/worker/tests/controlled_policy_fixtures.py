"""Real controlled approval for worker fixtures, with no persistent credential changes."""
from pathlib import Path
import importlib
import sys
from types import ModuleType


def owned_policy_gate():
    gate = sys.modules.get("_buyeros_owned_policy_gate")
    if gate is None:
        import importlib.util
        path = Path(__file__).resolve().parents[2] / "api/tests/policy_activation_target.py"
        spec = importlib.util.spec_from_file_location("_buyeros_owned_policy_gate", path)
        gate = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = gate
        spec.loader.exec_module(gate)
    return gate


def api_fixture_helpers():
    # Loading the gate is not authorization; every fixture operation still
    # requires an independently verified endpoint registered before SQL.
    gate = owned_policy_gate()
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
