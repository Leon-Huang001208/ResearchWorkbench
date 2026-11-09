"""Account-local event metadata is immutable, lazy and compare-and-swap protected."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from app.research_web.event_timeline.storage import RecordStore
from app.research_web.store import Store, StoreError


def records(tmp_path):
    return RecordStore(Store(tmp_path / "personal").root)


class EventTimelineStorageTests(unittest.TestCase):

    def setUp(self):
        temporary = TemporaryDirectory(prefix="rwb-event-unit-")
        self.addCleanup(temporary.cleanup)
        self.tmp_path = Path(temporary.name).resolve()

    def test_reads_do_not_initialize(self):
        tmp_path = self.tmp_path
        store = records(tmp_path)
        before = set(store.root.rglob("*"))
        assert store.list("event") == {"items": [], "next_cursor": None}
        with self.assertRaises(StoreError):
            store.get("event", "a" * 32)
        assert set(store.root.rglob("*")) == before

    def test_commit_guard_reads_same_transaction_and_refuses_late_publish(self):
        store = records(self.tmp_path)
        original = store.create("event", {"title": "existing"}, "guard-original-0001")

        def refuse():
            self.assertEqual(store.get("event", original["id"]), original)
            raise StoreError("cancelled", "event_source_cancelled", 409)

        with self.assertRaises(StoreError):
            store.create("event", {"title": "must rollback"}, "guard-refused-0001", guard=refuse)
        self.assertEqual(store.list("event")["items"], [original])

    def test_explicit_creation_and_price_attachment_are_atomic(self):
        store = records(self.tmp_path)
        prices = store.create("prices", {"calendar_id": None}, "prices-original-0001")
        calendar_id = "b" * 32
        ops = [
            {"kind": "calendar", "new_id": calendar_id, "payload": {"sessions": ["2026-01-02"]}},
            {
                "kind": "prices",
                "id": prices["id"],
                "expected_revision": 1,
                "payload": {"calendar_id": calendar_id},
            },
        ]
        result = store.batch(ops, "calendar-attach-0001")
        self.assertEqual(result[0]["id"], calendar_id)
        self.assertEqual(result[1]["revision"], 2)
        self.assertEqual(store.batch(ops, "calendar-attach-0001"), result)
        with self.assertRaises(StoreError):
            store.batch(
                [
                    {
                        "kind": "prices",
                        "id": prices["id"],
                        "expected_revision": 2,
                        "payload": {"calendar_id": "must rollback"},
                    },
                    {"kind": "calendar", "new_id": calendar_id, "payload": {}},
                ],
                "calendar-collision-0001",
            )
        self.assertEqual(store.get("prices", prices["id"]), result[1])
        with self.assertRaises(StoreError):
            store.batch(
                [{"kind": "calendar", "id": calendar_id, "new_id": calendar_id, "payload": {}}],
                "calendar-invalid-0001",
            )

    def test_idempotency_cas_versions_and_reopen(self):
        tmp_path = self.tmp_path
        store = records(tmp_path)
        first = store.create("event", {"title": "发布会"}, "create-event-0001")
        assert store.create("event", {"title": "发布会"}, "create-event-0001") == first
        second = store.update("event", first["id"], {"title": "延期"}, 1, "change-event-0001")
        assert second["revision"] == 2
        assert RecordStore(store.root).get("event", first["id"]) == second
        assert store.get("event", first["id"], revision=1) == first
        with self.assertRaises(StoreError):
            store.update("event", first["id"], {}, 1, "stale-event-0001")
        with self.assertRaises(StoreError):
            store.create("event", {"title": "different"}, "create-event-0001")

    def test_batch_is_atomic(self):
        tmp_path = self.tmp_path
        store = records(tmp_path)
        one = store.create("event", {}, "first-event-0001")
        two = store.create("event", {}, "second-event-0001")
        with self.assertRaises(StoreError):
            store.batch(
                [
                    {
                        "kind": "event",
                        "id": one["id"],
                        "expected_revision": 1,
                        "payload": {"ok": True},
                    },
                    {"kind": "event", "id": two["id"], "expected_revision": 7, "payload": {}},
                ],
                "batch-events-0001",
            )
        assert store.get("event", one["id"]) == one

    def test_concurrent_cas_only_one_wins(self):
        tmp_path = self.tmp_path
        store = records(tmp_path)
        first = store.create("event", {}, "create-event-0001")

        def change(number):
            try:
                return store.update(
                    "event", first["id"], {"n": number}, 1, f"concurrent-{number:04d}"
                )
            except StoreError:
                return None

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(change, [1, 2]))
        assert sum(result is not None for result in results) == 1

    def test_account_copy_is_rejected(self):
        tmp_path = self.tmp_path
        import shutil

        store = records(tmp_path)
        store.create("event", {}, "create-event-0001")
        other = Store(tmp_path / "other").root
        shutil.copytree(store.folder, other / store.folder.name)
        shutil.copyfile(store.marker, other / store.marker.name)
        with self.assertRaises(StoreError):
            RecordStore(other).list("event")

    def test_missing_database_and_unsafe_links_fail_closed(self):
        tmp_path = self.tmp_path
        store = records(tmp_path)
        store.create("event", {}, "create-event-0001")
        store.path.unlink()
        with self.assertRaises(StoreError):
            store.list("event")
        with self.assertRaises(StoreError):
            store.create("event", {}, "create-event-0002")
        store.path.symlink_to(tmp_path / "foreign.sqlite3")
        with self.assertRaises(StoreError):
            store.list("event")

    def test_namespaces_are_server_bounded(self):
        tmp_path = self.tmp_path
        for kind in ["../event", "anything", "owner", "credentials"]:
            with self.assertRaises(StoreError):
                records(tmp_path).create(kind, {}, "create-event-0001")


if __name__ == "__main__":
    unittest.main()
