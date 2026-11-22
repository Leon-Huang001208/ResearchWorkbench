"""One bounded owned storage worker; cancellation observes the real transaction."""

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial

from core.observability import get_logger

from ..market_store import (
    MarketStoreCancelled,
    MarketStoreError,
    OperationContext,
    operation_context,
)

log = get_logger(__name__)


class StorageOperationCancelled(asyncio.CancelledError):
    def __init__(self, outcome):
        super().__init__("warehouse_operation_cancelled")
        self.outcome = outcome


class StorageRunner:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datahub-warehouse")
        self._capacity = threading.BoundedSemaphore(1)
        self._lock = threading.Lock()
        self._futures: set[Future] = set()
        self._closed = False

    @property
    def active(self):
        with self._lock:
            return any(not future.done() for future in self._futures)

    def _finished(self, future):
        with self._lock:
            self._futures.discard(future)
        self._capacity.release()

    async def run(self, function, *args, **kwargs):
        if self._closed or not self._capacity.acquire(blocking=False):
            raise MarketStoreError("warehouse_busy")
        context = OperationContext()

        def owned():
            with operation_context(context):
                context.checkpoint()
                return partial(function, *args, **kwargs)()

        try:
            future = self._executor.submit(owned)
        except Exception:  # noqa: BLE001 - executor errors must not leak or retain capacity.
            self._capacity.release()
            log.error("datahub_storage_submit_failed")
            raise MarketStoreError("warehouse_worker_unavailable") from None
        with self._lock:
            self._futures.add(future)
        future.add_done_callback(self._finished)
        wrapped = asyncio.wrap_future(future)
        try:
            return await asyncio.shield(wrapped)
        except asyncio.CancelledError:
            context.cancel()
            log.info("datahub_storage_draining")
            while True:
                try:
                    await asyncio.shield(wrapped)
                    break
                except asyncio.CancelledError:
                    context.cancel()  # Repeated UI cancellation cannot skip draining.
                except MarketStoreCancelled:
                    break  # The worker confirmed cancellation before commit.
                except Exception as exc:  # noqa: BLE001 - observe the actual worker failure.
                    log.warning("datahub_storage_drain_failed", error_type=type(exc).__name__)
                    break
            raise StorageOperationCancelled(context.outcome) from None

    async def close(self):
        self._closed = True
        with self._lock:
            futures = tuple(self._futures)
        if futures:
            await asyncio.shield(
                asyncio.gather(
                    *(asyncio.wrap_future(future) for future in futures), return_exceptions=True
                )
            )
        self._executor.shutdown(wait=True)
