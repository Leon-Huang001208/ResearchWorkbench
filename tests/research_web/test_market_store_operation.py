"""Per-operation cancellation must not cross users or fabricate rollback."""

import asyncio
import unittest

from test_market_store import DATASET, SCOPE, batch, fact

from app.research_web.market_store import (
    InMemoryMarketStore,
    MarketStoreCancelled,
    OperationContext,
    operation_context,
)


class OperationTests(unittest.TestCase):
    def test_cancel_before_memory_commit_preserves_state_and_other_operation(self):
        store = InMemoryMarketStore()
        before = store.version(SCOPE, DATASET)
        cancelled = OperationContext()
        cancelled.cancel()
        with operation_context(cancelled), self.assertRaises(MarketStoreCancelled):
            store.commit_batch(SCOPE, DATASET, batch(fact()))
        self.assertFalse(cancelled.committed)
        self.assertEqual(store.version(SCOPE, DATASET), before)
        independent = OperationContext()
        with operation_context(independent):
            version = store.commit_batch(SCOPE, DATASET, batch(fact()))
        self.assertTrue(independent.committed)
        self.assertEqual(independent.outcome.result, version)

    def test_cancellation_after_memory_commit_keeps_truthful_outcome(self):
        store = InMemoryMarketStore()
        context = OperationContext()
        with operation_context(context):
            version = store.commit_batch(SCOPE, DATASET, batch(fact()))
        context.cancel()
        self.assertTrue(context.committed)
        self.assertEqual(context.outcome.result, version)
        self.assertEqual(store.version(SCOPE, DATASET), version)


class ThreadOperationTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_propagates_to_thread_without_cross_operation_cancellation(self):
        store = InMemoryMarketStore()
        cancelled = OperationContext()
        cancelled.cancel()
        with operation_context(cancelled), self.assertRaises(MarketStoreCancelled):
            await asyncio.to_thread(store.commit_batch, SCOPE, DATASET, batch(fact()))
        separate = OperationContext()
        with operation_context(separate):
            await asyncio.to_thread(store.commit_batch, SCOPE, DATASET, batch(fact()))
        self.assertTrue(separate.committed)
        self.assertFalse(cancelled.committed)


if __name__ == "__main__":
    unittest.main()
