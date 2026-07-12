from types import SimpleNamespace
from unittest.mock import MagicMock

from core.contracts.pdf_conversion import ConversionResult, StrategyType
from ingestion.converters.base import PDFConversionStrategy
from services import pdf_conversion_service as service_module
from services.pdf_conversion_service import PDFConversionService


class _FakeStrategy(PDFConversionStrategy):
    def __init__(self, name: str, result: ConversionResult):
        self._name = name
        self._result = result
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def convert(self, pdf_path: str) -> ConversionResult:
        self.calls += 1
        return self._result

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType(self._name)

    @property
    def name(self) -> str:
        return self._name


def test_convert_pdf_falls_back_after_empty_mineru_output(monkeypatch):
    db = MagicMock()
    artifact = SimpleNamespace(
        pdf_id="pdf_test",
        file_path="/tmp/report.pdf",
        file_name="report.pdf",
        source_type="zhiqiu_reports",
        source_name="知丘",
        source_url=None,
        source_broker="测试券商",
        source_author=None,
        pdf_metadata={},
        parse_status="error",
        parsed_at=None,
    )

    monkeypatch.setattr(service_module.pdf_repo, "get_pdf_by_id", lambda _db, _pdf_id: artifact)
    monkeypatch.setattr(service_module.pdf_repo, "add_conversion", lambda _db, _conversion: None)
    monkeypatch.setattr(
        service_module, "persist_raw_text", lambda pdf_id, text: f"/tmp/{pdf_id}.txt"
    )

    mineru = _FakeStrategy(
        "mineru",
        ConversionResult(
            success=False,
            strategy_used="mineru",
            error_message="mineru 输出为空",
        ),
    )
    raw_text = _FakeStrategy(
        "raw_text",
        ConversionResult(
            success=True,
            strategy_used="raw_text",
            raw_text="研报正文内容",
            page_count=2,
            token_count=20,
        ),
    )

    service = PDFConversionService(db, create_document=False)
    service._strategies = {"mineru": mineru, "raw_text": raw_text}
    service.STRATEGY_PRIORITY = [StrategyType.MINERU, StrategyType.RAW_TEXT]

    result = service.convert_pdf("pdf_test")

    assert result.success is True
    assert result.strategy_used == "raw_text"
    assert mineru.calls == 1
    assert raw_text.calls == 1
    assert artifact.parse_status == "success"
