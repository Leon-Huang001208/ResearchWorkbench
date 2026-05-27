"""测试 PDF 转换策略基类和契约模型"""
import pytest

from core.contracts.pdf_conversion import (
    ConversionRequest,
    ConversionResult,
    ConversionStatus,
    ConversionStatusResponse,
    StrategyType,
)
from ingestion.converters.base import PDFConversionStrategy


class TestStrategyType:
    """StrategyType 枚举测试"""

    def test_enum_values(self):
        assert StrategyType.AUTO.value == "auto"
        assert StrategyType.MARKITDOWN.value == "markitdown"
        assert StrategyType.MINERU.value == "mineru"
        assert StrategyType.RAW_TEXT.value == "raw_text"

    def test_enum_from_string(self):
        assert StrategyType("auto") == StrategyType.AUTO
        assert StrategyType("markitdown") == StrategyType.MARKITDOWN


class TestConversionStatus:
    """ConversionStatus 枚举测试"""

    def test_enum_values(self):
        assert ConversionStatus.PENDING.value == "pending"
        assert ConversionStatus.RUNNING.value == "running"
        assert ConversionStatus.SUCCESS.value == "success"
        assert ConversionStatus.ERROR.value == "error"
        assert ConversionStatus.SKIPPED.value == "skipped"

    def test_enum_from_string(self):
        assert ConversionStatus("success") == ConversionStatus.SUCCESS
        assert ConversionStatus("error") == ConversionStatus.ERROR


class TestConversionResult:
    """ConversionResult 模型测试"""

    def test_success_result(self):
        result = ConversionResult(
            success=True,
            strategy_used="raw_text",
            raw_text="Hello World",
            page_count=5,
            token_count=100,
            quality_score=0.85,
            has_tables=True,
        )
        assert result.success is True
        assert result.strategy_used == "raw_text"
        assert result.raw_text == "Hello World"
        assert result.page_count == 5
        assert result.token_count == 100
        assert result.quality_score == 0.85
        assert result.has_tables is True
        assert result.error_message == ""

    def test_error_result(self):
        result = ConversionResult(
            success=False,
            strategy_used="markitdown",
            error_message="File not found",
        )
        assert result.success is False
        assert result.error_message == "File not found"
        assert result.raw_text == ""
        assert result.markdown == ""
        assert result.page_count == 0

    def test_default_values(self):
        result = ConversionResult(success=True, strategy_used="raw_text")
        assert result.raw_text == ""
        assert result.markdown == ""
        assert result.has_tables is False
        assert result.has_images is False
        assert result.has_code_blocks is False
        assert result.quality_score is None
        assert result.metadata == {}

    def test_metadata_field(self):
        result = ConversionResult(
            success=True,
            strategy_used="raw_text",
            metadata={"first_page_chars": 500, "pages": 10},
        )
        assert result.metadata["first_page_chars"] == 500
        assert result.metadata["pages"] == 10

    def test_quality_score_range(self):
        """quality_score 应该在 0.0-1.0 范围内"""
        with pytest.raises(Exception):
            ConversionResult(
                success=True,
                strategy_used="raw_text",
                quality_score=1.5,
            )
        with pytest.raises(Exception):
            ConversionResult(
                success=True,
                strategy_used="raw_text",
                quality_score=-0.1,
            )

    def test_serialization(self):
        result = ConversionResult(
            success=True,
            strategy_used="raw_text",
            raw_text="Test content",
            page_count=3,
            token_count=50,
        )
        d = result.model_dump()
        assert d["success"] is True
        assert d["strategy_used"] == "raw_text"
        assert d["raw_text"] == "Test content"
        assert d["page_count"] == 3

    def test_deserialization(self):
        data = {
            "success": True,
            "strategy_used": "markitdown",
            "markdown": "# Title\nContent",
            "page_count": 10,
            "token_count": 500,
        }
        result = ConversionResult(**data)
        assert result.success is True
        assert result.markdown == "# Title\nContent"


class TestConversionRequest:
    """ConversionRequest 模型测试"""

    def test_default_strategy(self):
        req = ConversionRequest(pdf_id="pdf_001")
        assert req.pdf_id == "pdf_001"
        assert req.strategy == StrategyType.AUTO

    def test_specific_strategy(self):
        req = ConversionRequest(pdf_id="pdf_002", strategy=StrategyType.RAW_TEXT)
        assert req.strategy == StrategyType.RAW_TEXT


class TestConversionStatusResponse:
    """ConversionStatusResponse 模型测试"""

    def test_running_status(self):
        resp = ConversionStatusResponse(
            conversion_id="conv_001",
            pdf_id="pdf_001",
            status=ConversionStatus.RUNNING,
        )
        assert resp.conversion_id == "conv_001"
        assert resp.status == ConversionStatus.RUNNING

    def test_completed_status(self):
        resp = ConversionStatusResponse(
            conversion_id="conv_001",
            pdf_id="pdf_001",
            status=ConversionStatus.SUCCESS,
            strategy_used="raw_text",
            page_count=10,
            token_count=500,
            quality_score=0.9,
        )
        assert resp.status == ConversionStatus.SUCCESS
        assert resp.quality_score == 0.9


class TestPDFConversionStrategy:
    """PDFConversionStrategy 基类测试"""

    class MockStrategy(PDFConversionStrategy):
        """用于测试的模拟策略"""

        def is_available(self) -> bool:
            return True

        def convert(self, pdf_path: str) -> ConversionResult:
            return ConversionResult(
                success=True,
                strategy_used="mock",
                raw_text="mock text",
            )

        @property
        def strategy_type(self) -> StrategyType:
            return StrategyType.RAW_TEXT

        @property
        def name(self) -> str:
            return "mock"

    def test_strategy_interface(self):
        strategy = self.MockStrategy()
        assert strategy.is_available() is True
        result = strategy.convert("test.pdf")
        assert result.success is True
        assert result.raw_text == "mock text"
        assert strategy.strategy_type == StrategyType.RAW_TEXT
        assert strategy.name == "mock"

    def test_estimate_tokens_empty(self):
        assert PDFConversionStrategy.estimate_tokens("") == 0

    def test_estimate_tokens_english(self):
        tokens = PDFConversionStrategy.estimate_tokens("Hello world")
        assert tokens > 0

    def test_estimate_tokens_chinese(self):
        tokens = PDFConversionStrategy.estimate_tokens("你好世界测试文本")
        assert tokens > 0
