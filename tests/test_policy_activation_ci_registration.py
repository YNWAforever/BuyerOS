"""Exercise CI inventory consumers; synthetic XML is never runtime evidence."""
import importlib.util
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).resolve().parents[1]


class PolicyActivationCiRegistration(unittest.TestCase):
    def setUp(self):
        self.jobs = yaml.safe_load((ROOT / ".github/workflows/buyeros-ci.yml").read_text(encoding="utf-8"))["jobs"]

    def step(self, job, name):
        matches = [s for s in self.jobs[job]["steps"] if s.get("name") == name]
        self.assertEqual(len(matches), 1, f"missing/duplicate {name}")
        return matches[0]["run"]

    def test_policy_client_inventory_consumer_refuses_missing_duplicate_and_failed_cases(self):
        block = self.step("frontend", "Verify controlled policy client recovery")
        inline = [shlex.split(line.strip())[2] for line in block.splitlines() if line.strip().startswith("python -c ")]
        self.assertEqual(len(inline), 1)
        with tempfile.TemporaryDirectory(prefix="buyeros-policy-ci-") as directory:
            report = Path(directory) / "synthetic.xml"
            script = inline[0].replace("test-results/policy-activation-client.xml", report.as_posix())
            for count, duplicate, failed, passing in ((11, False, False, True), (10, False, False, False),
                    (0, False, False, False), (11, True, False, False), (11, False, True, False)):
                suite = ET.Element("testsuite")
                for index in range(count):
                    case = ET.SubElement(suite, "testcase", classname="policy-client",
                                         name="duplicate" if duplicate else str(index))
                    if failed and index == 0:
                        ET.SubElement(case, "failure")
                ET.ElementTree(suite).write(report)
                result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True)
                self.assertEqual(result.returncode == 0, passing)

    def test_new_policy_browser_uses_owned_runner_and_does_not_replace_native_inventory(self):
        block = self.step("browser-continuity", "Verify controlled policy activation without external work")
        commands = [shlex.split(line) for line in block.splitlines() if line.strip()]
        run = next(c for c in commands if "--run-suite" in c)
        self.assertEqual(run[run.index("--run-suite") + 1], "policy-browser")
        self.assertTrue(any("--expected-count" in c and c[c.index("--expected-count") + 1] == "8" for c in commands))
        native = self.step("browser-continuity", "Verify native lead workflow without provider activation")
        self.assertIn("--expected-count 19", native)
        self.assertIn("--run-suite native-browser", native)
        self.assertEqual(len(self.jobs), 12)

    def test_api_gate_has_no_application_database_url_fallback(self):
        block = self.step("api", "Create verified controlled policy test target")
        command = shlex.split(block.strip())
        self.assertIn("--github-env", command)
        self.assertTrue(command[-1].endswith("policy-api.target.json"))
        cleanup = self.step("api", "Clean exact controlled policy test target")
        self.assertIn("--cleanup", shlex.split(cleanup))

    def test_legacy_runtime_is_not_accepted_as_compatible_after_scoped_grants(self):
        spec = importlib.util.spec_from_file_location("policy_release_fixture", ROOT / "tests/test_release_readiness.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for missing in (False, True):
            manifest, receipts = module.candidate()
            if missing:
                receipts["items"].pop("rollback")
            else:
                receipts["items"]["rollback"]["data"]["compatible"] = False
            result = module.evaluate(manifest, receipts)
            self.assertFalse(result["promotable"])
            self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
