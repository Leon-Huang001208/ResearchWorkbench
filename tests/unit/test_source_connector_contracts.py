"""Source registry connector contract tests."""
import importlib

import data_sources  # noqa: F401
from core.connectors.base import BaseConnector
from core.source_registry import get_enabled


def test_all_enabled_sources_use_connector_classes():
    for spec in get_enabled():
        module_name, class_name = spec.connector_class.rsplit(".", 1)
        connector_cls = getattr(importlib.import_module(module_name), class_name)

        assert issubclass(connector_cls, BaseConnector), spec.source_type.value
        assert spec.adapter_class == spec.connector_class
        assert spec.connector_dataset, spec.source_type.value
        assert spec.pipeline_kind in {"document", "market"}


def test_legacy_adapter_class_alias_remains_supported():
    from core.contracts.documents_v1 import SourceType
    from core.source_registry import SourceSpec

    spec = SourceSpec(
        source_type=SourceType.OTHER,
        source_name="legacy",
        adapter_class="connectors.document.cls.CLSDocumentConnector",
        connector_dataset="telegram",
    )

    assert spec.connector_class == "connectors.document.cls.CLSDocumentConnector"
    assert spec.adapter_class == spec.connector_class


def test_document_sources_have_document_connector_datasets():
    document_specs = [spec for spec in get_enabled() if spec.pipeline_kind == "document"]

    expected = {
        "cls": "telegram",
        "cnstock": "news",
        "cnstock_flash": "flash",
        "cninfo": "announcements",
        "zhiqiu_reports": "report",
        "zhiqiu_wechat": "news",
        "zhiqiu_transcript": "meeting",
    }
    actual = {spec.source_type.value: spec.connector_dataset for spec in document_specs}

    assert actual == expected


def test_orchestrator_identifies_connector_sources_from_spec_metadata():
    from core.contracts.documents_v1 import SourceType
    from services.crawl_orchestrator import CrawlOrchestrator

    orchestrator = CrawlOrchestrator.__new__(CrawlOrchestrator)

    assert orchestrator._source_uses_connector(SourceType.ZHIQIU_REPORTS) is True
