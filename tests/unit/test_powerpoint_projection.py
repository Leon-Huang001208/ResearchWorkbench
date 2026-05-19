"""Tests for PowerPointProjection."""
from pathlib import Path
from unittest.mock import patch

import pytest

from core.contracts import SectionOutput, TableSpec
from reporting.projections.powerpoint import PowerPointProjection


class TestPowerPointProjection:
    """Test suite for PowerPointProjection."""

    @pytest.fixture
    def pptx_available(self) -> bool:
        """Check if python-pptx is available."""
        try:
            import pptx
            from pptx import Presentation

            return True
        except ImportError:
            return False

    @pytest.mark.skipif(
        not PowerPointProjection()._check_pptx(), reason="python-pptx not installed"
    )
    def test_save_to_file(self, tmp_path):
        """Test saving PowerPoint to a file."""
        projection = PowerPointProjection()
        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Test content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        output_file = tmp_path / "report.pptx"

        projection.save(output_file, "Test Report", sections)

        assert output_file.exists()

    def test_save_with_metadata(self, tmp_path):
        """Test saving with metadata."""
        projection = PowerPointProjection()
        if not projection._check_pptx():
            pytest.skip("python-pptx not installed")

        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Test content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        metadata = {"author": "Test Author"}
        output_file = tmp_path / "report.pptx"

        projection.save(output_file, "Test Report", sections, metadata=metadata)
        assert output_file.exists()

    def test_save_with_warnings(self, tmp_path):
        """Test saving with warnings."""
        projection = PowerPointProjection()
        if not projection._check_pptx():
            pytest.skip("python-pptx not installed")

        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Content",
                evidence_refs=[],
                warnings=["Warning 1"],
            )
        ]
        output_file = tmp_path / "report.pptx"

        projection.save(output_file, "Test Report", sections)
        assert output_file.exists()

    def test_save_raises_when_pptx_not_installed(self, tmp_path):
        """Test that it raises ImportError when python-pptx is not available."""
        projection = PowerPointProjection()
        projection._has_pptx = False

        sections = [
            SectionOutput(
                key="test",
                title="Test Section",
                content="Content",
                evidence_refs=[],
                warnings=[],
            )
        ]
        output_file = tmp_path / "report.pptx"

        with pytest.raises(ImportError):
            projection.save(output_file, "Test Report", sections)

    def test_check_pptx_handles_import_error(self):
        """Test that _check_pptx handles import errors gracefully."""
        projection = PowerPointProjection()

        with patch("reporting.projections.powerpoint.PPTX_AVAILABLE", False):
            # Create a new projection instance with the mocked state
            projection._has_pptx = False
            result = projection._check_pptx()
            assert result is False


class TestPowerPointProjectionFromTemplate:
    """测试从模板生成 PowerPoint 演示文稿"""

    @pytest.fixture
    def pptx_available(self) -> bool:
        """检查 python-pptx 是否可用"""
        try:
            import pptx
            from pptx import Presentation

            return True
        except ImportError:
            return False

    def create_test_template(self, tmp_path) -> Path:
        """创建测试用的 PowerPoint 模板文件"""
        from pptx import Presentation

        template_path = tmp_path / "template.pptx"
        prs = Presentation()

        # Title slide
        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "Report Title: {{title}}"

        # Content slide
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        slide.shapes.title.text = "Executive Summary"
        slide.placeholders[1].text = "{{summary}}"

        prs.save(template_path)
        return template_path

    @pytest.mark.skipif(
        not PowerPointProjection()._check_pptx(), reason="python-pptx not installed"
    )
    def test_save_from_template(self, tmp_path):
        """测试从模板保存"""

        projection = PowerPointProjection()

        # 创建测试模板
        template_path = self.create_test_template(tmp_path)
        output_path = tmp_path / "output.pptx"

        # 创建章节输出
        sections = [
            SectionOutput(
                key="title",
                title="Title",
                content="Q2 Investment Report",
                evidence_refs=[],
                warnings=[],
            ),
            SectionOutput(
                key="summary",
                title="Summary",
                content="Market performed well this quarter.",
                evidence_refs=[],
                warnings=[],
            ),
        ]

        # 创建占位符映射
        placeholders = {
            "title": "Q2 Investment Report",
            "summary": "Market performed well this quarter.",
        }

        # 从模板保存
        projection.save_from_template(
            output_path,
            template_path,
            sections,
            placeholders=placeholders,
        )

        assert output_path.exists()

    @pytest.mark.skipif(
        not PowerPointProjection()._check_pptx(), reason="python-pptx not installed"
    )
    def test_save_from_template_with_tables(self, tmp_path):
        """测试从模板保存并添加表格"""

        projection = PowerPointProjection()

        # 创建测试模板
        template_path = self.create_test_template(tmp_path)
        output_path = tmp_path / "output_with_table.pptx"

        # 创建表格规范
        table = TableSpec(
            table_id="metrics",
            title="Key Metrics",
            headers=["Metric", "Value"],
            rows=[["Revenue", "$10M"], ["Profit", "$2M"]],
        )

        # 从模板保存
        projection.save_from_template(
            output_path,
            template_path,
            sections=[],
            placeholders={"title": "Test", "summary": "Test"},
            tables=[table],
        )

        assert output_path.exists()

    def test_save_from_template_raises_when_file_not_found(self, tmp_path):
        """测试模板文件不存在时抛出异常"""
        projection = PowerPointProjection()
        if not projection._check_pptx():
            pytest.skip("python-pptx not installed")

        template_path = tmp_path / "non_existent.pptx"
        output_path = tmp_path / "output.pptx"

        with pytest.raises(FileNotFoundError):
            projection.save_from_template(output_path, template_path, [])

    def test_save_from_template_raises_when_pptx_not_installed(self, tmp_path):
        """测试 python-pptx 未安装时抛出异常"""
        projection = PowerPointProjection()
        projection._has_pptx = False

        template_path = tmp_path / "template.pptx"
        output_path = tmp_path / "output.pptx"

        with pytest.raises(ImportError):
            projection.save_from_template(output_path, template_path, [])
