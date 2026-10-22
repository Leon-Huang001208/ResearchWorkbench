"""Shared idle proof for bounded SDK workers, cancellation and resident updates."""

import asyncio
from concurrent.futures import Future

from core.observability import get_logger

from . import providers_akshare, providers_baostock, providers_cjpy, providers_wind
from .providers import ProviderError

log = get_logger(__name__)
SOURCES = frozenset({"tinysoft", "akshare", "wind", "baostock"})


def source_futures(source: str) -> tuple[Future, ...]:
    if source == "wind" and providers_wind._WIND_POISONED:
        log.warning("datahub_worker_cleanup_unconfirmed", source=source)
        raise ProviderError("provider_cleanup_unconfirmed")
    module = {
        "tinysoft": providers_cjpy,
        "akshare": providers_akshare,
        "baostock": providers_baostock,
        "wind": providers_wind,
    }.get(source)
    return module.active_futures() if module is not None else ()


def active_futures() -> tuple[Future, ...]:
    return tuple(future for source in SOURCES for future in source_futures(source))


async def drain_sources(sources: set[str] | frozenset[str]) -> None:
    """Wait on owned futures; never cancel underlying native/SDK operations."""
    for source in sources.intersection(SOURCES):
        futures = source_futures(source)
        if futures:
            log.info("datahub_worker_draining", source=source, count=len(futures))
            pending = asyncio.gather(
                *(asyncio.wrap_future(future) for future in futures), return_exceptions=True
            )
            while not pending.done():
                try:
                    await asyncio.shield(pending)
                except asyncio.CancelledError:
                    log.warning("datahub_worker_drain_cancel_repeated", source=source)
            pending.result()
        source_futures(source)  # Unconfirmed native cleanup must still fail closed.
