"""Source-qualified native responses captured for reproducible research, not PIT bars."""

from __future__ import annotations

import base64
import json
import math
import re
from datetime import UTC, date, datetime, timedelta
from threading import RLock
from uuid import uuid4

from core.observability import get_logger

from ..market_store import Batch, DatasetIdentity, Fact, MarketStoreError, RawOriginal
from ..market_store.models import canonical, digest, parse_batch
from .contracts import BusinessQuery
from .providers import MAX_QUERY_BYTES, MAX_RESPONSE_BYTES, MAX_ROWS, ProviderError, Result
from .providers_akshare import (
    FUND_FLOW_FAILURE_CODES,
    FUND_FLOW_SCHEMA,
    SINA_FINANCIAL_SCHEMA,
    china_macro_fields,
    china_macro_metadata,
    china_macro_projection,
    china_macro_source_url,
    sina_income_fields,
    sina_income_metadata,
    sina_income_projection,
    sina_income_source_url,
)
from .providers_baostock import FINANCIAL_DICTIONARY
from .providers_baostock_cashflow import (
    cash_flow_fields,
    cash_flow_metadata,
    cash_flow_projection,
)
from .providers_baostock_reference import (
    profitability_fields,
    profitability_metadata,
    profitability_projection,
)
from .providers_external import (
    OFFICIAL_NUMERIC,
    SPDR_METRIC_UNITS,
    SPDR_NUMERIC_CONTRACT,
    arguments,
    endpoint_request,
    official_numeric_contract,
    official_numeric_request,
    spdr_fields,
    spdr_projection,
)
from .providers_kapsarc import (
    KAPSARC_NUMERIC_CONTRACT,
    KAPSARC_UNITS,
    kapsarc_fields,
    kapsarc_metadata,
    kapsarc_projection,
)
from .providers_market import INDEXES
from .providers_nyfed_reference import nyfed_fields, nyfed_metadata, nyfed_projection
from .providers_wgc import WGC_DATASETS, WGC_NUMERIC_CONTRACT, WGC_UNITS, wgc_fields, wgc_projection

log = get_logger(__name__)
CAPABILITIES = frozenset(
    {"financials", "market_activity", "factor_macro", "fund_data", "index_data"}
)
SOURCES = frozenset(
    {
        "akshare",
        "baostock",
        "wind",
        "tinysoft",
        "eastmoney_fund",
        "fund_nav",
        "fund_profile",
        "fund_distributions",
        "fund_holdings",
    }
)
# Named public numeric endpoints only. Calendars, news and credential endpoints excluded.
PUBLIC_NUMERIC = frozenset(
    {
        ("ext_fred", "series"),
        ("ext_bls", "series"),
        ("ext_worldbank", "inflation"),
        ("ext_nyfed", "rates"),
        ("ext_treasury", "cash"),
        ("ext_spdr", "gld"),
        ("ext_wgc", "etf-holdings"),
        ("ext_wgc", "etf-flows"),
        ("ext_kapsarc", "production"),
        ("ext_ths", "cmd_history_quotation"),
        ("ext_ths", "basic_data_service"),
        ("ext_ths", "real_time_quotation"),
    }
)
METADATA_KEYS = frozenset(
    {
        "upstream_id",
        "provider_semantics_revision",
        "adjustment_contract",
        "field_dictionary_evidence",
        "reference_dictionary",
        "projection_scope",
        "reporting_basis",
        "statement",
        "schema_version",
        "units",
        "currency",
        "accounting_standard",
        "consolidation",
        "revision_policy",
        "transport",
        "independent_source",
        "availability_basis",
        "upstream_attempts",
    }
)
RESULT_KEYS = (
    "rows",
    "fields",
    "source_url",
    "status",
    "pages_fetched",
    "provider_total",
    "pagination_complete",
    "limitations",
    "missing",
    "duplicates",
    "as_of",
    "provider_id",
)
# Storage slot for one exact query; never a report, release or observation date.
# All observations are revisions of this one logical fact, projected by cutoff.
START = date(1970, 1, 1)
NAV_SEMANTIC_GAPS = frozenset(
    {"adjusted_total_return", "benchmark_timeseries", "verified_currency"}
)


