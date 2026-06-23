"""测试 MinerUStrategy"""
import os
from unittest.mock import MagicMock, patch

from ingestion.converters.mineru import MinerUStrategy


class TestMinerUStrategy:
    """MinerUStrategy 测试"""

    def test_strategy_type(self):
        strategy = MinerUStrategy()
        assert strategy.name == "mineru"
        assert strategy.strategy_type.value == "mineru"

    def test_default_backend(self):
        strategy = MinerUStrategy()
        assert strategy._backend == "auto"
        assert strategy._method == "auto"

    def test_custom_backend(self):
        strategy = MinerUStrategy(backend="pipeline", method="ocr")
        assert strategy._backend == "pipeline"
        assert strategy._method == "ocr"

    @patch("ingestion.converters.mineru.shutil.which")
    def test_builds_new_mineru_cli_command(self, mock_which):
        mock_which.side_effect = lambda name: "/usr/local/bin/mineru" if name == "mineru" else None
        strategy = MinerUStrategy(backend="pipeline", method="txt")

        cmd = strategy._build_cli_command("input.pdf", "/tmp/out")

        assert cmd == [
            "/usr/local/bin/mineru",
            "-p",
            "input.pdf",
            "-o",
            "/tmp/out",
            "-m",
            "txt",
            "-b",
            "pipeline",
        ]

    def test_subprocess_env_strips_proxy(self, monkeypatch):
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:7890")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7890")

        env = MinerUStrategy._subprocess_env()

        assert "http_proxy" not in env
        assert "HTTPS_PROXY" not in env
        assert env["NO_PROXY"] == "*"

    @patch("ingestion.converters.mineru.HAS_MINERU", True)
    def test_convert_file_not_found(self):
        strategy = MinerUStrategy()
        result = strategy.convert("/nonexistent/path/file.pdf")
        assert result.success is False
        assert "文件不存在" in result.error_message

    @patch("ingestion.converters.mineru.HAS_MINERU", False)
    def test_convert_not_installed(self):
        strategy = MinerUStrategy()
        result = strategy.convert("test.pdf")
        assert result.success is False
        assert "未安装" in result.error_message

    @patch("ingestion.converters.mineru.HAS_MINERU", True)
    @patch.object(MinerUStrategy, "_check_cli_available", return_value=True)
    @patch.object(MinerUStrategy, "_model_cache_ready", return_value=False)
    def test_is_unavailable_without_model_cache(self, mock_cache, mock_cli):
        strategy = MinerUStrategy()

        assert strategy.is_available() is False

    @patch("ingestion.converters.mineru.HAS_MINERU", True)
    @patch.object(MinerUStrategy, "_check_cli_available", return_value=True)
    def test_model_cache_can_be_enabled_for_download(self, mock_cli, monkeypatch):
        monkeypatch.setenv("MINERU_ALLOW_MODEL_DOWNLOAD", "1")
        strategy = MinerUStrategy()

        assert strategy.is_available() is True

    def test_count_pages_with_anchors(self):
        md = "<!-- page: 1 -->\nContent\n\n<!-- page: 2 -->\nMore\n\n<!-- page: 5 -->\nLast"
        count = MinerUStrategy._count_pages(md)
        assert count == 5

    def test_count_pages_no_anchors(self):
        md = "Short content without page markers"
        count = MinerUStrategy._count_pages(md)
        assert count >= 1

    def test_detect_features_all(self):
        md = (
            "# Report\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "![Image](img.png)\n\n"
            "```python\ncode\n```"
        )
        features = MinerUStrategy._detect_features(md)
        assert features["has_tables"] is True
        assert features["has_images"] is True
        assert features["has_code_blocks"] is True

    def test_detect_features_none(self):
        features = MinerUStrategy._detect_features("Plain text only")
        assert features["has_tables"] is False
        assert features["has_images"] is False
        assert features["has_code_blocks"] is False

    def test_compute_quality_score_empty(self):
        score = MinerUStrategy._compute_quality_score("", {})
        assert score == 0.0

    def test_compute_quality_score_excellent(self):
        md = (
            "# Title\n\n## Section\n\n### Sub\n\n#### Detail\n\n"
            "Content " * 200 + "\n\n| A | B |\n|---|---|\n"
        )
        features = {"has_tables": True}
        score = MinerUStrategy._compute_quality_score(md, features)
        assert score > 0.8
        assert score <= 1.0


class TestMinerUStrategyWithMock:
    """使用 mock mineru 的测试"""

    @patch("ingestion.converters.mineru.HAS_MINERU", True)
    @patch("ingestion.converters.mineru.os.path.exists")
    @patch("ingestion.converters.mineru.tempfile.mkdtemp")
    def test_convert_success(self, mock_mkdtemp, mock_exists, tmp_path):
        """测试成功转换（使用 CLI mock）"""
        output_dir = str(tmp_path / "mineru_output")
        os.makedirs(output_dir, exist_ok=True)
        mock_mkdtemp.return_value = output_dir
        mock_exists.return_value = True

        # 创建模拟的 mineru 输出
        os.makedirs(os.path.join(output_dir, "test"), exist_ok=True)
        md_path = os.path.join(output_dir, "test", "test.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(
                "<!-- page: 1 -->\n# Test Report\n\nContent of the report\n\n"
                "| Col A | Col B |\n|---|---|\n"
            )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            strategy = MinerUStrategy(backend="pipeline")
            result = strategy.convert("test.pdf")

            assert result.success is True
            assert result.strategy_used == "mineru"
            assert "# Test Report" in result.markdown
            assert result.has_tables is True
            assert result.page_count >= 1
            assert result.quality_score is not None

    @patch("ingestion.converters.mineru.HAS_MINERU", True)
    @patch("ingestion.converters.mineru.os.path.exists")
    @patch("ingestion.converters.mineru.tempfile.mkdtemp")
    def test_convert_error(self, mock_mkdtemp, mock_exists, tmp_path):
        """测试 mineru 执行失败"""
        output_dir = str(tmp_path / "mineru_error")
        os.makedirs(output_dir, exist_ok=True)
        mock_mkdtemp.return_value = output_dir
        mock_exists.return_value = True

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("MinerU CLI crashed")

            strategy = MinerUStrategy(backend="pipeline")
            result = strategy.convert("test.pdf")

            assert result.success is False
            assert result.error_message != ""
