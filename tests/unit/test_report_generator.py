"""Unit tests for report_generator."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.report_generator import ReportGenerator


@pytest.mark.asyncio
async def test_generate_summary_report():
    """Test generating a summary report."""
    with patch("core.services.report_generator.AssetAnalysisService") as MockService:
        mock_snapshot = MagicMock()
        mock_snapshot.canonical_id = "600519.SH"
        mock_snapshot.as_of = datetime(2024, 5, 10, tzinfo=timezone.utc)
        mock_snapshot.event_impact = ["Earnings beat"]
        mock_snapshot.valuation = {"pe_ttm": 35.0, "historical_percentile_pe": 0.6}
        mock_snapshot.financial = {"roe": {"ttm": 0.25}, "debt_ratio": 0.3}
        mock_snapshot.price_volume = {"close_price": 1800.0}
        mock_snapshot.industry = {}
        mock_snapshot.shareholder = {}
        mock_snapshot.fund_flow = {}

        mock_instance = MockService.return_value
        mock_instance.analyze = AsyncMock(return_value=mock_snapshot)

        generator = ReportGenerator()
        result = await generator.generate("600519.SH", "summary", mock_snapshot.as_of)

        assert "report_id" in result
        assert "content" in result
        assert "投资摘要报告" in result["content"]
        assert "600519.SH" in result["content"]
        assert "核心指标" in result["content"]
        assert "投资建议" in result["content"]


@pytest.mark.asyncio
async def test_generate_valuation_report():
    """Test generating a valuation report."""
    with patch("core.services.report_generator.AssetAnalysisService") as MockService:
        mock_snapshot = MagicMock()
        mock_snapshot.canonical_id = "600036.SH"
        mock_snapshot.as_of = datetime(2024, 5, 10, tzinfo=timezone.utc)
        mock_snapshot.event_impact = []
        mock_snapshot.valuation = {"pe_ttm": 8.0, "historical_percentile_pe": 0.3}
        mock_snapshot.financial = {}
        mock_snapshot.price_volume = {"close_price": 35.0}
        mock_snapshot.industry = {"industry_pe": 10.0, "industry_pb": 1.2}

        mock_instance = MockService.return_value
        mock_instance.analyze = AsyncMock(return_value=mock_snapshot)

        generator = ReportGenerator()
        result = await generator.generate("600036.SH", "valuation", mock_snapshot.as_of)

        assert "report_id" in result
        assert "content" in result
        assert "估值分析报告" in result["content"]
        assert "估值指标" in result["content"]
        assert "估值结论" in result["content"]


@pytest.mark.asyncio
async def test_generate_full_report():
    """Test generating a full report."""
    with patch("core.services.report_generator.AssetAnalysisService") as MockService:
        mock_snapshot = MagicMock()
        mock_snapshot.canonical_id = "600519.SH"
        mock_snapshot.as_of = datetime(2024, 5, 10, tzinfo=timezone.utc)
        mock_snapshot.event_impact = ["Q1 earnings beat by 10%", "Dividend announcement"]
        mock_snapshot.valuation = {"pe_ttm": 35.0, "historical_percentile_pe": 0.6}
        mock_snapshot.financial = {
            "roe": {"ttm": 0.25, "yoy": 0.05, "qoq": 0.02},
            "debt_ratio": 0.3,
            "revenue": {"ttm": 100e8, "yoy": 0.1, "qoq": 0.03},
            "net_profit": {"ttm": 50e8, "yoy": 0.15, "qoq": 0.04},
            "eps": {"ttm": 30.0, "yoy": 0.1, "qoq": 0.02},
        }
        mock_snapshot.price_volume = {
            "close_price": 1800.0,
            "high_52w": 2000.0,
            "low_52w": 1500.0,
        }
        mock_snapshot.industry = {"industry_pe": 30.0, "industry_pb": 8.0}
        mock_snapshot.shareholder = {"controlling_shareholder": "State-owned"}
        mock_snapshot.fund_flow = {
            "institutional_holding": 0.5,
            "main_net_inflow": 1e8,
            "northbound_holding": 0.08,
            "pledge_ratio": 0.1,
        }

        mock_instance = MockService.return_value
        mock_instance.analyze = AsyncMock(return_value=mock_snapshot)

        generator = ReportGenerator()
        result = await generator.generate("600519.SH", "full", mock_snapshot.as_of)

        assert "report_id" in result
        assert "content" in result
        assert "完整投资研究报告" in result["content"]
        assert "基本信息" in result["content"]
        assert "财务分析" in result["content"]
        assert "估值分析" in result["content"]
        assert "资金面分析" in result["content"]
        assert "近期重大事件" in result["content"]
        assert "投资建议" in result["content"]


@pytest.mark.asyncio
async def test_get_report_content():
    """Test retrieving report content."""
    with patch("core.services.report_generator.AssetAnalysisService") as MockService:
        mock_snapshot = MagicMock()
        mock_snapshot.canonical_id = "600519.SH"
        mock_snapshot.as_of = datetime(2024, 5, 10, tzinfo=timezone.utc)
        mock_snapshot.event_impact = []
        mock_snapshot.valuation = {}
        mock_snapshot.financial = {}
        mock_snapshot.price_volume = {}
        mock_snapshot.industry = {}

        mock_instance = MockService.return_value
        mock_instance.analyze = AsyncMock(return_value=mock_snapshot)

        generator = ReportGenerator()
        result = await generator.generate("600519.SH", "summary", mock_snapshot.as_of)
        report_id = result["report_id"]

        content = await generator.get_report_content(report_id)
        assert content == result["content"]


@pytest.mark.asyncio
async def test_get_report_content_not_found():
    """Test retrieving non-existent report raises error."""
    generator = ReportGenerator()

    with pytest.raises(ValueError, match="Report not found"):
        await generator.get_report_content("non_existent_id")