def _complete_ak_native_snapshot(query: BusinessQuery, result: Result) -> bool:
    """Bind new captures to one strictly reparsed original and fixed source contract."""
    if (
        result.provider_id != "akshare"
        or result.status != "snapshot"
        or type(result.pages_fetched) is not int
        or result.pages_fetched != 1
        or type(result.provider_total) is not int
        or type(result.pagination_complete) is not bool
        or len(result.raw) != 1
        or not result.rows
        or result.missing
        or type(result.duplicates) is not int
        or result.duplicates != 0
    ):
        return False
    try:
        if query.capability == "factor_macro":
            rows, total, pages_complete = china_macro_projection(result.raw[0], query)
            source_url = china_macro_source_url(query)
            metadata = china_macro_metadata(query.parameters["series"])
            fields = china_macro_fields(rows, query.parameters["series"])
            if not pages_complete or any(value is None for row in rows for value in row.values()):
                return False
        else:
            rows, total, missing = sina_income_projection(result.raw[0], query)
            if missing:
                return False
            source_url = sina_income_source_url(query)
            metadata = sina_income_metadata()
            fields = sina_income_fields(rows)
            # Strict duplicate/number validation already ran in the shared parser.
            captured = json.loads(result.raw[0])["result"]["data"]["report_date"]
            pages_complete = total == len(captured)
        expected_as_of = max(
            (
                str(row.get("date") or row.get("as_of"))
                for row in rows
                if row.get("date") or row.get("as_of")
            ),
            default=None,
        )
        return (
            result.source_url == source_url
            and result.as_of == expected_as_of
            and result.provider_total == total
            and result.pagination_complete is pages_complete
            and canonical(result.rows) == canonical(rows)
            and canonical(result.fields) == canonical(fields)
            and canonical(
                {
                    key: value
                    for key, value in result.metadata.items()
                    if key in METADATA_KEYS or key in metadata
                }
            )
            == canonical(metadata)
        )
    except (ProviderError, MarketStoreError, TypeError, ValueError, KeyError, AttributeError):
        return False


def _complete_profitability_snapshot(query: BusinessQuery, result: Result) -> bool:
    """Reject changed rows, references and originals before replacing a good snapshot."""
    if (
        set(query.parameters) != {"asset", "statements", "periods"}
        or query.parameters.get("statements") != ["profitability"]
        or not isinstance(query.parameters.get("periods"), list)
        or len(query.parameters["periods"]) != 1
        or result.provider_id != "baostock"
        or result.status != "complete"
        or result.pagination_complete is not True
        or type(result.provider_total) is not int
        or result.provider_total != 1
        or len(result.rows) != 1
        or len(result.raw) != 1
        or result.source_url != FINANCIAL_DICTIONARY
        or result.missing
    ):
        return False
    try:
        expected = profitability_metadata()
        rows, missing = profitability_projection(
            result.raw[0], query.parameters["asset"], query.parameters["periods"][0]
        )
        return (
            not missing
            and canonical(result.rows) == canonical(rows)
            and canonical(result.fields) == canonical(profitability_fields())
            and canonical(
                {
                    key: value
                    for key, value in result.metadata.items()
                    if key in METADATA_KEYS or key in expected
                }
            )
            == canonical(expected)
            and not any(
                key.startswith("reference") and key not in expected for key in result.metadata
            )
        )
    except (ProviderError, MarketStoreError, TypeError, ValueError, KeyError):
        return False


def _complete_cash_flow_snapshot(query: BusinessQuery, result: Result) -> bool:
    """Bind native financial ratios to their SDK original, never to market fund flow."""
    if (
        set(query.parameters) != {"asset", "statements", "periods"}
        or query.parameters.get("statements") != ["cash_flow"]
        or not isinstance(query.parameters.get("periods"), list)
        or len(query.parameters["periods"]) != 1
        or result.provider_id != "baostock"
        or result.status != "complete"
        or result.pagination_complete is not True
        or type(result.provider_total) is not int
        or result.provider_total != 1
        or len(result.rows) != 1
        or len(result.raw) != 1
        or result.missing
        or canonical({key: result.metadata.get(key) for key in cash_flow_metadata()})
        != canonical(cash_flow_metadata())
    ):
        return False
    try:
        rows, missing = cash_flow_projection(
            result.raw[0], query.parameters["asset"], query.parameters["periods"][0]
        )
        return (
            not missing
            and canonical(result.rows) == canonical(rows)
            and canonical(result.fields) == canonical(cash_flow_fields())
        )
    except (ProviderError, MarketStoreError, TypeError, ValueError, KeyError):
        return False


