"""Resource disposal must protect data and recheck exact identities."""

import copy
import tempfile
import unittest
from pathlib import Path

from research_workbench_entrypoint.docker_resources import (
    ResourceError,
    ResourceSession,
    apply_plan,
    plan_resources,
)


def inventory():
    return {
        "containers": [
            {
                "id": "c1",
                "image": "i1",
                "name": "test",
                "running": False,
                "labels": {
                    "io.research-workbench.project": "research-workbench",
                    "io.research-workbench.completed": "true",
                    "io.research-workbench.lifetime": "temporary",
                },
                "volumes": ["v1"],
                "binds": [],
            }
        ],
        "images": [
            {
                "id": "i1",
                "tags": ["research-workbench:test-db-task"],
                "labels": {
                    "io.research-workbench.project": "research-workbench",
                    "io.research-workbench.completed": "true",
                    "io.research-workbench.lifetime": "temporary",
                },
            }
        ],
        "volumes": [{"id": "v1", "labels": {}, "created": "today"}],
    }


class Driver:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def inventory(self):
        return copy.deepcopy(self.data)

    def remove(self, kind, identity):
        self.calls.append((kind, identity))
        key = {"container": "containers", "volume": "volumes", "image": "images"}[kind]
        self.data[key] = [row for row in self.data[key] if row["id"] != identity]

    def archive(self, identity, directory, helper):
        self.calls.append(("archive", identity))
        return {"verified": True, "sha256": "digest"}


def disposable_plan(data):
    return plan_resources(data, {}, {"volume:v1": "test fixture complete"})


class ResourcePolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name).resolve()

    def test_protected_install_and_stopped_reference(self):
        data = inventory()
        plan = plan_resources(data, {"images": ["i1"], "installations": []}, {})
        assert all(row["action"] == "keep" for row in plan["resources"])

    def test_unconfirmed_create_timeout_never_reports_cleaned(self):
        class UncertainDriver:
            def call(self, *args, **kwargs):
                raise ResourceError("docker_resource_command_timeout")

            def resolve(self, *args):
                return None

        task = ResourceSession(UncertainDriver(), "timeout-check")
        with self.assertRaises(ResourceError):
            task.volume()
        with self.assertRaisesRegex(ResourceError, "resource_session_cleanup_failed"):
            task.cleanup()
        self.assertTrue(task.resources)

    def test_explicit_old_fixture_can_be_removed_while_rollback_image_is_kept(self):
        data = inventory()
        plan = plan_resources(
            data, {"images": ["i1"]}, {"container:c1": "obsolete isolated fixture"}
        )
        assert plan["resources"][0]["action"] == "delete"
        assert plan["resources"][-1]["action"] == "keep"

    def test_unfinished_temporary_task_is_protected(self):
        data = inventory()
        del data["containers"][0]["labels"]["io.research-workbench.completed"]
        assert all(r["action"] == "keep" for r in plan_resources(data, {}, {})["resources"])

    def test_cleanup_lock_blocks_install_publication(self):
        from research_workbench_entrypoint.docker_resources import cleanup_locks
        from research_workbench_entrypoint.runtime_mode import RuntimeModeError, RuntimeModeStore

        home = self.tmp_path / "home"
        home.mkdir(mode=0o700)
        store = RuntimeModeStore(home)
        store.write("native")
        with (
            cleanup_locks([home]),
            self.assertRaises(RuntimeModeError),
            RuntimeModeStore(home)._write_lock(),
        ):
            self.fail("publication acquired cleanup-held lock")

    def test_shuffled_plan_still_deletes_container_before_volume(self):
        data = inventory()
        driver = Driver(data)
        plan = disposable_plan(data)
        plan["resources"].reverse()
        assert apply_plan(driver, plan, {}, self.tmp_path, "helper")["ok"]
        assert driver.calls[0] == ("container", "c1")

    def test_invalid_preview_is_rejected_before_any_mutation(self):
        for plan in (
            None,
            [],
            {"schema_version": 1, "retired": {}, "resources": [None]},
            {"schema_version": 1, "retired": {}, "resources": [{"kind": []}]},
            {"schema_version": 1, "retired": {}, "resources": [{"kind": "image", "action": []}]},
        ):
            with self.subTest(plan=plan):
                driver = Driver(inventory())
                with self.assertRaises(ResourceError):
                    apply_plan(driver, plan, {}, self.tmp_path, "helper")
                self.assertEqual(driver.calls, [])

    def test_unknown_and_persistent_are_never_implicitly_retired(self):
        data = inventory()
        data["containers"][0]["labels"] = {}
        plan = plan_resources(data, {}, {})
        assert all(row["action"] == "keep" for row in plan["resources"])
        data["containers"][0]["labels"] = {
            "io.research-workbench.project": "research-workbench",
            "io.research-workbench.lifetime": "persistent",
        }
        assert plan_resources(data, {}, {})["resources"][0]["action"] == "keep"

    def test_retirement_requires_exact_audited_resource(self):
        data = inventory()
        data["containers"][0]["labels"] = {"rwb.hot.instance": "instance"}
        plan = plan_resources(
            data,
            {},
            {
                "container:c1": "completed fixture; source absent",
                "volume:v1": "completed fixture; archive required",
                "image:i1": "old fixture build",
            },
        )
        assert [row["action"] for row in plan["resources"]] == [
            "delete",
            "archive-delete",
            "delete",
        ]

    def test_apply_archives_before_volume_delete_and_is_repeatable(self):
        tmp_path = self.tmp_path
        data = inventory()
        driver = Driver(data)
        plan = disposable_plan(data)
        receipt = apply_plan(driver, plan, {}, tmp_path, "helper")
        assert receipt["ok"]
        assert driver.calls == [
            ("container", "c1"),
            ("archive", "v1"),
            ("volume", "v1"),
            ("image", "i1"),
        ]
        assert apply_plan(driver, plan, {}, tmp_path, "helper")["ok"]

    def check_changed(self, change):
        tmp_path = self.tmp_path
        data = inventory()
        plan = disposable_plan(data)
        protection = {}
        if change == "running":
            data["containers"][0]["running"] = True
        elif change == "label":
            data["containers"][0]["labels"]["foreign"] = "yes"
        elif change == "new-reference":
            foreign = copy.deepcopy(data["containers"][0])
            foreign.update(id="foreign", labels={}, volumes=["v1"])
            data["containers"].append(foreign)
        else:
            protection = {"images": ["i1"]}
        driver = Driver(data)
        receipt = apply_plan(driver, plan, protection, tmp_path, "helper")
        assert not receipt["ok"]
        assert not any(kind in {"volume", "image"} for kind, _ in driver.calls)

    def test_backup_failure_preserves_source(self):
        tmp_path = self.tmp_path
        data = inventory()
        driver = Driver(data)

        def fail(*args):
            raise ResourceError("archive_failed")

        driver.archive = fail
        receipt = apply_plan(driver, disposable_plan(data), {}, tmp_path, "helper")
        assert not receipt["ok"]
        assert data["volumes"] and data["images"]

    def test_apply_refuses_changed_resources(self):
        for change in ("running", "label", "new-reference", "new-protection"):
            with self.subTest(change=change):
                self.check_changed(change)


if __name__ == "__main__":
    unittest.main()
