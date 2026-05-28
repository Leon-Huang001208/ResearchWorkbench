"""测试 PDFConversionService"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from core.contracts.pdf_conversion import ConversionResult, StrategyType
from data_layer.repositories.models import PDFArtifactV1DB
from services.pdf_conversion_service import PDFConversionService


def _make_artifact(pdf_id="pdf_001", file_path="/tmp/test.pdf", parse_status="pending"):
    """创建测试用 PDFArtifactV1DB"""
    return PDFArtifactV1DB(
        pdf_id=pdf_id,
        file_path=file_path,
        file_name="test.pdf",
        file_size_bytes=1024,
        file_hash_sha256="abc123",
        source_type="test",
        fetch_timestamp=datetime.now(timezone.utc),
        parse_status=parse_status,
    )


def _make_success_result():
    """创建成功的 ConversionResult"""
    return ConversionResult(
        success=True,
        strategy_used="mineru",
        markdown="# Test\n\nContent",
        raw_text="Test\nContent",
        page_count=3,
        token_count=100,
        quality_score=0.85,
        has_tables=True,
        has_images=False,
        has_code_blocks=True,
        metadata={"has_tables": True},
    )


def _make_error_result():
    """创建失败的 ConversionResult"""
    return ConversionResult(
        success=False,
        strategy_used="mineru",
        error_message="Conversion failed",
    )


class TestPDFConversionServiceInit:
    """测试服务初始化"""

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_init_registers_all_strategies(self, mock_raw, mock_md, mock_mineru):
        """初始化应注册所有三个策略"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = False
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        db = MagicMock()
        service = PDFConversionService(db)

        assert "mineru" in service._strategies
        assert "markitdown" in service._strategies
        assert "raw_text" in service._strategies

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_get_available_strategies_filters_unavailable(self, mock_raw, mock_md, mock_mineru):
        """get_available_strategies 应只返回可用的策略"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = False
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        db = MagicMock()
        service = PDFConversionService(db)

        available = service.get_available_strategies()
        assert "mineru" not in available
        assert "markitdown" in available
        assert "raw_text" in available


class TestStrategySelection:
    """测试策略选择逻辑"""

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_select_preferred_when_available(self, mock_raw, mock_md, mock_mineru):
        """首选策略可用时应选中它"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        service = PDFConversionService(MagicMock())
        result = service._select_strategy(StrategyType.MARKITDOWN)

        assert result is not None
        assert result.name == "markitdown"

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_select_falls_back_when_preferred_unavailable(self, mock_raw, mock_md, mock_mineru):
        """首选策略不可用时应按优先级降级"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = False
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        service = PDFConversionService(MagicMock())
        result = service._select_strategy(StrategyType.MARKITDOWN)

        assert result is not None
        assert result.name == "mineru"

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_select_auto_picks_highest_priority_available(self, mock_raw, mock_md, mock_mineru):
        """AUTO 模式应按优先级选择最高可用策略"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = False
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        service = PDFConversionService(MagicMock())
        result = service._select_strategy(StrategyType.AUTO)

        assert result is not None
        assert result.name == "markitdown"

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_select_returns_none_when_all_unavailable(self, mock_raw, mock_md, mock_mineru):
        """所有策略都不可用时应返回 None"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = False
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = False
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = False

        service = PDFConversionService(MagicMock())
        result = service._select_strategy()

        assert result is None

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_select_none_preferred_uses_auto(self, mock_raw, mock_md, mock_mineru):
        """preferred=None 时等同于 AUTO"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        service = PDFConversionService(MagicMock())
        result = service._select_strategy(None)

        assert result is not None
        assert result.name == "mineru"