def _complete_nyfed_snapshot(query: BusinessQuery, result: Result) -> bool:
    """Rebind exact native capture to its closed request and immutable dictionary."""
    limit = query.parameters.get("limit", MAX_ROWS)
    if (
        type(limit) is not int
        or not 1 <= limit <= MAX_ROWS
        or result.provider_id != "ext_nyfed"
        or result.status not in {"snapshot", "empty"}
        or result.pagination_complete is not True
        or type(result.provider_total) is not int
        or result.provider_total != len(result.rows)
        or type(result.pages_fetched) is not int
        or result.pages_fetched != 1
        or result.missing
        or len(result.raw) != 1
        or not isinstance(result.raw[0], bytes)
        or len(result.raw[0]) > MAX_RESPONSE_BYTES
        or result.raw_bytes != len(result.raw[0])
    ):
        return False
    try:
        # Validate the whole object before separating the three known DataHub annotations.
        # These fields are neither stored by METADATA_KEYS nor used as authorization here.
        canonical(result.metadata)
        metadata = dict(result.metadata)
        if "execution_authorization_digest" in metadata:
            value = metadata.pop("execution_authorization_digest")
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
                return False
        if "quality_accepted" in metadata and type(metadata.pop("quality_accepted")) is not bool:
            return False
        if "execution_attempts" in metadata:
            attempts = metadata.pop("execution_attempts")
            if not isinstance(attempts, list) or any(
                not isinstance(item, dict) for item in attempts
            ):
                return False
        if canonical(metadata) != canonical(nyfed_metadata()):
            return False
        args = arguments(query.parameters.get("arguments_json"))
        _, url = endpoint_request("ext_nyfed", "rates", args)
        official_numeric_request("ext_nyfed", "rates", args)
        rows = nyfed_projection(result.raw[0], args)
        numeric = {
            "percentRate",
            "volumeInBillions",
            "average30day",
            "average90day",
            "average180day",
            "index",
        }
        return (
            result.source_url == url
            and len(rows) <= limit
            and result.status == ("snapshot" if rows else "empty")
            and not any(
                row[key] is None or row[key] == "null"
                for row in rows
                for key in numeric & row.keys()
            )
            and canonical(result.rows) == canonical(rows)
            and canonical(result.fields) == canonical(nyfed_fields(rows))
        )
    except (ProviderError, MarketStoreError, TypeError, ValueError, KeyError, RecursionError):
        return False


def _complete_kapsarc_snapshot(result: Result) -> bool:
    """Require both count/unit evidence and the exact export projection before publishing."""
    expected = {
        "schema_version": KAPSARC_NUMERIC_CONTRACT,
        "provider_semantics_revision": KAPSARC_NUMERIC_CONTRACT,
        "upstream_id": "bgs-via-kapsarc",
        "availability_basis": "first_observed",
        "revision_policy": "first_observed_not_historical_vintage",
        "projection_scope": "gold_mine_annual_kg_source_export",
        "units": KAPSARC_UNITS,
    }
    if (
        result.provider_id != "ext_kapsarc"
        or result.status not in {"complete", "snapshot"}
        or result.pagination_complete is not True
        or type(result.provider_total) is not int
        or result.provider_total != len(result.rows)
        or not result.rows
        or result.missing
        or len(result.raw) != 2
        or any(result.metadata.get(key) != value for key, value in expected.items())
        or result.metadata.get("historical_point_in_time") is not False
        or result.metadata.get("formal_backtest_eligible") is not False
        or result.metadata.get("independent_source") is not False
    ):
        return False
    try:
        return (
            canonical(result.rows) == canonical(kapsarc_projection(*result.raw))
            and canonical(result.fields) == canonical(kapsarc_fields())
            and canonical(result.metadata.get("field_dictionary_evidence"))
            == canonical(kapsarc_metadata(result.raw[1])["field_dictionary_evidence"])
        )
    except (ProviderError, MarketStoreError, TypeError, ValueError):
        return False


