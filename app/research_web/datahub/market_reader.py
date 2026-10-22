"""Trusted sessionless Host bridge for one fixed public Eastmoney indices contract.

This deliberately does not register an unverified Broker fallback or invent a
research session. Public Eastmoney has no separate source grant in the current
Host. Personal warehouse profile revocation and Host ownership remain mandatory.
"""

from copy import deepcopy
from pathlib import Path

from core.observability import get_logger

from ..market_store import MarketStoreError
from ..market_store.models import canonical, digest
from .contracts import BusinessQuery
from .providers import Result
from .research_snapshot_store import MARKET_INDICES_PARAMETERS, complete_market_indices

log = get_logger(__name__)
SOURCE = "eastmoney"
CONTRACT = "market-indices-eastmoney-native-envelope-v1"
MAX_CAPTURE_BYTES = 4 * 1024 * 1024
UNAVAILABLE = frozenset(
    {"warehouse_busy", "warehouse_database_unavailable", "warehouse_database_operation_failed"}
)


class MarketReader:
    def __init__(self, datahub, *, admission=None):
        self.hub = datahub
        self.root = Path(datahub.store.root).resolve()
        self.admission = admission

    def _identity(self):
        """Recheck actual Host/root/profile facts; no actor or scope input is accepted."""
        warehouse = self.hub.warehouse
        if (
            self.hub.closed
            or Path(self.hub.store.root).resolve() != self.root
            or warehouse is None
            or Path(warehouse.root).resolve() != self.root
        ):
            log.warning("market_reader_admission_rejected")
            raise MarketStoreError("market_host_access_denied")
        if self.admission is not None:
            self.admission()  # Trusted Host extension; exceptions must propagate.
        profile = warehouse.capture_identity()
        source_digest = digest(
            canonical(
                [CONTRACT, MARKET_INDICES_PARAMETERS, self.hub.source_configuration_digest(SOURCE)]
            )
        )
        return warehouse, profile, source_digest

    def _recheck(self, initial):
        if self._identity() != initial:
            log.warning("market_reader_authorization_changed")
            raise MarketStoreError("market_authorization_changed")

    @staticmethod
    def _metadata(*, status, persisted=False, hit=False, version=None, capture=None):
        return {
            "status": status,
            "persisted": persisted,
            "hit": hit,
            "source": SOURCE,
            "source_count": 1,
            "version": version,
            "storage_form": "provider_native_snapshot",
            "formal_backtest_eligible": False,
            "availability_basis": "first_observed",
            "quality_accepted": False,
            "snapshot_sha256": (capture or {}).get("warehouse_snapshot_sha256"),
            "observed_at": (capture or {}).get("observed_at"),
            "display_cache_ttl_seconds": (capture or {}).get("display_cache_ttl_seconds"),
        }

    async def indices(self, provider, *, refresh=True):
        initial = self._identity()
        warehouse, profile, source_digest = initial
        query = BusinessQuery(
            capability="market_snapshot",
            source=SOURCE,
            refresh=refresh,
            purpose="display",
            quality="allow_stale",
            parameters=deepcopy(MARKET_INDICES_PARAMETERS),
        )
        enabled = bool(profile and profile["enabled"])
        status = "not_configured" if profile is None else "disabled"
        if enabled and not refresh:
            try:
                cached = await self.hub.storage_runner.run(
                    warehouse.read, query, SOURCE, source_digest
                )
            except MarketStoreError as exc:
                if str(exc) not in UNAVAILABLE:
                    raise
                status = str(exc)
                log.warning("market_warehouse_read_unavailable", code=status)
                cached = None
            self._recheck(initial)
            if cached is not None:
                if len(cached.rows) != 1 or not complete_market_indices(
                    cached.rows[0].get("response")
                ):
                    raise MarketStoreError("market_warehouse_snapshot_invalid")
                payload = deepcopy(cached.rows[0]["response"])
                payload["warehouse"] = self._metadata(
                    status="hit",
                    persisted=True,
                    hit=True,
                    capture=cached.metadata,
                )
                return payload
        self._recheck(initial)
        payload = await provider.fetch("indices")
        self._recheck(initial)
        try:
            if not isinstance(payload, dict):
                raise MarketStoreError("invalid_market_envelope")
            raw = canonical(payload)
        except MarketStoreError:
            log.warning("market_indices_response_rejected", reason="invalid_json_envelope")
            raise MarketStoreError("market_indices_response_invalid") from None
        if len(raw) > MAX_CAPTURE_BYTES:
            raise MarketStoreError("market_indices_response_limit")
        payload = deepcopy(payload)
        version = None
        if enabled and complete_market_indices(payload):
            result = Result(
                rows=[{"response": deepcopy(payload)}],
                raw=[raw],
                source_url=payload.get("source_url", ""),
                status="snapshot",
                pagination_complete=True,
                provider_total=1,
                provider_id=SOURCE,
                fields={"response": {"contract": CONTRACT, "unit": "provider_native"}},
            )
            try:
                version = await self.hub.storage_runner.run(
                    warehouse.ingest, query, SOURCE, source_digest, result
                )
                status = "persisted" if version else "not_persisted"
            except MarketStoreError as exc:
                if str(exc) not in UNAVAILABLE:
                    raise
                status = str(exc)
                log.warning("market_warehouse_write_unavailable", code=status)
            self._recheck(initial)
        elif enabled:
            status = "incomplete"
            log.info("market_warehouse_capture_rejected", reason=status)
        payload["warehouse"] = self._metadata(
            status=status, persisted=bool(version), version=version
        )
        return payload
