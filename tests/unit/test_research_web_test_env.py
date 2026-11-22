"""Finite offline checks for the shared development test environment helper."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_SPEC = importlib.util.spec_from_file_location(
    "research_web_test_env",
    Path(__file__).resolve().parents[2] / "scripts/research_web_test_env.py",
)
assert _SPEC is not None and _SPEC.loader is not None
helper = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(helper)


class SharedTestEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "checkout"
        (self.project / "requirements").mkdir(parents=True)
        (self.project / "requirements/web.lock").write_text("pydantic==2.0\n")
        (self.project / "requirements/research-test.in").write_text("pytest>=7.4\n")
        self.root = Path(self.temporary.name) / "shared"

    def test_fingerprint_is_checkout_independent_and_invalidates_inputs(self):
        first = helper.fingerprint(self.project)
        other = Path(self.temporary.name) / "other"
        (other / "requirements").mkdir(parents=True)
        for source in (self.project / "requirements").iterdir():
            (other / "requirements" / source.name).write_bytes(source.read_bytes())
        self.assertEqual(first, helper.fingerprint(other))
        for name in ("web.lock", "research-test.in"):
            source = other / "requirements" / name
            original = source.read_text()
            source.write_text(original + "# change\n")
            self.assertNotEqual(first, helper.fingerprint(other))
            source.write_text(original)
        with patch.object(helper.platform, "machine", return_value="different-architecture"):
            self.assertNotEqual(first, helper.fingerprint(other))

    def test_check_is_read_only(self):
        self.assertFalse(helper.inspect(self.project, self.root)["healthy"])
        self.assertFalse(self.root.exists())

    def test_healthy_environment_skips_all_installs_and_lock_creation(self):
        with (
            patch.object(helper, "health", return_value=True),
            patch.object(helper, "run_logged") as run,
        ):
            result = helper.prepare(self.project, self.root)
        self.assertTrue(result["reused"])
        run.assert_not_called()
        self.assertFalse(self.root.exists())

    def test_concurrent_or_unknown_lock_is_preserved(self):
        self.root.mkdir()
        lock = self.root / (helper.fingerprint(self.project) + ".lock")
        lock.write_text("unknown-owner")
        with self.assertRaisesRegex(helper.EnvError, "PREPARE_LOCKED"):
            helper.prepare(self.project, self.root)
        self.assertEqual(lock.read_text(), "unknown-owner")

    def test_unhealthy_existing_environment_is_preserved(self):
        env = self.root / helper.fingerprint(self.project)
        env.mkdir(parents=True)
        sentinel = env / "user-data"
        sentinel.write_text("preserve")
        with self.assertRaisesRegex(helper.EnvError, "EXISTING_ENV_UNHEALTHY"):
            helper.prepare(self.project, self.root)
        self.assertEqual(sentinel.read_text(), "preserve")
        self.assertEqual(list(self.root.glob("*.lock")), [])

    def test_failed_install_preserves_evidence_and_releases_own_lock(self):
        with (
            patch.object(helper, "run_logged", side_effect=helper.EnvError("INSTALL_FAILED")),
            self.assertRaisesRegex(helper.EnvError, "INSTALL_FAILED"),
        ):
            helper.prepare(self.project, self.root)
        env = self.root / helper.fingerprint(self.project)
        self.assertEqual(
            json.loads((env / "owner.json").read_text())["lifecycle"], "project-shared"
        )
        self.assertEqual(list(self.root.glob("*.lock")), [])

    def test_prepare_records_completion_and_keeps_runtime_hash_install(self):
        with (
            patch.object(helper, "run_logged") as run,
            patch.object(helper, "health", side_effect=[False, False, True]),
        ):
            result = helper.prepare(self.project, self.root)
        self.assertTrue(result["healthy"])
        self.assertFalse(result["reused"])
        self.assertEqual(run.call_count, 3)
        self.assertIn("--require-hashes", run.call_args_list[1].args[0])
        self.assertIn("--no-deps", run.call_args_list[1].args[0])
        self.assertNotIn("-e", run.call_args_list[2].args[0])
        for call in run.call_args_list:
            self.assertEqual(call.args[0][1], "-I")
        for call in run.call_args_list[1:]:
            self.assertIn("--isolated", call.args[0])
        self.assertEqual((Path(result["environment"]) / "prepared").read_text(), result["digest"])

    def test_child_environment_drops_install_and_python_redirection(self):
        pollution = {
            "PIP_TARGET": "/outside/target",
            "PIP_PREFIX": "/outside/prefix",
            "PIP_USER": "1",
            "PIP_CONFIG_FILE": "/outside/pip.conf",
            "PYTHONPATH": "/outside/modules",
            "PYTHONHOME": "/outside/python",
            "VIRTUAL_ENV": "/outside/venv",
            "__PYVENV_LAUNCHER__": "/outside/python",
        }
        with (
            patch.dict(os.environ, pollution),
            patch.object(
                helper.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ) as run,
        ):
            helper.run_logged(
                [sys.executable, "-I", "-c", "pass"], Path(self.temporary.name) / "child.log"
            )
        child_env = run.call_args.kwargs["env"]
        for key in pollution:
            if key != "PIP_CONFIG_FILE":
                self.assertNotIn(key, child_env)
        self.assertEqual(child_env["PIP_CONFIG_FILE"], os.devnull)

    def test_pip_configuration_cannot_redirect_install_target(self):
        config = Path(self.temporary.name) / "pip.conf"
        config.write_text(
            "[global]\ntarget = /outside/config-target\nprefix = /outside/config-prefix\nuser = true\n"
        )
        log = Path(self.temporary.name) / "pip-config.log"
        with patch.dict(
            os.environ, {"PIP_CONFIG_FILE": str(config), "PIP_TARGET": "/outside/env-target"}
        ):
            helper.run_logged(
                [sys.executable, "-I", "-m", "pip", "--isolated", "config", "list"], log
            )
        self.assertNotIn("/outside/", log.read_text())

    def test_health_is_bounded_and_does_not_import_application(self):
        env = self.root / "env"
        env.mkdir(parents=True)
        (env / "owner.json").write_text(
            json.dumps(
                {"project": "research-workbench", "lifecycle": "project-shared", "digest": "key"}
            )
        )
        (env / "prepared").write_text("key")
        with patch.object(
            helper.subprocess, "run", side_effect=subprocess.TimeoutExpired("python", 20)
        ) as run:
            self.assertFalse(helper.health(env, "key"))
        self.assertEqual(run.call_args.kwargs["timeout"], 20)
        self.assertEqual(run.call_args.args[0][-1], helper.HEALTH_CODE)
        self.assertNotIn("app.", helper.HEALTH_CODE)
        for module in ("pytest_cov", "ruff", "black", "isort", "mypy"):
            self.assertIn(module, helper.HEALTH_CODE)
        with patch.object(
            helper.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)
        ):
            self.assertFalse(helper.health(env, "key"))


if __name__ == "__main__":
    unittest.main()