def _complete_wgc_snapshot(result: Result, dataset: str) -> bool:
    """Bind the selected monthly slice to its original, without claiming vintage history."""
    if (
        result.provider_id != "ext_wgc"
        or result.status not in {"complete", "snapshot"}
        or result.pagination_complete is not True
        or type(result.provider_total) is not int
        or result.provider_total != len(result.rows)
        or not result.rows
        or result.missing
        or len(result.raw) != 1
        or any(
            result.metadata.get(key) != value
            for key, value in {
                "schema_version": WGC_NUMERIC_CONTRACT,
                "provider_semantics_revision": WGC_NUMERIC_CONTRACT,
                "upstream_id": "worldgoldcouncil",
                "availability_basis": "first_observed",
                "revision_policy": "first_observed_not_historical_vintage",
                "projection_scope": "monthly_tonnes_four_regions",
                "units": WGC_UNITS,
            }.items()
        )
        or result.metadata.get("historical_point_in_time") is not False
        or result.metadata.get("formal_backtest_eligible") is not False
    ):
        return False
    try:
        return canonical(result.rows) == canonical(
            wgc_projection(result.raw[0], dataset)
        ) and canonical(result.fields) == canonical(wgc_fields())
    except (ProviderError, MarketStoreError, TypeError, ValueError):
        return False


def _complete_spdr_snapshot(result: Result) -> bool:
    """Bind the typed projection and units to its one complete source original."""
    if (
        result.provider_id != "ext_spdr"
        or result.status not in {"complete", "snapshot"}
        or result.pagination_complete is not True
        or type(result.provider_total) is not int
        or result.provider_total != len(SPDR_METRIC_UNITS)
        or result.missing
        or result.metadata.get("schema_version") != SPDR_NUMERIC_CONTRACT
        or result.metadata.get("provider_semantics_revision") != SPDR_NUMERIC_CONTRACT
        or result.metadata.get("upstream_id") != "spdrgoldshares"
        or result.metadata.get("availability_basis") != "first_observed"
        or result.metadata.get("revision_policy") != "first_observed_not_historical_vintage"
        or result.metadata.get("historical_point_in_time") is not False
        or result.metadata.get("formal_backtest_eligible") is not False
        or result.metadata.get("units") != SPDR_METRIC_UNITS
        or len(result.raw) != 1
        or not isinstance(result.raw[0], bytes)
    ):
        return False
    try:
        # Canonical bytes distinguish bool from int and bind all original strings,
        # reference dates, decimal precision, field roles and source unit labels.
        return canonical(result.rows) == canonical(spdr_projection(result.raw[0])) and canonical(
            result.fields
        ) == canonical(spdr_fields())
    except (ProviderError, MarketStoreError, TypeError, ValueError):
        return False


MARKET_INDICES_PARAMETERS = {
    "asset_type": "index",
    "assets": [asset for asset, _, _ in INDEXES],
    "fields": ["price", "change", "change_pct", "as_of", "series"],
}


def _market_numeric(value):
    try:
        return type(value) in {int, float} and math.isfinite(value)
    except OverflowError:
        return False


def _market_stamp(value):
    """Match the Provider's full Shanghai ISO-second timestamp contract."""
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
        if (
            stamp.utcoffset() != timedelta(hours=8)
            or stamp.isoformat(timespec="seconds") != value
            or stamp.year < 1990
            or stamp > datetime.now(UTC) + timedelta(minutes=5)
        ):
            return None
        return stamp
    except (ValueError, OverflowError):
        return None


