"""测试 PDF 转换输出持久化"""

from pathlib import Path
from unittest.mock import patch

from core.settings.config import Settings


def _make_settings(markdown_dir, raw_text_dir):
    """创建带临时目录的测试 Settings"""
    return Settings(
        PDF_MARKDOWN_DIR=Path(markdown_dir),
        PDF_RAW_TEXT_DIR=Path(raw_text_dir),
    )


class TestPersistence:
    """测试持久化函数"""

    def test_sanitize_filename_normal(self):
        from ingestion.converters.persistence import _sanitize_filename

        assert _sanitize_filename("pdf_001") == "pdf_001"
        assert _sanitize_filename("conv_abc123def456") == "conv_abc123def456"

    def test_sanitize_filename_special_chars(self):
        from ingestion.converters.persistence import _sanitize_filename

        result = _sanitize_filename("file/with\\slashes:and*stuff")
        assert "/" not in result
        assert "\\" not in result
        assert ":" not in result
        assert "*" not in result

    def test_sanitize_filename_all_special(self):
        from ingestion.converters.persistence import _sanitize_filename

        result = _sanitize_filename("/*?:<>|")
        assert result == "unnamed"

    def test_persist_markdown(self, tmp_path):
        from ingestion.converters.persistence import persist_markdown

        md_dir = tmp_path / "markdown"
        raw_dir = tmp_path / "raw_text"

        with patch("ingestion.converters.persistence.settings", _make_settings(md_dir, raw_dir)):
            path = persist_markdown("pdf_test_001", "# Hello\n\nWorld")

        assert path == str(md_dir / "pdf_test_001.md")
        assert md_dir.exists()
        assert (md_dir / "pdf_test_001.md").exists()

        content = (md_dir / "pdf_test_001.md").read_text()
        assert "# Hello" in content
        assert "World" in content

    def test_persist_raw_text(self, tmp_path):
        from ingestion.converters.persistence import persist_raw_text

        md_dir = tmp_path / "markdown"
        raw_dir = tmp_path / "raw_text"

        with patch("ingestion.converters.persistence.settings", _make_settings(md_dir, raw_dir)):
            path = persist_raw_text("pdf_test_002", "Plain text content")

        assert path == str(raw_dir / "pdf_test_002.txt")
        assert (raw_dir / "pdf_test_002.txt").exists()

        content = (raw_dir / "pdf_test_002.txt").read_text()
        assert content == "Plain text content"

    def test_should_inline_small(self):
        from ingestion.converters import persistence as pmod

        small = "Hello"
        result = pmod.should_inline(small)
        assert result is True

    def test_should_inline_large(self):
        from ingestion.converters.persistence import should_inline

        big = "x" * (257 * 1024)
        result = should_inline(big)
        assert result is False

    def test_read_markdown_not_exists(self, tmp_path):
        from ingestion.converters.persistence import read_markdown

        md_dir = tmp_path / "markdown"
        raw_dir = tmp_path / "raw_text"

        with patch("ingestion.converters.persistence.settings", _make_settings(md_dir, raw_dir)):
            result = read_markdown("nonexistent")

        assert result is None

    def test_read_raw_text_not_exists(self, tmp_path):
        from ingestion.converters.persistence import read_raw_text

        md_dir = tmp_path / "markdown"
        raw_dir = tmp_path / "raw_text"

        with patch("ingestion.converters.persistence.settings", _make_settings(md_dir, raw_dir)):
            result = read_raw_text("nonexistent")

        assert result is None

    def test_delete_outputs(self, tmp_path):
        from ingestion.converters.persistence import (
            delete_outputs,
            persist_markdown,
            persist_raw_text,
        )

        md_dir = tmp_path / "markdown"
        raw_dir = tmp_path / "raw_text"

        test_settings = _make_settings(md_dir, raw_dir)
        with patch("ingestion.converters.persistence.settings", test_settings):
            persist_markdown("pdf_del_001", "# Test")
            persist_raw_text("pdf_del_001", "Text")

            assert (md_dir / "pdf_del_001.md").exists()
            assert (raw_dir / "pdf_del_001.txt").exists()

            delete_outputs("pdf_del_001")

            assert (md_dir / "pdf_del_001.md").exists() is False
            assert (raw_dir / "pdf_del_001.txt").exists() is False

    def test_output_path_uses_pdf_id(self, tmp_path):
        from ingestion.converters.persistence import _output_path

        path = _output_path("conv_abc123", "md", Path(tmp_path))
        assert path.name == "conv_abc123.md"
        assert path.parent == tmp_path

    def test_persist_creates_parent_dirs(self, tmp_path):
        from ingestion.converters.persistence import persist_markdown

        deep_dir = tmp_path / "a" / "b" / "c"
        raw_dir = tmp_path / "raw_text"

        with patch("ingestion.converters.persistence.settings", _make_settings(deep_dir, raw_dir)):
            path = persist_markdown("pdf_003", "# Deep")

        assert Path(path).exists()
        assert deep_dir.exists()
