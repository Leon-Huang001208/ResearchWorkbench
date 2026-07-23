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


def _build_service_with_two_strategies(db, mineru, raw_text):
    """构造一个仅含 mineru/raw_text 两个策略的 service（不创建 document）。"""
    service = PDFConversionService(db, create_document=False)
    service._strategies = {"mineru": mineru, "raw_text": raw_text}
    service.STRATEGY_PRIORITY = [StrategyType.MINERU, StrategyType.RAW_TEXT]
    return service


def _patch_artifact_and_persistence(monkeypatch, artifact):
    monkeypatch.setattr(service_module.pdf_repo, "get_pdf_by_id", lambda _db, _pdf_id: artifact)
    monkeypatch.setattr(service_module.pdf_repo, "add_conversion", lambda _db, _conversion: None)
    monkeypatch.setattr(
        service_module, "persist_raw_text", lambda pdf_id, text: f"/tmp/{pdf_id}.txt"
    )
    monkeypatch.setattr(
        service_module, "persist_markdown", lambda pdf_id, text: f"/tmp/{pdf_id}.md"
    )


def test_resolve_preferred_strategy_reads_global_config(monkeypatch):
    """未显式传参时，回退到 settings.PDF_PREFERRED_STRATEGY。"""
    service = PDFConversionService(MagicMock(), create_document=False)

    # auto / 空 → None（走自动降级）
    monkeypatch.setattr(service_module.settings, "PDF_PREFERRED_STRATEGY", "auto")
    assert service._resolve_preferred_strategy(None) is None

    monkeypatch.setattr(service_module.settings, "PDF_PREFERRED_STRATEGY", "  ")
    assert service._resolve_preferred_strategy(None) is None

    # 显式值仍优先于配置
    monkeypatch.setattr(service_module.settings, "PDF_PREFERRED_STRATEGY", "raw_text")
    assert service._resolve_preferred_strategy(StrategyType.MINERU) == StrategyType.MINERU

    # 配置值有效 → 解析为 StrategyType
    monkeypatch.setattr(service_module.settings, "PDF_PREFERRED_STRATEGY", "markitdown")
    assert service._resolve_preferred_strategy(None) == StrategyType.MARKITDOWN

    # 配置值无效 → 回退 None 并告警
    monkeypatch.setattr(service_module.settings, "PDF_PREFERRED_STRATEGY", "nonsense")
    assert service._resolve_preferred_strategy(None) is None


def test_low_quality_score_triggers_fallback(monkeypatch):
    """成功但质量分低于阈值时降级到下一策略。"""
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
    _patch_artifact_and_persistence(monkeypatch, artifact)

    mineru = _FakeStrategy(
        "mineru",
        ConversionResult(
            success=True,
            strategy_used="mineru",
            raw_text="低质量正文",
            quality_score=0.2,
            page_count=1,
            token_count=5,
        ),
    )
    raw_text = _FakeStrategy(
        "raw_text",
        ConversionResult(
            success=True,
            strategy_used="raw_text",
            raw_text="高质量正文",
            quality_score=0.9,
            page_count=2,
            token_count=20,
        ),
    )

    service = _build_service_with_two_strategies(db, mineru, raw_text)
    monkeypatch.setattr(service_module.settings, "PDF_PREFERRED_STRATEGY", "auto")
    monkeypatch.setattr(service_module.settings, "PDF_QUALITY_MIN_SCORE", 0.5)

    result = service.convert_pdf("pdf_test")

    assert result.success is True
    assert result.strategy_used == "raw_text"
    assert mineru.calls == 1
    assert raw_text.calls == 1
    assert artifact.parse_status == "success"


def test_quality_threshold_disabled_accepts_low_score(monkeypatch):
    """阈值为 0 时不过滤，低质量成功结果直接采纳。"""
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
    _patch_artifact_and_persistence(monkeypatch, artifact)

    mineru = _FakeStrategy(
        "mineru",
        ConversionResult(
            success=True,
            strategy_used="mineru",
            raw_text="低质量正文",
            quality_score=0.1,
            page_count=1,
            token_count=5,
        ),
    )
    raw_text = _FakeStrategy(
        "raw_text",
        ConversionResult(
            success=True,
            strategy_used="raw_text",
            raw_text="x",
            quality_score=0.0,
            page_count=1,
            token_count=1,
        ),
    )

    service = _build_service_with_two_strategies(db, mineru, raw_text)
    monkeypatch.setattr(service_module.settings, "PDF_PREFERRED_STRATEGY", "auto")
    monkeypatch.setattr(service_module.settings, "PDF_QUALITY_MIN_SCORE", 0.0)

    result = service.convert_pdf("pdf_test")

    # 阈值禁用 → mineru 低分成功直接采纳，不降级
    assert result.success is True
    assert result.strategy_used == "mineru"
    assert mineru.calls == 1
    assert raw_text.calls == 0
