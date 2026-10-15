"""Exercise registered CI guards with native inventories; synthetic reports test guards only."""
import importlib.util
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"lead-evidence.spec.ts": 5, "lead-preparations.spec.ts": 4,
            "lead-workflow.spec.ts": 4, "pilot-budget.spec.ts": 4}


class LeadWorkflowCIRegistration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/buyeros-ci.yml").read_text(encoding="utf-8")
        cls.tmp = tempfile.TemporaryDirectory(prefix="buyeros-lead-ci-")
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.directory = Path(cls.tmp.name)
        cls.inventories = {}
        for key, config, extra in [
            ("lead", "playwright.lead-workflow.config.ts", []),
            ("source", "playwright.buyer.config.ts", ["tests/e2e/buyer-source-checks.spec.ts"]),
        ]:
            result = subprocess.run(["node", "node_modules/@playwright/test/cli.js", "test", "--config", config,
                                     *extra, "--list", "--reporter=json"], cwd=ROOT, capture_output=True)
            if result.returncode:
                raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
            path = cls.directory / f"{key}-discovery.json"
            path.write_bytes(result.stdout)
            cls.inventories[key] = path
        spec = importlib.util.spec_from_file_location("lead_ci_checker", ROOT / "scripts/check-c61-evidence.py")
        cls.checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.checker)

    def block(self, name):
        marker = f"      - name: {name}\n"
        self.assertEqual(self.workflow.count(marker), 1, f"required CI step missing: {name}")
        return self.workflow.split(marker, 1)[1].split("\n      - ", 1)[0]

    def test_native_inventories_preserve_17_new_and_five_source_cases(self):
        names = self.checker._built_playwright_names(self.inventories["lead"].read_bytes(), "lead")
        actual = {file: sum(name.startswith(file + "::") for name in names) for file in EXPECTED}
        self.assertEqual(actual, EXPECTED)
        source = self.checker._built_playwright_names(self.inventories["source"].read_bytes(), "source")
        self.assertEqual(len(source), 5)
        self.assertEqual({name.split("::")[0] for name in source}, {"buyer-source-checks.spec.ts"})

    def test_registered_browser_commands_require_execution_and_exact_junit(self):
        for key, name, config in [
            ("lead", "Verify native lead workflow without provider activation", "playwright.lead-workflow.config.ts"),
            ("source", "Verify original buyer source checks", "playwright.buyer.config.ts"),
        ]:
            block = self.block(name)
            commands = [shlex.split(line.strip()) for line in block.splitlines() if line.strip().startswith(("pnpm ", "python "))]
            browser = [cmd for cmd in commands if cmd[:4] == ["pnpm", "exec", "playwright", "test"]]
            self.assertEqual(len(browser), 2)
            self.assertTrue(all(config in cmd for cmd in browser))
            self.assertEqual(sum("--list" in cmd for cmd in browser), 1)
            guards = [cmd for cmd in commands if cmd[:2] == ["python", "scripts/check-required-tests.py"]]
            self.assertEqual(len(guards), 2)
            execution = next(cmd for cmd in guards if "--junit" in cmd)
            names = self.checker._built_playwright_names(self.inventories[key].read_bytes(), key)
            report = self.directory / f"{key}-synthetic-guard-only.xml"
            suite = ET.Element("testsuite")
            for native in sorted(names):
                file, title = native.split("::", 1)
                ET.SubElement(suite, "testcase", classname=file, name=title)
            ET.ElementTree(suite).write(report, encoding="utf-8")
            argv = execution[:]
            argv[0] = sys.executable
            argv[argv.index("--playwright-discovery") + 1] = str(self.inventories[key])
            argv[argv.index("--junit") + 1] = str(report)
            passed = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            for mutation in ("skip", "missing", "empty"):
                broken = ET.fromstring(ET.tostring(suite))
                if mutation == "skip":
                    ET.SubElement(broken[0], "skipped")
                elif mutation == "missing":
                    broken.remove(broken[0])
                else:
                    broken.clear()
                ET.ElementTree(broken).write(report, encoding="utf-8")
                rejected = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
                self.assertNotEqual(rejected.returncode, 0, mutation)

    def test_node_client_suite_runs_with_nonempty_junit_guard(self):
        block = self.block("Verify native lead intent client recovery")
        commands = [shlex.split(line.strip()) for line in block.splitlines() if line.strip().startswith(("node ", "python "))]
        node = next(cmd for cmd in commands if cmd[0] == "node")
        self.assertIn("--test", node)
        self.assertIn("tests/lead-intents.test.mjs", node)
        output = next(value.split("=", 1)[1] for value in node if value.startswith("--test-reporter-destination="))
        guard = next(cmd for cmd in commands if cmd[:2] == ["python", "scripts/check-required-tests.py"])
        self.assertEqual(guard[guard.index("--junit") + 1], output)

    def test_node_inventory_cannot_pass_with_only_an_empty_file_wrapper(self):
        block = self.block("Verify native lead intent client recovery")
        inline = [shlex.split(line.strip()) for line in block.splitlines()
                  if line.strip().startswith("python -c ")]
        self.assertEqual(len(inline), 1, "Node suite requires its six distinct native cases")
        report = self.directory / "node-synthetic-guard-only.xml"
        script = inline[0][2].replace("artifacts/lead-workflow/lead-client.xml", report.as_posix())
        for count, expected in [(6, 0), (1, 1), (0, 1)]:
            suite = ET.Element("testsuite")
            for number in range(count):
                ET.SubElement(suite, "testcase", classname="node-native", name=f"case-{number}")
            ET.ElementTree(suite).write(report, encoding="utf-8")
            result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True)
            self.assertEqual(result.returncode == 0, expected == 0)

    def test_all_original_required_jobs_and_pg16_preload_remain(self):
        jobs = set(re.findall(r"^  ([a-z][a-z0-9-]*):$", self.workflow.split("jobs:", 1)[1], re.MULTILINE))
        self.assertEqual(jobs, {"release-readiness", "frontend", "cloudflare-controller", "api", "worker",
            "owned-worker-capacity", "browser-smoke", "browser-zoom", "cloudflare-staff-acceptance",
            "browser-continuity", "audit-fixes", "c61-evidence-checker"})
        preload = re.findall(r"run: (docker pull [^\n]+:16)\n", self.workflow)
        self.assertEqual(len(preload), 2)
        self.assertEqual(len(set(preload)), 1)


if __name__ == "__main__":
    unittest.main()