def _complete_index_row(row, identity, trade_date):
    asset, name, _secid = identity
    stamp = _market_stamp(row.get("as_of"))
    if (
        row.get("asset") != asset
        or row.get("code") != asset[:6]
        or row.get("name") != name
        or row.get("stale") is not False
        or stamp is None
        or stamp.date().isoformat() != trade_date
        or not all(_market_numeric(row.get(field)) for field in ("price", "change", "change_pct"))
    ):
        return False
    series = row.get("series")
    if not isinstance(series, list) or not 1 <= len(series) <= 500:
        return False
    previous = None
    for point in series:
        if not isinstance(point, dict) or not all(
            _market_numeric(point.get(field)) for field in ("price", "change_pct")
        ):
            return False
        observed = _market_stamp(point.get("time"))
        if (
            observed is None
            or observed.date() != stamp.date()
            or (previous is not None and observed <= previous)
        ):
            return False
        previous = observed
    return True


def complete_market_indices(payload):
    """Capture all fixed index fields and well-formed intraday points, never null gaps.

    Provider completeness only proves endpoint coverage. Missing numeric fields
    can still be null in its response; preserve that response but do not call it
    a complete warehouse capture of the required index field contract.
    """
    if not isinstance(payload, dict):
        return False
    rows = payload.get("rows")
    return bool(
        payload.get("provider") == "eastmoney"
        and payload.get("complete") is True
        and payload.get("pagination_complete") is True
        and payload.get("temporal_complete") is True
        and payload.get("provider_total") == len(INDEXES)
        and isinstance(rows, list)
        and len(rows) == len(INDEXES)
        and all(isinstance(row, dict) for row in rows)
        and all(
            _complete_index_row(row, identity, payload.get("quote_trade_date"))
            for row, identity in zip(rows, INDEXES, strict=True)
        )
        and _market_stamp(payload.get("as_of")) is not None
        and payload["as_of"] == max(row["as_of"] for row in rows)
        and payload.get("missing") == {"indices": 0, "intraday": 0, "quote_date": 0}
        and all(type(value) is int for value in payload["missing"].values())
    )


def _bounded_nav_capture(query, result, source):
    """Admit disclosed NAV semantics gaps only for a complete, narrow source response."""
    if (
        source != "eastmoney_fund"
        or result.provider_id != source
        or query.capability != "fund_data"
        or query.parameters.get("dataset") not in {"nav", "fund_nav"}
        or result.status != "complete"
        or result.pagination_complete is not True
        or not set(result.missing) <= NAV_SEMANTIC_GAPS
    ):
        return False
    try:
        start, end = (
            date.fromisoformat(query.parameters[name]) for name in ("start_date", "end_date")
        )
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= (end - start).days <= 30


