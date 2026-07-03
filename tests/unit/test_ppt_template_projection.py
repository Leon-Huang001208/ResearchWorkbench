"""Tests for static PPT template projection."""
from pathlib import Path
import zipfile

from reporting.projections.ppt import PPTTemplateProjection, extract_pptx_placeholders


def write_minimal_pptx(path: Path, slide_text: str) -> None:
    """Write a tiny PPTX package with a single slide text box."""
    slide_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:txBody>
          <a:bodyPr/><a:lstStyle/>
          <a:p><a:r><a:t>{slide_text}</a:t></a:r></a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/slides/slide1.xml", slide_xml)


def write_split_placeholder_pptx(path: Path) -> None:
    """Write a PPTX where one placeholder is split across text runs."""
    slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
       xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
      <p:sp>
        <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
        <p:txBody>
          <a:bodyPr/><a:lstStyle/>
          <a:p>
            <a:r><a:t>{{</a:t></a:r>
            <a:r><a:t>product_name</a:t></a:r>
            <a:r><a:t>}}</a:t></a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("ppt/slides/slide1.xml", slide_xml)


def read_slide_text(path: Path) -> str:
    """Return the raw slide XML text for assertions."""
    with zipfile.ZipFile(path) as archive:
        return archive.read("ppt/slides/slide1.xml").decode("utf-8")


def test_extract_pptx_placeholders_keeps_first_seen_order(tmp_path: Path):
    """PPT 占位符扫描应按首次出现顺序去重。"""
    template = tmp_path / "template.pptx"
    write_minimal_pptx(template, "{{title}} / {{period}} / {{title}}")

    assert extract_pptx_placeholders(template) == ["title", "period"]


def test_ppt_template_projection_replaces_static_text_placeholders(tmp_path: Path):
    """PPT 模板投影应替换文本占位符并保留 pptx 包结构。"""
    template = tmp_path / "template.pptx"
    output = tmp_path / "output.pptx"
    write_minimal_pptx(template, "标题：{{title}}，期间：{{period}}")

    result = PPTTemplateProjection().save_from_template(
        output_path=output,
        template_path=template,
        placeholders={"title": "华安ETF月报", "period": "2026年4月"},
    )

    assert output.exists()
    assert result.replaced_count == 2
    slide_xml = read_slide_text(output)
    assert "{{title}}" not in slide_xml
    assert "{{period}}" not in slide_xml
    assert "华安ETF月报" in slide_xml
    assert "2026年4月" in slide_xml


def test_ppt_projection_handles_placeholders_split_across_runs(tmp_path: Path):
    """PowerPoint 拆分富文本 run 时仍应识别并替换占位符。"""
    template = tmp_path / "template.pptx"
    output = tmp_path / "output.pptx"
    write_split_placeholder_pptx(template)

    assert extract_pptx_placeholders(template) == ["product_name"]

    result = PPTTemplateProjection().save_from_template(
        output_path=output,
        template_path=template,
        placeholders={"product_name": "科创芯片ETF"},
    )

    assert result.replaced_count == 1
    slide_xml = read_slide_text(output)
    assert "科创芯片ETF" in slide_xml
    assert "product_name" not in slide_xml