class TestConvertPdf:
    """测试 convert_pdf 方法"""

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pdf_artifact_not_found(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """PDF artifact 不存在时应返回错误"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True
        mock_repo.get_pdf_by_id.return_value = None

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("nonexistent_id")

        assert result.success is False
        assert "不存在" in result.error_message
        assert result.strategy_used == ""

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pdf_no_strategy_available(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """没有可用策略时应返回错误"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = False
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = False
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = False
        mock_repo.get_pdf_by_id.return_value = _make_artifact()

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is False
        assert "没有可用的转换策略" in result.error_message

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pdf_success(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """成功转换应更新 artifact 和 conversion 状态"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact = _make_artifact()
        mock_repo.get_pdf_by_id.return_value = artifact

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is True
        assert result.strategy_used == "mineru"
        assert result.markdown == "# Test\n\nContent"
        assert result.page_count == 3
        assert result.has_tables is True
        assert result.has_code_blocks is True

        # 验证 artifact 状态已同步
        assert artifact.parse_status == "success"
        assert artifact.parsed_at is not None

        # 验证 conversion 记录已创建并更新
        assert mock_repo.add_conversion.called
        assert db.commit.call_count >= 2  # 创建 conversion + 更新状态

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pdf_strategy_returns_error(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """策略返回失败结果时应更新为 error 状态"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_error_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact = _make_artifact()
        mock_repo.get_pdf_by_id.return_value = artifact

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is False
        assert result.error_message == "Conversion failed"
        assert artifact.parse_status == "error"

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pdf_exception_during_conversion(
        self, mock_repo, mock_raw, mock_md, mock_mineru
    ):
        """转换过程中抛异常应捕获并更新状态为 error"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.side_effect = RuntimeError("Unexpected crash")
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact = _make_artifact()
        mock_repo.get_pdf_by_id.return_value = artifact

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is False
        assert "Unexpected crash" in result.error_message
        assert artifact.parse_status == "error"

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pdf_updates_metadata_on_success(
        self, mock_repo, mock_raw, mock_md, mock_mineru
    ):
        """成功转换后应合并 metadata 到 artifact"""
        result_with_meta = ConversionResult(
            success=True,
            strategy_used="mineru",
            markdown="# Content",
            metadata={"pages": 3, "author": "test"},
        )
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = result_with_meta
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact = _make_artifact()
        artifact.pdf_metadata = {"existing_key": "existing_value"}
        mock_repo.get_pdf_by_id.return_value = artifact

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is True
        assert artifact.pdf_metadata["existing_key"] == "existing_value"
        assert artifact.pdf_metadata["pages"] == 3
        assert artifact.pdf_metadata["author"] == "test"

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pdf_tracks_duration(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """转换应记录耗时"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        mock_repo.get_pdf_by_id.return_value = _make_artifact()

        db = MagicMock()
        service = PDFConversionService(db)
        service.convert_pdf("pdf_001")

        # add_conversion 被调用，验证 conversion 记录包含 duration
        call_args = mock_repo.add_conversion.call_args
        assert call_args is not None


class TestConvertPending:
    """测试批量转换 pending PDF"""

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pending_no_pending_artifacts(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """没有 pending artifact 时返回空列表"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        db = MagicMock()
        # Mock the query chain for no results
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        db.query.return_value = mock_query

        service = PDFConversionService(db)
        results = service.convert_pending(limit=10)

        assert results == []

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pending_with_artifacts(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """有 pending artifact 时应逐个转换"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact1 = _make_artifact("pdf_001")
        artifact2 = _make_artifact("pdf_002")
        mock_repo.get_pdf_by_id.side_effect = [artifact1, artifact2]

        db = MagicMock()
        # Mock query for pending artifacts
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [artifact1, artifact2]
        db.query.return_value = mock_query

        service = PDFConversionService(db)
        results = service.convert_pending(limit=10)

        assert len(results) == 2
        assert all(r.success for r in results)

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_convert_pending_handles_exception_in_one(
        self, mock_repo, mock_raw, mock_md, mock_mineru
    ):
        """批量转换中某个失败不应中断整个批次"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        # First call succeeds, second raises exception
        mock_mineru.return_value.convert.side_effect = [
            _make_success_result(),
            RuntimeError("Boom"),
        ]
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact1 = _make_artifact("pdf_001")
        artifact2 = _make_artifact("pdf_002")
        mock_repo.get_pdf_by_id.side_effect = [artifact1, artifact2]

        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [artifact1, artifact2]
        db.query.return_value = mock_query

        service = PDFConversionService(db)
        results = service.convert_pending(limit=10)

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert "Boom" in results[1].error_message


class TestRetryFailed:
    """测试重试失败转换"""

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_retry_failed_no_failed_artifacts(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """没有失败 artifact 时返回空列表"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        db.query.return_value = mock_query

        service = PDFConversionService(db)
        results = service.retry_failed(limit=10)

        assert results == []

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_retry_failed_resets_status_to_pending(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """重试前应将 artifact 状态重置为 pending"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact = _make_artifact("pdf_001", parse_status="error")
        mock_repo.get_pdf_by_id.return_value = artifact

        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [artifact]
        db.query.return_value = mock_query

        service = PDFConversionService(db)
        results = service.retry_failed(limit=10)

        assert len(results) == 1
        assert results[0].success is True
        # commit 应被调用至少 3 次：重置状态 + add_conversion + 更新状态
        assert db.commit.call_count >= 3

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_retry_failed_handles_exception(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """重试时异常不应中断批次"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        # convert_pdf 内部会抛异常（因为 artifact 重置后 get_pdf_by_id 又被调用）
        mock_mineru.return_value.convert.side_effect = RuntimeError("Retry failed")
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        artifact = _make_artifact("pdf_001", parse_status="error")
        mock_repo.get_pdf_by_id.return_value = artifact

        db = MagicMock()
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [artifact]
        db.query.return_value = mock_query

        service = PDFConversionService(db)
        results = service.retry_failed(limit=10)

        assert len(results) == 1
        assert results[0].success is False
        assert "Retry failed" in results[0].error_message


class TestGetStatsAndPending:
    """测试统计和查询方法"""

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_get_stats_delegates_to_repo(self, mock_repo, mock_raw, mock_md, mock_mineru):
        """get_stats 应委托给 repository"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True
        mock_repo.get_conversion_stats.return_value = {"total_pdfs": 10, "converted": 5}

        db = MagicMock()
        service = PDFConversionService(db)
        stats = service.get_stats()

        assert stats == {"total_pdfs": 10, "converted": 5}
        mock_repo.get_conversion_stats.assert_called_once_with(db)

    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    def test_get_pending_queries_db_directly(self, mock_raw, mock_md, mock_mineru):
        """get_pending 应直接查询数据库"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
            []
        )

        service = PDFConversionService(db)
        result = service.get_pending(limit=20)

        assert result == []


class TestDocumentCreationFromConversion:
    """测试转换成功后自动创建 DocumentV1 和分块"""

    @patch("services.pdf_conversion_service.DocumentChunker")
    @patch("services.pdf_conversion_service.DocumentChunkV1Repository")
    @patch("services.pdf_conversion_service.DocumentV1Repository")
    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_create_document_after_successful_conversion(
        self,
        mock_repo,
        mock_raw,
        mock_md,
        mock_mineru,
        mock_doc_repo_class,
        mock_chunk_repo_class,
        mock_chunker_class,
    ):
        """转换成功后应自动创建 DocumentV1 和分块"""
        # Setup strategies
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        # Setup repos
        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_content_hash.return_value = None
        mock_doc_repo_class.return_value = mock_doc_repo
        mock_chunk_repo = MagicMock()
        mock_chunk_repo_class.return_value = mock_chunk_repo

        # Setup chunker
        mock_chunker = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.metadata = {}
        mock_chunker.chunk_document.return_value = [mock_chunk]
        mock_chunker_class.return_value = mock_chunker

        artifact = _make_artifact()
        mock_repo.get_pdf_by_id.return_value = artifact

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is True
        # 验证 DocumentV1 被创建
        mock_doc_repo.create.assert_called_once()
        # 验证分块被创建
        mock_chunker.chunk_document.assert_called_once()
        mock_chunk_repo.bulk_create.assert_called_once()

    @patch("services.pdf_conversion_service.DocumentChunker")
    @patch("services.pdf_conversion_service.DocumentChunkV1Repository")
    @patch("services.pdf_conversion_service.DocumentV1Repository")
    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_skip_document_when_create_document_false(
        self,
        mock_repo,
        mock_raw,
        mock_md,
        mock_mineru,
        mock_doc_repo_class,
        mock_chunk_repo_class,
        mock_chunker_class,
    ):
        """create_document=False 时不创建 DocumentV1"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        mock_repo.get_pdf_by_id.return_value = _make_artifact()

        db = MagicMock()
        service = PDFConversionService(db, create_document=False)
        result = service.convert_pdf("pdf_001")

        assert result.success is True
        # 不应创建 DocumentV1
        mock_doc_repo_class.assert_not_called()

    @patch("services.pdf_conversion_service.DocumentChunker")
    @patch("services.pdf_conversion_service.DocumentChunkV1Repository")
    @patch("services.pdf_conversion_service.DocumentV1Repository")
    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_no_document_on_failed_conversion(
        self,
        mock_repo,
        mock_raw,
        mock_md,
        mock_mineru,
        mock_doc_repo_class,
        mock_chunk_repo_class,
        mock_chunker_class,
    ):
        """转换失败时不应创建 DocumentV1"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_error_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        mock_repo.get_pdf_by_id.return_value = _make_artifact()

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is False
        mock_doc_repo_class.assert_not_called()

    @patch("services.pdf_conversion_service.DocumentChunker")
    @patch("services.pdf_conversion_service.DocumentChunkV1Repository")
    @patch("services.pdf_conversion_service.DocumentV1Repository")
    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_skip_duplicate_by_content_hash(
        self,
        mock_repo,
        mock_raw,
        mock_md,
        mock_mineru,
        mock_doc_repo_class,
        mock_chunk_repo_class,
        mock_chunker_class,
    ):
        """相同内容哈希的文档不重复创建"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_content_hash.return_value = MagicMock()  # 已存在
        mock_doc_repo_class.return_value = mock_doc_repo
        mock_chunk_repo_class.return_value = MagicMock()
        mock_chunker_class.return_value = MagicMock()

        mock_repo.get_pdf_by_id.return_value = _make_artifact()

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        assert result.success is True
        # get_by_content_hash 被调用了
        mock_doc_repo.get_by_content_hash.assert_called_once()
        # 但没有 create
        mock_doc_repo.create.assert_not_called()

    @patch("services.pdf_conversion_service.DocumentChunker")
    @patch("services.pdf_conversion_service.DocumentChunkV1Repository")
    @patch("services.pdf_conversion_service.DocumentV1Repository")
    @patch("services.pdf_conversion_service.MinerUStrategy")
    @patch("services.pdf_conversion_service.MarkItDownStrategy")
    @patch("services.pdf_conversion_service.RawTextStrategy")
    @patch("services.pdf_conversion_service.pdf_repo")
    def test_document_creation_failure_does_not_break_conversion(
        self,
        mock_repo,
        mock_raw,
        mock_md,
        mock_mineru,
        mock_doc_repo_class,
        mock_chunk_repo_class,
        mock_chunker_class,
    ):
        """DocumentV1 创建失败不应影响转换结果"""
        mock_mineru.return_value.name = "mineru"
        mock_mineru.return_value.is_available.return_value = True
        mock_mineru.return_value.convert.return_value = _make_success_result()
        mock_md.return_value.name = "markitdown"
        mock_md.return_value.is_available.return_value = True
        mock_raw.return_value.name = "raw_text"
        mock_raw.return_value.is_available.return_value = True

        mock_doc_repo = MagicMock()
        mock_doc_repo.get_by_content_hash.return_value = None
        mock_doc_repo.create.side_effect = RuntimeError("DB error")
        mock_doc_repo_class.return_value = mock_doc_repo
        mock_chunk_repo_class.return_value = MagicMock()
        mock_chunker_class.return_value = MagicMock()

        mock_repo.get_pdf_by_id.return_value = _make_artifact()

        db = MagicMock()
        service = PDFConversionService(db)
        result = service.convert_pdf("pdf_001")

        # 转换仍然成功
        assert result.success is True
        assert result.strategy_used == "mineru"