class SnapshotSeries:
    """Trusted Host adapter; actor/scope/schema/units must never come from a browser.

    ``schema_identity`` and ``units_identity`` name the reviewed provider contract,
    not a claim that unknown units or historical releases have been verified.
    Host must serialize ingestion for the same series across adapter instances.
    """

    def __init__(
        self,
        service,
        actor,
        scope,
        *,
        schema_identity="provider-native-v1",
        units_identity="provider-defined-unknown",
        display_ttl_seconds=300,
    ):
        if (
            not isinstance(schema_identity, str)
            or not schema_identity
            or not isinstance(units_identity, str)
            or not units_identity
        ):
            raise MarketStoreError("snapshot_contract_required")
        if type(display_ttl_seconds) is not int or not 1 <= display_ttl_seconds <= 3600:
            raise MarketStoreError("snapshot_ttl_invalid")
        self.service, self.actor, self.scope = service, actor, scope
        self.schema_identity, self.units_identity = schema_identity, units_identity
        self.display_ttl = timedelta(seconds=display_ttl_seconds)
        self._lock = RLock()

    def _now(self):
        return datetime.now(UTC)

    def dataset(self, query: BusinessQuery) -> DatasetIdentity | None:
        """Construct identity from all business parameters and reviewed source contract."""
        if query.required_semantics is not None:
            # Native captures retain unverified fields and never satisfy the
            # canonical raw-price contract, including historical cache reads.
            return None
        if query.source not in {"auto", self.scope.source}:
            raise MarketStoreError("snapshot_source_mismatch")
        accepted = query.capability in CAPABILITIES and self.scope.source in SOURCES
        accepted |= (
            query.capability == "market_snapshot"
            and self.scope.source == "eastmoney"
            and query.parameters == MARKET_INDICES_PARAMETERS
        )
        accepted |= (
            query.capability == "market_bars"
            and (
                query.parameters.get("asset_type") in {"etf", "index"}
                or (
                    self.scope.source == "tinysoft"
                    and query.parameters.get("asset_type", "stock") == "stock"
                )
            )
            and self.scope.source in SOURCES
        )
        accepted |= (
            query.capability == "external_data"
            and (self.scope.source, query.parameters.get("dataset")) in PUBLIC_NUMERIC
        )
        if (
            (self.scope.source, query.parameters.get("dataset")) == ("ext_spdr", "gld")
            or (self.scope.source == "ext_wgc" and query.parameters.get("dataset") in WGC_DATASETS)
            or (
                (self.scope.source, query.parameters.get("dataset"))
                == ("ext_kapsarc", "production")
            )
        ):
            try:
                if arguments(query.parameters.get("arguments_json")):
                    return None
            except ProviderError:
                return None
        if not accepted:
            return None
        if query.purpose == "backtest":
            raise MarketStoreError("snapshot_formal_backtest_unavailable")
        identity = {
            "format": "provider_native_snapshot-v1",
            "source": self.scope.source,
            "capability": query.capability,
            "parameters": query.parameters,
            "schema_identity": self.schema_identity,
            "units_identity": self.units_identity,
        }
        semantic = digest(canonical(identity))
        # Arbitrary native asset/series names remain in the hashed complete identity.
        return DatasetIdentity(
            query.capability,
            "query-" + semantic,
            "provider-native",
            "observed",
            "provider-native",
            "native",
            "unverified",
            semantic,
            ("snapshot",),
        )

    def _facts(self, dataset, cutoff):
        facts = self.service.read_range(
            self.actor, self.scope, dataset, START, START, as_of=cutoff
        ).facts
        if len(facts) > 1 or any(
            fact.logical_key != (START, "snapshot", "first-observed", ()) for fact in facts
        ):
            raise MarketStoreError("snapshot_projection_invalid")
        return facts

    def ingest(self, query: BusinessQuery, result: Result) -> str | None:
        dataset = self.dataset(query)
        if dataset is None:
            return None
        with self._lock:
            # Even rejected/empty outcomes recheck current read entitlement.
            previous = self._facts(dataset, None)
            if (
                self.scope.source == "akshare"
                and (
                    query.capability == "factor_macro"
                    or query.capability == "financials"
                    and query.parameters.get("statements") == ["income_statement"]
                )
                and not _complete_ak_native_snapshot(query, result)
            ):
                log.info("research_snapshot_not_ingested", reason="ak_native_binding_incomplete")
                return None
            if (
                query.capability == "financials"
                and self.scope.source == "baostock"
                and query.parameters.get("statements") == ["cash_flow"]
                and not _complete_cash_flow_snapshot(query, result)
            ):
                log.info("research_snapshot_not_ingested", reason="cash_flow_contract_incomplete")
                return None
            if self.scope.source == "akshare":
                required_contract = (
                    SINA_FINANCIAL_SCHEMA
                    if query.capability == "financials"
                    and query.parameters.get("statements") == ["income_statement"]
                    else (
                        FUND_FLOW_SCHEMA
                        if query.capability == "market_activity"
                        and query.parameters.get("dataset") == "fund_flow"
                        else None
                    )
                )
                if required_contract and result.metadata.get("schema_version") != required_contract:
                    log.info(
                        "research_snapshot_not_ingested", reason="provider_contract_incomplete"
                    )
                    return None
            if (
                query.capability == "financials"
                and self.scope.source == "baostock"
                and query.parameters.get("statements") == ["profitability"]
                and not _complete_profitability_snapshot(query, result)
            ):
                log.info(
                    "research_snapshot_not_ingested",
                    reason="baostock_financial_contract_incomplete",
                )
                return None
            if (
                query.capability == "external_data"
                and (self.scope.source, query.parameters.get("dataset"))
                == ("ext_kapsarc", "production")
                and not _complete_kapsarc_snapshot(result)
            ):
                log.info("research_snapshot_not_ingested", reason="kapsarc_contract_incomplete")
                return None
            if (
                query.capability == "external_data"
                and self.scope.source == "ext_wgc"
                and query.parameters.get("dataset") in WGC_DATASETS
                and not _complete_wgc_snapshot(result, query.parameters["dataset"])
            ):
                log.info("research_snapshot_not_ingested", reason="wgc_contract_incomplete")
                return None
            if (
                query.capability == "external_data"
                and (self.scope.source, query.parameters.get("dataset")) == ("ext_spdr", "gld")
                and not _complete_spdr_snapshot(result)
            ):
                log.info("research_snapshot_not_ingested", reason="spdr_contract_incomplete")
                return None
            if (
                query.capability == "external_data"
                and (self.scope.source, query.parameters.get("dataset")) in OFFICIAL_NUMERIC
                and (
                    result.pagination_complete is not True
                    or result.metadata.get("schema_version")
                    != official_numeric_contract(self.scope.source, query.parameters.get("dataset"))
                )
            ):
                log.info(
                    "research_snapshot_not_ingested", reason="official_numeric_contract_incomplete"
                )
                return None
            if (
                query.capability == "external_data"
                and (self.scope.source, query.parameters.get("dataset")) == ("ext_nyfed", "rates")
                and not _complete_nyfed_snapshot(query, result)
            ):
                log.info("research_snapshot_not_ingested", reason="nyfed_contract_incomplete")
                return None
            if query.capability == "market_snapshot" and (
                len(result.rows) != 1
                or not isinstance(result.rows[0], dict)
                or set(result.rows[0]) != {"response"}
                or not complete_market_indices(result.rows[0]["response"])
                or result.pagination_complete is not True
            ):
                log.info("research_snapshot_not_ingested", reason="market_indices_incomplete")
                return None
            if query.as_of is not None or result.status not in {"complete", "snapshot", "empty"}:
                log.info("research_snapshot_not_ingested", reason="historical_or_incomplete")
                return None
            if result.provider_id not in {None, self.scope.source} or (
                result.missing and not _bounded_nav_capture(query, result, self.scope.source)
            ):
                raise MarketStoreError("snapshot_provider_or_completeness_mismatch")
            if result.status == "empty" and result.rows:
                raise MarketStoreError("snapshot_empty_status_mismatch")
            if not result.raw or any(not isinstance(raw, bytes) for raw in result.raw):
                raise MarketStoreError("snapshot_original_required")
            document = {key: getattr(result, key) for key in RESULT_KEYS}
            document["metadata"] = {
                key: value for key, value in result.metadata.items() if key in METADATA_KEYS
            }
            if (
                self.scope.source == "akshare"
                and query.capability == "market_activity"
                and query.parameters.get("dataset") == "fund_flow"
                and result.metadata.get("schema_version") == FUND_FLOW_SCHEMA
                and "upstream_attempts" not in document["metadata"]
            ):
                log.info("research_snapshot_not_ingested", reason="fund_flow_attempts_missing")
                raise MarketStoreError("snapshot_attempt_evidence_invalid")
            if "upstream_attempts" in document["metadata"]:
                attempts = document["metadata"]["upstream_attempts"]
                allowed_attempts = [
                    [{"upstream": "eastmoney", "endpoint": "akshare_sdk", "status": "snapshot"}],
                    *[
                        [
                            {
                                "upstream": "eastmoney",
                                "endpoint": "akshare_sdk",
                                "status": "failed",
                                "error_code": code,
                            },
                            {"upstream": "eastmoney", "endpoint": "webguest", "status": "snapshot"},
                        ]
                        for code in sorted(FUND_FLOW_FAILURE_CODES)
                    ],
                ]
                if self.scope.source != "akshare" or query.capability != "market_activity":
                    document["metadata"].pop("upstream_attempts")
                elif not isinstance(attempts, list) or attempts not in allowed_attempts:
                    raise MarketStoreError("snapshot_attempt_evidence_invalid")
            document["provider_id"] = self.scope.source
            document["format"] = "provider_native_snapshot-v1"
            document["payloads"] = [
                {"sha256": digest(raw), "base64": base64.b64encode(raw).decode("ascii")}
                for raw in result.raw
            ]
            content = canonical(document)
            if len(content) > MAX_QUERY_BYTES:
                raise MarketStoreError("snapshot_response_limit")
            raw = RawOriginal(content)
            latest = previous[0] if previous else None
            if latest is not None and latest.raw_hash == raw.sha256:
                return self.service.version(self.actor, self.scope, dataset)
            observed = self._now()
            if latest is not None and observed <= latest.ingested_at:
                raise MarketStoreError("snapshot_clock_not_advanced")
            capture_id = uuid4().hex
            value = {
                "response_sha256": raw.sha256,
                "observed_at": observed.isoformat(),
                "availability_basis": "first_observed",
                "formal_backtest_eligible": False,
                "provider_schema_sha256": digest(canonical(result.fields)),
            }
            fact = Fact(
                "snapshot",
                START,
                "first-observed",
                canonical(value).decode(),
                observed,
                observed,
                capture_id,
                raw.sha256,
            )
            version = self.service.commit_batch(
                self.actor, self.scope, dataset, Batch((fact,), (raw,))
            )
            log.info("research_snapshot_ingested", rows=len(result.rows), empty=not result.rows)
            return version

    def read(self, query: BusinessQuery) -> Result | None:
        dataset = self.dataset(query)
        if dataset is None:
            return None
        facts = self._facts(dataset, query.as_of)
        # Latest strict research always fetches upstream; elapsed TTL is no proof of freshness.
        if query.refresh or (
            query.as_of is None and (query.purpose != "display" or query.quality != "allow_stale")
        ):
            return None
        if not facts:
            return None
        selected = facts[0]
        if query.as_of is None and self._now() - selected.ingested_at > self.display_ttl:
            return None
        frozen = self.service.freeze(
            self.actor, self.scope, dataset, START, START, as_of=query.as_of
        )
        if len(frozen.payload) > MAX_QUERY_BYTES:
            raise MarketStoreError("snapshot_response_limit")
        batch = parse_batch(json.loads(frozen.payload)["batch"])
        # Choose from the frozen read itself so a concurrent writer cannot mix reads.
        if len(batch.facts) != 1 or batch.facts[0].logical_key != (
            START,
            "snapshot",
            "first-observed",
            (),
        ):
            raise MarketStoreError("snapshot_projection_invalid")
        selected = batch.facts[0]
        if query.as_of is None and self._now() - selected.ingested_at > self.display_ttl:
            return None
        original = next((raw for raw in batch.originals if raw.sha256 == selected.raw_hash), None)
        if original is None:
            raise MarketStoreError("snapshot_original_missing")
        try:
            document = json.loads(original.payload)
            if (
                document["format"] != "provider_native_snapshot-v1"
                or document["provider_id"] != self.scope.source
            ):
                raise ValueError("invalid_snapshot")
            for payload in document["payloads"]:
                if digest(base64.b64decode(payload["base64"], validate=True)) != payload["sha256"]:
                    raise ValueError("invalid_payload")
            result = Result(**{key: document[key] for key in RESULT_KEYS})
        except (KeyError, TypeError, ValueError):
            raise MarketStoreError("snapshot_original_invalid") from None
        result.raw = [frozen.export()]
        result.metadata = {
            **document["metadata"],
            "warehouse_hit": True,
            "warehouse_snapshot_sha256": frozen.digest,
            "warehouse_scope_digest": self.scope.key,
            "warehouse_semantics_digest": dataset.semantic_digest,
            "storage_form": "provider_native_snapshot",
            "formal_backtest_eligible": False,
            "availability_basis": "first_observed",
            "observed_at": selected.ingested_at.isoformat(),
            "historical_point_in_time": False,
            "captured_as_of": query.as_of.isoformat() if query.as_of else None,
            "quality_accepted": False,
            "display_cache_ttl_seconds": int(self.display_ttl.total_seconds()),
        }
        result.limitations = list(
            dict.fromkeys(
                [
                    *result.limitations,
                    "provider_native_fields",
                    "single_response_not_complete_history",
                    "publication_time_unverified",
                    "units_not_normalized",
                    "not_formal_backtest_data",
                ]
            )
        )
        log.info(
            "research_snapshot_hit",
            rows=len(result.rows),
            historical_capture=query.as_of is not None,
        )
        return result
