"""DataHub owns frozen Hot copies in genuine target-session snapshot directories."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.research_web.store import Store, StoreError
from app.research_web.datahub.snapshots import Snapshots


def bundle(instance, material):
    raw = b"complete stored source response"
    value = {"materialId": material, "revision": 1, "title": "Official", "excerpt": "Stored full text",
             "originalUrl": "https://example.com/source", "publishedAt": None, "acquiredAt": "2026-10-08T00:00:00Z",
             "contentHash": "b" * 64, "raw": {"key": "raw:" + material, "contentHash": hashlib.sha256(raw).hexdigest()}}
    normalized = json.dumps(value).encode()
    objects = {"raw:" + material: raw, "material:" + material + ":1": normalized}
    manifest = {"schemaVersion": 1, "instanceId": instance, "briefId": str(uuid4()), "version": 1,
                "materialIds": [material], "cutoff": "2026-10-09T00:00:00Z", "timezone": "Asia/Shanghai",
                "briefContentHash": "a" * 64, "briefContext": {}, "totalBytes": len(raw) + len(normalized),
                "materials": [{"materialId": material, "revision": 1, "contentHash": "b" * 64,
                               "normalizedObject": "material:" + material + ":1", "rawObject": "raw:" + material}],
                "objects": [{"key": key, "filename": "raw-" + material + ".bin" if key.startswith("raw:") else "material-" + material + "-r1.json",
                             "format": "application/octet-stream" if key.startswith("raw:") else "application/json",
                             "bytes": len(data), "contentHash": hashlib.sha256(data).hexdigest()} for key, data in objects.items()]}
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return {"manifest": manifest, "manifestBytes": canonical, "manifestHash": hashlib.sha256(canonical).hexdigest(), "objects": objects}


class HotSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name).resolve())
        self.snapshots = Snapshots(self.store)
        self.instance, self.run, self.material = str(uuid4()), str(uuid4()), str(uuid4())
        self.data = bundle(self.instance, self.material)
        # Native acknowledgement is isolated in unit tests; real DSH evidence is a separate gate.
        self.row = self.store.create("fingpt", "Owned target")
        self.row.update(created=True, hot_origin={"runId": self.run, "instanceId": self.instance,
                                               "manifestHash": self.data["manifestHash"]})
        self.store.save()

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_copy_replay_and_generic_handoff_copy_keep_old_times_and_originals(self):
        original = self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.assertEqual(self.snapshots.publish_hot(self.row["id"], self.run, self.data)["dataset_id"], original["dataset_id"])
        self.assertEqual(original["retrieved_at"], "2026-10-08T00:00:00+00:00")
        for item in self.data["manifest"]["objects"]:
            self.assertEqual(self.snapshots.read(self.row["id"], original["dataset_id"], item["filename"]), self.data["objects"][item["key"]])
        target = self.store.create("claw", "Another genuine target")
        target["created"] = True
        self.store.save()
        copied = self.snapshots.copy_selected(self.row["id"], target["id"], [original["dataset_id"]])[0]
        self.assertEqual(copied["origin_dataset_id"], original["dataset_id"])
        self.assertEqual(copied["hot"]["manifestHash"], self.data["manifestHash"])
        self.assertEqual(copied["retrieved_at"], original["retrieved_at"])

    def test_wrong_owner_uncreated_session_tamper_and_path_injection_fail_closed(self):
        self.row["created"] = False
        with self.assertRaises(StoreError):
            self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.row["created"] = True
        with self.assertRaises(StoreError):
            self.snapshots.publish_hot(self.row["id"], str(uuid4()), self.data)
        self.data["objects"]["raw:" + self.material] = b"corrupt"
        with self.assertRaises(StoreError):
            self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.assertFalse((self.store.root / ".control" / "snapshots").exists())

    def test_public_commit_interruption_does_not_publish_private_catalog_and_same_request_recovers(self):
        import app.research_web.datahub.snapshots as module
        real = module.rename_directory
        calls = 0
        def interrupted(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt("synthetic process interruption")
            return real(*args)
        with patch.object(module, "rename_directory", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.assertEqual(self.snapshots.ids(self.row["id"]), [])
        result = self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.assertEqual(self.snapshots.ids(self.row["id"]), [result["dataset_id"]])

    def test_conflicting_preexisting_staging_is_preserved(self):
        from app.research_web.datahub.frozen_archive import build_archive
        did, _, _, _ = build_archive(self.row["id"], self.run, self.data, "2026-10-12T00:00:00Z")
        pending = self.store.root / ".control/snapshots" / self.row["id"] / (".pending-" + did)
        pending.mkdir(parents=True, mode=0o700)
        conflict = pending / "manifest.json"
        conflict.write_bytes(b"foreign bytes")
        conflict.chmod(0o600)
        with self.assertRaises(StoreError):
            self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.assertEqual(conflict.read_bytes(), b"foreign bytes")

    def test_post_commit_read_failure_preserves_catalog_and_replay(self):
        with patch.object(self.snapshots, "detail", side_effect=StoreError("synthetic read failure")):
            with self.assertRaises(StoreError):
                self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.assertEqual(len(self.snapshots.ids(self.row["id"])), 1)
        recovered = self.snapshots.publish_hot(self.row["id"], self.run, self.data)
        self.assertEqual(self.snapshots.ids(self.row["id"]), [recovered["dataset_id"]])
