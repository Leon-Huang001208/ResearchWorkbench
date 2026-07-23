"""ConnectorRegistry 集成测试 — 验证注册、发现、查找、健康检查."""

import pytest

from core.connectors.base import DiscoveryItem, MarketDataConnector
from core.connectors.registry import DatasetRouter, get_connector_registry, reset_connector_registry
from core.contracts.documents_v1 import SourceType
from core.contracts.ingestion_record import HealthStatus
from core.source_registry import SourceSpec

# ---------------------------------------------------------------------------
# 最小化 stub connector 用于测试 registry
# ---------------------------------------------------------------------------


class _StubConnector(MarketDataConnector):
    """用于 Registry 测试的最小化 connector."""

    @property
    def source(self) -> str:
        return "test_source"

    @property
    def datasets(self):
        return ["test_dataset"]

    def health_check(self):
        return HealthStatus.HEALTHY

    def discover(self, dataset, **params):
        return [DiscoveryItem(item_id="test", item_type="test")]

    def fetch(self, dataset, item, **params):
        from core.connectors.base import RawObject

        return RawObject(data="test", content_type="text/plain", source_uri="test://test")

    def parse_table(self, raw):
        from core.connectors.base import ParsedTable

        return ParsedTable(columns=["col"], rows=[{"col": 1}])

    def normalize_bars(self, dataset, table, raw_uri, content_hash):
        return []

    def persist(self, records):
        return len(records)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试前后重置全局 registry."""
    reset_connector_registry()
    yield
    reset_connector_registry()


@pytest.fixture
def registry():
    return get_connector_registry()


@pytest.fixture
def stub():
    return _StubConnector()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_new_connector(self, registry, stub):
        registry.register("test_source", stub)
        assert "test_source" in registry.list_sources()
        assert registry.get_connector("test_source") is stub

    def test_register_duplicate_raises(self, registry, stub):
        registry.register("test_source", stub)
        stub2 = _StubConnector()
        with pytest.raises(ValueError, match="already registered"):
            registry.register("test_source", stub2)

    def test_register_class(self, registry):
        connector = registry.register_class("test_source", _StubConnector)
        assert isinstance(connector, _StubConnector)
        assert registry.get_connector("test_source") is connector

    def test_register_with_config(self, registry, stub):
        config = {"retry": {"max_retries": 5}}
        registry.register("test_source", stub, config=config)
        assert registry._configs["test_source"] == config


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


class TestLookup:
    def test_get_connector_missing(self, registry):
        assert registry.get_connector("nonexistent") is None

    def test_get_connector_or_raise(self, registry, stub):
        registry.register("test_source", stub)
        result = registry.get_connector_or_raise("test_source")
        assert result is stub

    def test_get_connector_or_raise_missing(self, registry):
        with pytest.raises(KeyError, match="not found"):
            registry.get_connector_or_raise("nonexistent")

    def test_get_all_connectors(self, registry, stub):
        registry.register("test_source", stub)
        all_connectors = registry.get_all_connectors()
        assert "test_source" in all_connectors
        assert all_connectors["test_source"] is stub

    def test_list_sources(self, registry, stub):
        assert registry.list_sources() == []
        registry.register("test_source", stub)
        assert registry.list_sources() == ["test_source"]

    def test_list_datasets(self, registry, stub):
        registry.register("test_source", stub)
        datasets = registry.list_datasets()
        assert datasets == {"test_source": ["test_dataset"]}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_get_health(self, registry, stub):
        registry.register("test_source", stub)
        assert registry.get_health("test_source") == HealthStatus.HEALTHY

    def test_get_health_missing(self, registry):
        assert registry.get_health("nonexistent") == HealthStatus.UNKNOWN

    def test_get_all_health(self, registry, stub):
        registry.register("test_source", stub)

        class _DegradedStub(_StubConnector):
            @property
            def source(self) -> str:
                return "degraded_source"

            def health_check(self):
                return HealthStatus.DEGRADED

        registry.register("degraded_source", _DegradedStub())
        health = registry.get_all_health()
        assert health["test_source"] == HealthStatus.HEALTHY
        assert health["degraded_source"] == HealthStatus.DEGRADED

    def test_get_health_summary(self, registry, stub):
        registry.register("test_source", stub)
        summary = registry.get_health_summary()
        assert summary["healthy"] == 1
        assert summary["unavailable"] == 0
        assert summary["unknown"] == 0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_connector_registry_singleton(self):
        r1 = get_connector_registry()
        r2 = get_connector_registry()
        assert r1 is r2

    def test_reset_connector_registry(self, stub):
        r1 = get_connector_registry()
        r1.register("test_source", stub)
        assert r1.list_sources()

        reset_connector_registry()
        r2 = get_connector_registry()
        assert r2.list_sources() == []
        assert r1 is not r2


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_clear(self, registry, stub):
        registry.register("test_source", stub)
        assert registry.list_sources()
        registry.clear()
        assert registry.list_sources() == []

    def test_stop_all(self, registry, stub):
        """stop_all 应调用每个 connector 的 stop() 方法（如果存在）."""
        stop_called = []

        class _StoppableStub(_StubConnector):
            @property
            def source(self) -> str:
                return "stoppable"

            def stop(self):
                stop_called.append(self.source)

        registry.register("stoppable", _StoppableStub())
        registry.stop_all()
        assert stop_called == ["stoppable"]

    def test_stop_all_no_stop_method(self, registry, stub):
        """没有 stop() 方法的 connector 不应报错."""
        registry.register("test_source", stub)
        registry.stop_all()  # 不应抛出异常


# ---------------------------------------------------------------------------
# discover_all (集成现有 source_registry)
# ---------------------------------------------------------------------------


class TestDiscoverAll:
    def test_discover_all_no_sources(self, registry):
        count = registry.discover_all()
        assert count >= 0  # 取决于 core/source_registry 的状态

    def test_discover_all_skips_already_registered(self, registry, stub):
        registry.register("test_source", stub)
        registry.discover_all()
        # test_source 仍然在列表中，不会被覆盖
        assert "test_source" in registry.list_sources()
        assert registry.get_connector("test_source") is stub


# ---------------------------------------------------------------------------
# DatasetRouter fallback groups
# ---------------------------------------------------------------------------


class TestDatasetRouter:
    def test_build_orders_fallback_chain_by_source_spec_priority(self, registry, monkeypatch):
        specs = {
            "daily_quotes_cn": [
                SourceSpec(
                    source_type=SourceType.BAOSTOCK,
                    source_name="BaoStock",
                    connector_class="connectors.market.baostock.BaostockMarketConnector",
                    fallback_group="daily_quotes_cn",
                    fallback_priority=2,
                ),
                SourceSpec(
                    source_type=SourceType.CJPY,
                    source_name="Tinysoft",
                    connector_class="connectors.market.cjpy.CjpyMarketConnector",
                    fallback_group="daily_quotes_cn",
                    fallback_priority=0,
                ),
                SourceSpec(
                    source_type=SourceType.WIND,
                    source_name="Wind",
                    connector_class="connectors.market.wind.WindMarketConnector",
                    fallback_group="daily_quotes_cn",
                    fallback_priority=1,
                ),
            ]
        }
        monkeypatch.setattr("core.source_registry.get_fallback_groups", lambda: specs)

        router = DatasetRouter(registry)

        assert router.build() == 1
        assert router.get_chain("daily_quotes_cn") == ["cjpy", "wind", "baostock"]
