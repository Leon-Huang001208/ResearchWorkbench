"""Opt-in Mac Docker Desktop task/backup acceptance; never uses product data."""

import logging
import os
import tarfile
import tempfile
import unittest
from pathlib import Path

from research_workbench_entrypoint.docker_resources import (
    DockerResources,
    ResourceError,
    ResourceSession,
)


@unittest.skipUnless(os.environ.get("RWB_DOCKER_RESOURCE_LIVE") == "1", "explicit Docker opt-in")
class LiveResourceTests(unittest.TestCase):
    def setUp(self):
        Path("logs").mkdir(exist_ok=True)
        logging.basicConfig(filename="logs/docker-resources-live.log", level=logging.INFO)
        self.driver = DockerResources()
        self.before = self.driver.inventory()
        self.helper = self.driver.call(
            "image", "inspect", "--format", "{{.Id}}", "postgres:17-bookworm"
        ).strip()
        self.addCleanup(self.assert_no_leaks)

    def assert_no_leaks(self):
        self.assertEqual(self.before, self.driver.inventory())

    def test_backup_restores_real_content(self):
        with (
            tempfile.TemporaryDirectory(prefix="rwb-resource-archive-") as directory,
            ResourceSession(self.driver, "archive-check") as task,
        ):
            volume = task.volume()
            task.run(
                [
                    "--network",
                    "none",
                    "--entrypoint",
                    "/bin/sh",
                    "--mount",
                    f"type=volume,src={volume},dst=/data,volume-nocopy",
                    self.helper,
                    "-ec",
                    "printf lifecycle-proof > /data/proof",
                ]
            )
            archive = self.driver.archive(volume, Path(directory).resolve(), self.helper)
            self.assertTrue(archive["verified"])
            with tarfile.open(archive["path"]) as stream:
                self.assertEqual(stream.extractfile("./proof").read(), b"lifecycle-proof")

    def test_failed_helper_has_no_anonymous_volume_leak(self):
        with (
            self.assertRaises(ResourceError),
            ResourceSession(self.driver, "failure-check") as task,
        ):
            task.volume()
            task.run(["--network", "none", "--entrypoint", "/bin/sh", self.helper, "-c", "exit 7"])

    def test_test_image_name_labels_and_cleanup(self):
        with (
            tempfile.TemporaryDirectory(prefix="rwb-resource-build-") as directory,
            ResourceSession(self.driver, "image-check") as task,
        ):
            context = Path(directory).resolve()
            (context / "Dockerfile").write_text("FROM scratch\nCOPY proof /proof\n")
            (context / "proof").write_text("task-owned image")
            image = task.build(context)
            found = next(row for row in self.driver.inventory()["images"] if row["id"] == image)
            self.assertIn("research-workbench:test-image-check-" + task.task[:12], found["tags"])
            self.assertEqual(found["labels"]["io.research-workbench.task"], task.task)

    def test_interrupted_create_is_cleaned(self):
        original = self.driver.call

        def interrupt_after_create(*args, **kwargs):
            output = original(*args, **kwargs)
            if args[0] == "create":
                raise KeyboardInterrupt()
            return output

        self.driver.call = interrupt_after_create
        with (
            self.assertRaises(KeyboardInterrupt),
            ResourceSession(self.driver, "interrupt-check") as task,
        ):
            task.volume()
            task.run(["--network", "none", "--entrypoint", "/bin/sh", self.helper, "-c", "exit 0"])


if __name__ == "__main__":
    unittest.main()
