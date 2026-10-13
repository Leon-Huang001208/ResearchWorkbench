"""A native session accepted before reply loss is reconciled, never recreated."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.research_web.client import RuntimeFailure
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError
from app.research_web.hot_handoff import prepare_hot_handoff
from tests.research_web.test_hot_snapshot_publication import bundle


class Native:
    def __init__(self):
        self.items = {}
        self.creations = 0
        self.lose_reply = True

    async def rpc(self, operation, params):
        if operation == "session.list":
            return {"items": list(self.items.values())}
        if operation == "session.create":
            assert params["agentPreset"] == "research-hot-frozen"
            self.creations += 1
            self.items[params["sessionId"]] = {"sessionId": params["sessionId"], "cwd": params["cwd"], "running": False}
            if self.lose_reply:
                self.lose_reply = False
                raise RuntimeFailure("Synthetic lost creation reply")
            return {}
        if operation in {"session.selectModel", "session.rename"}:
            return {}
        raise AssertionError(operation)

    async def close(self):
        pass


class HotSessionRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.keys = {}
        self.patches = [patch("keyring.get_password", side_effect=lambda service, account: self.keys.get((service, account))),
                        patch("keyring.set_password", side_effect=lambda service, account, value: self.keys.__setitem__((service, account), value)),
                        patch("keyring.delete_password", side_effect=lambda service, account: self.keys.pop((service, account), None))]
        for item in self.patches:
            item.start()
        self.native = Native()
        self.service = ResearchService(self.native, Store(self.root), owned=True)
        self.record = {"runId": str(uuid4()), "sessionId": str(uuid4()), "targetMode": "fingpt",
                       "instanceId": str(uuid4()), "evidenceManifestHash": "a" * 64}

    async def asyncTearDown(self):
        await self.service.close()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    async def test_lost_reply_and_host_restart_preserve_reserved_identity_and_one_native_creation(self):
        with self.assertRaises(RuntimeFailure):
            await self.service.ensure_hot_session(self.record)
        saved = self.service.store.session(self.record["sessionId"])
        self.assertFalse(saved["created"])
        restarted = ResearchService(self.native, Store(self.root), owned=True)
        try:
            result = await restarted.ensure_hot_session(self.record)
            self.assertEqual(result["id"], self.record["sessionId"])
            self.assertTrue(restarted.store.session(result["id"])["created"])
            self.assertEqual(self.native.creations, 1)
            await restarted.ensure_hot_session(self.record)
            self.assertEqual(self.native.creations, 1)
        finally:
            await restarted.close()

    async def test_unknown_absence_does_not_automatically_resubmit_and_foreign_or_deleted_owner_rejects(self):
        with self.assertRaises(RuntimeFailure):
            await self.service.ensure_hot_session(self.record)
        self.native.items.clear()
        with self.assertRaisesRegex(RuntimeFailure, "未知"):
            await self.service.ensure_hot_session(self.record)
        self.assertEqual(self.native.creations, 1)
        with self.assertRaises(StoreError):
            await self.service.ensure_hot_session({**self.record, "runId": str(uuid4())})

    async def test_preexisting_native_identity_and_wrong_native_cwd_cannot_be_adopted(self):
        sid = self.record["sessionId"]
        self.native.items[sid] = {"sessionId": sid, "cwd": "/foreign", "running": False}
        with self.assertRaises(RuntimeFailure):
            await self.service.ensure_hot_session(self.record)
        self.assertEqual(self.native.creations, 0)

    async def test_unknown_native_creation_without_cwd_remains_unconfirmed(self):
        with self.assertRaises(RuntimeFailure):
            await self.service.ensure_hot_session(self.record)
        self.native.items[self.record["sessionId"]].pop("cwd")
        with self.assertRaises(RuntimeFailure):
            await self.service.ensure_hot_session(self.record)
        self.assertFalse(self.service.store.session(self.record["sessionId"])["created"])
        self.assertEqual(self.native.creations, 1)

    async def test_handoff_reply_loss_recovery_publishes_one_snapshot_without_starting_execution(self):
        evidence = bundle(self.record["instanceId"], str(uuid4()))
        self.record["evidenceManifestHash"] = evidence["manifestHash"]
        self.record.update(briefId=evidence["manifest"]["briefId"], version=1, materialIds=evidence["manifest"]["materialIds"],
                           revision=1, state="prepared", requestId=str(uuid4()))
        record = self.record
        class Hot:
            async def call(self, operation, *args, **kwargs):
                if operation == "prepare_research_run":
                    return dict(record)
                if operation == "research_evidence":
                    return evidence
                if operation == "advance_research_run":
                    params = args[0]
                    self.owner.assertEqual(params["expectedRevision"], record["revision"])
                    record.update({key: value for key, value in params.items() if key not in {"expectedRevision"}})
                    record["revision"] += 1
                    return dict(record)
                raise AssertionError(operation)
        hot = Hot()
        hot.owner = self
        first = await prepare_hot_handoff(self.service, hot, {}, record["requestId"])
        self.assertEqual(first["state"], "session_outcome_unknown")
        ready = await prepare_hot_handoff(self.service, hot, {}, record["requestId"])
        self.assertEqual(ready["state"], "snapshot_ready")
        self.assertFalse(ready["executionStarted"])
        self.assertEqual(self.native.creations, 1)
        self.assertTrue((self.service.store.directory(record["sessionId"]) / "inputs/hot-context.json").is_file())
        repeated = await prepare_hot_handoff(self.service, hot, {}, record["requestId"])
        self.assertEqual(repeated["datasetId"], ready["datasetId"])
        self.assertEqual(len(self.service.datahub.snapshots.ids(record["sessionId"])), 1)
