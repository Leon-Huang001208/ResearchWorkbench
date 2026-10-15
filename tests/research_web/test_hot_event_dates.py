"""Date corrections preserve precision and reject mismatching signed receipts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from research_workbench_entrypoint.hot import HotError
from research_workbench_entrypoint.hot_manager import HotManager


class HotEventDateTests(unittest.TestCase):
    def test_date_receipt_and_pre_rpc_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = HotManager(Path("/project"), Path(directory).resolve(), None)
            manager.directory.mkdir(mode=0o700)
            event = "11111111-1111-4111-8111-111111111111"
            request = "22222222-2222-4222-8222-222222222222"
            claim = {"value": "2026-03-17", "precision": "day", "timezone": "Europe/London",
                     "evidence": {"id": event, "revision": 1, "quote": "Effective 17 March 2026"}}
            change = {"type": "times", "id": event, "expected": 1, "occurred": None, "effective": claim}
            snapshot = {"state": "active", "occurredAt": None, "effectiveAt": claim["value"],
                        "dateEvidence": {"occurred": None, "effective": claim}, "manual": {"times": True}}
            result = {"source": {"id": event, "revision": 2, "snapshot": snapshot}}
            with patch.object(manager, "_state", return_value={"port": 1234, "owner": {}}), patch.object(manager, "_secret", return_value="controller"):
                with patch("research_workbench_entrypoint.hot_manager.rpc", return_value=result):
                    self.assertEqual(manager.correct_event(change, "Reviewed source", request)["source"], result["source"])
                with patch("research_workbench_entrypoint.hot_manager.rpc", return_value={"source": {**result["source"], "snapshot": {**snapshot, "effectiveAt": None}}}):
                    unknown = manager.correct_event(change, "Reviewed source", request)
                    self.assertEqual(unknown["state"], "outcome_unknown")
                    self.assertEqual(unknown["requestId"], request)
                for invalid in ({**claim, "value": "2026-02-30"}, {**claim, "timezone": "invalid"}, {**claim, "extra": True}, {**claim, "evidence": {**claim["evidence"], "revision": True}}):
                    with patch("research_workbench_entrypoint.hot_manager.rpc") as rpc, self.assertRaises(HotError):
                        manager.correct_event({**change, "effective": invalid}, "Reviewed source", request)
                    rpc.assert_not_called()
