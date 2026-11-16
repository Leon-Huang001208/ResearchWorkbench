"""Deterministic PNG and presentation projections of the canonical report blocks."""

import re
from io import BytesIO
from pathlib import Path
from textwrap import TextWrapper
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def png_bytes(blocks):
    from PIL import Image, ImageDraw, ImageFont

    font_path = Path(__file__).with_name("fonts") / "NotoSansSC-Regular.ttf"
    fonts = {
        True: ImageFont.truetype(str(font_path), 32),
        False: ImageFont.truetype(str(font_path), 24),
    }
    wrappers = {True: TextWrapper(width=38), False: TextWrapper(width=50)}
    height = 60
    lines = []
    for text, heading in blocks:
        for paragraph in text.splitlines() or [""]:
            for line in wrappers[heading].wrap(paragraph) or [""]:
                lines.append((line, heading, height))
                height += 50 if heading else 38
                if height > 14_000:
                    raise ValueError("research_png_page_limit")
        height += 12
    image = Image.new("RGB", (1400, height + 48), "white")
    draw = ImageDraw.Draw(image)
    for line, heading, y in lines:
        if draw.textlength(line, font=fonts[heading]) > 1280:
            raise ValueError("research_png_line_limit")
        draw.text((60, y), line, font=fonts[heading], fill="#17263a" if heading else "#273547")
    result = BytesIO()
    image.save(result, format="PNG")
    return result.getvalue()


def pptx_bytes(blocks):
    from copy import deepcopy

    from lxml import etree

    draw = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    slides = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    relation_id = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    relationships = "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
    content_type = "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
    slide_type = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
    template = Path(__file__).parent.parent / "office-template.pptx"
    if template.is_symlink() or not template.is_file():
        raise ValueError("research_pptx_template_missing")

    wrapper = TextWrapper(width=40)
    lines = []
    for text, heading in blocks:
        for paragraph in text.splitlines() or [""]:
            lines.extend((line, heading) for line in (wrapper.wrap(paragraph) or [""]))
        lines.append(("", False))
        if len(lines) > 700:
            raise ValueError("research_pptx_slide_limit")

    result = BytesIO()
    with ZipFile(template) as source, ZipFile(result, "w") as package:

        def xml(name):
            return etree.fromstring(source.read(name))

        def write(name, data):
            entry = ZipInfo(name)
            entry.compress_type = ZIP_DEFLATED
            if not isinstance(data, bytes):
                data = etree.tostring(data, encoding="UTF-8", xml_declaration=True)
            package.writestr(entry, data)

        presentation = xml("ppt/presentation.xml")
        order = presentation.find(slides + "sldIdLst")
        order.clear()
        links = xml("ppt/_rels/presentation.xml.rels")
        for link in list(links):
            if link.get("Type", "").endswith("/slide"):
                links.remove(link)
        types = xml("[Content_Types].xml")
        for kind in list(types):
            if kind.get("ContentType") == slide_type:
                types.remove(kind)
        layout = source.read("ppt/slides/_rels/slide2.xml.rels")
        for i, start in enumerate(range(0, len(lines), 10), 1):
            identifier = f"rIdSlide{i}"
            target = f"slides/slide{i}.xml"
            node = etree.SubElement(order, slides + "sldId", id=str(255 + i))
            node.set(relation_id, identifier)
            etree.SubElement(
                links,
                relationships,
                Id=identifier,
                Target=target,
                Type=relation_id.split("}")[0][1:] + "/slide",
            )
            etree.SubElement(types, content_type, PartName="/ppt/" + target, ContentType=slide_type)

            slide = xml("ppt/slides/slide2.xml")
            title, body = slide.findall(f".//{slides}sp/{slides}txBody")
            title.find(f".//{draw}t").text = f"研究报告 · {i}"
            prototype = body.find(draw + "p")
            body.remove(prototype)
            for text, heading in lines[start : start + 10]:
                paragraph = deepcopy(prototype)
                style = paragraph.find(f".//{draw}rPr")
                style.set("sz", "2200" if heading else "1800")
                style.set("b", "1" if heading else "0")
                # Report text is inserted only as text nodes, never as XML or fields.
                paragraph.find(f".//{draw}t").text = text or " "
                body.append(paragraph)
            write("ppt/" + target, slide)
            write(f"ppt/slides/_rels/slide{i}.xml.rels", layout)

        changed = {
            "[Content_Types].xml": types,
            "ppt/presentation.xml": presentation,
            "ppt/_rels/presentation.xml.rels": links,
        }
        for name in source.namelist():
            if not re.fullmatch(r"ppt/slides/(?:_rels/)?slide\d+\.xml(?:\.rels)?", name):
                write(name, changed[name] if name in changed else source.read(name))
    return result.getvalue()
