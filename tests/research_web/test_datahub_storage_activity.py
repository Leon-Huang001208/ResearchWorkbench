"""Storage cancellation drains owned threads and reports the actual commit point."""

import asyncio
import threading
import unittest


class StorageActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_before_commit_rolls_back_and_keeps_capacity_until_drained(self):
        from app.research_web.datahub.storage_activity import (
            StorageOperationCancelled,
            StorageRunner,
        )
        from app.research_web.market_store.operation import checkpoint

        entered, release = threading.Event(), threading.Event()
        runner = StorageRunner()

        def work():
            entered.set()
            release.wait(2)
            checkpoint()
            return "not committed"

        task = asyncio.create_task(runner.run(work))
        await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        await asyncio.sleep(0)
        self.assertTrue(runner.active)
        self.assertFalse(task.done())
        release.set()
        with self.assertRaises(StorageOperationCancelled) as caught:
            await task
        self.assertFalse(caught.exception.outcome.committed)
        self.assertFalse(runner.active)
        await runner.close()

    async def test_late_cancel_cannot_claim_a_committed_transaction_rolled_back(self):
        from app.research_web.datahub.storage_activity import (
            StorageOperationCancelled,
            StorageRunner,
        )
        from app.research_web.market_store.operation import record_committed

        entered, release = threading.Event(), threading.Event()
        runner = StorageRunner()

        def work():
            record_committed("a" * 64)
            entered.set()
            release.wait(2)
            return "a" * 64

        task = asyncio.create_task(runner.run(work))
        await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with self.assertRaises(StorageOperationCancelled) as caught:
            await task
        self.assertTrue(caught.exception.outcome.committed)
        self.assertEqual(caught.exception.outcome.result, "a" * 64)
        await runner.close()
