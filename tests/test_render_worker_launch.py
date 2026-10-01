"""Deployment launch boundaries; no database, broker or provider is contacted."""

import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


LAUNCHER = Path(__file__).resolve().parents[1] / "scripts/run-render-worker.py"


def load_launcher():
    assert LAUNCHER.is_file(), "Render runtime launcher is missing"
    spec = importlib.util.spec_from_file_location("render_worker_launch", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runtime_environment():
    return {
        "BUYEROS_WORKER_RUNTIME_ENABLED": "true",
        "BUYEROS_ENVIRONMENT": "production",
        "BUYEROS_DATABASE_URL": "postgresql://buyeros_worker_runtime:fixture-password@db.example.invalid/neondb?sslmode=require",
        "BUYEROS_BROKER_URL": "redis://broker.example.invalid:6379/0",
    }


class RenderWorkerLaunchTests(unittest.TestCase):
    def test_unconfigured_service_stays_in_standby(self):
        launcher = load_launcher()
        for role in ("worker", "dispatcher"):
            with self.subTest(role=role):
                self.assertIsNone(launcher.launch_command(role, {}))

    def test_activation_must_be_an_explicit_boolean(self):
        launcher = load_launcher()
        for value in ("yes", "1", "", "TRUE"):
            with self.subTest(value=value):
                with self.assertRaises(launcher.ConfigurationError):
                    launcher.launch_command("worker", {"BUYEROS_WORKER_RUNTIME_ENABLED": value})

    def test_activation_requires_production_and_both_connections(self):
        launcher = load_launcher()
        for key in ("BUYEROS_ENVIRONMENT", "BUYEROS_DATABASE_URL", "BUYEROS_BROKER_URL"):
            with self.subTest(key=key):
                environment = runtime_environment()
                del environment[key]
                with self.assertRaises(launcher.ConfigurationError):
                    launcher.launch_command("worker", environment)

    def test_api_owner_and_unencrypted_database_connections_are_rejected(self):
        launcher = load_launcher()
        invalid_connections = (
            "postgresql://buyeros_api:fixture-password@db.example.invalid/neondb?sslmode=require",
            "postgresql://neondb_owner:fixture-password@db.example.invalid/neondb?sslmode=require",
            "postgresql://buyeros_worker_runtime:fixture-password@db.example.invalid/neondb",
            "postgresql://buyeros_worker_runtime:fixture-password@localhost/neondb?sslmode=require",
        )
        for connection in invalid_connections:
            with self.subTest(connection_type=invalid_connections.index(connection)):
                environment = runtime_environment()
                environment["BUYEROS_DATABASE_URL"] = connection
                with self.assertRaises(launcher.ConfigurationError):
                    launcher.launch_command("dispatcher", environment)

    def test_broker_loopback_or_wrong_protocol_is_rejected(self):
        launcher = load_launcher()
        for connection in ("redis://localhost:6379/0", "redis://127.0.0.1:6379/0", "https://broker.example.invalid"):
            with self.subTest(connection_type=connection.split(":", 1)[0]):
                environment = runtime_environment()
                environment["BUYEROS_BROKER_URL"] = connection
                with self.assertRaises(launcher.ConfigurationError):
                    launcher.launch_command("worker", environment)

    def test_worker_runs_the_canonical_celery_app_with_recovery_and_bounded_concurrency(self):
        launcher = load_launcher()
        command = launcher.launch_command("worker", runtime_environment())
        self.assertEqual(command[:5], [sys.executable, "-m", "celery", "-A", "buyeros_worker.app:celery_app"])
        self.assertIn("--beat", command)
        self.assertIn("--concurrency=1", command)
        self.assertIn("--prefetch-multiplier=1", command)

    def test_dispatcher_uses_the_existing_continuous_bounded_outbox_cli(self):
        launcher = load_launcher()
        command = launcher.launch_command("dispatcher", runtime_environment())
        self.assertEqual(command[:4], [sys.executable, "-m", "buyeros_worker.cli", "dispatch"])
        self.assertIn("--loop", command)
        self.assertEqual(command[command.index("--max-total") + 1], "10")
        self.assertEqual(command[command.index("--time-budget-seconds") + 1], "10")

    def test_check_mode_never_connects_or_executes_and_does_not_print_credentials(self):
        launcher = load_launcher()
        output = io.StringIO()
        with patch.dict(os.environ, runtime_environment(), clear=True), \
                patch.object(launcher.os, "execv") as execute, \
                patch("socket.socket", side_effect=AssertionError("unexpected connection")), \
                contextlib.redirect_stdout(output):
            result = launcher.main(["worker", "--check"])
        self.assertEqual(result, 0)
        execute.assert_not_called()
        self.assertIn("configuration verified", output.getvalue())
        self.assertNotIn("fixture-password", output.getvalue())
        self.assertNotIn("db.example.invalid", output.getvalue())

    def test_invalid_configuration_exits_before_execution_without_disclosing_a_dsn(self):
        launcher = load_launcher()
        environment = runtime_environment()
        environment["BUYEROS_DATABASE_URL"] = "postgresql://neondb_owner:fixture-password@db.example.invalid/neondb"
        output = io.StringIO()
        with patch.dict(os.environ, environment, clear=True), \
                patch.object(launcher.os, "execv") as execute, \
                contextlib.redirect_stderr(output):
            result = launcher.main(["dispatcher"])
        self.assertEqual(result, 2)
        execute.assert_not_called()
        self.assertNotIn("fixture-password", output.getvalue())
        self.assertNotIn("db.example.invalid", output.getvalue())


if __name__ == "__main__":
    unittest.main()
