"""Resource recovery rechecks acceptance and budget without replaying deletion."""

import contextlib
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from research_workbench_entrypoint import iteration_resources as resources


class ResourceRevalidationTests(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory)
            state = root / "state"
            state.mkdir(mode=0o700)
            delivery = {
                "status": "cleaned",
                "ci": {"status": "passed"},
                "integrationCommit": "a" * 40,
                "cleanup": dict.fromkeys(
                    (
                        "featureWorktreeRemoved",
                        "integrationWorktreeRemoved",
                        "localBranchDeleted",
                        "remoteBranchDeleted",
                    ),
                    True,
                ),
            }
            previous = {
                "taskId": "task",
                "ok": True,
                "cache": {"ok": True},
                "status": "blocked",
                "blocked": [{"phase": "git"}],
            }
            values = {
                "receipt.json": previous,
                "git-finalization.json": {
                    "taskId": "task",
                    "candidateCommit": "a" * 40,
                    "status": "pending",
                    "restoreVerified": True,
                },
                "resources.json": {"roots": {str(root / "retired"): [1, 2]}},
            }
            for name, value in values.items():
                file = state / name
                file.write_text(json.dumps(value))
                file.chmod(0o600)
            driver = Mock()
            driver.inventory.return_value = {"containers": [], "images": [], "volumes": []}
            caches = Mock()
            caches.names = ("desktop-linux", "rwb-dev-builder")
            caches.maintenance.return_value = contextlib.nullcontext()
            budget = {"ok": True, "bytes": 128}
            plan = {"resources": [], "retired": {}}
            for name, value in {
                "state_paths": Mock(return_value=(root, state, delivery)),
                "git": Mock(return_value=""),
                "DockerResources": Mock(return_value=driver),
                "protections": Mock(return_value={}),
                "cleanup_locks": Mock(side_effect=lambda _: contextlib.nullcontext()),
                "operation_lock": Mock(side_effect=lambda _: contextlib.nullcontext()),
                "ManagedCaches": Mock(return_value=caches),
                "cache_budget": Mock(return_value=budget),
                "task_resource_plan": Mock(return_value=plan),
            }.items():
                stack.enter_context(patch.object(resources, name, value))
            yield root, state, delivery, driver, budget, plan

    def test_cleaned_pending_rechecks_budget_but_keeps_old_receipt_and_files(self):
        with self.fixture() as (_, state, _, driver, _, _):
            before = (state / "receipt.json").read_bytes()
            result = resources.revalidate_closeout(
                state, "task", {"cacheBudgetBytes": 20 * resources.GIB}
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["previousReceiptSha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual((state / "receipt.json").read_bytes(), before)
            driver.inventory.assert_called_once()
            resources.cache_budget.assert_called_once()

    def test_live_or_unaccepted_delivery_cannot_enter_revalidation(self):
        for status in ("ci_passed", "awaiting_ci", "started"):
            with self.subTest(status=status), self.fixture() as (_, state, delivery, driver, _, _):
                delivery["status"] = status
                with self.assertRaisesRegex(resources.ResourceError, "not_accepted"):
                    resources.revalidate_closeout(state, "task", {})
                driver.inventory.assert_not_called()

    def test_reappeared_root_and_remaining_docker_objects_are_not_deleted(self):
        with self.fixture() as (root, state, _, driver, _, _):
            (root / "retired").mkdir()
            with self.assertRaisesRegex(resources.ResourceError, "worktree_reappeared"):
                resources.revalidate_closeout(state, "task", {})
            driver.inventory.assert_not_called()
        with self.fixture() as (_, state, _, _, _, plan):
            plan["resources"] = [{"kind": "volume", "id": "owned", "action": "delete"}]
            with self.assertRaisesRegex(resources.ResourceError, "resources_remain"):
                resources.revalidate_closeout(state, "task", {})
            resources.cache_budget.assert_not_called()

    def test_budget_failure_keeps_prior_evidence(self):
        with self.fixture() as (_, state, _, _, budget, _):
            before = (state / "receipt.json").read_bytes()
            budget["ok"] = False
            with self.assertRaisesRegex(resources.ResourceError, "cache_over_budget"):
                resources.revalidate_closeout(
                    state, "task", {"cacheBudgetBytes": 20 * resources.GIB}
                )
            self.assertEqual((state / "receipt.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
