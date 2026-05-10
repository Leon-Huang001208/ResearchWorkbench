"""
测试 ingest CLI 命令
"""
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from app.cli.commands.ingest import ingest_command


class TestIngestCLI:
    """测试 ingest CLI 命令"""

    def test_ingest_basic(self, tmp_path):
        """测试基本 ingest 命令"""
        runner = CliRunner()
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试文本内容", encoding="utf-8")

        with patch("app.cli.commands.ingest.IngestService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_file.return_value = {
                "doc_id": "test-doc-123",
                "title": "test.txt",
                "assertions_extracted": 3,
                "assertions_approved": 2,
                "assertions_pending": 1,
                "events_extracted": 2,
                "events_approved": 1,
                "events_pending": 1,
            }
            mock_service_class.return_value = mock_service

            result = runner.invoke(ingest_command, ["--file", str(test_file)])

            assert result.exit_code == 0
            assert "Ingesting file" in result.output
            assert "Ingest completed successfully" in result.output
            mock_service.ingest_file.assert_called_once()

    def test_ingest_with_options(self, tmp_path):
        """测试带选项的 ingest 命令"""
        runner = CliRunner()
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试文本内容", encoding="utf-8")

        with patch("app.cli.commands.ingest.IngestService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_file.return_value = {
                "doc_id": "test-doc-123",
                "title": "测试标题",
                "assertions_extracted": 5,
                "assertions_approved": 3,
                "assertions_pending": 2,
                "events_extracted": 3,
                "events_approved": 2,
                "events_pending": 1,
            }
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                ingest_command,
                [
                    "--file",
                    str(test_file),
                    "--source-type",
                    "report",
                    "--source-name",
                    "券商研报",
                    "--title",
                    "测试标题",
                ],
            )

            assert result.exit_code == 0
            call_args = mock_service.ingest_file.call_args
            assert call_args[1]["source_type"] == "report"
            assert call_args[1]["source_name"] == "券商研报"
            assert call_args[1]["title"] == "测试标题"

    def test_ingest_file_not_found(self):
        """测试文件不存在的情况"""
        runner = CliRunner()

        result = runner.invoke(ingest_command, ["--file", "/nonexistent/file.txt"])

        assert result.exit_code != 0
        assert "File not found" in result.output

    def test_ingest_missing_file(self):
        """测试缺少必需的 file 参数"""
        runner = CliRunner()

        result = runner.invoke(ingest_command, [])

        assert result.exit_code != 0
        assert "Missing option" in result.output

    def test_ingest_with_pending_items(self, tmp_path):
        """测试有待审核项目的提示"""
        runner = CliRunner()
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="utf-8")

        with patch("app.cli.commands.ingest.IngestService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_file.return_value = {
                "doc_id": "test-doc-123",
                "title": "test.txt",
                "assertions_extracted": 3,
                "assertions_approved": 1,
                "assertions_pending": 2,
                "events_extracted": 2,
                "events_approved": 0,
                "events_pending": 2,
            }
            mock_service_class.return_value = mock_service

            result = runner.invoke(ingest_command, ["--file", str(test_file)])

            assert result.exit_code == 0
            assert "Tip" in result.output
            assert "af review list" in result.output

    def test_ingest_error_handling(self, tmp_path):
        """测试错误处理"""
        runner = CliRunner()
        test_file = tmp_path / "test.txt"
        test_file.write_text("测试内容", encoding="utf-8")

        with patch("app.cli.commands.ingest.IngestService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.ingest_file.side_effect = Exception("测试错误")
            mock_service_class.return_value = mock_service

            result = runner.invoke(ingest_command, ["--file", str(test_file)])

            assert result.exit_code != 0
            assert "Failed to ingest file" in result.output
