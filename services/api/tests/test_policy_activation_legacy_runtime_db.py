"""A specific historical reader is unsafe after scoped grants; not a live rollback rehearsal."""
import hashlib
import subprocess
from pathlib import Path
from types import ModuleType

from tests.policy_activation_fixtures import policy_case, owner_run
from tests.test_policy_activation_use_db import grant, context

BASE = "51532f19c19dd10ab3aa6c4a5fac87bc039856bb"


def test_base_51532_reader_is_unsafe_after_scoped_manual_grants(policy_case, record_property):
    grant(policy_case)
    root = Path(__file__).resolve().parents[3]
    source = subprocess.check_output(
        ["git", "show", BASE + ":services/api/buyeros_api/services/policy_service.py"],
        cwd=root, text=True, encoding="utf-8")
    legacy = ModuleType("buyeros_api.services._policy_reader_51532")
    legacy.__package__ = "buyeros_api.services"
    exec(compile(source, "owned-historical-reader-51532.py", "exec"), legacy.__dict__)
    record_property("historical_source_sha", BASE)
    record_property("historical_policy_reader_sha256", hashlib.sha256(source.encode()).hexdigest())
    async def run(session):
        from buyeros_api.services.policy_service import evaluate_current_policy
        subject = {"workspace_id": policy_case["workspace"], "project_id": policy_case["project"]}
        # The exact old reader admits the same permit without source/action proof.
        assert (await legacy.evaluate_current_policy(session, subject, "contact_research", policy_case["now"]))["allowed"]
        assert not (await evaluate_current_policy(session, subject, "contact_research", policy_case["now"]))["allowed"]
        assert (await evaluate_current_policy(session, subject, "contact_research", policy_case["now"],
                                              use_context=context(policy_case)))["allowed"]
    owner_run(policy_case, run, runtime=True)
